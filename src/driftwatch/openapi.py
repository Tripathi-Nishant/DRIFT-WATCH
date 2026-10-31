"""OpenAPI-compatible description for the public DriftWatch HTTP surface."""

from __future__ import annotations

API_SPEC = {
    "openapi": "3.0.3",
    "info": {
        "title": "DriftWatch API",
        "version": "0.1.0",
        "description": "Model monitoring, decisions, ingestion, and retraining workflows.",
    },
    "servers": [{"url": "/"}],
    "components": {
        "securitySchemes": {
            "bearerAuth": {"type": "http", "scheme": "bearer"},
            "ingestionKey": {"type": "apiKey", "in": "header", "name": "X-DriftWatch-Key"},
        }
    },
    "paths": {
        "/healthz": {"get": {"summary": "Process health"}},
        "/readyz": {"get": {"summary": "Database readiness"}},
        "/metrics": {"get": {"summary": "Prometheus metrics"}},
        "/api/v1/metrics": {"get": {"summary": "Metric catalog"}},
        "/api/v1/auth/register": {"post": {"summary": "Create an organization owner"}},
        "/api/v1/auth/login": {"post": {"summary": "Create a JWT session"}},
        "/api/analyze": {
            "post": {
                "summary": "Analyze reference/current records",
                "security": [{"bearerAuth": []}, {"ingestionKey": []}],
            }
        },
        "/api/ingest/predictions": {
            "post": {
                "summary": "Ingest prediction events",
                "security": [{"ingestionKey": []}],
            }
        },
        "/api/ingest/feedback": {
            "post": {
                "summary": "Attach delayed labels",
                "security": [{"ingestionKey": []}],
            }
        },
        "/api/runs": {"get": {"summary": "List monitoring runs", "security": [{"bearerAuth": []}]}},
        "/api/alerts": {"get": {"summary": "List alert delivery attempts", "security": [{"bearerAuth": []}]}},
        "/api/v1/retraining": {"get": {"summary": "List retraining requests", "security": [{"bearerAuth": []}]}},
    },
}
