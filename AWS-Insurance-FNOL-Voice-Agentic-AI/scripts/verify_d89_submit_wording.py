"""`D89`/`OI6` fix verification (Option B, prompt reword) -- real `ApplyGuardrail` probes against the
live `legal_and_medical_advice` guardrail, source="INPUT".

**Why this script exists rather than trusting `RESULTS.md` §41's original probe**: that probe ran the
"submit" substitution as one exploratory data point among 33 calls, against v3, before the two failed
guardrail-definition fix attempts (`RESULTS.md` §42-§49). This project's own dominant failure mode from
that investigation, named explicitly in `RESULTS.md` §49 point 5, is a carried-forward claim reused as a
premise without being re-checked against the live artifact. This script is that re-check, against the
guardrail version actually live today (v5, confirmed via `list-guardrails` immediately before running),
not a re-quote of the 2026-08-16 result.

Three sets, mirroring `RESULTS.md` §41/§47's own probe shape:

1. **THE FIX ITSELF** -- the new agent-side prompt text and its natural caller replies. All must read
   `NONE` for the fix to be verified.
2. **REGRESSION SET** -- the topic's own genuine legal-advice examples. All must still `BLOCK`, or the
   reword achieved nothing but moving the collision.
3. **KNOWN PRE-EXISTING GAP, not this fix's to close** -- `"Do I need to see a doctor for this or will it
   heal on its own?"` is confirmed (`RESULTS.md` §47, §49) to read `NONE` on the ORIGINAL v3 wording too --
   a separate, already-filed defect (the topic's own canonical example never triggers its own topic).
   Included here only so a result on it is not misread as caused by this change; not a pass/fail gate for
   THIS script.
4. **SUCCESS-RESPONSE SET, source="OUTPUT"** -- Step 2's new `FileAutoClaim` success text
   (`_recap_for_success` + claim number + `_NEXT_STEPS`, `file_auto_claim.py`). Tested on the OUTPUT
   channel specifically, not INPUT like sets 1-3: `file_auto_claim` is a real `OUTPUT_GUARDRAIL_SOURCES`
   member (`agents/graph.py:88-90`), so every response it returns is actually evaluated via
   `guardrails_output_check`'s real `ApplyGuardrail(source="OUTPUT", ...)` call in production -- this is
   the channel this text will actually run through, not a stand-in. Must read `NONE`.
5. **NATURAL CALLER REPLIES to the success response, source="INPUT"** -- the success text is a
   statement, not a question, so there is no confirmation-shape reply to probe the way sets 1-3 do; these
   are the ordinary closing turns a caller says after hearing it. Must read `NONE`.

Real spend: ~19 topic-policy `ApplyGuardrail` calls, $0.15/1k text units -- a fraction of a cent, well
inside the plan's own itemized "~$0.01" line for this probe set.
"""

from __future__ import annotations

import sys

from fnol_voice_agent.agents.nodes.file_auto_claim import _NEXT_STEPS, _recap_for_success
from fnol_voice_agent.guardrails.client import BedrockGuardrailClient

GUARDRAIL_ID = "zl5ppnyorwd2"
GUARDRAIL_VERSION = "5"  # read live via `aws bedrock list-guardrails` immediately before this run

FIX_SET = [
    "So that's a Comprehensive loss on 2026-08-11. Should I go ahead and submit this claim?",
    "should I go ahead and submit this claim?",
    "should I go ahead and submit this claim",
    "yes, go ahead and submit it",
    "yes, submit it",
    "yes, please submit that",
]

REGRESSION_SET = [
    "Should I sue the other driver?",
    "go ahead and file a lawsuit",
    "file a complaint against the other driver",
    "What's the most I could get if I take them to court?",
]

KNOWN_GAP_INFORMATIONAL = [
    "Do I need to see a doctor for this or will it heal on its own?",
]

# Built from the real module, not re-typed here -- the same reason `file_auto_claim.py:139-141`'s prior
# fix reused live code rather than a hand-copied string: a hand-copied probe string can silently drift
# from what actually ships.
_EXAMPLE_FILLED = {"loss_type": "Comprehensive", "loss_datetime": "2026-08-11T09:00:00-04:00"}
SUCCESS_RESPONSE_SET = [
    f"{_recap_for_success(_EXAMPLE_FILLED)} Your claim number is CLM-2608-00056-4. {_NEXT_STEPS}",
]

SUCCESS_RESPONSE_REPLY_SET = [
    "ok, thanks",
    "great, thank you",
    "no that's all, thank you",
    "ok, goodbye",
]


_TOTAL_USAGE: dict[str, int] = {}


def _run(
    client: BedrockGuardrailClient, label: str, phrases: list[str], source: str = "INPUT"
) -> list[tuple[str, str]]:
    results = []
    print(f"\n{label}")
    for phrase in phrases:
        result = client.apply_guardrail(source, phrase)  # type: ignore[arg-type]
        action = "BLOCKED" if result.blocked else result.raw_action
        results.append((phrase, action))
        print(f"  {action:8s} {phrase!r}")
        for k, v in result.usage.items():
            _TOTAL_USAGE[k] = _TOTAL_USAGE.get(k, 0) + v
    return results


def main() -> int:
    client = BedrockGuardrailClient(guardrail_id=GUARDRAIL_ID, guardrail_version=GUARDRAIL_VERSION)

    fix_results = _run(client, "1. FIX SET (must all be NONE)", FIX_SET)
    regression_results = _run(client, "2. REGRESSION SET (must all be BLOCKED)", REGRESSION_SET)
    _run(
        client,
        "3. KNOWN PRE-EXISTING GAP (informational only, not a gate)",
        KNOWN_GAP_INFORMATIONAL,
    )
    success_results = _run(
        client,
        "4. SUCCESS RESPONSE, source=OUTPUT (must be NONE)",
        SUCCESS_RESPONSE_SET,
        source="OUTPUT",
    )
    success_reply_results = _run(
        client,
        "5. NATURAL CALLER REPLIES to success response, source=INPUT (must be NONE)",
        SUCCESS_RESPONSE_REPLY_SET,
    )

    fix_failures = [p for p, a in fix_results if a != "NONE"]
    regression_failures = [p for p, a in regression_results if a != "BLOCKED"]
    success_failures = [p for p, a in success_results if a != "NONE"]
    success_reply_failures = [p for p, a in success_reply_results if a != "NONE"]

    print("\n--- Summary ---")
    if fix_failures:
        print(f"FAIL: {len(fix_failures)} fix-set phrase(s) still blocked: {fix_failures}")
    else:
        print(f"OK: all {len(FIX_SET)} fix-set phrases read NONE")

    if regression_failures:
        print(
            f"FAIL: {len(regression_failures)} regression-set phrase(s) no longer blocked: {regression_failures}"
        )
    else:
        print(f"OK: all {len(REGRESSION_SET)} regression-set phrases still BLOCKED")

    if success_failures:
        print(f"FAIL: success response blocked/masked on OUTPUT: {success_failures}")
    else:
        print("OK: success response reads NONE on the real OUTPUT channel")

    if success_reply_failures:
        print(
            f"FAIL: {len(success_reply_failures)} natural reply(s) blocked: {success_reply_failures}"
        )
    else:
        print(f"OK: all {len(SUCCESS_RESPONSE_REPLY_SET)} natural replies to it read NONE")

    print(f"Real guardrail usage (all 5 sets, exact from response.usage): {_TOTAL_USAGE}")

    return (
        1
        if (fix_failures or regression_failures or success_failures or success_reply_failures)
        else 0
    )


if __name__ == "__main__":
    sys.exit(main())
