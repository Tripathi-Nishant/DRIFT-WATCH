"""Bounded local worker queue; replace with Redis/SQS/Kafka in a cluster."""

from __future__ import annotations

from dataclasses import dataclass
from queue import Full, Queue
from threading import Event, Thread
from typing import Any, Callable


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
