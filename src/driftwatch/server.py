"""Zero-dependency local server for the DriftWatch dashboard."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pandas as pd

from .alerts import AlertDispatcher
from .metrics import metric_catalog
from .monitor import demo_datasets
from .observability import Metrics, log_event
from .pipeline import Monitor
from .production import RateLimiter, allowed_origins, max_body_bytes
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
        path = urlparse(self.path).path
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
            if not self._require_read_access():
                return
            self._send(json.dumps(STORE.list_runs()).encode())
            return
        if path == "/api/models":
            if not self._require_read_access():
                return
            self._send(json.dumps(STORE.list_models()).encode())
            return
        if path == "/api/alerts":
            if not self._require_read_access():
                return
            self._send(json.dumps(STORE.list_alerts()).encode())
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
        if path in {"/api/v1/projects", "/api/v1/api-keys"}:
            identity = self._identity()
            if not identity:
                self._send(b'{"error":"authentication required"}', status=401)
                return
            if path == "/api/v1/projects":
                project = STORE.create_project(identity["org_id"], body["name"])
                STORE.audit(
                    "project.created",
                    identity["org_id"],
                    identity["sub"],
                    "project",
                    project["id"],
                )
                self._send(json.dumps(project).encode(), status=201)
            else:
                raw, key_hash = new_api_key()
                item = STORE.save_api_key(
                    identity["org_id"], body.get("name", "library"), key_hash
                )
                STORE.audit(
                    "api_key.created",
                    identity["org_id"],
                    identity["sub"],
                    "api_key",
                    item["id"],
                )
                self._send(json.dumps(item | {"key": raw}).encode(), status=201)
            return
        if path == "/api/models":
            self._send(
                json.dumps(
                    STORE.create_model(
                        body["name"],
                        body.get("version", "1.0.0"),
                        body.get("model_type", "classification"),
                        body.get("reference_profile"),
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
        result = Monitor.from_reference(
            reference,
            model_type=body.get("model_type", "classification"),
            model_name=body.get("model_name", "model"),
        ).run(current, predictions=body.get("predictions"), labels=body.get("labels"))
        run = STORE.record_run(result.to_dict(), body.get("model_id"))
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
