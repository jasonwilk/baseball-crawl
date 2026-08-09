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
        "regex": (
            r'(?:api[_-]?key|secret[_-]?key|access[_-]?token|client[_-]?token'
            r'|refresh[_-]?token|device[_-]?id)'
            r'["\']?\s*[=:]\s*["\']?[^\s"\']{16,}'
        ),
        "description": "API key, secret, or token assignments with long quoted or unquoted values",
    },
]

# Credential patterns are compiled case-insensitively (F-H3): the project's own
# credential format is UPPERCASE env-var assignments (GC_ACCESS_TOKEN=...,
# GC_CLIENT_TOKEN=..., GC_REFRESH_TOKEN=..., GC_DEVICE_ID=...). Without
# re.IGNORECASE the key-name alternation only matched lowercase, so a pasted
# uppercase token passed clean. IGNORECASE is scoped to the credential regexes
# only -- the email/phone patterns are already case-neutral. The key-name
# broadening above is deliberately token-key-shaped (NOT a blanket \w+): the
# value side still requires [=:] plus a 16+ non-space value, so prose like
# "rotate the api_key" does not match. This STRENGTHENS the control
# (.claude/rules/pii-safety.md -- never weaken patterns).
_CASE_INSENSITIVE_PATTERNS: set[str] = {"bearer_token", "api_key_assignment"}

# Pre-compiled patterns for performance. Built once at module load time.
COMPILED_PATTERNS: list[dict[str, Any]] = [
    {
        "name": p["name"],
        "pattern": re.compile(
            p["regex"],
            re.IGNORECASE if p["name"] in _CASE_INSENSITIVE_PATTERNS else 0,
        ),
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

# Extensionless files to scan, matched on the LOWERCASED BASENAME. The
# extension allowlist above cannot reach these: a name with no dot has an empty
# suffix and does not start with "." either, so it was skipped outright as a
# "non-scannable extension" regardless of SKIP_PATHS. Two tracked files were
# affected -- `.githooks/pre-commit` (itself a PII gate) and `Dockerfile` (which
# the security checklist's 4h asks reviewers to check).
#
# ⚠ KNOWN LIMITATION, not a solved problem: a NEW extensionless file stays
# UNSCANNED until someone adds its basename here. A shebang test was considered
# and does NOT work -- `_scannability_skip_reason` runs BEFORE the content read
# on both paths (the `--staged` path reads its blob via `git show :<path>` only
# after the gate), so a shebang test would need the very read it gates, and
# `Dockerfile` has no shebang at all.
SCANNABLE_BASENAMES: set[str] = {
    "dockerfile",
    "pre-commit",
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

# Exact-match allowlist for known placeholder email addresses that appear in
# documentation, admin guides, and template text. These are never real contact
# information and should not require per-line pii-ok markers.
#
# Matching rule: normalize to lowercase, then check set membership.
# Scope: seed list only -- do not add entries without a clear justification.
PLACEHOLDER_EMAILS: frozenset[str] = frozenset({
    "your@email.com",        # generic template in onboarding docs
    "user@email.com",        # generic template in onboarding docs
    "user@domain.com",       # template placeholder in admin docs
    "admin@domain.com",      # template placeholder in admin docs
    "admin@yourcompany.com", # template placeholder in admin docs
    "info@yourcompany.com",  # template placeholder in admin docs
    "user@yourdomain.com",   # template placeholder in admin docs
    "admin@yourdomain.com",  # template placeholder in admin docs
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
    # Planning artifacts reference PII-like patterns as examples; scanning them
    # produces only noise. (TN-2) Measured 2026-08-02 with the skip lifted: 43
    # such matches across 15 files -- API-spec key assignments, 10-digit runs
    # reading as phone numbers -- so the noise is real and these stay skipped.
    "epics/",
    ".project/archive/", ".project/ideas/",
    ".project/research/", ".project/templates/",
    # `.project/` itself is NOT skipped, so `.project/specs/` -- the unit of
    # work under the spec-based flow -- is scanned before it is committed.
    # This buys credential/email/phone coverage there and NOTHING against
    # NAMES, which remains the real gap in planning artifacts (IDEA-102).
    # pip-compile generated lockfiles contain SHA256 hashes that trigger
    # the us_phone pattern (10-digit sequences inside hex strings).
    "requirements.txt",
    "requirements-dev.txt",
}
