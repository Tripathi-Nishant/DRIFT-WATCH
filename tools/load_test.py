"""Small dependency-free smoke/load test for a running DriftWatch API.

Usage: python tools/load_test.py --url http://127.0.0.1:8765/healthz --requests 200 --workers 8
"""

from __future__ import annotations

import argparse
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request, urlopen


def request(url: str) -> tuple[bool, float, int]:
    started = time.perf_counter()
    try:
        with urlopen(Request(url, method="GET"), timeout=10) as response:
            response.read()
            return True, time.perf_counter() - started, response.status
    except Exception:
        return False, time.perf_counter() - started, 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8765/healthz")
    parser.add_argument("--requests", type=int, default=200)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(lambda _: request(args.url), range(args.requests)))
    elapsed = time.perf_counter() - started
    durations = [duration for ok, duration, _ in results if ok]
    successes = sum(ok for ok, _, _ in results)
    print(
        {
            "requests": args.requests,
            "successes": successes,
            "errors": args.requests - successes,
            "seconds": round(elapsed, 3),
            "requests_per_second": round(args.requests / max(elapsed, 1e-9), 2),
            "p50_ms": round(statistics.median(durations) * 1000, 2)
            if durations
            else None,
            "p95_ms": round(
                sorted(durations)[max(0, int(len(durations) * 0.95) - 1)] * 1000, 2
            )
            if durations
            else None,
        }
    )
    raise SystemExit(0 if successes == args.requests else 1)


if __name__ == "__main__":
    main()
