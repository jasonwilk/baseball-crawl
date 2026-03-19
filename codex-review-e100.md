# Comprehensive Code Review: E-100 Team Model Overhaul + E-114 Fixes + E-115 Documentation

## Context

Three epics rewrote the baseball-crawl data model from scratch:

- **E-100** (Team Model Overhaul): Fresh-start schema rewrite with INTEGER PK for teams, programs table, membership_type replacing is_owned, complete stat coverage per endpoint, two-phase add-team flow, flat team list, and full pipeline/admin/dashboard migration. 6 stories, all implemented.
- **E-114** (Codex Review Fixes): 5 bug fixes found by a prior Codex review of E-100: phantom team rows in game_loader, admin duplicate detection, member radio UX guard, stale dashboard template refs, missing unique indexes in test schemas.
- **E-115** (Documentation Updates): 2 stories (READY, not yet implemented) updating admin docs. Review the story definitions for completeness.

This is a **current-state review**, not a diff review. Read the files as they exist now and evaluate them against the rubric, epics, and project conventions.

## Setup

Read these files first to understand the project conventions and what was built:

1. `CLAUDE.md` -- project conventions, architecture, security rules, data model
2. `.project/codex-review.md` -- the review rubric (priorities, reporting format)
3. `epics/E-100-team-model-overhaul/epic.md` -- the epic specification (goals, non-goals, technical notes, schema design)
4. `.project/archive/E-114-e100-codex-review-fixes/epic.md` -- the bug fix epic
5. `epics/E-115-e100-documentation/epic.md` -- the documentation epic

## Review Rubric

Follow the review priorities defined in `.project/codex-review.md`, in order:

1. **Bugs and regressions** -- logic errors, off-by-ones, wrong defaults, silent failures
2. **Missing tests** -- data parsing, transformation, and loader logic must have tests; flag any untested code
3. **Credential and security risks** -- credentials or tokens in code, logs, comments, or test fixtures; SQL injection; insecure defaults
4. **Schema drift** -- database writes that do not match current migration state; loader fields that do not exist in the schema
5. **Planning/implementation mismatch** -- code that does not satisfy the story's acceptance criteria, or contradicts the epic's Technical Notes
6. **Style and convention violations** -- missing type hints, `print()` instead of `logging`, raw `httpx.Client()` instead of `create_session()`, `os.path` instead of `pathlib`

## Files to Review

Read every file listed below. Review each against the rubric priorities.

### Schema & Migration

- `migrations/001_initial_schema.sql`
- `migrations/apply_migrations.py`

Cross-reference against: E-100 epic Technical Notes "Schema Design" and "Complete Stat Column Reference" sections, and `docs/gamechanger-stat-glossary.md` for stat column naming.

### Data Layer

- `src/api/db.py`
- `src/gamechanger/types.py` (TeamRef dataclass)

Verify: All query functions use INTEGER team PKs. `get_permitted_teams()` returns `list[int]`. No TEXT team_id remnants. TeamRef has `id: int`, `gc_uuid: str | None`, `public_id: str | None`.

### Pipeline

- `src/gamechanger/config.py`
- `src/gamechanger/crawlers/game_stats.py`
- `src/gamechanger/crawlers/opponent.py`
- `src/gamechanger/crawlers/opponent_resolver.py`
- `src/gamechanger/crawlers/player_stats.py`
- `src/gamechanger/crawlers/roster.py`
- `src/gamechanger/crawlers/schedule.py`
- `src/gamechanger/crawlers/scouting.py`
- `src/gamechanger/loaders/game_loader.py`
- `src/gamechanger/loaders/roster.py`
- `src/gamechanger/loaders/scouting_loader.py`
- `src/gamechanger/loaders/season_stats_loader.py`
- `src/pipeline/bootstrap.py`
- `src/pipeline/crawl.py`
- `src/pipeline/load.py`
- `src/cli/data.py`
- `config/teams.yaml`

Verify: All use TeamRef or INTEGER team references. `membership_type` replaces `is_owned`. No `_generate_opponent_team_id()` or `_resolve_team_ids()` remnants. CrawlConfig uses `member_teams` not `owned_teams`. Loaders write to correct schema columns. SQL INSERT/UPDATE statements match the DDL in `001_initial_schema.sql`.

### Admin UI

- `src/api/routes/admin.py`
- `src/api/templates/admin/confirm_team.html`
- `src/api/templates/admin/opponent_connect.html`
- `src/api/templates/errors/forbidden.html`

Verify: Two-phase add-team flow works (Phase 1: URL parse + bridge lookup; Phase 2: confirm with membership radio, program/division dropdowns). All routes use INTEGER `{id}` path parameters. Member radio disabled when gc_uuid unavailable (E-114-03 fix). Phase 1 gc_uuid preserved for duplicate detection on re-submit (E-114-02 fix).

