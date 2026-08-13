"""Block until a Lex V2 bot locale has finished building.

Phase 8 Stage 3. Called by `terraform_data.bot_built` between the bot stack and the release stack.

WHY THIS EXISTS
    Stage 2 measured CloudFormation reporting `CREATE_COMPLETE` on an `AWS::Lex::Bot` at 38 s while the
    `en_US` locale was still `Building`; `Built` arrived ~16 s later, on all three applies
    (`docs/phase8/LEXPOC-GATE.md` §4.1). Anything that depends on a built locale — publishing a version,
    associating Connect, a smoke test — can therefore race a green apply.

    `RESULTS.md` §3.5.1 names this as a platform pattern rather than a Lex quirk, on the strength of the
    same shape in Bedrock Guardrails twice: **AWS create/update calls return when the control plane has
    accepted the change, and each service chooses independently when the data plane reflects it.** Rule 3
    of that section is what this script is.

WHY NOT A SLEEP
    A `time_sleep` encodes the 16 s that happened to be measured once. It is wrong on the first slower
    day, and when it is wrong the failure surfaces downstream in `CreateBotVersion` as an error about the
    version rather than about the build. This polls the state the next step actually depends on, and says
    so when it gives up.

FAIL-CLOSED
    `Failed` exits non-zero. Timeout exits non-zero. **An unrecognised status also exits non-zero** — an
    unknown status is not evidence of a built locale, and the expensive failure here is proceeding. Same
    asymmetry as `stacks/telephony`'s import guard and Phase 7's mask-vs-block parser.

COST
    `DescribeBotLocale` is a `lexv2-models` control-plane call. Lex bills per RUNTIME request; control
    plane reads are free. Stage 2 confirmed this against the bill rather than assuming it.
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import Any

import boto3

#: The only status that means the locale can serve traffic and can be published as a version.
BUILT = "Built"

#: Statuses that are legitimately transient. Anything not in here and not `BUILT` stops the run.
IN_PROGRESS = frozenset({"Building", "ReadyExpressTesting", "Creating", "Importing", "Updating"})

#: Terminal failures. Named separately from "unknown" so the error message can say which happened.
FAILED = frozenset({"Failed", "Deleting", "NotBuilt"})

POLL_SECONDS = 3.0


class BuildWaitError(RuntimeError):
    """The locale did not reach `Built`."""


def _describe(client: Any, bot_id: str, locale_id: str) -> dict[str, Any]:
    return dict(
        client.describe_bot_locale(
            botId=bot_id,
            botVersion="DRAFT",
            localeId=locale_id,
        )
    )


def wait_for_built(
    client: Any,
    bot_id: str,
    locale_id: str,
    *,
    timeout: float,
    poll_seconds: float = POLL_SECONDS,
    now: Any = time.monotonic,
    sleep: Any = time.sleep,
) -> float:
    """Poll until the locale reports `Built`. Returns seconds waited.

    `now` and `sleep` are injected so the tests can drive this deterministically without a real clock —
    a test that actually slept would be slow enough that nobody would keep it.
    """
    started = now()
    seen: list[str] = []

    while True:
        response = _describe(client, bot_id, locale_id)
        status = str(response.get("botLocaleStatus", ""))
        seen.append(status)

        if status == BUILT:
            return float(now() - started)

        if status in FAILED:
            reasons = response.get("failureReasons") or []
            raise BuildWaitError(
                f"Locale {locale_id} of bot {bot_id} reported status {status!r}. "
                f"Failure reasons: {reasons or 'none reported'}. "
                f"Statuses seen: {seen}."
            )

        if status not in IN_PROGRESS:
            # Fail-closed on the unknown case. A status this script does not recognise may well be
            # benign, but treating it as benign is how a wait that no longer waits goes unnoticed.
            raise BuildWaitError(
                f"Locale {locale_id} of bot {bot_id} reported an UNRECOGNISED status {status!r}. "
                f"This script fails closed: an unknown status is not evidence of a built locale. "
                f"If {status!r} is a legitimate transient state, add it to IN_PROGRESS in "
                f"scripts/wait_for_lex_build.py — do not remove the check. Statuses seen: {seen}."
            )

        elapsed = float(now() - started)
        if elapsed >= timeout:
            raise BuildWaitError(
                f"Timed out after {elapsed:.0f}s waiting for locale {locale_id} of bot {bot_id} to "
                f"build. Last status {status!r}; statuses seen: {seen}. "
                f"Stage 2 measured this gap at ~16s, so a timeout here means the build has genuinely "
                f"stalled — raising --timeout is unlikely to be the fix."
            )

        sleep(poll_seconds)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bot-id", required=True)
    parser.add_argument("--locale-id", default="en_US")
    parser.add_argument("--region", required=True)
    parser.add_argument("--timeout", type=float, default=600.0)
    args = parser.parse_args(argv)

    client = boto3.client("lexv2-models", region_name=args.region)

    try:
        waited = wait_for_built(client, args.bot_id, args.locale_id, timeout=args.timeout)
    except BuildWaitError as exc:
        print(f"lex build wait: FAILED\n{exc}", file=sys.stderr)
        return 1

    print(f"lex build wait: {args.locale_id} Built after {waited:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
