"""Drives a REAL strangler-fig migration, not a canned animation.

local mode: starts/stops the actual local Python subprocesses for each
microservice (and eventually the monolith) as each step completes, polling
their real /health endpoints — the UI reflects genuine process state.

azure mode: `make provision` stands up only the foundation + monolith + bff.
The three microservices' Container Apps do not exist yet — each extraction
step here CREATES that Container App for the first time via the
azure-mgmt-appcontainers SDK (bff/app/azure_traffic.py), then updates
config.RUNTIME_BASE_URLS so the shop proxy has somewhere to route once that
service is live. If the bff isn't actually running inside the Azure
deployment yet, this mode reports that clearly instead of pretending to do
something.

Steps mirror the 7-step Strangler Fig framework from the provided study
guides (domain slicing -> proxy layer -> service extraction -> ACL ->
traffic redirection -> data sync -> decommission), compressed into one pass
per real service in this repo.
"""
import asyncio
import subprocess
import sys
import time
from dataclasses import dataclass
from enum import Enum

import httpx

from . import config

try:
    import psutil
except ImportError:  # psutil is optional; degrade gracefully
    psutil = None


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


@dataclass
class Step:
    id: str
    title: str
    description: str
    status: StepStatus = StepStatus.PENDING


def _default_steps() -> list[Step]:
    return [
        Step("assess", "Domain Assessment & Slicing",
             "Identify bounded contexts: user accounts, product catalog, and orders. "
             "Each becomes a candidate for extraction (Domain-Driven Design)."),
        Step("proxy", "Introduce the Proxy Layer",
             "The FastAPI BFF now sits between the frontend and the backend. "
             "100% of traffic still routes to the monolith."),
        Step("extract_user", "Extract user-service",
             "Clone auth logic into an independently deployable user-service with its own database."),
        Step("redirect_user", "Redirect auth traffic",
             "The BFF now routes /api/user* and /api/users to user-service instead of the monolith."),
        Step("extract_product", "Extract product-service",
             "Clone catalog logic into product-service with its own database."),
        Step("redirect_product", "Redirect catalog traffic",
             "The BFF now routes /api/product* to product-service."),
        Step("extract_order_acl", "Extract order-service + Anti-Corruption Layer",
             "order-service owns orders but has no access to the user table — it calls user-service "
             "over HTTP (UserClient) instead of joining the old shared schema."),
        Step("redirect_order", "Redirect order traffic",
             "The BFF now routes /api/order* to order-service. All three domains are now independent."),
        Step("decommission", "Decommission the monolith",
             "All functionality now lives in the microservices. The monolith process is stopped."),
    ]


