"""Double-submit cookie CSRF protection middleware.

On every non-exempt response, sets a ``csrf_token`` cookie (not httponly,
so client JS can read it for fetch-based POSTs).  On every POST, validates
that the submitted token (form field or ``X-CSRF-Token`` header) matches
the cookie value.  Returns 403 for missing or mismatched tokens.

Exempt paths: ``/health``, ``/static/``.

Template usage:
    All ``<form method="POST">`` elements must include::

        <input type="hidden" name="csrf_token"
               value="{{ request.state.csrf_token }}">

JS usage (fetch-based POSTs):
    Read the ``csrf_token`` cookie and send it as an ``X-CSRF-Token`` header.

Implementation note:
    Uses a pure ASGI middleware (not ``BaseHTTPMiddleware``) to avoid
    consuming the request body stream.  ``BaseHTTPMiddleware`` + ``request.form()``
    prevents downstream handlers from reading form data.
"""

from __future__ import annotations

import logging
import os
import secrets
from typing import Any
from urllib.parse import parse_qs

from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger(__name__)

CSRF_COOKIE_NAME = "csrf_token"
CSRF_FORM_FIELD = "csrf_token"
CSRF_HEADER = "X-CSRF-Token"

_EXEMPT_PREFIXES = ("/health", "/static/")


def _is_exempt(path: str) -> bool:
    """Return True if the path is exempt from CSRF validation."""
    return any(path.startswith(p) for p in _EXEMPT_PREFIXES)


class CSRFMiddleware:
    """Double-submit cookie CSRF protection for all POST endpoints.

    Pure ASGI middleware that reads the raw body to extract the CSRF form
    field without consuming the stream for downstream handlers.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> Any:
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        request = Request(scope)
        path = request.url.path

        if _is_exempt(path):
            return await self.app(scope, receive, send)

        csrf_cookie = request.cookies.get(CSRF_COOKIE_NAME, "")

        # Validate POST requests
        if request.method == "POST":
            if not csrf_cookie:
                logger.warning("CSRF rejected (no cookie): %s %s", request.method, path)
                response = Response(
                    "CSRF token missing or invalid",
                    status_code=403,
                    media_type="text/plain",
                )
                return await response(scope, receive, send)

            content_type = request.headers.get("content-type", "")
            if "application/json" in content_type:
                submitted = request.headers.get(CSRF_HEADER, "")
            else:
                # Read the raw body to extract the CSRF field without
                # consuming the stream for downstream handlers.
                body = b""
                while True:
                    message = await receive()
                    body += message.get("body", b"")
                    if not message.get("more_body", False):
                        break

                # Parse the CSRF token from URL-encoded form data
                try:
                    parsed = parse_qs(body.decode("utf-8"), keep_blank_values=True)
                    raw = parsed.get(CSRF_FORM_FIELD, [""])[0]
                    submitted = raw if isinstance(raw, str) else ""
                except (UnicodeDecodeError, ValueError):
                    submitted = ""

                # Replace receive so downstream gets the cached body
                body_sent = False

                async def cached_receive() -> Message:
                    nonlocal body_sent
                    if not body_sent:
                        body_sent = True
                        return {"type": "http.request", "body": body, "more_body": False}
                    return {"type": "http.request", "body": b"", "more_body": False}

                receive = cached_receive  # noqa: PLW0642

            if not submitted or not secrets.compare_digest(submitted, csrf_cookie):
                logger.warning("CSRF rejected (mismatch): %s %s", request.method, path)
                response = Response(
                    "CSRF token missing or invalid",
                    status_code=403,
                    media_type="text/plain",
                )
                return await response(scope, receive, send)

        # Generate token if cookie absent (first visit)
        if not csrf_cookie:
            csrf_cookie = secrets.token_urlsafe(32)

        # Make token available to templates via request.state
        scope.setdefault("state", {})
        scope["state"]["csrf_token"] = csrf_cookie

        # Intercept outgoing response to set the CSRF cookie
        is_prod = os.environ.get("APP_ENV", "development") == "production"
        cookie_value = (
            f"{CSRF_COOKIE_NAME}={csrf_cookie}; Path=/; SameSite=Lax"
        )
        if is_prod:
            cookie_value += "; Secure"

        async def send_with_cookie(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"set-cookie", cookie_value.encode("utf-8")))
                message = {**message, "headers": headers}
            await send(message)

        return await self.app(scope, receive, send_with_cookie)
