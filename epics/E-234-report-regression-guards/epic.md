# E-234: Report Regression Guards

## Status
`READY`
<!-- Lifecycle: DRAFT → READY → ACTIVE → COMPLETED (or BLOCKED / ABANDONED) -->

## Roadmap
- **Roadmap reference**: `docs/ROADMAP.md` §5 — **Epic A: Regression guards for the reports flow** (reports-first reframe, rev 2, 2026-06-12).
- This is the first epic of the roadmap sequence (A → B → C → D1 → D2 → E). Epics A and B are prerequisites for everything after them.
- Roadmap progress is tracked in the **Roadmap Tracking** table near the top of `docs/ROADMAP.md` (established as a planning deliverable of this epic — see Technical Notes §TN-6).

## Overview
Build a verifiable regression-guard layer around the standalone reports flow so that "we did not regress reports" becomes a green/red test result before any refactor (Epics B–E all touch the protected core). The guards are **additive tests plus one new operator-facing parity module** — no behavior change to the existing reports pipeline.

## Background & Context
The reports flow (`bb report generate` / `POST /admin/reports/generate` → `src/reports/generator.py` → frozen HTML at `data/reports/{slug}.html`) is the product as actually used (ROADMAP §1). Every subsequent roadmap epic refactors or deletes code that the reports flow depends on at runtime (ROADMAP §3 protected core). Today there is no fast, deterministic way to prove a refactor preserved report stat values, formulas, and aggregate integrity. ROADMAP §6 safety rule #1 makes Epic A's guards a hard precondition: **no epic that touches the protected core ships without these guards green.**

The reports pipeline already has strong test mock seams (`tests/test_report_generator.py` patches `ScoutingCrawler`/`ScoutingLoader`/`GameChangerClient`/`_crawl_and_load_spray`/`_crawl_and_load_plays`), an existing hand-computed fixture (`tests/fixtures/seed.sql`), and a schema loader (`tests/conftest.py::load_real_schema()`). This epic builds on those rather than inventing new harness infrastructure.

Two domain consultations grounded the plan:
- **software-engineer** (test-harness design): golden-file mechanism, credential-free subprocess smoke, negative-path mock seams, stretch-E2E feasibility.
- **data-engineer** (aggregate-parity semantics): the two-discriminator scoping (`stat_completeness` row scope + SUM-column subset), exact perspective mirroring, and the `gs` NULL-safe trap.
- **api-scout**: not consulted — story 05 (the only API-adjacent story) uses recorded payload fixtures, not live API behavior; endpoint sequencing/shapes are already documented (see TN-5 for the explicit skip rationale).

**New process requirement (user, this epic):** epics must be tied to the roadmap, and `docs/ROADMAP.md` must track progress as epics land. Handled by §TN-6.

## Goals
- A golden-stat-table test that runs the full report query surface against a seeded fixture DB and fails on any stat-value, formula (ERA/WHIP/K9/OBP), or heat-level regression.
- An aggregate parity module (`src/reports/aggregate_parity.py`) + operator command (`bb report verify-aggregates`) + test that diffs stored `player_season_*` against a perspective-filtered recompute from `player_game_*`, reusable as the Epic C cutover gate.
- A credential-free subprocess smoke test for `bb report generate` that catches packaging/import breaks.
- Negative-path characterization tests that pin current behavior (including the known ready-but-empty case) as the before-anchor for Epic B's quality gates.
- `docs/ROADMAP.md` carries a lightweight slice→epic→status tracking table and an update-cadence convention.

## Non-Goals
- **No behavior change to the reports pipeline.** No fixes to the ready-but-empty bug, the orphan-cleanup race, season-scope fallback, or stale aggregates — those are Epic B/C. Story 04 *characterizes* the current (buggy) behavior; it does not fix it.
- No new test-harness framework, no golden-file library, no new runtime dependency. Simple-first: committed JSON + a plain helper.
- No fix of any real staleness the parity command surfaces against the production DB — those are findings that feed Epic B/C, not Epic A work.
- No member/dashboard-surface guards. Scope is the reports flow only (ROADMAP reframe).
- Convention *codification* (a rule that all future epics reference the roadmap) is deferred to the closure-time context-layer assessment, not a story (§TN-6).

