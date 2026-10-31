"""Optional PostgreSQL backend using psycopg 3.

Install with ``pip install driftwatch[server]`` and set
``DRIFTWATCH_DATABASE_URL=postgresql://...``.
"""

from __future__ import annotations

import os
from typing import Any

from .storage import Store


class PostgresStore(Store):
    """Store-compatible backend for PostgreSQL deployments."""

    def __init__(self, url: str | None = None) -> None:
        try:
            import psycopg
            from psycopg.rows import dict_row
            from psycopg_pool import ConnectionPool
        except ImportError as error:
            raise RuntimeError(
                "PostgreSQL support requires: pip install driftwatch[server]"
            ) from error
        self._psycopg = psycopg
        self._dict_row = dict_row
        self.url = url or os.getenv("DRIFTWATCH_DATABASE_URL")
        if not self.url or not self.url.startswith(("postgresql://", "postgres://")):
            raise ValueError(
                "DRIFTWATCH_DATABASE_URL must be a PostgreSQL connection URL"
            )
        self._pool = ConnectionPool(
            self.url,
            min_size=max(1, int(os.getenv("DRIFTWATCH_DB_POOL_MIN", "2"))),
            max_size=max(2, int(os.getenv("DRIFTWATCH_DB_POOL_MAX", "10"))),
            kwargs={"row_factory": dict_row},
            open=True,
        )
        super().__init__(path=":postgres:")

    def _connect(self):
        return _PostgresConnection(self._pool.connection())

    def _init(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS organizations (id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS memberships (user_id TEXT NOT NULL, organization_id TEXT NOT NULL, role TEXT NOT NULL, PRIMARY KEY(user_id, organization_id));
                CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, organization_id TEXT NOT NULL, name TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS api_keys (id TEXT PRIMARY KEY, organization_id TEXT NOT NULL, name TEXT NOT NULL, key_hash TEXT UNIQUE NOT NULL, created_at TEXT NOT NULL, revoked_at TEXT);
                CREATE TABLE IF NOT EXISTS audit_events (id TEXT PRIMARY KEY, organization_id TEXT, user_id TEXT, action TEXT NOT NULL, entity_type TEXT, entity_id TEXT, detail TEXT, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS models (id TEXT PRIMARY KEY, organization_id TEXT, name TEXT NOT NULL, version TEXT NOT NULL, model_type TEXT NOT NULL, created_at TEXT NOT NULL, reference_profile JSONB);
                CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, organization_id TEXT, model_id TEXT, severity TEXT NOT NULL, decision TEXT NOT NULL, created_at TEXT NOT NULL, report JSONB NOT NULL);
                CREATE TABLE IF NOT EXISTS predictions (id TEXT PRIMARY KEY, model_id TEXT, prediction TEXT NOT NULL, features JSONB NOT NULL, created_at TEXT NOT NULL, label TEXT);
                CREATE TABLE IF NOT EXISTS feedback (id TEXT PRIMARY KEY, prediction_id TEXT NOT NULL, label TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS alerts (id TEXT PRIMARY KEY, run_id TEXT NOT NULL, channel TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL, detail TEXT);
                CREATE TABLE IF NOT EXISTS retraining_requests (id TEXT PRIMARY KEY, organization_id TEXT, model_id TEXT, status TEXT NOT NULL, requested_by TEXT, approved_by TEXT, report JSONB NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS dataset_versions (id TEXT PRIMARY KEY, organization_id TEXT NOT NULL, model_id TEXT, name TEXT NOT NULL, version TEXT NOT NULL, kind TEXT NOT NULL, rows INTEGER NOT NULL, columns INTEGER NOT NULL, fingerprint TEXT NOT NULL, metadata JSONB NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS schedules (id TEXT PRIMARY KEY, organization_id TEXT NOT NULL, model_id TEXT, name TEXT NOT NULL, cadence TEXT NOT NULL, enabled INTEGER NOT NULL, next_run_at TEXT, last_run_at TEXT, config JSONB NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS schedule_runs (id TEXT PRIMARY KEY, schedule_id TEXT NOT NULL, organization_id TEXT NOT NULL, status TEXT NOT NULL, severity TEXT, started_at TEXT NOT NULL, completed_at TEXT, detail TEXT, output_path TEXT);
                CREATE TABLE IF NOT EXISTS alert_rules (id TEXT PRIMARY KEY, organization_id TEXT NOT NULL, name TEXT NOT NULL, enabled INTEGER NOT NULL, severity TEXT NOT NULL, channel TEXT NOT NULL, destination TEXT, threshold REAL, metric TEXT NOT NULL DEFAULT 'drift_rate', created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS research_runs (id TEXT PRIMARY KEY, organization_id TEXT NOT NULL, suite TEXT NOT NULL, seeds JSONB NOT NULL, result JSONB NOT NULL, created_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS idx_runs_org_created ON runs(organization_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_models_org_created ON models(organization_id, created_at DESC);
                ALTER TABLE alert_rules ADD COLUMN IF NOT EXISTS metric TEXT NOT NULL DEFAULT 'drift_rate';
                """
            )

    def compare_models(self, organization_id: str) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                """SELECT model_id, COUNT(*) AS runs,
                   AVG((report->'summary'->>'drift_rate')::double precision) AS avg_drift,
                   AVG((report->'summary'->>'quality_score')::double precision) AS avg_quality,
                   MAX(created_at) AS last_run
                   FROM runs WHERE organization_id = ? AND model_id IS NOT NULL
                   GROUP BY model_id ORDER BY avg_quality DESC""",
                (organization_id,),
            )
            return [dict(row) for row in rows]

    def record_research_run(
        self, organization_id: str, suite: str, seeds: list[int], result: dict[str, Any]
    ) -> dict[str, Any]:
        import uuid
        from datetime import UTC, datetime

        item = {
            "id": str(uuid.uuid4()),
            "organization_id": organization_id,
            "suite": suite,
            "seeds": seeds,
            "result": result,
            "created_at": datetime.now(UTC).isoformat(),
        }
        with self._connect() as db:
            db.execute(
                "INSERT INTO research_runs VALUES (?, ?, ?, ?, ?, ?)",
                (item["id"], organization_id, suite, seeds, result, item["created_at"]),
            )
        return item

    def list_research_runs(self, organization_id: str) -> list[dict[str, Any]]:
        with self._connect() as db:
            return [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM research_runs WHERE organization_id = ? ORDER BY created_at DESC LIMIT 50",
                    (organization_id,),
                )
            ]


class _PostgresConnection:
    def __init__(self, pooled_connection: Any) -> None:
        self.pooled_connection = pooled_connection
        self.connection = None

    def __enter__(self):
        self.connection = self.pooled_connection.__enter__()
        return self

    def __exit__(self, *args):
        return self.pooled_connection.__exit__(*args)

    def execute(self, query: str, params: tuple[Any, ...] = ()):
        return self.connection.execute(query.replace("?", "%s"), params)

    def executescript(self, script: str) -> None:
        for statement in script.split(";"):
            if statement.strip():
                self.connection.execute(statement)
