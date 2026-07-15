# E-264-01: Storage foundation — migration 012 + reader JOIN + ensure_team_row plumbing

## Epic
[E-264: League-Aware ERA Basis Fix](epic.md)

## Status
`TODO`

## Description
After this story is complete, the schema will carry a per-team-season `teams.innings_per_game` column (nullable, NULL = never-fetched/assumed), the query-time season pitching reader will carry that raw value on every pitcher row, and `ensure_team_row` will accept and NULL-safely backfill the value. This is the storage foundation that E-264-02 (fetch + apply) and E-264-03 (display) consume. No behavior visible on a report changes yet.

## Context
GameChanger computes ERA on a per-team-season game-length basis (`innings_per_game`, integer, observed 6 or 7; fallback 7). This story adds where that value lives and how it reaches the query-time ERA computation, without yet fetching it or changing any formula. The storage shape, reader threading, and self-heal plumbing are specified by data-engineer in the epic Technical Notes (TN-2, TN-3, TN-4). The NULL-vs-integer distinction is load-bearing: it is the sole signal the display layer (E-264-03) uses to decide whether to show "(assumed)".

## Acceptance Criteria
- [ ] **AC-1**: `migrations/012_*.sql` adds the column per Technical Notes TN-2 — `ALTER TABLE teams ADD COLUMN innings_per_game INTEGER;`, bare nullable with NO `DEFAULT` and NO `NOT NULL`, carrying the TN-2 comment verbatim. Given the migrations apply at startup, when the app/reset runs migrations, then the `teams` table has an `innings_per_game` column and every pre-existing row is NULL.
- [ ] **AC-2**: The column remains nullable and NULL is documented as load-bearing provenance (per TN-2). This AC exists so a reviewer catches any later attempt to add a `DEFAULT`/`NOT NULL` — such a change is a regression of the display contract and must be rejected.
- [ ] **AC-3**: `get_season_pitching` (`src/api/db.py`) carries `teams.innings_per_game` RAW (possibly NULL) on every returned pitcher row per Technical Notes TN-3 — added at the OUTER wrapper level, NOT inside the shared `pitching_recompute_select()` projection — with NO SQL-level COALESCE. Given a team with a stored basis and a team with NULL, when `get_season_pitching` is called for each, then each returned row exposes that team's `innings_per_game` value unchanged (integer or None). The perspective filter behavior is unchanged, and `pitching_recompute_select()` and its other consumers are unaffected.
- [ ] **AC-4**: `ensure_team_row` / `ensure_team_row_with_provenance` (`src/db/teams.py`) accept an `innings_per_game: int | None` parameter and backfill it via a new `_backfill_innings_per_game` that mirrors `_backfill_season_year` per Technical Notes TN-4. Given an existing row with NULL `innings_per_game`, when `ensure_team_row` is called with a non-NULL value, then the row is updated to that value; given an existing row with a stored integer, when `ensure_team_row` is called with `None`, then the stored integer is NOT clobbered.
- [ ] **AC-5**: Unit tests cover the migration (column exists, nullable, existing rows NULL), the reader (raw NULL and raw integer both surface), and the backfill direction (NULL→value fills; value→None does not clobber). Existing tests still pass (`migrations`, `db`, `ensure_team_row` suites). Note: adding `innings_per_game` to the `get_season_pitching` row dict changes the returned row shape — update any existing test that asserts an exact key set on those rows (test-scope discovery).

## Technical Approach
Add migration `012` per TN-2 (confirm `012` is the next number by `ls migrations/` — `011` is the current max). Thread the reader read (an outer-level `LEFT JOIN teams` or a scalar subselect — implementer's choice) into `get_season_pitching` per TN-3; do NOT modify the shared `pitching_recompute_select()` projection (it has other consumers). Add the param + `_backfill_innings_per_game` helper in `src/db/teams.py` modeled on the existing `season_year` / `_backfill_season_year` pattern (same NULL→value-only direction). Do not COALESCE in SQL; the fallback-to-7 constant belongs at the compute site (that is E-264-02's concern, not this story). Do not change any ERA formula or template in this story.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-264-02 (consumes the column, reader value, and `ensure_team_row` param), E-264-03 (consumes the raw NULL for the assumed flag)

## Files to Create or Modify
- `migrations/012_*.sql` (create)
- `src/api/db.py` (modify — `get_season_pitching` JOIN + select)
- `src/db/teams.py` (modify — `ensure_team_row`/`ensure_team_row_with_provenance` param + `_backfill_innings_per_game`)
- `tests/test_migrations.py`, `tests/test_db.py`, `tests/test_ensure_team_row.py` (modify/add coverage per AC-5)

## Agent Hint
data-engineer

## Handoff Context
- **Produces for E-264-02**: the `teams.innings_per_game` column, the `ensure_team_row(innings_per_game=...)` param to write into, and `get_season_pitching` rows carrying the raw value for the ERA compute site.
- **Produces for E-264-03**: the raw (possibly NULL) `innings_per_game` on pitcher rows — NULL is the "assumed" signal the disclosure reads.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
The column is nullable by design; see epic TN-2. Do not add a default value.

**Story-split rationale (why this is a data-layer-first story).** This story delivers no user-visible report change on its own, which normally argues against a standalone story per the PM "no set-up-the-database in isolation" guidance. It is deliberately split from E-264-02 because the two halves are genuinely different domains — migration + SQL reader + `teams.py` plumbing (data-engineer) vs API fetch + display formula (software-engineer) — and merging them would force one agent to work outside its domain (a migration inside an SE story). This story carries concrete, independently testable ACs (migration shape, reader value pass-through, backfill no-clobber direction), so it is an enabling data layer with real test coverage, not untestable scaffolding.
