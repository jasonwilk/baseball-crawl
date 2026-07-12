---
name: season-aggregate-writers
description: ONE canonical boxscore_only recompute since E-237-03 (src/db/season_aggregates.py); history of the prior THREE divergent writers, the gs-vs-w/l/sv hybrid-row footgun it fixed, and the renderer-derived PA/XBH trap
metadata:
  type: project
---

# UPDATE (E-237-03 DONE, 2026-06-16): boxscore_only recompute is now CONSOLIDATED

The two divergent `boxscore_only` writers (#1 ScoutingLoader + #2 player_dedup) below
were collapsed into ONE canonical module-level function:
**`src/db/season_aggregates.py::canonical_recompute(conn, team_id, season_id)`**.

- Scope = `(team_id, season_id)`: DELETE all `boxscore_only` rows for the scope, then INSERT
  every player (GROUP BY player_id). Perspective-filtered (`perspective_team_id = team_id`).
- Writes the **Option B superset** = ScoutingLoader's parity-checked subset (batting 16; pitching
  14 incl `gs`) PLUS the dedup-derived extras (batting pa/singles/xbh; pitching w/l/sv) for EVERY
  player → hybrid-row non-determinism is gone.
- **Provenance guard**: only `boxscore_only` rows are deleted/written. A player that already owns a
  `full`/`supplemented` row for the scope is EXCLUDED from the INSERT (NOT EXISTS guard) → member
  rows survive intact. This also fixed the latent dedup DELETE+INSERT data-loss bug.
- Wiring (TN-11): `ScoutingLoader._compute_season_aggregates` is now a 1-line delegate to it;
  the two embedded load-path dedup calls pass `recompute_aggregates=False` (new kwarg on
  `dedup_team_players`) so the canonical recompute runs EXACTLY ONCE per load, committed with the
  dedup sweep. Standalone `recompute_affected_seasons` (CLI `bb data dedup-players`) keeps its
  signature but now reduces affected tuples to distinct `(team_id, season_id)` scopes and calls
  `canonical_recompute`. The per-player `recompute_season_batting`/`recompute_season_pitching`
  functions were REMOVED. **(Verified against current `src/` 2026-07-08:** the live
  `canonical_recompute` callers are `src/gamechanger/loaders/scouting_loader.py`,
  `src/db/player_dedup.py`, and `src/cli/data.py` (via `recompute_affected_seasons`). The former
  member-sync Hook-2 driver `trigger.py` was DELETED in E-239 and no longer exists in `src/`.)
- Parity guard column set + `parity_consistent.sql` fixture UNCHANGED (TN-7 did not fire —
  superset's parity-checked subset == ScoutingLoader's old set). Stale doc comments repointed.
- **COUPLING (Codex P1, fixed E-237-03 round 1):** the provenance guard means a member
  `(team_id, season_id)` scope can now legitimately hold BOTH a `full` row (member player) AND
  `boxscore_only` rows (other players) — a *mixed* scope that did not exist before. `verify_aggregates`
  (`aggregate_parity.py::_check_table`) recomputes EVERY player in a scope from per-game rows, so it
  MUST mirror the canonical NOT EXISTS guard with a **per-player** exclusion: drop players who own a
  `full`/`supplemented` row in THAT table+scope from the recompute comparison, else the preserved
  member player (per-game rows present, no boxscore_only stored row) surfaces as a synthetic
  `stored=None` mismatch. The pre-existing `member_scopes` exclusion only handled WHOLE-scope
  (zero-boxscore_only) member scopes — insufficient for mixed. Invariant: any change to
  `canonical_recompute`'s provenance/player-set selection must be mirrored in `_check_table`.
- **MERGE-path AC-8 (Phase 5 invariant audit, fixed E-237-03):** `merge_player_pair`
  (`player_dedup.py` TN-6 Step 6/7) USED to unconditionally `DELETE FROM player_season_* WHERE
  player_id IN (canonical, duplicate)` — deleting a merged player's member `full`/`supplemented`
  row BEFORE the recompute, so the canonical NOT EXISTS guard no longer saw it and rebuilt the
  player as boxscore_only → silent downgrade of authoritative member stats. Fixed via new helper
  `_delete_or_repoint_season_rows(db, table, canonical, duplicate)`: (1) DELETE only `boxscore_only`
  rows (rederivable); (2) re-point surviving `full`/`supplemented` rows duplicate→canonical (member
  rows are API-authoritative, must MOVE not recompute); (3) PK-collision (both own a member row for
  same team+season) → canonical's row WINS, duplicate's dropped (matches canonical-preference in the
  other `_delete_or_update_*` merge helpers). Invariant: member full/supplemented season rows must
  never be deleted/downgraded by ANY path — recompute guard (non-merged) + merge re-point (merged)
  are the two closures.

The rest of this file is the PRE-consolidation history (kept for context on WHY).

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
   (`src/gamechanger/loaders/season_stats_loader.py`). MEMBER flow only (NOT reports).
   Straight from season-stats API, `stat_completeness='full'`, full ~50-col wide set.
   **DELETED in E-239** along with the member-sync surface — `season_stats_loader.py` no longer
   exists in `src/` (verified 2026-07-08).

**POST-E-239 provenance reality**: with SeasonStatsLoader and member-sync deleted, NO writer
produces `full`/`supplemented` rows anymore. Those two `stat_completeness` enum values are now
READ-ONLY — the recompute provenance guard in `src/db/season_aggregates.py` (`_MEMBER_PROVENANCE
= ("full", "supplemented")`) never deletes/rewrites them, and `src/db/player_dedup.py` still
ranks them (`_COMPLETENESS_RANK = {"full": 3, "supplemented": 2, "boxscore_only": 1}`) for
merge-conflict resolution. The only live season-aggregate writer is `canonical_recompute`, which
writes `boxscore_only` rows exclusively. Do NOT drop the `full`/`supplemented` enum values —
dropping ripples into the rank map and the parity member-scope exclusion.

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
> **History (E-256-01):** `GameLoader.load_file` (the disk twin) was DELETED — `load_payload` is now
> the sole loader entry path (`game_loader.py:321` no longer valid). The crash-atomicity note above is
> retained as the historical rationale; payload-first single-transaction is the actual state now, not a
> future fix.

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
