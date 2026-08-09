# Roadmap: Reports-First Architecture

**Date**: 2026-06-12 (rev 2 — review-hardened)
**Status**: EXECUTED — slices A–E are ALL COMPLETED and archived (see §0 Roadmap Tracking:
E-234/235/236/237/238/239/240). This document is retained as the reference record of the
reports-first reframe and its as-planned epic sequence. §4 (Cruft Inventory) and §5 (Proposed
Epic Sequence) are the AS-PLANNED record — the quarantine/removal verdicts and the D1/D2 plans
they describe have SHIPPED (D1 = E-238, D2 = E-239); read them as history, with §0 as the
authoritative current status. (Was `DRAFT` while the sequence was being planned.) The
epic/story/dispatch vocabulary throughout is the retired PM/epic/dispatch workflow's,
preserved as written; the live process is the chunk lifecycle in `CLAUDE.md`.
**Method**: Synthesized from parallel subagent surveys (reports critical-path trace, cruft
inventory, forward-path gap analysis, regression-guard design) plus the 2026-06-09/10
architecture assessments (pipeline accuracy, identity model, stability, backlog mining,
Codex cross-review). Rev 2 folds in: five live API probes (2026-06-12, api-scout), an
independent Codex (GPT-5.5 xhigh) architecture evaluation, and an adversarial Codex
review of rev 1 (8 findings, all accepted — see §5 epic deltas and §3 corrections).

---

## 0. Roadmap Tracking

*The convention and status ladder below governed this table while the roadmap ran; they
are recorded as they stood, not as live instruction. The live process is `CLAUDE.md`.*

Maps each roadmap slice (§5) to its epic and current status, so the roadmap evolves
as epics land. **Convention**: this table is updated at two moments — at an epic's
**planning commit** (slice → epic ID, status `PLANNING`) and at **epic closure**
(status `COMPLETED`). Each roadmap-derived epic also carries an explicit
`## Roadmap` reference back to the relevant §5 slice.

| Slice | Title | Epic | Status |
|-------|-------|------|--------|
| A | Regression guards for the reports flow | E-234 | COMPLETED |
| B | Report run records + trust signals + quality gates | E-235 | COMPLETED |
| B2 | Report self-reporting integrity hardening | E-236 | COMPLETED |
| C | Payload-first loaders + aggregate integrity | E-237 | COMPLETED |
| D1 | Quarantine + navigation retarget + passkey fix | E-238 | COMPLETED |
| D2 | Decouple imports, then remove unused surfaces | E-239 | COMPLETED |
| E | Morning-of-game scheduled reports | E-240 | COMPLETED |

Status values: `NOT STARTED` → `PLANNING` (epic DRAFT) → `READY` (epic refined,
awaiting dispatch authorization) → `IN PROGRESS` (epic ACTIVE) → `COMPLETED` (epic
archived). A slice may span more than one epic; add rows as needed.

---

## 1. The Reframe

The product, as actually used, is: **log in → generate a one-off scouting report for any
GameChanger public_id → share the link with coaches.** That flow is invaluable and works
today. Nothing else is used: no member-team sync browsing, no dashboard, no
tracked-opponent management, no schedule views.

The forward vision is narrow and concrete: **a scheduling system that generates a fresh
opponent report the morning of a game and gets it to coaches.** Until that exists, manual
generate-and-distribute is the product.

Every decision below is judged by one question: *does it make the report more accurate,
more reliable, or easier to deliver?*

---

## 2. Current State (evidence-based)

### What works
- `bb report generate <gc_url>` and `POST /admin/reports/generate` run an 8-stage
  in-memory pipeline (`src/reports/generator.py:987-1377`): team creation → report row →
  scouting crawl → load → gc_uuid resolve → spray → plays + reconciliation → query/render.
- Reports are frozen, self-contained HTML at `data/reports/{slug}.html`, served publicly
  at `GET /reports/{slug}` (no auth for viewers, 404 for expired/missing — no info leak).
- Failure isolation is already good: spray, plays, reconciliation, LLM Tier-2, and orphan
  cleanup all degrade gracefully rather than failing the report.
- Perspective provenance (E-220) is enforced at the schema level on all stat tables.
- ~4,500 tests pass; auth/token refresh with login fallback is mature.

### What's weak (carried forward from the 2026-06-09 assessment, reports-scoped)
- **No run record for report generation.** The `reports` row has status/error, but no
  per-stage visibility. A degraded report (spray failed, plays partial) looks identical
  to a complete one. Fine when an operator watches; fatal for unattended scheduled runs.
- **Ready-but-empty reports** (verified): `generate_report()` fails only on `errors > 0`.
  A team with zero completed games and zero errors (early season, wrong team) renders an
  empty report marked "ready". The `generator.py:1098-1102` gate does not cover this case
  — it is the crawl-FAILURE guard (`errors > 0 AND games_crawled == 0`); the
  zero-games/zero-errors path skips it and the empty "ready" report is emitted downstream
  at post-load render.
- **Orphan-cleanup concurrency race** (verified): `cleanup_orphan_teams()` deletes teams
  discovered after a pre-run snapshot (`generator.py:1652`) — two concurrent generations
  can delete each other's freshly created teams. Matters once scheduled runs generate
  several reports in one morning window.
