"""Typed public API models for SDK and generated-client consumers."""

from __future__ import annotations

from typing import Any, NotRequired, TypedDict


class MonitoringSummary(TypedDict, total=False):
    severity: str
    decision: str
    model: str
    drift_rate: float
    quality_score: float


class MonitoringRun(TypedDict):
    id: str
    created_at: str
    severity: str
    decision: str
    report: dict[str, Any]


class UsageSummary(TypedDict):
    plan: str
    usage: dict[str, int]
    limits: dict[str, int]
    remaining: dict[str, int]
    exceeded: list[str]


class AccessRequest(TypedDict):
    id: str
    email: str
    organization: str
    use_case: str
    status: str
    created_at: str
    invitation_token: NotRequired[str]
