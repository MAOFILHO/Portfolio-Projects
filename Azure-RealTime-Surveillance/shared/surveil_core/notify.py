"""Alert delivery via Azure Communication Services (email + SMS)."""

from __future__ import annotations

import logging

from azure.communication.email import EmailClient
from azure.communication.sms import SmsClient

from surveil_core.models import AlertMessage

logger = logging.getLogger("surveil_core.notify")


class AcsNotifier:
    """Sends alert emails/SMS via Azure Communication Services.

    Any missing recipient/sender config disables that channel rather than
    raising, so email-only or SMS-only setups (or neither, e.g. running the
    unit tests) work without extra guards at call sites.
    """

    def __init__(
        self,
        connection_string: str | None,
        sender_email: str | None = None,
        alert_email_to: str | None = None,
        alert_sms_to: str | None = None,
        sms_from: str | None = None,
    ) -> None:
        self._email_client = EmailClient.from_connection_string(connection_string) if connection_string else None
        self._sms_client = SmsClient.from_connection_string(connection_string) if connection_string else None
        self._sender_email = sender_email
        self._alert_email_to = alert_email_to
        self._alert_sms_to = alert_sms_to
        self._sms_from = sms_from

    @property
    def email_enabled(self) -> bool:
        return bool(self._email_client and self._sender_email and self._alert_email_to)

    @property
    def sms_enabled(self) -> bool:
        return bool(self._sms_client and self._sms_from and self._alert_sms_to)

    def send_alert_email(self, alert: AlertMessage) -> bool:
        if not self.email_enabled:
            logger.info("Email alerting disabled (missing ACS sender/recipient config) — skipping.")
            return False

        tags = ", ".join(alert.matched_tags)
        subject = f"[Surveillance Alert] {tags} detected on camera {alert.camera_id}"
        body = (
            f"Detected: {tags}\n"
            f"Camera: {alert.camera_id}\n"
            f"Time: {alert.triggered_at.isoformat()}\n"
            f"Caption: {alert.caption or 'n/a'}\n"
            f"Frame: {alert.frame_url or alert.frame_blob_name}\n"
        )
        message = {
            "senderAddress": self._sender_email,
            "recipients": {"to": [{"address": self._alert_email_to}]},
            "content": {"subject": subject, "plainText": body},
        }
        poller = self._email_client.begin_send(message)
        poller.result()
        logger.info("Sent alert email for event %s", alert.event_id)
        return True

    def send_alert_sms(self, alert: AlertMessage) -> bool:
        if not self.sms_enabled:
            logger.info("SMS alerting disabled (missing ACS sms-from/recipient config) — skipping.")
            return False

        tags = ", ".join(alert.matched_tags)
        message = f"Surveillance alert: {tags} detected on camera {alert.camera_id} at {alert.triggered_at.isoformat()}"
        self._sms_client.send(from_=self._sms_from, to=[self._alert_sms_to], message=message)
        logger.info("Sent alert SMS for event %s", alert.event_id)
        return True

    def send_all(self, alert: AlertMessage) -> dict[str, bool]:
        return {
            "email": self.send_alert_email(alert),
            "sms": self.send_alert_sms(alert),
        }
