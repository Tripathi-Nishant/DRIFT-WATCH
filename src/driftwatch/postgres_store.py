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
                CREATE INDEX IF NOT EXISTS idx_runs_org_created ON runs(organization_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_models_org_created ON models(organization_id, created_at DESC);
                """
            )


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
