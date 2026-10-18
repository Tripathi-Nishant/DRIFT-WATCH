"""Create a consistent PostgreSQL backup using pg_dump.

Usage: python tools/backup_postgres.py --output backups/driftwatch.dump
The connection URL is read from DRIFTWATCH_DATABASE_URL and is never printed.
"""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Back up DriftWatch PostgreSQL")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    url = os.environ.get("DRIFTWATCH_DATABASE_URL")
    if not url or not url.startswith(("postgresql://", "postgres://")):
        raise SystemExit("DRIFTWATCH_DATABASE_URL must be a PostgreSQL URL")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["pg_dump", "--format=custom", "--file", str(args.output), url],
        check=False,
    )
    if result.returncode:
        raise SystemExit(result.returncode)
    print(f"Backup written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
