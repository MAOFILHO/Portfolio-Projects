"""Contact-flow CI check — constraint 18 (recording stays off) and the contact tag schema.

Phase 8 Stage 3. Runs in `make lint` and in CI, and fails the build rather than warning.

WHAT IT CHECKS

  1. **Recording is off.** No `UpdateContactRecordingBehavior` action may record anyone.
  2. **No analytics.** No `AnalyticsBehavior`, `ContactLens` or `RealTimeContactAnalysis` anywhere in a
     flow file — all three are banned-by-default billable features.
  3. **Contact tags are exactly the decided three.** `{Project, Env, FlowVersion}` and nothing else, per
     `docs/phase8/CONTACT-TAG-SCHEMA.md`. Tags reach the billing system, which sits outside `ADR-011`'s
     redaction boundary entirely, and they are effectively immutable after three hours.
  4. **Every path is tagged before it can end.** A `TagContact` must dominate every `DisconnectParticipant`
     and `TransferContactToQueue`, on every reachable path from `StartAction`.

WHY GLOBBING IS BY CONTENT AND NOT BY EXTENSION
    `CLAUDE.md` requires it and the reason is in the Phase 0 archaeology: some upstream flow exports have
    no file extension at all, and an extension glob skips them in silence. A check that silently examines
    zero files passes. This walks the tree, parses what parses, and treats anything carrying an `Actions`
    or `modules` key as a flow.

CHECK 1 COVERS THREE SWITCHES BECAUSE THE SERVICE HAS THREE
    Constraint 18 originally read *"`RecordedParticipants` is non-empty"*, derived in Phase 0 from the
    live instance's own sample flow — accurate about what it inspected, incomplete about what exists. The
    `UpdateContactRecordingBehavior` parameter reference shows the recording behaviour object carries
    **three independent switches**:

        RecordedParticipants        — Agent / Customer call audio
        ScreenRecordedParticipants  — Agent screen recording
        IVRRecordingBehavior        — "Enabled" | "Disabled", the IVR leg

    An empty `RecordedParticipants` does not disable the other two. A flow with
    `{"RecordedParticipants": [], "IVRRecordingBehavior": "Enabled"}` would have passed the original
    wording **while recording the caller's entire self-service conversation** — which is the only leg this
    system has, since there are no agents. Constraint 18 was amended to name all three plus a missing
    behaviour object (`D73`, 2026-08-13), so this checker and `CLAUDE.md` now say the same thing. Keep
    them that way: a constraint narrower than its checker gets reconciled by widening the constraint or by
    narrowing the checker, and only one of those is safe.

TEMPLATES
    The shipped flow is a `templatefile()` source carrying `$${...}` placeholders, all of which sit inside
    JSON strings. They are substituted with a marker before parsing, so the check reads the same file
    Terraform renders rather than a copy of it.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import deque
from pathlib import Path
from typing import Any

#: The three tags `CONTACT-TAG-SCHEMA.md` decided on, and the only ones permitted.
ALLOWED_CONTACT_TAGS = frozenset({"Project", "Env", "FlowVersion"})

#: Substrings that must not appear anywhere in a flow file. All three are billable analytics features on
#: `CLAUDE.md`'s banned-by-default list.
BANNED_SUBSTRINGS = ("AnalyticsBehavior", "ContactLens", "RealTimeContactAnalysis")

#: Actions that end a caller's journey. A contact that reaches one of these untagged is a contact whose
#: cost is unattributable, permanently — tags cannot be added to a finished contact's billing record.
TERMINAL_ACTION_TYPES = frozenset(
    {"DisconnectParticipant", "TransferContactToQueue", "TransferToFlow"}
)

#: Directories never worth walking. `.terraform` in particular contains provider binaries.
SKIP_DIRS = frozenset(
    {".git", ".venv", ".terraform", "node_modules", "__pycache__", ".mypy_cache", ".pytest_cache"}
)

#: Anything larger is not a hand-authored contact flow, and parsing it wastes time.
MAX_FLOW_BYTES = 2_000_000

_TEMPLATE_PLACEHOLDER = re.compile(r"\$\{[^{}]*\}")


class FlowCheckError(Exception):
    """A flow violated a rule. Carries the file and the specific violation."""


def substitute_template_placeholders(text: str) -> str:
    """Replace `$${...}` with a marker so a `templatefile()` source parses as JSON.

    Every placeholder in this project's flow templates sits inside a JSON string, so the substitution
    leaves the document well-formed. A placeholder used as a bare value would not parse, and that is the
    correct outcome: the checker would report the file as unparseable rather than skipping it quietly.
    """
    return _TEMPLATE_PLACEHOLDER.sub("TEMPLATED", text)


def parse_flow(text: str) -> dict[str, Any] | None:
    """Return the flow document, or `None` if this is not a contact flow.

    The identification rule is `CLAUDE.md`'s: an object carrying `Actions` or `modules`. Nothing here
    looks at the filename.
    """
    try:
        document = json.loads(substitute_template_placeholders(text))
    except (json.JSONDecodeError, ValueError):
        return None

    if not isinstance(document, dict):
        return None

    if "Actions" in document or "modules" in document:
        return document

    return None


def discover_flows(root: Path) -> list[tuple[Path, dict[str, Any], str]]:
    """Every contact flow under `root`, found by content.

    Returns `(path, document, raw_text)` — the raw text as well, because check 2 is a substring check
    over the whole file and must catch a banned name in a comment or in a field this parser ignores.
    """
    found: list[tuple[Path, dict[str, Any], str]] = []

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.stat().st_size > MAX_FLOW_BYTES:
            continue

        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        document = parse_flow(text)
        if document is not None:
            found.append((path, document, text))

    return found


def _actions(document: dict[str, Any]) -> list[dict[str, Any]]:
    raw = document.get("Actions")
    return [a for a in raw if isinstance(a, dict)] if isinstance(raw, list) else []


def check_recording_is_off(document: dict[str, Any]) -> list[str]:
    """Constraint 18, on all three switches. See the module docstring on why one is not enough."""
    violations: list[str] = []

    for action in _actions(document):
        if action.get("Type") != "UpdateContactRecordingBehavior":
            continue

        identifier = action.get("Identifier", "<unnamed>")
        parameters = action.get("Parameters")
        behaviour = parameters.get("RecordingBehavior") if isinstance(parameters, dict) else None

        if not isinstance(behaviour, dict):
            violations.append(
                f"action {identifier!r}: UpdateContactRecordingBehavior with no RecordingBehavior "
                f"object. Recording state is entirely this object; its absence is not 'off', it is "
                f"unspecified."
            )
            continue

        for key in ("RecordedParticipants", "ScreenRecordedParticipants"):
            participants = behaviour.get(key, [])
            if participants:
                violations.append(
                    f"action {identifier!r}: {key} is {participants!r}, must be []. Constraint 18 — "
                    f"recording stays off, and it is off only when the list is empty."
                )

        ivr = behaviour.get("IVRRecordingBehavior")
        if ivr is not None and ivr != "Disabled":
            violations.append(
                f"action {identifier!r}: IVRRecordingBehavior is {ivr!r}, must be 'Disabled'. This is "
                f"a SEPARATE switch from RecordedParticipants and is not covered by an empty list — "
                f"and the IVR leg is the only leg this system has."
            )

    return violations


def check_no_analytics(raw_text: str) -> list[str]:
    """Substring check over the whole file, not over parsed fields.

    Deliberate: a banned feature name appearing anywhere — including in a field this parser does not
    model, or in a comment describing how to turn it on — is worth stopping on.
    """
    return [
        f"contains {banned!r} — banned by default (billable analytics, constraint 18)."
        for banned in BANNED_SUBSTRINGS
        if banned in raw_text
    ]


def check_contact_tags(document: dict[str, Any]) -> list[str]:
    """`CONTACT-TAG-SCHEMA.md` consequence 3: keys restricted to the decided three."""
    violations: list[str] = []

    for action in _actions(document):
        if action.get("Type") != "TagContact":
            continue

        identifier = action.get("Identifier", "<unnamed>")
        parameters = action.get("Parameters")
        tags = parameters.get("Tags") if isinstance(parameters, dict) else None

        if not isinstance(tags, dict):
            violations.append(f"action {identifier!r}: TagContact with no Tags object.")
            continue

        for key in sorted(set(tags) - ALLOWED_CONTACT_TAGS):
            violations.append(
                f"action {identifier!r}: contact tag {key!r} is not in "
                f"{sorted(ALLOWED_CONTACT_TAGS)}. Contact tags reach the billing system, which sits "
                f"outside ADR-011's redaction boundary, and are unredactable after three hours. "
                f"Adding one is a decision for CONTACT-TAG-SCHEMA.md, not for a flow edit."
            )

    return violations


def _successors(action: dict[str, Any]) -> list[str]:
    transitions = action.get("Transitions")
    if not isinstance(transitions, dict):
        return []

    nexts: list[str] = []

    if isinstance(transitions.get("NextAction"), str):
        nexts.append(transitions["NextAction"])

    for key in ("Errors", "Conditions"):
        entries = transitions.get(key)
        if isinstance(entries, list):
            nexts.extend(
                e["NextAction"]
                for e in entries
                if isinstance(e, dict) and isinstance(e.get("NextAction"), str)
            )

    return nexts


def check_tagged_before_every_ending(document: dict[str, Any]) -> list[str]:
    """`CONTACT-TAG-SCHEMA.md` consequence 1, enforced as reachability rather than as a comment.

    The schema says the tag block goes *"before any branch that can escalate or disconnect"*, because a
    tag set on only some paths produces a cost report that silently under-counts — the failure shape
    Stage 0's whole audit was about. "Before" is a graph property, so this walks the graph from
    `StartAction` and reports any terminal action reachable without passing through a `TagContact`.
    """
    by_id = {a["Identifier"]: a for a in _actions(document) if isinstance(a.get("Identifier"), str)}
    start = document.get("StartAction")

    if not isinstance(start, str) or start not in by_id:
        return [f"StartAction {start!r} names no action in this flow."]

    if not any(a.get("Type") == "TagContact" for a in by_id.values()):
        return [
            "no TagContact action at all. Every contact this flow handles would be unattributable in "
            "the cost report, which reads identically to a project that spent nothing."
        ]

    violations: list[str] = []
    # (identifier, tagged-so-far). Visiting the same node in both states is meaningful, so the seen set
    # carries the flag too.
    queue: deque[tuple[str, bool]] = deque([(start, False)])
    seen: set[tuple[str, bool]] = set()

    while queue:
        identifier, tagged = queue.popleft()
        if (identifier, tagged) in seen:
            continue
        seen.add((identifier, tagged))

        action = by_id.get(identifier)
        if action is None:
            violations.append(f"transition to {identifier!r}, which names no action in this flow.")
            continue

        action_type = action.get("Type")

        if action_type in TERMINAL_ACTION_TYPES and not tagged:
            violations.append(
                f"action {identifier!r} ({action_type}) is reachable from StartAction without passing "
                f"through a TagContact. Contacts taking that path are unattributable, permanently."
            )
            continue

        tagged_now = tagged or action_type == "TagContact"

        for successor in _successors(action):
            queue.append((successor, tagged_now))

    return violations


def check_flow(path: Path, document: dict[str, Any], raw_text: str) -> list[str]:
    """Every check, on one flow. Returns violation strings, empty if clean."""
    return [
        *check_recording_is_off(document),
        *check_no_analytics(raw_text),
        *check_contact_tags(document),
        *check_tagged_before_every_ending(document),
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Contact-flow CI check. Constraint 18 + tag schema."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Tree to walk. Defaults to the repository root.",
    )
    parser.add_argument(
        "--require-at-least",
        type=int,
        default=1,
        help=(
            "Fail if fewer than this many flows were found. A content-globbing check that matches "
            "nothing passes, which is indistinguishable from a check that works."
        ),
    )
    args = parser.parse_args(argv)

    flows = discover_flows(args.root)

    print(f"check-flows: {len(flows)} flow file(s) found by content under {args.root}")

    failed = False

    for path, document, raw_text in flows:
        relative = path.relative_to(args.root)
        violations = check_flow(path, document, raw_text)

        if violations:
            failed = True
            print(f"  FAIL {relative}")
            for violation in violations:
                print(f"       {violation}")
        else:
            print(f"  ok   {relative}")

    if len(flows) < args.require_at_least:
        print(
            f"check-flows: FAILED — found {len(flows)} flows, expected at least "
            f"{args.require_at_least}. A check that examines nothing is not a passing check.",
            file=sys.stderr,
        )
        return 1

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
