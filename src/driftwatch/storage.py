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


def _decode_json(value: Any) -> Any:
    """Decode SQLite JSON strings while preserving PostgreSQL JSONB values."""
    return json.loads(value) if isinstance(value, (str, bytes, bytearray)) else value


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
                    id TEXT PRIMARY KEY, organization_id TEXT, name TEXT NOT NULL, version TEXT NOT NULL,
                    model_type TEXT NOT NULL, environment TEXT NOT NULL DEFAULT 'production',
                    lifecycle_status TEXT NOT NULL DEFAULT 'candidate', created_at TEXT NOT NULL,
                    reference_profile TEXT
                );
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY, organization_id TEXT, model_id TEXT, severity TEXT NOT NULL,
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
                CREATE TABLE IF NOT EXISTS dataset_versions (
                    id TEXT PRIMARY KEY, organization_id TEXT NOT NULL, model_id TEXT,
                    name TEXT NOT NULL, version TEXT NOT NULL, kind TEXT NOT NULL,
                    rows INTEGER NOT NULL, columns INTEGER NOT NULL, fingerprint TEXT NOT NULL,
                    metadata TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS schedules (
                    id TEXT PRIMARY KEY, organization_id TEXT NOT NULL, model_id TEXT,
                    name TEXT NOT NULL, cadence TEXT NOT NULL, enabled INTEGER NOT NULL,
                    next_run_at TEXT, last_run_at TEXT, config TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS schedule_runs (
                    id TEXT PRIMARY KEY, schedule_id TEXT NOT NULL, organization_id TEXT NOT NULL,
                    status TEXT NOT NULL, severity TEXT, started_at TEXT NOT NULL,
                    completed_at TEXT, detail TEXT, output_path TEXT
                );
                CREATE TABLE IF NOT EXISTS alert_rules (
                    id TEXT PRIMARY KEY, organization_id TEXT NOT NULL, name TEXT NOT NULL,
                    enabled INTEGER NOT NULL, severity TEXT NOT NULL, channel TEXT NOT NULL,
                    destination TEXT, threshold REAL, metric TEXT NOT NULL DEFAULT 'drift_rate',
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS research_runs (
                    id TEXT PRIMARY KEY, organization_id TEXT NOT NULL, suite TEXT NOT NULL,
                    seeds TEXT NOT NULL, result TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS incidents (
                    id TEXT PRIMARY KEY, organization_id TEXT NOT NULL, run_id TEXT,
                    model_id TEXT, title TEXT NOT NULL, severity TEXT NOT NULL,
                    status TEXT NOT NULL, owner TEXT, detail TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS access_requests (
                    id TEXT PRIMARY KEY, email TEXT NOT NULL, organization TEXT NOT NULL,
                    use_case TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL,
                    reviewed_at TEXT, reviewer TEXT
                );
                """
            )
            for table, column in (("models", "organization_id"), ("runs", "organization_id")):
                try:
                    db.execute(f"ALTER TABLE {table} ADD COLUMN {column} TEXT")
                except sqlite3.OperationalError:
                    pass
            try:
                db.execute(
                    "ALTER TABLE alert_rules ADD COLUMN metric TEXT NOT NULL DEFAULT 'drift_rate'"
                )
            except sqlite3.OperationalError:
                pass
            for column, definition in (
                ("environment", "TEXT NOT NULL DEFAULT 'production'"),
                ("lifecycle_status", "TEXT NOT NULL DEFAULT 'candidate'"),
            ):
                try:
                    db.execute(f"ALTER TABLE models ADD COLUMN {column} {definition}")
                except sqlite3.OperationalError:
                    pass

    def create_organization(self, name: str) -> dict[str, Any]:
        organization = {"id": str(uuid.uuid4()), "name": name, "created_at": _now()}
        with self._lock, self._connect() as db:
            db.execute(
                "INSERT INTO organizations VALUES (?, ?, ?)",
                tuple(organization.values()),
            )
        return organization

    def create_access_request(
        self, email: str, organization: str, use_case: str
    ) -> dict[str, Any]:
        normalized_email = email.strip().lower()
        item = {
            "id": str(uuid.uuid4()), "email": normalized_email,
            "organization": organization.strip(), "use_case": use_case.strip(),
            "status": "PENDING", "created_at": _now(),
            "reviewed_at": None, "reviewer": None,
        }
        with self._lock, self._connect() as db:
            existing = db.execute(
                "SELECT * FROM access_requests WHERE email = ? AND status = 'PENDING' "
                "ORDER BY created_at DESC LIMIT 1",
                (normalized_email,),
            ).fetchone()
            if existing:
                return dict(existing)
            db.execute("INSERT INTO access_requests VALUES (?, ?, ?, ?, ?, ?, ?, ?)", tuple(item.values()))
        return item

    def list_access_requests(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            return [dict(row) for row in db.execute(
                "SELECT * FROM access_requests ORDER BY created_at DESC"
            )]

    def review_access_request(
        self, request_id: str, status: str, reviewer: str
    ) -> dict[str, Any] | None:
        if status not in {"APPROVED", "REJECTED"}:
            raise ValueError("status must be APPROVED or REJECTED")
        with self._lock, self._connect() as db:
            db.execute(
                "UPDATE access_requests SET status = ?, reviewed_at = ?, reviewer = ? "
                "WHERE id = ? AND status = 'PENDING'",
                (status, _now(), reviewer, request_id),
            )
            row = db.execute(
                "SELECT * FROM access_requests WHERE id = ?", (request_id,)
            ).fetchone()
            return dict(row) if row else None

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

    def create_dataset_version(
        self, organization_id: str, name: str, version: str, kind: str,
        rows: int, columns: int, fingerprint: str, model_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        item = {
            "id": str(uuid.uuid4()), "organization_id": organization_id,
            "model_id": model_id, "name": name, "version": version, "kind": kind,
            "rows": int(rows), "columns": int(columns), "fingerprint": fingerprint,
            "metadata": json.dumps(metadata or {}), "created_at": _now(),
        }
        with self._lock, self._connect() as db:
            db.execute(
                "INSERT INTO dataset_versions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                tuple(item.values()),
            )
        item["metadata"] = metadata or {}
        return item

    def list_dataset_versions(self, organization_id: str) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM dataset_versions WHERE organization_id = ? ORDER BY created_at DESC",
                (organization_id,),
            )
            return [{**dict(row), "metadata": _decode_json(row["metadata"])} for row in rows]

    def create_schedule(
        self, organization_id: str, name: str, cadence: str,
        model_id: str | None = None, config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        item = {
            "id": str(uuid.uuid4()), "organization_id": organization_id,
            "model_id": model_id, "name": name, "cadence": cadence, "enabled": 1,
            "next_run_at": None, "last_run_at": None,
            "config": json.dumps(config or {}), "created_at": _now(),
        }
        with self._lock, self._connect() as db:
            db.execute("INSERT INTO schedules VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", tuple(item.values()))
        item["config"] = config or {}
        item["enabled"] = True
        return item

    def list_schedules(self, organization_id: str) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM schedules WHERE organization_id = ? ORDER BY created_at DESC", (organization_id,))
            return [{**dict(row), "enabled": bool(row["enabled"]), "config": _decode_json(row["config"])} for row in rows]

    def record_schedule_run(
        self, schedule: dict[str, Any], status: str, started_at: str,
        completed_at: str | None = None, severity: str | None = None,
        detail: str | None = None, output_path: str | None = None,
    ) -> dict[str, Any]:
        item = {
            "id": str(uuid.uuid4()), "schedule_id": schedule["id"],
            "organization_id": schedule["organization_id"], "status": status,
            "severity": severity, "started_at": started_at,
            "completed_at": completed_at, "detail": detail,
            "output_path": output_path,
        }
        with self._lock, self._connect() as db:
            db.execute("INSERT INTO schedule_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", tuple(item.values()))
        return item

    def list_schedule_runs(
        self, organization_id: str, schedule_id: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        where = "organization_id = ?"
        params: list[Any] = [organization_id]
        if schedule_id:
            where += " AND schedule_id = ?"
            params.append(schedule_id)
        params.append(max(1, min(limit, 200)))
        with self._connect() as db:
            rows = db.execute(
                f"SELECT * FROM schedule_runs WHERE {where} ORDER BY started_at DESC LIMIT ?",
                tuple(params),
            )
            return [dict(row) for row in rows]

    def create_alert_rule(
        self, organization_id: str, name: str, severity: str, channel: str,
        destination: str | None = None, threshold: float | None = None,
        metric: str = "drift_rate",
    ) -> dict[str, Any]:
        item = {
            "id": str(uuid.uuid4()), "organization_id": organization_id, "name": name,
            "enabled": 1, "severity": severity, "channel": channel,
            "destination": destination, "threshold": threshold, "metric": metric,
            "created_at": _now(),
        }
        with self._lock, self._connect() as db:
            db.execute(            "INSERT INTO alert_rules VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            tuple(item.values()),
            )
        item["enabled"] = True
        return item

    def list_alert_rules(self, organization_id: str) -> list[dict[str, Any]]:
        with self._connect() as db:
            return [
                {**dict(row), "enabled": bool(row["enabled"])}
                for row in db.execute("SELECT * FROM alert_rules WHERE organization_id = ? ORDER BY created_at DESC", (organization_id,))
            ]

    def compare_models(self, organization_id: str) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                """SELECT model_id, COUNT(*) AS runs,
                   AVG(CAST(json_extract(report, '$.summary.drift_rate') AS REAL)) AS avg_drift,
                   AVG(CAST(json_extract(report, '$.summary.quality_score') AS REAL)) AS avg_quality,
                   MAX(created_at) AS last_run
                   FROM runs WHERE organization_id = ? AND model_id IS NOT NULL
                   GROUP BY model_id ORDER BY avg_quality DESC""",
                (organization_id,),
            )
            return [dict(row) for row in rows]

    def record_research_run(
        self, organization_id: str, suite: str, seeds: list[int], result: dict[str, Any]
    ) -> dict[str, Any]:
        item = {
            "id": str(uuid.uuid4()),
            "organization_id": organization_id,
            "suite": suite,
            "seeds": json.dumps(seeds),
            "result": json.dumps(result),
            "created_at": _now(),
        }
        with self._lock, self._connect() as db:
            db.execute("INSERT INTO research_runs VALUES (?, ?, ?, ?, ?, ?)", tuple(item.values()))
        return {**item, "seeds": seeds, "result": result}

    def list_research_runs(self, organization_id: str) -> list[dict[str, Any]]:
        with self._connect() as db:
            return [
                {**dict(row), "seeds": _decode_json(row["seeds"]), "result": _decode_json(row["result"])}
                for row in db.execute(
                    "SELECT * FROM research_runs WHERE organization_id = ? ORDER BY created_at DESC LIMIT 50",
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

    def list_api_keys(self, organization_id: str) -> list[dict[str, Any]]:
        with self._connect() as db:
            return [
                dict(row)
                for row in db.execute(
                    "SELECT id, name, created_at, revoked_at FROM api_keys "
                    "WHERE organization_id = ? ORDER BY created_at DESC",
                    (organization_id,),
                )
            ]

    def revoke_api_key(self, organization_id: str, key_id: str) -> dict[str, Any] | None:
        with self._lock, self._connect() as db:
            active = db.execute(
                "SELECT id FROM api_keys WHERE id = ? AND organization_id = ? "
                "AND revoked_at IS NULL",
                (key_id, organization_id),
            ).fetchone()
            if not active:
                return None
            db.execute(
                "UPDATE api_keys SET revoked_at = ? "
                "WHERE id = ? AND organization_id = ? AND revoked_at IS NULL",
                (_now(), key_id, organization_id),
            )
            row = db.execute(
                "SELECT id, name, created_at, revoked_at FROM api_keys "
                "WHERE id = ? AND organization_id = ?",
                (key_id, organization_id),
            ).fetchone()
            return dict(row) if row else None

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
        organization_id: str | None = None,
        environment: str = "production",
        lifecycle_status: str = "candidate",
    ) -> dict[str, Any]:
        model = {
            "id": str(uuid.uuid4()),
            "organization_id": organization_id,
            "name": name,
            "version": version,
            "model_type": model_type,
            "environment": environment,
            "lifecycle_status": lifecycle_status,
            "created_at": _now(),
        }
        with self._lock, self._connect() as db:
            db.execute(
                "INSERT INTO models (id, organization_id, name, version, model_type, environment, lifecycle_status, created_at, reference_profile) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    model["id"], model["organization_id"], model["name"], model["version"],
                    model["model_type"], model["environment"], model["lifecycle_status"],
                    model["created_at"],
                    json.dumps(reference_profile) if reference_profile else None,
                ),
            )
        return model

    def list_models(self, organization_id: str | None = None) -> list[dict[str, Any]]:
        with self._connect() as db:
            where = "WHERE organization_id = ?" if organization_id else ""
            params = (organization_id,) if organization_id else ()
            return [
                dict(row)
                for row in db.execute(
                    f"SELECT id, name, version, model_type, environment, lifecycle_status, created_at FROM models {where} ORDER BY created_at DESC",
                    params,
                )
            ]

    def update_model_lifecycle(
        self, organization_id: str, model_id: str, status: str, environment: str | None = None
    ) -> dict[str, Any] | None:
        allowed = {"candidate", "staging", "production", "deprecated"}
        if status not in allowed:
            raise ValueError(f"status must be one of {sorted(allowed)}")
        with self._lock, self._connect() as db:
            if environment:
                db.execute(
                    "UPDATE models SET lifecycle_status = ?, environment = ? WHERE id = ? AND organization_id = ?",
                    (status, environment, model_id, organization_id),
                )
            else:
                db.execute(
                    "UPDATE models SET lifecycle_status = ? WHERE id = ? AND organization_id = ?",
                    (status, model_id, organization_id),
                )
            row = db.execute(
                "SELECT id, name, version, model_type, environment, lifecycle_status, created_at FROM models WHERE id = ? AND organization_id = ?",
                (model_id, organization_id),
            ).fetchone()
            return dict(row) if row else None

    def record_run(
        self,
        report: dict[str, Any],
        model_id: str | None = None,
        organization_id: str | None = None,
    ) -> dict[str, Any]:
        run = {
            "id": str(uuid.uuid4()),
            "organization_id": organization_id,
            "model_id": model_id,
            "severity": report["summary"]["severity"],
            "decision": report["summary"]["decision"],
            "created_at": _now(),
            "report": report,
        }
        with self._lock, self._connect() as db:
            db.execute(
                "INSERT INTO runs (id, organization_id, model_id, severity, decision, created_at, report) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    run["id"],
                    organization_id,
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

    def list_runs(
        self,
        limit: int = 30,
        organization_id: str | None = None,
        *,
        model_id: str | None = None,
        severity: str | None = None,
        decision: str | None = None,
        created_after: str | None = None,
        created_before: str | None = None,
    ) -> list[dict[str, Any]]:
        with self._connect() as db:
            clauses = []
            params: list[Any] = []
            for column, value in (
                ("organization_id", organization_id),
                ("model_id", model_id),
                ("severity", severity),
                ("decision", decision),
            ):
                if value:
                    clauses.append(f"{column} = ?")
                    params.append(value)
            if created_after:
                clauses.append("created_at >= ?")
                params.append(created_after)
            if created_before:
                clauses.append("created_at <= ?")
                params.append(created_before)
            where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
            params.append(max(1, min(limit, 100)))
            rows = db.execute(
                f"SELECT id, model_id, severity, decision, created_at, report FROM runs {where} ORDER BY created_at DESC LIMIT ?",
                tuple(params),
            )
            return [{**dict(row), "report": _decode_json(row["report"])} for row in rows]

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
            return [{**dict(row), "report": _decode_json(row["report"])} for row in rows]

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
                "report": _decode_json(row["report"]),
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

    def list_alerts(self, limit: int = 30, organization_id: str | None = None) -> list[dict[str, Any]]:
        with self._connect() as db:
            where = "WHERE run_id IN (SELECT id FROM runs WHERE organization_id = ?)" if organization_id else ""
            params = (organization_id, max(1, min(limit, 100))) if organization_id else (max(1, min(limit, 100)),)
            rows = db.execute(
                f"SELECT id, run_id, channel, status, created_at, detail FROM alerts {where} ORDER BY created_at DESC LIMIT ?",
                params,
            )
            return [dict(row) for row in rows]

    def create_incident(
        self, organization_id: str, title: str, severity: str, detail: str,
        run_id: str | None = None, model_id: str | None = None,
        owner: str | None = None,
    ) -> dict[str, Any]:
        item = {
            "id": str(uuid.uuid4()), "organization_id": organization_id,
            "run_id": run_id, "model_id": model_id, "title": title,
            "severity": severity, "status": "OPEN", "owner": owner,
            "detail": detail, "created_at": _now(), "updated_at": _now(),
        }
        with self._lock, self._connect() as db:
            db.execute("INSERT INTO incidents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", tuple(item.values()))
        return item

    def list_incidents(self, organization_id: str, status: str | None = None) -> list[dict[str, Any]]:
        where = "organization_id = ?"
        params: list[Any] = [organization_id]
        if status:
            where += " AND status = ?"
            params.append(status)
        with self._connect() as db:
            return [dict(row) for row in db.execute(
                f"SELECT * FROM incidents WHERE {where} ORDER BY updated_at DESC", tuple(params)
            )]

    def update_incident(
        self, organization_id: str, incident_id: str, status: str, owner: str | None = None
    ) -> dict[str, Any] | None:
        if status not in {"OPEN", "ACKNOWLEDGED", "RESOLVED"}:
            raise ValueError("invalid incident status")
        with self._lock, self._connect() as db:
            db.execute(
                "UPDATE incidents SET status = ?, owner = COALESCE(?, owner), updated_at = ? WHERE id = ? AND organization_id = ?",
                (status, owner, _now(), incident_id, organization_id),
            )
            row = db.execute(
                "SELECT * FROM incidents WHERE id = ? AND organization_id = ?",
                (incident_id, organization_id),
            ).fetchone()
            return dict(row) if row else None
