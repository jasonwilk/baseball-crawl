# Re-run / Accumulate-Only Data-Fidelity Audit — Master Tracked Record (2026-07-19)

**Status:** Durable tracking record. Every finding below is captured so it can be tracked if it bites — not just the promoted ones (operator directive, 2026-07-19).

## What this is

A read-only two-channel investigation triggered by an operator question: *"is there a bug where a subsequent run of a team is impacted by the fact that a run already exists?"* The theme: the scouting/report load pipeline is **ACCUMULATE-ONLY**. A second run (re-scout of the same team, report regeneration, or a morning-run over an already-loaded game) upserts what is IN the fresh payload but never reconciles what is MISSING from it — no per-run pass retires or refreshes rows that vanished or changed on GameChanger. Season aggregates derive at QUERY TIME from `player_game_*` via `get_season_batting` / `get_season_pitching` (`src/api/db.py`), so stale or duplicate rows silently corrupt them.

The only DELETE paths in the whole pipeline: team-delete cascade (`src/reports/lifecycle.py`), player-dedup merge (`src/db/player_dedup.py`), twin game-merge (`src/db/game_merge.py`). No loader does a set-difference / orphan-retire delete on any re-scout path.

## Validation methodology

- The 7 primary hazards (H1–H7) were each validated by TWO independent channels: Codex `gpt-5.6-terra` reasoning=xhigh (one adversarial review per hazard) AND an independent general-purpose subagent. Both channels converged on every hazard.
- The 10 corner cases (CC-1..CC-10) came from a single fable-model discovery sweep (single channel) EXCEPT CC-2, which is in the same two-channel validation as H1–H7 because it is the only new silent-correctness claim. **CC-2's disposition is finalized separately when the verdict lands** (see IDEA-153).

Legend — Verdict: CONFIRMED (real + reachable) / PARTIAL (real but narrower or hygiene-only) / REFUTED. Coach-facing = corrupts a number or view a coach sees. Hygiene = DB bloat / internal only, no coach impact.

Source ledgers (transient scratch, not in repo): the main session's `rerun-audit-ledger.md` and `hazards.md`. This file is the durable copy.

---

## Primary hazards (H1–H7) — two-channel validated

