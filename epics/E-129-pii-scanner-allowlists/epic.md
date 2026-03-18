<!-- synthetic-test-data -->
# E-129: PII Scanner Allowlists

## Status
`READY`

## Overview
The PII scanner blocks commits on obviously fake data -- RFC 2606 reserved-domain emails (`user@example.com`), PII-like terms in planning artifacts, and test fixtures. This epic adds targeted allowlists so the scanner stops crying wolf on safe patterns while continuing to catch real PII.

## Background & Context
The PII scanner (`src/safety/pii_scanner.py`) is hooked into the commit flow via `.claude/hooks/pii-check.sh` (PreToolUse on Bash tool for `git commit`). It scans staged files against four regex patterns (email, US phone, bearer token, API key assignment).

Current exclusion mechanisms:
- **SKIP_PATHS**: Path prefixes (`.git/`, `.claude/`, `node_modules/`, `requirements*.txt`)
- **SCANNABLE_EXTENSIONS**: Allowlisted file types (`.py`, `.json`, `.md`, etc.)
- **SYNTHETIC_MARKER**: Per-file `synthetic-test-data` marker in first 5 lines

The problem: `SKIP_PATHS` does not include `epics/` or `.project/` -- so story files and planning artifacts that reference PII-like patterns as examples trigger false positives. The email regex has no concept of RFC 2606 reserved domains, so `user@example.com` is flagged identically to a real email address. There is no inline suppression mechanism for individual lines.

**Expert consultation**: SE reviewed the scanner architecture (patterns in `pii_patterns.py`, scanner logic in `pii_scanner.py`, hook in `pii-check.sh`). No context-layer changes needed -- the hook passes through to the scanner unchanged. All modifications are in `src/safety/`.

## Goals
- RFC 2606 reserved-domain emails (`@example.com`, `@example.org`, `@example.net`, `@*.test`, `@*.example`, `@*.invalid`, `@*.localhost`) pass through the email pattern without triggering a finding
- Planning artifacts (`epics/`, `.project/`) are excluded from scanning
- Individual lines can be suppressed with an inline marker when needed
- All allowlist logic is tested

## Non-Goals
- Overhauling the scanner architecture or detection patterns
- Adding a `.pii-ignore` config file (premature -- inline suppression + path exclusions cover current needs)
- Pattern-specific path exclusions (e.g., skip `us_phone` only in migrations)
- Modifying the hook script or hook configuration

## Success Criteria
- A commit containing `user@example.com` in a `.py` file passes the PII scan
- A commit modifying a story file under `epics/` passes the PII scan
- A commit containing a real email address in a `.py` file is still caught
- The `# pii-ok` marker on a line suppresses that line's findings
- All new logic has test coverage

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-129-01 | RFC 2606 domain allowlist | TODO | None | - |
| E-129-02 | Path exclusions and inline suppression | TODO | E-129-01 | - |
| E-129-03 | Update safe data handling guide | TODO | None | - |

## Dispatch Team
- software-engineer
- docs-writer

## Technical Notes

### TN-1: RFC 2606 Reserved Domains
RFC 2606 reserves these domains for documentation and testing. Email addresses using them are never real:
- `example.com`, `example.org`, `example.net` (second-level -- match the domain itself and any subdomain, e.g., `sub.example.com`)
- `.test`, `.example`, `.invalid`, `.localhost` (top-level -- match any domain ending in these TLDs, e.g., `foo.test`, `bar.baz.example`)

Additionally, `localhost` (without TLD) should be treated as safe.

**Matching strategy**: Suffix matching. A domain is allowed if it equals or ends with a dot followed by any reserved domain entry. For example, `subdomain.example.org` matches because it ends with `.example.org`. This is safe because RFC 2606 reserves the entire subtree under each reserved domain.

The allowlist applies only to the `email` pattern. Other patterns (phone, bearer, API key) are unaffected.

### TN-2: Path Exclusion Additions
Add these prefixes to `SKIP_PATHS` in `pii_patterns.py`:
- `epics/` -- active epic and story files
- `.project/` -- archive, ideas, templates, research

These directories contain planning artifacts that frequently reference PII-like patterns as examples. The `.claude/` prefix is already excluded.

`docs/` is intentionally NOT excluded -- documentation could contain real PII if someone pastes it carelessly. Individual lines in docs can use inline suppression.

`tests/` is intentionally NOT excluded -- the existing `SYNTHETIC_MARKER` convention handles test fixtures. Inline suppression covers edge cases.

### TN-3: Inline Suppression Convention
A `# pii-ok` comment at the end of a line suppresses all findings on that line. The marker is language-agnostic (works in Python, YAML, shell, etc.). For HTML/XML where `#` isn't a comment character, use `<!-- pii-ok -->`.

This is analogous to `# noqa` in flake8 or `# type: ignore` in mypy.

### TN-4: No Hook Changes Required
The hook script (`.claude/hooks/pii-check.sh`) passes all logic to the scanner. All changes are in `src/safety/pii_patterns.py` (configuration) and `src/safety/pii_scanner.py` (logic). The hook remains untouched.

## Open Questions
None.

## History
- 2026-03-18: Created. SE and CA consulted on scanner architecture. Both confirmed no hook changes needed. CA recommended a `.pii-allowlist` config file with file:line:pattern granularity; SE recommended inline `# pii-ok` suppression. Decision: inline suppression (simpler, self-documenting, follows `# noqa` convention, no line-number brittleness). Config file deferred per "simple first" principle. Story 03 updated to modify existing `docs/safe-data-handling.md` rather than creating new file (git hook already references it).
- 2026-03-18: Codex spec review — 2 P1s, 2 P2s triaged. P1-1: E-129-02 now depends on E-129-01 (shared files: pii_scanner.py, test_pii_scanner.py). P1-2: Added AC-8 to E-129-02 for HTML `<!-- pii-ok -->` form. P2-3: Reworded epic Background/Goals to not imply docs/ is excluded. P2-4: Clarified TN-1 to specify suffix matching for subdomain support; aligned E-129-01 Technical Approach.
