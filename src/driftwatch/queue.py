"""Bounded local worker queue; replace with Redis/SQS/Kafka in a cluster."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from queue import Full, Queue
from threading import Event, Thread
from typing import Any


@dataclass
class Job:
    kind: str
    payload: dict[str, Any]


class IngestionQueue:
    def __init__(self, handler: Callable[[Job], None], maxsize: int = 10000) -> None:
        self._queue: Queue[Job] = Queue(maxsize=maxsize)
        self._stop = Event()
        self._handler = handler
        self._worker = Thread(
            target=self._run, name="driftwatch-ingestion", daemon=True
        )
        self._worker.start()

    def submit(self, kind: str, payload: dict[str, Any]) -> bool:
        try:
            self._queue.put_nowait(Job(kind, payload))
            return True
        except Full:
            return False

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                job = self._queue.get(timeout=0.2)
            except Exception:
                continue
            try:
                self._handler(job)
            finally:
                self._queue.task_done()

    def close(self) -> None:
        self._stop.set()
        self._worker.join(timeout=2)


class RedisIngestionQueue:
    """Redis-backed queue for multi-process deployments.

    Install ``driftwatch[distributed]`` and run a separate worker process that
    calls ``work``. Payloads are JSON and are removed only after the handler
    succeeds; operational deployments should also configure Redis persistence.
    """

    def __init__(self, name: str = "driftwatch:ingestion", url: str | None = None):
        try:
            import redis
        except ImportError as error:
            raise RuntimeError(
                "Redis support requires: pip install driftwatch[distributed]"
            ) from error
        self._redis = redis.Redis.from_url(url or os.getenv("DRIFTWATCH_REDIS_URL", "redis://localhost:6379/0"), decode_responses=True)
        self.name = name

    def submit(self, kind: str, payload: dict[str, Any]) -> bool:
        self._redis.rpush(self.name, json.dumps({"kind": kind, "payload": payload}))
        return True

    def work(self, handler: Callable[[Job], None], timeout: int = 5) -> None:
        while True:
            item = self._redis.blpop(self.name, timeout=timeout)
            if not item:
                continue
            _, encoded = item
            job = json.loads(encoded)
            handler(Job(job["kind"], job["payload"]))
