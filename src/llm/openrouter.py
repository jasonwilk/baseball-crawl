"""Reusable OpenRouter HTTP client.

Sends chat completion requests to the OpenRouter API.  Uses ``httpx``
directly -- this is a documented exception to the project HTTP discipline
rule (``create_session()`` is for the GameChanger API, not standard APIs).

Environment variables:
    OPENROUTER_API_KEY   Required for LLM requests.  Absence is detected
                         by ``is_llm_available()`` so callers can skip
                         Tier 2 silently.
    OPENROUTER_MODEL     Optional model override.  Defaults to
                         ``anthropic/claude-haiku-4-5-20251001``.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_DEFAULT_MODEL = "anthropic/claude-haiku-4-5-20251001"
_TIMEOUT_SECONDS = 30


class LLMError(Exception):
    """Raised when an LLM request fails or returns an unusable response."""


def is_llm_available() -> bool:
    """Return True if ``OPENROUTER_API_KEY`` is set in the environment."""
    return bool(os.environ.get("OPENROUTER_API_KEY"))


def query_openrouter(
    messages: list[dict[str, str]],
    model: str | None = None,
    max_tokens: int = 1024,
    temperature: float = 0.3,
) -> dict[str, Any]:
    """Send a chat completion request to OpenRouter.

    Args:
        messages: Chat messages in OpenAI format
            (``[{"role": "system", "content": "..."}, ...]``).
        model: Model identifier.  Defaults to ``OPENROUTER_MODEL`` env var,
            then ``anthropic/claude-haiku-4-5-20251001``.
        max_tokens: Maximum tokens in the response.
        temperature: Sampling temperature.

    Returns:
        Parsed JSON response body from OpenRouter.

    Raises:
        LLMError: On missing API key, HTTP errors, or timeouts.
    """
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise LLMError("OPENROUTER_API_KEY is not set")

    resolved_model = model or os.environ.get("OPENROUTER_MODEL", _DEFAULT_MODEL)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": resolved_model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    try:
        with httpx.Client(timeout=_TIMEOUT_SECONDS) as client:
            response = client.post(_OPENROUTER_URL, headers=headers, json=body)
    except httpx.TimeoutException as exc:
        raise LLMError(f"OpenRouter request timed out: {exc}") from exc
    except httpx.HTTPError as exc:
        raise LLMError(f"OpenRouter request failed: {exc}") from exc

    if response.status_code == 401:
        raise LLMError("OpenRouter authentication failed (401)")
    if response.status_code == 429:
        raise LLMError("OpenRouter rate limit exceeded (429)")
    if response.status_code >= 400:
        raise LLMError(
            f"OpenRouter returned HTTP {response.status_code}: "
            f"{response.text[:200]}"
        )

    try:
        return response.json()
    except ValueError as exc:
        raise LLMError(f"OpenRouter returned invalid JSON: {exc}") from exc
