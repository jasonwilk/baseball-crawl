"""Parse GameChanger curl commands and extract authentication credentials.

Accepts a raw curl command string (copied from browser dev tools), tokenises it
with ``shlex.split()``, and extracts the headers and URL that carry persistent
auth credentials.  The output is a flat ``dict[str, str]`` mapping .env key
names to values -- ready to be merged into a ``.env`` file.

Header-to-.env key mapping (curl-paste path is web-only):
    gc-token        -> GAMECHANGER_REFRESH_TOKEN_WEB    (primary JWT, required)
    gc-device-id    -> GAMECHANGER_DEVICE_ID_WEB
    gc-app-name     -> GAMECHANGER_APP_NAME_WEB
    Cookie / -b     -> GAMECHANGER_COOKIE_<NAME> (one entry per cookie)
    URL (base)      -> GAMECHANGER_BASE_URL

Headers that are skipped (per-request, not persistent credentials):
    gc-user-action-id, gc-user-action, x-pagination, and all standard
    browser headers (User-Agent, Accept, Referer, sec-ch-ua-*, DNT, etc.)
"""

from __future__ import annotations

import logging
import shlex
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Headers that carry persistent credentials and the .env key to store them under.
# The curl-paste path is inherently web-only, so keys use the _WEB suffix.
_CREDENTIAL_HEADERS: dict[str, str] = {
    "gc-token": "GAMECHANGER_REFRESH_TOKEN_WEB",
    "gc-device-id": "GAMECHANGER_DEVICE_ID_WEB",
    "gc-app-name": "GAMECHANGER_APP_NAME_WEB",
}

# Headers that should be silently skipped (per-request, not credentials).
_SKIP_HEADERS: frozenset[str] = frozenset(
    {
        "gc-user-action-id",
        "gc-user-action",
        "x-pagination",
        # Standard browser headers handled by src/http/
        "user-agent",
        "accept",
        "accept-language",
        "accept-encoding",
        "referer",
        "origin",
        "dnt",
        "content-type",
        "sec-ch-ua",
        "sec-ch-ua-mobile",
        "sec-ch-ua-platform",
        "sec-fetch-site",
        "sec-fetch-mode",
        "sec-fetch-dest",
        "connection",
    }
)


class CurlParseError(ValueError):
    """Raised when the curl command is malformed or missing required credentials."""


