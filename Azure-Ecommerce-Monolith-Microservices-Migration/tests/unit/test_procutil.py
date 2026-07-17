"""Unit test for the ownership-matching logic in scripts/_procutil.py.

Real leftover-process detection was verified twice against actual processes
during development: once with an unrealistic invocation (cwd=repo root,
`python monolith/run.py`) which passed on cmdline matching alone, and then
against the REAL invocation pattern every script in this project actually
uses (`cwd=<service_dir>`, bare `run.py`/`uvicorn ...` argv with no repo path
in the command line at all) — which cmdline-only matching failed to
recognize. That's why _is_own_process also checks cwd; see CLAUDE.md."""
from _procutil import OWN_PROJECT_MARKERS, REPO_ROOT, _is_own_process


def test_recognizes_own_entry_point_via_cmdline():
    assert _is_own_process("/usr/bin/python3 monolith/run.py") is True


def test_recognizes_own_repo_path_via_cmdline():
    marker = OWN_PROJECT_MARKERS[0]  # the repo root absolute path
    assert _is_own_process(f"/usr/bin/python3 {marker}/bff/app/main.py") is True


def test_recognizes_own_process_via_cwd_when_cmdline_is_generic():
    """The realistic case: cwd=<service_dir>, cmdline is just 'python run.py'
    with no repo path anywhere in it — this is exactly how run_local.py and
    migration_engine.py actually launch every service."""
    generic_cmdline = "/usr/bin/python3 run.py"
    assert _is_own_process(generic_cmdline, cwd="") is False  # cmdline alone: correctly can't tell
    assert _is_own_process(generic_cmdline, cwd=str(REPO_ROOT / "monolith")) is True


def test_rejects_unrelated_process():
    assert _is_own_process("/usr/sbin/some-other-daemon --port 6000", cwd="/var/empty") is False


def test_rejects_empty_cmdline_and_cwd():
    assert _is_own_process("", cwd="") is False