| ID | One-line | File:line anchor | Verdict (Codex / subagent) | Coach-facing? | Severity | Bites-if trigger | Disposition (tracker) |
|----|----------|------------------|-----------------------------|---------------|----------|------------------|-----------------------|
| H1 | Removed-player stat line persists in `player_game_batting`/`pitching` (UPSERT-only, no set-difference delete) → `get_season_*` SUMs stay inflated. | `game_loader.py:1423-1447,1484-1504,780,862`; `api/db.py` season readers | CONFIRMED/high · CONFIRMED/high | YES | Med-High | A player is dropped from a boxscore between two runs (scorekeeper deletes a mis-credited line) and the opponent is re-scouted. | **E-267** (player-line grain) |
| H2 | Departed players never leave `team_rosters` (INSERT/UPSERT-only, no prune); report roster grid renders ex-players indefinitely; `_validate_roster_count` only warns. | `scouting_loader.py:406-430`; `game_loader.py:1526-1565`; `generator.py:626-641` | CONFIRMED/high · CONFIRMED/high | YES | Med | A player is removed from the GC roster between runs and the team is re-scouted. | **E-267** (roster grain) |
| H3 | Plays & spray frozen at first scout (whole-game skip-if-any-row gate); post-charting edits, corrected pitch counts, partial-first-pass spray never refresh → plays-derived FPS%/QAB/P-PA drift from the boxscore that DOES upsert. NARROWED: uncharted→charted self-heals; freeze applies only to edit-after-charted + partial spray. | `plays_loader.py:141-152`; `scouting_spray_loader.py:183-192`; `generator.py:888-895` | CONFIRMED/high · CONFIRMED/high | YES (narrow) | Med | A game is re-scouted AFTER it was already charted once, and GC's chart changed (late edits / corrected counts / spray filled in). | **IDEA-146** (staleness-aware refresh; distinct mechanism) |
| H4 | `plays.batting_team_id` stale after a `games` home/away orientation correction; `_upsert_game` rewrites orientation unconditionally but frozen plays keep run-1 batting_team_id → swapped batting-side splits. | `game_loader.py:1370-1374`; `_resolve_home_away 568-573` | CONFIRMED/high · CONFIRMED/medium | YES (narrow) | Med | A real orientation flip occurs on re-run (most often `home_away=None`→resolved) on an already-charted game. | **IDEA-147** (re-derive on orientation change; overlaps CC-2 root) |
| H5 | `reconciliation_discrepancies` unbounded per-regeneration accumulation (fresh `run_id`=uuid4 per game per run; full signal row-set incl. MATCH re-written every regen; nothing prunes). Readers take latest-per-key so summaries SELF-HEAL → bloat, not corruption. | `engine.py:111-112,251-257`; `generator.py:964-975`; migration `001:536` | PARTIAL/high · CONFIRMED-bloat | NO | Low | Same games regenerated many times over a season; table grows linearly (bloat, never wrong output). | **IDEA-152** (hygiene cluster) |
| H6 | Renamed-opponent duplicate `teams` row + orphaned prior-run child anchors (name-only resolution misses a rename → new team row; per-run `_cleanup_orphans` only reaps THIS run's teams). REFUTED corruption: reports are `public_id`-anchored + subject-scoped, so stranded rows are never queried. | `teams.py:167-187`; `generator.py:2225-2251` | PARTIAL/high · PARTIAL/medium | NO | Low | An opponent renames on GC between runs; leaves an unqueried stranded team row (bloat only). | **IDEA-152** (hygiene cluster) |
| H7 | `season_id` drift orphans children (`teams.season_year` change moves `games` season, frozen children keep old `season_id`). COLLAPSED: only SPRAY vanishes (`_query_spray_charts` filters `spray_charts.season_id`); plays refuted (join fresh `games.season_id`); roster self-heals. | `generator.py:1664`; `game_loader.py:1371` | PARTIAL/high · PARTIAL/med-low | NO (spray only) | Low | `teams.season_year` changes between runs (calendar-year crossing / manual edit) under the current single-season scope. | **IDEA-152** (hygiene cluster; spray-only) |

---

## Corner cases (CC-1..CC-10) — single-channel fable sweep (CC-2 in two-channel validation)

| ID | One-line | File:line anchor | Coach-facing? | Severity / Likelihood | Bites-if trigger | Disposition (tracker) |
|----|----------|------------------|---------------|-----------------------|------------------|-----------------------|
| CC-1 | Game-grain no-retire: a GC-deleted/voided/un-finalized game persists forever in `_query_record` (W-L), season lines, recent form, freshness N (footer N can exceed schedule M). This IS IDEA-140's removed-game half, now confirmed coach-facing. **api-scout Probe 1 (2026-07-19, 633 live records) CLOSED the false-delete risk: GC KEEPS not-final/unplayed games in the schedule array, so absent-from-FULL-array = genuine removal — safe PROVIDED the reconcile diffs the full schedule, not `completed_games` (crawler `scouting.py:155`).** | `scouting_loader.py:246-248`; `game_loader.py:1363-1398` | YES | Med / low-med | A completed game is deleted/voided on GC after it was loaded, then the team is re-scouted. | **E-267** (game grain; folds into IDEA-140) |
| CC-2 | Cross-perspective redirect flips home/away while FREEZING the other perspective's scores → runs silently re-credited to the wrong team (`_upsert_game` COALESCE asymmetry: scores `preserve_scores`, team ids overwritten unconditionally). Corrupts W-L, recent form, runs-for/against on BOTH reports; poisons `batting_team_id`. **Two-channel CONFIRMED/high (2026-07-19), each with an executable in-memory repro through the real `ScoutingLoader`.** Precise locus `game_loader.py:1373-1378`; reachability = cross-perspective 2nd load (`preserve_scores=True` @:441) + `home_away=None` flip (@:568) + tolerant score-agnostic schedule-count redirect (@:1065) + non-tie. `game_stream_id` @:1391 is the correct keep-existing pattern. | `game_loader.py:1373-1378`; `_resolve_home_away 568-573` | YES | **High** / low | A game already loaded from one perspective is re-loaded from the opposite perspective and the redirect flips orientation while old scores stay frozen. | **IDEA-153 → E-268** (own targeted fix, READY 2026-07-19; CONFIRMED) |
| CC-3 | Jersey NULL-clobber: roster upsert overwrites jersey unconditionally incl. with NULL; boxscore path is backfill-only — divergent paths. A roster payload omitting `number` nulls a known jersey. | `scouting_loader.py:418-426`; `game_loader.py:1556-1565` | YES (minor) | Low / low-med | A roster re-scrape returns a player with `number` omitted after a prior run stored their jersey. | **IDEA-152** (hygiene cluster; unify the two upsert paths) |
| CC-4 | Player-name corrections that are NOT strictly longer are permanently blocked by the longer-name-wins ratchet; "Jon"→"Jim", wrong-long→correct-short never propagate; feeds LLM narrative too. | `players.py:41-64` | YES | Low-Med / low-med | A name is corrected on GC to something not strictly longer than what we already stored. | **IDEA-148** (coach-visible; cheap standalone) |
| CC-5 | ERA basis `innings_per_game` write-once: a mid-season 7→6 change never propagates; ERA computed on stale basis WITHOUT the "(assumed)" flag. | `teams.py:357-380` | YES (minor) | Low / low | A team's game length changes mid-season and the team is re-scouted. | **IDEA-152** (hygiene cluster) |
| CC-6 | Failed-after-HTML-write generations leak orphan HTML files no sweep reaps (failed row, NULL `report_path`, on-disk file). | `generator.py:2494-2519` | NO | Low / low | A generation fails after the HTML file is written but before the row is finalized. | **IDEA-152** (hygiene cluster; disk only) |
| CC-7 | Reports-row accumulation monotonically degrades the team-deletion cascade: `_live_report_perspective_ids` treats any reports row as a live dependency and nothing auto-deletes reports/`report_generation_runs`/`scheduled_report_runs` → over a season cascade-delete becomes progressively partial. | `lifecycle.py:363-381` | NO | Low / certain (steady-state) | Any team deletion late in a season after many report rows accumulated. | **IDEA-152** (hygiene cluster) |
| CC-8 | E-261 fail-closed residual: an un-merged twin `games` row (ambiguous-date fail-closed + score disagreement) double-counts in `_query_record`/recent-form/runs-avg (non-perspective-scoped game-level reads). Known territory (`bb data merge-duplicate-games`), new query-surface consequence. | (E-261 twin residual) game-level reads in `generator.py` | YES | Med / low | A cross-perspective twin the E-261 pass refused to merge exists at report time. | **IDEA-149** (relate to E-261 / E-267) |
| CC-9 | Outings card vs. headline FPS% read different plays scopes (this-run canonical game ids vs. whole-season) → same report, two different numbers when the DB carries a game this run's crawl no longer returns. Feature-flagged (`FEATURE_PITCHER_OUTINGS`). | `pitcher_outings.py:311-314` | YES (if flag on) | Low / low | The outings flag is ON and the DB holds a game the current crawl no longer returns. | **IDEA-150** (coherence) |
| CC-10 | Morning-run `opponent_links` resolve-once permanence: a wrong auto single-hit match, or a later coach re-link, is reused forever → wrong-team scouting report delivered every game morning until manual `bb report map-opponent`. | `opponent_ladder.py:329-368` | YES | Med-if-fires / low | A single-hit auto-resolve picks the wrong team, or a correct link later goes stale, and morning-run keeps reusing it. | **IDEA-151** (morning-run; design-adjacent) |

---

## Already-safe (recorded so we don't re-investigate)

- **LLM narrative**: not cached — `enrich_prediction` runs fresh every generation. Safe.
- **Pitcher workload/history/profiles**: pure query-time, no derived/cached tables. Safe (aside from CC-1 feeding them).
- **Spray cross-perspective double-count** in `_query_spray_charts`: neutralized by `perspective_team_id` filter + migration-009 UNIQUE. Safe.
- **`game_stream_id` clobbering**: fixed (COALESCE keep-existing + offline restore in `merge-duplicate-games`). Safe.
- **`scouting_runs`**: keyed UPSERT, no accumulation. Safe.
- **Morning-run double-generation**: guarded by `_prior_success` + 600s reservation lease. Safe (residual: >600s overlap = wasted duplicate, not corruption).
- **Concurrent admin-delete vs in-flight generation**: eligibility guard covers the pipeline; unguarded window is milliseconds. Theoretical only.
- **Serve route `/reports/{slug}`**: 404s stale/failed/expired, re-reads status per request `no-store`. Safe.
- **No "latest report" stale reads** — all listings ORDER BY `generated_at` DESC.

---

## Disposition map (which tracker owns each finding)

| Tracker | Findings owned | Kind |
|---------|----------------|------|
| **E-267** Reconcile-at-Load Against the Fresh Crawl (FORWARD-ONLY) | IDEA-140, CC-1 (game grain); H1 (player-line grain); H2 (roster grain) | READY epic (6 stories; DE-consulted 2026-07-19) |
| **E-268** Cross-Perspective Redirect Score-Misattribution Fix | CC-2 | READY epic (targeted fix) |
| **IDEA-146** | H3 | idea (coach-facing) |
| **IDEA-147** | H4 | idea (coach-facing) |
| **IDEA-148** | CC-4 | idea (coach-facing) |
| **IDEA-149** | CC-8 | idea (coach-facing) |
| **IDEA-150** | CC-9 | idea (coach-facing) |
| **IDEA-151** | CC-10 | idea (coach-facing) |
| **IDEA-152** | H5, H6, H7, CC-3, CC-5, CC-6, CC-7 | idea (accumulate-only hygiene cluster) |
| **IDEA-153 → E-268** | CC-2 | PROMOTED (two-channel CONFIRMED/high 2026-07-19) |
| **IDEA-134** (existing) | play-level cross-perspective duplication | cross-linked (hygiene, related family) |

## Cross-cutting requirement (operator directive, 2026-07-19)

1. **Durable record of ALL findings** — this file. Trackable if any bites, including the already-safe list.
2. **Every fix MUST ship regression tests** — a test that reproduces the corruption (fails pre-fix) and asserts the fix (passes post-fix). Baked into E-267 story ACs and IDEA-153's spec, and noted as a standing requirement in every idea file so it carries into any future promotion.
3. **Every ingestion change gated against the E-257 reconciliation-scoreboard ratchet** — `bb report reconcile-scoreboard` must not regress (no gated stat's abs-Δ increases, neither ratcheted axis counter increases, `self_games` stays 0). Baked into E-267.
4. **Removed-vs-transient corroboration (bias-to-refuse)** — any retire-absent machinery MUST distinguish a genuinely removed row from a transient/postponed/not-yet-final absence; a transient absence must NEVER delete live data (mirror `is_offline_same_game`'s bias-to-refuse). Owned by E-267's shared machinery.
5. **E-267 is FORWARD-ONLY (operator decision, 2026-07-19)** — prevention-at-load, reconcile as part of the normal re-scout. NO retroactive `bb data` pass and NO rewrite of already-loaded historical rows. Existing corruption is wiped for a clean slate — NOT repaired by the epic.
6. **Clean-slate = targeted purge, not report-mass-delete (operator option C, 2026-07-19; RESOLVED).** The `teams.is_active` cascade caveat is CONFIRMED: a mass report-delete does not clean-slate (a report-delete purges team data only when it is the LAST report for the team AND `is_active=0`, so `is_active=1` subject teams + children strand). Clean-slate is instead a new destructive CLI command (**E-267-06**) that FK-safe-purges all scouting/report data while PRESERVING user identity + auth (existing logins survive) — production-guarded via the canonical `is_production()` seam. Dev may alternatively use `bb db reset`; live uses E-267-06 to keep auth.

---
Created: 2026-07-19
