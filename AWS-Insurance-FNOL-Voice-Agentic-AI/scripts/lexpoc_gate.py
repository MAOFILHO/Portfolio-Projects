"""`ADR-007`'s proof-of-concept gate. Phase 8 Stage 2.

`ADR-007` chose nested CloudFormation `AWS::Lex::Bot` over native `aws_lexv2models_*`, and was explicit
that the choice rests on the *absence* of a confirmed defect rather than on a positive confirmation. It
wrote its own mandatory POC into its consequences section:

    Build the smallest `AWS::Lex::Bot` stack that exercises the FNOL intent with
    `PromptAttemptsSpecification` and `DTMFSpecification`, apply it, change a prompt, apply again, and
    confirm the change actually took. If it does not, `ADR-007` is superseded here -- not worked around.

The second apply is the whole test. Provider issue #42147 is a *silent* failure: the first apply looks
fine either way, so a gate that only ever creates has proven nothing.

**Three instruments, at three depths**, because they can disagree and the disagreement is the finding:

  DECLARED   what Terraform rendered into the template, read from `terraform output`.
  DEFINITION what `DescribeSlot` reports for the DRAFT bot -- the artifact.
  RUNTIME    what `RecognizeText` actually says to a caller -- the outcome.

DEFINITION matching DECLARED while RUNTIME lags is a real and reachable state: the locale build is
asynchronous and completes *after* CloudFormation reports success. A gate that stopped at DEFINITION
would be `RESULTS.md` §3.5 again -- a guard that checks the artifact rather than the outcome.

A negative control runs alongside: `police_report_number`'s DTMF `endTimeoutMs` is hardcoded in the
template while `policy_number`'s is templated. An update mechanism that rewrote everything, or one that
reported success while changing nothing, would both look identical to a passing gate if every observed
field moved together.

Cost: `lexv2-models` reads are control-plane and free. Each snapshot makes 3 `RecognizeText` calls at
$0.00075 -- under a cent for the whole gate, logged in `COSTS.md` anyway.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

import boto3

STACK_DIR = Path(__file__).resolve().parents[1] / "infra" / "terraform" / "stacks" / "lexpoc"

REGION = "us-west-2"
LOCALE = "en_US"
DRAFT = "DRAFT"
INTENT = "FileAutoClaim"
TEST_ALIAS = "TSTALIASID"

# The slot under test and the slot held still. Both carry `PromptAttemptsSpecification`; only the first
# has any templated field.
SUBJECT_SLOT = "policy_number"
CONTROL_SLOT = "police_report_number"

# Elicitation order from `docs/phase4/SLOT-DESIGN.md` §1.1, as authored in `bot.yaml.tftpl`.
EXPECTED_SLOT_ORDER = [
    "injuries_present",
    "policy_number",
    "insured_vehicle",
    "loss_datetime",
    "loss_location",
    "loss_type",
    "damage_description",
    "other_party_involved",
    "police_report_filed",
    "police_report_number",
    "driver_name",
]

# Turns that walk a caller from "hello" to the slot under test. Two turns, because `policy_number` is
# priority 2 and safety is asked first -- which is itself worth exercising rather than shortcutting.
PROBE_OPENING = "I need to file a claim"
PROBE_NO_INJURIES = "no"
# Not an assertion. Whether `MessageSelectionStrategy: Ordered` advances to the second message group on a
# retry decides whether Phase 4's "offer the keypad on the FIRST no-match" is expressible declaratively
# or needs the codehook. Recorded as an observation for Stage 3 either way.
PROBE_NO_MATCH = "zzz qqq zzz"


def _terraform_outputs() -> dict[str, Any]:
    """Everything the stack declares. Fails loudly rather than defaulting if it has not been applied."""
    result = subprocess.run(
        ["terraform", "output", "-json"],
        cwd=STACK_DIR,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(
            f"lexpoc-gate: no terraform output in {STACK_DIR}.\n"
            f"Apply the POC stack first.\n{result.stderr.strip()}"
        )
    raw: dict[str, dict[str, Any]] = json.loads(result.stdout)
    return {key: value["value"] for key, value in raw.items()}


def _paginate_slots(models: Any, bot_id: str, intent_id: str) -> list[dict[str, Any]]:
    """Every slot on the intent.

    `ListSlots` returns 10 per page by default and this intent has 11. Reading one page would have
    reported 10 slots and silently omitted `other_party_involved` -- a check that counts an incomplete
    set is worse than no check, because it answers confidently.
    """
    slots: list[dict[str, Any]] = []
    token: str | None = None
    while True:
        kwargs: dict[str, Any] = {
            "botId": bot_id,
            "botVersion": DRAFT,
            "localeId": LOCALE,
            "intentId": intent_id,
            "maxResults": 50,
        }
        if token is not None:
            kwargs["nextToken"] = token
        page = models.list_slots(**kwargs)
        slots.extend(page.get("slotSummaries", []))
        token = page.get("nextToken")
        if token is None:
            return slots


def _dtmf_end_timeout(slot: dict[str, Any], attempt: str) -> int | None:
    """`endTimeoutMs` for one prompt attempt, or None if any level of the nesting is absent.

    Absence returns None rather than a default. A missing DTMF specification and a DTMF specification
    whose timeout happens to equal the expected value must not be indistinguishable.
    """
    attempts = (
        slot.get("valueElicitationSetting", {})
        .get("promptSpecification", {})
        .get("promptAttemptsSpecification", {})
    )
    spec = attempts.get(attempt, {}).get("audioAndDTMFInputSpecification", {})
    dtmf = spec.get("dtmfSpecification")
    if dtmf is None:
        return None
    value = dtmf.get("endTimeoutMs")
    return int(value) if value is not None else None


def read_definition(bot_id: str) -> dict[str, Any]:
    """What the Lex service says the DRAFT bot is. The artifact half."""
    models = boto3.client("lexv2-models", region_name=REGION)

    locale = models.describe_bot_locale(botId=bot_id, botVersion=DRAFT, localeId=LOCALE)

    intents = models.list_intents(botId=bot_id, botVersion=DRAFT, localeId=LOCALE)
    intent_ids = {i["intentName"]: i["intentId"] for i in intents.get("intentSummaries", [])}
    if INTENT not in intent_ids:
        raise SystemExit(f"lexpoc-gate: intent {INTENT} not found on bot {bot_id}")
    intent_id = intent_ids[INTENT]

    intent = models.describe_intent(
        botId=bot_id, botVersion=DRAFT, localeId=LOCALE, intentId=intent_id
    )
    slots = _paginate_slots(models, bot_id, intent_id)
    slot_ids = {s["slotName"]: s["slotId"] for s in slots}

    # `slotPriorities` reference slot IDs, not names, and come back unordered. Resolving them is the
    # only way to check that the elicitation order Phase 4 specified is the order that deployed.
    id_to_name = {v: k for k, v in slot_ids.items()}
    priorities = sorted(intent.get("slotPriorities", []), key=lambda p: int(p["priority"]))
    order = [id_to_name.get(p["slotId"], f"<unknown:{p['slotId']}>") for p in priorities]

    described: dict[str, dict[str, Any]] = {}
    for name in (SUBJECT_SLOT, CONTROL_SLOT):
        if name not in slot_ids:
            raise SystemExit(f"lexpoc-gate: slot {name} not found on intent {INTENT}")
        described[name] = models.describe_slot(
            botId=bot_id,
            botVersion=DRAFT,
            localeId=LOCALE,
            intentId=intent_id,
            slotId=slot_ids[name],
        )

    subject_prompt = described[SUBJECT_SLOT]["valueElicitationSetting"]["promptSpecification"][
        "messageGroups"
    ][0]["message"]["plainTextMessage"]["value"]

    return {
        "locale_status": locale.get("botLocaleStatus"),
        "slot_count": len(slots),
        "slot_order": order,
        "subject_initial_prompt": subject_prompt,
        "subject_retry1_dtmf_end_timeout_ms": _dtmf_end_timeout(described[SUBJECT_SLOT], "Retry1"),
        "subject_retry2_dtmf_end_timeout_ms": _dtmf_end_timeout(described[SUBJECT_SLOT], "Retry2"),
        "control_retry1_dtmf_end_timeout_ms": _dtmf_end_timeout(described[CONTROL_SLOT], "Retry1"),
    }


def read_runtime(bot_id: str) -> dict[str, Any]:
    """What a caller is actually told. The outcome half.

    Three `RecognizeText` calls against the built test alias. This is the only instrument here that can
    tell a stale build from a fresh one, because the definition is what the build reads, not what it
    serves.
    """
    runtime = boto3.client("lexv2-runtime", region_name=REGION)
    session = f"lexpoc-{uuid.uuid4()}"

    def turn(text: str) -> list[str]:
        response = runtime.recognize_text(
            botId=bot_id,
            botAliasId=TEST_ALIAS,
            localeId=LOCALE,
            sessionId=session,
            text=text,
        )
        return [m.get("content", "") for m in response.get("messages", [])]

    opening = turn(PROBE_OPENING)
    at_subject = turn(PROBE_NO_INJURIES)
    after_no_match = turn(PROBE_NO_MATCH)

    return {
        "text_requests": 3,
        "opening_messages": opening,
        "subject_prompt_messages": at_subject,
        "spoken_subject_prompt": at_subject[0] if at_subject else None,
        # Observation, not assertion. See PROBE_NO_MATCH.
        "after_no_match_messages": after_no_match,
    }


def read_tags(bot_arn: str) -> dict[str, str]:
    """Tags actually on the bot.

    Stage 0's finding was that an activated cost allocation tag can propagate to nothing. CloudFormation
    propagates stack-level tags to resources that support them, and "supports them" is a claim about this
    resource type that is cheaper to check than to look up.
    """
    models = boto3.client("lexv2-models", region_name=REGION)
    response = models.list_tags_for_resource(resourceARN=bot_arn)
    tags: dict[str, str] = response.get("tags", {})
    return tags


def snapshot(label: str) -> dict[str, Any]:
    declared = _terraform_outputs()
    bot_id = str(declared["bot_id"])
    bot_arn = str(declared["bot_arn"])
    return {
        "label": label,
        "bot_id": bot_id,
        "declared": {
            "policy_number_initial_prompt": declared["declared_policy_number_initial_prompt"],
            "dtmf_end_timeout_ms": int(declared["declared_dtmf_end_timeout_ms"]),
            "control_dtmf_end_timeout_ms": int(declared["control_dtmf_end_timeout_ms"]),
            "template_sha256": declared["template_sha256"],
        },
        "definition": read_definition(bot_id),
        "runtime": read_runtime(bot_id),
        "tags": read_tags(bot_arn),
    }


def check_snapshot(snap: dict[str, Any]) -> list[str]:
    """Declared == definition == runtime, plus the control and the slot inventory."""
    failures: list[str] = []
    declared = snap["declared"]
    definition = snap["definition"]
    runtime = snap["runtime"]

    if definition["locale_status"] != "Built":
        failures.append(
            f"locale status is {definition['locale_status']}, not Built -- the runtime half of this "
            "snapshot is reading a locale that is still building"
        )

    if definition["subject_initial_prompt"] != declared["policy_number_initial_prompt"]:
        failures.append(
            f"DEFINITION prompt {definition['subject_initial_prompt']!r} != "
            f"DECLARED {declared['policy_number_initial_prompt']!r}"
        )

    if runtime["spoken_subject_prompt"] != declared["policy_number_initial_prompt"]:
        failures.append(
            f"RUNTIME prompt {runtime['spoken_subject_prompt']!r} != "
            f"DECLARED {declared['policy_number_initial_prompt']!r} -- the definition may be current "
            "while the built locale is stale"
        )

    for attempt in ("retry1", "retry2"):
        observed = definition[f"subject_{attempt}_dtmf_end_timeout_ms"]
        if observed != declared["dtmf_end_timeout_ms"]:
            failures.append(
                f"DEFINITION {attempt} dtmf endTimeoutMs {observed} != "
                f"DECLARED {declared['dtmf_end_timeout_ms']}"
            )

    control = definition["control_retry1_dtmf_end_timeout_ms"]
    if control != declared["control_dtmf_end_timeout_ms"]:
        failures.append(
            f"CONTROL slot dtmf endTimeoutMs {control} != {declared['control_dtmf_end_timeout_ms']} -- "
            "a field nothing templated has moved"
        )

    if definition["slot_count"] != len(EXPECTED_SLOT_ORDER):
        failures.append(
            f"{definition['slot_count']} slots deployed, expected {len(EXPECTED_SLOT_ORDER)}"
        )
    if definition["slot_order"] != EXPECTED_SLOT_ORDER:
        failures.append(
            f"slot priority order {definition['slot_order']} != {EXPECTED_SLOT_ORDER} -- "
            "the intent/slot relationship #39948 makes impossible natively did not survive here either"
        )

    return failures


def check_change(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    """The gate proper: the second apply moved what it said it would, and only that.

    Every assertion here is about a DIFFERENCE. `check_snapshot` on the second snapshot alone would pass
    happily against a bot that had never been updated, because it compares the deployment to whatever
    Terraform currently declares -- and after a silent no-op those two disagree, but after a silent
    no-op *plus* a stale `terraform output` they might not.
    """
    failures: list[str] = []

    if before["declared"]["template_sha256"] == after["declared"]["template_sha256"]:
        failures.append(
            "the two snapshots share a template hash -- nothing was changed between them, so this "
            "gate has tested only that a create works, which was never in doubt"
        )

    moved = [
        ("prompt", "subject_initial_prompt"),
        ("retry1 dtmf endTimeoutMs", "subject_retry1_dtmf_end_timeout_ms"),
    ]
    for label, key in moved:
        if before["definition"][key] == after["definition"][key]:
            failures.append(
                f"DEFINITION {label} unchanged across the two applies "
                f"({before['definition'][key]!r}) -- this is #42147's signature: the update reported "
                "success and the deployed bot did not move"
            )

    if before["runtime"]["spoken_subject_prompt"] == after["runtime"]["spoken_subject_prompt"]:
        failures.append(
            f"RUNTIME prompt unchanged across the two applies "
            f"({before['runtime']['spoken_subject_prompt']!r}) -- a caller would still hear the old "
            "wording regardless of what the definition says"
        )

    control_key = "control_retry1_dtmf_end_timeout_ms"
    if before["definition"][control_key] != after["definition"][control_key]:
        failures.append(
            f"CONTROL moved from {before['definition'][control_key]} to "
            f"{after['definition'][control_key]} -- the update changed a field no template did"
        )

    if before["definition"]["slot_order"] != after["definition"]["slot_order"]:
        failures.append("slot priority order changed across the update")

    return failures


def check_removal(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    """Did an element REMOVED from the template actually disappear from the deployed bot?

    A separate question from `check_change`, and the more dangerous one. An update mechanism that merges
    rather than replaces will apply every edit correctly and quietly keep everything you deleted --
    which looks like a working pipeline until the thing you deleted was a prompt you deleted for a
    reason. Measured on the runtime message list, because that is what a caller is exposed to.
    """
    failures: list[str] = []

    was = before["runtime"]["subject_prompt_messages"]
    now = after["runtime"]["subject_prompt_messages"]

    if len(now) >= len(was):
        failures.append(
            f"the subject slot still returns {len(now)} message(s), was {len(was)} -- a message group "
            "removed from the template did not disappear from the deployed bot"
        )

    orphans = [
        m for m in was if m not in now and m != before["declared"]["policy_number_initial_prompt"]
    ]
    if not orphans:
        failures.append(
            "no message was actually removed between these snapshots, so this comparison tested nothing"
        )
    for message in now:
        if message in orphans:
            failures.append(f"removed message still served at runtime: {message!r}")

    return failures


def _report(title: str, failures: list[str]) -> bool:
    print(f"  {'ok  ' if not failures else 'FAIL'} {title}")
    for f in failures:
        print(f"         - {f}")
    return not failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ADR-007 POC gate.")
    parser.add_argument(
        "--record", type=Path, help="write a snapshot of the deployed bot to this path"
    )
    parser.add_argument("--label", default="snapshot", help="label stored inside the snapshot")
    parser.add_argument(
        "--compare",
        nargs=2,
        type=Path,
        metavar=("BEFORE", "AFTER"),
        help="assert the second apply actually reached the deployed bot",
    )
    parser.add_argument(
        "--compare-removal",
        nargs=2,
        type=Path,
        metavar=("BEFORE", "AFTER"),
        help="assert an element deleted from the template actually left the deployed bot",
    )
    args = parser.parse_args(argv)

    ok = True

    if args.record is not None:
        print(f"lexpoc-gate: recording {args.label}\n")
        snap = snapshot(args.label)
        args.record.parent.mkdir(parents=True, exist_ok=True)
        args.record.write_text(json.dumps(snap, indent=2, sort_keys=True) + "\n")
        ok &= _report(f"declared == definition == runtime ({args.label})", check_snapshot(snap))
        print(f"\n  written: {args.record}")
        print(f"  locale:  {snap['definition']['locale_status']}")
        print(f"  prompt:  {snap['runtime']['spoken_subject_prompt']!r}")
        print(f"  tags:    {snap['tags']}")

    if args.compare is not None:
        before = json.loads(args.compare[0].read_text())
        after = json.loads(args.compare[1].read_text())
        print(f"\nlexpoc-gate: {args.compare[0].name} -> {args.compare[1].name}\n")
        ok &= _report("the update reached the deployed bot", check_change(before, after))
        ok &= _report("before: declared == definition == runtime", check_snapshot(before))
        ok &= _report("after:  declared == definition == runtime", check_snapshot(after))

    if args.compare_removal is not None:
        before = json.loads(args.compare_removal[0].read_text())
        after = json.loads(args.compare_removal[1].read_text())
        print(
            f"\nlexpoc-gate: removal {args.compare_removal[0].name} -> {args.compare_removal[1].name}\n"
        )
        ok &= _report("a deleted message group left the deployed bot", check_removal(before, after))

    if args.record is None and args.compare is None and args.compare_removal is None:
        parser.error("nothing to do: pass --record, --compare and/or --compare-removal")

    print("\nlexpoc-gate: " + ("passed" if ok else "FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
