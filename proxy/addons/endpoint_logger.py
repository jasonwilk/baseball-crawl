"""mitmproxy addon: API endpoint discovery log.

Logs every GameChanger API request/response pair to an append-only JSONL file.
Each entry records the method, host, path, query parameter keys, content-types,
status code, timestamp, and traffic source.

When PROXY_CAPTURE_BODIES=true (the default), each entry also includes the full
request/response bodies (as strings), all headers, and query parameter values.
Bodies exceeding MAX_BODY_BYTES are replaced with a truncation sentinel.
Binary content types (image/*, video/*, application/octet-stream) produce a null
body field. Auth header stripping is configurable via PROXY_STRIP_AUTH_HEADERS.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse, parse_qs, parse_qsl

from proxy.addons import gc_filter

if TYPE_CHECKING:
    from mitmproxy import http

logger = logging.getLogger(__name__)

# Fallback path used when PROXY_SESSION_DIR is not set.
LOG_PATH = Path("/app/proxy/data/endpoint-log.jsonl")

# Default body size cap (2 MB). Override via MAX_BODY_BYTES env var.
_DEFAULT_MAX_BODY_BYTES = 2 * 1024 * 1024

# Headers stripped when PROXY_STRIP_AUTH_HEADERS=true (lowercase, already normalised by mitmproxy).
_SENSITIVE_HEADERS: frozenset[str] = frozenset({
    "gc-token",
    "gc-device-id",
    "authorization",
    "gc-signature",
    "cookie",
    "set-cookie",
})

# Content-type prefixes/exact values indicating binary data (body capture skipped).
_BINARY_CT_PREFIXES = ("image/", "video/")
_BINARY_CT_EXACT = "application/octet-stream"


def _is_binary_content_type(content_type: str) -> bool:
    """Return True if the content type indicates non-text binary data."""
    ct = content_type.lower().split(";")[0].strip()
    return ct == _BINARY_CT_EXACT or any(ct.startswith(p) for p in _BINARY_CT_PREFIXES)


_PII_FIELDS = frozenset({"email", "password"})


def _redact_auth_body(body: str | None) -> str | None:
    """Redact PII fields from a POST /auth request body string.

    Parses the body as JSON and replaces the values of ``email`` and
    ``password`` keys with ``"[REDACTED]"``.  The ``type`` field and all
    other fields are preserved.  Returns the body unchanged when it is
    ``None``, empty, or not valid JSON.

    Args:
        body: Decoded request body string (may be ``None``).

    Returns:
        Redacted JSON string, or the original value if redaction is not
        applicable.
    """
    if not body:
        return body
    try:
        parsed = json.loads(body)
    except (ValueError, TypeError):
        return body
    if not isinstance(parsed, dict):
        return body
    redacted = {
        k: "[REDACTED]" if k in _PII_FIELDS else v
        for k, v in parsed.items()
    }
    return json.dumps(redacted)


def _extract_body(content: bytes, content_type: str, max_bytes: int) -> str | None:
    """Extract a request or response body as a string.

    Args:
        content: Raw bytes from flow.request.content or flow.response.content.
        content_type: Content-Type header value (used to detect binary payloads).
        max_bytes: Body size cap; exceeded bodies become a truncation sentinel.

    Returns:
        None for empty bodies or binary content types.
        A truncation sentinel string for oversized bodies.
        The decoded body string otherwise.
    """
    if not content:
        return None
    if _is_binary_content_type(content_type):
        return None
    if len(content) > max_bytes:
        return f"<truncated: {len(content)} bytes>"
    return content.decode("utf-8", errors="replace")


class EndpointLogger:
    """Append a JSONL entry to the endpoint log for every GameChanger response."""

    def __init__(self) -> None:
        session_dir = os.environ.get("PROXY_SESSION_DIR")
        if session_dir:
            self.log_path = Path(session_dir) / "endpoint-log.jsonl"
        else:
            self.log_path = LOG_PATH

        self.capture_bodies: bool = (
            os.environ.get("PROXY_CAPTURE_BODIES", "true").lower() == "true"
        )
        self.strip_auth_headers: bool = (
            os.environ.get("PROXY_STRIP_AUTH_HEADERS", "false").lower() == "true"
        )

        raw_max = os.environ.get("MAX_BODY_BYTES", str(_DEFAULT_MAX_BODY_BYTES))
        try:
            self.max_body_bytes: int = int(raw_max)
        except (ValueError, TypeError):
            logger.warning(
                "endpoint_logger: invalid MAX_BODY_BYTES value %r; using default %d",
                raw_max,
                _DEFAULT_MAX_BODY_BYTES,
            )
            self.max_body_bytes = _DEFAULT_MAX_BODY_BYTES

    def response(self, flow: http.HTTPFlow) -> None:
        """Hook called after a response is received.

        Filters to GameChanger domains and logs the request/response pair.
        """
        host = flow.request.pretty_host
        if not gc_filter.is_gamechanger_domain(host):
            return

        user_agent = flow.request.headers.get("user-agent", "")
        source = gc_filter.detect_source(user_agent)

        entry = _build_entry(
            flow,
            host,
            source,
            capture_bodies=self.capture_bodies,
            strip_auth_headers=self.strip_auth_headers,
            max_body_bytes=self.max_body_bytes,
        )
        _append_entry(entry, self.log_path)


def _build_capture_fields(
    flow: http.HTTPFlow,
    query: str,
    request_content_type: str,
    response_content_type: str,
    *,
    strip_auth_headers: bool,
    max_body_bytes: int,
) -> dict[str, Any]:
    """Build the capture-mode fields (bodies, headers, query values).

    Called only when PROXY_CAPTURE_BODIES=true.
    """
    req_headers = dict(flow.request.headers)
    resp_headers = dict(flow.response.headers)
    if strip_auth_headers:
        req_headers = {k: v for k, v in req_headers.items() if k not in _SENSITIVE_HEADERS}
        resp_headers = {k: v for k, v in resp_headers.items() if k not in _SENSITIVE_HEADERS}

    request_body = _extract_body(flow.request.content, request_content_type, max_body_bytes)
    # Redact PII fields from POST /auth request bodies before logging.
    parsed_path = urlparse(flow.request.pretty_url).path
    if flow.request.method == "POST" and parsed_path.endswith("/auth"):
        request_body = _redact_auth_body(request_body)

    return {
        "query_params": dict(parse_qsl(query, keep_blank_values=True)),
        "request_headers": req_headers,
        "response_headers": resp_headers,
        "request_body": request_body,
        "response_body": _extract_body(flow.response.content, response_content_type, max_body_bytes),
    }


def _build_entry(
    flow: http.HTTPFlow,
    host: str,
    source: str,
    *,
    capture_bodies: bool = True,
    strip_auth_headers: bool = False,
    max_body_bytes: int = _DEFAULT_MAX_BODY_BYTES,
) -> dict[str, Any]:
    """Build a log dict from a mitmproxy flow object.

    Args:
        flow: mitmproxy flow with .request and .response populated.
        host: Pre-resolved hostname (GC domain, already validated).
        source: Traffic source string from gc_filter.detect_source().
        capture_bodies: When True, include bodies, headers, and query values.
        strip_auth_headers: When True, exclude sensitive auth headers.
        max_body_bytes: Body size cap; exceeded bodies become truncation sentinels.

    Returns:
        Dict suitable for JSON serialisation.
    """
    parsed = urlparse(flow.request.pretty_url)
    query_keys = sorted(parse_qs(parsed.query, keep_blank_values=True).keys())
    request_content_type = flow.request.headers.get("content-type", "")
    response_content_type = flow.response.headers.get("content-type", "")

    entry: dict[str, Any] = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "method": flow.request.method,
        "host": host,
        "path": parsed.path,
        "query_keys": query_keys,
        "request_content_type": request_content_type,
        "response_content_type": response_content_type,
        "status_code": flow.response.status_code,
        "source": source,
    }

    if capture_bodies:
        entry.update(_build_capture_fields(
            flow,
            parsed.query,
            request_content_type,
            response_content_type,
            strip_auth_headers=strip_auth_headers,
            max_body_bytes=max_body_bytes,
        ))

    return entry


def _append_entry(entry: dict[str, Any], path: Path | None = None) -> None:
    """Append a single JSONL entry to the log file, creating it if needed.

    Args:
        entry: Dict to serialise as a JSONL line.
        path: Output file path. Defaults to LOG_PATH when not provided.
    """
    target = path if path is not None else LOG_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")
    logger.debug("endpoint_logger: appended entry to %s", target)
