"""Run placement monitoring repeatedly on a small laptop or college server."""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser(description="Schedule placement monitoring")
    parser.add_argument("--interval", type=int, default=3600, help="seconds between runs")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--api-url", default="http://127.0.0.1:8765")
    args = parser.parse_args()
    command = [
        sys.executable,
        str(ROOT / "driftwatch_monitor.py"),
        "--email",
        args.email,
        "--password",
        args.password,
        "--api-url",
        args.api_url,
    ]
    while True:
        subprocess.run(command, check=False)
        print(f"Next placement monitoring run in {args.interval} seconds", flush=True)
        time.sleep(max(60, args.interval))


if __name__ == "__main__":
    raise SystemExit(main())
