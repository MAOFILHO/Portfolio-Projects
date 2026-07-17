"""Environment-driven settings for the BFF. No secrets/API keys required."""
import os
from pathlib import Path

# Path(__file__).resolve().parents[2] gives the repo root when running from a
# checkout (bff/app/config.py -> bff -> repo root), but the Docker image
# flattens bff/'s own contents onto WORKDIR /app, one level shallower
# (/app/app/config.py -> /app, not the repo root) — REPO_ROOT_OVERRIDE lets
# the Dockerfile say explicitly what "repo root" means inside the container
# instead of relying on fragile parent-count arithmetic.
REPO_ROOT = (
    Path(os.environ["REPO_ROOT_OVERRIDE"])
    if os.environ.get("REPO_ROOT_OVERRIDE")
    else Path(__file__).resolve().parents[2]
)

RUN_MODE = os.environ.get("RUN_MODE", "local")

MONOLITH_BASE_URL = os.environ.get("MONOLITH_BASE_URL", "http://127.0.0.1:6000")
USER_SERVICE_BASE_URL = os.environ.get("USER_SERVICE_BASE_URL", "http://127.0.0.1:5001")
PRODUCT_SERVICE_BASE_URL = os.environ.get("PRODUCT_SERVICE_BASE_URL", "http://127.0.0.1:5002")
ORDER_SERVICE_BASE_URL = os.environ.get("ORDER_SERVICE_BASE_URL", "http://127.0.0.1:5003")

MONOLITH_PORT = int(os.environ.get("MONOLITH_PORT", 6000))
USER_SERVICE_PORT = int(os.environ.get("USER_SERVICE_PORT", 5001))
PRODUCT_SERVICE_PORT = int(os.environ.get("PRODUCT_SERVICE_PORT", 5002))
ORDER_SERVICE_PORT = int(os.environ.get("ORDER_SERVICE_PORT", 5003))

FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "http://127.0.0.1:5173")

# Browsers treat 'localhost' and '127.0.0.1' as different origins for CORS
# purposes even though they resolve to the same machine. Vite's dev server
# binds to both (host: true), so a user visiting via either hostname must
# both be allowed — otherwise the browser blocks the BFF's response and
# fetch() fails with a generic "TypeError: Failed to fetch" that gives no
# hint it was a CORS issue. If FRONTEND_ORIGIN is overridden (e.g. for an
# Azure Static Web Apps hostname), only that exact origin is allowed.
if "FRONTEND_ORIGIN" in os.environ:
    FRONTEND_ORIGINS = [FRONTEND_ORIGIN]
else:
    _port = FRONTEND_ORIGIN.rsplit(":", 1)[-1]
    FRONTEND_ORIGINS = [f"http://127.0.0.1:{_port}", f"http://localhost:{_port}"]

RESULTS_DIR = REPO_ROOT / "results"
STATE_FILE = REPO_ROOT / "infra" / ".state.json"

MICROSERVICES_ROOT = REPO_ROOT / "microservices"
MONOLITH_ROOT = REPO_ROOT / "monolith"

SERVICE_ROUTE_PREFIXES = {
    "user": (USER_SERVICE_BASE_URL, MICROSERVICES_ROOT / "user-service", USER_SERVICE_PORT),
    "product": (PRODUCT_SERVICE_BASE_URL, MICROSERVICES_ROOT / "product-service", PRODUCT_SERVICE_PORT),
    "order": (ORDER_SERVICE_BASE_URL, MICROSERVICES_ROOT / "order-service", ORDER_SERVICE_PORT),
}

# Mutable — the shop proxy (routers/shop.py) reads from this instead of the
# static constants above. In local mode every backend's URL is already known
# (a fixed localhost port), so this is seeded fully at import time. In azure
# mode the microservices' Container Apps don't exist until the live
# migration creates them (bff/app/azure_traffic.py), so those three start out
# unset and migration_engine.py fills each one in the moment its Container
# App comes online — there is nothing to route to before that.
RUNTIME_BASE_URLS: dict[str, str | None] = {
    "monolith": MONOLITH_BASE_URL,
    "user": USER_SERVICE_BASE_URL if RUN_MODE == "local" else None,
    "product": PRODUCT_SERVICE_BASE_URL if RUN_MODE == "local" else None,
    "order": ORDER_SERVICE_BASE_URL if RUN_MODE == "local" else None,
}
