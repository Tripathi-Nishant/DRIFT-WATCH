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
from .multimodal import analyze as analyze_multimodal
from .multimodal import analyze_images, analyze_text, load_image_batch
from .pipeline import Monitor, MonitorResult, ReferenceProfile
from .production import GeminiLLMJudge
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
