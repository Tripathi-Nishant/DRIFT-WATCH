"""Alert delivery with explicit, inspectable webhook payloads."""

from __future__ import annotations

import json
import os
import smtplib
import time
import urllib.error
import urllib.request
from email.message import EmailMessage
from typing import Any

from .storage import Store


class AlertDispatcher:
    def __init__(self, store: Store, webhook_url: str | None = None) -> None:
        self.store = store
        self.webhook_url = webhook_url or os.getenv("DRIFTWATCH_WEBHOOK_URL")

    def dispatch(self, run: dict[str, Any], retries: int = 3) -> dict[str, Any] | None:
        summary = run["report"]["summary"]
        if summary.get("severity") not in {"HIGH", "CRITICAL"}:
            return None
        payload = {
            "event": "driftwatch.alert",
            "run_id": run["id"],
            "severity": summary.get("severity"),
            "decision": summary.get("decision"),
            "model": summary.get("model"),
            "recommendation": summary.get("recommendation"),
            "reasons": summary.get("reasons", []),
        }
        if not self.webhook_url:
            webhook_result = self.store.record_alert(
                run["id"], "webhook", "skipped", "Webhook URL is not configured"
            )
        else:
            webhook_result = self._dispatch_webhook(run, payload, retries)
        self._dispatch_email(run, payload, retries)
        return webhook_result

    def _dispatch_webhook(self, run: dict[str, Any], payload: dict[str, Any], retries: int):
        status, detail = "failed", "delivery failed"
        for attempt in range(max(1, retries)):
            try:
                request = urllib.request.Request(
                    self.webhook_url,
                    data=json.dumps(payload).encode(),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(request, timeout=5) as response:
                    status = "delivered" if 200 <= response.status < 300 else "failed"
                    detail = f"HTTP {response.status}; attempts={attempt + 1}"
                if status == "delivered":
                    break
            except (OSError, urllib.error.URLError) as error:
                detail = f"{error}; attempts={attempt + 1}"
                if attempt + 1 < retries:
                    time.sleep(0.25 * (2**attempt))
        return self.store.record_alert(run["id"], "webhook", status, detail)

    def _dispatch_email(self, run: dict[str, Any], payload: dict[str, Any], retries: int) -> None:
        host, recipient = os.getenv("DRIFTWATCH_SMTP_HOST"), os.getenv("DRIFTWATCH_ALERT_EMAIL")
        if not host or not recipient:
            return
        message = EmailMessage()
        message["Subject"] = f"DriftWatch {payload['severity']} alert: {payload['model']}"
        message["From"] = os.getenv("DRIFTWATCH_SMTP_FROM", recipient)
        message["To"] = recipient
        message.set_content(json.dumps(payload, indent=2))
        for attempt in range(max(1, retries)):
            try:
                with smtplib.SMTP(host, int(os.getenv("DRIFTWATCH_SMTP_PORT", "587")), timeout=5) as client:
                    if os.getenv("DRIFTWATCH_SMTP_TLS", "true").lower() == "true":
                        client.starttls()
                    username, password = os.getenv("DRIFTWATCH_SMTP_USER"), os.getenv("DRIFTWATCH_SMTP_PASSWORD")
                    if username and password:
                        client.login(username, password)
                    client.send_message(message)
                self.store.record_alert(run["id"], "email", "delivered", f"attempts={attempt + 1}")
                return
            except (OSError, smtplib.SMTPException) as error:
                if attempt + 1 == retries:
                    self.store.record_alert(run["id"], "email", "failed", str(error))
                else:
                    time.sleep(0.25 * (2**attempt))