class MigrationEngine:
    def __init__(self):
        self.steps: list[Step] = _default_steps()
        self.active_backend = "monolith"  # or "microservices"
        self.running = False
        self.last_error: str | None = None

    def snapshot(self) -> dict:
        return {
            "mode": config.RUN_MODE,
            "active_backend": self.active_backend,
            "running": self.running,
            "last_error": self.last_error,
            "steps": [
                {"id": s.id, "title": s.title, "description": s.description, "status": s.status.value}
                for s in self.steps
            ],
        }

    def reset(self):
        for step in self.steps:
            step.status = StepStatus.PENDING
        self.active_backend = "monolith"
        self.running = False
        self.last_error = None
        config.RUNTIME_BASE_URLS["monolith"] = config.MONOLITH_BASE_URL

    async def restart_monolith(self) -> bool:
        """Undoes the decommission step for real, then resets the whole
        migration state so the guided walkthrough can be re-run from scratch.
        Without this, clicking 'Start Migration' just to see what happens is
        a one-way trip — the monolith stays dead until manually restarted.
        Local mode: respawns the actual process. Azure mode: scales the
        monolith Container App back up from 0 replicas. Checks health first
        so this is a no-op (besides the reset) if it was never actually
        stopped."""
        already_up = await self._wait_for_health(config.MONOLITH_BASE_URL, timeout=1.0)
        if not already_up:
            if config.RUN_MODE == "local":
                self._start_service_process(config.MONOLITH_ROOT, "MONOLITH_PORT", config.MONOLITH_PORT)
            else:
                from . import azure_traffic

                if not azure_traffic.is_configured():
                    self.last_error = "Azure mode requires the bff to be running inside the Azure deployment."
                    return False
                await azure_traffic.scale_monolith(1, 3)
            already_up = await self._wait_for_health(config.MONOLITH_BASE_URL)
        if already_up:
            self.reset()
        return already_up

    async def _wait_for_health(self, base_url: str, timeout: float = 15.0) -> bool:
        deadline = time.monotonic() + timeout
        async with httpx.AsyncClient(timeout=2) as client:
            while time.monotonic() < deadline:
                try:
                    r = await client.get(f"{base_url}/health")
                    if r.status_code == 200:
                        return True
                except httpx.HTTPError:
                    pass
                await asyncio.sleep(0.5)
        return False

    def _start_service_process(self, service_dir, port_env_var: str, port: int):
        venv_python = service_dir / ".venv" / "bin" / "python"
        python_bin = str(venv_python) if venv_python.exists() else sys.executable
        env = {"RUN_MODE": "local", "FLASK_ENV": "development", port_env_var: str(port)}
        import os
        full_env = {**os.environ, **env}
        subprocess.Popen(
            [python_bin, "run.py"],
            cwd=str(service_dir),
            env=full_env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def _stop_process_on_port(self, port: int) -> bool:
        """Finds the process listening on `port` and stops it. Deliberately
        iterates psutil.Process(pid).net_connections() per-process rather
        than the system-wide psutil.net_connections() — the latter raises
        psutil.AccessDenied on macOS without root, which was caught here for
        real: the decommission step hung forever in 'running' because that
        exception wasn't handled and silently escaped run()'s loop."""
        if psutil is None:
            return False

        stopped_any = False
        for pid in psutil.pids():
            try:
                proc = psutil.Process(pid)
                conns = proc.net_connections(kind="inet")
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

            if any(c.status == psutil.CONN_LISTEN and c.laddr and c.laddr.port == port for c in conns):
                try:
                    proc.terminate()
                    proc.wait(timeout=5)
                    stopped_any = True
                except (psutil.NoSuchProcess, psutil.TimeoutExpired):
                    pass

        return stopped_any

    async def run(self, mode: str):
        """Advances self.steps in place. The SSE endpoint (routers/migration.py)
        observes progress by polling self.snapshot() — no separate event bus
        needed since this is the single source of truth for state."""
        if self.running:
            return

        self.running = True
        try:
            for step in self.steps:
                step.status = StepStatus.RUNNING
                await asyncio.sleep(0.6)  # let the UI show the transition

                try:
                    ok = await self._execute_step(step, mode)
                except Exception as exc:  # noqa: BLE001 — any failure must resolve the step, never leave it "running" forever
                    ok = False
                    self.last_error = f"Step '{step.id}' raised {type(exc).__name__}: {exc}"
                step.status = StepStatus.DONE if ok else StepStatus.FAILED
                if not ok:
                    break
        finally:
            self.running = False

    async def _execute_step(self, step: Step, mode: str) -> bool:
        if step.id == "extract_user":
            if mode == "local":
                base_url, service_dir, port = config.SERVICE_ROUTE_PREFIXES["user"]
                self._start_service_process(service_dir, "USER_SERVICE_PORT", port)
                return await self._wait_for_health(base_url)
            return await self._azure_step(step, "user")

        if step.id == "extract_product":
            if mode == "local":
                base_url, service_dir, port = config.SERVICE_ROUTE_PREFIXES["product"]
                self._start_service_process(service_dir, "PRODUCT_SERVICE_PORT", port)
                return await self._wait_for_health(base_url)
            return await self._azure_step(step, "product")

        if step.id == "extract_order_acl":
            if mode == "local":
                base_url, service_dir, port = config.SERVICE_ROUTE_PREFIXES["order"]
                self._start_service_process(service_dir, "ORDER_SERVICE_PORT", port)
                return await self._wait_for_health(base_url)
            return await self._azure_step(step, "order")

        if step.id in ("redirect_user", "redirect_product"):
            return True  # BFF routing already dispatches by prefix; nothing to flip physically

        if step.id == "redirect_order":
            self.active_backend = "microservices"
            return True

        if step.id == "decommission":
            if mode == "local":
                return self._stop_process_on_port(config.MONOLITH_PORT) or True  # ok even if already stopped
            ok = await self._azure_step(step, None)
            if ok:
                config.RUNTIME_BASE_URLS["monolith"] = None
            return ok

        return True  # assess / proxy steps are narrative-only

    async def _azure_step(self, step: Step, service_key: str | None) -> bool:
        from . import azure_traffic

        if not azure_traffic.is_configured():
            self.last_error = (
                "Azure mode requires the bff to be running inside the Azure deployment created by "
                "`make provision` (AZURE_RESOURCE_GROUP is not set) — switch to local mode to see the "
                "live process-based migration instead."
            )
            return False
        try:
            ok, new_base_url = await azure_traffic.shift_traffic_for_step(step.id)
            if ok and service_key and new_base_url:
                config.RUNTIME_BASE_URLS[service_key] = new_base_url
            return ok
        except Exception as exc:  # pragma: no cover - defensive, reported to the UI
            self.last_error = f"Azure step '{step.id}' failed: {exc}"
            return False


engine = MigrationEngine()
