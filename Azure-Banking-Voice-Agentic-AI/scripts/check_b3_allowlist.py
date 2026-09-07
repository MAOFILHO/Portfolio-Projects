#!/usr/bin/env python3
"""B3's static check: no code path may name a realtime model outside the allowlist.

Deliberately independent of the runtime boot guard (`azbank_voice_agent/boot.py`). The guard
proves what is *deployed* is approved; this proves what is *written down in the source* is
approved. Either alone leaves a gap:

  - guard only: a hardcoded model name somewhere in the package would be invisible until the code
    path that uses it actually ran.
  - static only: source can be correct while the live deployment has silently moved.

docs/PLAN.md, Verification: "CI static check enforces B3's allowlist across the tree."

Scope: the package source only. Tests are excluded on purpose -- test_boot.py has to name
rejected models (`gpt-4o-realtime-preview`, and the 2025-12-15 version of the pinned name) in
order to prove they are rejected. A checker that failed on those would be forbidding the tests
that prove the guard works.

Exit code 0 = clean, 1 = a disallowed model name is present.
"""
import pathlib
import re
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
PACKAGE_ROOT = REPO_ROOT / "voice-agent" / "azbank_voice_agent"

# Anything that looks like a realtime model id, whether or not this project uses it.
MODEL_PATTERN = re.compile(r"\bgpt-[a-z0-9.\-]*realtime[a-z0-9.\-]*\b", re.IGNORECASE)


def allowed_names():
    """The model names B3 permits, read from the guard itself rather than restated here.

    Reading them from the source of truth is the point: a checker carrying its own copy of the
    allowlist would keep passing after the real allowlist changed.
    """
    sys.path.insert(0, str(REPO_ROOT / "voice-agent"))
    from azbank_voice_agent import boot

    return {name for name, _version in boot.ALLOWED_REALTIME_MODELS}


def main():
    permitted = allowed_names()
    violations = []

    for path in sorted(PACKAGE_ROOT.rglob("*.py")):
        for lineno, line in enumerate(path.read_text().splitlines(), start=1):
            for match in MODEL_PATTERN.finditer(line):
                if match.group(0) not in permitted:
                    violations.append((path.relative_to(REPO_ROOT), lineno, match.group(0), line.strip()))

    if violations:
        print("B3 STATIC CHECK FAILED -- realtime model named outside the allowlist:\n")
        for path, lineno, found, line in violations:
            print(f"  {path}:{lineno}: {found!r}")
            print(f"      {line}")
        print(f"\nAllowed model names: {sorted(permitted)}")
        print("Change the allowlist in azbank_voice_agent/boot.py deliberately, or fix the code path.")
        return 1

    print(f"B3 static check: ok -- every realtime model named in the package is allowlisted {sorted(permitted)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
