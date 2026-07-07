# E-254-06: PII scanner: case-insensitive patterns + staged-blob scanning (F-H3)

## Epic
[E-254: Security & PII Hardening](epic.md)

## Status
`DONE`

## Description
After this story is complete, the PII scanner detects the project's own UPPERCASE credential-assignment format (F-H3), and in `--staged` mode it scans the actual staged blob content rather than the working-tree bytes — closing the two holes that let a pasted `GC_ACCESS_TOKEN=eyJ…` commit with "[pii-scan] … 0 violations".

## Context
The PII scanner is the sole enforcement behind "credentials MUST NEVER appear in commit history," and it has two holes:
- **F-H3 (HIGH)** (`src/safety/pii_patterns.py`, `COMPILED_PATTERNS` build 73-79): patterns compile case-sensitively, and the `api_key_assignment` pattern only matches lowercase `api_key`/`secret_key`/`access_token` key names. The project's own credential format is UPPERCASE env-var assignments (`GC_ACCESS_TOKEN=…`, `GC_CLIENT_TOKEN=…`), which pass clean end-to-end.
- **Staged-blob gap** (`src/safety/pii_scanner.py`, `scan_file` reads the path ~139-141; `--staged` at 201-217): `--staged` reads working-tree bytes, not the staged blob — so a token can be staged, the working tree cleaned, and the commit still leaks. Staged-but-deleted files are also silently mis-handled.

This is a security control (`.claude/rules/pii-safety.md`); this work STRENGTHENS it (does not weaken patterns or add blanket exclusions). See Technical Notes TN-5 and TN-6.

## Acceptance Criteria
- [ ] **AC-1**: Given a file containing an UPPERCASE credential assignment for each of `GC_ACCESS_TOKEN`, `GC_CLIENT_TOKEN`, `GC_REFRESH_TOKEN`, and `GC_DEVICE_ID` (with a realistic long value), when the scanner scans it, then each is flagged as a violation. Parametrized across uppercase, lowercase, and mixed-case key forms (per TN-5).
- [ ] **AC-2**: Given the existing clean/synthetic fixtures already covered by the suite, when the scanner runs after the pattern changes, then they still report 0 violations (no false-positive blowup from `re.IGNORECASE` or the key-name broadening) — the broadening is token-key-shaped, not a blanket `\w+` (TN-5).
- [ ] **AC-3**: The `SYNTHETIC_MARKER` and `pii-ok` inline markers remain case-sensitive (TN-5) — a marker in a non-canonical case does NOT suppress scanning.
- [ ] **AC-4**: Given a token is `git add`-ed and then the working-tree copy is edited to remove the token (the file STILL EXISTS on disk, now clean), when `pii_scanner --staged` runs in a throwaway git repo (TN-6), then the staged token is still flagged (the scanner reads the staged blob via `git show :<path>`, not the working tree).
- [ ] **AC-5**: Given a token is `git add`-ed as an ADD and then the working-tree copy is DELETED (`rm`, so `Path.exists()` is now False but the index still holds the blob, listed Added), when `pii_scanner --staged` runs, then the staged token is STILL flagged — the staged-blob path does NOT reuse the `Path.exists()` scannability gate (TN-5 exists()-gate footgun). This is the genuine leak vector; a naive refactor that reuses `_scannability_skip_reason` wholesale would SKIP it.
- [ ] **AC-6**: Given a clean staged blob whose working tree is dirty with a token, when `pii_scanner --staged` runs, then no violation is reported for that file (the inverse of AC-4 — staged content, not working tree, is authoritative in `--staged` mode).
- [ ] **AC-7**: Given a staged file DELETION (`git rm`), when `pii_scanner --staged` runs, then it is skipped without error (already excluded by the `--diff-filter=ACM`, per TN-5 — distinct from AC-5's staged-add-then-`rm`).
- [ ] **AC-8**: Given `git show :<path>` fails for a staged path (mocked/absent blob), when `pii_scanner --staged` runs, then the scanner FAILS CLOSED — it emits an operator-visible stdout refusal message (it refuses to certify the scan clean when it cannot read a staged blob) AND exits NON-ZERO — while any other real findings are still reported. (Strengthened from the originally-specified warn-and-skip after the Phase-4b Codex review flagged warn-and-skip as a fail-open: a security control MUST NOT report a clean pass when it silently skipped an unreadable staged blob.)
- [ ] **AC-9**: The full `tests/test_pii_scanner.py` and `tests/test_pii_hook_integration.py` suites pass, and the scanner keeps the <1s/20-file performance bar (per TN-5, `.claude/rules/pii-safety.md`).

## Technical Approach
Compile `COMPILED_PATTERNS` with `re.IGNORECASE` and broaden the `api_key_assignment` key alternation to the project token-key names (targeted, not blanket) per TN-5. For `--staged`, read the staged blob via `git show :<path>` in `--staged` mode only, refactoring the post-read scanning body into a shared text-scanning helper consumed by both the file-path and staged-blob paths. Tests use a throwaway git repo in `tmp_path` and never stage into the project repo (TN-6). See TN-5, TN-6.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/safety/pii_patterns.py` (`re.IGNORECASE`, token-key-name broadening)
- `src/safety/pii_scanner.py` (staged-blob read via `git show :<path>`, shared text-scanning helper)
- `tests/test_pii_scanner.py` (uppercase/mixed-case regression, staged-blob fixture, `git show` failure path)
- `tests/test_pii_hook_integration.py` (run to confirm no integration regression)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
File-independent of the auth/serving stories; can run in any order. This is the F-H3 HIGH quick-win the audit flagged as pull-forward-eligible.

**Phase-4b remediation (2026-07-07)**: the Codex post-dev review flagged the originally-specified AC-8 warn-and-skip (unreadable staged blob → warn + continue, exit code reflects only OTHER findings) as itself a fail-OPEN — the scanner could report a clean pass while silently having skipped a staged blob it could not read. Hardened to FAIL CLOSED: an unreadable staged blob now forces a non-zero exit + an operator-visible stdout refusal, so the scanner never certifies clean when a staged blob is unreadable. AC-8 updated to match the shipped behavior.
