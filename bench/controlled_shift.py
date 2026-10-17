"""Reproducible smoke benchmark for planted numeric drift."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from driftwatch import Monitor


def run(seed: int = 42) -> dict[str, object]:
    rng = np.random.default_rng(seed)
    reference = pd.DataFrame(
        {"signal": rng.normal(0, 1, 1000), "stable": rng.normal(0, 1, 1000)}
    )
    shifted = pd.DataFrame(
        {"signal": rng.normal(2.5, 1, 1000), "stable": rng.normal(0, 1, 1000)}
    )
    result = Monitor.from_reference(reference, model_name="benchmark").run(shifted)
    return {
        "seed": seed,
        "severity": result.severity,
        "decision": result.decision,
        "features": result.report["features"],
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
