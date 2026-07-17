"""Shared port-collision self-healing helpers, used by run_local.py and setup.py.

Only kills a process on a target port if it's clearly identifiable as a
leftover instance of THIS project. Never touches an unrelated process.

Ownership is checked two ways:
1. Command line contains this repo's absolute path or a known entry point.
2. The process's current working directory is inside this repo.

Both checks matter in practice: every service in this project is launched
with `cwd=<service_dir>` and a bare `run.py`/`uvicorn ...` argv (no absolute
path in the command line at all) — verified for real that cmdline-only
matching fails to recognize this exact, realistic case and would wrongly
treat the project's own leftover process as foreign. The cwd check is what
actually catches it.
"""
import shutil
import subprocess
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Substrings that, if found in a process's command line, identify it as
# belonging to this project (kept as a secondary signal alongside cwd).
OWN_PROJECT_MARKERS = [
    str(REPO_ROOT),
    "monolith/run.py",
    "user-service/run.py",
    "product-service/run.py",
    "order-service/run.py",
    "bff/app/main.py",
    "uvicorn app.main:app",
]


def _pids_on_port(port: int) -> list[int]:
    if shutil.which("lsof") is None:
        print(f"  ! 'lsof' not found — cannot check port {port} for leftover processes.")
        return []
    try:
        out = subprocess.run(
            ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
            capture_output=True, text=True, timeout=5,
        )
    except subprocess.SubprocessError:
        return []
    return [int(pid) for pid in out.stdout.split() if pid.strip().isdigit()]


def _cmdline(pid: int) -> str:
    try:
        out = subprocess.run(["ps", "-p", str(pid), "-o", "command="], capture_output=True, text=True, timeout=5)
        return out.stdout.strip()
    except subprocess.SubprocessError:
        return ""


def _cwd(pid: int) -> str:
    """Process's current working directory, via `lsof -d cwd` (portable across
    macOS/Linux without adding a psutil dependency to this stdlib-only script,
    which is invoked with plain `python3.12`, not a project venv)."""
    try:
        out = subprocess.run(
            ["lsof", "-a", "-d", "cwd", "-p", str(pid), "-Fn"],
            capture_output=True, text=True, timeout=5,
        )
    except subprocess.SubprocessError:
        return ""
    for line in out.stdout.splitlines():
        if line.startswith("n"):
            return line[1:]
    return ""


def _is_own_process(cmdline: str, cwd: str = "") -> bool:
    if cwd and cwd.startswith(str(REPO_ROOT)):
        return True
    return any(marker in cmdline for marker in OWN_PROJECT_MARKERS)


def ensure_port_free(port: int, service_name: str) -> None:
    """Detects a leftover instance of THIS project on `port` and cleans it up.
    Raises RuntimeError with an actionable message if the port is occupied by
    something else, or still busy after a clean shutdown attempt."""
    pids = _pids_on_port(port)
    if not pids:
        return

    print(f"  Port {port} ({service_name}) is in use by PID(s) {pids} — checking ownership…")

    # Snapshot every PID's ownership up front. Killing one PID (e.g. a Flask
    # reloader's parent) can cascade-kill a child sharing the same port, so
    # checking lazily one-by-one would see empty info for an already-dead
    # child and wrongly treat it as an unrecognized process.
    identities = {pid: (_cmdline(pid), _cwd(pid)) for pid in pids}
    for pid, (cmdline, cwd) in identities.items():
        if cmdline and not _is_own_process(cmdline, cwd):
            raise RuntimeError(
                f"Port {port} needed for {service_name} is occupied by PID {pid} "
                f"('{cmdline}', cwd='{cwd}'), which is not this project's own process. "
                f"Find and stop it manually, e.g.: lsof -nP -iTCP:{port} -sTCP:LISTEN"
            )

    for pid, (cmdline, _cwd_val) in identities.items():
        if not cmdline:
            continue  # already gone (e.g. cascade-killed with its parent)
        print(f"    PID {pid} looks like a leftover {service_name} from a previous run — stopping it.")
        subprocess.run(["kill", "-TERM", str(pid)])

    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        if not _pids_on_port(port):
            print(f"    Port {port} is now free.")
            return
        time.sleep(0.3)

    remaining = _pids_on_port(port)
    for pid in remaining:
        print(f"    PID {pid} still alive after SIGTERM — sending SIGKILL.")
        subprocess.run(["kill", "-KILL", str(pid)])

    time.sleep(0.5)
    if _pids_on_port(port):
        raise RuntimeError(
            f"Port {port} for {service_name} is still busy after attempting cleanup. "
            f"Inspect manually: lsof -nP -iTCP:{port} -sTCP:LISTEN"
        )
