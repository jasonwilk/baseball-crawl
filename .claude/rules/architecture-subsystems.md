---
paths:
  - "src/reports/**"
  - "src/reconciliation/**"
  - "src/charts/**"
  - "src/llm/**"
  - "src/gamechanger/crawlers/**"
  - "src/gamechanger/parsers/**"
  - "src/gamechanger/loaders/**"
  - "src/pipeline/**"
  - "src/api/routes/dashboard.py"
  - "src/api/routes/reports.py"
---

# Architecture Subsystems

Subsystem-specific implementation details. For general architecture principles and canonical MUST constraints, see CLAUDE.md's Architecture section.

## Scouting Pipeline

Five stages: (1) scouting crawl (`ScoutingCrawler` -- schedules, rosters, boxscores), (2) scouting load (`ScoutingLoader` -- aggregate boxscores into season stats), (3) gc_uuid resolution (resolve `public_id` → `gc_uuid` via `POST /search` for spray chart access), (4) spray crawl (`ScoutingSprayChartCrawler`), (5) spray load (`ScoutingSprayChartLoader`). Source files: `src/gamechanger/crawlers/scouting.py`, `src/gamechanger/crawlers/scouting_spray.py`, `src/gamechanger/loaders/scouting_loader.py`, `src/gamechanger/loaders/scouting_spray_loader.py`, `src/pipeline/trigger.py` (web), `src/cli/data.py` (CLI).

**In-memory crawl-to-load**: Scouting crawlers return data in-memory (dataclasses/dicts) directly to loaders -- no disk intermediary (`data/raw/` files) for the scouting or spray stages. Game IDs come from crawl results, not filesystem globs. This eliminates stale-file contamination across runs. The own-team (member) pipeline retains disk caching because its crawl and load are separate CLI invocations. See `.claude/rules/perspective-provenance.md` for the full perspective tagging invariant.

## Background Pipeline Trigger

`src/pipeline/trigger.py` provides fire-and-forget pipeline execution from HTTP routes (FastAPI `BackgroundTasks`). Each trigger function creates its own DB connection, refreshes auth eagerly, tracks status via `crawl_jobs` rows, and updates `teams.last_synced` on success. Two pipelines: `run_member_sync` (crawl+load+opponent discovery for owned teams) and `run_scouting_sync` (all five scouting stages for tracked teams -- see Scouting pipeline). `run_member_sync` includes automatic opponent discovery after crawl+load: the schedule seeder (`src/gamechanger/loaders/opponent_seeder.py`) seeds `opponent_links` from cached `schedule.json`/`opponents.json`, then `OpponentResolver.resolve()` upgrades linked rows via live API calls. Seeder failures are non-fatal; `CredentialExpiredError` from the resolver propagates. **Auto-scout after resolution**: When an opponent is resolved with a non-null `public_id`, scouting is triggered automatically. This pattern exists in three places: (1) admin manual connect (`/admin/opponents/{link_id}/resolve`), (2) admin GC search resolve, and (3) auto-resolver during `_discover_opponents()` in `run_member_sync`. Admin routes (manual connect, GC search) enqueue `run_scouting_sync` via FastAPI `BackgroundTasks`; the auto-resolver during `_discover_opponents()` calls `run_scouting_sync` directly (already executing inside a background job). No manual sync trigger needed. **Auto-sync resilience pattern**: Auto-sync triggers from admin actions (team add, merge) use a two-phase approach: `_prepare_auto_sync()` does DB-only work (running-job check, `crawl_jobs` creation) in a thread pool, then `_enqueue_from_prep()` calls `background_tasks.add_task()` from the async handler. Both phases are wrapped in try/except so auto-sync failures never prevent the primary operation from completing.

## Canonical Team Creation (Detail)

`ensure_team_row()` in `src/db/teams.py` implements a deterministic dedup cascade: gc_uuid match → public_id match → name+season_year match (tracked only) → INSERT. A self-tracking guard prevents member teams from being re-created as tracked opponents. Back-fill rules are conservative: gc_uuid/public_id are NOT attached on name-only matches (step 3) to avoid irreversible misidentification.

## Canonical-Function Additive Extension Pattern

When a heavily-called canonical function needs to return MORE (provenance, fallback flags, telemetry) without churning its many call sites, add a sibling `*_with_provenance` / `*_with_fallback` variant that returns a small result dataclass, move the logic into the variant, and have the legacy function DELEGATE to it (returning the unchanged scalar). The cascade/derivation logic lives in exactly one place; existing callers are untouched. E-235 examples: `ensure_team_row()` → `ensure_team_row_with_provenance()` returning `EnsureTeamResult(team_id, match_method, inserted)` (`src/db/teams.py`); `derive_season_id_for_team()` → `derive_season_id_for_team_with_fallback()` returning a `SeasonDerivation` (`src/gamechanger/loaders/__init__.py`). New telemetry needs on a canonical function SHOULD use this additive-sibling shape rather than widening the legacy signature or duplicating the cascade.

