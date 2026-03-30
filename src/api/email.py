"""Mailgun email helper for the baseball-crawl application.

Sends magic link login emails via Mailgun API (when configured) or
logs the link to stdout (for local development without email infrastructure).

Configuration (environment variables):
    MAILGUN_API_KEY   -- Mailgun API key. If absent, falls back to stdout logging.
    MAILGUN_DOMAIN    -- Mailgun sending domain (e.g. mg.example.com).
    MAILGUN_FROM_EMAIL -- Sender address. Defaults to noreply@{MAILGUN_DOMAIN}.
"""

from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger(__name__)

_MAILGUN_API_BASE = "https://api.mailgun.net/v3"
_SUBJECT = "Your login link for Baseball Stats"


async def send_magic_link_email(to_email: str, magic_link_url: str) -> bool:
    """Send a magic link login email to the given address.

    When ``MAILGUN_API_KEY`` is set, sends via the Mailgun async API using
    HTTP Basic auth.  When it is not set, logs the link to stdout at INFO
    level so local development works without email infrastructure.

    Args:
        to_email: Recipient email address.
        magic_link_url: The full magic link URL to send.

    Returns:
        True if the email was sent (or logged) successfully; False on error.
    """
    mg_key = os.environ.get("MAILGUN_API_KEY", "")
    if not mg_key:
        logger.info("[DEV] Magic link for %s: %s", to_email, magic_link_url)
        return True

    domain = os.environ.get("MAILGUN_DOMAIN", "")
    if not domain:
        logger.error("MAILGUN_DOMAIN is required when MAILGUN_API_KEY is set")
        return False

    from_email = os.environ.get("MAILGUN_FROM_EMAIL", f"noreply@{domain}")
    body = (
        f"Click the link below to log in to Baseball Stats.\n\n"
        f"{magic_link_url}\n\n"
        f"This link expires in 15 minutes and can only be used once.\n"
        f"If you did not request this, you can safely ignore this email."
    )

    url = f"{_MAILGUN_API_BASE}/{domain}/messages"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                auth=("api", mg_key),
                data={
                    "from": from_email,
                    "to": to_email,
                    "subject": _SUBJECT,
                    "text": body,
                },
                timeout=10.0,
            )
        if response.is_success:
            logger.info("Magic link email sent to %s", to_email)
            return True
        logger.error(
            "Mailgun request failed: status=%d body=%s",
            response.status_code,
            response.text[:200],
        )
        return False
    except httpx.RequestError:
        logger.exception("Mailgun request error for %s", to_email)
        return False
