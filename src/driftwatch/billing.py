"""Optional Stripe billing integration with environment-based configuration."""

from __future__ import annotations

import json
import os
from typing import Any


def create_checkout_session(organization_id: str, plan: str, success_url: str, cancel_url: str) -> dict[str, Any]:
    try:
        import stripe
    except ImportError as error:
        raise RuntimeError("Stripe support requires the optional stripe package") from error
    secret = os.getenv("STRIPE_SECRET_KEY")
    price_id = os.getenv(f"STRIPE_PRICE_{plan.upper()}")
    if not secret or not price_id:
        raise RuntimeError(f"Stripe is not configured for plan {plan}")
    stripe.api_key = secret
    return stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        client_reference_id=organization_id,
        metadata={"organization_id": organization_id, "plan": plan},
    )


def parse_webhook(payload: bytes, signature: str) -> dict[str, Any]:
    try:
        import stripe
    except ImportError as error:
        raise RuntimeError("Stripe support requires the optional stripe package") from error
    secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    if not secret:
        raise RuntimeError("STRIPE_WEBHOOK_SECRET is required")
    return json.loads(stripe.Webhook.construct_event(payload, signature, secret))
