"""Alert delivery with explicit, inspectable webhook payloads."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
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
            return self.store.record_alert(
                run["id"], "webhook", "skipped", "Webhook URL is not configured"
            )
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
