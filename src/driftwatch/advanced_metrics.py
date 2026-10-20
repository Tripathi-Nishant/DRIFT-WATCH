"""Optional-domain monitoring primitives.

These metrics are deterministic and provider-neutral. They intentionally do not
call an LLM or upload customer data. Teams can replace the evaluator functions
with a governed model provider while retaining the same JSON contract.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def _round(value: Any, digits: int = 6) -> float | None:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return round(value, digits) if np.isfinite(value) else None


def semantic_text_metrics(
    reference: Iterable[str],
    current: Iterable[str],
    provider: Any = None,
) -> dict[str, Any]:
    """Measure semantic text-window shift with TF-IDF cosine distance.

    This is a reproducible lexical-semantic baseline, not a substitute for a
    domain embedding model. Supply a custom embedding service for production
    multilingual or domain-specific semantics.
    """
    ref, cur = [str(x or "") for x in reference], [str(x or "") for x in current]
    if not ref or not cur:
        return {"available": False, "reason": "both windows must contain text"}
    if provider is not None:
        ref_matrix = np.asarray(provider.encode(ref), dtype=float)
        cur_matrix = np.asarray(provider.encode(cur), dtype=float)
        ref_centroid, cur_centroid = (
            ref_matrix.mean(axis=0, keepdims=True),
            cur_matrix.mean(axis=0, keepdims=True),
        )
        vocabulary_size = int(ref_matrix.shape[-1])
        method = "external_embedding_provider"
    else:
        vectorizer = TfidfVectorizer(max_features=10000, ngram_range=(1, 2))
        matrix = vectorizer.fit_transform(ref + cur)
        ref_centroid = np.asarray(matrix[: len(ref)].mean(axis=0))
        cur_centroid = np.asarray(matrix[len(ref) :].mean(axis=0))
        vocabulary_size = int(len(vectorizer.vocabulary_))
        method = "tfidf_cosine_centroid"
    similarity = cosine_similarity(ref_centroid, cur_centroid)[0, 0]
    return {
        "available": True,
        "method": method,
        "reference_documents": len(ref),
        "current_documents": len(cur),
        "centroid_cosine_similarity": _round(similarity),
        "semantic_shift": _round(1.0 - similarity),
        "vocabulary_size": vocabulary_size,
    }


def image_metrics(reference: Any, current: Any) -> dict[str, Any]:
    """Compare image tensors or arrays without storing image content."""
    ref, cur = np.asarray(reference), np.asarray(current)
    if ref.ndim < 3 or cur.ndim < 3:
        return {
            "available": False,
            "reason": (
                "expected image batches with shape (n, height, width[, channels])"
            ),
        }
    ref_pixels, cur_pixels = ref.astype(float), cur.astype(float)
    ref_flat, cur_flat = ref_pixels.reshape(-1), cur_pixels.reshape(-1)
    bins = np.linspace(0, 255, 33)
    ref_hist = np.histogram(np.clip(ref_flat, 0, 255), bins=bins, density=True)[0]
    cur_hist = np.histogram(np.clip(cur_flat, 0, 255), bins=bins, density=True)[0]
    ref_hist = ref_hist / max(ref_hist.sum(), 1e-12)
    cur_hist = cur_hist / max(cur_hist.sum(), 1e-12)
    return {
        "available": True,
        "reference_shape": list(ref.shape),
        "current_shape": list(cur.shape),
        "shape_changed": list(ref.shape[1:]) != list(cur.shape[1:]),
        "reference_mean_pixel": _round(ref_flat.mean()),
        "current_mean_pixel": _round(cur_flat.mean()),
        "reference_std_pixel": _round(ref_flat.std()),
        "current_std_pixel": _round(cur_flat.std()),
        "pixel_histogram_distance": _round(0.5 * np.abs(ref_hist - cur_hist).sum()),
        "reference_channel_count": int(ref.shape[-1]) if ref.ndim == 4 else 1,
        "current_channel_count": int(cur.shape[-1]) if cur.ndim == 4 else 1,
    }


def embedding_shift_metrics(reference: Any, current: Any, provider: Any) -> dict[str, Any]:
    """Compare two batches of vectors from a text or vision embedding provider."""
    reference_vectors = np.asarray(provider.encode(reference), dtype=float)
    current_vectors = np.asarray(provider.encode(current), dtype=float)
    if reference_vectors.ndim != 2 or current_vectors.ndim != 2:
        return {"available": False, "reason": "embedding provider must return 2D vectors"}
    reference_centroid = reference_vectors.mean(axis=0, keepdims=True)
    current_centroid = current_vectors.mean(axis=0, keepdims=True)
    similarity = cosine_similarity(reference_centroid, current_centroid)[0, 0]
    return {
        "available": True,
        "method": getattr(provider, "name", "custom_embedding_provider"),
        "dimensions": int(reference_vectors.shape[1]),
        "centroid_cosine_similarity": _round(similarity),
        "embedding_shift": _round(1.0 - similarity),
    }


def ranking_metrics(
    relevance: Any, recommendations: Any | None = None, k: int = 10
) -> dict[str, Any]:
    """Compute ranking metrics from relevance matrices or ranked item lists."""
    values = np.asarray(relevance, dtype=float)
    if values.ndim == 1:
        values = values[None, :]
    values = values[:, :k]
    if not values.size:
        return {"available": False, "reason": "relevance data is empty"}
    ranks = np.arange(1, values.shape[1] + 1)
    gains = (2**values - 1) / np.log2(ranks + 1)
    dcg = gains.sum(axis=1)
    ideal = np.sort(values, axis=1)[:, ::-1]
    ideal_dcg = ((2**ideal - 1) / np.log2(ranks + 1)).sum(axis=1)
    ndcg = np.divide(dcg, ideal_dcg, out=np.ones_like(dcg), where=ideal_dcg != 0)
    hits = values > 0
    reciprocal_rank = [1 / (np.argmax(row) + 1) if row.any() else 0.0 for row in hits]
    return {
        "available": True,
        "k": int(k),
        "ndcg_at_k": _round(ndcg.mean()),
        "mrr_at_k": _round(np.mean(reciprocal_rank)),
        "precision_at_k": _round(hits.mean()),
        "hit_rate_at_k": _round(hits.any(axis=1).mean()),
        "users": int(values.shape[0]),
        "recommendations_supplied": recommendations is not None,
    }


def _token_set(value: Any) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", str(value or "").lower()))


def llm_metrics(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Evaluate provider-neutral LLM records using transparent lexical checks."""
    rows = list(records)
    if not rows:
        return {"available": False, "reason": "records are empty"}
    relevance, groundedness, citation = [], [], []
    for row in rows:
        answer = _token_set(row.get("answer"))
        question = _token_set(row.get("question"))
        context = _token_set(row.get("context"))
        relevance.append(len(answer & question) / max(len(question), 1))
        groundedness.append(
            len(answer & context) / max(len(answer), 1) if answer else 0.0
        )
        citation.append(1.0 if row.get("citation") or row.get("citations") else 0.0)
    return {
        "available": True,
        "method": "token_overlap_baseline",
        "records": len(rows),
        "answer_relevance": _round(np.mean(relevance)),
        "groundedness": _round(np.mean(groundedness)),
        "citation_coverage": _round(np.mean(citation)),
    }


def rag_metrics(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Evaluate retrieval context coverage and answer grounding."""
    rows = list(records)
    if not rows:
        return {"available": False, "reason": "records are empty"}
    retrieval_hits, context_precision = [], []
    for row in rows:
        answer = _token_set(row.get("answer"))
        contexts = row.get("contexts") or row.get("context") or []
        if isinstance(contexts, str):
            contexts = [contexts]
        context_tokens = [_token_set(item) for item in contexts]
        union = set().union(*context_tokens) if context_tokens else set()
        retrieval_hits.append(float(bool(answer & union)))
        context_precision.append(
            float(np.mean([bool(answer & item) for item in context_tokens]))
            if context_tokens
            else 0.0
        )
    return {
        "available": True,
        "method": "token_overlap_baseline",
        "records": len(rows),
        "retrieval_hit_rate": _round(np.mean(retrieval_hits)),
        "context_precision": _round(np.mean(context_precision)),
    }
