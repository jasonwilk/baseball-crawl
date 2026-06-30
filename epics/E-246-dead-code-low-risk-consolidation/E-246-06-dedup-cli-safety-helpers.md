# E-246-06: Dedup low-risk CLI/safety constants, predicates, printers

## Epic
[E-246: Dead-Code Removal & Low-Risk Consolidation](epic.md)

## Status
`TODO`

## Description
After this story is complete, several low-risk hand-redefined constants, predicates, and print idioms across the CLI and safety modules will be replaced by their canonical shared sources.

## Context
The sweep's L1 finding enumerates self-contained, low-risk duplications:
- The `(web, mobile)` profile tuple is hand-redefined in `src/cli/status.py:26` and `src/cli/proxy.py:111` despite a canonical `ALL_PROFILES` already existing.
- `_AVAILABILITY_SIGNALS` is defined function-locally in two printers.
- A signal match-rate print idiom is copy-pasted ~4× (`src/cli/data.py:337`, `:439`, `:371-394`, `:457-464`).
- `pii_scanner`'s scannability gate is implemented in two functions that must stay in lockstep (`src/safety/pii_scanner.py:240-246`).

These are independent, low-blast-radius dedups grouped into one story.

## Acceptance Criteria
- [ ] **AC-1**: Given the `(web, mobile)` tuple is hand-redefined, when the story completes, then `status.py` and `proxy.py` import the canonical `ALL_PROFILES` instead of redefining it (a grep confirms no remaining local `(web, mobile)` profile-tuple literals in those modules).
- [ ] **AC-2**: Given `_AVAILABILITY_SIGNALS` is function-local in two printers, when the story completes, then it is hoisted to a single module-level constant that both printers reference.
- [ ] **AC-3**: Given the signal match-rate print idiom is copy-pasted, when the story completes, then it is extracted into one shared print helper and the call sites delegate to it, producing byte-identical console output.
- [ ] **AC-4**: Given the `pii_scanner` scannability gate exists in two functions, when the story completes, then both `scan_file` and `_count_scannable` route through one shared predicate so they cannot diverge.
- [ ] **AC-5**: Given the consolidations, when the CLI/safety test modules run (`tests/test_pii_scanner.py`, `tests/test_cli_status.py`, `tests/test_cli_proxy.py`), then they pass, and the `pii_scanner` continues to flag the same files as before (the scannability decision is unchanged). (The full-suite-green check across `tests/` is the epic-level closure gate, not a per-story AC — it is only authoritative in the merged main checkout, not the worktree.)

## Technical Approach
Report locations (re-verify before acting): `src/cli/status.py:26`, `src/cli/proxy.py:111`, `src/cli/data.py:337`, `:439`, `:371-394`, `:457-464`, `src/safety/pii_scanner.py:240-246`. Each item is independent. For the print-helper extraction, console output must remain byte-identical. For the `pii_scanner` predicate, the scannability decision (which files are scanned) must not change — this is a security-relevant gate, so verify it flags the same set before and after.

## Dependencies
- **Blocked by**: E-246-03 (both touch `src/cli/data.py`; E-246-03 finalizes the DB-path option wiring first)
- **Blocks**: None

## Files to Create or Modify
- `src/cli/status.py`
- `src/cli/proxy.py`
- `src/cli/data.py`
- `src/safety/pii_scanner.py`
- `tests/test_pii_scanner.py` (extend — assert the scannability gate flags the same file set before/after per AC-5; file exists today)
- `tests/test_cli_status.py`, `tests/test_cli_proxy.py` (extend only if the print-helper/profile-tuple changes alter asserted console output; both exist today)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] `pii_scanner` flags the same file set before and after (verified)
- [ ] No regressions in existing tests
- [ ] Code follows project style (see CLAUDE.md)

## Notes
Runs after E-246-03 because both edit `src/cli/data.py`. The `pii_scanner` change is behavior-preserving but security-relevant — keep the scannability decision identical.
