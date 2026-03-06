"""mitmproxy addon: API endpoint discovery log.

Logs every GameChanger API request/response pair to an append-only JSONL file.
Each entry records the method, host, path, query parameter names (not values),
content-types, status code, timestamp, and traffic source.

Bodies and query parameter values are NOT logged.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse, parse_qs

from proxy.addons import gc_filter

if TYPE_CHECKING:
    from mitmproxy import http

logger = logging.getLogger(__name__)

# Fallback path used when PROXY_SESSION_DIR is not set.
LOG_PATH = Path("/app/proxy/data/endpoint-log.jsonl")


class EndpointLogger:
    """Append a JSONL entry to the endpoint log for every GameChanger response."""

    def __init__(self) -> None:
        session_dir = os.environ.get("PROXY_SESSION_DIR")
        if session_dir:
            self.log_path = Path(session_dir) / "endpoint-log.jsonl"
        else:
            self.log_path = LOG_PATH

    def response(self, flow: http.HTTPFlow) -> None:
        """Hook called after a response is received.

        Filters to GameChanger domains and logs request/response metadata.
        """
        host = flow.request.pretty_host
        if not gc_filter.is_gamechanger_domain(host):
            return

        user_agent = flow.request.headers.get("user-agent", "")
        source = gc_filter.detect_source(user_agent)

        entry = _build_entry(flow, host, source)
        _append_entry(entry, self.log_path)


def _build_entry(flow: http.HTTPFlow, host: str, source: str) -> dict[str, Any]:
    """Build a log dict from a mitmproxy flow object.

    Args:
        flow: mitmproxy flow with .request and .response populated.
        host: pre-resolved hostname (gc domain, already validated).
        source: traffic source string from gc_filter.detect_source().

    Returns:
        Dict suitable for JSON serialisation.
    """
    parsed = urlparse(flow.request.pretty_url)
    query_keys = sorted(parse_qs(parsed.query, keep_blank_values=True).keys())

    request_content_type = flow.request.headers.get("content-type", "")
    response_content_type = flow.response.headers.get("content-type", "")

    return {
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
