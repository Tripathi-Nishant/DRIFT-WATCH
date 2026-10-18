"""Optional remote vector-store adapter with explicit tenant boundaries."""

from __future__ import annotations

import json
import os
from typing import Any
from urllib import request as urllib_request


class QdrantVectorStore:
    """Minimal Qdrant REST adapter for production embedding workflows."""

    def __init__(
        self,
        collection: str | None = None,
        url: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float = 10,
    ) -> None:
        self.url = (url or os.getenv("DRIFTWATCH_VECTOR_URL", "")).rstrip("/")
        self.api_key = api_key or os.getenv("DRIFTWATCH_VECTOR_API_KEY")
        self.collection = collection or os.getenv("DRIFTWATCH_VECTOR_COLLECTION", "driftwatch")
        self.timeout_seconds = timeout_seconds
        if not self.url:
            raise ValueError("DRIFTWATCH_VECTOR_URL is required")

    def upsert(
        self,
        points: list[dict[str, Any]],
        organization_id: str,
    ) -> dict[str, Any]:
        if not organization_id:
            raise ValueError("organization_id is required for vector writes")
        payload = []
        for point in points:
            item = dict(point)
            item["payload"] = {
                **dict(item.get("payload") or {}),
                "organization_id": organization_id,
            }
            payload.append(item)
        return self._request(
            "PUT",
            f"/collections/{self.collection}/points?wait=true",
            {"points": payload},
        )

    def search(
        self,
        vector: list[float],
        organization_id: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        if not organization_id:
            raise ValueError("organization_id is required for vector reads")
        result = self._request(
            "POST",
            f"/collections/{self.collection}/points/search",
            {
                "vector": vector,
                "limit": max(1, min(limit, 100)),
                "with_payload": True,
                "filter": {"must": [{"key": "organization_id", "match": {"value": organization_id}}]},
            },
        )
        return list(result.get("result") or [])

    def _request(self, method: str, path: str, body: dict[str, Any]) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["api-key"] = self.api_key
        req = urllib_request.Request(
            f"{self.url}{path}",
            data=json.dumps(body).encode(),
            headers=headers,
            method=method,
        )
        with urllib_request.urlopen(req, timeout=self.timeout_seconds) as response:
            return json.loads(response.read())
