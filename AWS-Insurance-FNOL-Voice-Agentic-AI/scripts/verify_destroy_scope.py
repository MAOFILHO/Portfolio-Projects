"""Assert that nothing destroyable can reach the protected telephony stack.

Constraint 16 and Phase 8 Stage 1. Releasing the claimed DID `+14169871547` risks a **180-day claim
block** -- the only irreversible action in this project. Four things protect it, and this script checks
the three that are checkable statically:

  1. `prevent_destroy = true` on the phone-number resource.
  2. A state key distinct from every other stack, so no other stack's destroy can take it.
  3. No Makefile target references the telephony directory.

The fourth -- the import guard asserting `Protected=true` -- is checked by running Terraform, and was
demonstrated by failing it deliberately in a scratch copy (Phase 8 criterion 3).

**Why this exists at all.** The build plan's wording: *"A CI check greps the destroy target for it,
because 'we know not to' is not a control."* Today there is no `destroy` target, so item 3 passes
vacuously -- and that is exactly when a check like this has to be written, because the moment the target
appears is the moment nobody is looking. The check is written against ANY target, not only one named
`destroy`, so it does not depend on guessing what the dangerous target will be called.

Free: reads files, makes no AWS calls.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TELEPHONY = REPO / "infra" / "terraform" / "stacks" / "telephony"
MAKEFILE = REPO / "Makefile"

# The path fragment that must not appear in any Makefile recipe.
TELEPHONY_FRAGMENT = "stacks/telephony"


def _backend_key(main_tf: Path) -> str | None:
    """The `key = "..."` inside a stack's `backend "s3"` block, or None if it has no backend."""
    text = main_tf.read_text()
    block = re.search(r'backend "s3" \{(.*?)\n  \}', text, re.S)
    if block is None:
        return None
    key = re.search(r'key\s*=\s*"([^"]+)"', block.group(1))
    return key.group(1) if key else None


def check_prevent_destroy() -> list[str]:
    """The phone-number resource must carry `prevent_destroy = true`."""
    main_tf = TELEPHONY / "main.tf"
    if not main_tf.exists():
        return [f"{main_tf} does not exist"]
    text = main_tf.read_text()
    if not re.search(r"prevent_destroy\s*=\s*true", text):
        return ["telephony/main.tf has no `prevent_destroy = true`"]
    # Presence is not enough -- it has to be on the phone number, not on some other resource that
    # happens to be in the file. Scope the search to the resource block.
    resource = re.search(r'resource "aws_connect_phone_number".*', text, re.S)
    if resource is None:
        return ["telephony/main.tf declares no aws_connect_phone_number resource"]
    if not re.search(r"prevent_destroy\s*=\s*true", resource.group(0)):
        return [
            "`prevent_destroy = true` exists but not inside the aws_connect_phone_number resource"
        ]
    return []


def check_state_isolation() -> list[str]:
    """Telephony's state key must be unique across every stack in the repo."""
    telephony_key = _backend_key(TELEPHONY / "main.tf")
    if telephony_key is None:
        return [
            "telephony/main.tf has no backend block -- its state is not isolated in the backend"
        ]

    failures = []
    for main_tf in sorted((REPO / "infra" / "terraform").rglob("main.tf")):
        if main_tf.parent == TELEPHONY:
            continue
        other = _backend_key(main_tf)
        if other is not None and other == telephony_key:
            rel = main_tf.relative_to(REPO)
            failures.append(f"{rel} shares telephony's state key '{telephony_key}'")
    return failures


def check_makefile() -> list[str]:
    """No Makefile recipe line may reference the telephony directory."""
    if not MAKEFILE.exists():
        return ["Makefile does not exist"]

    failures = []
    current_target = "(top level)"
    for lineno, line in enumerate(MAKEFILE.read_text().splitlines(), start=1):
        stripped = line.lstrip("\t")
        if line and not line.startswith(("\t", " ", "#")) and ":" in line:
            current_target = line.split(":", 1)[0].strip()
        # Comments are allowed to name it -- the header of the telephony stack and the Makefile's own
        # documentation both do, deliberately. Only executable recipe lines are the hazard.
        if line.startswith("\t") and not stripped.startswith("#"):
            if TELEPHONY_FRAGMENT in line:
                failures.append(
                    f"Makefile:{lineno} target '{current_target}' references {TELEPHONY_FRAGMENT}: "
                    f"{stripped.strip()!r}"
                )
    return failures


def run() -> list[str]:
    return check_prevent_destroy() + check_state_isolation() + check_makefile()


def main() -> int:
    checks = [
        ("prevent_destroy on the phone number", check_prevent_destroy),
        ("telephony state key is unique", check_state_isolation),
        ("no Makefile recipe touches stacks/telephony", check_makefile),
    ]
    failures: list[str] = []
    print("verify-destroy-scope: the protected DID cannot be reached by a destroy\n")
    for label, fn in checks:
        result = fn()
        print(f"  {'ok  ' if not result else 'FAIL'} {label}")
        failures.extend(result)

    if failures:
        print("\nverify-destroy-scope: FAILED")
        for f in failures:
            print(f"  - {f}")
        print(
            "\nReleasing the claimed DID risks a 180-day block. Fix the cause; do not relax the check."
        )
        return 1

    print("\nverify-destroy-scope: passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
