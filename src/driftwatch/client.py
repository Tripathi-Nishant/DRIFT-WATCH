"""Small dependency-free client for sending monitoring data to DriftWatch."""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .models import UsageSummary


class DriftWatchError(RuntimeError):
    """Raised when the DriftWatch API rejects a request."""


class DriftWatchClient:
    """Use DriftWatch from any model project without writing HTTP boilerplate.

    A dashboard JWT is useful for interactive use. Production model jobs should
    use an ingestion API key created from the dashboard.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8765",
        *,
        api_key: str | None = None,
        token: str | None = None,
        timeout: float = 15.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.token = token
        self.timeout = timeout

    @classmethod
    def from_environment(cls) -> DriftWatchClient:
        """Create a client from DRIFTWATCH_URL and DRIFTWATCH_API_KEY."""
        return cls(
            os.getenv("DRIFTWATCH_URL", "http://localhost:8765"),
            api_key=os.getenv("DRIFTWATCH_API_KEY"),
            token=os.getenv("DRIFTWATCH_TOKEN"),
        )

    def _request(self, path: str, payload: dict[str, Any] | None = None) -> Any:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-DriftWatch-Key"] = self.api_key
        elif self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode() if payload is not None else None,
            headers=headers,
            method="POST" if payload is not None else "GET",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode())
        except (HTTPError, URLError, TimeoutError) as error:
            detail = getattr(error, "read", lambda: b"")()
            try:
                message = json.loads(detail.decode()).get("error", str(error))
            except (AttributeError, UnicodeDecodeError, json.JSONDecodeError):
                message = str(error)
            raise DriftWatchError(message) from error

    def health(self) -> dict[str, Any]:
        """Return process health without authentication."""
        return self._request("/healthz")

    def analyze(
        self,
        reference: Any,
        current: Any,
        *,
        model_name: str = "model",
        model_type: str = "auto",
        task: str | None = None,
        predictions: Any = None,
        labels: Any = None,
        **extra: Any,
    ) -> dict[str, Any]:
        """Run an analysis and persist the report in the workspace history."""
        payload = {
            "reference": _records(reference),
            "current": _records(current),
            "model_name": model_name,
            "model_type": task or model_type,
        }
        if predictions is not None:
            payload["predictions"] = _values(predictions)
        if labels is not None:
            payload["labels"] = _values(labels)
        payload.update(extra)
        return self._request("/api/analyze", payload)

    def monitor(
        self,
        reference: Any,
        current: Any,
        *,
        model_name: str = "model",
        model_type: str = "auto",
        predictions: Any = None,
        labels: Any = None,
        **extra: Any,
    ) -> dict[str, Any]:
        """Analyze and persist one monitoring window for a registered workspace."""
        return self.analyze(
            reference,
            current,
            model_name=model_name,
            model_type=model_type,
            predictions=predictions,
            labels=labels,
            **extra,
        )

    def ingest_predictions(
        self, predictions: list[dict[str, Any]], *, model_id: str | None = None
    ) -> dict[str, Any]:
        """Submit prediction events using an ingestion API key."""
        return self._request(
            "/api/ingest/predictions",
            {"model_id": model_id, "predictions": predictions},
        )

    def ingest_feedback(self, prediction_id: str, label: Any) -> dict[str, Any]:
        """Attach a delayed ground-truth label to a prediction event."""
        return self._request(
            "/api/ingest/feedback", {"prediction_id": prediction_id, "label": label}
        )

    def usage(self) -> UsageSummary:
        """Return organization usage and quota status."""
        return self._request("/api/v1/usage")


def _records(value: Any) -> list[dict[str, Any]]:
    if hasattr(value, "to_dict"):
        value = value.to_dict(orient="records")
    records = list(value)
    if not all(isinstance(row, dict) for row in records):
        raise TypeError("reference and current data must be records or DataFrames")
    return records


def _values(value: Any) -> list[Any]:
    if hasattr(value, "tolist"):
        value = value.tolist()
    return list(value)