## Canonical Team Deletion (Detail)

`src/reports/generator.py` provides two consolidated deletion paths via common helpers `_delete_game_scoped_data()` and `_delete_team_scoped_data()`: (1) `cascade_delete_team()` -- aggressive, deletes all games involving the team, used by report-deletion cleanup; (2) `cleanup_orphan_teams()` -- safe, only deletes games where the team is the sole participant, used during report generation to clean temporary data. `is_team_eligible_for_cleanup()` enforces 4 guard conditions (not member, not tracked opponent, no public_id, no gc_uuid) before any cascade.

## Canonical Opponent Resolution (Detail)

`finalize_opponent_resolution()` in `src/api/db.py` performs a write-through operation atomically: upserts `team_opponents`, sets `teams.is_active = 1`, discovers and reassigns FKs from old stub teams, and returns the result.

## Season_id Derivation (Detail)

`derive_season_id_for_team(db, team_id)` in `src/gamechanger/loaders/__init__.py` returns `tuple[str, int | None]` -- `(season_id, season_year)`. Maps `program_type` to suffix: `hs` → `spring-hs`, `usssa` → `summer-usssa`, `legion` → `summer-legion`. Fallbacks: NULL `season_year` → current year, NULL `program_id` → year-only (no suffix). `ensure_season_row(db, season_id)` is the consolidated function replacing all private `_ensure_season_row()` methods.

## Filesystem vs DB Season_id Decoupling

The filesystem path (`data/raw/{season_slug}/teams/{uuid}/`) is for file organization and discovery only. The DB `season_id` column is for data identity. These are decoupled -- a team's data may live in `data/raw/2026-spring-hs/` on disk but be tagged as `2025-summer-usssa` in the DB if the team's actual season context differs. Crawlers write to filesystem paths (derived from crawl config); loaders call `derive_season_id_for_team()` for DB inserts. `scouting_runs.season_id` is a file-discovery column reflecting the crawl directory path -- it does NOT necessarily match the DB season_id of the loaded data.

## Chart Rendering

`src/charts/` package contains headless PNG rendering modules (matplotlib + numpy). Currently: `src/charts/spray.py` (spray chart renderer). Future chart types go in this package. Image endpoints under `/dashboard/charts/` use `run_in_threadpool` for DB + renderer calls.

## Plays Pipeline

`src/gamechanger/crawlers/plays.py` (crawler), `src/gamechanger/parsers/plays_parser.py` (pure parser, no DB dependency), `src/gamechanger/loaders/plays_loader.py` (thin DB writer). Parser/loader separation pattern: the parser is a pure function producing dataclasses from raw JSON, enabling unit testing without DB fixtures. The loader handles DB writes only. **Pitcher state tracking**: the parser maintains `current_pitcher_top` and `current_pitcher_bottom` state variables that persist across innings within the same half, updated on substitution events, with explicit pitcher references in `final_details` as ground truth override. **team_players asymmetric keys**: own team uses `public_id` slug, opponent uses UUID -- build a flat lookup dict across both. Entry points: `bb data crawl --crawler plays`, `bb data load --loader plays`. Cached data: `data/raw/{season}/teams/{gc_uuid}/plays/{event_id}.json`.

## Spray Chart Pipeline

`src/gamechanger/crawlers/spray_chart.py` (crawler) and `src/gamechanger/loaders/spray_chart_loader.py` (loader). The spray endpoint is team-scoped and asymmetric: calling with the owning team's UUID returns both teams' spray data; calling with a participant's UUID returns only that team's data (verified 2026-03-29). The crawler uses the owning team's UUID to get complete per-game data. Entry points: `bb data crawl --crawler spray-chart`, `bb data load --loader spray-chart`.

**Spray chart auth exception**: Image routes (`/dashboard/charts/spray/player/{id}.png`, `/dashboard/charts/spray/team/{id}.png`) require an authenticated session but deliberately skip the `permitted_teams` authorization check. Reason: opponent players cannot pass `permitted_teams` but their spray data is legitimately viewable. This is a documented exception to the normal dashboard auth pattern.

## Reports Package

`src/reports/` is a self-contained package for standalone report generation. `generator.py` orchestrates crawl→load→gc_uuid resolve→spray crawl→spray load→plays crawl→plays load→reconciliation→query→render→write; `renderer.py` produces self-contained HTML files written to `data/reports/`. The plays stage is non-fatal (auth expiry caught, per-game error isolation). The reports serving route (`/reports/{slug}`) requires no authentication and is separate from the dashboard.

**In-memory crawl-to-load**: The report generator's scouting and spray stages use in-memory data flow (crawlers return data directly to loaders). Game discovery comes from crawl results, not filesystem globs or file-existence checks. This mirrors the scouting pipeline's in-memory pattern. See `.claude/rules/perspective-provenance.md`.

