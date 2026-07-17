"""Reports which backend URLs are currently live, straight from the BFF's
own runtime registry (config.RUNTIME_BASE_URLS) — the single source of
truth for what exists right now. scripts/benchmark.py uses this instead of
hardcoding localhost ports, so it works unchanged against Azure Container
Apps FQDNs once a live migration creates them, while still hitting each
backend directly (not through this BFF) to keep the monolith-vs-microservices
comparison fair."""
from fastapi import APIRouter

from .. import config

router = APIRouter(prefix="/api/services", tags=["services"])


@router.get("")
async def list_services() -> dict[str, str | None]:
    return dict(config.RUNTIME_BASE_URLS)
