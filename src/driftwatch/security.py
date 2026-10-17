"""Offline-friendly authentication primitives for the self-hosted server."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Any


def hash_password(password: str, salt: bytes | None = None) -> str:
    if len(password) < 8:
        raise ValueError("password must contain at least 8 characters")
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 240_000)
    return f"pbkdf2$240000${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds, salt, digest = encoded.split("$")
        candidate = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt), int(rounds)
        ).hex()
        return algorithm == "pbkdf2" and hmac.compare_digest(candidate, digest)
    except (ValueError, TypeError):
        return False


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def issue_token(
    subject: str, role: str, org_id: str, secret: str | None = None, expires: int = 3600
) -> str:
    configured = secret or os.getenv("DRIFTWATCH_SECRET_KEY")
    if not configured:
        if os.getenv("DRIFTWATCH_ENV", "development").lower() == "production":
            raise RuntimeError("DRIFTWATCH_SECRET_KEY is required in production")
        configured = "development-only-change-me"
    key = configured.encode()
    header = _b64(
        json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode()
    )
    payload = _b64(
        json.dumps(
            {
                "sub": subject,
                "role": role,
                "org_id": org_id,
                "exp": int(time.time()) + expires,
            },
            separators=(",", ":"),
        ).encode()
    )
    signature = _b64(
        hmac.new(key, f"{header}.{payload}".encode(), hashlib.sha256).digest()
    )
    return f"{header}.{payload}.{signature}"


def verify_token(token: str, secret: str | None = None) -> dict[str, Any] | None:
    try:
        header, payload, signature = token.split(".")
        configured = secret or os.getenv("DRIFTWATCH_SECRET_KEY")
        if not configured:
            if os.getenv("DRIFTWATCH_ENV", "development").lower() == "production":
                return None
            configured = "development-only-change-me"
        key = configured.encode()
        expected = _b64(
            hmac.new(key, f"{header}.{payload}".encode(), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(signature, expected):
            return None
        padding = "=" * (-len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode((payload + padding).encode()))
        return data if int(data.get("exp", 0)) > int(time.time()) else None
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


def new_api_key() -> tuple[str, str]:
    raw = f"dw_{secrets.token_urlsafe(32)}"
    return raw, hashlib.sha256(raw.encode()).hexdigest()
