"""Core data-quality and drift calculations used by DriftWatch."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency, ks_2samp, wasserstein_distance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score


@dataclass
class FeatureResult:
    name: str
    kind: str
    drift_score: float
    drifted: bool
    missing_reference: float
    missing_current: float
    unique_reference: int
    unique_current: int
    reference_mean: float | None = None
    current_mean: float | None = None
    top_changes: list[dict[str, Any]] | None = None
    metrics: dict[str, Any] | None = None


def _number(value: Any) -> float | None:
    return None if pd.isna(value) else round(float(value), 6)


def _psi(reference: pd.Series, current: pd.Series, bins: int = 10) -> float:
    ref = pd.to_numeric(reference, errors="coerce").dropna().to_numpy()
    cur = pd.to_numeric(current, errors="coerce").dropna().to_numpy()
    if len(ref) == 0 or len(cur) == 0:
        return 0.0
    edges = np.unique(np.quantile(ref, np.linspace(0, 1, bins + 1)))
    if len(edges) < 3:
        return 0.0
    edges[0], edges[-1] = -np.inf, np.inf
    ref_hist = np.histogram(ref, bins=edges)[0].astype(float)
    cur_hist = np.histogram(cur, bins=edges)[0].astype(float)
    ref_hist = np.clip(ref_hist / len(ref), 1e-6, None)
    cur_hist = np.clip(cur_hist / len(cur), 1e-6, None)
    return float(np.sum((cur_hist - ref_hist) * np.log(cur_hist / ref_hist)))


def _categorical_drift(
    reference: pd.Series, current: pd.Series
) -> tuple[float, list[dict[str, Any]]]:
    ref = reference.fillna("<missing>").astype(str).value_counts(normalize=True)
    cur = current.fillna("<missing>").astype(str).value_counts(normalize=True)
    categories = set(ref.index) | set(cur.index)
    changes = []
    for category in categories:
        before = float(ref.get(category, 0))
        after = float(cur.get(category, 0))
        changes.append(
            {
                "value": category,
                "reference": round(before, 4),
                "current": round(after, 4),
                "change": round(after - before, 4),
            }
        )
    changes.sort(key=lambda row: abs(row["change"]), reverse=True)
    score = 0.5 * sum(abs(row["change"]) for row in changes)
    return min(score, 1.0), changes[:5]


def _domain_classifier_drift(
    reference: pd.DataFrame, current: pd.DataFrame
) -> dict[str, Any]:
    """Estimate joint shift by classifying reference rows from current rows."""
    shared = [column for column in reference.columns if column in current.columns]
    if len(reference) < 30 or len(current) < 30 or not shared:
        return {
            "available": False,
            "reason": "minimum samples or shared features not met",
        }
    combined = pd.concat([reference[shared], current[shared]], ignore_index=True)
    encoded = (
        pd.get_dummies(combined, dummy_na=True)
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0)
    )
    target = np.concatenate([np.zeros(len(reference)), np.ones(len(current))])
    try:
        model = LogisticRegression(max_iter=300, solver="liblinear")
        model.fit(encoded, target)
        probability = model.predict_proba(encoded)[:, 1]
        auc = float(roc_auc_score(target, probability))
        return {
            "available": True,
            "auc": round(max(auc, 1 - auc), 6),
            "interpretation": "higher values mean the joint distributions are easier to distinguish",
        }
    except ValueError as error:
        return {"available": False, "reason": str(error)}


def analyze(
    reference: pd.DataFrame, current: pd.DataFrame, threshold: float = 0.1
) -> dict[str, Any]:
    """Compare two tabular datasets and return JSON-safe monitoring results."""
    shared = [column for column in reference.columns if column in current.columns]
    features: list[FeatureResult] = []
    for name in shared:
        ref_col, cur_col = reference[name], current[name]
        numeric = pd.api.types.is_numeric_dtype(
            ref_col
        ) and pd.api.types.is_numeric_dtype(cur_col)
        if numeric:
            ref_values, cur_values = ref_col.dropna(), cur_col.dropna()
            score = _psi(ref_col, cur_col)
            kind = "numeric"
            changes = None
            ref_mean, cur_mean = _number(ref_values.mean()), _number(cur_values.mean())
            ks_stat, ks_p = (0.0, 1.0)
            if len(ref_values) and len(cur_values):
                ks_stat, ks_p = ks_2samp(ref_values, cur_values)
            metrics = {
                "psi": round(score, 6),
                "ks_statistic": round(float(ks_stat), 6),
                "ks_p_value": round(float(ks_p), 6),
                "wasserstein": round(
                    float(wasserstein_distance(ref_values, cur_values)), 6
                )
                if len(ref_values) and len(cur_values)
                else 0.0,
                "mean_shift": round(float(cur_values.mean() - ref_values.mean()), 6)
                if len(ref_values) and len(cur_values)
                else 0.0,
                "variance_shift": round(float(cur_values.var() - ref_values.var()), 6)
                if len(ref_values) and len(cur_values)
                else 0.0,
            }
            if len(ref_values) and len(cur_values):
                edges = np.linspace(
                    min(float(ref_values.min()), float(cur_values.min())),
                    max(float(ref_values.max()), float(cur_values.max())),
                    9,
                )
                if len(np.unique(edges)) > 2:
                    metrics["histogram_edges"] = [
                        round(float(edge), 6) for edge in edges
                    ]
                    metrics["reference_histogram"] = [
                        int(value) for value in np.histogram(ref_values, bins=edges)[0]
                    ]
                    metrics["current_histogram"] = [
                        int(value) for value in np.histogram(cur_values, bins=edges)[0]
                    ]
        else:
            score, changes = _categorical_drift(ref_col, cur_col)
            kind = "categorical"
            ref_mean = cur_mean = None
            categories = sorted(
                set(ref_col.fillna("<missing>").astype(str))
                | set(cur_col.fillna("<missing>").astype(str))
            )
            ref_counts = ref_col.fillna("<missing>").astype(str).value_counts()
            cur_counts = cur_col.fillna("<missing>").astype(str).value_counts()
            table = [
                [int(ref_counts.get(category, 0)), int(cur_counts.get(category, 0))]
                for category in categories
            ]
            chi_stat, chi_p = (0.0, 1.0)
            if len(table) > 1:
                chi_stat, chi_p, _, _ = chi2_contingency(table)
            metrics = {
                "frequency_distance": round(score, 6),
                "chi_square": round(float(chi_stat), 6),
                "chi_square_p_value": round(float(chi_p), 6),
                "new_categories": sorted(set(cur_counts.index) - set(ref_counts.index)),
            }
        features.append(
            FeatureResult(
                name,
                kind,
                round(score, 6),
                score >= threshold,
                round(float(ref_col.isna().mean()), 4),
                round(float(cur_col.isna().mean()), 4),
                int(ref_col.nunique(dropna=True)),
                int(cur_col.nunique(dropna=True)),
                ref_mean,
                cur_mean,
                changes,
                metrics,
            )
        )

    drifted = sum(item.drifted for item in features)
    all_missing = (
        float(pd.concat([reference, current]).isna().mean().mean()) if shared else 0.0
    )
    result = {
        "summary": {
            "reference_rows": int(len(reference)),
            "current_rows": int(len(current)),
            "features": len(features),
            "drifted_features": drifted,
            "drift_rate": round(drifted / len(features), 4) if features else 0,
            "quality_score": round(max(0, 100 * (1 - all_missing)), 1),
            "status": "critical"
            if drifted >= max(1, len(features) // 2)
            else ("warning" if drifted else "healthy"),
        },
        "features": [
            asdict(item)
            for item in sorted(
                features, key=lambda item: item.drift_score, reverse=True
            )
        ],
        "multivariate": _domain_classifier_drift(reference, current),
    }
    for item in result["features"]:
        if item["drifted"]:
            before = item.get("reference_mean")
            after = item.get("current_mean")
            if before is not None and after is not None:
                item["explanation"] = (
                    f"Possible contributing factor: {item['name']} changed "
                    f"from {before:.3f} to {after:.3f}."
                )
            else:
                item["explanation"] = (
                    f"Possible contributing factor: the category distribution "
                    f"for {item['name']} changed."
                )
        else:
            item["explanation"] = (
                f"{item['name']} remains within the configured drift threshold."
            )
        item["category"] = item["kind"]
    return result


def demo_datasets() -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(42)
    reference = pd.DataFrame(
        {
            "latency_ms": rng.normal(180, 24, 1000),
            "basket_value": rng.lognormal(3.2, 0.45, 1000),
            "plan": rng.choice(["free", "pro", "team"], 1000, p=[0.62, 0.3, 0.08]),
            "region": rng.choice(
                ["us-east", "eu-west", "ap-south"], 1000, p=[0.45, 0.35, 0.2]
            ),
        }
    )
    current = pd.DataFrame(
        {
            "latency_ms": rng.normal(216, 33, 800),
            "basket_value": rng.lognormal(3.35, 0.58, 800),
            "plan": rng.choice(["free", "pro", "team"], 800, p=[0.42, 0.43, 0.15]),
            "region": rng.choice(
                ["us-east", "eu-west", "ap-south"], 800, p=[0.38, 0.36, 0.26]
            ),
        }
    )
    current.loc[rng.choice(current.index, 34, replace=False), "basket_value"] = np.nan
    return reference, current
