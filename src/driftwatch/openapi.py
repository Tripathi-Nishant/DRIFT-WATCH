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
        "/api/runs": {
            "get": {
                "summary": "List monitoring runs with optional filters",
                "security": [{"bearerAuth": []}],
                "parameters": [
                    {"name": "limit", "in": "query", "schema": {"type": "integer", "maximum": 100}},
                    {"name": "model_id", "in": "query", "schema": {"type": "string"}},
                    {"name": "severity", "in": "query", "schema": {"type": "string"}},
                    {"name": "decision", "in": "query", "schema": {"type": "string"}},
                    {"name": "created_after", "in": "query", "schema": {"type": "string", "format": "date-time"}},
                    {"name": "created_before", "in": "query", "schema": {"type": "string", "format": "date-time"}},
                ],
            }
        },
        "/api/alerts": {"get": {"summary": "List alert delivery attempts", "security": [{"bearerAuth": []}]}},
        "/api/v1/retraining": {"get": {"summary": "List retraining requests", "security": [{"bearerAuth": []}]}},
        "/api/v1/datasets": {
            "get": {"summary": "List versioned datasets", "security": [{"bearerAuth": []}]},
            "post": {"summary": "Register a dataset version", "security": [{"bearerAuth": []}]},
        },
        "/api/v1/schedules": {
            "get": {"summary": "List monitoring schedules", "security": [{"bearerAuth": []}]},
            "post": {"summary": "Create a monitoring schedule", "security": [{"bearerAuth": []}]},
        },
        "/api/v1/schedule-runs": {
            "get": {"summary": "List persisted schedule executions", "security": [{"bearerAuth": []}]},
        },
        "/api/v1/alert-rules": {
            "get": {"summary": "List alert rules", "security": [{"bearerAuth": []}]},
            "post": {"summary": "Create an alert rule", "security": [{"bearerAuth": []}]},
        },
        "/api/v1/model-comparison": {
            "get": {"summary": "Compare model monitoring outcomes", "security": [{"bearerAuth": []}]},
        },
        "/api/v1/incidents": {
            "get": {"summary": "List monitoring incidents", "security": [{"bearerAuth": []}]},
            "post": {"summary": "Create an incident", "security": [{"bearerAuth": []}]},
        },
        "/api/v1/api-keys": {
            "get": {"summary": "List organization API keys", "security": [{"bearerAuth": []}]},
            "post": {"summary": "Create an ingestion API key", "security": [{"bearerAuth": []}]},
        },
        "/api/v1/research": {
            "get": {"summary": "List reproducible benchmark runs", "security": [{"bearerAuth": []}]},
            "post": {"summary": "Run a seeded research benchmark", "security": [{"bearerAuth": []}]},
        },
        "/api/v1/integration": {
            "get": {"summary": "Get copy-ready SDK integration instructions", "security": [{"bearerAuth": []}]},
        },
    },
}
