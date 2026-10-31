"""Zero-dependency local server for the DriftWatch dashboard."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import numpy as np
import pandas as pd

from .alerts import AlertDispatcher
from .metrics import metric_catalog
from .monitor import demo_datasets
from .observability import Metrics, log_event
from .openapi import API_SPEC
from .pipeline import Monitor
from .production import GeminiLLMJudge, RateLimiter, allowed_origins, max_body_bytes
from .research import run_public_suite, run_suite
from .security import (
    hash_password,
    issue_token,
    new_api_key,
    verify_password,
    verify_token,
)
from .storage import Store

ROOT = Path(
    os.getenv("DRIFTWATCH_WEB_ROOT", str(Path(__file__).resolve().parents[2]))
)
WEB = ROOT / "web"
DASHBOARD = ROOT if (ROOT / "index.html").exists() else ROOT / "dashboard" / "dist"


def _store():
    if os.getenv("DRIFTWATCH_DATABASE_URL", "").startswith(
        ("postgresql://", "postgres://")
    ):
        from .postgres_store import PostgresStore

        return PostgresStore()
    return Store()


STORE = _store()
ALERTS = AlertDispatcher(STORE)
METRICS = Metrics()
LIMITER = RateLimiter(
    rate=float(os.getenv("DRIFTWATCH_RATE_LIMIT", "60")),
    burst=int(os.getenv("DRIFTWATCH_RATE_BURST", "120")),
)
LOGGER = logging.getLogger("driftwatch.api")


class Handler(BaseHTTPRequestHandler):
    def _identity(self) -> dict[str, Any] | None:
        header = self.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return None
        return verify_token(header[7:])

    def _api_key_identity(self) -> dict[str, Any] | None:
        raw = self.headers.get("X-DriftWatch-Key")
        if not raw:
            return None
        key_hash = hashlib.sha256(raw.encode()).hexdigest()
        with STORE._connect() as db:
            row = db.execute(
                "SELECT organization_id, id FROM api_keys WHERE key_hash = ? AND revoked_at IS NULL",
                (key_hash,),
            ).fetchone()
        return (
            {"org_id": row["organization_id"], "sub": "api-key", "role": "ML_ENGINEER"}
            if row
            else None
        )

    def _require_write_access(self) -> dict[str, Any] | None:
        identity = self._identity() or self._api_key_identity()
        if not identity:
            self._send(b'{"error":"authentication required"}', status=401)
            return None
        if (
            identity.get("role") not in {"OWNER", "ADMIN", "ML_ENGINEER"}
            and identity.get("sub") != "api-key"
        ):
            self._send(b'{"error":"insufficient role"}', status=403)
            return None
        return identity

    def _require_read_access(self) -> dict[str, Any] | None:
        identity = self._identity()
        if not identity:
            self._send(b'{"error":"authentication required"}', status=401)
            return None
        if identity.get("role") not in {"OWNER", "ADMIN", "ML_ENGINEER", "VIEWER"}:
            self._send(b'{"error":"insufficient role"}', status=403)
            return None
        return identity

    def _send(
        self, payload: bytes, content_type: str = "application/json", status: int = 200
    ) -> None:
        self.send_response(status)
        origin = self.headers.get("Origin")
        if origin and origin in allowed_origins():
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:  # noqa: N802
        started = time.perf_counter()
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/metrics":
            self._send(METRICS.prometheus().encode(), "text/plain; version=0.0.4")
            return
        if not LIMITER.allow(self.client_address[0]):
            self._send(b'{"error":"rate limit exceeded"}', status=429)
            return
        if path == "/api/demo":
            ref, cur = demo_datasets()
            result = Monitor.from_reference(ref, model_name="demo-checkout").run(cur)
            run = STORE.record_run(result.to_dict())
            ALERTS.dispatch(run)
            self._send(json.dumps(run["report"]).encode())
            return
        if path == "/api/v1/metrics":
            self._send(json.dumps({"metrics": metric_catalog()}).encode())
            return
        if path == "/openapi.json":
            self._send(json.dumps(API_SPEC).encode())
            return
        if path == "/healthz":
            self._send(
                json.dumps({"status": "ok", "backend": type(STORE).__name__}).encode()
            )
            return
        if path == "/readyz":
            try:
                with STORE._connect() as db:
                    db.execute("SELECT 1").fetchone()
                self._send(json.dumps({"status": "ready"}).encode())
            except Exception as error:
                self._send(
                    json.dumps({"status": "not_ready", "error": str(error)}).encode(),
                    status=503,
                )
            return
        if path == "/api/runs":
            identity = self._require_read_access()
            if not identity:
                return
            query = parse_qs(parsed.query)
            try:
                limit = int(query.get("limit", ["30"])[0])
            except ValueError:
                self._send(b'{"error":"limit must be an integer"}', status=400)
                return
            self._send(
                json.dumps(
                    STORE.list_runs(
                        organization_id=identity["org_id"],
                        limit=limit,
                        model_id=query.get("model_id", [None])[0],
                        severity=query.get("severity", [None])[0],
                        decision=query.get("decision", [None])[0],
                        created_after=query.get("created_after", [None])[0],
                        created_before=query.get("created_before", [None])[0],
                    )
                ).encode()
            )
            return
        if path == "/api/models":
            identity = self._require_read_access()
            if not identity:
                return
            self._send(json.dumps(STORE.list_models(identity["org_id"])).encode())
            return
        if path == "/api/alerts":
            identity = self._require_read_access()
            if not identity:
                return
            self._send(json.dumps(STORE.list_alerts(organization_id=identity["org_id"])).encode())
            return
        if path == "/api/v1/me":
            identity = self._identity()
            self._send(
                json.dumps(identity or {"error": "authentication required"}).encode(),
                status=200 if identity else 401,
            )
            return
        if path.startswith("/api/v1/projects") or path in {
            "/api/v1/audit",
            "/api/v1/retraining",
            "/api/v1/datasets",
            "/api/v1/schedules",
            "/api/v1/schedule-runs",
            "/api/v1/alert-rules",
            "/api/v1/research",
            "/api/v1/integration",
            "/api/v1/model-comparison",
        }:
            identity = self._identity()
            if not identity:
                self._send(b'{"error":"authentication required"}', status=401)
                return
            if path == "/api/v1/audit":
                self._send(json.dumps(STORE.list_audit(identity["org_id"])).encode())
            elif path == "/api/v1/retraining":
                self._send(
                    json.dumps(
                        STORE.list_retraining_requests(identity["org_id"])
                    ).encode()
                )
            elif path == "/api/v1/datasets":
                self._send(json.dumps(STORE.list_dataset_versions(identity["org_id"])).encode())
            elif path == "/api/v1/schedules":
                self._send(json.dumps(STORE.list_schedules(identity["org_id"])).encode())
            elif path == "/api/v1/schedule-runs":
                self._send(json.dumps(STORE.list_schedule_runs(identity["org_id"])).encode())
            elif path == "/api/v1/alert-rules":
                self._send(json.dumps(STORE.list_alert_rules(identity["org_id"])).encode())
            elif path == "/api/v1/model-comparison":
                self._send(json.dumps(STORE.compare_models(identity["org_id"])).encode())
            elif path == "/api/v1/research":
                self._send(json.dumps(STORE.list_research_runs(identity["org_id"])).encode())
            elif path == "/api/v1/integration":
                self._send(
                    json.dumps(
                        {
                            "install": 'pip install "driftwatch @ git+https://github.com/Tripathi-Nishant/DRIFT-WATCH.git"',
                            "python": (
                                "from driftwatch import monitor\n"
                                "report = monitor(reference_df, current_df, "
                                'model_name="my-model", api_key="YOUR_DW_KEY")\n'
                                'print(report["summary"]["decision"])'
                            ),
                            "dashboard": "Reports are persisted in this organization workspace.",
                            "api_key_header": "X-DriftWatch-Key",
                        }
                    ).encode()
                )
            else:
                self._send(json.dumps(STORE.list_projects(identity["org_id"])).encode())
            return
        files = {
            "/": "index.html",
            "/index.html": "index.html",
            "/app.js": "app.js",
            "/styles.css": "styles.css",
        }
        file_name = files.get(path)
        if path.startswith("/assets/") and DASHBOARD.exists():
            candidate = (DASHBOARD / path.lstrip("/")).resolve()
            if DASHBOARD.resolve() in candidate.parents and candidate.is_file():
                types = {
                    ".js": "text/javascript",
                    ".css": "text/css",
                    ".map": "application/json",
                }
                self._send(candidate.read_bytes(), types.get(candidate.suffix, "application/octet-stream"))
                return
        if file_name:
            file = (DASHBOARD if (DASHBOARD / file_name).exists() else WEB) / file_name
            types = {
                ".html": "text/html; charset=utf-8",
                ".js": "text/javascript",
                ".css": "text/css",
            }
            self._send(file.read_bytes(), types[file.suffix])
            return
        METRICS.observe(path, 404, time.perf_counter() - started)
        log_event(LOGGER, "http_request", method="GET", route=path, status=404)
        self._send(b"Not found", "text/plain", 404)

    def do_OPTIONS(self) -> None:  # noqa: N802
        origin = self.headers.get("Origin")
        if origin not in allowed_origins():
            self._send(b'{"error":"origin not allowed"}', status=403)
            return
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header(
            "Access-Control-Allow-Headers",
            "Authorization,Content-Type,X-DriftWatch-Key",
        )
        self.send_header("Access-Control-Max-Age", "600")
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path not in {
            "/api/analyze",
            "/api/models",
            "/api/ingest/predictions",
            "/api/ingest/feedback",
            "/api/v1/auth/register",
            "/api/v1/auth/login",
            "/api/v1/projects",
            "/api/v1/api-keys",
            "/api/v1/datasets",
            "/api/v1/schedules",
            "/api/v1/alert-rules",
        } and not path.startswith("/api/v1/retraining"):
            self._send(b"Not found", "text/plain", 404)
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            self._send(b'{"error":"invalid content length"}', status=400)
            return
        if length <= 0 or length > max_body_bytes():
            self._send(b'{"error":"request body too large or empty"}', status=413)
            return
        try:
            body = json.loads(self.rfile.read(length))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send(b'{"error":"invalid JSON"}', status=400)
            return
        if path == "/api/v1/retraining":
            identity = self._require_write_access()
            if not identity:
                return
            request = STORE.create_retraining_request(
                identity["org_id"],
                body.get("model_id"),
                identity["sub"],
                body["report"],
            )
            STORE.audit(
                "retraining.requested",
                identity["org_id"],
                identity["sub"],
                "retraining",
                request["id"],
            )
            self._send(json.dumps(request).encode(), status=201)
            return
        if path.startswith("/api/v1/retraining/") and path.endswith("/approve"):
            identity = self._require_write_access()
            if not identity:
                return
            request_id = path.split("/")[-2]
            request = STORE.approve_retraining_request(
                identity["org_id"], request_id, identity["sub"]
            )
            if not request:
                self._send(
                    b'{"error":"pending retraining request not found"}', status=404
                )
                return
            STORE.audit(
                "retraining.approved",
                identity["org_id"],
                identity["sub"],
                "retraining",
                request_id,
            )
            self._send(json.dumps(request).encode())
            return
        if path in {
            "/api/ingest/predictions",
            "/api/ingest/feedback",
            "/api/analyze",
            "/api/models",
        }:
            identity = self._require_write_access()
            if not identity:
                return
        if path == "/api/v1/auth/register":
            organization = STORE.create_organization(
                body.get("organization", f"{body['email']}'s workspace")
            )
            user = STORE.create_user(
                body["email"], hash_password(body["password"]), organization["id"]
            )
            STORE.audit(
                "user.registered", organization["id"], user["id"], "user", user["id"]
            )
            token = issue_token(user["id"], user["role"], organization["id"])
            self._send(
                json.dumps(
                    {"user": user, "organization": organization, "access_token": token}
                ).encode(),
                status=201,
            )
            return
        if path == "/api/v1/auth/login":
            user = STORE.find_user(body["email"])
            if not user or not verify_password(body["password"], user["password_hash"]):
                self._send(b'{"error":"invalid credentials"}', status=401)
                return
            token = issue_token(user["id"], user["role"], user["organization_id"])
            STORE.audit(
                "user.login", user["organization_id"], user["id"], "user", user["id"]
            )
            self._send(
                json.dumps(
                    {
                        "access_token": token,
                        "user": {
                            "id": user["id"],
                            "email": user["email"],
                            "role": user["role"],
                            "organization_id": user["organization_id"],
                        },
                    }
                ).encode()
            )
            return
        if path in {"/api/v1/projects", "/api/v1/api-keys", "/api/v1/datasets", "/api/v1/schedules", "/api/v1/alert-rules"}:
            identity = self._require_write_access()
            if not identity:
                return
            if path == "/api/v1/projects":
                item = STORE.create_project(identity["org_id"], body["name"])
                event = "project.created"
            elif path == "/api/v1/api-keys":
                raw, key_hash = new_api_key()
                item = STORE.save_api_key(identity["org_id"], body.get("name", "library"), key_hash)
                item["key"] = raw
                event = "api_key.created"
            elif path == "/api/v1/datasets":
                item = STORE.create_dataset_version(
                    identity["org_id"], body["name"], body["version"], body.get("kind", "reference"),
                    body["rows"], body["columns"], body["fingerprint"], body.get("model_id"), body.get("metadata"),
                )
                event = "dataset.version.created"
            elif path == "/api/v1/schedules":
                item = STORE.create_schedule(identity["org_id"], body["name"], body["cadence"], body.get("model_id"), body.get("config"))
                event = "schedule.created"
            else:
                item = STORE.create_alert_rule(
                    identity["org_id"], body["name"], body.get("severity", "HIGH"),
                    body.get("channel", "webhook"), body.get("destination"),
                    body.get("threshold"), body.get("metric", "drift_rate"),
                )
                event = "alert-rule.created"
            STORE.audit(event, identity["org_id"], identity["sub"], path.rsplit("/", 1)[-1], item["id"])
            self._send(json.dumps(item).encode(), status=201)
            return
        if path == "/api/v1/research":
            identity = self._require_write_access()
            if not identity:
                return
            seeds = body.get("seeds", [1, 7, 42, 99])
            if (
                not isinstance(seeds, list)
                or not seeds
                or len(seeds) > 50
                or not all(isinstance(seed, int) for seed in seeds)
            ):
                self._send(b'{"error":"seeds must be a non-empty list of at most 50 integers"}', status=400)
                return
            suite = body.get("suite", "synthetic")
            if suite not in {"synthetic", "public"}:
                self._send(b'{"error":"suite must be synthetic or public"}', status=400)
                return
            with tempfile.NamedTemporaryFile(suffix=".json") as output:
                result = (
                    run_public_suite(output.name, seeds)
                    if suite == "public"
                    else run_suite(output.name, seeds)
                )
            item = STORE.record_research_run(identity["org_id"], suite, seeds, result)
            STORE.audit("research.run.created", identity["org_id"], identity["sub"], "research", item["id"])
            self._send(json.dumps(item).encode(), status=201)
            return
        if path == "/api/models":
            self._send(
                json.dumps(
                    STORE.create_model(
                        body["name"],
                        body.get("version", "1.0.0"),
                        body.get("model_type", "classification"),
                        body.get("reference_profile"),
                        identity["org_id"],
                    )
                ).encode(),
                status=201,
            )
            return
        if path == "/api/ingest/predictions":
            ids = STORE.add_predictions(
                body.get("model_id"), body.get("predictions", [])
            )
            self._send(
                json.dumps({"accepted": len(ids), "ids": ids}).encode(), status=202
            )
            return
        if path == "/api/ingest/feedback":
            accepted = STORE.add_feedback(body["prediction_id"], body["label"])
            self._send(
                json.dumps({"accepted": accepted}).encode(),
                status=202 if accepted else 404,
            )
            return
        reference = pd.DataFrame(body["reference"])
        current = pd.DataFrame(body["current"])
        semantic_text = None
        if isinstance(body.get("semantic_text_reference"), list) and isinstance(
            body.get("semantic_text_current"), list
        ):
            semantic_text = (
                body["semantic_text_reference"],
                body["semantic_text_current"],
            )
        images = None
        if isinstance(body.get("images_reference"), list) and isinstance(
            body.get("images_current"), list
        ):
            images = (
                np.asarray(body["images_reference"]),
                np.asarray(body["images_current"]),
            )
        result = Monitor.from_reference(
            reference,
            model_type=body.get("task", body.get("model_type", "auto")),
            model_name=body.get("model_name", "model"),
        ).run(
            current,
            predictions=body.get("predictions"),
            labels=body.get("labels"),
            semantic_text=semantic_text,
            images=images,
        )
        report = result.to_dict()
        judge_records = body.get("llm_judge_records")
        if isinstance(judge_records, list):
            if os.getenv("GEMINI_API_KEY"):
                report["llm_judge"] = {
                    "available": True,
                    "provider": "gemini",
                    "results": GeminiLLMJudge.from_environment().evaluate(
                        judge_records
                    ),
                }
            else:
                report["llm_judge"] = {
                    "available": False,
                    "reason": "GEMINI_API_KEY is not configured",
                }
        run = STORE.record_run(report, body.get("model_id"), identity["org_id"])
        profile = report.get("profile", {})
        fingerprint = profile.get("fingerprint", report["summary"].get("reference_profile", ""))
        STORE.create_dataset_version(
            identity["org_id"], f"{report['summary'].get('model', 'model')}-reference",
            fingerprint or "unversioned", "reference", len(reference), len(reference.columns),
            fingerprint or "unversioned", body.get("model_id"),
            {"source": "analysis", "run_id": run["id"]},
        )
        current_fingerprint = hashlib.sha256(
            json.dumps(current.to_dict(orient="list"), sort_keys=True, default=str).encode()
        ).hexdigest()[:16]
        STORE.create_dataset_version(
            identity["org_id"], f"{report['summary'].get('model', 'model')}-current",
            current_fingerprint, "current", len(current), len(current.columns),
            current_fingerprint, body.get("model_id"),
            {"source": "analysis", "run_id": run["id"]},
        )
        ALERTS.dispatch(run)
        self._send(json.dumps(run["report"]).encode())


def run(host: str = "127.0.0.1", port: int = 8765) -> None:
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"DriftWatch running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
