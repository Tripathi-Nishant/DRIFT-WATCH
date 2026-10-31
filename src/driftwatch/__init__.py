"""DriftWatch: open-source ML monitoring."""

import os
from typing import Any

from .advanced_metrics import (
    image_metrics,
    llm_metrics,
    rag_metrics,
    ranking_metrics,
    semantic_text_metrics,
)
from .client import DriftWatchClient, DriftWatchError
from .decision import DecisionConfig
from .metrics import (
    metric_catalog,
    register_metric,
    registered_metrics,
    unregister_metric,
)
from .monitor import analyze, demo_datasets
from .multimodal import analyze as analyze_multimodal
from .multimodal import analyze_images, analyze_text, load_image_batch
from .pipeline import Monitor, MonitorResult, ReferenceProfile
from .production import GeminiLLMJudge
from .vector_store import QdrantVectorStore

__version__ = "0.1.0"

__all__ = [
    "Monitor",
    "DecisionConfig",
    "DriftWatchClient",
    "DriftWatchError",
    "monitor",
    "MonitorResult",
    "ReferenceProfile",
    "analyze",
    "demo_datasets",
    "metric_catalog",
    "register_metric",
    "unregister_metric",
    "registered_metrics",
    "QdrantVectorStore",
    "GeminiLLMJudge",
    "semantic_text_metrics",
    "image_metrics",
    "ranking_metrics",
    "llm_metrics",
    "rag_metrics",
    "analyze_multimodal",
    "analyze_text",
    "analyze_images",
    "load_image_batch",
    "__version__",
]


def monitor(
    reference: Any,
    current: Any,
    *,
    model_name: str = "model",
    model_type: str = "classification",
    api_key: str | None = None,
    base_url: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """One-call monitoring integration using explicit or environment config."""
    client = DriftWatchClient(
        base_url or os.getenv("DRIFTWATCH_URL", "http://localhost:8765"),
        api_key=api_key or os.getenv("DRIFTWATCH_API_KEY"),
        token=os.getenv("DRIFTWATCH_TOKEN"),
    )
    return client.monitor(
        reference,
        current,
        model_name=model_name,
        model_type=model_type,
        **kwargs,
    )
