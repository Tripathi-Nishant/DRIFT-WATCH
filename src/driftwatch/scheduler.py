"""Simple local scheduler for cron-like monitoring without a queue dependency."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from .pipeline import Monitor
from .storage import Store


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
        model_type=config.get("task", config.get("model_type", "auto")),
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


def run_due_schedules(store: Store, organization_id: str) -> list[dict[str, Any]]:
    """Execute enabled persisted schedules and record an auditable run result.

    A schedule config must contain ``reference_path``, ``current_path``, and
    ``output_path``. Cadence accepts ``hourly``, ``daily``, or an integer number
    of seconds.
    """
    now = datetime.now(UTC)
    results: list[dict[str, Any]] = []
    for schedule in store.list_schedules(organization_id):
        if not schedule["enabled"]:
            continue
        due_at = _parse_time(schedule.get("next_run_at"))
        if due_at and due_at > now:
            continue
        started = now.isoformat()
        config = schedule.get("config") or {}
        try:
            required = ("reference_path", "current_path", "output_path")
            missing = [key for key in required if not config.get(key)]
            if missing:
                raise ValueError(f"schedule config missing: {', '.join(missing)}")
            severity = run_once(
                config["reference_path"], config["current_path"],
                config["output_path"], config,
            )
            completed = datetime.now(UTC)
            result = store.record_schedule_run(
                schedule, "SUCCEEDED", started, completed.isoformat(),
                severity, output_path=config["output_path"],
            )
            results.append(result)
        except (OSError, ValueError, KeyError) as error:
            result = store.record_schedule_run(
                schedule, "FAILED", started, datetime.now(UTC).isoformat(),
                detail=str(error), output_path=config.get("output_path"),
            )
            results.append(result)
        _advance_schedule(store, schedule, now)
    return results


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _advance_schedule(store: Store, schedule: dict[str, Any], now: datetime) -> None:
    cadence = str(schedule["cadence"]).strip().lower()
    if cadence == "hourly":
        delta = timedelta(hours=1)
    elif cadence == "daily":
        delta = timedelta(days=1)
    else:
        delta = timedelta(seconds=max(1, int(cadence)))
    next_run = now + delta
    with store._lock, store._connect() as db:
        db.execute(
            "UPDATE schedules SET last_run_at = ?, next_run_at = ? WHERE id = ? AND organization_id = ?",
            (now.isoformat(), next_run.isoformat(), schedule["id"], schedule["organization_id"]),
        )
