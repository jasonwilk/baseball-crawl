# E-229-01: Migration 002 v2 — schema rewrite in place

## Epic
[E-229: Team-Aggregate Defensive Positioning](epic.md)

## Status
`DONE`

## Description
After this story is complete, `migrations/002_batter_positioning.sql` will be rewritten end-to-end to the E-229 v2 schema: the `batter_positioning` table drops E-228's categorical columns and adds `zone_id` + confidence flags, and a new `team_position_aggregate` table is added with the four-tuple PK that DE locked. Both tables carry proper FK `REFERENCES` clauses, correct column types matching the live schema in `001_initial_schema.sql`, and idempotent DDL per `.claude/rules/migrations.md`. The conftest fixture builders no longer reference any retired columns. A fresh-db migration test verifies the v2 schema lands cleanly.

## Context
E-228's commit `2d6be06` on the branch added `migrations/002_batter_positioning.sql` with the v1 schema (categorical `call_state` + `team_state_call` + `direction_shade`/`depth_shade`/`zone_concentration`). Migration 002 never reached `main`, so per DE's Q-2 analysis the discipline rule that protects against rewriting applied migrations does NOT bind us — the cleanest path is to **rewrite the file in place** rather than chain a v2-as-migration-003. The branch's commit history reads honestly: `feat(E-228)` created 002 v1, `feat(E-229)` rewrites 002 to v2.

The operator's local `data/app.db` has the v1 migration applied. When E-229 lands, the migration runner sees "002 already applied" and skips. Operator must `rm data/app.db && docker compose up -d --build app` to let the runner rebuild from scratch. This is captured in epic Technical Notes (TN-1) and surfaced again in this story's Notes.

