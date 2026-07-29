from __future__ import annotations

from functools import lru_cache

from azure.identity import DefaultAzureCredential
from azure.monitor.query import LogsQueryClient
from fastapi import Depends, Header, HTTPException
from semantic_kernel import Kernel
from surveil_core import AlertRuleConfig
from surveil_core.agents import EventQueryAgent, MonitoringAgent, build_kernel
from surveil_core.analyzer import AzureVisionAnalyzer
from surveil_core.notify import AcsNotifier
from surveil_core.storage import SurveillanceStorage

from app.config import Settings, get_settings


@lru_cache
def get_credential() -> DefaultAzureCredential:
    settings = get_settings()
    if settings.azure_client_id:
        return DefaultAzureCredential(managed_identity_client_id=settings.azure_client_id)
    return DefaultAzureCredential()


@lru_cache
def get_storage() -> SurveillanceStorage:
    settings = get_settings()
    return SurveillanceStorage(account_url=settings.storage_blob_endpoint, credential=get_credential())


@lru_cache
def get_vision_analyzer() -> AzureVisionAnalyzer:
    settings = get_settings()
    return AzureVisionAnalyzer(endpoint=settings.vision_endpoint, credential=get_credential())


@lru_cache
def get_logs_client() -> LogsQueryClient:
    return LogsQueryClient(credential=get_credential())


@lru_cache
def get_kernel() -> Kernel:
    settings = get_settings()
    return build_kernel(
        endpoint=settings.openai_endpoint,
        deployment_name=settings.openai_chat_deployment,
        credential=get_credential(),
    )


@lru_cache
def get_query_agent() -> EventQueryAgent:
    return EventQueryAgent(kernel=get_kernel(), storage=get_storage())


@lru_cache
def get_monitoring_agent() -> MonitoringAgent:
    return MonitoringAgent(kernel=get_kernel())


@lru_cache
def get_notifier() -> AcsNotifier:
    settings = get_settings()
    return AcsNotifier(
        connection_string=settings.acs_connection_string or None,
        sender_email=settings.acs_sender_email or None,
        alert_email_to=settings.alert_email_to or None,
        alert_sms_to=settings.alert_sms_to or None,
        sms_from=settings.acs_sms_from or None,
    )


def get_alert_rule_config(settings: Settings | None = None) -> AlertRuleConfig:
    settings = settings or get_settings()
    kwargs: dict = dict(
        watch_tags=settings.watch_tags_list(),
        min_confidence=settings.alert_min_confidence,
        min_count=settings.alert_min_count,
        crowd_threshold=settings.alert_crowd_threshold,
        restricted_zone=settings.restricted_zone_tuple(),
    )
    severity_map = settings.severity_map_dict()
    if severity_map is not None:
        kwargs["severity_map"] = severity_map
    return AlertRuleConfig(**kwargs)


def require_frame_upload_key(
    x_api_key: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    """Gate POST /api/v1/frames behind a shared secret when one is configured.

    No-op when `frame_upload_api_key` is unset, so local dev and anyone
    running this project without the always-on Nest ingestor enabled sees no
    behavior change.
    """
    if settings.frame_upload_api_key and x_api_key != settings.frame_upload_api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Api-Key")
