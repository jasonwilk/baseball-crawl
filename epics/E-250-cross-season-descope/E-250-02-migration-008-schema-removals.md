# E-250-02: Migration 008 — drop identity/opponent/season_type schema + reference code

## Epic
[E-250: Root-Level Cross-Season / Multi-Season De-Scope](../E-250-cross-season-descope/epic.md)

## Status
`TODO`

## Description
After this story is complete, three pieces of dead cross-season/identity schema are gone from the database and from every `src/` reference: the `players.gc_athlete_profile_id` column (the E-104 cross-team identity anchor, never written or read), the whole `team_opponents` table (write-orphaned since E-239), and the `seasons.season_type` column (write-only constant `'default'`, the exact column behind the two-writers-must-agree footgun). Migration 008 performs the DROPs following the layered 006 pattern, and all code that inserted into or read from these is removed.

## Context
These three schema elements are the durable cross-season/identity residue. `gc_athlete_profile_id` was the anchor for the abandoned cross-team-identity direction (E-104, abandoned in E-250-07). `team_opponents` fed the removed tracked-opponent surface. `seasons.season_type` is a write-only `'default'` constant whose only live effect is the "two writers must agree on season_type" multi-writer footgun — dropping it deletes a footgun class. This story pairs the schema DROP with removal of every code reference so no mid-epic state SELECTs a dropped table.