### Dashboard

- `src/api/routes/dashboard.py`
- `src/api/templates/dashboard/_team_selector.html`
- `src/api/templates/dashboard/game_detail.html`
- `src/api/templates/dashboard/game_list.html`
- `src/api/templates/dashboard/opponent_detail.html`
- `src/api/templates/dashboard/opponent_list.html`
- `src/api/templates/dashboard/player_profile.html`
- `src/api/templates/dashboard/team_pitching.html`

Verify: `team_id` query params parse as int. No stale `display_name` or `is_admin` references (E-114-04 fix). Templates use `user.username` and `user.role == 'admin'`.

### Tests

- `tests/fixtures/seed.sql`
- `tests/test_admin.py`
- `tests/test_admin_opponents.py`
- `tests/test_admin_teams.py`
- `tests/test_auth.py`
- `tests/test_auth_routes.py`
- `tests/test_bootstrap.py`
- `tests/test_cli_scout.py`
- `tests/test_coaching_assignments.py`
- `tests/test_config.py`
- `tests/test_crawlers/test_game_stats_crawler.py`
- `tests/test_crawlers/test_opponent_crawler.py`
- `tests/test_crawlers/test_opponent_resolver.py`
- `tests/test_crawlers/test_player_stats_crawler.py`
- `tests/test_crawlers/test_roster_crawler.py`
- `tests/test_crawlers/test_schedule_crawler.py`
- `tests/test_dashboard.py`
- `tests/test_dashboard_auth.py`
- `tests/test_db.py`
- `tests/test_e100_schema.py`
- `tests/test_loaders/test_game_loader.py`
- `tests/test_loaders/test_roster_loader.py`
- `tests/test_loaders/test_season_stats_loader.py`
- `tests/test_migration_003.py`
- `tests/test_migrations.py`
- `tests/test_passkey.py`
- `tests/test_schema.py`
- `tests/test_schema_queries.py`
- `tests/test_scouting_crawler.py`
- `tests/test_scouting_loader.py`
- `tests/test_scouting_schema.py`
- `tests/test_scripts/test_crawl_orchestrator.py`
- `tests/test_scripts/test_load_orchestrator.py`
- `tests/test_seed.py`

Verify: No xfail markers. Test schemas include UNIQUE indexes matching production DDL (E-114-05 fix). Seed data matches current schema. Tests cover the E-114 bug fixes (phantom team rows, duplicate detection, member radio guard, stale template refs).

### Epic/Story Definitions (Review for Completeness)

- `epics/E-115-e100-documentation/epic.md`
- `epics/E-115-e100-documentation/E-115-01-operations-team-management.md`
- `epics/E-115-e100-documentation/E-115-02-architecture-schema-admin.md`

Verify: Stories have clear ACs. Referenced source files exist. No stale references to pre-E-100 concepts.

## Specific Cross-Cutting Concerns

Check these across ALL files:

1. **No TEXT team_id remnants**: Search for any use of TEXT-typed team_id parameters, string team_id comparisons, or `is_owned` references. Everything should use INTEGER `teams.id` and `membership_type`.
2. **No stale references**: No `display_name`, `is_admin` (use `user.username`, `user.role`), `level` (use `classification`), `owned_teams` (use `member_teams`).
3. **SQL injection safety**: All SQL uses parameterized queries, never string interpolation.
4. **Schema-code alignment**: Every `INSERT INTO` and `UPDATE` statement references columns that exist in `001_initial_schema.sql`. Every `SELECT` references valid column names.
5. **Import boundary**: `src/` modules do not import from `scripts/`. `scripts/` imports from `src/`.
6. **Test isolation**: Each test file creates its own schema and seed data; tests do not depend on external state.

## Output

Write your findings to `codex-review-e100-findings.md` in the project root with this structure:

```markdown
# Code Review Findings: E-100 + E-114 + E-115

Date: [today's date]

## Summary
[1-3 sentence overview of findings]

## Priority 1: Bugs and Regressions
[findings or "None"]

## Priority 2: Missing Tests
[findings or "None"]

## Priority 3: Credential and Security Risks
[findings or "None"]

## Priority 4: Schema Drift
[findings or "None"]

## Priority 5: Planning/Implementation Mismatch
[findings or "None"]

## Priority 6: Style and Convention Violations
[findings or "None"]

## Cross-Cutting Concerns
[findings from the 6 cross-cutting checks above]

## E-115 Story Review
[assessment of E-115 story definitions]
```

Cite file and line number for every finding. If the review is clean for a priority level, state "None" explicitly.