def parse_curl(curl_command: str) -> dict[str, str]:
    """Parse a raw curl command string and return extracted credentials as a dict.

    The returned dict maps .env variable names to their values.  At minimum,
    ``GAMECHANGER_REFRESH_TOKEN_WEB`` and ``GAMECHANGER_BASE_URL`` are required; the
    function raises ``CurlParseError`` if either is absent.

    Args:
        curl_command: The full curl command string, including the ``curl`` prefix,
            as copied from browser dev tools (may span multiple lines with
            backslash continuations).

    Returns:
        A dict mapping .env key names to credential values.

    Raises:
        CurlParseError: If the input is not a curl command, is missing the
            required ``gc-token`` auth header, or is otherwise unparseable.
    """
    curl_command = curl_command.strip()
    if not curl_command:
        raise CurlParseError("Empty curl command.")

    # shlex.split handles backslash-newline continuations and quoted strings.
    try:
        tokens = shlex.split(curl_command)
    except ValueError as exc:
        raise CurlParseError(f"Could not tokenise curl command: {exc}") from exc

    if not tokens or tokens[0].lower() != "curl":
        raise CurlParseError(
            "Input does not appear to be a curl command "
            "(must start with 'curl')."
        )

    url: str | None = None
    credentials: dict[str, str] = {}
    i = 1
    while i < len(tokens):
        token = tokens[i]

        # -H / --header
        if token in ("-H", "--header"):
            if i + 1 >= len(tokens):
                raise CurlParseError(
                    f"Flag {token!r} at position {i} is missing its value."
                )
            header_raw = tokens[i + 1]
            _process_header(header_raw, credentials)
            i += 2
            continue

        # -b / --cookie (cookie string not in a -H Cookie: header)
        if token in ("-b", "--cookie"):
            if i + 1 >= len(tokens):
                raise CurlParseError(
                    f"Flag {token!r} at position {i} is missing its value."
                )
            cookie_str = tokens[i + 1]
            _extract_cookies(cookie_str, credentials)
            i += 2
            continue

        # Flags with values that we do not care about -- skip both tokens.
        if token in (
            "-X", "--request",
            "-d", "--data", "--data-raw", "--data-binary",
            "-u", "--user",
            "-o", "--output",
            "--max-time", "--connect-timeout",
            "--cacert", "--cert", "--key",
            "-A", "--user-agent",
            "-e", "--referer",
        ):
            i += 2
            continue

        # Boolean flags -- skip single token.
        if token.startswith("-") and "=" not in token:
            # If the next token looks like a value (doesn't start with -), consume it.
            # This is a best-effort heuristic for unknown flags.
            if i + 1 < len(tokens) and not tokens[i + 1].startswith("-"):
                i += 2
            else:
                i += 1
            continue

        # Positional argument: the URL (first non-flag token after 'curl').
        if not token.startswith("-") and url is None:
            url = token
            i += 1
            continue

        i += 1

    if url is None:
        raise CurlParseError(
            "No URL found in curl command.  "
            "Expected a positional URL argument after 'curl'."
        )

    # Extract base URL (scheme + host only).
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise CurlParseError(
            f"URL {url!r} could not be parsed into a valid scheme + host."
        )
    credentials["GAMECHANGER_BASE_URL"] = f"{parsed.scheme}://{parsed.netloc}"

    # Enforce that the primary auth credential is present.
    if "GAMECHANGER_REFRESH_TOKEN_WEB" not in credentials:
        raise CurlParseError(
            "Required credential 'gc-token' header not found in curl command.\n"
            "Make sure you are copying the full curl command from the GameChanger "
            "network request in browser dev tools (Network tab -> right-click "
            "request -> Copy as cURL)."
        )

    logger.debug("Parsed credentials: %s", sorted(credentials.keys()))
    return credentials


def _process_header(header_raw: str, credentials: dict[str, str]) -> None:
    """Parse a single ``Name: Value`` header string and update *credentials*.

    Args:
        header_raw: The raw header string, e.g. ``'gc-token: eyJ...'``.
        credentials: The dict to update in-place.
    """
    if ":" not in header_raw:
        logger.debug("Skipping malformed header (no colon): %r", header_raw)
        return

    name, _, value = header_raw.partition(":")
    name = name.strip()
    value = value.strip()
    name_lower = name.lower()

    # Cookie header (e.g., ``Cookie: a=b; c=d``)
    if name_lower == "cookie":
        _extract_cookies(value, credentials)
        return

    # Credential headers with an explicit mapping.
    if name_lower in _CREDENTIAL_HEADERS:
        env_key = _CREDENTIAL_HEADERS[name_lower]
        credentials[env_key] = value
        logger.debug("Extracted %s from header %r", env_key, name)
        return

    # Known skip list -- silently ignore.
    if name_lower in _SKIP_HEADERS:
        return

    # Unknown headers -- log and skip (do not store; not a credential).
    logger.debug("Ignoring unrecognised header: %r", name)


def _extract_cookies(cookie_str: str, credentials: dict[str, str]) -> None:
    """Parse a ``name=value; name2=value2`` cookie string into .env entries.

    Each cookie becomes ``GAMECHANGER_COOKIE_<NAME>=<value>``.

    Args:
        cookie_str: The cookie string to parse.
        credentials: The dict to update in-place.
    """
    for pair in cookie_str.split(";"):
        pair = pair.strip()
        if not pair:
            continue
        if "=" in pair:
            cname, _, cvalue = pair.partition("=")
            cname = cname.strip()
            cvalue = cvalue.strip()
        else:
            cname = pair
            cvalue = ""
        env_key = f"GAMECHANGER_COOKIE_{cname.upper().replace('-', '_')}"
        credentials[env_key] = cvalue
        logger.debug("Extracted cookie %r -> %s", cname, env_key)