## Acceptance Criteria
- [ ] **AC-1**: `migrations/002_batter_positioning.sql` is rewritten end-to-end (full file replace; NOT `ALTER` patches stacked on E-228's v1 definitions). All DDL uses `CREATE TABLE IF NOT EXISTS` and `CREATE INDEX IF NOT EXISTS` per `.claude/rules/migrations.md` idempotency requirements.
- [ ] **AC-2**: `batter_positioning` table created with the column list and types specified in Technical Approach below, including: standard provenance columns with correct `TEXT`/`INTEGER` types matching the live schema in `001_initial_schema.sql` (`season_id TEXT`, `player_id TEXT`, `team_id INTEGER`, `perspective_team_id INTEGER`); kept deviation columns (`direction_deviation INTEGER`, `depth_deviation INTEGER`); new `zone_id TEXT` with the CHECK constraint per Technical Approach; `is_thin INTEGER NOT NULL DEFAULT 0`; `bip_count INTEGER NOT NULL`; `hr_count INTEGER NOT NULL DEFAULT 0` (kept per E-228 parity); `computed_at TEXT NOT NULL DEFAULT (datetime('now'))`. NO categorical-model columns (`call_state`, `team_state_call`, `direction_shade`, `depth_shade`, `zone_concentration`) are present.
- [ ] **AC-3**: NEW `team_position_aggregate` table created with PK `(team_id, season_id, perspective_team_id, position)` and columns `star_x REAL NOT NULL`, `star_y REAL NOT NULL`, `bip_count INTEGER NOT NULL`, `is_low_confidence INTEGER NOT NULL DEFAULT 0`, `computed_at TEXT NOT NULL DEFAULT (datetime('now'))` per Technical Approach. CHECK constraint on `position` matching the closed set `('LF','CF','RF','3B','SS','2B')`.
- [ ] **AC-4**: `batter_positioning` PK is `(player_id, team_id, season_id, perspective_team_id, position)` (per DE B-4 / CR B2 lock; matches E-228 v1 pattern). An explicit `CREATE INDEX IF NOT EXISTS idx_batter_positioning_lookup ON batter_positioning (team_id, season_id, perspective_team_id)` is included for the render-time per-card lookup pattern. NO additional index is added on `team_position_aggregate` (its PK leads with `(team_id, season_id, perspective_team_id)` and serves the lookup natively).
- [ ] **AC-5**: All FK columns carry `REFERENCES` clauses: `team_id INTEGER NOT NULL REFERENCES teams(id)`, `perspective_team_id INTEGER NOT NULL REFERENCES teams(id)`, `season_id TEXT NOT NULL REFERENCES seasons(season_id)`, `player_id TEXT NOT NULL REFERENCES players(player_id)`. Verified via `PRAGMA foreign_key_list(batter_positioning)` and `PRAGMA foreign_key_list(team_position_aggregate)` in the migration test.
- [ ] **AC-6**: NO column from E-228's v1 retired set survives: `call_state`, `team_state_call`, `direction_shade`, `depth_shade`, `zone_concentration`. Migration test verifies absence via `PRAGMA table_info(batter_positioning)`.
- [ ] **AC-7**: `conftest.py` schema loading sequence (and any test-fixture builders that populate `batter_positioning`) contains NO references to retired columns. **Scope**: this story scrubs retired column references only; extending fixtures with new column writes (`zone_id`, `is_low_confidence`, etc.) for engine tests is E-229-02's scope (per DE I-9).
- [ ] **AC-8**: A new test (`tests/test_migration_002.py`) asserts the v2 schema is present after migration: creates a fresh in-memory database with `PRAGMA foreign_keys=ON`, applies migrations 001 then 002 via `apply_migrations.py`, then queries `PRAGMA table_info` for both `batter_positioning` and `team_position_aggregate` to confirm the expected column set and types. Tests the `zone_id` CHECK constraint by attempting an invalid insert (expects `IntegrityError`). Tests FK enforcement by attempting an insert with a non-existent `team_id`/`season_id`/`player_id` (expects `IntegrityError`).
- [ ] **AC-9**: The migration is runner-level idempotent: re-applying via `apply_migrations.py` against a DB that already has migration 002 applied is a no-op (migration runner tracks `_migrations`). The DDL itself uses `CREATE TABLE IF NOT EXISTS` and `CREATE INDEX IF NOT EXISTS` as belt-and-suspenders per `.claude/rules/migrations.md`.

## Technical Approach

**Migration file shape (full rewrite):**

```sql
-- Migration 002: batter positioning (E-229 v2 schema)
-- Supersedes E-228 v1 in-place per epic TN-1 (branch-stack chain).

CREATE TABLE IF NOT EXISTS batter_positioning (
    player_id            TEXT    NOT NULL REFERENCES players(player_id),
    team_id              INTEGER NOT NULL REFERENCES teams(id),
    season_id            TEXT    NOT NULL REFERENCES seasons(season_id),
    perspective_team_id  INTEGER NOT NULL REFERENCES teams(id),
    position             TEXT    NOT NULL CHECK (position IN ('LF','CF','RF','3B','SS','2B')),
    direction_deviation  INTEGER,
    depth_deviation      INTEGER,
    zone_id              TEXT    CHECK (zone_id IS NULL OR zone_id IN ('A','B','C','D','E','F','G','H')),
    is_thin              INTEGER NOT NULL DEFAULT 0,
    bip_count            INTEGER NOT NULL,
    hr_count             INTEGER NOT NULL DEFAULT 0,
    computed_at          TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (player_id, team_id, season_id, perspective_team_id, position)
);

CREATE INDEX IF NOT EXISTS idx_batter_positioning_lookup
    ON batter_positioning (team_id, season_id, perspective_team_id);

CREATE TABLE IF NOT EXISTS team_position_aggregate (
    team_id              INTEGER NOT NULL REFERENCES teams(id),
    season_id            TEXT    NOT NULL REFERENCES seasons(season_id),
    perspective_team_id  INTEGER NOT NULL REFERENCES teams(id),
    position             TEXT    NOT NULL CHECK (position IN ('LF','CF','RF','3B','SS','2B')),
    star_x               REAL    NOT NULL,
    star_y               REAL    NOT NULL,
    bip_count            INTEGER NOT NULL,
    is_low_confidence    INTEGER NOT NULL DEFAULT 0,
    computed_at          TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (team_id, season_id, perspective_team_id, position)
);
```

**conftest scrub** (AC-7 scope, NOT extension): grep `tests/conftest.py` and any test-builder modules for references to `call_state`, `team_state_call`, `direction_shade`, `depth_shade`, `zone_concentration`. Remove or comment out the fixture rows that reference these columns. **Do NOT add `zone_id` / `is_low_confidence` writes in this story** — that's E-229-02's scope per the AC-7/I-9 split.

**Migration test**: `tests/test_migration_002.py`. Asserts column presence/absence on both tables after migration applies to a fresh database. Tests CHECK constraints (zone_id invalid value, position invalid value) and FK enforcement (non-existent team/season/player IDs).

**Operator note in story Notes**: include the `rm data/app.db && docker compose up -d --build app` step for the user.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-229-02

## Files to Create or Modify
- `migrations/002_batter_positioning.sql` — modify (full file rewrite)
- `tests/conftest.py` — modify (scrub references to retired columns; do NOT extend fixtures with new column writes — that's E-229-02)
- `tests/test_migration_002.py` — create (fresh-DB schema verification + CHECK + FK enforcement tests)

## Agent Hint
data-engineer

## Handoff Context
- **Produces for E-229-02**: the v2 `batter_positioning` and `team_position_aggregate` table shapes that the engine writes to. E-229-02's engine code reads column names from the v2 schema; ACs there assume the v2 column set per Technical Notes TN-13/TN-14 and extend test fixtures with the new column writes.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes

**Operator release-step note (release-time, NOT story implementation):**
Before bringing up the stack on the E-229 branch, the operator (Jason) MUST drop the local database:
```
rm data/app.db && docker compose up -d --build app
```
This is required because the migration runner sees E-228's v1 migration 002 already applied in `_migrations` and would skip the v2 schema apply. Single-operator project; no cleanup migration is needed (YAGNI, per epic TN-1).

**Type/FK note**: column types and FK targets verified against `migrations/001_initial_schema.sql` lines 80–104 (`seasons.season_id TEXT PRIMARY KEY`, `players.player_id TEXT PRIMARY KEY`) and lines 122–129 (`team_rosters` reference pattern). E-228's v1 migration 002 had these correct; the E-229 draft introduced a type regression that was caught and fixed during Phase 3 iteration 1 review.