- **Silent wrong-scope risks**: season derivation falls back to the current year on
  incomplete team metadata (`src/gamechanger/loaders/__init__.py:72`) — a transient
  public-profile failure can silently scope a report to the wrong season. Team identity
  falls back to name+season matching (`src/db/teams.py`) — can attach data to the wrong
  common-name team. (Note: the *current-year fallback itself* is usually benign in
  report-only mode — year-only scoping is the expected window for a single-season team;
  it is the E-235 trust-flag's coach-visible *interpretation* of that fallback as
  "degraded" that was under re-scope, per §4 and IDEA-077 — now **DECIDED (baseball-coach,
  2026-06-14, Option A): the coach-visible `season_fallback` degraded line is dropped**;
  the column stays as operator-only telemetry. The genuine risk here is the
  transient-failure path scoping to the wrong year, and the name-match identity fallback.)
- ~~**Stored season aggregates** (`player_season_batting/_pitching`) are computed at load
  time and can go stale within a generation run (player merges happen after aggregation
  in some paths) — and silently diverge after any post-load mutation.~~ **RESOLVED (E-259,
  2026-07-12):** the stored season-aggregate tables were dropped (migration 011) and the
  season line is now derived at query time from the per-game tables
  (`get_season_batting`/`get_season_pitching` in `src/api/db.py`), so there is no stored
  copy left to go stale or diverge.
- ~~**Loaders are Path-only, bridged by temp files** — in TWO places: the generator writes
  plays to a tempdir for `PlaysLoader.load_all(Path)` (`generator.py:598-609`), and
  `ScoutingLoader` internally writes boxscore JSON to temp files because
  `GameLoader.load_file()` is path-only (`scouting_loader.py:450-472`).~~ **RESOLVED (E-256-01, 2026-07-12):** the temp-file bridges were already removed by E-237, and the file-reading loader twin (`PlaysLoader.load_all`, `GameLoader.load_file`, `ScoutingLoader._load_team_from_disk`) was DELETED in E-256-01 — `load_payload`/`load_from_data` is now the sole loader entry path and no `src/` module reads `data/raw/`.
- **No trust signal on the report itself.** Coaches can't see "12 of 14 games loaded,
  spray unavailable, reconciliation clean."
- **Passkey challenges live in module globals** (`src/api/routes/auth.py:75-88`) —
  single-worker only, lost on restart mid-login. Auth IS used (operator logs in to
  generate), so this is a real, small bug.
- **No expired-report cleanup**: expired reports 404 but HTML files accumulate on disk.
- **No regeneration concept**: same team → new slug every time; no "latest report for
  this opponent." Interacts badly with scheduled delivery (a coach clicking Tuesday's
  emailed link after the 14-day expiry gets a 404).

### The big number
Roughly **25-30% of the codebase serves surfaces that are never used** (dashboard,
member-team sync orchestration, opponent-management admin UI, related tests). It is not
broken — it is weight: every refactor, review, and test run pays for it.

---

## 3. Protected Core (must not regress)

The reports flow depends on the following at RUNTIME. **Caution (adversarial-review
finding)**: runtime-unused is NOT import-decoupled — `src/api/routes/admin.py` (which
contains the reports routes) imports `src.pipeline.trigger` at module level
(`admin.py:83`), and `trigger.py` imports `crawl`/`load` at module level. Deleting
"unused" pipeline code without first decoupling those imports breaks app startup for
the reports admin surface. D2's decoupling story (below) exists for exactly this.

**Entry points**
- `src/cli/report.py` (`generate`, `list`)
- `src/api/routes/admin.py` reports section (`/admin/reports` list/generate/delete)
- `src/api/routes/reports.py` (`GET /reports/{slug}` public serving; auth exclusion in
  `src/api/auth.py`)

**Pipeline** (`src/reports/generator.py`)
- `ScoutingCrawler` / `ScoutingLoader` (in-memory crawl→load at the interface;
  internal temp-file bridge to `GameLoader` noted in §2)
- `ScoutingSprayChartCrawler` / `ScoutingSprayChartLoader`
- `PlaysLoader` + `src/gamechanger/parsers/plays_parser.py`
- `src/reconciliation/engine.py::reconcile_game` (perspective-scoped, dry_run=False)
- `src/db/player_dedup.py` post-load hooks
- Query layer: `_query_*` functions in generator.py + `get_pitching_workload`,
  `get_pitching_history`, `build_pitcher_profiles` in `src/api/db.py`
- `src/reports/starter_prediction.py` (Tier 1) + `src/reports/llm_analysis.py` /
  `src/llm/openrouter.py` (Tier 2, optional)
- `src/charts/spray.py` (base64-inline PNGs)
- `src/reports/renderer.py` + template **`src/api/templates/reports/scouting_report.html`**
  (rev 1 listed a nonexistent `report.html` — corrected) + **`src/api/helpers.py`**
  (report-critical Jinja filters: `format_avg`, `format_date`, `ip_display` — looks
  dashboard-owned by name; it is not)

