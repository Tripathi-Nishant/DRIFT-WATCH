"""Advisory retraining workflow. It never trains or deploys automatically."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def create_request(report: dict[str, Any], output: str | Path) -> dict[str, Any]:
    summary = report["summary"]
    request = {
        "id": str(uuid.uuid4()),
        "status": "PENDING_APPROVAL",
        "created_at": datetime.now(UTC).isoformat(),
        "model": summary.get("model", "model"),
        "severity": summary.get("severity"),
        "decision": summary.get("decision"),
        "recommendation": summary.get("recommendation"),
        "approval_required": True,
        "deployment": "never automatic",
    }
    Path(output).write_text(json.dumps(request, indent=2), encoding="utf-8")
    return request


def approve_request(path: str | Path, approver: str) -> dict[str, Any]:
    request = json.loads(Path(path).read_text(encoding="utf-8"))
    if request.get("status") != "PENDING_APPROVAL":
        raise ValueError("Only pending retraining requests can be approved")
    request.update(
        {
            "status": "APPROVED",
            "approved_by": approver,
            "approved_at": datetime.now(UTC).isoformat(),
        }
    )
    Path(path).write_text(json.dumps(request, indent=2), encoding="utf-8")
    return request
