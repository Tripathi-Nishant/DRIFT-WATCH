"""Simple local scheduler for cron-like monitoring without a queue dependency."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pandas as pd

from .pipeline import Monitor


def run_once(
    reference_path: str,
    current_path: str,
    output_path: str,
    config: dict[str, Any] | None = None,
) -> str:
    config = config or {}
    def read(path: str) -> pd.DataFrame:
        return (
            pd.read_parquet(path)
            if Path(path).suffix.lower() == ".parquet"
            else pd.read_csv(path)
        )
    result = Monitor.from_reference(
        read(reference_path),
        model_name=config.get("model_name", "scheduled-model"),
        model_type=config.get("model_type", "classification"),
        decision_config=config.get("decision"),
    ).run(read(current_path))
    result.save_html(output_path)
    return result.severity


def watch(
    reference_path: str,
    current_path: str,
    output_path: str,
    interval_seconds: int = 3600,
    config: dict[str, Any] | None = None,
) -> None:
    """Run repeatedly until interrupted; intended for a small self-hosted machine."""
    while True:
        severity = run_once(reference_path, current_path, output_path, config)
        print(f"DriftWatch scheduled run complete: {severity}")
        time.sleep(interval_seconds)