**Standalone report JS conventions**: Reports are self-contained HTML files with embedded `<script>` blocks for client-side enhancements (e.g., relative date display). JS in reports uses `var` (not `let`/`const`), targets elements by CSS class, and degrades gracefully (static content remains readable if JS fails).

**Report generation run record (`report_generation_runs`, migration 002)**: One WIDE row per report generation (NOT a per-stage child table) capturing per-stage status columns + per-stage counts + report-level trust flags, FK→`reports(id)` ON DELETE CASCADE, `UNIQUE(report_id)` (1:1 enforcer + idempotency key + admin-list join index). Mirrors the existing `scouting_runs` shape rather than inventing a new pattern: the stage set is fixed and the counts are heterogeneous, so a normalized child table would force generic `count_a/count_b` columns and a fan-out join. `reports` is intentionally NOT altered — it stays the thin artifact-identity row the public serve path reads; all trust flags live on the run record. This is the standard generation telemetry/audit trail and the storage foundation Epic E (morning-of-game scheduled, unattended report runs) builds on — a degraded report (half-loaded, spray-failed, zero-games) is indistinguishable from a complete one without it. New generation telemetry SHOULD extend this wide row, keeping recognizable per-stage column names.

**Per-run created-set orphan attribution (TN-4)**: To attribute orphan-team cleanup to a single generation run across a CROSS-PROCESS boundary (admin-UI + CLI + future cron all hitting one SQLite file), the generator tracks the set of team ids THIS run actually INSERTed — `self.created_team_ids`, fed by `EnsureTeamResult.inserted` at every `ensure_team_row` site (loaders record stubs they insert) — and cleans up only those (`orphan_ids = created_team_ids - {report_team_id}`). This replaces a global pre/post team-table snapshot diff, which would mis-attribute a concurrent run's teams. No DB lock, no migration, no snapshot — `inserted` (insert-vs-match) is the single signal.

## Reconciliation Package

`src/reconciliation/` is a post-load quality pass that cross-references plays data against boxscore data to detect and correct discrepancies (e.g., pitcher attribution errors). It reads from the DB (not raw API data) and operates after loaders have populated the database -- it does NOT belong in `src/gamechanger/`. Entry point: `reconcile_game(conn, game_id, dry_run=True)` in `engine.py` for per-game processing; `reconcile_all(conn, dry_run=True)` for batch. Discrepancy records are always written to `reconciliation_discrepancies` (migration 012); only corrections (e.g., `plays.pitcher_id` updates) are gated by `dry_run=False`. BF boundary correction algorithm: walks plays in `play_order`, assigns pitcher by boxscore appearance order and batters-faced counts; pitcher order extracted from cached boxscore JSON (not DB AUTOINCREMENT).

## LLM Package

`src/llm/` provides optional LLM integration via OpenRouter. `openrouter.py` uses plain `httpx.Client()` -- a documented exception to HTTP discipline (OpenRouter is a standard API, not GameChanger; no browser-identity headers needed). Env vars: `OPENROUTER_API_KEY` (required for Tier 2, absence = silent skip), `OPENROUTER_MODEL` (optional, canonical default `anthropic/claude-haiku-4.5` -- use the undated slug; the dated form `anthropic/claude-haiku-4-5-20251001` does NOT resolve to a live OpenRouter id; production overrides via `OPENROUTER_MODEL`). Future LLM integrations should reuse this client.

**JSON extraction (`json_extract.py`)**: `extract_json_object()` is a pure, HTTP-free, model-agnostic helper that recovers a JSON object from messy real-world LLM responses (bare, fenced, or prose-wrapped) via string-aware brace matching plus trial-parse; raises `LLMError` on unrecoverable input. Separation of concerns: `src/llm/` owns extraction (get a dict out of messy text); `llm_analysis.py` owns domain validation of that dict. Future Tier-2 integrations should reuse this helper rather than re-implementing JSON recovery.

**`response_format` request hardening**: `query_openrouter()` accepts an optional `response_format` pass-through (omitted from the request body when `None`); `enrich_prediction()` opts in with `{"type": "json_object"}` on both the initial call and the one retry. This is an additive belt-and-suspenders defense on top of the parser baseline -- the `extract_json_object` parser remains the model-agnostic baseline; never assume `response_format` alone is sufficient.

## Two-Tier Enrichment Pattern

Tier 1 (deterministic, pure Python, always runs) produces a typed dataclass. Tier 2 (optional LLM via OpenRouter, non-fatal) wraps the Tier 1 dataclass with narrative enrichment. Renderers select presentation path based on which dataclass they receive. New enrichment features should follow this pattern: deterministic first, LLM optional. **Operator-detectable Tier-2 status**: Tier-2 generation reports a cause-agnostic status (`success` / `unavailable-no-key` / `failed`) at log level so operators can distinguish "no API key" from a genuine enrichment failure without the absence of narrative being silently ambiguous.
