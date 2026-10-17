"""Production extension points and privacy helpers.

Heavy providers stay optional. The interfaces make provider selection explicit
and keep raw text, images, prompts, and labels out of logs by default.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from collections.abc import Callable, Mapping
from typing import Any, Protocol


class EmbeddingProvider(Protocol):
    def encode(self, texts: list[str]) -> Any: ...


class VisionQualityProvider(Protocol):
    def score(self, images: Any) -> Mapping[str, float]: ...


class LLMJudge(Protocol):
    def evaluate(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]: ...


def embedding_provider() -> EmbeddingProvider | None:
    """Load the configured sentence-transformers provider when installed."""
    model_name = os.getenv("DRIFTWATCH_EMBEDDING_MODEL")
    if not model_name:
        return None
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as error:
        raise RuntimeError(
            "DRIFTWATCH_EMBEDDING_MODEL requires the optional embeddings extra"
        ) from error
    return SentenceTransformer(model_name)


def redacted(value: Any, *, sensitive_keys: set[str] | None = None) -> Any:
    """Recursively redact common PII/secrets before audit or debug storage."""
    keys = sensitive_keys or {
        "password",
        "token",
        "access_token",
        "api_key",
        "authorization",
        "email",
        "phone",
        "ssn",
        "prompt",
        "context",
        "answer",
        "label",
    }
    if isinstance(value, Mapping):
        return {
            str(key): "[REDACTED]"
            if str(key).lower() in keys
            else redacted(item, sensitive_keys=keys)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redacted(item, sensitive_keys=keys) for item in value]
    return value


def fingerprint(value: Any) -> str:
    """Return a stable non-reversible identifier for correlation logs."""
    raw = json.dumps(value, sort_keys=True, default=str).encode()
    return hashlib.sha256(raw).hexdigest()[:16]


def max_body_bytes() -> int:
    return int(os.getenv("DRIFTWATCH_MAX_BODY_BYTES", str(5 * 1024 * 1024)))


def allowed_origins() -> set[str]:
    return {
        item.strip()
        for item in os.getenv("DRIFTWATCH_ALLOWED_ORIGINS", "").split(",")
        if item.strip()
    }


def judge_records(
    judge: LLMJudge | Callable[..., Any], records: list[dict[str, Any]]
) -> Any:
    """Run a governed external judge without embedding provider assumptions."""
    if hasattr(judge, "evaluate"):
        return judge.evaluate(records)
    return judge(records)


class RateLimiter:
    """Process-local token bucket; use a shared gateway for multi-node deployments."""

    def __init__(self, rate: float = 60.0, burst: int = 120) -> None:
        self.rate, self.burst = rate, burst
        self._lock = threading.Lock()
        self._buckets: dict[str, tuple[float, float]] = {}

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            tokens, last = self._buckets.get(key, (float(self.burst), now))
            tokens = min(float(self.burst), tokens + (now - last) * self.rate)
            if tokens < 1:
                self._buckets[key] = (tokens, now)
                return False
            self._buckets[key] = (tokens - 1, now)
            return True
