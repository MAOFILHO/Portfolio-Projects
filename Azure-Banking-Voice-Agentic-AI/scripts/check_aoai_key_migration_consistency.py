#!/usr/bin/env python3
"""Phase 7 D2's static check: infra/modules/aoai.bicep may only declare `disableLocalAuth: true`
once AOAI_KEY is gone from the voice agent's source.

Added 2026-09-16, a code-review Spec-axis finding on Phase 7's first two commits: D5 (phone-number
safety) got a real, blocking CI check; D2 (retire AOAI_KEY) was enforced only by a comment in
aoai.bicep's own header ("THIS MODULE MUST NOT BE DEPLOYED... UNTIL"). A comment cannot fail a build.
This check makes the same rule mechanical, the same way B3's static check and D5's static check
already are for their own constraints.

What it actually checks: `disableLocalAuth` in aoai.bicep must not be `true` while any voice-agent
source file still references `AOAI_KEY`. This is deliberately narrower than "has the migration to
Entra ID auth actually happened and been verified live" -- this check cannot know that (it is a
static scan, not a live call), the same limitation B3's runtime boot guard exists to cover for model
pinning. What it CAN catch, and does: the specific, mechanical failure mode of flipping the Bicep
property to `true` while the code that would break is still sitting right there in the tree. A
`disableLocalAuth: false` (or absent) value always passes regardless of AOAI_KEY's presence -- this
check has nothing to say about the safe, current state, only about the unsafe transition.

Scope: infra/modules/aoai.bicep for the property, and every voice-agent/azbank_voice_agent/**/*.py
file for the AOAI_KEY reference. Not docs/**/*.md or tests/ -- both legitimately name AOAI_KEY as
research record or as the very thing being tested away from, and scanning them would fail this check
for reasons unrelated to what actually ships.

Exit code 0 = clean (disableLocalAuth is not true, or it is true and AOAI_KEY is truly gone),
1 = disableLocalAuth is true while AOAI_KEY still appears in the app's source.
"""
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _scan_utils

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
AOAI_MODULE = REPO_ROOT / "infra" / "modules" / "aoai.bicep"
PACKAGE_ROOT = REPO_ROOT / "voice-agent" / "azbank_voice_agent"

# `disableLocalAuth: true` (or `false`), Bicep property syntax -- a colon, optional whitespace, then
# the literal. Matched against the module's whole text, case-sensitive: Bicep booleans are lowercase.
DISABLE_LOCAL_AUTH_PATTERN = re.compile(r"disableLocalAuth\s*:\s*(true|false)\b")

AOAI_KEY_PATTERN = re.compile(r"\bAOAI_KEY\b")


def aoai_module_declares_local_auth_disabled():
    """True if aoai.bicep's disableLocalAuth is explicitly `true`. Absent or `false` both return
    False -- this check only ever objects to the affirmative, unsafe value."""
    text = AOAI_MODULE.read_text()
    match = DISABLE_LOCAL_AUTH_PATTERN.search(text)
    return bool(match) and match.group(1) == "true"


def scan_targets():
    return sorted(PACKAGE_ROOT.rglob("*.py"))


def main():
    if not aoai_module_declares_local_auth_disabled():
        print(
            "D2 AOAI key-migration consistency check: ok -- "
            "infra/modules/aoai.bicep does not declare disableLocalAuth: true"
        )
        return 0

    violations = []
    for path in scan_targets():
        rel = path.relative_to(REPO_ROOT)
        text = path.read_text()
        for match in AOAI_KEY_PATTERN.finditer(text):
            line = _scan_utils.lineno(text, match.start())
            snippet = _scan_utils.flatten(text.splitlines()[line - 1])
            violations.append((rel, line, "AOAI_KEY referenced", snippet))

    return _scan_utils.report(
        violations,
        title=(
            "D2 AOAI KEY-MIGRATION CONSISTENCY CHECK FAILED -- "
            "infra/modules/aoai.bicep declares disableLocalAuth: true, but AOAI_KEY is still live:"
        ),
        footer=(
            "infra/modules/aoai.bicep's own header names the two-part gate: migrate the realtime "
            "client off AOAI_KEY onto the system-assigned identity, verify a real call on the new "
            "path, then flip disableLocalAuth. Either finish that migration or set it back to false."
        ),
        ok_message=(
            "D2 AOAI key-migration consistency check: ok -- "
            "disableLocalAuth: true and AOAI_KEY is gone from the app's source"
        ),
    )


if __name__ == "__main__":
    sys.exit(main())
