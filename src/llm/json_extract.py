"""Model-agnostic JSON extraction from raw LLM ``content`` strings.

Capable models emit JSON in a handful of real-world shapes despite prompt
instructions: bare, fenced in a ```json``` block, fenced without a language
tag, or wrapped in leading/trailing prose.  :func:`extract_json_object`
recovers a ``dict`` from all of these, and raises :class:`LLMError` on input
it cannot recover (prose-only, empty, ``None``, truncated/mid-object JSON) so
callers need no error mapping and the Tier-1 fallback path still fires.

This module is pure: no HTTP, no environment access.  It owns *extraction*
only -- domain validation (presence/type of ``narrative``,
``bullpen_sequence``) stays in ``enrich_prediction``.
"""

from __future__ import annotations

import json
from collections.abc import Iterator

from src.llm.openrouter import LLMError


def _strip_code_fence(text: str) -> str:
    """Remove a surrounding markdown code fence, if present.

    Handles ```` ```json ... ``` ```` and ```` ``` ... ``` ```` by taking the
    content between the first opening fence and the last closing fence.  If no
    fence is present the text is returned unchanged.
    """
    if "```" not in text:
        return text

    fence_start = text.find("```")
    after_open = text[fence_start + 3 :]

    # Drop an optional language tag (e.g. ``json``) on the opening fence line.
    newline = after_open.find("\n")
    if newline != -1:
        first_line = after_open[:newline].strip()
        if first_line == "" or first_line.isalpha():
            after_open = after_open[newline + 1 :]

    fence_end = after_open.rfind("```")
    if fence_end != -1:
        after_open = after_open[:fence_end]

    return after_open


def _iter_json_object_candidates(text: str) -> Iterator[str]:
    """Yield each top-level balanced ``{...}`` substring, left to right.

    Brace matching is string-aware: ``{`` / ``}`` characters inside a JSON
    string literal (e.g. inside narrative text) do not affect the balance, and
    escaped quotes within strings are honored.  Each candidate begins at a
    top-level ``{`` (depth 0, outside any string) and ends at its matching
    ``}``; an unterminated object at end-of-text yields nothing.  Yielding
    successive candidates lets the caller trial-parse and skip earlier
    fragments -- e.g. leading prose that itself contains braces -- before the
    real object.
    """
    depth = 0
    in_string = False
    escaped = False
    start = -1
    for index, char in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}":
            if depth > 0:
                depth -= 1
                if depth == 0:
                    yield text[start : index + 1]


def extract_json_object(content: str) -> dict:
    """Extract a JSON object (``dict``) from a raw LLM ``content`` string.

    Recovers JSON from bare, fenced (with or without a language tag), and
    prose-wrapped responses.  Performs no HTTP and no environment access.

    Args:
        content: The raw ``content`` string returned by the model.

    Returns:
        The parsed JSON object as a ``dict``.

    Raises:
        LLMError: If ``content`` is not a non-empty string, contains no
            recoverable JSON object, or the recovered object does not parse to
            a ``dict``.
    """
    if not isinstance(content, str):
        raise LLMError(
            f"LLM content is not a string (got {type(content).__name__})"
        )

    stripped = content.strip()
    if not stripped:
        raise LLMError("LLM content is empty")

    candidate_text = _strip_code_fence(stripped).strip()

    # Trial-parse each balanced {...} candidate left to right, returning the
    # first that parses to a dict.  This advances past leading prose fragments
    # that themselves contain braces (e.g. "Use {a,b}:\n{...}") before reaching
    # the real object -- TN-1's blessed "trial-parsing trimmed candidates".
    found_candidate = False
    last_error: Exception | None = None
    for json_text in _iter_json_object_candidates(candidate_text):
        found_candidate = True
        try:
            parsed = json.loads(json_text)
        except (ValueError, TypeError) as exc:
            last_error = exc
            continue
        if isinstance(parsed, dict):
            return parsed
        # A balanced {...} always parses to a dict; guard defensively anyway.
        last_error = ValueError(
            f"candidate did not parse to a JSON object "
            f"(got {type(parsed).__name__})"
        )

    if not found_candidate:
        raise LLMError("No balanced JSON object found in LLM content")
    raise LLMError(f"Failed to parse JSON from LLM content: {last_error}")
