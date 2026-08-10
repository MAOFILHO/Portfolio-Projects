import sys


def test_python_version_is_3_12() -> None:
    assert sys.version_info[:2] == (3, 12), f"Expected Python 3.12, got {sys.version_info[:2]}"
