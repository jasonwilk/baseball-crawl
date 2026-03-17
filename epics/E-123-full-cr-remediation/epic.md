# E-123: Full Code Review Remediation

## Status
`READY`

## Overview
Fix 20+ confirmed bugs and safety gaps discovered during the full codebase code review. These span silent auth failure in crawlers, a PII scanner regex gap with a failing test, FK cascade violations, exception type mismatches, data display bugs, unsafe backup operations, and small correctness issues. Left unfixed, they cause silent credential-expiry waste across all crawl operations, a safety tool blind spot, admin delete crashes, wrong error diagnostics, and stale season defaults that will break next year.

## Background & Context
Five code reviewers audited the entire codebase (web app/auth, GC client/credentials, crawlers/pipeline, loaders/schema, CLI/scripts/infra). SE and DE verified all findings against current source code. Results are in `.project/research/full-code-review/cr1-verified.md` through `cr5-verified.md`.

This epic covers net-new confirmed findings NOT already addressed by:
- **E-122** (E-100 family CR remediation): scouting auth abort, dashboard template fixes, proxy import boundary, test fixture migration, credentials public API
- **E-117** (loader stat population): game_loader batting/pitching skip-lists, `_PlayerPitching.hr` dead code, `game_stream_id` threading, season stats column expansion
- **E-121** (style guide remediation): context-layer only, no code overlap

Expert consultation: No expert consultation required -- all findings are verified bugs with clear, scoped fixes. The verified-findings files provide full diagnostic context including line numbers and root cause analysis.

