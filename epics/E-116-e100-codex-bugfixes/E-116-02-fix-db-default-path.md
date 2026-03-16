# E-116-02: Fix db.py cwd-Relative Default Path

## Epic
[E-116: E-100 Codex Review Bug Fixes](epic.md)

## Status
`TODO`

## Description
After this story is complete, `src/api/db.py` will resolve its default database path relative to the repo root using `Path(__file__).resolve().parents[2]`, consistent with the project's repo-root resolution convention.

## Context
`src/api/db.py` uses `_DEFAULT_DB_PATH = "./data/app.db"` which resolves relative to the current working directory. CLAUDE.md requires `src/` modules to use `Path(__file__).resolve().parents[N]` for repo-root-relative paths. The `DATABASE_PATH` environment variable mitigates in Docker (where it's always set), but the fallback path is fragile when running outside the repo root (e.g., tests, scripts, or manual invocations).

## Acceptance Criteria
- [ ] **AC-1**: `_DEFAULT_DB_PATH` in `src/api/db.py` is computed as `Path(__file__).resolve().parents[2] / "data" / "app.db"` (or equivalent repo-root-relative derivation).
- [ ] **AC-2**: When `DATABASE_PATH` env var is set, it takes precedence over the default (existing behavior preserved).
- [ ] **AC-3**: A test verifies the default path ends with `data/app.db` and is an absolute path (not cwd-relative).
- [ ] **AC-4**: All existing tests pass.

## Technical Approach
The fix is described in the epic Technical Notes "db.py Default Path Bug" section. `src/api/db.py` is at `src/api/db.py` — two levels below repo root, so `Path(__file__).resolve().parents[2]` gives the repo root.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/api/db.py`
- `tests/test_api/test_db.py` (create if not exists, or add to existing test file)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- SE confirmed: the `DATABASE_PATH` env var is always set in Docker, so this bug only manifests in non-Docker contexts (local dev, direct script execution).
- `parents[2]` for `src/api/db.py`: parents[0] = `src/api/`, parents[1] = `src/`, parents[2] = repo root.
