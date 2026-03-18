<!-- synthetic-test-data -->
# E-129-02: Path Exclusions and Inline Suppression

## Epic
[E-129: PII Scanner Allowlists](epic.md)

## Status
`TODO`

## Description
After this story is complete, planning artifacts under `epics/` and `.project/` will be excluded from PII scanning, and individual lines in any scanned file can be suppressed with an inline `# pii-ok` marker. This eliminates false positives from story files that reference PII-like patterns as examples and provides an escape hatch for edge cases in any file.

## Context
Story files, idea files, and templates frequently reference PII-like patterns when describing PII-related features (e.g., "the scanner should catch emails like `user@example.com`"). These are planning artifacts, not application code. The existing `SKIP_PATHS` mechanism already excludes `.git/`, `.claude/`, and `node_modules/` -- this story extends it to planning directories.

The inline suppression mechanism (`# pii-ok`) follows the established convention of `# noqa` (flake8) and `# type: ignore` (mypy). It provides per-line granularity without requiring entire files to be excluded or marked with the `synthetic-test-data` header.

## Acceptance Criteria
- [ ] **AC-1**: Given a staged file at `epics/E-129-pii-scanner-allowlists/E-129-01-rfc2606-domain-allowlist.md` containing `jason@realdomain.com`, when the PII scanner runs with `--staged`, then no finding is reported (file is skipped by path)
- [ ] **AC-2**: Given a staged file at `.project/ideas/IDEA-042-foo.md` containing an email address, when the PII scanner runs, then no finding is reported (file is skipped by path)
- [ ] **AC-3**: Given a staged `.py` file containing `email = "jason@real.com"  # pii-ok`, when the PII scanner runs, then no finding is reported for that line
- [ ] **AC-4**: Given a staged `.py` file containing `email = "jason@real.com"` (no suppression marker), when the PII scanner runs, then a finding IS reported
- [ ] **AC-5**: The `SKIP_PATHS` additions include `epics/` and `.project/` per TN-2
- [ ] **AC-6**: The inline suppression marker convention follows TN-3 (`# pii-ok` suffix)
- [ ] **AC-7**: Unit tests cover path exclusion for both new prefixes and inline suppression for both suppressed and unsuppressed lines (including HTML form)
- [ ] **AC-8**: Given a staged `.html` file containing `<!-- pii-ok -->` on a line with a PII match, when the PII scanner runs, then no finding is reported for that line (HTML suppression form per TN-3)

## Technical Approach
Path exclusions: add entries to the existing `SKIP_PATHS` set in `pii_patterns.py`. The scanner already iterates this set for prefix matching -- no logic changes needed in the scanner for this part.

Inline suppression: in the scanner's line-scanning loop (in `pii_scanner.py`), check if the line contains the suppression marker before reporting a finding. The check should be case-sensitive and match the marker as a substring (accommodating both `# pii-ok` and `<!-- pii-ok -->`).

## Dependencies
- **Blocked by**: E-129-01 (shared files: `pii_scanner.py`, `test_pii_scanner.py`)
- **Blocks**: None

## Files to Create or Modify
- `src/safety/pii_patterns.py` -- add `epics/`, `.project/` to `SKIP_PATHS`; add `PII_OK_MARKER` constant
- `src/safety/pii_scanner.py` -- add inline suppression check in scan loop
- `tests/test_pii_scanner.py` -- add tests for path exclusions and inline suppression

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