## Success Criteria
- All stories DONE; full suite green at closure (`python -m pytest tests/` → 0 failed).
- The golden test passes on the seed fixture, and the parity test passes on its purpose-built `tests/fixtures/parity_consistent.sql` fixture, both with hand-reviewed values (no current bug or staleness encoded as truth — §TN-1, §TN-2).
- `bb report verify-aggregates` runs as a real operator command and returns an empty mismatch list on a clean DB.
- `docs/ROADMAP.md` shows E-234 mapped to Epic A with the correct status, and the update convention is stated.

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-234-01 | Golden stat tables for the report query surface | TODO | None | - |
| E-234-02 | Aggregate parity module + `bb report verify-aggregates` | TODO | None | - |
| E-234-03 | `bb report` subprocess smoke tests | TODO | None | - |
| E-234-04 | Report-generation negative-path characterization tests | TODO | None | - |
| E-234-05 | (Stretch) E2E fixture-driven report generation from recorded payloads | TODO | None | - |

## Dispatch Team
- software-engineer
- data-engineer

## Technical Notes

### TN-1: Golden stat tables (story 01)
- **Fixture**: reuse `tests/fixtures/seed.sql` (TEAM_VARSITY/JV across 2 seasons; hand-computed expected values already in its header). Load via `tests/conftest.py::load_real_schema()`.
- **Collector**: a helper that runs every `_query_*` in `src/reports/generator.py` (`_query_team_info`, `_query_record`, `_query_batting`, `_query_pitching`, `_query_recent_games`, `_query_runs_avg`, `_query_freshness`, `_query_roster`, `_query_spray_charts`, and the plays-stats queries) **plus** the `src/api/db.py` families the report consumes (`get_pitching_workload`, `get_pitching_history`, `build_pitcher_profiles`), assembling one dict.
- **Determinism (required)**: the collector MUST pass `get_pitching_workload` a FIXED `reference_date` anchored to the fixture's game dates (e.g. the season's last game date), NOT the default `None` — `reference_date=None` uses today, making `last_outing_days_ago`/`pitches_7d`/`span_days_7d` drift daily and the committed golden rot overnight. These are integer stat values, so "normalize-out timestamps" does NOT cover them. (`get_pitching_history`'s `rest_days`/`team_game_number` are season-relative and deterministic — no change needed.)
- **Exclusions**: normalize-out (drop or zero) timestamps, `slug`, `generated_at`, and any LLM/Tier-2 narrative **before** comparison.
- **Golden storage**: committed `tests/fixtures/golden/report_stats.json`. The **test never writes the golden** — it loads and deep-equals. Regeneration is a separate, explicit path (a standalone `scripts/regen_report_golden.py` is preferred over a pytest addoption to avoid coupling `tests/conftest.py`); regen rewrites the JSON so the change surfaces in `git diff` and is gated by code review. This is the anti-silent-overwrite mechanism. The regen script is a dev-only tool (not an operator script) and is exempt from the `tests/test_script_entry_points.py` `--help` subprocess convention.
- **Anti-bug-as-truth + observable review**: hand-review the golden values once at creation against the seed.sql header math (do not encode a current bug as the golden), and record that review as an OBSERVABLE artifact — the golden JSON carries a top-level `_meta` provenance object (`reviewed_by`, `reviewed_date`, `basis: "seed.sql header math"`) that the normalizer strips before comparison (same treatment as timestamps). The `_meta` block makes the hand-review checkable in `git`/code review rather than merely asserted.
- **Coverage scope (be honest in the AC)**: seed.sql has NO `spray_charts`/`plays`/`play_events` rows, so the golden captures EMPTY results for `_query_spray_charts` and the plays-stats queries — those surfaces get a shape/no-crash guard only, NOT value-regression coverage. Story 05's e2e is the value guard for spray/plays. Story 01's AC must state this rather than imply full coverage. (seed.sql is NOT extended here — it is shared by existing query tests; see TN-2's fixture caution.)
- **Data-layer boundary**: the golden guards `_query_*` OUTPUT (stat values/formulas), NOT `renderer.py`/`scouting_report.html`. HTML rendering is covered by existing `test_report_renderer.py`/`test_report_rendering.py` (+ story 05 end-to-end). Do not over-trust the golden as a full reports guard.

### TN-2: Aggregate parity (story 02) — data-engineer semantics
Home (SE+DE aligned): reusable logic in `src/reports/aggregate_parity.py` (the import-boundary rule forbids `src/` importing `scripts/`, so logic must live in `src/`); operator entry point `bb report verify-aggregates` in `src/cli/report.py` (`bb report` is a KEEP surface; `bb data` is quarantined under the reframe). The test imports the `src/reports/aggregate_parity.py` function directly.
- **Row scope**: diff only rows with `stat_completeness = 'boxscore_only'` (confirmed `NOT NULL DEFAULT 'boxscore_only'` on `player_season_batting`/`player_season_pitching` in `migrations/001_initial_schema.sql`). ScoutingLoader rows take that default; member season-stats-loader rows (`full`/`supplemented`) come straight from the API, are not summed from game rows, and must be excluded.
- **Column set**: diff only the SUM-computed subset that `ScoutingLoader._compute_*_aggregates` writes.
  - Batting (16): `gp`, `games_tracked`, `ab`, `h`, `doubles`, `triples`, `hr`, `rbi`, `r`, `bb`, `so`, `sb`, `tb`, `hbp`, `shf`, `cs` (`gp == games_tracked == COUNT(*)`).
  - Pitching (14): `gp_pitcher`, `games_tracked`, `ip_outs`, `h`, `r`, `er`, `bb`, `so`, `wp`, `hbp`, `pitches`, `total_strikes`, `bf`, `gs` (`gp_pitcher == games_tracked`). **Pitching `hr` is deliberately NOT stored — do not diff it.**
  - **Exclude** all member-season-stats-only columns (`pa`, `singles`, splits, qab/hard/weak/ps/sw, home/away + vs-LHP/RHP). The exclusion reason is **provenance, NOT NULL-ness**: these columns are not part of the ScoutingLoader SUM subset (they are written by the member season-stats loader or carry split provenance), so they are out of scope whether NULL or populated. (seed.sql actually populates some split columns on `boxscore_only`-default rows — a further reason not to use seed.sql for this guard; see the fixture spec below.) Rate stats (AVG/OBP/ERA/WHIP) are not stored — nothing to diff.
- **Recompute query**: mirror `_compute_*_aggregates` EXACTLY — `WHERE pgX.team_id = ? AND g.season_id = ? AND pgX.perspective_team_id = team_id`, `JOIN games g ON game_id`, `GROUP BY player_id`. Replicate the `gs` NULL-safe CASE verbatim (`MAX(appearance_order) IS NULL → NULL`, else `SUM(appearance_order = 1)`). Treat `NULL == NULL` as a match; `NULL` vs non-`NULL` is a mismatch.
- **Reporting shape**: per `(player_id, team_id, season_id, column)` with `(stored, recomputed)` values; **exact integer equality, no tolerance**; empty mismatch list = clean. The function also returns a `cells_compared` count (rows compared × diffed columns) so the test can assert it examined `> 0` cells — guarding against a vacuous green if the row-scope filter or the join matches zero rows.
- **Green-path fixture — independent oracle (story 02 uses its OWN fixture, NOT seed.sql)**: the clean-green case runs against a purpose-built `tests/fixtures/parity_consistent.sql` whose stored `player_season_*` rows are the EXACT perspective-filtered SUM of its `player_game_*` rows. Those expected values are **hand-authored independently of the recompute code** (per testing.md test-validates-spec), so the green path verifies the recompute query is actually correct — not merely that two copies of the same SUM agree. (A loader-built fixture was rejected: it would make the "stored" side a near-copy of the recompute logic, passing by construction even if that shared logic — gs CASE, perspective filter, a dropped column — were wrong.)
- **Epic C anchor**: this module IS the Epic C cutover gate, and Epic C refactors ScoutingLoader/GameLoader internals. The static SQL fixture is a fixed anchor that must survive Epic C untouched — a guard for a loader refactor must be independent of loader internals. seed.sql is NOT used and is NOT mutated (it is shared by story 01's golden and existing OBP/K-9 query tests).
- **Lock-step maintenance invariant (review-enforced, NOT test-enforced)**: the parity test never runs ScoutingLoader, so it cannot detect loader-semantic drift on its own (that is the job of story 01's golden and story 05's e2e, which exercise real output). Therefore, on any change to `_compute_*_aggregates` that alters the aggregate CONTRACT (a SUM-subset column added/removed, or the `gs` definition), update BOTH the recompute query AND `parity_consistent.sql`'s expected values in lock-step — and the updated fixture values MUST be hand-recomputed independently from the game rows, NEVER regenerated by dumping loader output (which would silently convert this into the rejected loader-built approach and lose the independent-oracle property). This is a manual invariant enforced by code review.
- **Staleness is a real finding, not a false positive**: post-load player-dedup merges that run *after* aggregation re-point game rows to the surviving `player_id` while the stored season row reflects the pre-merge grouping → recompute diverges. The guard exists to catch exactly this. On the **clean `parity_consistent.sql` fixture** (no post-load mutation) the test is exact-green; an **operator run against production** may surface staleness → that is an Epic B/C finding, not an Epic A fix. No fixture may bake current staleness in as "expected."

**`parity_consistent.sql` fixture spec (DE-supplied, exact rollup-consistent values).** Scaffolding: 1 team T, season `2026-spring-hs`, 3 games `PG_1/PG_2/PG_3` (each `season_id='2026-spring-hs'` + all NOT NULL games columns), batters PB_01/PB_02, pitchers PP_01/PP_02/PP_03. **Every game stat row: `perspective_team_id = team_id = T`.** Season rows leave `stat_completeness` unset (→ default `boxscore_only`) and populate ONLY the diffed SUM-subset columns (NO split/home-away columns — faithfully models real ScoutingLoader `boxscore_only` output).
- Batting game rows (ab, r, h, doubles, triples, hr, rbi, bb, so, sb, tb, hbp, shf, cs):
  - PB_01: PG_1 = 4,1,2,1,0,0,1,1,1,1,3,0,0,0; PG_2 = 3,2,1,0,0,1,2,2,0,0,4,1,1,0; PG_3 = 4,0,1,0,1,0,0,0,2,1,3,0,0,1.
  - PB_02: PG_1 = 4,0,1,0,0,0,0,0,2,0,1,0,0,0; PG_2 = 3,1,1,1,0,0,1,1,1,0,2,0,0,0; PG_3 = 4,1,2,0,0,0,1,0,1,1,2,1,0,0.
- Batting expected season rollup (gp = games_tracked = 3):
  - PB_01: ab11 h4 doubles1 triples1 hr1 rbi3 r3 bb3 so3 sb2 tb10 hbp1 shf1 cs1.
  - PB_02: ab11 h4 doubles1 triples0 hr0 rbi2 r2 bb2 so4 sb1 tb5 hbp1 shf0 cs0.
- Pitching game rows (appearance_order, ip_outs, h, r, er, bb, so, wp, hbp, pitches, total_strikes, bf):
  - PP_01 (start+relief): PG_1 = 1,18,5,3,2,2,7,1,1,85,55,24; PG_3 = 2,6,1,0,0,0,3,0,0,28,20,7.
  - PP_02 (two starts): PG_2 = 1,21,4,1,1,1,5,0,0,92,60,26; PG_3 = 1,15,7,4,4,3,4,2,1,78,48,23.
  - PP_03 (gs-NULL branch): PG_1 = NULL,12,4,2,2,1,3,0,0,50,32,15.
- Pitching expected season rollup (gp_pitcher = games_tracked = appearance count):
  - PP_01: gp_pitcher2 ip_outs24 h6 r3 er2 bb2 so10 wp1 hbp1 pitches113 total_strikes75 bf31 **gs=1** (one appearance_order=1).
  - PP_02: gp_pitcher2 ip_outs36 h11 r5 er5 bb4 so8 wp2 hbp1 pitches170 total_strikes108 bf49 **gs=2** (two appearance_order=1).
  - PP_03: gp_pitcher1 ip_outs12 h4 r2 er2 bb1 so3 wp0 hbp0 pitches50 total_strikes32 bf15 **gs=NULL** (its only appearance has appearance_order NULL → MAX IS NULL → gs NULL).
- PP_01 is the key row (games_tracked=2 but gs=1 — proves gs counts STARTS not appearances and exercises the non-NULL CASE branch); PP_03 covers the NULL branch.
- **Injected-divergence (AC-5)**: mutate PP_01 stored `gs` 1→5 and assert exactly one mismatch `(PP_01, gs, stored=5, recomputed=1)`.

### TN-3: Subprocess smoke (story 03) — software-engineer
`generate_report()` hits the network immediately, so the smoke MUST NOT call real generation. Two credential-free, network-free layers added to the existing subprocess pattern in `tests/test_cli.py` (the `_bb_installed` skipif block, ~lines 256-320):
1. `subprocess.run(["bb", "report", "generate", "--help"])` → exit 0, output contains a stable substring (e.g., `gc_url` / `Generate`). This is the packaging/import canary.
2. `subprocess.run(["bb", "report", "generate", "not-a-valid-url-@@@"])` → `parse_team_url()` raises `ValueError` and returns failure **before any network call** (`generator.py:1000-1003`), so the CLI exits non-zero with the error printed. Asserts the failure path is wired through the real entry point. No mocks injected into the child process.

### TN-4: Negative-path characterization (story 04) — software-engineer
Mock seams already exist in `tests/test_report_generator.py` (patch-at-module-level: `GameChangerClient`, `ScoutingCrawler` + `scout_team.return_value`/`.side_effect`, `ScoutingLoader` + `load_team.return_value`, `_crawl_and_load_spray`, `_crawl_and_load_plays`, `get_connection`). 4 of 5 cases are clean at the generator boundary:
- **No completed games / zero loaded**: `scout_team.return_value = ScoutingCrawlResult(team_id=<varsity team id>, season_id="2026-spring-hs", games_crawled=0, errors=0, games=[], boxscores={})` (illustrative — `team_id` and `season_id` are required positionals with no defaults; omitting them raises `TypeError`). This is the ready-but-empty case: a crawl returning zero games with **zero errors** passes BOTH error-gated guards — the crawl-failure guard at `generator.py:1098-1102` fires only on `errors > 0 AND games_crawled == 0`, and the load guard only on `errors > 0` — so generation proceeds to the post-load render step and emits a "ready" but empty report (NOT the `1098-1102` branch, which the rev-1 spec mis-cited as the ready-but-empty location). The test asserts **current behavior** (renders "ready") and is explicitly labeled as the before-anchor for Epic B's no-completed-games gate — it does NOT assert desired behavior.
- **Auth expiry mid-run**: already covered by existing tests; extend to assert which stages did/did not run.
- **Public-profile fetch failure**: patch `src.http.session.create_session` (imported inside `generate_report`) to return a session whose `.get` raises or returns non-200; assert graceful degradation.
- **Roster-fetch failure** belongs one layer down (inside `ScoutingCrawler.scout_team`) → implement as a `ScoutingCrawler` unit test in `tests/test_scouting_crawler.py`, not a generator test.

### TN-5: Stretch E2E (story 05) — software-engineer, CUTTABLE
Feasible per SE: recorded payloads exist (`data/raw/` cached crawler JSON + `tests/fixtures/game-plays-fresh.json`). A true E2E mocks only the HTTP transport (respx-style, keyed per-URL across the sequenced schedule→boxscore→roster→spray→plays calls) and drives `generate_report()` end to end — the only guard that catches GC payload-shape drift (existing tests mock the crawler/loader and cannot). Scope to **ONE recorded game-set for ONE team** — prove the transport-mocked path, expand later. `data/raw/` is only the AUTHORING-TIME source for building the fixture (on a dev machine); the sanitized payloads are committed under `tests/fixtures/e2e/` and the test reads ONLY from there at runtime — never `data/raw/` (gitignored, absent in worktrees/CI). The committed fixture MUST be curated for PII/credentials (strip any auth headers/tokens per the security rule) before commit. **Oracle**: the e2e asserts a NAMED stat set — team W-L record, ≥1 batting season line, ≥1 pitching season line, and ≥1 plays-derived stat (e.g. FPS%) if present in the chosen game-set — against expected values **hand-computed from the chosen recorded payloads at fixture-curation time** and committed alongside the fixture; the implementer does NOT invent the oracle. **api-scout consultation — explicitly skipped (option a)**: story 05 uses RECORDED payload fixtures, not live API calls, so there is no live API-behavior question; the endpoint sequencing (schedule→boxscore→roster→spray→plays) and payload shapes are already documented in `.claude/rules/architecture-subsystems.md` (scouting pipeline) and `docs/api/`. No consultation was fabricated; the user may override at READY presentation and request a real api-scout consult. **If fixture curation balloons the story beyond a single session, cut it and convert to an idea** (per planning honesty) rather than padding the epic.

### TN-6: Roadmap tracking mechanism (planning deliverable, NOT a story)
Per the user's roadmap-tying requirement and the lead's direction, the tracking mechanism is established by the PM directly during planning (a planning-artifact edit, not implementation code):
- (a) **Epic→roadmap reference**: this epic's `## Roadmap` section names `docs/ROADMAP.md §5 Epic A`. This is the convention for every roadmap-derived epic going forward.
- (b) **Roadmap status table**: a lightweight table near the top of `docs/ROADMAP.md` mapping slices A–E → epic ID → status, plus a one-line convention note: *updated at planning commit (slice → epic ID, status PLANNING) and at epic closure (status COMPLETED).* Added directly as part of this planning commit; no new tooling.
- **Convention codification** (a rule binding future epics to reference the roadmap and update the table) is deferred to the **closure-time context-layer assessment** — claude-architect evaluates whether to codify, rather than carrying a story here.

### TN-7: Cross-cutting
- All stories are additive: new test files, one new `src/reports/` module, one new `bb report` subcommand, one new fixtures dir. Zero change to existing reports-pipeline behavior.
- No real network or credentials in any test (testing rule). Mock at the HTTP/seam layer.
- Stories are file-independent (see each story's Files list) → no ordering dependencies; dispatch order is free. The only fixture either touched is seed.sql, which **story 01 reads read-only** (it does not modify it) while **story 02 uses its own new `tests/fixtures/parity_consistent.sql`** — so no two stories share a mutable file. (seed.sql must NOT be mutated: existing OBP/K-9 query tests and story 01's golden both depend on its current hand-authored values.)

## Open Questions
- **Command name** (RESOLVED): `bb report verify-aggregates` — approved by team-lead in Phase 3 (follows the existing `bb` command-group convention; SE+DE aligned on the `src/reports/aggregate_parity.py` home). The user retains veto at READY presentation.
- **Story 05 inclusion**: kept as a clearly-cuttable stretch story (SE judged it feasible). If the user wants Epic A kept to a half-day, cut 05 to an idea at READY time.

## History
- 2026-06-12: Created (DRAFT). Discovery + se/de consultations complete; incorporated into Technical Notes.
- 2026-06-12: Reviewed (internal iteration 1: CR spec audit + holistic self/SE/DE; then Codex iteration 1). Combined triage: all findings ACCEPT, 0 DISMISS; incorporated in two one-pass edits, each followed by a consistency sweep (the second caught and fixed 1 drift). Set **READY**.

### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 — CR spec audit | 5 | 5 | 0 |
| Internal iteration 1 — Holistic team (self+SE+DE)¹ | 12 | 12 | 0 |
| Codex iteration 1 | 5 | 5 | 0 |
| **Total (raw reported)** | **22** | **22** | **0** |

¹ Holistic raw = self 4 + SE 5 + DE 3. The 17 internal findings (CR 5 + holistic 12) deduped to **12 distinct actionable items (T1–T12)**; T1 (parity fixture not rollup-consistent) alone had **4 independent sources** (self F1 + DE Finding 1 + SE Blocker 1 + CR F1). Codex's 5 (C1–C5) were distinct from the 12. Zero dismissals across all passes; "checked & sound" validations (e.g. story-03 AC-2 `parse_team_url` ValueError-before-network) are not counted as findings.
