#!/usr/bin/env python3
"""make run — launches the full local stack as plain Python/Node processes.

No Docker Desktop, no containers. By default only the monolith + BFF +
frontend start (the "before" state) — the three microservices start live
when you click "Start Migration" on the Migrate page. Pass --all to start
every service immediately (useful for testing/benchmarking outside the
guided migration flow).
"""
import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _procutil import ensure_port_free  # noqa: E402

import urllib.request  # noqa: E402
import urllib.error  # noqa: E402

MONOLITH_DIR = REPO_ROOT / "monolith"
BFF_DIR = REPO_ROOT / "bff"
FRONTEND_DIR = REPO_ROOT / "frontend"
MICROSERVICES_DIR = REPO_ROOT / "microservices"

MONOLITH_PORT = int(os.environ.get("MONOLITH_PORT", 6000))
BFF_PORT = int(os.environ.get("BFF_PORT", 8000))
FRONTEND_PORT = int(os.environ.get("FRONTEND_PORT", 5173))
USER_SERVICE_PORT = int(os.environ.get("USER_SERVICE_PORT", 5001))
PRODUCT_SERVICE_PORT = int(os.environ.get("PRODUCT_SERVICE_PORT", 5002))
ORDER_SERVICE_PORT = int(os.environ.get("ORDER_SERVICE_PORT", 5003))

processes: list[subprocess.Popen] = []


def _venv_python(service_dir: Path) -> str:
    venv_python = service_dir / ".venv" / "bin" / "python"
    return str(venv_python) if venv_python.exists() else sys.executable


def _wait_for_health(url: str, timeout: float = 20.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    return True
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            pass
        time.sleep(0.5)
    return False


def start_flask_service(name: str, service_dir: Path, port: int, port_env_var: str) -> subprocess.Popen:
    ensure_port_free(port, name)
    env = {**os.environ, "RUN_MODE": "local", "FLASK_ENV": "development", port_env_var: str(port)}
    proc = subprocess.Popen([_venv_python(service_dir), "run.py"], cwd=str(service_dir), env=env)
    processes.append(proc)
    print(f"  {name} starting on :{port} (pid {proc.pid})…")
    return proc


def start_bff() -> subprocess.Popen:
    ensure_port_free(BFF_PORT, "bff")
    env = {**os.environ, "RUN_MODE": "local"}
    python_bin = _venv_python(BFF_DIR)
    proc = subprocess.Popen(
        [python_bin, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", str(BFF_PORT)],
        cwd=str(BFF_DIR),
        env=env,
    )
    processes.append(proc)
    print(f"  bff starting on :{BFF_PORT} (pid {proc.pid})…")
    return proc


def start_frontend() -> subprocess.Popen:
    ensure_port_free(FRONTEND_PORT, "frontend")
    env = {**os.environ, "FRONTEND_PORT": str(FRONTEND_PORT), "VITE_BFF_BASE_URL": f"http://127.0.0.1:{BFF_PORT}"}
    proc = subprocess.Popen(["npm", "run", "dev", "--", "--port", str(FRONTEND_PORT)], cwd=str(FRONTEND_DIR), env=env)
    processes.append(proc)
    print(f"  frontend starting on :{FRONTEND_PORT} (pid {proc.pid})…")
    return proc


def shutdown(*_args):
    print("\nShutting down local stack…")
    for proc in processes:
        if proc.poll() is None:
            proc.terminate()
    for proc in processes:
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
    sys.exit(0)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="also start the 3 microservices immediately")
    args = parser.parse_args()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print("=== Starting local stack (no Docker) ===")
    start_flask_service("monolith", MONOLITH_DIR, MONOLITH_PORT, "MONOLITH_PORT")
    if not _wait_for_health(f"http://127.0.0.1:{MONOLITH_PORT}/health"):
        print("monolith failed to become healthy — aborting.")
        shutdown()
        return 1

    if args.all:
        start_flask_service("user-service", MICROSERVICES_DIR / "user-service", USER_SERVICE_PORT, "USER_SERVICE_PORT")
        start_flask_service("product-service", MICROSERVICES_DIR / "product-service", PRODUCT_SERVICE_PORT, "PRODUCT_SERVICE_PORT")
        start_flask_service("order-service", MICROSERVICES_DIR / "order-service", ORDER_SERVICE_PORT, "ORDER_SERVICE_PORT")

    start_bff()
    if not _wait_for_health(f"http://127.0.0.1:{BFF_PORT}/health"):
        print("bff failed to become healthy — aborting.")
        shutdown()
        return 1

    start_frontend()

    print(f"""
Local stack is up:
  Frontend  http://127.0.0.1:{FRONTEND_PORT}
  BFF       http://127.0.0.1:{BFF_PORT}
  Monolith  http://127.0.0.1:{MONOLITH_PORT}
{"  (microservices also started via --all)" if args.all else "  Microservices start live from the Migrate page."}

Press Ctrl+C to stop everything.
""")

    try:
        while True:
            time.sleep(1)
            for proc in processes:
                if proc.poll() is not None:
                    print(f"Process {proc.pid} exited unexpectedly (code {proc.returncode}).")
    except KeyboardInterrupt:
        shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
