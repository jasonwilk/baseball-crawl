# Data Engineer -- Agent Memory

## Storage Architecture (E-009 Decision, 2026-02-28)

- SQLite everywhere. Local dev and production both use SQLite. No D1. No Wrangler.
- Local dev DB path: `./data/app.db` (host-mounted Docker volume)
- Production: SQLite in Docker volume with WAL mode + Litestream backup
- Dev/prod parity: `docker compose up` runs the same stack locally and in production

## Migration Tooling

- Migration runner: `apply_migrations.py` (runs at app startup, applies unapplied migrations in order)
- Migration files: `migrations/001_*.sql`, `migrations/002_*.sql`, etc.
  - Three-digit prefix, underscore, descriptive slug, `.sql` extension
- Migrations are append-only. Never edit an applied migration.
- Track applied state in a `_migrations` metadata table
- **Current state (verified 2026-06-14)**: E-220 SQUASHED the schema into `001_initial_schema.sql` (704 lines; old migrations 001–015 archived in `.project/archive/migrations-pre-E220/`), folding all prior migrations and adding `perspective_team_id` as a first-class concept on stat tables. **E-235 added `002_report_generation_runs.sql`** (one wide telemetry row per report generation; FK→reports ON DELETE CASCADE; UNIQUE(report_id)). **E-236 added `003_report_run_count_columns.sql`** (additive ALTER TABLE ADD COLUMN ×4 on report_generation_runs: boxscores_fetched, load_errors, plays_errors, spray_games_with_data — all nullable INTEGER). So `migrations/` now holds `001_*` + `002_*` + `003_*` (verified by glob 2026-06-16). **E-238-06 (in flight in the epic worktree, NOT yet merged to main as of 2026-06-16) adds `004_webauthn_challenge_store.sql`** — TTL'd `webauthn_challenges` table (composite PK (kind, lookup_key); CHECK(kind IN 'login'/'registration'); `expires_at TEXT NOT NULL DEFAULT (datetime('now','+5 minutes'))`; `created_at` default; index `idx_webauthn_challenges_expires_at`) that replaces the in-process passkey challenge dicts in `src/api/routes/auth.py`, fronted by helper `src/api/passkey_challenges.py` (store/get/consume/sweep; sweep-on-write TTL). **Replay safety pattern (Codex P1 / F1 remediation):** under multiple workers, a read-then-delete-later consume is racy (two workers read the same live challenge, both verify, both create sessions). Fix = make the DELETE the ATOMIC ARBITER: `consume_challenge` returns `cursor.rowcount`, and the login verify path creates a session ONLY when consume deleted exactly 1 row (0 ⇒ another worker won ⇒ reject 401). SQLite single-writer (WAL) serialization guarantees exactly one winner. Reusable pattern for any single-use-token-under-concurrency need. **VERIFIED LIVE 2026-06-29 by glob: `migrations/` holds 001–006** — 001_initial_schema, 002_report_generation_runs, 003_report_run_count_columns, 004_webauthn_challenge_store, 005_scheduled_report_runs, 006_drop_season_fallback. **Next migration is `007`** (E-245 story 01's pitch-type columns = `007_*`). The older "next is 005" note was stale. NOTE: `.claude/rules/migrations.md` is STALE; ALWAYS glob the live dir before assigning a number — do not trust either doc.
  - (Prior 2026-03-26 note claimed 001–005 as separate files — that was pre-squash and is now stale/wrong.)

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
| `Player` | A unique person (cross-team, cross-season identity) |
| `PlayerTeamSeason` | Junction: which player was on which team in which season |
| `Game` | A single game event (date, opponent, location, result) |
| `Lineup` | A player's position in a game lineup (batting order, fielding position) |
| `PlateAppearance` | A single plate appearance event (outcome, counts, matchup context) |
| `PitchingAppearance` | A pitcher's appearance in a game (outs recorded, runs, K, BB) |

### Key Design Decisions
- Event-level data (plate appearances) is the source of truth; aggregate tables valid when query-time computation is impractical
- Player identity across teams is the hard problem -- `PlayerTeamSeason` junction handles it
- Opponent data is first-class: same schema structure as own-team data
- Normalize first; denormalize only for proven performance needs

## Topic File Index

- [endpoint-schema-notes.md](endpoint-schema-notes.md) -- Detailed schema implications for all discovered GameChanger API endpoints (team-detail, /me/teams, player-stats, schedule, public endpoints, opponents, boxscore, plays, roster, bridge endpoints). Response shapes, field types, join keys, normalization guidance, raw sample paths.
- [etl-patterns.md](etl-patterns.md) -- Token lifetime and ETL scheduling (14-day window), raw-to-processed pipeline, idempotent ingestion, pagination patterns (cursor-based, x-next-page), project file paths for migrations/DB/API spec/stat glossary.
- [fixture_seed_not_rollup_consistent.md](fixture_seed_not_rollup_consistent.md) -- `tests/fixtures/seed.sql` season aggregates are NOT a literal SUM of its per-game rows; aggregate-parity/recompute tests need a dedicated rollup-consistent fixture (discovered E-234 review).
- [games_row_vs_stat_rows_coupling.md](games_row_vs_stat_rows_coupling.md) -- A completed `games` row can exist with ZERO player stat rows (loose loader coupling); "games-with-data" counts MUST EXISTS-filter on a perspective-scoped stat row, not COUNT bare completed games (E-235 Codex HIGH).
- [season_aggregate_writers.md](season_aggregate_writers.md) -- THREE divergent writers of `player_season_*` boxscore_only rows (ScoutingLoader vs dedup recompute disagree: gs vs w/l/sv vs pa/singles/xbh → non-deterministic hybrid rows); canonical set = ScoutingLoader's; PA/XBH are renderer-derived not stored-read (E-237/Epic C).
- [pitch_type_annotation_parser_gap.md](pitch_type_annotation_parser_gap.md) -- GC pitch-type charting mode strands pitch events as `event_type='other'` (raw_template has `(Fastball)` suffix the parser misses) → `plays.pitch_count`/`is_first_pitch_strike` collapse to 0 → impossible FPS/P-PA. Default-0 masks absence; QAB exempt (outcome-derived). (2026-06-28 team 133 diag.)
- [plays_boxscore_reconciliation_baseline.md](plays_boxscore_reconciliation_baseline.md) -- E-245 north-star baseline: plays→boxscore fidelity is 98-100% (COVERAGE is the gap, not fidelity); correct grain = player-level (game+persp+player_id), NOT team-level; self-game (home==away) integrity bug = 23 games, breaks team attribution. Full inventory in `.project/research/E-245-*`.
