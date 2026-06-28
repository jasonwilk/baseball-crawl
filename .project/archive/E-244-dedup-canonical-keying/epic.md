# E-244: File Plays & Spray Under Canonical Game IDs After Cross-Perspective Dedup

## Status
`COMPLETED`
<!-- Lifecycle: DRAFT → READY → ACTIVE → COMPLETED (or BLOCKED / ABANDONED) -->

## Overview
When the report pipeline dedups a cross-perspective duplicate game, it redirects the boxscore to the existing canonical `game_id` (correct -- prevents double-counting), but the plays and spray stages are still keyed on the original source event IDs. Those source IDs no longer have a `games` row, so plays and spray rows are silently skipped for every deduped game, and reconciliation silently no-ops on them. This epic threads the dedup redirect map through to the plays, spray, and reconciliation stages so all per-game data is filed under the canonical `game_id` -- restoring full coverage for the scouted perspective's plays-derived rate stats (FPS%, QAB%, pitches/BF, pitches/PA) and the reconciliation that protects pitcher-attribution accuracy.

## Background & Context
The `GameLoader` deduplicates cross-perspective games using a natural key (`game_date` + unordered team pair). On a hit it redirects the boxscore to the existing canonical `game_id` and writes the per-player boxscore stats under that canonical id -- so boxscore stat coverage is complete (DB-confirmed: team_id=91 had 24/24 boxscore coverage). The defect is that the plays stage re-derives its game ids from `sorted(self.crawl_result.boxscores.keys())` (`src/reports/generator.py:1975`) -- the SOURCE (scouted-perspective) event IDs -- and the `PlaysLoader` FK guard (`src/gamechanger/loaders/plays_loader.py:193-197`) skips any game id with no `games` row. Result for team_id=91: plays coverage 22/24, with the 2 missing games being exactly the deduped ones (DB-confirmed: `plays WHERE game_id IN (60b49dd6,114c324e) AND perspective_team_id=91` = 0 rows).

Impact: the scouted perspective's plays-derived rate stats (FPS%, QAB%, pitches/BF, pitches/PA) are silently computed over a subset of games. There is no wrong number and no double-count -- a silent coverage hole in a flagship coaching stat (FPS% is the first stat coaches look at when scouting a pitching staff, per `.claude/rules/key-metrics.md`). The hole appears on any scouted opponent whose schedule contains a cross-perspective duplicate game.

The bug is pre-existing -- introduced by E-237 ("Payload-First Loaders") when the plays stage began keying off the in-memory boxscores dict, not by E-243. Per project rules, "pre-existing" is not a reason to leave it.

Two expert consultations (data-engineer, software-engineer) shaped the fix; see Technical Notes for the agreed seam, the consumers, and the divergence reconciliation.

**No new GC API behavior is assumed (no fresh api-scout consultation required).** Although the fix rests on the API property that plays/spray are fetched by SOURCE event_id and filed by canonical id, this epic does NOT change any crawl/fetch behavior -- it is load-keying only; the fetch stays by source event_id exactly as today. The relevant source-id fetch behavior was already validated by api-scout and is documented at `docs/api/flows/plays-ingestion.md` (`/game-stream-processing/{event_id}/plays`) and `docs/api/flows/spray-chart-rendering.md` (`/teams/{uuid}/schedule/events/{event_id}/player-stats`). The fix consumes that documented behavior unchanged, so it cites the existing api-scout validation rather than a new consultation.

## Goals
- Plays rows for a cross-perspective-deduped game are filed under the canonical `game_id` with `perspective_team_id` = the scouted team, joining the canonical games row the boxscore stats already occupy.
- Spray rows for a deduped game are likewise filed under the canonical `game_id`.
- Reconciliation runs against the canonical `game_id` for deduped games (so pitcher attribution is corrected, not silently skipped).
- The plays-derived rate queries (FPS%, QAB%, pitches/BF, pitches/PA) compute over full coverage for the scouted perspective (plays coverage matches boxscore coverage).
- Re-running a report does NOT re-fetch the PLAYS API for an already-loaded deduped game (the precheck remap finds the canonical id loaded), AND re-running inserts NO DUPLICATE spray rows under the canonical id (spray loader row-level idempotency under the now-canonical key). Note the asymmetry: the spray CRAWLER still hits the API on rerun (pre-existing behavior, out of scope -- do NOT add a spray pre-fetch gate); spray rerun-safety is row-level, not fetch-level. See Technical Notes TN-3.

## Non-Goals
- Changing the dedup natural key or the redirect behavior in `GameLoader` -- the dedup is correct and stays as-is.
- Touching the boxscore stat load path -- it already files under canonical ids (24/24 coverage) and is out of scope.
- Any change to `perspective_team_id` semantics -- this is load-keying only; perspective tagging is unchanged.
- Schema or migration changes -- there are none; `LoadResult` is an in-memory dataclass.
- Broadening reconciliation logic itself -- only the game id it is invoked with changes.

