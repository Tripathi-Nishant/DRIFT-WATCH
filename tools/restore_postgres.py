"""Restore a DriftWatch PostgreSQL custom-format backup with pg_restore."""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Restore DriftWatch PostgreSQL")
    parser.add_argument("backup", type=Path)
    parser.add_argument("--clean", action="store_true")
    args = parser.parse_args()
    url = os.environ.get("DRIFTWATCH_DATABASE_URL")
    if not url or not url.startswith(("postgresql://", "postgres://")):
        raise SystemExit("DRIFTWATCH_DATABASE_URL must be a PostgreSQL URL")
    if not args.backup.is_file():
        raise SystemExit(f"Backup does not exist: {args.backup}")
    command = ["pg_restore", "--if-exists", "--no-owner"]
    if args.clean:
        command.append("--clean")
    command += ["--dbname", url, str(args.backup)]
    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
