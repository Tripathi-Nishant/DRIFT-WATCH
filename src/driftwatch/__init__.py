"""DriftWatch: open-source ML monitoring."""

from .advanced_metrics import (
    image_metrics,
    llm_metrics,
    rag_metrics,
    ranking_metrics,
    semantic_text_metrics,
)
from .decision import DecisionConfig
from .metrics import metric_catalog
from .monitor import analyze, demo_datasets
from .pipeline import Monitor, MonitorResult, ReferenceProfile
from .vector_store import QdrantVectorStore

__version__ = "0.1.0"

__all__ = [
    "Monitor",
    "DecisionConfig",
    "MonitorResult",
    "ReferenceProfile",
    "analyze",
    "demo_datasets",
    "metric_catalog",
    "QdrantVectorStore",
    "semantic_text_metrics",
    "image_metrics",
    "ranking_metrics",
    "llm_metrics",
    "rag_metrics",
    "__version__",
]
