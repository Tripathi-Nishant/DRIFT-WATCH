"""Reusable monitoring metric families.

The functions in this module are deliberately dependency-light and return JSON
safe dictionaries. They are useful both to the tabular monitor and to custom
integrations that want Evidently-style metric/test primitives.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import ks_2samp


def _round(value: Any, digits: int = 6) -> Any:
    if value is None or (isinstance(value, float) and not np.isfinite(value)):
        return None
    if isinstance(value, (np.integer, np.floating)):
        return round(float(value), digits)
    return value


def data_quality_metrics(
    reference: pd.DataFrame, current: pd.DataFrame
) -> dict[str, Any]:
    """Return column-, dataset-, and schema-level quality measurements."""
    common = [name for name in reference.columns if name in current.columns]
    columns: dict[str, Any] = {}
    for name in common:
        before, after = reference[name], current[name]
        numeric = pd.api.types.is_numeric_dtype(
            before
        ) and pd.api.types.is_numeric_dtype(after)
        item: dict[str, Any] = {
            "dtype_reference": str(before.dtype),
            "dtype_current": str(after.dtype),
            "dtype_changed": str(before.dtype) != str(after.dtype),
            "reference_null_count": int(before.isna().sum()),
            "current_null_count": int(after.isna().sum()),
            "reference_null_rate": _round(before.isna().mean()),
            "current_null_rate": _round(after.isna().mean()),
            "reference_unique_count": int(before.nunique(dropna=True)),
            "current_unique_count": int(after.nunique(dropna=True)),
            "reference_unique_rate": _round(
                before.nunique(dropna=True) / max(len(before), 1)
            ),
            "current_unique_rate": _round(
                after.nunique(dropna=True) / max(len(after), 1)
            ),
            "is_constant_current": bool(after.nunique(dropna=True) <= 1),
        }
        if numeric:
            ref = pd.to_numeric(before, errors="coerce").dropna()
            cur = pd.to_numeric(after, errors="coerce").dropna()
            if len(ref) and len(cur):
                low, high = ref.quantile(0.01), ref.quantile(0.99)
                item.update(
                    {
                        "reference_mean": _round(ref.mean()),
                        "current_mean": _round(cur.mean()),
                        "reference_std": _round(ref.std()),
                        "current_std": _round(cur.std()),
                        "reference_min": _round(ref.min()),
                        "current_min": _round(cur.min()),
                        "reference_max": _round(ref.max()),
                        "current_max": _round(cur.max()),
                        "current_outlier_rate": _round(
                            ((cur < low) | (cur > high)).mean()
                        ),
                        "reference_quantiles": [
                            _round(v)
                            for v in ref.quantile([0.01, 0.25, 0.5, 0.75, 0.99])
                        ],
                        "current_quantiles": [
                            _round(v)
                            for v in cur.quantile([0.01, 0.25, 0.5, 0.75, 0.99])
                        ],
                    }
                )
        columns[name] = item
    return {
        "reference_rows": int(len(reference)),
        "current_rows": int(len(current)),
        "reference_columns": int(len(reference.columns)),
        "current_columns": int(len(current.columns)),
        "missing_columns": sorted(set(reference.columns) - set(current.columns)),
        "new_columns": sorted(set(current.columns) - set(reference.columns)),
        "duplicate_row_rate_reference": _round(reference.duplicated().mean()),
        "duplicate_row_rate_current": _round(current.duplicated().mean()),
        "columns": columns,
    }


def text_metrics(reference: pd.Series, current: pd.Series) -> dict[str, Any]:
    """Compare plain-text columns without requiring an NLP model."""
    ref = reference.fillna("").astype(str)
    cur = current.fillna("").astype(str)
    ref_lengths, cur_lengths = ref.str.len(), cur.str.len()
    ref_words, cur_words = ref.str.split().str.len(), cur.str.split().str.len()
    ks_stat, ks_p = (0.0, 1.0)
    if len(ref_lengths) and len(cur_lengths):
        ks_stat, ks_p = ks_2samp(ref_lengths, cur_lengths)
    return {
        "reference_empty_rate": _round((ref.str.len() == 0).mean()),
        "current_empty_rate": _round((cur.str.len() == 0).mean()),
        "reference_unique_rate": _round(ref.nunique() / max(len(ref), 1)),
        "current_unique_rate": _round(cur.nunique() / max(len(cur), 1)),
        "reference_mean_characters": _round(ref_lengths.mean()),
        "current_mean_characters": _round(cur_lengths.mean()),
        "reference_mean_words": _round(ref_words.mean()),
        "current_mean_words": _round(cur_words.mean()),
        "length_ks_statistic": _round(ks_stat),
        "length_ks_p_value": _round(ks_p),
        "new_empty_rate": _round(
            (cur.str.len() == 0).mean() - (ref.str.len() == 0).mean()
        ),
    }


def prediction_quality_metrics(
    predictions: Any, labels: Any, *, model_type: str = "classification"
) -> dict[str, Any]:
    """Return richer quality measurements for labelled prediction windows."""
    y_pred, y_true = np.asarray(predictions), np.asarray(labels)
    if len(y_pred) != len(y_true) or not len(y_true):
        return {
            "available": False,
            "reason": "equal non-zero prediction and label arrays required",
        }
    result: dict[str, Any] = {"available": True, "rows": int(len(y_true))}
    if model_type == "regression":
        residuals = y_true.astype(float) - y_pred.astype(float)
        result.update(
            {
                "residual_mean": _round(residuals.mean()),
                "residual_std": _round(residuals.std()),
                "residual_p95_abs": _round(np.quantile(np.abs(residuals), 0.95)),
                "target_mean": _round(y_true.mean()),
                "prediction_mean": _round(y_pred.mean()),
            }
        )
    else:
        classes, counts = np.unique(y_true, return_counts=True)
        predicted_classes, predicted_counts = np.unique(y_pred, return_counts=True)
        result.update(
            {
                "class_count": int(len(classes)),
                "label_distribution": {str(k): int(v) for k, v in zip(classes, counts)},
                "prediction_distribution": {
                    str(k): int(v) for k, v in zip(predicted_classes, predicted_counts)
                },
            }
        )
    return result


def run_tests(
    report: dict[str, Any],
    *,
    max_drift_rate: float = 0.2,
    min_quality_score: float = 80.0,
) -> list[dict[str, Any]]:
    """Evaluate portable monitoring assertions and return a test suite result."""
    summary = report.get("summary", {})
    drift_rate = float(summary.get("drift_rate", 0.0))
    quality_score = float(
        report.get("quality", {}).get("score", summary.get("quality_score", 0.0))
    )
    tests = [
        {
            "id": "drift_rate",
            "description": f"Drifted feature rate <= {max_drift_rate:.1%}",
            "passed": drift_rate <= max_drift_rate,
            "value": drift_rate,
            "threshold": max_drift_rate,
        },
        {
            "id": "data_quality",
            "description": f"Quality score >= {min_quality_score:.1f}",
            "passed": quality_score >= min_quality_score,
            "value": quality_score,
            "threshold": min_quality_score,
        },
    ]
    return tests


def metric_catalog() -> list[dict[str, str]]:
    """List supported metric families for UI/API discovery."""
    return [
        {"id": "psi", "family": "drift", "kind": "numeric"},
        {"id": "ks_statistic", "family": "drift", "kind": "numeric"},
        {"id": "ks_p_value", "family": "drift", "kind": "numeric"},
        {"id": "wasserstein", "family": "drift", "kind": "numeric"},
        {"id": "mean_shift", "family": "drift", "kind": "numeric"},
        {"id": "variance_shift", "family": "drift", "kind": "numeric"},
        {"id": "frequency_distance", "family": "drift", "kind": "categorical"},
        {"id": "chi_square", "family": "drift", "kind": "categorical"},
        {"id": "domain_classifier_auc", "family": "drift", "kind": "multivariate"},
        {"id": "null_rate", "family": "quality", "kind": "all"},
        {"id": "unique_rate", "family": "quality", "kind": "all"},
        {"id": "duplicate_row_rate", "family": "quality", "kind": "dataset"},
        {"id": "outlier_rate", "family": "quality", "kind": "numeric"},
        {"id": "text_length_ks", "family": "text", "kind": "text"},
        {"id": "empty_rate", "family": "text", "kind": "text"},
        {"id": "accuracy", "family": "performance", "kind": "classification"},
        {"id": "precision", "family": "performance", "kind": "classification"},
        {"id": "recall", "family": "performance", "kind": "classification"},
        {"id": "f1", "family": "performance", "kind": "classification"},
        {"id": "roc_auc", "family": "performance", "kind": "classification"},
        {"id": "mae", "family": "performance", "kind": "regression"},
        {"id": "rmse", "family": "performance", "kind": "regression"},
        {"id": "r2", "family": "performance", "kind": "regression"},
        {"id": "mape", "family": "performance", "kind": "regression"},
        {"id": "residual_mean", "family": "performance", "kind": "regression"},
        {"id": "residual_p95_abs", "family": "performance", "kind": "regression"},
        {"id": "drift_rate_test", "family": "tests", "kind": "assertion"},
        {"id": "quality_score_test", "family": "tests", "kind": "assertion"},
        {"id": "semantic_shift", "family": "text", "kind": "semantic"},
        {"id": "centroid_cosine_similarity", "family": "text", "kind": "semantic"},
        {"id": "pixel_histogram_distance", "family": "image", "kind": "image"},
        {"id": "image_shape_changed", "family": "image", "kind": "image"},
        {"id": "mean_pixel_shift", "family": "image", "kind": "image"},
        {"id": "ndcg_at_k", "family": "ranking", "kind": "ranking"},
        {"id": "mrr_at_k", "family": "ranking", "kind": "ranking"},
        {"id": "precision_at_k", "family": "ranking", "kind": "ranking"},
        {"id": "hit_rate_at_k", "family": "ranking", "kind": "ranking"},
        {"id": "answer_relevance", "family": "llm", "kind": "generation"},
        {"id": "groundedness", "family": "llm", "kind": "generation"},
        {"id": "citation_coverage", "family": "llm", "kind": "generation"},
        {"id": "retrieval_hit_rate", "family": "rag", "kind": "retrieval"},
        {"id": "context_precision", "family": "rag", "kind": "retrieval"},
    ]
