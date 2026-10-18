"""Production extension points and privacy helpers.

Heavy providers stay optional. The interfaces make provider selection explicit
and keep raw text, images, prompts, and labels out of logs by default.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol
from urllib import request as urllib_request


class EmbeddingProvider(Protocol):
    def encode(self, texts: list[str]) -> Any: ...


class VisionQualityProvider(Protocol):
    def score(self, images: Any) -> Mapping[str, float]: ...


class LLMJudge(Protocol):
    def evaluate(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]: ...


@dataclass(frozen=True)
class LLMJudgeConfig:
    """Governance controls for an OpenAI-compatible judge endpoint."""

    endpoint: str
    model: str
    api_key: str
    prompt_version: str = "driftwatch-judge-v1"
    timeout_seconds: float = 20.0
    max_records: int = 100
    max_cost_usd: float = 1.0
    estimated_cost_per_record_usd: float = 0.01
    min_score: float = 0.0
    max_score: float = 1.0


class GovernedLLMJudge:
    """Authenticated, budgeted, redacted and calibrated LLM judge adapter.

    The endpoint must accept an OpenAI-compatible ``/chat/completions`` request
    and return JSON content containing ``results``. Raw records are redacted
    before transport and are never included in exceptions or logs.
    """

    def __init__(
        self,
        config: LLMJudgeConfig,
        transport: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> None:
        if config.max_records < 1 or config.max_cost_usd < 0:
            raise ValueError("judge limits must be positive")
        if not 0 <= config.min_score <= config.max_score <= 1:
            raise ValueError("calibration score bounds must be between zero and one")
        self.config = config
        self._transport = transport

    @classmethod
    def from_environment(cls) -> GovernedLLMJudge:
        endpoint = os.getenv("DRIFTWATCH_LLM_ENDPOINT")
        api_key = os.getenv("DRIFTWATCH_LLM_API_KEY")
        if not endpoint or not api_key:
            raise RuntimeError(
                "DRIFTWATCH_LLM_ENDPOINT and DRIFTWATCH_LLM_API_KEY are required"
            )
        return cls(
            LLMJudgeConfig(
                endpoint=endpoint.rstrip("/"),
                model=os.getenv("DRIFTWATCH_LLM_MODEL", "judge"),
                api_key=api_key,
                prompt_version=os.getenv(
                    "DRIFTWATCH_LLM_PROMPT_VERSION", "driftwatch-judge-v1"
                ),
                timeout_seconds=float(
                    os.getenv("DRIFTWATCH_LLM_TIMEOUT_SECONDS", "20")
                ),
                max_records=int(os.getenv("DRIFTWATCH_LLM_MAX_RECORDS", "100")),
                max_cost_usd=float(os.getenv("DRIFTWATCH_LLM_MAX_COST_USD", "1")),
                estimated_cost_per_record_usd=float(
                    os.getenv("DRIFTWATCH_LLM_COST_PER_RECORD_USD", "0.01")
                ),
                min_score=float(os.getenv("DRIFTWATCH_LLM_MIN_SCORE", "0")),
                max_score=float(os.getenv("DRIFTWATCH_LLM_MAX_SCORE", "1")),
            )
        )

    def evaluate(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not records:
            return []
        if len(records) > self.config.max_records:
            raise ValueError("LLM judge record limit exceeded")
        estimated_cost = len(records) * self.config.estimated_cost_per_record_usd
        if estimated_cost > self.config.max_cost_usd:
            raise ValueError("LLM judge cost limit exceeded")
        safe_records = redacted(records)
        body = {
            "model": self.config.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        f"You are DriftWatch evaluator prompt {self.config.prompt_version}. "
                        "Return JSON with a results array; each score must be between 0 and 1."
                    ),
                },
                {"role": "user", "content": json.dumps(safe_records)},
            ],
        }
        response = self._transport(body) if self._transport else self._call(body)
        results = response.get("results")
        if not isinstance(results, list) or len(results) != len(records):
            raise ValueError("LLM judge returned an invalid result count")
        validated = []
        for result in results:
            if not isinstance(result, Mapping):
                raise ValueError("LLM judge returned an invalid result")
            score = float(result.get("score"))
            if not self.config.min_score <= score <= self.config.max_score:
                raise ValueError("LLM judge score failed calibration bounds")
            validated.append({**dict(result), "score": score})
        return validated

    def _call(self, body: dict[str, Any]) -> dict[str, Any]:
        payload = json.dumps(body).encode()
        req = urllib_request.Request(
            f"{self.config.endpoint}/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib_request.urlopen(req, timeout=self.config.timeout_seconds) as response:
            raw = json.loads(response.read())
        content = raw.get("choices", [{}])[0].get("message", {}).get("content")
        if isinstance(content, str):
            return json.loads(content)
        if isinstance(content, Mapping):
            return dict(content)
        raise ValueError("LLM judge returned no JSON content")


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
    if isinstance(value, str):
        value = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[REDACTED_EMAIL]", value)
        return re.sub(r"\+?\d[\d ()-]{7,}\d", "[REDACTED_PHONE]", value)
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
