"""FastAPI application entry point."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.auth_entra import require_entra_auth
from app.config import get_settings
from app.routers import agent, auth, catalog, finetune, health, inference
from app.telemetry import init_telemetry

logging.basicConfig(level=logging.INFO, format="%(message)s")
_LOGGER = logging.getLogger("foundry.api")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    # Telemetry first, so every request and tool call downstream is traced.
    init_telemetry()

    _LOGGER.info("Foundry agentic platform v%s", __version__)
    _LOGGER.info("  mode   : %s", settings.demo_mode)
    _LOGGER.info("  region : %s", settings.azure_location)
    if settings.is_mock:
        _LOGGER.info("  billing: none — mock mode, no Azure calls")
    else:
        _LOGGER.warning("  billing: LIVE — tokens are billed on every request")
    yield


app = FastAPI(
    title="Azure Foundry Agentic Fine-Tuning Platform",
    description=(
        "Automates two Microsoft Foundry labs — model discovery/evaluation and "
        "supervised fine-tuning — behind a LangGraph orchestrator over MCP tools."
    ),
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# health and auth (the demo/demo123 login screen) stay open — everything
# that touches real functionality (and, in live mode, real billing) requires
# a valid Entra token in the hosted deployment (no-op in local/mock dev, see
# auth_entra.require_entra_auth).
for module in (health, auth):
    app.include_router(module.router)
for module in (catalog, finetune, inference, agent):
    app.include_router(module.router, dependencies=[Depends(require_entra_auth)])


@app.get("/", tags=["health"])
async def root() -> dict[str, str]:
    return {
        "service": "foundry-agentic-platform",
        "version": __version__,
        "docs": "/docs",
    }
