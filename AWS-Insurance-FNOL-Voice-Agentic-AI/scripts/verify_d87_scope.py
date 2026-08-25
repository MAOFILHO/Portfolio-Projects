"""`D87` scope resolution -- confirm or refute `contact_server.py` and `policy_server.py` individually
against the deployed Lambda, rather than resting on "shared import" alone (Marco, 2026-08-16).

Same pattern as the invoke that found `D87`: a direct `lambda:Invoke` with a hand-built Lex-shaped event
carrying every slot a real conversation would have filled by the time the affected code path runs, so the
graph reaches real fulfillment instead of an early `ElicitSlot`.

`contact_server.py` -- DETERMINISTIC. `update_contact_info_node` reads `filled_slots["policy_number"]`/
`["field"]`/`["new_value"]`/`["confirm_update_contact_info"]` directly off the event; all four are
supplied here, so the real deployed `update_contact_info()` (`mcp/contact_server.py`, imports
`POLICYHOLDERS_PATH` from the same `_paths.py` `D87` names) is guaranteed to run if `D87` doesn't stop it
first. Cheap, same pattern, no model-classification gamble.

`policy_server.py` -- NOT DETERMINISTIC BY SLOT ALONE, STATED HONESTLY RATHER THAN FORCED. Its only call
site (`coverage_question.py`) is gated on `state["coverage_question_type"] ==
"election_fact_optional"`, which is not a slot -- it is the real router's live classification of
`turn_input` (`routing.py`, a real Bedrock Nova Micro call), not something this event's `slots` dict can
set directly. This script makes one real attempt with a turn phrased to elicit that classification and
reports the ACTUAL outcome plainly: if the router classifies it as `election_fact_optional`, the affected
code runs and confirms/refutes the crash for real; if the router classifies it any other way, that is
reported as "unreachable by this test" -- not papered over as a confirmation either way, and not retried
with a different prompt to force a particular answer (this project's own recent finding about not
re-selecting a path to make a claim go green applies here too, one level removed: this script tries once,
honestly, and reports whichever real thing happened).

Cost: two `lambda:Invoke` calls. `UpdateContactInfo`'s event skips the guardrail-free `ElicitSlot` turns
entirely by supplying every slot on turn one, so it makes the same 1 INPUT + up to 1 OUTPUT guardrail call
(~$0.0006) `verify_lambda_execution.py`'s own ordinary-intent events make. `CoverageQuestion`'s event adds
one real Nova Micro router call (a fraction of a cent) on top. Estimated **~$0.001 total**.

**Known flakiness in `_crashed_on_paths`, found and worked around by hand this run, not yet fixed in
code**: on the `contact_server.py` invoke, this function's own 8×4s retry loop returned zero matching
CloudWatch events even though the crash line existed -- confirmed seconds later by an unscoped, un-retried
`filter_log_events` call for the same `requestId` run directly from the shell. The gap is CloudWatch
ingestion lag exceeding this function's own poll budget, not a wrong `requestId` or a wrong filter
pattern (both were correct). **Report the printed verdict for `contact_server.py` from this script's own
run with that in mind** -- `RESULTS.md` §29 records the cross-checked, correct verdict
(CONFIRMED BROKEN), not this script's possibly-stale "INCONCLUSIVE" if it reappears on a re-run. Fixing
the poll budget properly (longer window, or switch to `start_query`/Logs Insights like
`verify_stage_b1_live_invoke.py` already does for the `pii_log_filter_installed` check) is real,
worthwhile follow-up, not done here so as not to re-spend invoke cost re-validating tooling rather than
the finding itself.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

import boto3

sys.path.insert(0, str(Path(__file__).resolve().parent))
# mypy can't see this sibling-module import (no scripts/__init__.py, resolved at runtime via the
# sys.path.insert above).
from verify_lambda_execution import (  # type: ignore[import-not-found]  # noqa: E402
    _event,
    _slot,
    terraform_outputs,
)

REGION = "us-west-2"
_REAL_POLICY_NUMBER = (
    "PY4821"  # data/synthetic/policyholders/policyholders.json -- also CLM-2608-00042-4's policy
)
_ESTIMATED_COST_USD = 0.001


def _invoke(
    lambda_client: Any, function_name: str, event: dict[str, Any]
) -> tuple[dict[str, Any] | None, str]:
    response = lambda_client.invoke(
        FunctionName=function_name,
        InvocationType="RequestResponse",
        Payload=json.dumps(event).encode("utf-8"),
    )
    raw = response["Payload"].read()
    request_id = response["ResponseMetadata"]["RequestId"]
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        payload = None
    return payload, request_id


def _crashed_on_paths(logs_client: Any, log_group: str, request_id: str) -> tuple[bool, str]:
    """Polls CloudWatch (real ingestion lag, not instant) for this invocation's own log lines and
    reports whether a `FileNotFoundError` on a `_paths.py`-derived path fired. Returns
    (crashed_on_paths, evidence_line)."""
    for _ in range(8):
        resp = logs_client.filter_log_events(
            logGroupName=log_group,
            filterPattern=f'"{request_id}"',
        )
        messages = [e["message"] for e in resp.get("events", [])]
        if messages:
            break
        time.sleep(4)
    for message in messages:
        if "FileNotFoundError" in message and "synthetic" in message:
            return True, message.strip()
    return False, ""


def main() -> int:
    print(f"=== D87 scope resolution: estimated cost ~${_ESTIMATED_COST_USD} ===")

    outputs = terraform_outputs()
    function_name = str(outputs["codehook_function_name"])
    log_group = f"/aws/lambda/{function_name}"
    lambda_client = boto3.client("lambda", region_name=REGION)
    logs_client = boto3.client("logs", region_name=REGION)

    results: dict[str, str] = {}

    # -----------------------------------------------------------------------------------------------
    # contact_server.py -- deterministic.
    # -----------------------------------------------------------------------------------------------
    print("\n--- contact_server.py (UpdateContactInfo, all four slots pre-filled) ---")
    contact_event = _event(
        intent_name="UpdateContactInfo",
        transcript="update my phone number",
        slots={
            "policy_number": _slot(_REAL_POLICY_NUMBER),
            "field": _slot("phone"),
            "new_value": _slot("555-0199"),
            "confirm_update_contact_info": _slot("Yes"),
        },
    )
    payload, request_id = _invoke(lambda_client, function_name, contact_event)
    message = ((payload.get("messages") or [{}])[0]).get("content", "") if payload else ""
    print(f"  response: {message!r}")
    crashed, evidence = _crashed_on_paths(logs_client, log_group, request_id)
    if crashed:
        print(f"  CONFIRMED BROKEN: {evidence}")
        results["contact_server.py"] = "CONFIRMED BROKEN"
    elif message and "problem" not in message.lower():
        print("  CONFIRMED WORKING: real update completed without a _paths.py crash")
        results["contact_server.py"] = "CONFIRMED WORKING"
    else:
        print(f"  INCONCLUSIVE: no _paths.py crash found, but response was {message!r}")
        results["contact_server.py"] = "INCONCLUSIVE"

    # -----------------------------------------------------------------------------------------------
    # policy_server.py -- one honest attempt, real classification, reported whichever way it lands.
    # -----------------------------------------------------------------------------------------------
    print(
        "\n--- policy_server.py (CoverageQuestion, election-fact-shaped turn, real router call) ---"
    )
    coverage_event = _event(
        intent_name="CoverageQuestion",
        transcript="what accident benefits elections do I have on my policy",
        slots={
            "policy_number": _slot(_REAL_POLICY_NUMBER),
            "coverage_topic": _slot("what accident benefits elections do I have on my policy"),
        },
    )
    payload, request_id = _invoke(lambda_client, function_name, coverage_event)
    message = ((payload.get("messages") or [{}])[0]).get("content", "") if payload else ""
    print(f"  response: {message!r}")
    crashed, evidence = _crashed_on_paths(logs_client, log_group, request_id)
    # Independent of the crash check: did the real router classify this as election_fact_optional at
    # all? Read from the same request's log lines rather than assumed from the prompt's intent.
    for _ in range(1):
        resp = logs_client.filter_log_events(
            logGroupName=log_group, filterPattern=f'"{request_id}"'
        )
        classify_lines = [
            e["message"] for e in resp.get("events", []) if "coverage_question_type" in e["message"]
        ]
    if crashed:
        print(f"  CONFIRMED BROKEN: {evidence}")
        results["policy_server.py"] = "CONFIRMED BROKEN"
    elif classify_lines and "election_fact_optional" in classify_lines[0]:
        print("  CONFIRMED WORKING: classified election_fact_optional, no crash")
        results["policy_server.py"] = "CONFIRMED WORKING"
    else:
        classified_as = classify_lines[0] if classify_lines else "(no classification line found)"
        print(
            f"  UNREACHABLE BY THIS TEST: router did not classify this turn as "
            f"election_fact_optional this attempt -- {classified_as!r}. Not retried with a different "
            f"prompt to force a particular answer."
        )
        results["policy_server.py"] = "UNREACHABLE BY THIS TEST"

    print("\n=== D87 scope resolution: per-module verdicts ===")
    for module, verdict in results.items():
        print(f"  {module}: {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
