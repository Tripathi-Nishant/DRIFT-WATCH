"""Small Prometheus-compatible metrics and structured logging helpers."""

from __future__ import annotations

import json
import logging
import threading
import time
from collections import Counter
from typing import Any


class Metrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.requests = Counter()
        self.latency = []

    def observe(self, route: str, status: int, elapsed: float) -> None:
        with self._lock:
            self.requests[(route, str(status))] += 1
            self.latency.append(elapsed)
            self.latency = self.latency[-10000:]

    def prometheus(self) -> str:
        with self._lock:
            lines = [
                "# TYPE driftwatch_http_requests_total counter",
                *(
                    f'driftwatch_http_requests_total{{route="{route}",status="{status}"}} {count}'
                    for (route, status), count in self.requests.items()
                ),
                "# TYPE driftwatch_http_latency_seconds gauge",
                f"driftwatch_http_latency_seconds {sum(self.latency) / len(self.latency) if self.latency else 0}",
            ]
        return "\n".join(lines) + "\n"


def log_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    logger.info(json.dumps({"event": event, "ts": time.time(), **fields}, default=str))
