"""Optional transactional notifications for beta onboarding."""

from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage


def send_invitation(email: str, token: str) -> bool:
    """Send an invitation when SMTP is configured; return False when disabled."""
    host = os.getenv("DRIFTWATCH_SMTP_HOST")
    sender = os.getenv("DRIFTWATCH_SMTP_FROM")
    if not host or not sender:
        return False
    app_url = os.getenv("DRIFTWATCH_APP_URL", "http://localhost:8765").rstrip("/")
    message = EmailMessage()
    message["Subject"] = "Your DriftWatch beta invitation"
    message["From"] = sender
    message["To"] = email
    message.set_content(
        "Your DriftWatch beta access was approved.\n\n"
        f"Open {app_url}/?invite={token} to create your account. "
        "This invitation expires in seven days and can only be used once.\n"
    )
    with smtplib.SMTP(
        host, int(os.getenv("DRIFTWATCH_SMTP_PORT", "587")), timeout=10
    ) as client:
        if os.getenv("DRIFTWATCH_SMTP_TLS", "true").lower() == "true":
            client.starttls()
        username = os.getenv("DRIFTWATCH_SMTP_USER")
        password = os.getenv("DRIFTWATCH_SMTP_PASSWORD")
        if username and password:
            client.login(username, password)
        client.send_message(message)
    return True
