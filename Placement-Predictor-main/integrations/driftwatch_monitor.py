"""Send placement-model monitoring data to a running DriftWatch instance.

Example:
    python integrations/driftwatch_monitor.py \
      --email student@example.com --password your-password
"""

from __future__ import annotations

import argparse
import json
import pickle
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _post(url: str, payload: dict, token: str | None = None) -> dict:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"DriftWatch returned HTTP {error.code}: {detail}") from error
    except URLError as error:
        raise RuntimeError(f"Could not reach DriftWatch: {error.reason}") from error


def _records(frame: pd.DataFrame) -> list[dict]:
    """Convert pandas values to JSON-safe records, including NaN handling."""
    return json.loads(frame.to_json(orient="records"))


def _values(path: str | None) -> list | None:
    if not path:
        return None
    frame = pd.read_csv(path)
    if frame.shape[1] != 1:
        raise ValueError(f"Label file must contain exactly one column: {path}")
    return json.loads(frame.to_json(orient="values"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Monitor the placement model with DriftWatch")
    parser.add_argument("--api-url", default="http://127.0.0.1:8765")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--reference", default=str(PROJECT_ROOT / "data/processed/X_prepared.csv"))
    parser.add_argument("--current", default=str(PROJECT_ROOT / "data/processed/X_prepared.csv"))
    parser.add_argument("--model-path", default=str(PROJECT_ROOT / "models/placement_model.pkl"))
    parser.add_argument("--reference-labels")
    parser.add_argument("--current-labels", default=str(PROJECT_ROOT / "data/processed/Y_prepared.csv"))
    parser.add_argument("--model-name", default="placement-logistic-regression")
    args = parser.parse_args()

    reference = pd.read_csv(args.reference)
    current = pd.read_csv(args.current)
    with open(args.model_path, "rb") as file:
        model = pickle.load(file)
    current_predictions = model.predict(current).tolist()
    labels = _values(args.current_labels)
    if labels is not None and len(labels) != len(current_predictions):
        raise ValueError("Current labels and current feature rows must have equal length")

    base_url = args.api_url.rstrip("/")
    login = _post(
        f"{base_url}/api/v1/auth/login",
        {"email": args.email, "password": args.password},
    )
    report = _post(
        f"{base_url}/api/analyze",
        {
            "reference": _records(reference),
            "current": _records(current),
            "predictions": current_predictions,
            "labels": labels,
            "model_name": args.model_name,
        },
        token=login["access_token"],
    )
    summary = report.get("summary", {})
    print(json.dumps({
        "status": "submitted",
        "model": args.model_name,
        "severity": summary.get("severity"),
        "decision": summary.get("decision"),
        "drift_rate": summary.get("drift_rate"),
        "quality_score": summary.get("quality_score"),
        "dashboard": base_url,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
