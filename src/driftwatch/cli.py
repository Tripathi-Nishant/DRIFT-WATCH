"""Command line interface for profile and monitoring workflows."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from .pipeline import Monitor, ReferenceProfile
from .retraining import approve_request, create_request
from .scheduler import watch
from .server import run as run_server


def _read_table(path: str) -> pd.DataFrame:
    source = Path(path)
    if source.suffix.lower() in {".parquet", ".pq"}:
        return pd.read_parquet(source)
    return pd.read_csv(source)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="driftwatch", description="Detect, understand and act on ML data changes."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    profile = sub.add_parser("profile", help="Save a compact reference profile")
    profile.add_argument("--reference", required=True)
    profile.add_argument("--out", required=True)
    run = sub.add_parser("run", help="Run a monitor and write JSON/HTML results")
    run.add_argument("--reference", required=True)
    run.add_argument("--current", required=True)
    run.add_argument("--out", required=True)
    run.add_argument("--target")
    run.add_argument("--predictions")
    run.add_argument("--labels")
    run.add_argument(
        "--model-type",
        default="classification",
        choices=["classification", "regression"],
    )
    run.add_argument("--model-name", default="model")
    run.add_argument("--config", help="JSON configuration file")
    serve = sub.add_parser("serve", help="Start the local dashboard server")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", default=8765, type=int)
    schedule = sub.add_parser(
        "schedule", help="Run monitoring repeatedly on an interval"
    )
    schedule.add_argument("--reference", required=True)
    schedule.add_argument("--current", required=True)
    schedule.add_argument("--out", required=True)
    schedule.add_argument("--interval", default=3600, type=int)
    retrain = sub.add_parser(
        "retrain", help="Create or approve an advisory retraining request"
    )
    retrain.add_argument("--report", required=True)
    retrain.add_argument("--out", required=True)
    retrain.add_argument("--approve-by")
    args = parser.parse_args(argv)
    if args.command == "profile":
        ReferenceProfile.from_dataframe(_read_table(args.reference)).save(args.out)
        print(f"Saved reference profile to {args.out}")
        return 0
    if args.command == "serve":
        run_server(args.host, args.port)
        return 0
    if args.command == "schedule":
        watch(args.reference, args.current, args.out, args.interval)
        return 0
    if args.command == "retrain":
        if args.approve_by:
            print(json.dumps(approve_request(args.out, args.approve_by), indent=2))
        else:
            report = json.loads(Path(args.report).read_text(encoding="utf-8"))
            print(json.dumps(create_request(report, args.out), indent=2))
        return 0
    reference, current = _read_table(args.reference), _read_table(args.current)
    predictions = (
        pd.read_csv(args.predictions).squeeze().to_numpy() if args.predictions else None
    )
    labels = pd.read_csv(args.labels).squeeze().to_numpy() if args.labels else None
    config = (
        json.loads(Path(args.config).read_text(encoding="utf-8")) if args.config else {}
    )
    result = Monitor.from_reference(
        reference,
        target=args.target,
        model_type=args.model_type,
        model_name=args.model_name,
        threshold=config.get("threshold", 0.1),
        decision_config=config.get("decision", config.get("thresholds", {})),
    ).run(current, predictions=predictions, labels=labels)
    output = Path(args.out)
    if output.suffix.lower() == ".html":
        result.save_html(output)
    else:
        result.save_json(output)
    print(
        json.dumps(
            {
                "severity": result.severity,
                "decision": result.decision,
                "out": str(output),
            }
        )
    )
    return {"NORMAL": 0, "WARNING": 1, "HIGH": 2, "CRITICAL": 3}[result.severity]
