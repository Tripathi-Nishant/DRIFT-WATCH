"""Small SQLite store for local-first monitoring history and ingestion."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(UTC).isoformat()


class Store:
    """Thread-safe persistence for a single self-hosted DriftWatch workspace."""

    def __init__(self, path: str | Path | None = None) -> None:
        default = Path(os.getenv("DRIFTWATCH_DB", ".driftwatch/driftwatch.db"))
        self.path = Path(path or default)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        return connection

    def _init(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS models (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, version TEXT NOT NULL,
                    model_type TEXT NOT NULL, created_at TEXT NOT NULL,
                    reference_profile TEXT
                );
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY, model_id TEXT, severity TEXT NOT NULL,
                    decision TEXT NOT NULL, created_at TEXT NOT NULL,
                    report TEXT NOT NULL,
                    FOREIGN KEY(model_id) REFERENCES models(id)
                );
                CREATE TABLE IF NOT EXISTS predictions (
                    id TEXT PRIMARY KEY, model_id TEXT, prediction TEXT NOT NULL,
                    features TEXT NOT NULL, created_at TEXT NOT NULL, label TEXT,
                    FOREIGN KEY(model_id) REFERENCES models(id)
                );
                CREATE TABLE IF NOT EXISTS feedback (
                    id TEXT PRIMARY KEY, prediction_id TEXT NOT NULL,
                    label TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(prediction_id) REFERENCES predictions(id)
                );
                CREATE TABLE IF NOT EXISTS alerts (
                    id TEXT PRIMARY KEY, run_id TEXT NOT NULL, channel TEXT NOT NULL,
                    status TEXT NOT NULL, created_at TEXT NOT NULL, detail TEXT,
                    FOREIGN KEY(run_id) REFERENCES runs(id)
                );
                CREATE TABLE IF NOT EXISTS organizations (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS memberships (
                    user_id TEXT NOT NULL, organization_id TEXT NOT NULL, role TEXT NOT NULL,
                    PRIMARY KEY(user_id, organization_id)
                );
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY, organization_id TEXT NOT NULL, name TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS api_keys (
                    id TEXT PRIMARY KEY, organization_id TEXT NOT NULL, name TEXT NOT NULL,
                    key_hash TEXT UNIQUE NOT NULL, created_at TEXT NOT NULL, revoked_at TEXT
                );
                CREATE TABLE IF NOT EXISTS audit_events (
                    id TEXT PRIMARY KEY, organization_id TEXT, user_id TEXT, action TEXT NOT NULL,
                    entity_type TEXT, entity_id TEXT, detail TEXT, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS retraining_requests (
                    id TEXT PRIMARY KEY, organization_id TEXT, model_id TEXT, status TEXT NOT NULL,
                    requested_by TEXT, approved_by TEXT, report TEXT NOT NULL, created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )

    def create_organization(self, name: str) -> dict[str, Any]:
        organization = {"id": str(uuid.uuid4()), "name": name, "created_at": _now()}
        with self._lock, self._connect() as db:
            db.execute(
                "INSERT INTO organizations VALUES (?, ?, ?)",
                tuple(organization.values()),
            )
        return organization

    def create_user(
        self, email: str, password_hash: str, organization_id: str, role: str = "OWNER"
    ) -> dict[str, Any]:
        user = {"id": str(uuid.uuid4()), "email": email.lower(), "created_at": _now()}
        with self._lock, self._connect() as db:
            db.execute(
                "INSERT INTO users VALUES (?, ?, ?, ?)",
                (user["id"], user["email"], password_hash, user["created_at"]),
            )
            db.execute(
                "INSERT INTO memberships VALUES (?, ?, ?)",
                (user["id"], organization_id, role),
            )
        return user | {"organization_id": organization_id, "role": role}

    def find_user(self, email: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT u.*, m.organization_id, m.role FROM users u JOIN memberships m ON m.user_id = u.id WHERE u.email = ? LIMIT 1",
                (email.lower(),),
            ).fetchone()
            return dict(row) if row else None

    def create_project(self, organization_id: str, name: str) -> dict[str, Any]:
        project = {
            "id": str(uuid.uuid4()),
            "organization_id": organization_id,
            "name": name,
            "created_at": _now(),
        }
        with self._lock, self._connect() as db:
            db.execute(
                "INSERT INTO projects VALUES (?, ?, ?, ?)", tuple(project.values())
            )
        return project

    def list_projects(self, organization_id: str) -> list[dict[str, Any]]:
        with self._connect() as db:
            return [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM projects WHERE organization_id = ? ORDER BY created_at DESC",
                    (organization_id,),
                )
            ]

    def save_api_key(
        self, organization_id: str, name: str, key_hash: str
    ) -> dict[str, Any]:
        item = {
            "id": str(uuid.uuid4()),
            "organization_id": organization_id,
            "name": name,
            "key_hash": key_hash,
            "created_at": _now(),
        }
        with self._lock, self._connect() as db:
            db.execute(
                "INSERT INTO api_keys VALUES (?, ?, ?, ?, ?, NULL)",
                tuple(item.values()),
            )
        return {key: value for key, value in item.items() if key != "key_hash"}

    def audit(
        self,
        action: str,
        organization_id: str | None = None,
        user_id: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        event = {
            "id": str(uuid.uuid4()),
            "organization_id": organization_id,
            "user_id": user_id,
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "detail": json.dumps(detail or {}),
            "created_at": _now(),
        }
        with self._lock, self._connect() as db:
            db.execute(
                "INSERT INTO audit_events VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                tuple(event.values()),
            )
        return event

    def list_audit(
        self, organization_id: str, limit: int = 100
    ) -> list[dict[str, Any]]:
        with self._connect() as db:
            return [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM audit_events WHERE organization_id = ? ORDER BY created_at DESC LIMIT ?",
                    (organization_id, min(limit, 200)),
                )
            ]

    def create_model(
        self,
        name: str,
        version: str = "1.0.0",
        model_type: str = "classification",
        reference_profile: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        model = {
            "id": str(uuid.uuid4()),
            "name": name,
            "version": version,
            "model_type": model_type,
            "created_at": _now(),
        }
        with self._lock, self._connect() as db:
            db.execute(
                "INSERT INTO models VALUES (?, ?, ?, ?, ?, ?)",
                (
                    *model.values(),
                    json.dumps(reference_profile) if reference_profile else None,
                ),
            )
        return model

    def list_models(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            return [
                dict(row)
                for row in db.execute(
                    "SELECT id, name, version, model_type, created_at FROM models "
                    "ORDER BY created_at DESC"
                )
            ]

    def record_run(
        self, report: dict[str, Any], model_id: str | None = None
    ) -> dict[str, Any]:
        run = {
            "id": str(uuid.uuid4()),
            "model_id": model_id,
            "severity": report["summary"]["severity"],
            "decision": report["summary"]["decision"],
            "created_at": _now(),
            "report": report,
        }
        with self._lock, self._connect() as db:
            db.execute(
                "INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?)",
                (
                    run["id"],
                    model_id,
                    run["severity"],
                    run["decision"],
                    run["created_at"],
                    json.dumps(report),
                ),
            )
        return {key: value for key, value in run.items() if key != "report"} | {
            "report": report
        }

    def list_runs(self, limit: int = 30) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT id, model_id, severity, decision, created_at, report FROM runs "
                "ORDER BY created_at DESC LIMIT ?",
                (max(1, min(limit, 100)),),
            )
            return [{**dict(row), "report": json.loads(row["report"])} for row in rows]

    def add_predictions(
        self, model_id: str | None, rows: list[dict[str, Any]]
    ) -> list[str]:
        ids = []
        with self._lock, self._connect() as db:
            for row in rows:
                prediction_id = str(row.get("id") or uuid.uuid4())
                ids.append(prediction_id)
                db.execute(
                    "INSERT OR REPLACE INTO predictions VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        prediction_id,
                        model_id,
                        json.dumps(row.get("prediction")),
                        json.dumps(row.get("features", {})),
                        row.get("created_at", _now()),
                        json.dumps(row["label"]) if "label" in row else None,
                    ),
                )
        return ids

    def add_feedback(self, prediction_id: str, label: Any) -> bool:
        with self._lock, self._connect() as db:
            exists = db.execute(
                "SELECT 1 FROM predictions WHERE id = ?", (prediction_id,)
            ).fetchone()
            if not exists:
                return False
            db.execute(
                "INSERT INTO feedback VALUES (?, ?, ?, ?)",
                (str(uuid.uuid4()), prediction_id, json.dumps(label), _now()),
            )
            db.execute(
                "UPDATE predictions SET label = ? WHERE id = ?",
                (json.dumps(label), prediction_id),
            )
            return True

    def create_retraining_request(
        self,
        organization_id: str,
        model_id: str | None,
        requested_by: str,
        report: dict[str, Any],
    ) -> dict[str, Any]:
        request = {
            "id": str(uuid.uuid4()),
            "organization_id": organization_id,
            "model_id": model_id,
            "status": "PENDING_APPROVAL",
            "requested_by": requested_by,
            "approved_by": None,
            "report": json.dumps(report),
            "created_at": _now(),
            "updated_at": _now(),
        }
        with self._lock, self._connect() as db:
            db.execute(
                "INSERT INTO retraining_requests VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                tuple(request.values()),
            )
        request["report"] = report
        return request

    def list_retraining_requests(self, organization_id: str) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM retraining_requests WHERE organization_id = ? ORDER BY created_at DESC",
                (organization_id,),
            )
            return [{**dict(row), "report": json.loads(row["report"])} for row in rows]

    def approve_retraining_request(
        self, organization_id: str, request_id: str, approver: str
    ) -> dict[str, Any] | None:
        with self._lock, self._connect() as db:
            row = db.execute(
                "SELECT * FROM retraining_requests WHERE id = ? AND organization_id = ?",
                (request_id, organization_id),
            ).fetchone()
            if not row or row["status"] != "PENDING_APPROVAL":
                return None
            updated = _now()
            db.execute(
                "UPDATE retraining_requests SET status = ?, approved_by = ?, updated_at = ? WHERE id = ?",
                ("APPROVED", approver, updated, request_id),
            )
            return {
                **dict(row),
                "status": "APPROVED",
                "approved_by": approver,
                "updated_at": updated,
                "report": json.loads(row["report"]),
            }

    def record_alert(
        self, run_id: str, channel: str, status: str, detail: str
    ) -> dict[str, Any]:
        alert = {
            "id": str(uuid.uuid4()),
            "run_id": run_id,
            "channel": channel,
            "status": status,
            "created_at": _now(),
            "detail": detail,
        }
        with self._lock, self._connect() as db:
            db.execute(
                "INSERT INTO alerts VALUES (?, ?, ?, ?, ?, ?)", tuple(alert.values())
            )
        return alert

    def list_alerts(self, limit: int = 30) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT id, run_id, channel, status, created_at, detail "
                "FROM alerts ORDER BY created_at DESC LIMIT ?",
                (max(1, min(limit, 100)),),
            )
            return [dict(row) for row in rows]
