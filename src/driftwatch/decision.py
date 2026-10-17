"""Transparent severity, impact, recommendation, and decision policy."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DecisionConfig:
    """Configurable policy; values are rules, not learned research results."""

    drift_warning: float = 0.10
    drift_high: float = 0.25
    warning_share: float = 0.20
    high_share: float = 0.50
    min_samples: int = 30
    performance_tolerance: float = 0.03
    currency: str = "INR"
    period_volume: float | None = None
    cost_false_negative: float | None = None
    cost_false_positive: float | None = None
    action_cost: float | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, values: dict[str, Any] | None) -> DecisionConfig:
        if not values:
            return cls()
        allowed = set(cls.__dataclass_fields__) - {"extra"}
        known = {key: value for key, value in values.items() if key in allowed}
        known["extra"] = {
            key: value for key, value in values.items() if key not in allowed
        }
        return cls(**known)


def evaluate_decision(summary, features, quality, performance, config):
    rows = max(summary.get("current_rows", 0), 0)
    drifted = [item for item in features if item.get("drifted")]
    high_drifted = [
        item for item in features if item.get("drift_score", 0) >= config.drift_high
    ]
    share = len(drifted) / max(1, len(features))
    trace = []
    reasons = []
    trace.append(
        {
            "rule": "minimum_sample_guard",
            "passed": rows >= config.min_samples,
            "value": rows,
            "threshold": config.min_samples,
        }
    )
    if rows < config.min_samples:
        reasons.append(
            f"Only {rows} current rows are available; confidence is limited "
            f"below {config.min_samples} rows."
        )
    trace.append(
        {
            "rule": "high_drift_share",
            "passed": share >= config.high_share,
            "value": round(share, 4),
            "threshold": config.high_share,
        }
    )
    trace.append(
        {
            "rule": "high_score_features",
            "passed": bool(high_drifted),
            "value": len(high_drifted),
            "threshold": config.drift_high,
        }
    )
    if drifted:
        reasons.append(
            f"{len(drifted)} of {len(features)} features exceeded the drift threshold."
        )
    if high_drifted:
        reasons.append(
            f"{len(high_drifted)} feature(s) reached the high-drift threshold "
            f"of {config.drift_high}."
        )
    multivariate = summary.get("multivariate") or {}
    joint_shift = bool(
        multivariate.get("available") and multivariate.get("auc", 0) >= 0.65
    )
    trace.append(
        {
            "rule": "multivariate_domain_auc",
            "passed": joint_shift,
            "value": multivariate.get("auc"),
            "threshold": 0.65,
        }
    )
    if joint_shift:
        reasons.append(
            f"A domain classifier separated reference and current rows with AUC {multivariate['auc']:.3f}; this is evidence of joint distribution shift."
        )
    performance_drop = False
    if performance and performance.get("available"):
        metric = "r2" if "r2" in performance else "f1" if "f1" in performance else None
        if metric and performance[metric] < 1 - config.performance_tolerance:
            performance_drop = True
            trace.append(
                {
                    "rule": "labelled_performance_drop",
                    "passed": True,
                    "metric": metric,
                    "value": performance[metric],
                    "tolerance": config.performance_tolerance,
                }
            )
            reasons.append(
                f"Labelled {metric} is {performance[metric]:.3f}; performance "
                "evidence is available."
            )
        elif metric:
            trace.append(
                {
                    "rule": "labelled_performance_drop",
                    "passed": False,
                    "metric": metric,
                    "value": performance[metric],
                    "tolerance": config.performance_tolerance,
                }
            )
    low_confidence = (
        rows < config.min_samples or not performance or not performance.get("available")
    )
    if (
        share >= config.high_share
        or (high_drifted and performance_drop)
        or (joint_shift and high_drifted)
    ):
        severity = "CRITICAL"
    elif (
        high_drifted or share >= config.warning_share or performance_drop or joint_shift
    ):
        severity = "HIGH"
    elif drifted or quality.get("findings"):
        severity = "WARNING"
    else:
        severity = "NORMAL"
    decision = (
        "ACT"
        if severity in {"HIGH", "CRITICAL"}
        else "MONITOR"
        if severity == "WARNING"
        else "IGNORE"
    )
    confidence = (
        "LOW" if low_confidence else "MEDIUM" if severity == "WARNING" else "HIGH"
    )
    action = {
        "ACT": "Investigate affected features and compare a candidate model "
        "before approving retraining or a deployment change.",
        "MONITOR": "Keep monitoring the next windows and collect labels "
        "before escalating.",
        "IGNORE": "No action required; continue routine monitoring.",
    }[decision]
    recommendation_type = {
        "ACT": "RETRAIN" if performance_drop else "INVESTIGATE",
        "MONITOR": "COLLECT_LABELS" if low_confidence else "MONITOR",
        "IGNORE": "IGNORE",
    }[decision]
    if low_confidence:
        action += " This result is low-confidence because labelled outcomes or "
        "sufficient sample size are unavailable."
    return {
        "severity": severity,
        "decision": decision,
        "confidence": confidence,
        "low_confidence": low_confidence,
        "reasons": reasons,
        "recommendation": action,
        "recommendation_type": recommendation_type,
        "impact_estimate": estimate_impact(severity, config),
        "rule_trace": trace,
    }


def estimate_impact(severity: str, config: DecisionConfig) -> dict[str, Any] | None:
    if config.period_volume is None or config.cost_false_negative is None:
        return None
    multiplier = {"NORMAL": 0.0, "WARNING": 0.10, "HIGH": 0.25, "CRITICAL": 0.50}[
        severity
    ]
    estimated = config.period_volume * multiplier * config.cost_false_negative
    action_cost = config.action_cost or 0.0
    return {
        "label": "estimate",
        "currency": config.currency,
        "assumptions": {
            "period_volume": config.period_volume,
            "cost_false_negative": config.cost_false_negative,
            "action_cost": action_cost,
        },
        "estimated_exposure": round(estimated, 2),
        "estimated_net_exposure_after_action": round(
            max(0.0, estimated - action_cost), 2
        ),
    }
