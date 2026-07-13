# Data Engineer -- Agent Memory

## Storage Architecture (E-009 Decision, 2026-02-28)

- SQLite everywhere. Local dev and production both use SQLite. No D1. No Wrangler.
- Local dev DB path: `./data/app.db` (host-mounted Docker volume)
- Production: SQLite in Docker volume with WAL mode + simple file backup via `scripts/backup_db.py`
- Dev/prod parity: `docker compose up` runs the same stack locally and in production

## Migration Tooling

- Migration runner: `apply_migrations.py` (runs at app startup, applies unapplied migrations in order)
- Migration files: `migrations/001_*.sql`, `migrations/002_*.sql`, etc.
  - Three-digit prefix, underscore, descriptive slug, `.sql` extension
- Migrations are append-only. Never edit an applied migration.
- Track applied state in a `_migrations` metadata table
- **Current state**: E-220 SQUASHED the schema into `001_initial_schema.sql` (old migrations 001–015 archived in `.project/archive/migrations-pre-E220/`), folding all prior migrations and adding `perspective_team_id` as a first-class concept on stat tables. Since the squash, migrations are added incrementally on top of `001_*` (E-235 report_generation_runs, E-236 run count columns, E-238 webauthn_challenge_store, E-240 scheduled_report_runs, the E-250 identity/opponent/season_type drops, E-253 spray chart_type UNIQUE + game-dedup backstop, etc.).
- **Do NOT trust any concrete "next migration is NNN" claim** — this line and `.claude/rules/migrations.md` both self-rot. ALWAYS `ls migrations/*.sql` in the live checkout and take max+1 before assigning a number. The glob is the sole authority.
- **Notable schema notes carried forward**: `webauthn_challenges` (TTL'd, composite PK `(kind, lookup_key)`, CHECK kind IN 'login'/'registration', 5-minute `expires_at` default) fronted by `src/api/passkey_challenges.py`. **Replay-safety pattern (reusable for any single-use-token-under-concurrency need):** make the DELETE the ATOMIC ARBITER — `consume_challenge` returns `cursor.rowcount`, and the privileged action (session create) fires ONLY when consume deleted exactly 1 row (0 ⇒ another worker won ⇒ reject). SQLite single-writer (WAL) serialization guarantees exactly one winner.

## Schema Conventions

### ip_outs Convention
- Innings pitched stored as integer outs: 1 IP = 3 outs, 6.2 IP = 20 outs
- Storage format is always integer outs. No floating-point innings in the database.
- Display formatting is a valid read-time concern: `ip_outs // 3` for full innings, `ip_outs % 3` for partial

### Referential Integrity
- FK-safe orphan handling: when a player_id is not in `players`, insert a stub row (first_name='Unknown', last_name='Unknown') before writing the stat row. Log a WARNING for operator backfill.
- Foreign keys declared and enforced (`PRAGMA foreign_keys = ON`)
- Stub rows ensure FK constraints are never violated during ingestion

### Splits
- Home/away and L/R splits stored as nullable columns in season stats tables
- Column naming: `home_obp`, `away_obp`, `vs_lhp_obp`, `vs_rhp_obp`
- Not separate rows. Null means "not enough data to split."

### Timestamps
- All `created_at` and `updated_at` columns: text in SQLite `datetime('now')` format (e.g., `2026-03-01 14:30:00` -- space-separated, no `T`, no `Z`)

### IDs
- GameChanger-sourced entities: `TEXT` primary keys (their IDs are opaque strings)
- Internally-generated entities: `INTEGER PRIMARY KEY` (SQLite rowid alias)

## Core Entity Model

| Entity | Purpose |
|--------|---------|
| `Team` | A team identity (LSB Varsity, opponent teams) |
| `Player` | A unique person (single-season scope; cross-team identity is a permanent non-goal) |
| `team_rosters` | Junction: which players are on a team in a season (single-season roster membership) |
| `Game` | A single game event (date, opponent, location, result) |
| `player_game_batting` | A player's per-game batting line (boxscore-sourced; batting order, positions) |
| `player_game_pitching` | A player's per-game pitching line (outs recorded, runs, K, BB, pitches; boxscore-sourced) |
| `plays` | One row per plate appearance (batter/pitcher, pitch count, outcome, pre-computed `is_first_pitch_strike`/`is_qab` flags) |
| `play_events` | Individual events within a PA (pitch results, baserunner events, substitutions, `pitch_type`/`pitch_speed_mph`) |

### Key Design Decisions
- Event-level data (`plays`/`play_events`) and per-game tables (`player_game_*`) are the source of truth; season batting/pitching aggregates are DERIVED AT QUERY TIME by `src.api.db.get_season_batting`/`get_season_pitching` (SUM per-game, perspective-filtered) — the stored `player_season_*` tables were DROPPED by E-259 (migration 011, 2026-07-12)
- Cross-team player identity and multi-season rollups are permanent non-goals; `season_id` (year-only) is the single-season partition key. Roster membership lives in `team_rosters` (team_id, player_id, season_id)
- Opponent data is first-class: same schema structure as own-team data
- Normalize first; denormalize only for proven performance needs

## Topic File Index

- [endpoint-schema-notes.md](endpoint-schema-notes.md) -- Detailed schema implications for all discovered GameChanger API endpoints (team-detail, /me/teams, player-stats, schedule, public endpoints, opponents, boxscore, plays, roster, bridge endpoints). Response shapes, field types, join keys, normalization guidance, raw sample paths.
- [etl-patterns.md](etl-patterns.md) -- Programmatic token refresh (`token_manager.py` + `signing.py`, auto-refresh before expiry), raw-to-processed pipeline, idempotent ingestion, pagination patterns (cursor-based, x-next-page), project file paths for migrations/DB/API spec/stat glossary.
- [fixture_seed_not_rollup_consistent.md](fixture_seed_not_rollup_consistent.md) -- `tests/fixtures/seed.sql` was never rollup-consistent; E-259 stripped its `player_season_*` rows + dropped the tables, so the specific divergence is history — but the live lesson holds: exact-SUM tests (`test_season_projection.py` projection golden, `test_season_query_cutover.py`) use the dedicated `parity_consistent.sql`, not seed.sql (discovered E-234 review).
- [games_row_vs_stat_rows_coupling.md](games_row_vs_stat_rows_coupling.md) -- A completed `games` row can exist with ZERO player stat rows (loose loader coupling); "games-with-data" counts MUST EXISTS-filter on a perspective-scoped stat row, not COUNT bare completed games (E-235 Codex HIGH).
- [season_aggregate_writers.md](season_aggregate_writers.md) -- HISTORY: the entire season-aggregate WRITER architecture (three writers → `canonical_recompute` → `aggregate_parity` → `player_season_*` tables) was RETIRED by E-259 (query-time derivation). Live residual: canonical column set = ScoutingLoader's, now the surviving SUM projection in `season_projection.py` (RENAMED from `season_aggregates.py` by E-262-04); PA/XBH are renderer-derived, never stored.
- [pitch_type_annotation_parser_gap.md](pitch_type_annotation_parser_gap.md) -- GC pitch-type charting mode strands pitch events as `event_type='other'` (raw_template has `(Fastball)` suffix the parser misses) → `plays.pitch_count`/`is_first_pitch_strike` collapse to 0 → impossible FPS/P-PA. Default-0 masks absence; QAB exempt (outcome-derived). (2026-06-28 team 133 diag.)
- [plays_boxscore_reconciliation_baseline.md](plays_boxscore_reconciliation_baseline.md) -- E-245 north-star baseline: plays→boxscore fidelity is 98-100% (COVERAGE is the gap, not fidelity); correct grain = player-level (game+persp+player_id), NOT team-level; self-game (home==away) integrity bug = 23 games, breaks team attribution. Full inventory in `.project/research/E-245-*`.
- [season_tables_are_a_pure_cache.md](season_tables_are_a_pure_cache.md) -- DESIGN BASIS for the E-259 cutover (SHIPPED 2026-07-12): `player_season_*` were a pure derived cache (100% boxscore_only) so the migration-011 DROP was data-lossless; query-time derivation costs 0.046 ms/team; the perspective-double-count hazard was DISCHARGED in E-259-01 (readers add the explicit `perspective_team_id` filter); keeps the corrected post-cutover rollback.
- [scouting_query_role_vs_dedup_filters.md](scouting_query_role_vs_dedup_filters.md) -- Scouting rollups: `perspective_team_id` is a DEDUP key (holds BOTH teams' rows), NOT a role filter; each source table needs a separate ROLE filter (`plays.batting_team_id`, `spray_charts.team_id`/`chart_type`); spray error-maps MUST use `chart_type='defensive'` (the wrong-team trap); clean steals name no catcher so per-catcher CS% is uncomputable (team-battery CS% + raw per-catcher counts). (E-263 planning.)
- [schema_drop_test_blast_radius.md](schema_drop_test_blast_radius.md) -- Checklist of what a column/table DROP breaks in the test suite beyond INSERT sites (SELECTs, tuple asserts, whole premise-classes, expected-tables SETS, FK-violation vehicles → OperationalError not IntegrityError); AC must be concern-scoped not line-scoped; SQLite 3.35+ direct-DROP feasibility. (E-250 review.)