## Success Criteria
- A regression test built on a cross-perspective DEDUPED-game fixture (two source event IDs collapsing to one canonical id via `_find_duplicate_game`) proves: plays under canonical id, spray under canonical id, reconcile invoked for the canonical id, no plays API re-fetch on a second run (client call-count), and no duplicate spray rows under the canonical id on a second run (DB row-count -- NOT a spray client call-count, since the spray crawler re-fetches every run today). See Technical Notes TN-3/TN-6.
- For the deduped-game fixture, the plays-derived rate stats are computed over the full game set (the deduped game is included).
- The full pytest suite passes (`python -m pytest tests/`).

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-244-01 | Thread dedup redirect map to plays, spray, and reconciliation stages | DONE | None | software-engineer |

## Dispatch Team
- software-engineer

## Technical Notes

### TN-1: The defect, precisely
The dedup redirect happens inside `GameLoader` at `src/gamechanger/loaders/game_loader.py:589-600`: `canonical_id = self._find_duplicate_game(...)`, then `summary = replace(summary, event_id=canonical_id)`. Boxscore stats are subsequently upserted under the canonical id -- which is why boxscore coverage is complete. The plays and spray stages, which run later off `crawl_result` keyed by SOURCE event IDs, never learn of the redirect, so their FK guards skip the deduped games.

### TN-2: The seam -- producing and carrying the redirect map (data-engineer)
- **Origin**: accumulate a `{source_event_id: canonical_game_id}` map as a side-effect on the `GameLoader` instance. Populate it at the redirect site (`game_loader.py:589-600`) ONLY on an actual redirect, BEFORE the `replace()`. `GameLoader` is constructed fresh per report run, so the map is naturally scoped to one run with no reset needed.
- **Carrier (divergence resolved)**: data-engineer and software-engineer agreed on the origin and consumption but differed on the carrier (a new typed `LoadResult` field vs. a `GameLoader` attribute surfaced through `load_team`). Resolution: use a single typed carrier -- a new `redirect_map: dict[str, str] = field(default_factory=dict)` declared as the LAST field on the `LoadResult` dataclass (`src/gamechanger/loaders/__init__.py`, after `loaded`/`skipped`/`errors`). Use `field(default_factory=dict)`, NOT a bare `= {}` mutable default (which raises `ValueError` at class definition and leaks state across runs). `field` is already imported at `loaders/__init__.py:11`; all `LoadResult(...)` constructions use keyword args, so a trailing default is backward-compatible. The generator already holds the load result as `self.load_result` (set when `load_team` is called at `src/reports/generator.py:1701`).
- **Exposure**: `ScoutingLoader.load_team` assigns `result.redirect_map = game_loader.redirect_map` as a SINGLE assignment (the map is assigned/merged whole, NOT summed per-game like the int counts in `_load_boxscores_from_data`). The disk-flow counterpart (`_load_team_from_disk`) gets the same single assignment for parity. The assignment MUST sit AFTER the boxscore-load block: `load_team`'s early-return on `not crawl_result.boxscores` fires BEFORE `GameLoader` is constructed, and that early path correctly returns the default-empty map (relying on `default_factory`).
- The map MUST be the one `GameLoader` produced THIS run. The consuming stages MUST NOT recompute the redirect by calling `_find_duplicate_game` a second time (divergence risk). The remap target is FK-valid by construction: the canonical id is `_find_duplicate_game`'s return value, which is an existing `games.id`.