## Goals
- The 4 non-scouting crawlers (schedule, roster, game_stats, player_stats) abort immediately on `CredentialExpiredError` instead of logging N errors per team (scouting crawler covered by E-122-01)
- PII scanner detects unquoted YAML key assignments; failing test passes
- Admin user deletion cascades correctly through all FK-dependent tables
- `GameChangerAPIError` is a single type across the codebase (no shadowing)
- Two-way players show both batting and pitching data in recent games
- Scouting freshness gating works correctly (no infinite re-scouting)
- Client retry errors report correct context on final 5xx
- Database backup is WAL-safe
- Season default is dynamic (won't break next year)
- CLI display values are accurate
- Admin template XSS vector is closed

## Non-Goals
- CSRF protection (SameSite=Lax + Cloudflare Zero Trust provide adequate mitigation for current single-admin deployment; revisit if multi-user)
- Session/token garbage collection (negligible table growth at current scale)
- In-memory passkey challenge store persistence (acknowledged limitation, single-worker deployment)
- DRY refactoring of duplicated code (`_compute_pitching_rates`, `_is_fresh`, `_ensure_season_row`, team auth checks, inline imports) -- these are code smells, not bugs
- HTTP discipline gaps in token_manager/key_extractor (low practical risk)
- Scouting crawler test coverage (significant effort, separate epic)
- RateLimitError handling in crawlers (client-level retry mitigates API abuse)
- `sys.path.insert()` cleanup in test files (cosmetic inconsistency)
- Type annotation improvements (`object` type hints in pipeline modules)

## Success Criteria
- `CredentialExpiredError` during the 4 non-scouting crawlers' `crawl_all()` loops (schedule, roster, game_stats, player_stats) aborts immediately (scouting crawler is covered by E-122-01)
- `pytest tests/test_pii_scanner.py::test_secret_key_colon` passes (currently failing)
- Deleting a user with coaching assignments succeeds without `IntegrityError`
- `team_resolver.py` raises exceptions from `src.gamechanger.exceptions` (not local duplicates)
- Player profile recent games includes both batting and pitching rows for two-way players
- Scouting run status reflects actual completion state; freshness check works
- Final 5xx retry error includes retry context (not "Unexpected status")
- `backup_database()` uses `sqlite3.Connection.backup()` for WAL-safe copies
- Season default derives from available data (not hardcoded `"2026-spring-hs"`)
- `_human_size()` displays fractional values correctly (e.g., "2.4 MB" not "2.0 MB")
- Admin user delete confirmation uses safe JS escaping
- All existing tests pass

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-123-01 | Crawler CredentialExpiredError propagation (4 non-scouting) | TODO | E-122-01 | - |
| E-123-02 | PII scanner regex fix for unquoted values | TODO | None | - |
| E-123-03 | User cascade delete FK fix | TODO | None | - |
| E-123-04 | GameChangerAPIError type consolidation | TODO | None | - |
| E-123-05 | Two-way player recent games fix | TODO | None | - |
| E-123-06 | Scouting run status lifecycle fix | TODO | None | - |
| E-123-07 | Client retry error message fix | TODO | None | - |
| E-123-08 | WAL-safe database backup | TODO | None | - |
| E-123-09 | Small correctness fixes (season default, display, XSS) | TODO | E-123-05 | - |

## Dispatch Team
- software-engineer (E-123-01 through E-123-09)

## Technical Notes

### TN-1: Crawler Auth Abort Pattern (extends E-122-01)
E-122-01 fixes this pattern in `scouting.py` only. E-123-01 applies the same pattern to the 4 remaining crawlers. The fix: in each crawler's `crawl_all()` loop, add a `except CredentialExpiredError: raise` clause BEFORE the existing `except Exception` catch-all. This re-raises immediately, aborting the loop. The caller (pipeline orchestrator or CLI) handles the propagated error.

The four crawlers and their catch-all locations:
- `src/gamechanger/crawlers/schedule.py:101`
- `src/gamechanger/crawlers/roster.py:92`
- `src/gamechanger/crawlers/game_stats.py:177`
- `src/gamechanger/crawlers/player_stats.py:96`

### TN-2: PII Scanner Regex
The `api_key_assignment` pattern at `src/safety/pii_patterns.py:67` requires values wrapped in quotes. Unquoted YAML values (e.g., `secret_key: xKfake_value`) bypass detection. The fix should match both quoted and unquoted values. The test at `tests/test_pii_scanner.py:228-236` (`test_secret_key_colon`) is already written correctly -- it expects 1 violation but gets 0. After the regex fix, this test should pass.

### TN-3: Cascade Delete
`src/api/routes/admin.py:279-294` (`_delete_user()`) deletes from `user_team_access`, `sessions`, `magic_link_tokens`, `passkey_credentials`, then `users`. Missing: `coaching_assignments` table which has `user_id INTEGER NOT NULL REFERENCES users(id)` (schema line 469). The fix adds a `DELETE FROM coaching_assignments WHERE user_id = ?` before the `DELETE FROM users` statement.

### TN-4: GameChangerAPIError Duplication
`src/gamechanger/team_resolver.py:43-44` defines a local `GameChangerAPIError(Exception)` that shadows `src.gamechanger.exceptions.GameChangerAPIError`. These are different Python types -- `except` clauses catching one will miss the other. The fix: import from `exceptions.py` instead of defining locally. Also assess `TeamNotFoundError(ValueError)` at line 47 -- if it should be in the shared exceptions module.

### TN-5: Two-Way Player Recent Games
`src/api/db.py:747-752` deduplicates recent games by preferring batting rows. For a two-way player (bats AND pitches in the same game), only the batting row survives. The fix must return both rows (one batting, one pitching) tagged with `appearance_type`, so the template can display complete game data per AC-1.

### TN-6: Scouting Status Lifecycle
`src/gamechanger/crawlers/scouting.py:182` writes `status='running'` after crawl completion. The `_is_scouted_recently()` check at line 436 requires `status = 'completed'`. If the load step (external CLI call) fails, status stays `'running'` and freshness gating never engages. The fix should set `status='completed'` at the appropriate point in the lifecycle -- after successful crawl, not after load (since load is a separate step).

### TN-7: Client Retry Error
`src/gamechanger/client.py:539-558` -- on the final retry attempt for a 5xx, execution falls through to the generic "Unexpected status" error instead of raising `last_error` which contains retry context. The fix should ensure `last_error` is raised when all retries are exhausted.

### TN-8: WAL-Safe Backup
`src/db/backup.py:68` uses `shutil.copy2()` which doesn't capture WAL-mode sidecar files. The fix: use `sqlite3.Connection.backup()` API which performs a safe, consistent backup regardless of WAL state. This is the SQLite-recommended approach.

### TN-9: Verified Findings Reference
Full diagnostic details for each finding are in:
- `/.project/research/full-code-review/cr1-verified.md` (CR1-C2, CR1-C3, CR1-M7)
- `/.project/research/full-code-review/cr2-verified.md` (CR2-C2, CR2-H3)
- `/.project/research/full-code-review/cr3-verified.md` (CR3-C1, CR3-C2)
- `/.project/research/full-code-review/cr4-verified.md` (CR4-H6, CR4-M8)
- `/.project/research/full-code-review/cr5-verified.md` (CR5-C1, CR5-H3)

Story implementers should read the relevant finding section for line numbers, code context, and root cause analysis.

## Open Questions
- None. All findings verified with line-level precision.

## History
- 2026-03-17: Created from full codebase code review verified findings. 5 verifiers (SE x4, DE x1) confirmed ~40 findings; ~20 net-new after excluding E-117, E-122, E-121 overlap. Organized into 9 stories (all parallel, no file conflicts). Set DRAFT pending user review.
- 2026-03-17: Codex spec review produced 5 findings; all 5 accepted and applied. Fixes: E-123-06 AC-1 tightened to require `"completed"` status; E-123-06 file list added `tests/test_scouting_crawler.py`; E-123-01 scoped to 4 non-scouting crawlers with E-122-01 dependency; E-123-05 AC-1/AC-3 specified two-row display contract and added template to file list; E-123-09 AC-1 specified query-most-recent-season resolution and added `tests/test_db.py`. Set READY.
- 2026-03-17: Post-E-122 review found two AC-vs-Technical-Approach contradictions. E-123-05: removed "consider merging" alternative from Technical Approach -- AC-1 mandates two rows, not a merge. E-123-09: removed "or using a helper that derives from current date" from Technical Approach -- AC-1 mandates DB-query for most recent season_id. Also aligned TN-5 in epic to match the two-row contract.
