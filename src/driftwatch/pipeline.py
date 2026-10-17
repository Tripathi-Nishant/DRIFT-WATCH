"""User-facing monitor pipeline for the DriftWatch R1 library surface."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    mean_absolute_error,
    mean_absolute_percentage_error,
    mean_squared_error,
    precision_score,
    recall_score,
    r2_score,
    roc_auc_score,
)

from .decision import DecisionConfig, evaluate_decision
from .advanced_metrics import (
    image_metrics,
    llm_metrics,
    rag_metrics,
    ranking_metrics,
    semantic_text_metrics,
)
from .metrics import (
    data_quality_metrics,
    prediction_quality_metrics,
    run_tests,
    text_metrics,
)
from .monitor import analyze


def _jsonable(value: Any) -> Any:
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    return value


@dataclass
class ReferenceProfile:
    """Portable, data-free summary of a reference dataset."""

    schema: dict[str, dict[str, Any]]
    rows: int
    created_at: str
    engine_version: str = "0.2.0"

    @classmethod
    def from_dataframe(cls, data: pd.DataFrame) -> ReferenceProfile:
        schema: dict[str, dict[str, Any]] = {}
        for name in data.columns:
            column = data[name]
            info: dict[str, Any] = {
                "dtype": str(column.dtype),
                "kind": "numeric"
                if pd.api.types.is_numeric_dtype(column)
                else "categorical",
                "missing_rate": round(float(column.isna().mean()), 6),
                "unique": int(column.nunique(dropna=True)),
            }
            if info["kind"] == "numeric":
                info.update(
                    {
                        "mean": _jsonable(column.mean()),
                        "std": _jsonable(column.std()),
                        "min": _jsonable(column.min()),
                        "max": _jsonable(column.max()),
                        "quantiles": [
                            _jsonable(value)
                            for value in column.dropna()
                            .quantile([0.01, 0.25, 0.5, 0.75, 0.99])
                            .tolist()
                        ],
                    }
                )
            else:
                info["categories"] = {
                    str(key): int(value)
                    for key, value in column.fillna("<missing>")
                    .value_counts()
                    .head(100)
                    .items()
                }
            schema[name] = info
        return cls(
            schema=schema,
            rows=len(data),
            created_at=pd.Timestamp.now(tz="UTC").isoformat(),
        )

    def save(self, path: str | Path) -> None:
        Path(path).write_text(
            json.dumps(asdict(self), indent=2, default=_jsonable), encoding="utf-8"
        )

    @classmethod
    def load(cls, path: str | Path) -> ReferenceProfile:
        return cls(**json.loads(Path(path).read_text(encoding="utf-8")))


@dataclass
class MonitorResult:
    report: dict[str, Any]

    @property
    def severity(self) -> str:
        return self.report["summary"]["severity"]

    @property
    def decision(self) -> str:
        return self.report["summary"]["decision"]

    def to_dict(self) -> dict[str, Any]:
        return self.report

    def save_json(self, path: str | Path) -> None:
        Path(path).write_text(
            json.dumps(self.report, indent=2, default=_jsonable), encoding="utf-8"
        )

    def save_html(self, path: str | Path) -> None:
        from .report import render_html

        Path(path).write_text(render_html(self.report), encoding="utf-8")


def _quality(reference: pd.DataFrame, current: pd.DataFrame) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    missing_columns = sorted(set(reference.columns) - set(current.columns))
    new_columns = sorted(set(current.columns) - set(reference.columns))
    if missing_columns:
        findings.append(
            {
                "category": "schema",
                "severity": "HIGH",
                "message": f"Missing columns: {', '.join(missing_columns)}",
            }
        )
    if new_columns:
        findings.append(
            {
                "category": "schema",
                "severity": "WARNING",
                "message": f"New columns: {', '.join(new_columns)}",
            }
        )
    common = [name for name in reference.columns if name in current.columns]
    for name in common:
        before, after = reference[name], current[name]
        if str(before.dtype) != str(after.dtype):
            findings.append(
                {
                    "category": "schema",
                    "feature": name,
                    "severity": "HIGH",
                    "message": f"Type changed from {before.dtype} to {after.dtype}.",
                }
            )
        missing_delta = float(after.isna().mean() - before.isna().mean())
        if missing_delta > 0.05:
            findings.append(
                {
                    "category": "missingness",
                    "feature": name,
                    "severity": "WARNING",
                    "message": f"Missing values increased by {missing_delta:.1%}.",
                }
            )
        if after.duplicated().mean() > 0.9 and len(after) > 10:
            findings.append(
                {
                    "category": "duplicates",
                    "feature": name,
                    "severity": "WARNING",
                    "message": "Feature has very low variety in the current window.",
                }
            )
        if pd.api.types.is_numeric_dtype(before) and pd.api.types.is_numeric_dtype(
            after
        ):
            lower, upper = before.quantile(0.01), before.quantile(0.99)
            outlier_rate = float(((after < lower) | (after > upper)).mean())
            if outlier_rate > 0.05:
                findings.append(
                    {
                        "category": "outlier",
                        "feature": name,
                        "severity": "WARNING",
                        "message": f"{outlier_rate:.1%} of current values fall outside the reference 1st–99th percentile range.",
                    }
                )
        else:
            old_categories = set(before.dropna().astype(str))
            new_categories = sorted(set(after.dropna().astype(str)) - old_categories)
            if new_categories:
                findings.append(
                    {
                        "category": "category",
                        "feature": name,
                        "severity": "WARNING",
                        "message": f"New categories observed: {', '.join(new_categories[:5])}.",
                    }
                )
    total_missing = float(current[common].isna().mean().mean()) if common else 1.0
    duplicate_rate = float(current.duplicated().mean()) if len(current) else 0.0
    score = max(
        0.0,
        100.0
        - total_missing * 100.0
        - duplicate_rate * 20.0
        - len(missing_columns) * 10.0,
    )
    return {
        "score": round(score, 2),
        "missing_rate": round(total_missing, 6),
        "duplicate_rate": round(duplicate_rate, 6),
        "findings": findings,
    }


def _performance(
    predictions: Any, labels: Any, model_type: str
) -> dict[str, Any] | None:
    if predictions is None or labels is None:
        return None
    prediction_values = np.asarray(predictions)
    label_values = np.asarray(labels)
    if len(prediction_values) != len(label_values) or not len(label_values):
        return {
            "available": False,
            "message": "Predictions and labels must have equal non-zero length.",
        }
    result: dict[str, Any] = {
        "available": True,
        "label_coverage": 1.0,
        "model_type": model_type,
    }
    if model_type == "regression":
        result.update(
            {
                "mae": round(
                    float(mean_absolute_error(label_values, prediction_values)), 6
                ),
                "rmse": round(
                    float(mean_squared_error(label_values, prediction_values) ** 0.5), 6
                ),
                "r2": round(float(r2_score(label_values, prediction_values)), 6),
                "mape": round(
                    float(
                        mean_absolute_percentage_error(label_values, prediction_values)
                    ),
                    6,
                ),
            }
        )
    else:
        labels_int = label_values.astype(int)
        predicted = (
            (prediction_values >= 0.5).astype(int)
            if np.issubdtype(prediction_values.dtype, np.floating)
            and len(np.unique(labels_int)) == 2
            else prediction_values.astype(int)
        )
        result.update(
            {
                "accuracy": round(float(accuracy_score(labels_int, predicted)), 6),
                "f1": round(
                    float(f1_score(labels_int, predicted, average="weighted")), 6
                ),
                "precision": round(
                    float(
                        precision_score(
                            labels_int, predicted, average="weighted", zero_division=0
                        )
                    ),
                    6,
                ),
                "recall": round(
                    float(
                        recall_score(
                            labels_int, predicted, average="weighted", zero_division=0
                        )
                    ),
                    6,
                ),
            }
        )
        if len(np.unique(labels_int)) == 2 and len(np.unique(prediction_values)) > 1:
            result["roc_auc"] = round(
                float(roc_auc_score(labels_int, prediction_values)), 6
            )
    return result


class Monitor:
    """Run repeatable monitoring against a DataFrame or saved reference profile."""

    def __init__(
        self,
        reference: pd.DataFrame,
        *,
        target: str | None = None,
        model_type: str = "classification",
        threshold: float = 0.1,
        model_name: str = "model",
        decision_config: DecisionConfig | dict[str, Any] | None = None,
        reference_predictions: Any = None,
        alert_callback: Any = None,
    ) -> None:
        self.reference = reference.copy()
        self.target = target
        self.model_type = model_type
        self.threshold = threshold
        self.model_name = model_name
        self.decision_config = (
            decision_config
            if isinstance(decision_config, DecisionConfig)
            else DecisionConfig.from_dict(decision_config)
        )
        self.reference_predictions = reference_predictions
        self.alert_callback = alert_callback
        self.profile = ReferenceProfile.from_dataframe(reference)

    @classmethod
    def from_reference(cls, reference: pd.DataFrame, **kwargs: Any) -> Monitor:
        return cls(reference, **kwargs)

    @classmethod
    def from_profile(cls, profile: ReferenceProfile, **kwargs: Any) -> Monitor:
        raise ValueError(
            "A profile contains summaries only. Use Monitor.from_reference for "
            "in-memory "
            "analysis or provide the original feature data."
        )

    def run(
        self,
        current: pd.DataFrame,
        *,
        predictions: Any = None,
        labels: Any = None,
        group_by: str | None = None,
        semantic_text: tuple[Any, Any] | None = None,
        images: tuple[Any, Any] | None = None,
        ranking_relevance: Any = None,
        llm_records: Any = None,
        rag_records: Any = None,
    ) -> MonitorResult:
        reference_features = self.reference.drop(columns=[self.target], errors="ignore")
        current_features = current.drop(columns=[self.target], errors="ignore")
        base = analyze(reference_features, current_features, threshold=self.threshold)
        quality = _quality(reference_features, current_features)
        base["summary"]["multivariate"] = base.get("multivariate", {})
        performance = _performance(predictions, labels, self.model_type)
        decision = evaluate_decision(
            base["summary"],
            base["features"],
            quality,
            performance,
            self.decision_config,
        )
        config_hash = hashlib.sha256(
            json.dumps(
                {"threshold": self.threshold, "model_type": self.model_type},
                sort_keys=True,
            ).encode()
        ).hexdigest()[:12]
        base["summary"].update(
            {
                "model": self.model_name,
                "severity": decision["severity"],
                "decision": decision["decision"],
                "confidence": decision["confidence"],
                "low_confidence": decision["low_confidence"],
                "quality_score": quality["score"],
                "config_hash": config_hash,
                "recommendation": decision["recommendation"],
                "recommendation_type": decision["recommendation_type"],
                "reasons": decision["reasons"],
                "impact_estimate": decision["impact_estimate"],
                "rule_trace": decision["rule_trace"],
                "honesty_note": "Statistical drift is not proof of concept drift; "
                "concept drift requires labelled performance evidence.",
            }
        )
        base.update(
            {
                "quality": quality,
                "quality_metrics": data_quality_metrics(
                    reference_features, current_features
                ),
                "performance": performance,
                "profile": asdict(self.profile),
            }
        )
        text_report: dict[str, Any] = {}
        for name in reference_features.columns:
            if name not in current_features.columns:
                continue
            if reference_features[
                name
            ].dtype == "object" or pd.api.types.is_string_dtype(
                reference_features[name]
            ):
                text_report[name] = text_metrics(
                    reference_features[name], current_features[name]
                )
        if text_report:
            base["text_metrics"] = text_report
        if predictions is not None and labels is not None:
            base["prediction_quality"] = prediction_quality_metrics(
                predictions, labels, model_type=self.model_type
            )
        if semantic_text is not None:
            base["semantic_text"] = semantic_text_metrics(*semantic_text)
        if images is not None:
            base["image_metrics"] = image_metrics(*images)
        if ranking_relevance is not None:
            base["ranking_metrics"] = ranking_metrics(ranking_relevance)
        if llm_records is not None:
            base["llm_metrics"] = llm_metrics(llm_records)
        if rag_records is not None:
            base["rag_metrics"] = rag_metrics(rag_records)
        base["tests"] = run_tests(base)
        if (
            group_by
            and group_by in reference_features.columns
            and group_by in current_features.columns
        ):
            subgroup_results = {}
            for group in sorted(
                set(current_features[group_by].dropna().astype(str))
                & set(reference_features[group_by].dropna().astype(str))
            ):
                ref_group = reference_features[
                    reference_features[group_by].astype(str) == group
                ].drop(columns=[group_by])
                cur_group = current_features[
                    current_features[group_by].astype(str) == group
                ].drop(columns=[group_by])
                subgroup_results[group] = analyze(
                    ref_group, cur_group, threshold=self.threshold
                )["summary"]
            base["subgroups"] = subgroup_results
        if self.reference_predictions is not None and predictions is not None:
            prediction_report = analyze(
                pd.DataFrame({"prediction": self.reference_predictions}),
                pd.DataFrame({"prediction": predictions}),
                threshold=self.threshold,
            )
            base["prediction_drift"] = prediction_report["features"][0]
            base["summary"]["prediction_drifted"] = (
                prediction_report["summary"]["drifted_features"] > 0
            )
        if self.alert_callback and decision["severity"] in {"HIGH", "CRITICAL"}:
            self.alert_callback(MonitorResult(base))
        return MonitorResult(base)
