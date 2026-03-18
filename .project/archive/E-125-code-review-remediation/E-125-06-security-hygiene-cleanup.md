# E-125-06: Security Hygiene (Hardcoded UUIDs, Backup Connection, PII Scanner sys.path, Stale .env.example)

## Epic
[E-125: Full-Project Code Review Remediation](epic.md)

## Status
`TODO`

## Description
After this story is complete, four hygiene issues will be resolved: hardcoded real UUIDs removed from a committed script, the backup database function properly closes connections on error, the PII scanner eliminates its `sys.path` manipulation, and the stale `.env.example` SQL instruction matches the current schema. These are individually small fixes grouped because each is a few-line change.

## Context
**Hardcoded UUIDs** (Review 04 #1): `scripts/collect-endpoints.sh` contains hardcoded real GameChanger UUIDs (team, org, event, stream). Per CLAUDE.md security rules, these should not be in committed source.

**Backup connection** (Review 04 #8): `src/db/backup.py:72-73` uses `with sqlite3.connect()` which does NOT close the connection (only commits/rolls back). If `src.backup(dst)` fails, connections are not closed. For WAL-mode databases, unclosed connections can hold locks.

**PII scanner sys.path** (Review 04 #7): `src/safety/pii_scanner.py:40` uses `sys.path.insert()` in a `src/` module, violating the python-style rule. The pre-commit hook can invoke it as a module instead.

**Stale .env.example** (Review 04 #5): `.env.example:171` references `display_name` and `is_admin` columns that no longer exist in the `users` table (E-100 schema rewrite removed them). Following the instruction produces an error.

## Acceptance Criteria
- [ ] **AC-1**: `scripts/collect-endpoints.sh` loads UUIDs from environment variables or a config file, not hardcoded in source
- [ ] **AC-2**: `src/db/backup.py` explicitly closes both source and destination connections in all cases (success and failure), using a pattern that guarantees closure (e.g., try/finally with explicit `.close()`)
- [ ] **AC-3**: `src/safety/pii_scanner.py` does not use `sys.path.insert()` or any `sys.path` manipulation
- [ ] **AC-4**: `.githooks/pre-commit` invokes the PII scanner in a way that works without `sys.path` manipulation (e.g., `python3 -m src.safety.pii_scanner`). Note: `.claude/hooks/pii-check.sh` is handled separately by E-125-07 (claude-architect).
- [ ] **AC-5**: `.env.example` stale references are corrected: (a) line ~150 comment about `is_admin=1` auto-creation is updated to reflect current DEV_USER_EMAIL behavior (finds or creates user by email only, no `is_admin` column); (b) line ~171 SQL INSERT instruction matches the current `users` table schema (email only, no `display_name` or `is_admin` columns)
- [ ] **AC-6**: All existing tests pass

## Technical Approach
**UUIDs**: Replace hardcoded values with `${TEAM_UUID:-}` style env var reads with error messages if unset, or source from a `.env` file that is gitignored.

**Backup**: Replace the `with sqlite3.connect()` pattern with explicit try/finally that calls `.close()` on both connections. The `with` statement on `sqlite3.connect()` is a well-known Python gotcha -- it manages transactions, not the connection lifecycle.

**PII scanner**: Remove the `sys.path.insert()` call and the fallback import block. Update the pre-commit hook to invoke via `python3 -m src.safety.pii_scanner` which uses the editable install and avoids path manipulation.

**Stale .env.example**: Update the SQL instruction to match the current `users` table columns from `migrations/001_initial_schema.sql`.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `scripts/collect-endpoints.sh` (remove hardcoded UUIDs)
- `src/db/backup.py` (connection close fix)
- `src/safety/pii_scanner.py` (remove sys.path manipulation)
- `.githooks/pre-commit` (update PII scanner invocation)
- `.env.example` (fix stale SQL instruction)
- `tests/test_backup.py` (connection close verification if testable)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The hardcoded UUIDs in `collect-endpoints.sh` are team/org/event/stream IDs that resolve to real GameChanger entities. While not auth tokens, they are identifiers that should not be in source control per project security policy.
- The backup connection issue is a well-known Python/SQLite gotcha. See Python docs: `sqlite3.Connection` as context manager commits/rolls back but does not close.
- The `.claude/hooks/pii-check.sh` file also invokes the PII scanner directly (`python3 "$SCANNER" --staged`) and needs the same invocation update, but it is a context-layer file and must be handled by claude-architect in E-125-07.
