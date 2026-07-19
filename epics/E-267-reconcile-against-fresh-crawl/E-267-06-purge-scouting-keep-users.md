# E-267-06: `bb db purge-scouting` — Purge Scouting/Report Data, Preserve User Identity + Auth (clean-slate command)

## Epic
[E-267: Reconcile-at-Load Against the Fresh Crawl](epic.md)

## Status
`TODO`

## Description
After this story is complete, the destructive operator CLI command `bb db purge-scouting` (in `src/cli/db.py`, alongside `reset`) wipes ALL scouting and report data for a true clean data slate while PRESERVING user identity and auth, so existing coaches stay logged in. This is the post-epic clean-slate mechanism for both dev and live (dev may alternatively use `bb db reset`; live uses this to preserve auth). It exists because mass report-deletion leaves residue (players/seasons/programs + orphan team rows) that the `teams.is_active` cascade guard does not reap.

## Context
The operator's plan after this epic lands is to start from a clean data slate (per epic Clean-Slate section). A plain report-mass-delete does not clean-slate: a report-delete purges team data only when it is the LAST report for the team AND `is_active=0`, so `is_active=1` subject teams and their children strand. `bb db reset` would clear everything but also destroys user identity/auth (logins). This command is the targeted middle path: purge scouting/report data, keep identity/auth.

## Acceptance Criteria
- [ ] **AC-1**: Given a DB with scouting + report data and user identity/auth rows, when the purge command runs, then every PURGE-partition table is empty and every KEEP-partition table survives intact, exactly per the partition in Technical Notes TN-8 (KEEP: `users`, `passkey_credentials`, `magic_link_tokens`, `sessions`, `webauthn_challenges`, `programs`, `_migrations`; PURGE incl. `user_team_access`, `coaching_assignments`, `crawl_jobs`, `seasons`, `teams`, `players`, all game/report tables).
- [ ] **AC-2**: Given the same run, when it completes, then an existing user's login capability is intact (passkey + magic-link + session auth still resolve the surviving `users` rows), and the `programs` `lsb-hs` bootstrap row is preserved (as `bb db reset` does).
- [ ] **AC-3 (FK enforcement must be LIVE)**: The purge deletes in the FK-safe order in TN-8, and the module MUST explicitly set `PRAGMA foreign_keys = ON` (or route through `get_connection()` in `src/api/db.py`, which sets it) — `sqlite3.connect()` defaults it OFF and `reset.py` never enables it, so a naive mirror would silently orphan while appearing to pass. The regression test MUST deliberately reorder one delete and assert it RAISES, proving FK-ON is live, not merely intended (per TN-9).
- [ ] **AC-4**: Given `APP_ENV=production`, when the command runs WITHOUT `--force`, then it refuses and logs loudly; with `--force` it proceeds. The guard is a FRESH check through the canonical `is_production()` seam (`src/api/helpers.py`, returns bool) — do NOT reuse `reset.py`'s `check_production_guard`, which routes through the inline `.lower()==` compare (the IDEA-101 bypass class); mirror reset.py's STRUCTURE only, not its guard body (per TN-9).
- [ ] **AC-5**: The command unlinks the on-disk `report_path` HTML files for ALL purged reports — enumerate `SELECT id, report_path FROM reports WHERE report_path IS NOT NULL` (NO expiry filter — do NOT call `cleanup_expired_reports()`, which filters to expired-only), resolve each against the module's `_REPO_ROOT / "data"`, `unlink()` with per-row error isolation, and do it BEFORE the `reports` DELETE removes the rows (once gone, `report_path` can't be enumerated), per TN-9.
- [ ] **AC-6 (single transaction)**: All ordered deletes (and any report-path handling) run inside ONE transaction — commit at end, rollback on error — so a mid-purge failure never leaves a corrupt half-state (per TN-9).
- [ ] **AC-7 (partition drift-proofing)**: A test enumerates the live `sqlite_master` tables and asserts each is classified as exactly KEEP or PURGE — INCLUDING `_migrations` (which is KEEP per AC-1/TN-8), excluding only sqlite internals (e.g. `sqlite_sequence`) — so a future migration that adds a table cannot silently fall through the partition.
- [ ] **AC-8**: Regression test per TN-7: seeds identity + scouting rows (and at least one on-disk report HTML, resolving the module `_REPO_ROOT` to a patchable seam pointed at `tmp_path` — NOT the real `data/reports/`), runs the purge, and asserts (a) all PURGE tables empty — INCLUDING `user_team_access`, which is PURGE and must NOT be asserted to survive, (b) all KEEP tables survive, (c) existing-login capability intact, (d) the on-disk HTML is unlinked. Hard AC.
- [ ] **AC-9 (production-guard test — GAP-2, destructive/live-safe command)**: A test pins the AC-4 guard: (a) `APP_ENV=production` WITHOUT `--force` REFUSES and deletes NOTHING (all tables intact), (b) `--force` proceeds, and critically (c) a whitespace/case variant (`" Production "`) STILL refuses — this bypass class (IDEA-101) is the entire reason AC-4 mandates the fresh `is_production()` seam over reset.py's `.lower()==` body, so it MUST be tested or the motivating fix ships unverified. Hard AC.
- [ ] **AC-10 (rollback + unlink-isolation robustness)**: Tests assert (a) an injected mid-purge failure ROLLS BACK to no half-state (AC-6 single transaction), and (b) a missing on-disk `report_path` file does NOT abort the purge (AC-5 per-row unlink error isolation).

## Technical Approach
Mirror `src/db/reset.py`'s STRUCTURE (the `bb db purge-scouting` Typer command lives in `src/cli/db.py` next to `reset`; the destructive logic in a new `src/db/` module) but partition the schema per TN-8 rather than dropping the file, set `PRAGMA foreign_keys = ON` explicitly (AC-3), write a FRESH `is_production()` guard (AC-4, not reset.py's guard body), unlink report HTML by the mechanism before the reports DELETE (AC-5), and wrap the whole purge in one transaction (AC-6). Resolve report paths through a patchable `_REPO_ROOT` seam so AC-8 points at `tmp_path`. Data-engineer OWNS the TN-8 partition + FK-order as an advisory decision (already locked); software-engineer authors the module + CLI + tests (no schema/migration/ETL work — SE-routed per the 2026-07-19 SE consultation).

## Dependencies
- **Blocked by**: None
- **Blocks**: E-267-05 (docs cover this command)

## Files to Create or Modify
- A new purge module under `src/db/` (mirroring `src/db/reset.py`'s structure; sets `PRAGMA foreign_keys = ON`; patchable `_REPO_ROOT` seam)
- The CLI command surface `src/cli/db.py` (`bb db purge-scouting`, alongside `reset`)
- Test file under `tests/`

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing (incl. the identity-survives + login-intact assertions)
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Post-epic clean-slate mechanism (operator option C, 2026-07-19). Production-safe (runs on live). Master record: `.project/research/2026-07-19-rerun-accumulate-only-audit.md`. Relates to IDEA-101 (reset-guard whitespace-bypass — route through `is_production()`).
