"""
synthetic-test-data
Sensitive data detection patterns for baseball-crawl.

This module serves as the PII and credential taxonomy for the project.
Patterns are stored as Python constants -- NOT YAML -- to keep the scanner
stdlib-only with zero external dependencies.

PII categories (why each is sensitive in this context):

- **Email addresses**: Coach, parent, and player contact info appears in
  GameChanger API responses. Any email address in a committed file is likely
  real contact information.

- **US phone numbers**: Coach and parent phone numbers appear in GameChanger
  team and roster data. Common formats: (555) 867-5309, 555-867-5309,
  555.867.5309, +1-555-867-5309. May produce occasional false positives on
  10-digit number sequences -- this is acceptable.

- **Full names**: Full names ARE PII but are NOT detected by regex. Name
  patterns are too unreliable (high false positive rate on common words).
  Names are protected by the /ephemeral/ directory convention instead --
  any file containing real names from API responses goes in /ephemeral/,
  which is gitignored.

- **GameChanger user IDs**: These are PII because they resolve to real
  people via the API. However, they are opaque strings with no scannable
  pattern. Like names, they are protected by the /ephemeral/ convention.

Credential categories:

- **Bearer tokens**: GameChanger API auth headers (Authorization: Bearer ...).
  These are short-lived but must never enter Git history.

- **API key assignments**: Common patterns like api_key = "sk-...",
  secret_key: "abc123...", access_token = "...". Catches most hardcoded
  secrets in code and config files.

Pre-compiled patterns are available via COMPILED_PATTERNS for performance.
"""

import re
from typing import Any

# Pattern definitions -- each dict has name, regex, and description.
# Regexes are strings here; compiled versions are in COMPILED_PATTERNS below.
PATTERNS: list[dict[str, str]] = [
    # PII patterns
    {
        "name": "email",
        "regex": r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
        "description": "Email addresses",
    },
    {
        "name": "us_phone",
        "regex": r'(?<!\d)(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}(?!\d)',
        "description": "US phone numbers in common formats",
    },
    # Credential patterns
    {
        "name": "bearer_token",
        "regex": r'[Bb]earer\s+[A-Za-z0-9\-._~+/]+=*',
        "description": "Bearer authorization tokens",
    },
    {
        "name": "api_key_assignment",
        "regex": r'(?:api[_-]?key|secret[_-]?key|access[_-]?token)["\']?\s*[=:]\s*["\']?[^\s"\']{16,}',
        "description": "API key or secret assignments with long quoted or unquoted values",
    },
]

# Pre-compiled patterns for performance. Built once at module load time.
COMPILED_PATTERNS: list[dict[str, Any]] = [
    {
        "name": p["name"],
        "pattern": re.compile(p["regex"]),
        "description": p["description"],
    }
    for p in PATTERNS
]

# Synthetic data annotation that exempts a file from scanning.
# If this string appears anywhere in the first 5 lines of a file, the entire
# file is skipped. Case-sensitive. This is the canonical convention.
SYNTHETIC_MARKER: str = "synthetic-test-data"

# File extensions to scan (allowlist). Files with extensions not in this set
# are skipped without being read. This avoids reading binary files.
SCANNABLE_EXTENSIONS: set[str] = {
    ".py", ".json", ".yaml", ".yml", ".md", ".txt",
    ".csv", ".toml", ".cfg", ".ini", ".html", ".xml",
    ".env", ".sh", ".bash",
}

# RFC 2606 reserved domain allowlist for email filtering.
# Email addresses using these domains are never real and are excluded from
# findings. See TN-1 in the E-129 epic for matching strategy details.
#
# Matching rule: a domain is allowed if it equals any entry (after stripping
# a leading dot) or ends with "." + entry (after stripping a leading dot).
# Examples:
#   "example.com"  → allows example.com, sub.example.com
#   ".test"        → allows foo.test, bar.baz.test
#   "localhost"    → allows localhost, foo.localhost
RFC2606_DOMAINS: frozenset[str] = frozenset({
    # Second-level reserved domains (RFC 2606 §3)
    "example.com",
    "example.org",
    "example.net",
    # Reserved TLDs (RFC 2606 §2) -- leading dot signals TLD-only entries
    ".test",
    ".example",
    ".invalid",
    ".localhost",
    # Bare hostname
    "localhost",
})

# Inline suppression marker. A line containing this string (as a substring,
# case-sensitive) is excluded from all findings on that line. Language-agnostic:
# works in Python, YAML, shell, etc. (`# pii-ok`). For HTML/XML where `#` is
# not a comment character, use `<!-- pii-ok -->` -- both are caught by the same
# substring check.
PII_OK_MARKER: str = "pii-ok"

# Path prefixes to always skip, relative to repo root. Any file whose path
# starts with one of these prefixes is skipped without being read.
SKIP_PATHS: set[str] = {
    ".git/", ".claude/", "node_modules/", "__pycache__/",
    # Planning artifacts -- story and idea files frequently reference PII-like
    # patterns as examples; scanning them produces only noise. (TN-2)
    "epics/", ".project/",
    # pip-compile generated lockfiles contain SHA256 hashes that trigger
    # the us_phone pattern (10-digit sequences inside hex strings).
    "requirements.txt",
    "requirements-dev.txt",
}