### TN-3: Consumers -- fetch by source, file by canonical (software-engineer)
The remap is a source→canonical translation applied between the API fetch and the DB write, so rows are filed under the canonical id. Both `PlaysLoader` and the spray loader derive their `game_id` solely from the in-memory dict KEY (never from the payload body), so the cleanest remap is a dict-key remap at the generator boundary (illustrative shape, not prescriptive: `{redirect_map.get(k, k): v for k, v in ...}`) before calling `load_payload` / `load_from_data`, leaving the loaders redirect-agnostic. (The implementer MAY instead remap inside the loaders immediately before their FK guards; either location is acceptable as long as rows land under canonical ids and the loaders' own idempotency prechecks see the canonical key. The generator-boundary dict-key remap is the recommended, simpler shape.)

**Plays stage** (`_crawl_and_load_plays`, `src/reports/generator.py:843`; called at `:1975`). The API FETCH must continue to use the SOURCE event ids (`game-stream-processing/{source_event_id}/plays` returns the scouted team's perspective -- the data we want). THREE additional sites must use the CANONICAL id:
1. **Idempotency precheck** (`generator.py:880-893`): remap to canonical, else every re-run re-fetches the API for every deduped game (the loader's whole-game idempotency at `plays_loader.py:204` still prevents duplicate rows, so this is an HTTP-discipline issue, not corruption).
2. **Reconcile loop** (`generator.py:952-963`): the `SELECT 1 FROM plays WHERE game_id=?` check and the `reconcile_game(conn, game_id, ...)` call both key off the game id. Under the bug they key off source ids, so reconcile silently no-ops on deduped games and pitcher attribution is never corrected -- degrading FPS%/pitch-count trust. Remap to canonical here.
3. **Return value** (`generator.py:973`, `return game_ids`): the returned list becomes `self.plays_game_ids` (assigned at `:1457` init, `:1969` reset, `:1973` from the return). It is consumed by EXACTLY three direct rate queries -- `_query_plays_pitching_stats`, `_query_plays_batting_stats`, `_query_plays_team_stats` (all filter `game_id IN (...)`) at `generator.py:2167-2173`. The footer coverage count `plays_games_covered` at `:2178` is NOT a separate direct consumer of `plays_game_ids` -- it rides on query #3 (`_query_plays_team_stats`), so it is fixed transitively. Remapping the RETURN value is the SINGLE propagation point that fixes all of these at once (no per-consumer change). The returned list MUST contain the CANONICAL ids, and MUST be DEDUPED -- two source perspectives can collapse to one canonical id, so a naive remap would put a duplicate id in the `IN`-clause. This site is REQUIRED, and is independent of and additional to the precheck (site 1) and reconcile-loop (site 2) remaps.

**Spray stage** (`_crawl_and_load_spray`, `src/reports/generator.py:749`; called at `:1929`). The crawl fetches by source event id (`src/gamechanger/crawlers/scouting_spray.py:178`, `event_id = game.get("id")`); the loader FK-guards at `scouting_spray_loader.py:253` and idempotency-checks at `:242` on the dict key. Apply the same dict-key remap of the spray data before `load_from_data`; the loader's in-loader precheck then sees the canonical key automatically (no separate generator-side spray precheck exists).

**Spray idempotency is row-level (loader), not fetch-level (crawler) -- important for the test**: the spray CRAWLER (`_fetch_spray_data`, `scouting_spray.py:160-212`) has NO pre-fetch DB idempotency check -- it re-fetches every completed game on every run TODAY (this is pre-existing and NOT created by this epic). Spray idempotency lives ONLY in the LOADER (`:242`), which dedups ROWS after fetch. Consequence for AC-6: "spray API not re-fetched on run 2" is FALSE and must NOT be asserted (a spray client call-count assertion would fail and tempt an out-of-scope spray-crawl precheck). The correct run-2 spray assertion is a DB row-count: no DUPLICATE spray rows under the canonical id (loader idempotency under the now-canonical key). Do NOT add a spray-crawl precheck -- out of scope.

**Plays/spray asymmetry (do NOT add a spray return remap)**: the spray side needs ONLY the one dict-key remap -- there is NO spray return-value remap to make. `_crawl_and_load_spray` returns a `_SprayOutcome` (status/counts), never a game-id list, and `_query_spray_charts` (`generator.py:665-674`) scopes by `team_id` + `chart_type` + `season_id` + `perspective_team_id` -- it does NOT take a game-id list. So once spray rows land under canonical ids, the spray query picks them up automatically (game-id-agnostic). The asymmetry is intrinsic: plays-derived queries scope by an explicit game-id list; spray queries scope by team/season/perspective.

### TN-4: Audit of other stages (resolves the "same bug elsewhere?" question)
The complete set of source-vs-canonical keying surfaces is: plays load, plays idempotency precheck, plays reconcile loop, plays query-scope (via the return value), and spray load. Reconciliation's batch entry (`reconcile_all`) reads game ids from the DB `games` table (canonical already) and is not in scope here; only the per-game `reconcile_game` invocation inside the plays stage is affected (covered above). The boxscore stat load is already correct (files under canonical internally). The audit story AC requires confirming no OTHER generator stage keys a DB write or idempotency check off the source `boxscores`/`crawl_result` ids.

### TN-5: Invariants to preserve
- Load-keying ONLY: `perspective_team_id` stays = the scouted team throughout; only the `game_id` the rows are filed under changes (per `.claude/rules/perspective-provenance.md`).
- Consumers default to identity for non-deduped games via `.get(src, src)` -- a report with zero dedups behaves exactly as today.
- Do not recompute the redirect in the plays/spray stages -- consume the map produced by `GameLoader` this run (TN-2).

### TN-6: Test obligation (software-engineer)
The regression fixture MUST include a cross-perspective DEDUPED game -- two source event ids that collapse to one canonical id via `_find_duplicate_game`. A single-event-id fixture passes vacuously and hides the bug. Idempotency assertions differ by stage: the run-2 PLAYS assertion is a client call-count (no re-fetch, via the precheck remap), while the run-2 SPRAY assertion is a DB row-count (no duplicate rows under the canonical id, via loader row-level idempotency) -- NOT a spray client call-count, because the spray crawler re-fetches every run today (see TN-3). See `.claude/rules/testing.md` for the disk-backed `db` fixture deadlock caveat (do not call `db.backup()` against a same-path connection) and the trustworthy-pytest-exit-code gotcha. Plays/spray tests live in `tests/test_report_plays.py`; generator-level tests in `tests/test_report_generator.py`.

## Open Questions
- None. Both expert consultations (data-engineer on the carrier seam; software-engineer on the fetch/load split, the three plays sites, and the spray symmetry) are resolved and incorporated above.

## History
- 2026-06-28: Created (DRAFT). Diagnosis supplied by main session; data-engineer and software-engineer consulted on the redirect-map seam and consumer threading.
- 2026-06-28: Refined and set READY (user-authorized). Two review iterations ran, every finding accepted (none dismissed). Internal iteration 1: CR spec audit + holistic data-engineer/software-engineer review -- the substantive finding was SE's AC-6 MUST-FIX (the original AC-6 wrongly asserted spray API is not re-fetched on rerun; spray rerun-safety is row-level in the loader, not fetch-level, because the spray crawler has no pre-fetch idempotency). Codex iteration 1: the substantive finding was the epic-body-vs-AC contradiction (the AC-6 split had not been propagated up to epic Goals/Success Criteria). Both classes fixed and swept.

### Review Scorecard
| Pass | Findings | Accepted | Dismissed | Substantive item |
|------|----------|----------|-----------|------------------|
| Internal iter 1 — CR spec audit | 7 | 7 | 0 | AC-2/AC-5 source-id negatives; AC-8 assertion-set widening (AC-4/AC-7); AC-9 pinned to durable story Notes with enumerated audit |
| Internal iter 1 — Holistic team (DE + SE) | 2 | 2 | 0 | SE MUST-FIX: AC-6 spray clause (row-level idempotency, not fetch-level); DE/SE: `field(default_factory=dict)` safe mutable default |
| Codex iter 1 | 3 | 3 | 0 | P1: AC-6 split not propagated to epic Goals/Success Criteria (body-vs-AC contradiction) |
| **Total** | **12** | **12** | **0** | — |

- 2026-06-28: COMPLETED. Single-story load-keying fix (E-244-01) threading the `GameLoader` dedup redirect map (the new `LoadResult.redirect_map` field) through the generator's plays stage (idempotency precheck, DB-write key, reconcile loop, and deduped return value) and spray stage (dict-key remap) so cross-perspective-deduped games file their plays/spray rows and run reconciliation under the canonical `game_id` instead of being silently FK-skipped under the orphaned source event ids. Restores plays-derived rate-stat coverage (FPS%, QAB%, pitches/BF, pitches/PA) for the scouted perspective. The fetch path is unchanged (still by source event id); this is load-keying only, `perspective_team_id` semantics untouched. Implemented by software-engineer; per-story CR, CR integration review, and Codex headless review all clean (0 findings); a 9-test deduped-game regression suite (genuine `_find_duplicate_game` collapse fixture) added. PM verified all 10 ACs PASS. Full suite green at SE's run (3414 passed, 0 failed); authoritative confirmation is the closure full-suite green gate.

### Closure Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|-------------|----------|----------|-----------|
| Per-story CR — E-244-01 | 0 | 0 | 0 |
| CR integration review | 0 | 0 | 0 |
| Codex code review | 0 | 0 | 0 |
| **Total** | **0** | **0** | **0** |

### Documentation Assessment
No documentation impact. This is an internal data-correctness fix: no admin/coaching docs change, and no `docs/api/` flow docs change (the fetch behavior is unchanged — load-keying only). No update trigger fires.

### Context-Layer Assessment (six-trigger)
- **Trigger 1 — new convention/pattern/constraint: YES.** New generator per-game stages must remap source→canonical via the dedup `redirect_map` before keying DB writes/idempotency/reconcile/query-scope off game ids. Codified by claude-architect this closure.
- **Trigger 2 — architectural decision with ongoing implications: NO.**
- **Trigger 3 — footgun/failure mode/boundary: YES.** Downstream per-game stages that key off `crawl_result`/`boxscores` SOURCE ids silently skip cross-perspective-deduped games (the E-244 defect, originally introduced by E-237). Codified by claude-architect this closure as a guardrail note.
- **Trigger 4 — agent behavior/routing/coordination change: NO.**
- **Trigger 5 — domain knowledge for future agents: NO.**
- **Trigger 6 — new CLI command/workflow/procedure: NO.**

Triggers 1 and 3 fire; claude-architect is being dispatched this closure to codify a concise guardrail note. The codification is in progress and will land in the closure patch.
