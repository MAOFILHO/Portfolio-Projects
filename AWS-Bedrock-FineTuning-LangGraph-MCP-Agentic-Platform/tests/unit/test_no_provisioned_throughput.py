from pathlib import Path

from bedrock_platform.aws.guards import FORBIDDEN_STRINGS

REPO_ROOT = Path(__file__).resolve().parents[2]
SCAN_DIRS = ["src", "infra", "scripts"]

# guards.py is the canonical, deliberate home of the forbidden-string list itself.
ALLOWED_FILES = {REPO_ROOT / "src" / "bedrock_platform" / "aws" / "guards.py"}


def test_no_provisioned_throughput_strings_present() -> None:
    violations: list[str] = []
    for scan_dir in SCAN_DIRS:
        root = REPO_ROOT / scan_dir
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path in ALLOWED_FILES:
                continue
            try:
                text = path.read_text()
            except (UnicodeDecodeError, OSError):
                continue
            for forbidden in FORBIDDEN_STRINGS:
                if forbidden in text:
                    violations.append(f"{path}: contains {forbidden!r}")

    assert not violations, "Forbidden Provisioned Throughput strings found:\n" + "\n".join(
        violations
    )
