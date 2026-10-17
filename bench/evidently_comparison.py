"""Matched-method benchmark against an installed Evidently version.

This intentionally reports side-by-side outputs instead of claiming identical
implementations. Run with ``pip install evidently`` in the benchmark env.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
from driftwatch import Monitor  # noqa: E402


def run(seed: int = 42) -> dict[str, object]:
    rng = np.random.default_rng(seed)
    reference = pd.DataFrame(
        {"x": rng.normal(0, 1, 2000), "group": rng.choice(["a", "b"], 2000)}
    )
    current = pd.DataFrame(
        {"x": rng.normal(0.8, 1.2, 2000), "group": rng.choice(["a", "b"], 2000)}
    )
    ours = Monitor.from_reference(reference).run(current).to_dict()
    evidently_result: dict[str, object]
    try:
        from evidently import Report
        from evidently.presets import DataDriftPreset

        report = Report([DataDriftPreset()]).run(
            current_data=current, reference_data=reference
        )
        evidently_result = {
            "available": True,
            "json_size": len(json.dumps(report.json())),
        }
    except ImportError:
        evidently_result = {
            "available": False,
            "reason": "install evidently to run comparison",
        }
    return {
        "driftwatch": {
            "drift_rate": ours["summary"]["drift_rate"],
            "drifted_features": ours["summary"]["drifted_features"],
            "auc": ours["multivariate"].get("auc"),
        },
        "evidently": evidently_result,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