**Shared infrastructure**
- `GameChangerClient`, token manager, credential parser, HTTP session/rate limiting
- `ensure_team_row()`, `ensure_player_row()`, `derive_season_id_for_team()`,
  `ensure_season_row()` — **but only the year-only/current-season slice of season
  derivation is protected.** A report is one team's *current* body of work; a `season_id`
  in report-only mode is just a within-report game filter ("which of this team's games
  belong in this one shared report"). The multi-season *machinery* layered on top —
  cross-season partitioning, season selection/comparison, longitudinal rollups, and the
  E-235 `season_fallback` *trust-flag interpretation* (treating year-only scoping as
  "degraded") — is NOT protected and is a removal/re-scope candidate (§4, §7, IDEA-077).
  Year-only scoping is the *correct, complete* window for the common single-season travel
  team, not a degraded condition. **(DECIDED 2026-06-14, baseball-coach: drop the
  coach-visible `season_fallback` degraded line entirely — Option A; see §4.)**
- `search_teams_by_name()` (gc_uuid bridge), `parse_team_url()`
- `cascade_delete_team()` / `cleanup_orphan_teams()` + the admin delete-confirmation
  mirror query (cleanup-detection mirror invariant)
- **App auth** (users, sessions, magic links, passkeys): the operator logs in to generate
  reports. The cruft survey misclassified this as unused — it is SUPPORTING. Only report
  *viewing* is auth-free. NOTE: auth success paths currently redirect to `/dashboard`
  (four sites in `auth.py`, root redirect in `main.py:133`, passkey templates, and the
  reports admin page's own nav) — see D1.

**Tables written/read**: teams, players, games, game_perspectives, player_game_batting,
player_game_pitching, ~~player_season_batting, player_season_pitching~~ (dropped in
migration 011, E-259 — season line derived at query time), team_rosters,
spray_charts, plays, play_events, reconciliation_discrepancies, reports, seasons,
programs (+ auth tables for the admin UI session).

**Not used by reports at runtime** (verified by call trace; import coupling caveat
above): member-team pipeline (`src/pipeline/crawl.py`, `load.py`, `bootstrap.py`, disk
cache `data/raw/`), `run_member_sync`, opponent discovery
(seeder/resolver/`opponent_links`/~~`team_opponents`~~ -- table dropped in migration 008,
E-250-02), schedule/roster/player-stats/
game-stats/season-stats member loaders, `crawl_jobs`, `scouting_runs`, `teams.yaml`,
dashboard routes/templates/queries, `user_team_access` gating (admin sees all).

---

## 4. Cruft Inventory & Verdicts

> **Executed (2026-07-08, E-255-06):** This inventory is the AS-PLANNED record. The
> `QUARANTINE → REMOVE` verdicts below were CARRIED OUT — D1 (E-238) quarantined and
> retargeted navigation, and D2 (E-239) removed the dashboard, member-sync, and
> opponent-management surfaces (−59k lines). The verdicts read in the future tense
> ("QUARANTINE → REMOVE") because they were written during planning; treat them as the
> record of what was decided and shipped, not as pending work. Table rows carrying dated
> "Update" annotations (e.g. `team_opponents` dropped in migration 008) reflect subsequent
> changes. §0 is authoritative for current status.

Policy: **quarantine before remove.** Quarantine = mark deprecated, stop maintaining,
exclude from new-feature parity requirements. Removal happens in a dedicated epic only
after regression guards are green. Never drop tables in the same epic that removes code.

| Subsystem | Verdict | Notes |
|---|---|---|
| Reports flow + scouting crawlers/loaders/plays/spray/reconciliation | **KEEP** | The product. |
| HTTP client, credentials, search bridge, canonical row helpers | **KEEP** | Foundation. |
| App auth (magic links, passkeys, sessions) | **KEEP** | Operator logs in to generate. Passkey-challenge fix is its own migration-backed story (see D1 delta). |
| `bb creds`, `bb status`, `bb db`, `bb report` | **KEEP** | Operator workflow. |
| `bb data reconcile` | **KEEP** | Same engine reports use; operator diagnostic. |
| `bb data dedup-players` | **KEEP** | Hooks run inside scouting loads; CLI form is the manual escape hatch. |
| `resolve_unlinked()` follow→bridge→unfollow path (`opponent_resolver.py:668`) | **QUARANTINE FIRST — highest priority** | Experimental path that POSTs follows on GameChanger (mutates external follow state) against `root_team_id` — the wrong namespace per verified API facts; the code's own docstring says unverified. Ban from Epic E explicitly. |
| Dashboard (`/dashboard/*`, ~8 templates, chart routes, ~30 test files) | **QUARANTINE → REMOVE** | Complete unused surface. Largest single cleanup (~8k LOC + tests). Removal REQUIRES D1's redirect retargeting first (login lands on /dashboard today). |
| Admin non-reports surface (team CRUD/merge, opponent resolution UI, sync buttons, user mgmt beyond what login needs) | **QUARANTINE → mostly REMOVE** | Keep: reports page, login, the delete-report path with its cascade. Removal REQUIRES D2's import decoupling first (reports routes live in the same module that imports the pipeline). |
| Member-team sync (`bootstrap/crawl/load.py`, disk cache, member crawlers+loaders, `run_member_sync`, `teams.yaml`, `crawl_jobs`) | **QUARANTINE** | Unused by reports at runtime, but import-coupled via `admin.py → trigger → crawl/load` — decouple before delete. The morning-of-game feature reads the own-team schedule from the authenticated schedule endpoint (or public games as fallback), not member sync. Decide REMOVE only after the scheduler epic confirms. |
| Opponent discovery (`opponent_links`, ~~`team_opponents`~~, seeder, resolver, `run_scouting_sync`, `bb data scout`) | **QUARANTINE** | Serves tracked-opponent flow operator never uses. `bb data scout` duplicates what reports do; the trigger.py/cli duplication problem dissolves if this is retired rather than unified. **Amendment 2026-06-12**: Epic E's opponent resolution ladder reuses the resolver's `progenitor_team_id` bridging logic — D2 must not delete that piece without Epic E's design settled. **Update 2026-07-05 (E-250-02)**: `team_opponents` (the table) has been DROPPED; `opponent_links` survives as Epic E's resolution ladder. |
| `bb data dedup`, `repair-opponents`, `bb data sync/crawl/load` | **QUARANTINE** | Member/opponent-flow maintenance commands. |
| `bb data backfill-appearance-order` | **QUARANTINE → DELETED by E-256** (E-256-02) | ~~It is a report-quality recovery path: `appearance_order` feeds pitcher GS aggregation (`scouting_loader.py:739`) and reports read `psp.gs`. Do not delete until production GS provenance is known clean or recomputed from fresh runs.~~ **Resolved 2026-07-12:** DE confirmed on the live DB that `player_game_pitching.appearance_order IS NULL` count = 0 (no backfill owed), so the command was removed in E-256-02 along with its module/script/test and all context-layer references (epic Technical Notes §15 eviction). |
| `gc_athlete_profile_id`, E-104, cross-team/multi-season identity work | **DE-SCOPED, REMOVED** | Explicit non-goal (§7). `gc_athlete_profile_id` was DROPPED from `players` in migration 008 (E-250-02); E-104 (the identity probe) is ABANDONED and archived (E-250-07). |
| Season-scoping / multi-season machinery (cross-season partitioning, season selection/comparison, longitudinal rollups) layered above year-only derivation | **DE-SCOPE → re-scope candidate** | The cross-season/rollup non-goals (§7) trace down to this machinery — it was load-bearing only for those now-dropped features. Report-only needs a season concept only as a *within-report game filter* (year-only/current scope). Name it as a removal candidate in the D-slice sweep; preserve only the year-only derivation the reports flow actually reads. See §3 protected-core note and IDEA-077. |
| E-235 `season_fallback` *trust-flag interpretation* (year-only scoping treated as coach-visible "degraded confidence") | **DECIDED: Option A (baseball-coach, 2026-06-14)** | **DROP the coach-visible `season_fallback` contribution to the footer degraded-confidence line; KEEP the `report_generation_runs.season_fallback` column as operator-only run-record telemetry** (still shown on `/admin/reports` — it just shouldn't drive anything coach-visible). Coach verdict: a single GC `public_id` does NOT blend multiple programs/levels within a calendar year (one GC team entity = one continuous program; HS-spring vs. summer-legion are separate teams with separate public_ids; travel orgs register each squad separately), so year-only scoping is essentially always correct and the `no program_type` trigger has *zero* correlation with real data-quality problems — it fires on the cleanest data (the 48/48 travel report) and would NOT fire on genuinely dirty data. The coach-visible "⚠️ Data accuracy may be limited" line is therefore harmful noise (erodes pre-game trust, generates unresolvable operator pings, costs the coach's pre-game cognitive budget). Option B (a real blend-detector) was explicitly REJECTED: "solves a problem that does not exist in the field — engineering effort for zero coaching value." Code implication (for whoever implements later): `degraded_confidence` drops the `season_fallback` term and keeps ONLY `identity_match_method == 'name_only'`; coverage severity stays its own separate N/M signal. Small follow-up — fold into Epic D or a small dedicated epic; tracked in IDEA-077. |
| Tables `opponent_links`, `scouting_runs`, `crawl_jobs`, `user_team_access`, ~~`team_opponents`~~, `coaching_assignments` | **QUARANTINE** | Inert tables are cheap; dropping requires cascade-logic rewrites. Revisit in the removal epic. **Inventory audit (2026-06-15 drift scour):** this list MUST be reconciled against the actual `_delete_team_scoped_data` DELETE set (`src/reports/generator.py:2197-2210`) when D2's cascade-rewrite story is written — the cascade deletes 9 tables; `coaching_assignments` (dead multi-user-permissions table, §7 non-goal) was missing from this row until the scour caught it. **`team_opponents` DROPPED in migration 008 (E-250-02)** — no longer inert, no longer present. |

**Estimated eventual reduction**: 15-18k LOC (~25-30%), plus ~5k LOC of tests, plus the
maintenance/parity burden those surfaces impose on every future epic (e.g., the
"delivery parity" and "pipeline parity" rules shrink to reports-only).

---

## 5. Proposed Epic Sequence

> **Executed (2026-07-08, E-255-06):** All of A–E SHIPPED and are archived — A=E-234, B=E-235,
> B2=E-236, C=E-237, D1=E-238, D2=E-239, E=E-240 (§0). The epic descriptions below are the
> AS-PLANNED specs (kept as the design record); where they read as future work ("D2 (removal,
> after A+B green…)", "FIRST story is…"), that work is DONE. §0 is authoritative for status.

Ordered smallest-safe-step first. Each epic lists risk and the guard that must be green
before it ships. Epics A and B are prerequisites for everything after them.

### Epic A — Regression guards for the reports flow *(do first; no behavior change)*
**Goal**: Make "we didn't regress reports" verifiable before any refactor.
**Scope**:
1. **Golden stat tables** (~200 LOC): seed fixture DB → run all `_query_*` functions →
   compare to golden JSON. Excludes timestamps, slug, LLM narrative. Catches stat-value,
   formula (ERA/WHIP/K9/OBP), and heat-level regressions.
2. **Aggregate parity script** (~150 LOC): diff stored `player_season_*` vs recomputed
   from `player_game_*` (perspective-filtered). Operator script + test.
3. **Subprocess smoke test** for `bb report generate` (catches packaging/import breaks).
4. **Negative-path tests**: no completed games, roster fetch failure, zero loaded games,
   auth expiry mid-run, public-profile fetch failure. (These also characterize current
   behavior for the Epic B gates.)
5. *(Stretch)* E2E fixture-driven generation test from recorded GC payloads — existing
   tests are mostly mocked and will not catch real GC payload drift.
**Builds on**: `tests/fixtures/seed.sql`, `conftest.load_real_schema()`, existing loader
test patterns, existing report tests (`test_cli_report.py`, `test_report_routes.py`,
`test_report_generator.py`, `test_report_plays.py`).
**Risk**: minimal — additive tests only. Main risk is golden files encoding a *current
bug* as truth; mitigate by hand-reviewing golden values once at creation.

### Epic B — Report run records + trust signals + quality gates *(stability + scouting impact)*
**Goal**: Every generation is auditable; every report tells coaches how complete it is;
degraded or empty outcomes are explicit, never silent.
**Scope**:
1. `report_generation_runs` (or extend `reports`): per-stage status — crawl, load,
   gc_uuid, spray, plays, reconciliation, enrichment — with counts (games expected vs
   loaded, plays games covered, discrepancies found/corrected).
2. Surface in the admin reports list (replace binary ready/failed with stage detail).
3. **Report footer trust block**: "Through {date} ({N} of {M} games) · plays data for
   {K} games · spray {available/unavailable} · {generated date}" — extends the existing
   game-coverage freshness philosophy.
4. **Hard quality gates** (new in rev 2):
   - **No-completed-games gate**: a crawl that returns zero completed games produces an
     explicit "no games yet" outcome, not a ready-but-empty report.
   - **Season-scope gate**: flag (in the run record and report footer) any report whose
     season was derived via the current-year fallback rather than team metadata.
     **DECIDED post-E-235 — Option A (baseball-coach, 2026-06-14; IDEA-077)**: in
     report-only mode year-only scoping is the correct, complete window, so this gate
     over-fires on the whole travel/USSSA class (no `program_type`) and was decided to be
     harmful noise on the coach-visible line. **Drop the coach-visible `season_fallback`
     degraded-confidence contribution; keep the `report_generation_runs.season_fallback`
     column as operator-only telemetry.** Coach confirmed a single GC `public_id` does not
     blend programs within a calendar year, so the flag is uncorrelated with real
     data-quality problems (a blend-detector, Option B, was rejected as zero coaching
     value). Code implication: `degraded_confidence` keeps ONLY
     `identity_match_method == 'name_only'`; coverage severity stays its own separate N/M
     signal. Small follow-up — tracked in §4 and IDEA-077.
   - **Identity gate**: flag any report whose team row was matched by name+season only
     (no public_id/gc_uuid anchor).
5. **Generation concurrency lock** (new in rev 2): one generation at a time, or
   run-scoped orphan cleanup — closes the `cleanup_orphan_teams()` race before Epic E
   multiplies concurrent runs.
6. Restructure `generate_report()` internals into named stage methods writing to the run
   record (no behavior change beyond the explicit gates above — same stages, same order,
   same non-fatal semantics, asserted by Epic A's negative-path tests).
**Risk**: low-medium. Restructuring the generator touches the protected core — Epic A
guards must be green; stage semantics must be preserved exactly and asserted in tests.
**Why before cleanup**: scheduled runs (Epic E) and safe refactors both need this
visibility.

### Epic B2 — Report self-reporting integrity hardening *(reliability; post-B, before C)*
**Goal**: The report never overstates its own completeness on the two surfaces that become
the SOLE trust signal once Epic E runs reports unattended — the operator run record and the
coach footer/no-games page. Epic B added those surfaces; this makes them HONEST.
**Scope** (implemented by E-236):
1. A unifying invariant + one shared `classify_stage_status` helper: no stage records
   "completed" when it had failures OR loaded zero of an expected non-zero set. Per-stage
   statuses gain a `partial` value; **plays/spray status is ERROR-driven, not
   coverage-driven** — a no-scorebook/no-chart game is the NORMAL case, not a degradation
   (this is the false-alarm class the §4/IDEA-077 `season_fallback` decision also targets).
2. Migration 003 adds per-stage count columns (`boxscores_fetched`, `load_errors`,
   `plays_errors`, `spray_games_with_data`) to `report_generation_runs` (extends Epic B's
   run record; additive, no stat tables touched).
3. Six self-reporting gaps closed: plays partial/loader failures (#1), partial boxscore
   crawl (#2), spray rows-vs-fetches (#3), the `season_fallback` coach-line (#4 — Option A
   per §4/IDEA-077), no_games M=0-vs-N=0 copy + CLI exit (#5), and the load-stage hardcoded
   status (#6).
4. All-boxscores-blocked → a hard `failed` outcome (no shareable page; operator alert),
   distinct from the benign `no_games` page ("we were blocked" ≠ "no data exists").
5. Admin run-record view surfaces partial/failed + a derived operator-"degraded" flag
   (operator-only; the coach footer is unchanged beyond #4/#5).
6. A degraded-opponent acceptance E2E asserts BOTH surfaces are honest in one test.
**Risk**: low-medium — telemetry/copy/status only, **NO stat-value changes**; touches the
protected core (`generator.py`), so Epic A goldens + aggregate parity must stay green
(asserted in the spec).
**Why here (post-B, before C)**: it builds on B's run record and makes the trust signals
honest before Epic E removes the human backstop; C/D/E inherit the corrected telemetry.

### Epic C — Payload-first loaders + aggregate integrity *(accuracy)*
**Goal**: Remove the temp-file bridges and the stale-aggregate class inside the
protected core.
**Scope** (resized per adversarial review):
1. Payload-first loaders — BOTH bridges: `PlaysLoader.load_payload()` (deletes the
   generator's tempdir bridge) AND a `GameLoader` boxscore payload path (deletes
   `ScoutingLoader`'s internal temp-file bridge). `load_all`/`load_file` become
   file-reading wrappers.
2. Aggregates: **recompute-atomically at the end of every load is the default option**
   (keeps the `player_season_*` tables — required because dashboard/scouting surfaces
   still query them until D2 removes those surfaces; `src/api/db.py` reads them in at
   least five query families). The replace-with-views option is DEFERRED until after
   D2. Sequencing note: if D2 lands first, revisit and simplify.
**Risk**: medium. Derived numbers can diverge from previously stored ones where stored
rows were stale or were sourced differently (the member season-stats loader writes full
API aggregate columns; `ScoutingLoader` recomputes a smaller boxscore-derived subset —
semantics must be made explicit per surface). **Gate**: Epic A's parity script must run
on real data (production DB copy) before cutover; every mismatch is investigated —
each is either a bug found (good) or a semantic gap (handle explicitly). Golden stat
tables must not change.

### Epic D — Quarantine sweep, then removal *(cleanup; two epics)*
**D1 (quarantine + navigation retarget)**: mark dashboard, member-sync, and
opponent-discovery surfaces deprecated — banner comments, README note, exclude from
parity rules, stop routing new work to them. **Quarantine the follow→bridge→unfollow
resolver path first** (it mutates external GC state). **Retarget all navigation away
from `/dashboard`** → `/admin/reports`: root redirect (`main.py:133`), four auth.py
success-path redirects, passkey prompt/register templates, the reports page's own nav
link, and pass `is_admin_page` on `/admin/reports` so the base template's dashboard nav
does not render. Add expired-report file cleanup. **Passkey challenge store fix is its
own story** (SQLite challenge table with TTL — a migration plus login regression
checks; this is protected-core auth work, not comment cleanup).
**Risk**: low (was "near-zero" in rev 1 — raised because redirect retargeting and the
passkey migration touch the operator's actual login path; both need explicit login →
generate → share verification).
**D2 (removal, after A+B green and D1 has soaked)**: FIRST story is the import-graph
audit AND decoupling: split the reports admin routes out of `src/api/routes/admin.py`
(or make the `trigger` import lazy) so deleting pipeline modules cannot break app
startup (`admin.py:83 → trigger.py:35` chain, verified). THEN: delete dashboard
routes/templates/tests; delete member-sync orchestration + member-only crawlers/loaders
+ their CLI commands + `teams.yaml`; trim admin to login + reports + the delete cascade.
**Also in scope for D2: the cross-season / multi-season scoping machinery** (cross-season
`season_id` partitioning, season selection/comparison, longitudinal rollup code — §4, §7),
keeping only the year-only/current-season derivation the reports flow reads
(`derive_season_id_for_team()`'s year-only path). This is the season-scoping half of the
"trace the non-goal down to the machinery" item; scope the exact removable surface in the
D2 planning session (it is not yet inventoried at the file/function level). Tables stay
(inert) unless trivially droppable. ~~`backfill-appearance-order` survives
until GS provenance is clean (§4).~~ **Update 2026-07-12 (E-256-02):** `backfill-appearance-order` was DELETED — DE confirmed the live-DB `appearance_order` NULL count is 0, so GS provenance is clean and the recovery path is unneeded. Other verified shared seams to guard:
`src/api/helpers.py` (report filters), `src/charts/spray.py` (serves both surfaces),
report-delete cascade's reuse of admin team-deletion helpers.
**Risk**: D2 medium — pure deletion under guard, but only after the decoupling story.
Run full suite + golden guards + a real report generation against production data
before merging.

### Epic E — Morning-of-game scheduled reports *(the forward feature)*
**Goal**: Coaches get a fresh opponent report link the morning of every game.
**Design changes from review (rev 2)**: cron-invoked CLI instead of in-process
APScheduler; authenticated schedule instead of public-only; resolve opponents from the
schedule, not the registry. Estimate resized: this is a real epic (schema + CLI +
resolution + delivery + status), not the rev-1 "~150-300 LOC".
**Scope**:
1. **Own-team schedule reading**: authenticated `GET /teams/{team_id}/schedule` — its
   `pregame_data.opponent_id` joins directly to the opponents registry (the public games
   endpoint carries free-text names only and survives as the no-auth fallback; verified
   2026-06-12 that it does return upcoming games). Teams configured by public_id;
   resolve to gc_uuid via the search bridge. Verify fan-level access to the schedule
   endpoint early (registry access at fan level is verified; the schedule endpoint at
   fan level is assumed — confirm in the epic's first story).
2. **Resolve from the SCHEDULE, not the registry** (probe finding): the opponents
   registry is cumulative/historical — most registry names map to no current game.
   Per upcoming game: take `pregame_data.opponent_name` + `opponent_id`, join
   `opponent_id → root_team_id` in the registry, read that record's
   `progenitor_team_id`. Never feed `opponent_id` to `GET /teams/{id}` (wrong
   namespace).
3. **Resolution ladder** per opponent, persisted in an `opponent_name → public_id`
   mapping so each opponent is resolved once:
   a. `progenitor_team_id` present → `GET /teams/{progenitor_team_id}` returns
      `public_id` directly (verified for non-managed teams; the
      `public-team-profile-id` endpoint 403s for non-managed — do not use it). Fan/
      follower role suffices for the registry (verified on all four LSB teams) — the
      operator only needs to FOLLOW a team for this rung. `progenitor_team_id` is
      *absent (key omitted)*, not null, on manual entries.
   b. **Placeholder deferral** (probe finding): no structural flag exists — classify by
      name pattern (`TBD|TBA|Winner|Loser|Seed|Game \d|Pool|Bracket|Tournament|
      Invitational|Classic|Showcase`) → defer and re-poll near game time, don't ask the
      operator. Observed share: ~6% of manual entries; GC never retroactively relabels
      them.
   c. `POST /search` by name (gc-uuid bridge quirks apply) — auto-ingest only on an
      unambiguous single match, after dropping organization hits and hits from a
      different season year (implemented 2026-08-09; fail-closed on a missing
      year on either side). Name source: the `name` from `GET /public/teams/...` or
      the registry entry, never URL-slug text (slug search returns 0 hits). Expect this
      rung to fail for most manual entries: they are typically teams ABSENT from GC's
      search index entirely (HS varsity programs like "Bellevue West").
   d. Otherwise: queue for operator input in the admin UI, **accepting a pasted GC team
      URL** (the same input `bb report generate` takes); answer stored in the mapping,
      asked once per opponent. Opponents with no GC presence → "no report possible" on
      the schedule, never a silent skip.
   **Observed ratios (5 teams, 2026-06-12)**: 27%–100% search-linked; LSB four-team
   aggregate 64% linked; placeholders ~6% of manual entries (immaterial: 64%→65%
   effective auto). Rung (a) resolves roughly two-thirds automatically on a typical LSB
   team; the ask-once queue handles the rest. **Cross-team borrowing does NOT work**
   (verified negative: 15 shared names, 0 recoverable) — don't build it.
4. **Scheduler**: a cron-invoked CLI — `bb report morning-run [--date YYYY-MM-DD]
   [--dry-run]` — run by host cron/systemd/container scheduler. No APScheduler, no
   long-lived in-process scheduler (simple-first; survives app restarts; no new runtime
   dependency). Preflight credential refresh; fail early and visibly. Per-game
   independence: one opponent's failure never blocks another. Each run records to the
   Epic B run table: date, own team, opponent text, resolved public_id, report slug,
   delivery status, error. Idempotent per (team, opponent, date) — safe to re-run.
   **Never use the follow/bridge/unfollow path.**
5. **Freshness/expiry semantics**: delivered links must outlive the morning — either
   extend expiry for scheduler-generated reports, or implement "latest report per
   opponent" with stable URLs. Decide in the epic; do not ship scheduled delivery with
   silently expiring links.
6. **Delivery**: extract a generic Mailgun sender from the magic-link-specific
   `src/api/email.py` (hardcoded subject/body today); operator failure alerts first,
   coach `report_subscriptions` second. Admin page shows the morning run's status
   (Epic B surfacing).
7. **Version gotcha**: `GET /me/teams` (role/team enumeration) requires
   `Accept: ...team:list+json; version=0.10.0` — an older version string returns a
   FALSE 403 easily misread as auth expiry.
**Risk**: medium — unattended execution is exactly where silent failures bite, which is
why Epic B precedes it. Sequential generation (rate limits); a missed morning run must
page the operator, not vanish.

#### Operator-session design decisions (2026-06-13)
Settled in conversation with the operator; bind the Epic E planning session. They keep
the forward feature **admin-free** — no team-management or opponent-registry UI (consistent
with the §7 non-goal on tracked-opponent surfaces).

1. **Team list = inline in the crontab (no admin, no config file).** The morning run is a
   single invocation that takes the operator's own teams as args and iterates them
   **sequentially**:
   ```
   0 6 * * *  bb report morning-run <varsity-url> <jv-url> <fresh-url> <reserve-url>
   ```
   The crontab line *is* the config — zero new storage, edited once a season. **Never
   multiple concurrent invocations (one per team)**: that re-introduces the
   `cleanup_orphan_teams()` race the Epic B concurrency lock closes, duplicates credential
   refreshes, and breaks rate-limit coordination. One process, sequential generation. (Move
   to a small text/YAML team file only if editing the crontab becomes a burden — a new file,
   not a reuse of the quarantined `teams.yaml`.)

2. **Opponent mapping = a CLI command keyed on `root_team_id`, not the typed name.** The
   unresolved opponent has no `public_id` yet (finding it is the task), and its free-text
   name is the least reliable field in the system — coaches type opponent names by hand with
   no GC lookup (the documented duplicate-opponent root cause), so "Bellevue West" vs
   "Bellevue West HS" vs a typo would each be a different key and silently miss an existing
   mapping. Key the mapping on the schedule's stable registry identifier instead:
   ```
   bb report morning-run --dry-run
     → Varsity vs "Bellevue West"  [opponent_id: a1b2c3…]  UNRESOLVED
   bb report map-opponent a1b2c3… <public_id | GC team URL>
     → stored: root_team_id a1b2c3… → public_id; auto-resolves every future game.
   ```
   Both values are copy-paste (the `opponent_id` off the dry-run line, the target from GC) —
   no quoting, no name-matching. The **target** accepts a bare `public_id` or a full team URL
   (the URL is just `.../teams/<public_id>`). The name still *displays* for confirmation but
   is not the key. **Storage**: a dedicated `root_team_id → public_id` lookup table.
   `root_team_id` is a separate namespace from `gc_uuid` — it is a fine mapping key but MUST
   NOT land in a `gc_uuid` column (CLAUDE.md "Opponent entry duality").

3. **Three-way outcome — never a silent skip.** Every scheduled opponent resolves to exactly
   one of:
   - **auto-resolved** — rungs (a)–(c) of the §5 item-3 ladder; report generated.
   - **unresolved-but-mappable** — on GC but not auto-matched (typical for HS varsity absent
     from GC search); surfaced in `--dry-run` and the Epic B run record for one-time
     `map-opponent`. Resolved once, cached forever; the queue shrinks across a season.
   - **no GC presence** — no `public_id` exists, a report is impossible; marked "no report
     possible" on that game so the absence is explained, never silently dropped.

4. **Admin-free surfacing.** Unresolved opponents appear in `--dry-run` output and the Epic B
   run record (shown on the existing `/admin/reports` page). The only thing that would push
   this back toward a management UI is letting coaches (not the operator) resolve names —
   out of scope.

### Deliberately dropped from the old roadmap
- ~~Shared scouting runner unifying trigger.py/cli scout~~ — both copies serve the
  quarantined opponent flow; retirement beats unification.
- ~~E-104 athlete-profile probe / cross-team identity~~ — de-scoped (§7).
- ~~Games natural-key UNIQUE constraint~~ — breaks doubleheaders; post-run assertions
  (Epic B quality counts) cover it instead.
- ~~Auto-executing dedup merges in pipeline~~ — detection runs automatically and is
  *reported* (Epic B); destructive merges stay behind review (sibling false-positive
  risk: "J Smith"/"Jake Smith").
- ~~In-process APScheduler~~ — replaced by cron-invoked CLI (rev 2).

---

## 6. Safety Rules for All of the Above

*These six rules governed the roadmap while it ran; they are recorded as they stood, not
as live instruction. The live process is `CLAUDE.md`.*

1. **No epic that touches the protected core ships without Epic A guards green** plus a
   manual report generation against real data, eyeballed against the prior output.
2. **Quarantine before remove; code before tables; decouple imports before deleting
   modules.** Two separate epics, soak time between.
3. **Every spec carries its risk section** — the parity-diff gate (Epic C), the
   import-decoupling story (Epic D2), redirect retargeting (D1), and stage-semantics
   preservation (Epic B) are acceptance criteria, not suggestions.
4. **Anything that could change report stat values is flagged loudly** in the story and
   verified against goldens — never assumed safe.
5. **Login → generate → share is the canary path**: D1's redirect/passkey stories and
   every D2 deletion verify it end-to-end before merging.
6. Normal workflow applies: each epic goes through "plan an epic for X" → codex spec
   review → READY → explicit dispatch authorization.

---

## 7. Explicit Non-Goals (so future sessions don't rebuild them)

- **Cross-team player identity** (athlete_profile_id population, player tracking across
  programs, cross-program blending of one player's record). Per-team identity is
  sufficient for scouting reports.
- **Cross-season / multi-season / longitudinal anything.** No multi-season rollups, no
  multi-year analytics, no season-over-season comparison, no longitudinal player or team
  tracking, no recency-tapering across seasons. Each report is one team's *current* body
  of work, generated fresh. **This non-goal applies all the way down to the machinery,
  not just the user-facing feature**: cross-season `season_id` partitioning, season
  selection/comparison logic, and multi-season rollup code are removal candidates (§4),
  because `season_id` was the load-bearing partition key for exactly these now-dropped
  capabilities. Report-only needs season only as a within-report game filter — year-only
  / current scope is sufficient and is the *expected, complete* window for a single-season
  team, never a "degraded" one. (Surprised this wasn't caught at the 2026-06-12 reframe:
  the non-goals were declared at the feature level but never traced down to the
  season-scoping machinery or the E-235 `season_fallback` trust flag — IDEA-077.)
- **Member-team season-management product** (dashboard browsing, roster/season stat
  pages, schedule UI). The schedule *data* need is met by the authenticated schedule
  endpoint (public games endpoint as fallback).
- **Tracked/followed opponent management as a product surface.** Reports are generated
  on demand (or on schedule) for whoever is next; no standing opponent registry UI.
  (GC-side "following" a team to enable fan-level registry reads is just configuration,
  not a product surface.)
- **Multi-user team-scoped permissions.** One operator generates; coaches consume public
  links (later, emailed links).
- **Distributed job infrastructure** (Redis/Celery) and in-process schedulers. Host cron
  invoking a CLI is the ceiling until reality demands more.

*Vision-signal note: this reframe (reports-first; member/dashboard surfaces de-scoped;
morning-of-game delivery as the forward feature) supersedes parts of docs/VISION.md
Layers 2-4 and should be processed at the next "curate the vision" session — this file
is the signal; VISION.md is deliberately untouched.*

---

## 8. Suggested Order of Operations

```
A (guards)  →  B (run records + gates + lock)  →  B2 (self-reporting integrity)  →  C (payload-first + aggregates)
                     ↓                                                                       ↓
              D1 (quarantine + redirects + passkey)  →  D2 (decouple imports, then remove)
                     ↓
              E (scheduled morning reports)   ← needs B (+ B2 honesty); benefits from C/D
```

A is a half-day-to-day epic. B is the keystone — it serves stability today, trust
signaling for coaches, and is the foundation E builds on. C and D2 have a soft ordering
dependency (C's view option waits for D2; C's recompute option doesn't) — final order is
an epic-planning decision. D2 is the only high-LOC epic and is pure deletion under
guard, gated by its decoupling story. E is the payoff.
