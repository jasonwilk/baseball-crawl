# E-144: PII Scanner Placeholder Email Allowlist

## Status
`COMPLETED`

## Overview
The PII scanner flags common placeholder email addresses (e.g., `your@email.com`, `user@domain.com`) as real PII, forcing authors to add manual `pii-ok` markers to documentation. This epic adds an exact-match placeholder email allowlist so that unambiguously fake emails pass the scanner automatically.

## Background & Context
During E-143, `docs/admin/operations.md` contained `your@email.com` in a SQL example and was blocked by the pre-commit hook. The scanner's RFC 2606 domain allowlist (`example.com`, `.test`, etc.) correctly handles reserved domains, but common placeholder patterns use real registerable domains (`email.com`, `domain.com`, `yourcompany.com`) that are not in the RFC 2606 set.

The existing escape mechanisms (`pii-ok` inline marker, `synthetic-test-data` file marker) work but require manual intervention that is easy to forget and clutters documentation files.

**SE consultation** (2026-03-21): SE recommended Option 2 (exact full-email allowlist) over Option 1 (domain-level allowlist). Rationale: `email.com` and `domain.com` are real live domains where real people have accounts. A domain-level allowlist would silently suppress real leaks. Exact-match is more conservative -- only unambiguously fake addresses are allowlisted. The `pii-ok` marker remains the escape hatch for anything not on the list. No pre-commit hook changes needed (the hook calls the scanner as a subprocess transparently).

## Goals
- Placeholder emails in documentation pass the PII scanner without manual `pii-ok` markers
- The allowlist is conservative: only unambiguously fake email addresses are included
- Existing RFC 2606 domain filtering continues to work unchanged

## Non-Goals
- Domain-level allowlisting of non-RFC-2606 domains (too risky for false negatives)
- Heuristic or regex-based placeholder detection (too complex, hard to audit)
- Removing the `pii-ok` inline marker mechanism (still needed for edge cases)

## Success Criteria
- `your@email.com`, `user@domain.com`, and other seeded placeholder emails produce zero violations when scanned
- A similar-but-not-listed email (e.g., `me@domain.com`) still gets flagged
- All existing PII scanner tests continue to pass
- The `pii-ok` marker and RFC 2606 allowlist still work as before

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-144-01 | Add placeholder email allowlist and tests | DONE | None | SE |
| E-144-02 | Update .env.example auth comments for post-E-143 behavior | DONE | None | SE |

## Dispatch Team
- software-engineer

## Technical Notes

### TN-1: Allowlist Design
The allowlist is a `PLACEHOLDER_EMAILS: frozenset[str]` constant in `src/safety/pii_patterns.py`, containing exact lowercase full-email addresses. Matching is case-insensitive (normalize to lowercase before lookup).

**Seed list** (known false positives from documentation):
- `your@email.com`, `user@email.com`
- `user@domain.com`, `admin@domain.com`
- `admin@yourcompany.com`, `info@yourcompany.com`
- `user@yourdomain.com`, `admin@yourdomain.com`

Each entry should have a brief inline comment explaining why it is there (e.g., "template placeholder in admin docs"). This deters allowlist sprawl.

**Scope constraint**: The allowlist MUST contain exactly the seed entries listed above and no others. Adding entries requires a deliberate decision (new story or epic), not ad-hoc expansion during implementation.

### TN-4: Self-Hosting Note
`src/safety/pii_patterns.py` already contains the `synthetic-test-data` marker on line 2 of its module docstring. The scanner's `has_synthetic_marker()` check skips the entire file before pattern matching. This means the literal email strings inside `PLACEHOLDER_EMAILS` will NOT trigger the scanner. Do NOT add redundant `pii-ok` markers to the frozenset lines.

### TN-2: Integration Point
The check integrates into `scan_file()` in `src/safety/pii_scanner.py` alongside the existing `is_rfc2606_email()` check. The existing function is NOT renamed (it is imported directly in tests). A new `is_placeholder_email()` function handles the exact-match check. The condition in `scan_file()` becomes an `or` of both checks.

### TN-3: Test Strategy
Tests go in a new `TestPlaceholderEmailAllowlist` class in `tests/test_pii_scanner.py`, mirroring the existing `TestRfc2606DomainAllowlist` class structure. Coverage:
- Each seeded placeholder email produces no violations via `scan_file()`
- A similar-but-not-listed email (e.g., `me@domain.com`) still gets flagged (regression guard)
- The `is_placeholder_email()` function works case-insensitively

## Open Questions
None -- SE consultation resolved the approach question.

## History
- 2026-03-21: Created. SE consulted on approach; recommended exact-match allowlist (Option 2).
- 2026-03-21: Spec review complete. 2 findings accepted and incorporated: (1) self-hosting dependency documented in TN-4 (pre-mitigated by existing `synthetic-test-data` marker), (2) AC-1 tightened to "exactly the seed entries" with scope constraint added to TN-1. Consistency sweep clean. Status set to READY.
- 2026-03-21: Added E-144-02 (update `.env.example` auth comments for post-E-143 behavior). Stale comments for `ADMIN_EMAIL` and `DEV_USER_EMAIL` need to reflect the current auth model.
- 2026-03-21: Dispatch started. Epic set to ACTIVE. E-144-01 assigned to SE.
- 2026-03-21: All stories implemented and reviewed. Codex found 1 P2 (missing allowlist content assertion) -- remediated. Integration CR clean. Epic COMPLETED.
- **Documentation assessment**: No triggers fired. PII scanner internals only; .env.example comments updated as part of the epic. No user-facing doc changes needed.
- **Context-layer assessment**:
  - New convention or workflow pattern: NO
  - Architectural decision worth codifying: NO
  - Footgun or subtle constraint discovered: NO
  - Agent definition or routing change: NO
  - Domain knowledge worth preserving: NO
  - CLI or operator interface change: NO
