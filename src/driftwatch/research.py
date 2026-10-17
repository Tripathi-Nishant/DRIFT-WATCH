"""Reproducible experiment runner for planted shifts and policy comparisons."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .pipeline import Monitor


def run_suite(out: str | Path, seeds: list[int] | None = None) -> dict[str, Any]:
    seeds = seeds or [1, 7, 42, 99]
    rows = []
    for seed in seeds:
        rng = np.random.default_rng(seed)
        reference = pd.DataFrame(
            {"stable": rng.normal(0, 1, 500), "shifted": rng.normal(0, 1, 500)}
        )
        clean = pd.DataFrame(
            {"stable": rng.normal(0, 1, 500), "shifted": rng.normal(0, 1, 500)}
        )
        planted = pd.DataFrame(
            {"stable": rng.normal(0, 1, 500), "shifted": rng.normal(2, 1, 500)}
        )
        clean_result = Monitor.from_reference(reference).run(clean)
        shifted_result = Monitor.from_reference(reference).run(planted)
        rows.extend(
            [
                {
                    "seed": seed,
                    "scenario": "clean",
                    "severity": clean_result.severity,
                    "decision": clean_result.decision,
                },
                {
                    "seed": seed,
                    "scenario": "shifted",
                    "severity": shifted_result.severity,
                    "decision": shifted_result.decision,
                },
            ]
        )
    result = {
        "seeds": seeds,
        "results": rows,
        "clean_false_alerts": sum(
            row["decision"] != "IGNORE" for row in rows if row["scenario"] == "clean"
        ),
        "shifted_actions": sum(
            row["decision"] == "ACT" for row in rows if row["scenario"] == "shifted"
        ),
    }
    clean = [row["decision"] != "IGNORE" for row in rows if row["scenario"] == "clean"]
    shifted = [row["decision"] == "ACT" for row in rows if row["scenario"] == "shifted"]
    result["confidence_intervals"] = {
        "clean_false_alert_rate_95": _interval(clean),
        "shifted_action_rate_95": _interval(shifted),
    }
    Path(out).write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def _interval(values: list[bool]) -> list[float]:
    if not values:
        return [0.0, 0.0]
    rate = sum(values) / len(values)
    margin = 1.96 * (rate * (1 - rate) / len(values)) ** 0.5
    return [round(max(0.0, rate - margin), 4), round(min(1.0, rate + margin), 4)]


def run_public_suite(out: str | Path, seeds: list[int] | None = None) -> dict[str, Any]:
    """Run planted shifts against built-in scikit-learn datasets."""
    from sklearn.datasets import load_breast_cancer, load_diabetes

    seeds = seeds or [1, 7, 42]
    datasets = [
        ("breast_cancer", load_breast_cancer().data),
        ("diabetes", load_diabetes().data),
    ]
    rows = []
    for dataset_name, values in datasets:
        for seed in seeds:
            rng = np.random.default_rng(seed)
            frame = pd.DataFrame(values[: min(500, len(values))])
            shifted = frame.copy()
            scale = max(0.1, float(shifted.iloc[:, 0].std()) * 2)
            shifted.iloc[:, 0] += rng.normal(0, scale, len(shifted))
            result = Monitor.from_reference(frame).run(shifted)
            rows.append(
                {
                    "dataset": dataset_name,
                    "seed": seed,
                    "severity": result.severity,
                    "decision": result.decision,
                }
            )
    summary = {
        "datasets": [name for name, _ in datasets],
        "seeds": seeds,
        "results": rows,
        "action_rate": sum(row["decision"] == "ACT" for row in rows) / len(rows),
    }
    Path(out).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
