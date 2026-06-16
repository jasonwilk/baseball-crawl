---
name: season-aggregate-writers
description: THREE divergent writers compute player_season_batting/_pitching boxscore_only rows with disagreeing column sets; the gs-vs-w/l/sv footgun and the renderer-derived PA/XBH trap (E-237/Epic C discovery)
metadata:
  type: project
---

# player_season_* aggregate writers (verified 2026-06-16, E-237 Epic C planning)

**Fact (derivable from code, but non-obvious — took a full trace to surface).** There are
THREE writers of `player_season_batting`/`player_season_pitching`, and the two
`boxscore_only` writers DISAGREE on columns:

1. **ScoutingLoader** — `_compute_batting_aggregates`/`_compute_pitching_aggregates`
   (`src/gamechanger/loaders/scouting_loader.py:660-803`), called by
   `_compute_season_aggregates` (`:643`) at the END of `load_team` (`:159`), AFTER the
   Hook-1 dedup sweep (`:143`), committed once at `:160`. Perspective-filtered SUM
   (`perspective_team_id = team_id`). `stat_completeness='boxscore_only'` (column default).
   `INSERT … ON CONFLICT DO UPDATE` (its subset only). **This is the REPORTS flow.**
   - Batting (16): gp, games_tracked, ab, h, doubles, triples, hr, rbi, r, bb, so, sb, tb, hbp, shf, cs
   - Pitching (15): gp_pitcher, games_tracked, ip_outs, h, r, er, bb, so, wp, hbp, pitches, total_strikes, bf, **gs**

2. **player_dedup recompute** — `recompute_season_batting`/`recompute_season_pitching`
   (`src/db/player_dedup.py:798-944`) via `recompute_affected_seasons`, called by
   `dedup_team_players` (`:787`) for MERGED players only. Also `boxscore_only`, also
   perspective-filtered SUM, but **DELETE+INSERT** with a DIFFERENT set:
   - Batting ADDS pa, singles, xbh (ScoutingLoader omits)
   - Pitching writes **w, l, sv** (from `decision`) but **OMITS `gs`** — exact inverse.

3. **SeasonStatsLoader** — `_upsert_batting`/`_upsert_pitching`
   (`src/gamechanger/loaders/season_stats_loader.py:265+`). MEMBER flow only (NOT reports).
   Straight from season-stats API, `stat_completeness='full'`, full ~50-col wide set.

## The footgun
Because dedup (#2) runs BEFORE ScoutingLoader (#1) in `load_team`, a *merged* player ends up
with a HYBRID row (dedup's pa/singles/xbh/w/l/sv survive + ScoutingLoader's cols overwritten);
a *non-merged* player gets NULLs in those columns. → population of pa/singles/xbh/w/l/sv is
non-deterministic w.r.t. whether a merge happened. This is an integrity inconsistency, not
within-run staleness.

## Staleness reality (reports flow)
Aggregates are NOT stale within a generation run: no post-load stage mutates `player_game_*`
or merges players. gc_uuid resolve only `UPDATE teams`; spray only `spray_charts`;
`reconcile_game` only `plays.pitcher_id` + `reconciliation_discrepancies` (engine.py:1137,1240).
The one genuine remaining gap is crash-atomicity: per-game writes commit individually inside
`GameLoader.load_file` (`game_loader.py:321`), recompute commits separately at
`scouting_loader.py:160` — a crash between leaves committed game rows with stale aggregates
(self-heals on next run; payload-first single-transaction closes it).

## Canonical-column decision (E-237)
**Canonical boxscore_only set = ScoutingLoader's set, full stop.** Verified NO live reader of
pa/singles/xbh/w/l/sv anywhere (`src/api/db.py`, generator queries, renderer, templates).
TRAP CHECKED: the report template displays PA and XBH columns, but both are DERIVED in the
renderer — `_compute_pa` = ab+bb+hbp+shf (`renderer.py:95-102`); `_xbh` = doubles+triples+hr
(`renderer.py:164-169`) — never read from stored `pa`/`xbh`. Dashboard reads `tb` (written) and
pitching `hr` (COALESCE→0; boxscore_only can't populate it — ScoutingLoader deliberately omits
pitching hr, `scouting_loader.py:733-740`). So dropping the dedup-only columns is number-neutral
across reports + dashboard + profiles.

The parity guard `verify_aggregates` (`src/reports/aggregate_parity.py`) already diffs ONLY the
ScoutingLoader subset (`_BATTING_COLUMNS`/`_PITCHING_COLUMNS`, `:62-98`) and is the Epic C
cutover gate; it needs no change for the unification. Maintenance invariant at `:39-48`: if the
recompute contract changes, update the script AND `tests/fixtures/parity_consistent.sql` in
lockstep (fixture values hand-recomputed, never dumped from loader output).

`'supplemented'` stat_completeness is defined + ranked (`player_dedup.py:331`) but NO loader
ever writes it — inert. Recompute should treat full AND supplemented as member-owned (never
touch); don't drop the enum value (ripples into rank + parity member-scope exclusion).

See [[etl-patterns.md]].
