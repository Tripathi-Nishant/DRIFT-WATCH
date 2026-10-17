"""Apply ordered PostgreSQL SQL migrations with a durable schema table."""

from __future__ import annotations

import os
from pathlib import Path


def main() -> None:
    import psycopg

    url = os.environ["DRIFTWATCH_DATABASE_URL"]
    migration_dir = Path(__file__).parents[1] / "migrations"
    with psycopg.connect(url) as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS driftwatch_schema_migrations (version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
        )
        applied = {
            row[0]
            for row in connection.execute(
                "SELECT version FROM driftwatch_schema_migrations"
            )
        }
        for path in sorted(migration_dir.glob("*.sql")):
            if path.name in applied:
                continue
            with connection.transaction():
                for statement in path.read_text(encoding="utf-8").split(";"):
                    if statement.strip():
                        connection.execute(statement)
                connection.execute(
                    "INSERT INTO driftwatch_schema_migrations(version) VALUES (%s)",
                    (path.name,),
                )
            print(f"applied {path.name}")


if __name__ == "__main__":
    main()