def _build_merged_lines(env_path: str, new_values: dict[str, str]) -> list[str]:
    """Read an existing .env file and return merged lines with *new_values* applied.

    Existing keys present in *new_values* are updated in place.  New keys are
    appended.  Lines starting with ``#`` and blank lines are preserved unchanged.

    Args:
        env_path: Absolute path to the .env file (may not exist yet).
        new_values: New credential key-value pairs to merge in.

    Returns:
        List of merged lines (each ending with ``\\n``).
    """
    from pathlib import Path

    path = Path(env_path)
    existing_lines: list[str] = []
    existing_keys: dict[str, int] = {}  # key -> line index

    if path.exists():
        with path.open("r", encoding="utf-8") as fh:
            existing_lines = fh.readlines()
        for idx, line in enumerate(existing_lines):
            stripped = line.rstrip("\n")
            if stripped.startswith("#") or not stripped.strip():
                continue
            if "=" in stripped:
                key, _, _ = stripped.partition("=")
                existing_keys[key.strip()] = idx

    # Update lines in place for existing keys; append new ones.
    for key, value in new_values.items():
        if key in existing_keys:
            existing_lines[existing_keys[key]] = f"{key}={value}\n"
        else:
            existing_lines.append(f"{key}={value}\n")

    return existing_lines


def merge_env_file(env_path: str, new_values: dict[str, str]) -> dict[str, str]:
    """Read an existing .env file, merge new values, write it back, and return the merged dict.

    Existing keys that are NOT present in *new_values* are preserved unchanged.
    Keys present in *new_values* overwrite existing values.  New keys are
    appended.  The updated content is written back to *env_path*.

    The .env file format is simple ``KEY=VALUE`` lines.  Lines starting with
    ``#`` are treated as comments and preserved.  Blank lines are preserved.

    Args:
        env_path: Absolute path to the .env file (may not exist yet).
        new_values: New credential key-value pairs to merge in.

    Returns:
        The merged dict (existing non-credential keys + new values).
    """
    from pathlib import Path

    merged_lines = _build_merged_lines(env_path, new_values)

    # Write the merged content back to disk.
    with Path(env_path).open("w", encoding="utf-8") as fh:
        fh.writelines(merged_lines)

    # Reconstruct merged dict for the caller (used for confirmation output).
    merged: dict[str, str] = {}
    for line in merged_lines:
        stripped = line.rstrip("\n")
        if stripped.startswith("#") or not stripped.strip():
            continue
        if "=" in stripped:
            k, _, v = stripped.partition("=")
            merged[k.strip()] = v

    return merged


def atomic_merge_env_file(env_path: str, new_values: dict[str, str]) -> dict[str, str]:
    """Read an existing .env file, merge new values, and write back atomically.

    Identical to ``merge_env_file()`` in merge semantics, but uses a temporary
    file and ``os.replace()`` for the write step.  This prevents data loss if
    the process crashes mid-write -- the original file is left intact until the
    rename succeeds.

    Use this function wherever write-back failure could be catastrophic (e.g.,
    persisting a rotated refresh token that has already been invalidated
    server-side).

    Args:
        env_path: Absolute path to the .env file (may not exist yet).
        new_values: New credential key-value pairs to merge in.

    Returns:
        The merged dict (existing non-credential keys + new values).

    Raises:
        OSError: If the temporary file cannot be written or the rename fails.
            Callers should catch this and handle gracefully (e.g., log warning).
    """
    import os
    import tempfile
    from pathlib import Path

    merged_lines = _build_merged_lines(env_path, new_values)

    env_dir = str(Path(env_path).parent)
    fd, tmp_path = tempfile.mkstemp(dir=env_dir, prefix=".env.tmp.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.writelines(merged_lines)
        os.replace(tmp_path, env_path)
    except Exception:
        # Clean up the temp file if rename failed.
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    # Reconstruct merged dict for the caller.
    merged: dict[str, str] = {}
    for line in merged_lines:
        stripped = line.rstrip("\n")
        if stripped.startswith("#") or not stripped.strip():
            continue
        if "=" in stripped:
            k, _, v = stripped.partition("=")
            merged[k.strip()] = v

    return merged
