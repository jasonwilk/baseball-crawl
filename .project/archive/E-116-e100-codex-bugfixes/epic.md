# E-116: E-100 Codex Review Bug Fixes

## Status
`COMPLETED`

## Overview
Fix two bugs discovered by Codex code review of E-100 implementation: a broken YAML load path that produces `TeamRef(id=0)` causing FK violations, and a cwd-relative default database path in `src/api/db.py` that violates the project's repo-root resolution convention.

## Background & Context
After E-100 (Team Model Overhaul) and E-114 (Codex Review Fixes) shipped, a post-dev Codex review (two runs: high and medium reasoning) found 10 findings. PM triaged with SE and DE input (2026-03-16): 2 FIX (this epic), 6 DISMISS (expected E-100 Non-Goal deferrals), 2 DEFER (bundle with future stat population epic). The dismissed findings (stat column gaps, game_stream_id, season loader coverage) were captured as IDEA-028 through IDEA-037 in the ideas backlog.

No expert consultation required — both fixes are small, well-understood bugs with clear root causes identified by SE investigation.

## Goals
- `bb data load` (YAML path) correctly resolves `TeamRef.id` from the database, eliminating FK violations
- `src/api/db.py` resolves its default database path relative to the repo root via `Path(__file__).resolve().parents[N]`, not cwd

## Non-Goals
- Expanding loader stat coverage (deferred to IDEA-028)
- Populating game_stream_id, batting_order, bats/throws, or other enriched columns (E-100 Non-Goals)
- Expanding loader tests beyond the two targeted fixes

## Success Criteria
- `bb data load --source yaml` successfully loads game data without FK violations (TeamRef.id is a valid teams.id value)
- `src/api/db.py` default path resolves to `<repo-root>/data/app.db` regardless of cwd
- All existing tests pass

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-116-01 | Fix YAML load path TeamRef(id=0) regression | DONE | None | - |
| E-116-02 | Fix db.py cwd-relative default path | DONE | None | - |

## Dispatch Team
- software-engineer (E-116-01, E-116-02)

## Technical Notes

### YAML Load Path Bug (E-116-01)
`src/pipeline/load.py` calls `load_config()` without passing `db_path` when `--source yaml` is selected. This means `load_config_from_db()` is never called, so `TeamEntry.internal_id` stays `None`. Downstream, `_run_game_loader()` constructs `TeamRef(id=team.internal_id or 0, ...)`, producing `TeamRef(id=0)`. Since `PRAGMA foreign_keys=ON` and no `teams.id=0` row exists, all player stat INSERTs fail with FK violations.

The fix: pass `db_path` to `load_config()` in `src/pipeline/load.py` so that YAML-sourced teams get their `internal_id` resolved from the database. AC-4 in E-100-03 specified this behavior ("load_config() (YAML path) populates internal_id via a DB lookup before returning"), so this is a regression in the call site, not a missing feature.

### db.py Default Path Bug (E-116-02)
`src/api/db.py` line 23 uses `_DEFAULT_DB_PATH = "./data/app.db"` which resolves relative to cwd. CLAUDE.md convention requires `src/` modules to use `Path(__file__).resolve().parents[N]` for repo-root-relative paths. For `src/api/db.py` (two levels deep: `src/api/`), `parents[2]` gives the repo root. The `DATABASE_PATH` env var mitigates in Docker, but the fallback is fragile.

## Open Questions
- None.

## History
- 2026-03-16: Created from Codex review triage (2 FIX items). SE and DE investigation confirmed both bugs. IDEA-028 through IDEA-037 captured deferred E-100 Non-Goal work.
- 2026-03-17: COMPLETED. Both stories implemented and verified. E-116-01: Fixed YAML load path TeamRef(id=0) regression by passing db_path to load_config() and replacing silent id=0 fallback with explicit ValueError. E-116-02: Fixed cwd-relative default db path in src/api/db.py using Path(__file__).resolve().parents[2]. Both stories include new tests (2 in load_orchestrator, 3 in test_db). All ACs verified by PM.
