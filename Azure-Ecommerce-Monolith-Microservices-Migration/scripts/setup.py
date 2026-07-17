#!/usr/bin/env python3
"""make setup — installs all dependencies and runs pre-smoke-tests.

No Docker Desktop is used anywhere: this creates one Python 3.12 venv per
Flask service + the FastAPI BFF, and installs frontend npm dependencies.
Containers only exist on Azure (built later via `az acr build`).
"""
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _procutil import ensure_port_free  # noqa: E402

PYTHON_SERVICES = [
    ("monolith", REPO_ROOT / "monolith", 6000),
    ("user-service", REPO_ROOT / "microservices" / "user-service", 5001),
    ("product-service", REPO_ROOT / "microservices" / "product-service", 5002),
    ("order-service", REPO_ROOT / "microservices" / "order-service", 5003),
    ("bff", REPO_ROOT / "bff", 8000),
]
FRONTEND_DIR = REPO_ROOT / "frontend"
FRONTEND_PORT = 5173

MIN_PYTHON = (3, 12)


def find_python312() -> str | None:
    """Resolves an explicit `python3.12` binary to use for every `venv` call
    below, rather than trusting whatever interpreter happened to launch this
    script via `sys.executable` — this way the venv-creation command is
    always literally `python3.12 -m venv .venv`, never an ambiguous alias."""
    candidate = shutil.which("python3.12")
    if candidate:
        return candidate

    # Homebrew on Apple Silicon doesn't always put python3.12 on PATH by default.
    for fallback in ("/opt/homebrew/opt/python@3.12/bin/python3.12", "/usr/local/opt/python@3.12/bin/python3.12"):
        if Path(fallback).exists():
            return fallback

    if sys.version_info[:2] == MIN_PYTHON:
        return sys.executable  # last resort: the interpreter already running this script

    return None


def check_python_version(python_bin: str | None) -> bool:
    if python_bin is None:
        print(
            "[pre-smoke] python3.12 ... FAIL: no python3.12 found on PATH. "
            "Install it (e.g. `brew install python@3.12` on macOS) and try again."
        )
        return False

    result = subprocess.run([python_bin, "--version"], capture_output=True, text=True)
    version_str = result.stdout.strip() or result.stderr.strip()
    print(f"[pre-smoke] Using {python_bin} ({version_str}) for every venv created below ... OK")
    return True


def check_ports_free() -> bool:
    all_ok = True
    for name, _dir, port in PYTHON_SERVICES + [("frontend", FRONTEND_DIR, FRONTEND_PORT)]:
        try:
            ensure_port_free(port, name)
            print(f"[pre-smoke] Port {port} ({name}) ... OK")
        except RuntimeError as exc:
            print(f"[pre-smoke] Port {port} ({name}) ... FAIL: {exc}")
            all_ok = False
    return all_ok


def create_venv_and_install(python312_bin: str, name: str, venv_parent: Path, requirements_file: Path) -> None:
    venv_dir = venv_parent / ".venv"
    venv_python = venv_dir / "bin" / "python"
    print(f"\n=== {name} ===")
    if not venv_python.exists():
        print(f"$ {python312_bin} -m venv {venv_dir}")
        subprocess.run([python312_bin, "-m", "venv", str(venv_dir)], check=True)
    subprocess.run([str(venv_python), "-m", "pip", "install", "--upgrade", "pip", "-q"], check=True)
    subprocess.run(
        [str(venv_python), "-m", "pip", "install", "-r", str(requirements_file), "-q"],
        check=True,
    )
    print(f"{name}: dependencies installed into {venv_dir}")


def install_frontend() -> None:
    print("\n=== frontend ===")
    if shutil.which("npm") is None:
        print("npm not found — install Node.js 18+ before running the frontend.")
        return
    subprocess.run(["npm", "install", "--silent"], cwd=FRONTEND_DIR, check=True)
    print("frontend: npm dependencies installed")


def main() -> int:
    print("=== Pre-setup smoke tests ===")
    python312_bin = find_python312()
    ok = check_python_version(python312_bin)
    ok = check_ports_free() and ok
    if not ok:
        print("\nPre-setup checks failed — fix the issues above before continuing.")
        return 1

    print("\n=== Installing dependencies (no Docker involved) ===")
    create_venv_and_install(python312_bin, "repo-root (dev/test tooling)", REPO_ROOT, REPO_ROOT / "requirements-dev.txt")
    for name, service_dir, _port in PYTHON_SERVICES:
        create_venv_and_install(python312_bin, name, service_dir, service_dir / "requirements.txt")
        # pytest is needed to run each service's own tests/ folder (see Makefile's `test` target)
        pip_bin = service_dir / ".venv" / "bin" / "pip"
        subprocess.run([str(pip_bin), "install", "pytest==8.3.4", "-q"], check=True)
    install_frontend()

    print("\nSetup complete. Run `make run` (or `python scripts/run_local.py`) next.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