## Acceptance Criteria
- [ ] **AC-1**: `migrations/008_<descriptive_name>.sql` exists and, per Technical Notes TN-2, drops `players.gc_athlete_profile_id`, `team_opponents` (whole table), and `seasons.season_type`; `001_initial_schema.sql`'s `CREATE TABLE` DDL is left unchanged (layered pattern). A fresh DB (migrations 001→008) and a migrated DB converge to the same schema.
- [ ] **AC-2**: The migration file documents (as 006 did) the verification that `gc_athlete_profile_id` and `season_type` are plain columns with no index/FK/generated-column/view dependency. DE confirmed direct `ALTER TABLE ... DROP COLUMN` is feasible on the actual runtime (SQLite 3.45.1, past 3.35) — NO table-rebuild is needed. The 12-step table-rebuild remains documented in Technical Notes TN-2 only as the defensive fallback were the runtime ever <3.35; the migration confirms the mechanism against the actual runtime version, not by assumption.
- [ ] **AC-3**: No `src/` code references `gc_athlete_profile_id`, `team_opponents`, or `seasons.season_type` after this story (grep-clean across `src/`).
- [ ] **AC-4**: The `season_type` INSERT column is removed from `src/gamechanger/crawlers/scouting.py:364` and `src/gamechanger/loaders/__init__.py:82`; the "must agree on `season_type`" multi-writer docstring at `src/gamechanger/crawlers/scouting.py:354-358` is removed; and the `ensure_season_row` docstring line ("writes `season_type='default'`", `src/gamechanger/loaders/__init__.py:71-77`) is updated so it no longer references the dropped column. (The AC-3 `src/` grep for `season_type` must return zero — including docstrings/comments.)
- [ ] **AC-5**: ALL `season_type` references that touch the dropped column are removed in THIS story, atomically with the column drop, per Technical Notes TN-3 (`season_type` is `NOT NULL` with no usable default, so anything referencing it breaks the instant the column drops AND cannot be pre-emptively edited while it exists — the removal must ride with the drop). This covers BOTH:
    - **INSERT fixtures**: the ~29 test files that `INSERT INTO seasons(...season_type...)` PLUS the two SQL fixtures `tests/fixtures/seed.sql` and `tests/fixtures/parity_consistent.sql`.
    - **READS / asserts / semantic shift** (Codex #5, concern-scoped per DE — enumerate the concern, NOT line numbers, or the third sub-test is missed): in `tests/test_season_id_derivation.py` remove ALL `season_type` usages across the `TestEnsureSeasonRow` class — the class docstring (~:143), the `test_year_only_format` SELECT (~:149) AND its expected tuple (drop the `season_type` element, since after AC-6 `ensure_season_row` no longer writes it), AND `test_does_not_overwrite_existing` (~:164-172) which both INSERTs and SELECTs `season_type`. In `tests/test_schema_queries.py`, drop `season_type` from `_QUERY_ALL_ORDERED` (~:538 — `SELECT season_id, season_type, year FROM seasons`, used by both `test_all_seasons_ordered_by_year` and `test_query_performance`; `season_type` is selected but never asserted) and update the ~:532-533 docstring. Net: no `season_type` read, assert, insert, or expected-value survives in either file.
    (Exact fixture/test paths confirmed during implementation.) This is the CR F1 green-gate fix; missing the reads would leave the suite RED on `no such column: season_type`.
- [ ] **AC-6**: In `ensure_season_row` (`src/gamechanger/loaders/__init__.py`), the defensive `season_id.split("-", 1)[0]` / `.isdigit()` parse is removed so `ensure_season_row` requires a pure-year `season_id`: any non-numeric OR compound value now RAISES via `int()` instead of silently deriving a wrong or zero year (per Technical Notes TN-4 — precise behavior: today `"2026-spring-hs"` derives `2026` and a non-numeric-first token like `"old-season"` derives `year=0`; after the change BOTH raise). The existing caller test `tests/test_loaders/test_game_loader.py` (DE: the season_id-override test at ~:2002-2030 calls `ensure_season_row(db, "old-season")` and `ensure_season_row(db, "new-season")` at ~:2015-2016, which today silently pass and after this change RAISE) is fixed in THIS story: those two opaque tokens are replaced with distinct numeric year tokens (e.g. `"2024"`/`"2025"`) or seeded via a direct `INSERT INTO seasons` that bypasses the loader. This file MUST be fixed here because E-250-02 is self-green (AC-10).
- [ ] **AC-7**: `is_team_eligible_for_cleanup` no longer references `team_opponents`: Guard 2 (`src/reports/generator.py:2721-2728`) and Guard 4 (`:2738-2754`) are removed, the `team_opponents` DELETE (`:2560-2564`) is removed, and the docstring (`:2699-2705`) is updated — including renumbering its enumerated guards from 1-4 down to 1-2 (only `is_active` and no-other-report survive). The surviving Guard 1 (`is_active = 0`) + Guard 3-now-2 (no OTHER report references this team) are the correct reports-first eligibility semantics (SE-confirmed). The `reports_admin.py:604` caller is unaffected. Per Technical Notes TN-5, tests PROVE eligibility is unchanged: no team that was ineligible becomes eligible, and teams gated only by the surviving guards behave identically.
- [ ] **AC-8**: `tests/test_e100_schema.py:807` is updated — `gc_athlete_profile_id` is dropped from the asserted `players` column tuple while `bats`/`throws` remain asserted.
- [ ] **AC-9**: The stale tests that seed or assert the dropped `team_opponents` table are fixed in THIS story (they would otherwise fail the moment the table is dropped), with the delete-vs-edit decision named explicitly per file (DE enumeration):
    - `tests/test_e100_schema.py` — THREE team_opponents concerns (distinct from the `gc_athlete_profile_id` column-tuple edit in AC-8; same file, multiple edits): (i) the entire `TestTeamOpponents` class (~:277-310 — `test_table_exists` / `test_unique_constraint` / `test_self_reference_check_constraint`) is DELETED wholesale; (ii) in `test_all_expected_tables_created` (~:145-158), `"team_opponents"` is removed from the `expected` table set (:149) — that set-membership removal is the functional gate-fix (`missing = expected - actual` would otherwise yield `{team_opponents}`); the "All 20 expected tables" docstring→19 is cosmetic-but-correct (no `len()==20` assert exists) (Codex #4, DE-confirmed); (iii) `test_foreign_keys_enabled` (~:160-167) uses `INSERT INTO team_opponents` (:164) as its FK-violation vehicle — after the drop that raises `OperationalError (no such table)` not `IntegrityError`, so the `pytest.raises(IntegrityError)` errors. Repoint to another all-FK-bearing table; DE's suggested vehicle is `team_rosters` (`INSERT INTO team_rosters (team_id, player_id, season_id) VALUES (9999, 'nope', 'nope')` violates the teams FK → `IntegrityError` with FK enforcement on).
    - `tests/test_admin_reports.py`: the `team_opponents`-dependent test at `:462-510` (`test_ac2_preserved_when_tracked_via_team_opponents`, which SEEDS a `team_opponents` row and asserts preservation via guard 2) is DELETED, not patched/preserved — it asserts the removed behavior and cannot even INSERT into the dropped table (per SE; do NOT "make it pass", which would reintroduce the removed guard).
    - `tests/test_schema.py:102`: `"team_opponents",` is removed from the `_EXPECTED_TABLES` set.
    - `tests/test_migrations.py:168`: `"team_opponents",` is removed from the `expected_tables` set.
- [ ] **AC-10**: The full test suite passes (`python -m pytest tests/` green) — achievable precisely because AC-5 removed the `season_type` fixtures in this same story (CR F1). Green confirms no seed path still inserts `season_type`, seeds/asserts `team_opponents`, or reads a dropped element. (Class-1 compound-slug normalization is the separate concern of E-250-03; the compound slugs that remain here are internally consistent and were green before, so they do not block this gate.)

## Technical Approach
Write migration 008 per TN-2 (layered ALTER DROP COLUMN for the two columns, DROP TABLE for `team_opponents`, no `season_id` rewrite). Remove the three code reference sites (season_type INSERTs, the compound parse, the team_opponents DELETE and eligibility guards). Remove every `season_type`-INSERT fixture (~29 test files + the two SQL fixtures) in the SAME story per TN-3 — `season_type` is `NOT NULL`, so this cannot be deferred to a later story without leaving the suite RED at this story's green-gate (CR F1). For the eligibility guards (TN-5), trace that removing guards 2 and 4 is behavior-preserving on the empty table and add tests that exercise the surviving guards (is_active, other-reports) to lock the behavior. Because migration + drops + code removal + season_type fixtures must land atomically to keep the suite green, they are one story — do not split the table/column drops from their code and fixture removals.

The context-layer prose that references these elements (`.claude/rules/data-model.md` "awaits E-104"/E-249 bullet) and the docs (`docs/admin/architecture.md`, `docs/ROADMAP.md`) are handled in E-250-04 (CA) and E-250-05 (docs-writer) respectively — NOT here — to respect routing.

## Dependencies
- **Blocked by**: E-250-01 (this story edits `tests/test_player_dedup.py` and `tests/test_cli_data.py` for `season_type`-fixture removal — the same files E-250-01 edits for the dedup contract; same-files ordering, CR F4)
- **Blocks**: E-250-03 (Class-1 compound-slug normalization runs after the schema/fixture changes here), E-250-04 (documents schema removals), E-250-05 (documents schema removals)

## Files to Create or Modify
- `migrations/008_<descriptive_name>.sql` — new migration (DROP column x2 + DROP TABLE)
- `src/gamechanger/crawlers/scouting.py` — remove season_type INSERT column + multi-writer docstring
- `src/gamechanger/loaders/__init__.py` — remove season_type INSERT column + dead compound parse in `ensure_season_row` + stale `season_type='default'` docstring
- `src/reports/generator.py` — remove `team_opponents` DELETE (:2560-2564), eligibility Guard 2 (:2721-2728) + Guard 4 (:2738-2754), and update the docstring (:2699-2705, renumber guards 1-4→1-2)
- ~29 test files that `INSERT INTO seasons(...season_type...)` — remove the `season_type` column from those inserts (AC-5); enumerate via grep during implementation. Includes `tests/test_player_dedup.py` and `tests/test_cli_data.py` (hence the blocked-by E-250-01).
- `tests/fixtures/seed.sql`, `tests/fixtures/parity_consistent.sql` — remove `season_type` from the `seasons` inserts (AC-5; exact fixture paths confirmed during implementation)
- `tests/test_season_id_derivation.py` — remove ALL `season_type` usages in `TestEnsureSeasonRow`: docstring (~:143), `test_year_only_format` SELECT (~:149) + expected tuple, and `test_does_not_overwrite_existing` (~:164-172) insert+select (AC-5, concern-scoped)
- `tests/test_schema_queries.py` — drop `season_type` from `_QUERY_ALL_ORDERED` (~:538, used by two tests) + the ~:532-533 docstring (AC-5, concern-scoped)
- `tests/test_e100_schema.py` — TWO concerns: drop `gc_athlete_profile_id` from the asserted column tuple (AC-8) AND delete the whole `TestTeamOpponents` class (~:277-310) + the `team_opponents` refs at ~:149/:164 (AC-9)
- `tests/test_loaders/test_game_loader.py` — replace the `ensure_season_row(db, "old-season"/"new-season")` tokens (~:2015-2016, test ~:2002-2030) with distinct numeric year tokens or a direct `INSERT INTO seasons`, per the fail-loud change (AC-6)
- `tests/test_admin_reports.py` — delete the `team_opponents`-dependent assertions (:462-510), not patch (AC-9)
- `tests/test_schema.py:102` — remove `"team_opponents",` from `_EXPECTED_TABLES` (AC-9)
- `tests/test_migrations.py:168` — remove `"team_opponents",` from `expected_tables` (AC-9)
- `tests/` — new/updated tests proving cleanup eligibility is unchanged (TN-5)

## Agent Hint
data-engineer

## Handoff Context
- **Produces for E-250-03**: A DB with `season_type` dropped and all its fixtures already cleaned, so E-250-03 handles ONLY the Class-1 compound-slug `season_id` normalization (TN-3) — it does NOT touch `season_type`.
- **Produces for E-250-04 / E-250-05**: The schema removals that the "awaits E-104" prose, `data-model.md` E-104 note, `docs/admin/architecture.md:211` team_opponents row, and `docs/ROADMAP.md:205` "leave the column inert" line must be corrected to reflect.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Merges the brief's stories 2 and 3 (schema removal + `team_opponents` code) into one atomic story so the table drop and its code removal land together. Per DE prep, this story is SE+DE-paired in skill: the migration is DE-led, but the `generator.py` DELETE + eligibility-guard tracing (TN-5) needs SE-level rigor with tests. Assigned data-engineer-led; the main session may pair SE. See epic TN-2, TN-4, TN-5.
