"""Fixed names and region. Every one of these matches a Bicep module's own default (`infra/modules/
*.bicep`), on purpose -- Marco, 2026-09-18: this project's whole IaC premise is that a name never
changes on collision (see resources.py's sibling docs and Phase 7's design discussion), so these are
constants, not something a flag silently mutates. Only the resource group is meant to differ between
"the live system" and "a clean subscription" (Phase 7's own exit criterion), so that one alone is
configurable.
"""
from __future__ import annotations

import os

LOCATION = "canadacentral"  # docs/PLAN.md decision 12 -- no fallback

DEFAULT_RESOURCE_GROUP = "rg-azure-banking-voice-agentic-ai"

NAMES = {
    "app_insights": "appi-azure-banking-voice",
    "container_apps_env": "cae-azure-banking-voice-p0",
    "call_records_account": "stazbankcallrecords",
    "mock_core_banking": "ca-azbank-core-banking",
    "acs": "acs-azure-banking-voice",
    "voice_agent": "ca-azbank-echo-p0",
    "call_records_rbac": "stazbankcallrecords",  # same physical account as call_records_account
    "aoai": "aoai-azure-banking-voice-cc",
}

LOG_ANALYTICS_WORKSPACE = "workspace-rgazurebankingvoiceagenticai1D"


def resource_group() -> str:
    return os.environ.get("AZURE_RESOURCE_GROUP", DEFAULT_RESOURCE_GROUP)


def required_env(name: str, why: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"{name} is required: {why}")
    return value
