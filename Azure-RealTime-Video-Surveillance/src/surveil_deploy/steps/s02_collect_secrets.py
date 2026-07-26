from __future__ import annotations

from surveil_deploy.config import DeployConfig
from surveil_deploy.console import log_info, log_step, log_success, log_warning
from surveil_deploy.state import DeploymentState

STEP_NAME = "s02_collect_secrets"
STEP_TITLE = "Collecting alert configuration"


def run(config: DeployConfig, state: DeploymentState) -> dict:
    log_step(2, 12, STEP_TITLE)

    log_info(f"Watch tags: {config.alert_watch_tags}")
    log_info(f"Min confidence: {config.alert_min_confidence}  Min count: {config.alert_min_count}")

    email_configured = bool(config.alert_email_to)
    sms_configured = bool(config.alert_sms_to and config.acs_sms_from)

    if email_configured:
        log_success(f"Email alerts will be sent to {config.alert_email_to}")
    else:
        log_warning("ALERT_EMAIL_TO not set — email alerting will be disabled after deploy")

    if sms_configured:
        log_success(f"SMS alerts will be sent to {config.alert_sms_to}")
    else:
        log_warning(
            "ALERT_SMS_TO / ACS_SMS_FROM not set — SMS alerting disabled. "
            "(SMS requires purchasing an ACS phone number first; see docs/deployment.md.)"
        )

    if not email_configured and not sms_configured:
        log_warning("No ACS alert channel configured — only the in-app WebSocket alert feed will fire.")

    return {
        "email_alerting_enabled": email_configured,
        "sms_alerting_enabled": sms_configured,
    }
