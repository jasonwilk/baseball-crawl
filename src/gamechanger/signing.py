"""gc-signature HMAC-SHA256 signing module.

Implements the GameChanger request signing algorithm reverse-engineered from the
web.gc.com JavaScript bundle (2026-03-07).  Provides pure functions for body
value extraction, HMAC payload signing, and gc-signature header assembly.

Reference: data/raw/gc-signature-algorithm.md

Usage::

    from src.gamechanger.signing import build_signature_headers

    headers = build_signature_headers(
        client_id="...",
        client_key_b64="...",
        body={"type": "refresh"},
    )
    # Returns {"gc-signature": "...", "gc-timestamp": "...", "gc-client-id": "..."}
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import time
from typing import Any

logger = logging.getLogger(__name__)


def values_for_signer(obj: Any) -> list[str]:
    """Recursively extract leaf string values from a JSON-compatible object.

    Mirrors the JavaScript ``valuesForSigner`` function from the GC auth module.
    Object keys are sorted alphabetically before recursion; array elements are
    flatmapped in order.

    Args:
        obj: Any JSON-compatible value (dict, list, str, int/float, or None).

    Returns:
        Flat list of string leaf values in sorted-key traversal order.

    Examples::

        >>> values_for_signer({"type": "refresh"})
        ['refresh']
        >>> values_for_signer({"type": "client-auth", "client_id": "abc"})
        ['abc', 'client-auth']
        >>> values_for_signer(None)
        ['null']
        >>> values_for_signer([1, 2])
        ['1', '2']
    """
    if isinstance(obj, list):
        result: list[str] = []
        for item in obj:
            result.extend(values_for_signer(item))
        return result

    if isinstance(obj, dict):
        if obj is None:
            return ["null"]
        result = []
        for key in sorted(obj.keys()):
            result.extend(values_for_signer(obj[key]))
        return result

    if isinstance(obj, str):
        return [obj]

    if isinstance(obj, (int, float)):
        # Mirrors JS: case "number": return [String(obj)]
        # Use int representation for whole numbers to match JS Number -> String behavior.
        if isinstance(obj, float) and obj == int(obj):
            return [str(int(obj))]
        return [str(obj)]

    if obj is None:
        return ["null"]

    # Fallback for unexpected types -- return empty list (mirrors JS "undefined" -> [])
    return []


def sign_payload(
    client_key_b64: str,
    timestamp: int,
    nonce_b64: str,
    body: Any,
    previous_signature_b64: str | None = None,
) -> str:
    """Compute the HMAC-SHA256 signature for a POST /auth request.

    Mirrors the JavaScript ``signPayload`` function.  The nonce and optional
    previous signature are decoded from Base64 to raw bytes before being fed
    into the HMAC -- they are NOT included as Base64 strings.

    Args:
        client_key_b64: Base64-encoded HMAC-SHA256 secret key (from .env).
        timestamp: Unix epoch seconds (integer).
        nonce_b64: Base64-encoded random 32-byte nonce.
        body: Request body as a JSON-compatible Python object.
        previous_signature_b64: Optional Base64-encoded previous response
            signature (HMAC part only, without the ``nonce.`` prefix).
            Omit for standalone calls (token refresh without a preceding
            request in the same chain).

    Returns:
        Base64-encoded HMAC-SHA256 digest string.
    """
    logger.debug("Computing HMAC-SHA256 for POST /auth")

    key_bytes = base64.b64decode(client_key_b64)
    nonce_bytes = base64.b64decode(nonce_b64)
    body_values = values_for_signer(body)

    mac = hmac.new(key_bytes, digestmod=hashlib.sha256)

    # Step 1: timestamp as string followed by pipe delimiter
    mac.update((str(timestamp) + "|").encode())

    # Step 2: nonce as raw bytes
    mac.update(nonce_bytes)
    mac.update(b"|")

    # Step 3: body values pipe-delimited
    mac.update("|".join(body_values).encode())

    # Step 4: optional previous signature as raw bytes
    if previous_signature_b64 is not None:
        prev_bytes = base64.b64decode(previous_signature_b64)
        mac.update(b"|")
        mac.update(prev_bytes)

    return base64.b64encode(mac.digest()).decode()


def build_signature_headers(
    client_id: str,
    client_key_b64: str,
    body: Any,
    previous_signature_b64: str | None = None,
) -> dict[str, str]:
    """Assemble gc-signature headers for a POST /auth request.

    Generates a fresh random 32-byte nonce, computes the HMAC signature, and
    returns the three signing-related headers required by the GC auth endpoint.

    The caller is responsible for adding ``gc-token``, ``gc-device-id``,
    ``gc-app-name``, and ``gc-app-version`` headers separately.

    Args:
        client_id: The GC client UUID (``gc-client-id`` header value).
        client_key_b64: Base64-encoded HMAC-SHA256 secret key (from .env).
        body: Request body as a JSON-compatible Python object.
        previous_signature_b64: Optional Base64-encoded previous response
            signature (the part after the dot in the server's ``gc-signature``
            response header).  Omit for standalone refresh calls.

    Returns:
        Dict with keys ``gc-signature``, ``gc-timestamp``, and ``gc-client-id``.
    """
    logger.debug("Generating gc-signature headers for POST /auth")

    timestamp = int(time.time())
    nonce_bytes = os.urandom(32)
    nonce_b64 = base64.b64encode(nonce_bytes).decode()

    hmac_digest = sign_payload(
        client_key_b64=client_key_b64,
        timestamp=timestamp,
        nonce_b64=nonce_b64,
        body=body,
        previous_signature_b64=previous_signature_b64,
    )

    gc_signature = f"{nonce_b64}.{hmac_digest}"

    return {
        "gc-signature": gc_signature,
        "gc-timestamp": str(timestamp),
        "gc-client-id": client_id,
    }
