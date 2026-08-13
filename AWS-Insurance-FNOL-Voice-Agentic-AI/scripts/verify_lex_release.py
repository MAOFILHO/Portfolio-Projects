"""Read the deployed Lex release back from the service and check it against what Terraform declared.

Phase 8 Stage 3. `make verify-lex`.

WHY THIS EXISTS
    `RESULTS.md` §3.5.1 rule 1: **verify against a service read, not against the apply output.** The apply
    output is Terraform's record of its own request; the read is a fact. Three instances in this project
    now separate the two — Bedrock Guardrails' DRAFT, the guardrail version pin, and Lex's locale build —
    and this stage adds a fourth mechanism that could produce the same shape:

        AWS::Lex::BotVersion, verbatim from its reference: *"If the DRAFT version of this resource hasn't
        changed since you created the last version, Amazon Lex doesn't create a new version, it returns
        the last created version."*

    `release.yaml.tftpl` handles that by putting the bot definition's hash in the version resource's
    CloudFormation logical ID, which forces a republish on a definition change. That is a mechanism, and
    the mechanism has a stated residual hazard. This script is the other half.

WHAT IT CHECKS, AND AGAINST WHICH VERSION
    Everything is read against the version **the alias actually points at**, never against DRAFT. That is
    the whole point: DRAFT is what an apply mutates, and the published version is what a caller reaches.
    A verifier that read DRAFT would agree with Terraform in exactly the cases where the deployment is
    broken.

COST
    All `lexv2-models` control-plane reads. Lex bills per runtime request; these are free. No
    `RecognizeText` here — a runtime probe belongs with the real-call criterion, where it is priced.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import boto3

REPO_ROOT = Path(__file__).resolve().parents[1]
STACK_DIR = REPO_ROOT / "infra" / "terraform" / "stacks" / "main"

#: The slot the declared-value comparison runs against. Chosen because it is the one carrying BOTH a
#: templated prompt string and a templated nested integer, which are the two shapes `ADR-007`'s provider
#: bugs distinguish (#42147 on prompts, #36845 on prompt-attempt settings).
SUBJECT_SLOT = "policy_number"

#: `ListSlots` defaults to a page size of 10 and `FileAutoClaim` has 11 — Stage 2 finding 4.4. An
#: unpaginated read silently drops `driver_name` and reports a clean, wrong answer.
SLOT_PAGE_SIZE = 50

LOCALE_ID = "en_US"


class VerificationError(Exception):
    """A declared value and the deployed value disagree, or a read failed."""


def terraform_outputs(stack_dir: Path = STACK_DIR) -> dict[str, Any]:
    result = subprocess.run(
        ["terraform", f"-chdir={stack_dir}", "output", "-json"],
        capture_output=True,
        text=True,
        check=True,
    )
    return {k: v["value"] for k, v in json.loads(result.stdout).items()}


def _paginate_slots(client: Any, bot_id: str, version: str, intent_id: str) -> list[dict[str, Any]]:
    slots: list[dict[str, Any]] = []
    token: str | None = None

    while True:
        kwargs: dict[str, Any] = {
            "botId": bot_id,
            "botVersion": version,
            "localeId": LOCALE_ID,
            "intentId": intent_id,
            "maxResults": SLOT_PAGE_SIZE,
        }
        if token:
            kwargs["nextToken"] = token

        response = client.list_slots(**kwargs)
        slots.extend(response.get("slotSummaries", []))
        token = response.get("nextToken")

        if not token:
            return slots


def _intent_id(client: Any, bot_id: str, version: str, intent_name: str) -> str:
    response = client.list_intents(botId=bot_id, botVersion=version, localeId=LOCALE_ID)

    for summary in response.get("intentSummaries", []):
        if summary.get("intentName") == intent_name:
            return str(summary["intentId"])

    raise VerificationError(
        f"intent {intent_name!r} is not present in version {version} of bot {bot_id}."
    )


def _dtmf_end_timeout(slot: dict[str, Any]) -> int | None:
    """The nested integer, or `None` if any level of the nesting is absent.

    Never a default. A default here would make "the field is missing" and "the field is 3000" produce the
    same answer, which is the failure this whole script exists to make impossible.
    """
    attempts = (
        slot.get("valueElicitationSetting", {})
        .get("promptSpecification", {})
        .get("promptAttemptsSpecification", {})
    )
    retry1 = attempts.get("Retry1", {})
    dtmf = retry1.get("audioAndDTMFInputSpecification", {}).get("dtmfSpecification", {})
    value = dtmf.get("endTimeoutMs")

    return int(value) if value is not None else None


def _first_prompt(slot: dict[str, Any]) -> str | None:
    groups = (
        slot.get("valueElicitationSetting", {})
        .get("promptSpecification", {})
        .get("messageGroupsList", [])
    )
    if not groups:
        return None

    message = groups[0].get("message", {}).get("plainTextMessage", {}).get("value")
    return str(message) if message is not None else None


def verify(client: Any, outputs: dict[str, Any]) -> list[str]:
    """Every check. Returns failure strings; empty means the deployment matches its declaration."""
    failures: list[str] = []

    bot_id = outputs["bot_id"]
    alias_id = outputs["bot_alias_id"]
    declared_version = str(outputs["bot_version"])

    # 1. The alias, read from the service. This is the object a caller actually reaches.
    alias = client.describe_bot_alias(botId=bot_id, botAliasId=alias_id)
    served_version = str(alias.get("botVersion", ""))

    if alias.get("botAliasStatus") != "Available":
        failures.append(
            f"alias {alias_id} reports status {alias.get('botAliasStatus')!r}, not 'Available'. "
            f"An alias that is not Available cannot serve a call."
        )

    if served_version != declared_version:
        failures.append(
            f"alias {alias_id} serves version {served_version!r}; Terraform's output says "
            f"{declared_version!r}. This is the §3.5.1 rule 2 failure — the apply reported one version "
            f"and the caller reaches another."
        )

    if served_version in ("", "DRAFT"):
        failures.append(
            f"alias {alias_id} points at {served_version!r}. DRAFT is what an apply mutates; a published "
            f"version is what makes a measurement attributable to a configuration."
        )
        return failures

    # 2. The codehook. Without it every turn is Lex's own slot filling with no agent behind it, and
    #    nothing in the control plane looks wrong.
    locale_settings = alias.get("botAliasLocaleSettings", {}).get(LOCALE_ID, {})
    if not locale_settings.get("enabled"):
        failures.append(f"alias {alias_id} does not have locale {LOCALE_ID} enabled.")

    code_hook = locale_settings.get("codeHookSpecification", {}).get("lambdaCodeHook", {})
    if not code_hook.get("lambdaARN"):
        failures.append(
            f"alias {alias_id} has no Lambda code hook on {LOCALE_ID}. The bot would run its own slot "
            f"filling with no agent behind it, and no control-plane read would look wrong."
        )
    elif code_hook["lambdaARN"] != outputs["codehook_function_arn"]:
        failures.append(
            f"alias code hook is {code_hook['lambdaARN']}, not the deployed function "
            f"{outputs['codehook_function_arn']}."
        )

    # 3. The served version's locale is built. Stage 2 finding 4.1's shape, checked on the version rather
    #    than on DRAFT.
    locale = client.describe_bot_locale(botId=bot_id, botVersion=served_version, localeId=LOCALE_ID)
    if locale.get("botLocaleStatus") != "Built":
        failures.append(
            f"version {served_version} locale {LOCALE_ID} reports "
            f"{locale.get('botLocaleStatus')!r}, not 'Built'."
        )

    # 4. The declared values, against the served version's definition.
    intent_id = _intent_id(client, bot_id, served_version, "FileAutoClaim")
    slots = _paginate_slots(client, bot_id, served_version, intent_id)
    by_name = {s["slotName"]: s for s in slots}

    if SUBJECT_SLOT not in by_name:
        failures.append(f"{SUBJECT_SLOT} is not in version {served_version}.")
        return failures

    detail = client.describe_slot(
        botId=bot_id,
        botVersion=served_version,
        localeId=LOCALE_ID,
        intentId=intent_id,
        slotId=by_name[SUBJECT_SLOT]["slotId"],
    )

    served_prompt = _first_prompt(detail)
    if served_prompt != outputs["declared_policy_number_prompt"]:
        failures.append(
            f"{SUBJECT_SLOT} prompt served is {served_prompt!r}; Terraform declared "
            f"{outputs['declared_policy_number_prompt']!r}."
        )

    served_timeout = _dtmf_end_timeout(detail)
    if served_timeout != outputs["declared_dtmf_end_timeout_ms"]:
        failures.append(
            f"{SUBJECT_SLOT} DTMF endTimeoutMs served is {served_timeout!r}; Terraform declared "
            f"{outputs['declared_dtmf_end_timeout_ms']!r}."
        )

    # 5. `D70`'s obfuscation, on the version, across every intent rather than only this one.
    declared_obfuscated = set(outputs.get("declared_obfuscated_slots", []))
    served_obfuscated: set[str] = set()

    for summary in client.list_intents(
        botId=bot_id, botVersion=served_version, localeId=LOCALE_ID
    ).get("intentSummaries", []):
        for slot in _paginate_slots(client, bot_id, served_version, summary["intentId"]):
            slot_detail = client.describe_slot(
                botId=bot_id,
                botVersion=served_version,
                localeId=LOCALE_ID,
                intentId=summary["intentId"],
                slotId=slot["slotId"],
            )
            setting = slot_detail.get("obfuscationSetting", {}).get("obfuscationSettingType")
            if setting and setting != "None":
                served_obfuscated.add(slot["slotName"])

    if served_obfuscated != declared_obfuscated:
        missing = sorted(declared_obfuscated - served_obfuscated)
        extra = sorted(served_obfuscated - declared_obfuscated)
        failures.append(
            f"obfuscated slots disagree. Declared but not served: {missing}. Served but not declared: "
            f"{extra}. `D70` made this a decision; a decision nobody reads back is a preference."
        )

    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--region", default="us-west-2")
    parser.add_argument("--stack-dir", type=Path, default=STACK_DIR)
    args = parser.parse_args(argv)

    try:
        outputs = terraform_outputs(args.stack_dir)
    except subprocess.CalledProcessError as exc:
        print(
            f"verify-lex: could not read terraform outputs — has the stack been applied?\n{exc.stderr}",
            file=sys.stderr,
        )
        return 1

    client = boto3.client("lexv2-models", region_name=args.region)

    try:
        failures = verify(client, outputs)
    except VerificationError as exc:
        print(f"verify-lex: FAILED\n  {exc}", file=sys.stderr)
        return 1

    if failures:
        print("verify-lex: FAILED", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        return 1

    print(
        f"verify-lex: alias {outputs['bot_alias_id']} serves version {outputs['bot_version']}, "
        f"locale Built, code hook attached, declared prompt and DTMF timeout match, "
        f"{len(outputs.get('declared_obfuscated_slots', []))} slots obfuscated as declared."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
