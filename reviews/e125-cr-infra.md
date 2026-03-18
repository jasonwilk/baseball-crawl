# Code Review: E-125 Correctness & Infrastructure Stories (03, 04, 06, 07)

## Critical Issues

None.

## Important Issues

### 1. `.env.example` and `production-deployment.md` admin seed SQL uses wrong column names -- E-125-06 AC-5 not met

**Files**: `.env.example:127`, `docs/production-deployment.md:127`

Both files still contain:
```sql
sqlite3 data/app.db "INSERT INTO users (user_email, display_name, is_admin) VALUES ('<ADMIN_EMAIL>', '<ADMIN_NAME>', 1);"
```

The actual `users` table schema (`migrations/001_initial_schema.sql:427-432`) has:
- Column is `email`, not `user_email`
- No `display_name` column
- No `is_admin` column

Running this SQL produces: `Error: table users has no column named user_email`. Any operator following the deployment runbook will hit a hard error during initial setup.

AC-5 required: "line ~171 SQL INSERT instruction matches the current `users` table schema (email only, no `display_name` or `is_admin` columns)". The correct SQL should be:
```sql
sqlite3 data/app.db "INSERT INTO users (email) VALUES ('<YOUR_EMAIL>');"
```

### 2. OBP NULL-coalesce test only covers one of three template paths

**File**: `tests/test_dashboard.py:1736-1772`

The `test_null_hbp_shf_coalesced_to_zero` test only exercises `GET /dashboard` (team_stats template). The opponent scouting query (`get_opponent_scouting_report`) and player profile query (`get_player_profile`) also received COALESCE changes for `hbp`/`shf`, but no test verifies NULL handling on those paths.

Lower risk because all three queries use identical COALESCE patterns, but the other two paths are untested for the specific edge case this story was fixing.

## Minor Issues

### 3. `collect-endpoints.sh` sources entire `.env` including all secrets

**File**: `scripts/collect-endpoints.sh:29-32`

```bash
set -a
source .env
set +a
```

This exports every variable in `.env` into the shell environment, including `GAMECHANGER_REFRESH_TOKEN_WEB`, `GAMECHANGER_CLIENT_KEY_WEB`, etc. The script only needs 4 UUID variables (`GC_TEAM_UUID`, `GC_ORG_UUID`, `GC_EVENT_UUID`, `GC_STREAM_UUID`). Consider extracting only those rather than sourcing everything.

### 4. `production-deployment.md` upgrade note lacks failure consequence

**File**: `docs/production-deployment.md:79-80`

The upgrade note mentions `sudo chown -R 1000:1000 data` but doesn't state that existing containers **will fail to start** without this step. The troubleshooting table at line 321 has the `PermissionError` entry but the upgrade note doesn't cross-reference it. A one-sentence addition ("Without this, the container will fail with `PermissionError`") would prevent confusion.

## Observations

### Things Done Well

1. **OBP formula is mathematically correct**: `(H+BB+HBP)/(AB+BB+HBP+SF)` applied consistently across all three templates (`team_stats.html:57`, `opponent_detail.html:129`, `player_profile.html:51,106`). DB queries properly SELECT `hbp` and `shf` with COALESCE.

2. **COALESCE pattern handles NULL correctly**: `COALESCE(psb.hbp, 0)` and `COALESCE(psb.shf, 0)` in all three query functions (`get_team_batting_stats`, `get_opponent_scouting_report`, `get_player_profile`). Per the story notes, NULL means "not reported" -- COALESCE to 0 is the right semantic.

3. **SLG formula verified correct**: The template expression `(h + doubles + 2*triples + 3*hr) / ab` is algebraically equivalent to the standard `(1B + 2*2B + 3*3B + 4*HR) / AB` since `H = 1B + 2B + 3B + HR`. E-125-03 story notes confirm the reviewer validated this.

4. **FK enforcement via inline PRAGMA is the right fix**: `executescript()` resets connection state (documented SQLite behavior), so prepending `PRAGMA foreign_keys=ON;\n` to the SQL string is the correct pattern. Applied consistently in `apply_migrations.py:131,169`, `reset.py:130`, `seed_dev.py:108`.

5. **FK enforcement tests are effective**: `test_fk_violation_rejected_during_migration` proves FK violations raise `IntegrityError`, and `test_fk_enforcement_pragma_is_inline` proves the pragma survives `executescript()`.

6. **Dockerfile is well-structured**: Layer caching preserved (requirements before source), explicit UID 1000 for appuser, data directory pre-owned, `USER appuser` placed after all root-only operations (package install, useradd, chown). Seed data copied before ownership transfer.

7. **Backup connection fix is complete**: try/finally with explicit `close()` on both `src` and `dst` connections. Test `test_backup_closes_connections_on_failure` verifies both connections are closed even when `backup()` raises.

8. **OBP test suite is thorough**: Known HBP/SF values with pre-computed expected results, negative assertion (`.417` not present proves old formula is gone), zero-denominator guard, NULL coalesce test, backlink URL verification, and tests for all three template pages.

9. **PII scanner migration clean**: `sys.path.insert()` removed from `src/safety/pii_scanner.py`. Both `.githooks/pre-commit` and `.claude/hooks/pii-check.sh` updated to use `python3 -m src.safety.pii_scanner` module invocation. Imports use proper package path (`from src.safety.pii_patterns import ...`).

## Summary

The E-125 correctness and infrastructure stories are well-implemented overall. The OBP formula fix, FK enforcement, Dockerfile hardening, backup connection fix, and PII scanner migration are all correct and properly tested.

**One important finding**: The `.env.example` and `production-deployment.md` admin user seed SQL still references non-existent columns (`user_email`, `display_name`, `is_admin`), which produces a hard error for anyone following the deployment runbook. This is an E-125-06 AC-5 failure that should be fixed.

Minor items: broader NULL-hbp test coverage and `.env` sourcing scope in the endpoint collection script.
