"""Shared exception types for the GameChanger client stack.

Defined in a standalone module to avoid circular imports between
``client.py`` and ``token_manager.py``.
"""

from __future__ import annotations


class ConfigurationError(Exception):
    """Raised when required environment variables are missing or invalid."""


class CredentialExpiredError(Exception):
    """Raised when the API returns 401 (token has expired or is invalid)."""


class ForbiddenError(CredentialExpiredError):
    """Raised when the API returns 403 (per-resource access denial).

    Subclass of ``CredentialExpiredError`` for backward compatibility -- existing
    ``except CredentialExpiredError`` clauses will still catch 403 responses.
    Use ``except ForbiddenError`` before ``except CredentialExpiredError`` to
    distinguish per-resource denial from token expiry.
    """


class RateLimitError(Exception):
    """Raised when the API returns 429 (rate limit hit)."""


class GameChangerAPIError(Exception):
    """Raised when the API returns a 5xx error after all retries are exhausted."""
