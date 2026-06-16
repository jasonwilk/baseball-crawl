# E-237-03: Consolidate boxscore_only season-aggregate recompute (deterministic, ordering-independent)

## Epic
[E-237: Payload-First Loaders + Aggregate Integrity](epic.md)

## Status
`TODO`

## Description
After this story is complete, exactly one canonical boxscore_only season-aggregate recompute exists. Both `load_team` aggregate call sites (in-memory and disk) and the player-dedup path route through it, so a merged player and a non-merged player produce the same deterministic **superset** column population for the same per-game rows — the hybrid-row non-determinism is gone. No report stat value changes; goldens and the parity fixture are unchanged (parity checks only ScoutingLoader's subset, which the superset preserves).

## Context
Two divergent boxscore_only recomputes run today inside `ScoutingLoader.load_team`: the player-dedup sweep recompute (`src/db/player_dedup.py::recompute_*`, `798-944`, DELETE+INSERT, batting adds pa/singles/xbh, pitching writes w/l/sv but OMITS `gs`) at `scouting_loader.py:143-157`, then `ScoutingLoader._compute_*_aggregates` (`643-803`, ON CONFLICT DO UPDATE of its 16-batting / 14-pitching-incl-`gs` subset) at `:159`. The same pair recurs on the disk path `_load_team_from_disk` (dedup `:217`, aggregate `:224`). A *merged* player ends with a HYBRID row (dedup-only columns survive + ScoutingLoader columns overwritten); a *non-merged* player has the dedup-only columns NULL. Whether pa/singles/xbh/w/l/sv get populated is non-deterministic w.r.t. whether a merge happened (DE finding). Reports aggregates are NOT stale today (the recompute is committed atomically with dedup; no post-load stage mutates `player_game_*`), so this is an unenforced-ordering + divergent-writer fragility, not an active bug. This story collapses the two writers into ONE canonical superset recompute (Option B, TN-5). See Technical Notes TN-4, TN-5, TN-7, TN-8, TN-10 in the epic.

## Acceptance Criteria
- [ ] **AC-1**: Given BOTH in-load paths (`load_team:159` AND disk `_load_team_from_disk:224`) and the player-dedup path, when boxscore_only season aggregates are recomputed, then exactly ONE module-level canonical recompute function exists (consolidating away `ScoutingLoader._compute_*_aggregates` and `player_dedup.recompute_*`), all three routes use it, and it runs EXACTLY ONCE per load — wiring per Technical Notes TN-11.
- [ ] **AC-2**: Given identical per-game rows, when the canonical recompute runs for a *merged* player and for a *non-merged* player, then the resulting `player_season_batting`/`player_season_pitching` column population is the same deterministic **superset** in both cases (no hybrid row; the dedup-derived columns pa/singles/xbh/w/l/sv are populated identically for both, per Option B) — per Technical Notes TN-4, TN-5.
- [ ] **AC-3**: Given the canonical recompute, when it writes, then it (a) is perspective-scoped (`perspective_team_id = team_id`) at scope `(team_id, season_id)` per Technical Notes TN-4/TN-11; (b) uses DELETE-boxscore_only-for-scope + INSERT (not partial ON CONFLICT); (c) never UPDATEs or DELETEs a `full` OR `supplemented` row (provenance guard); and (d) is committed atomically WITH THE DEDUP SWEEP (same transaction at `scouting_loader.py:160`), NOT all-or-nothing with the per-game writes, per Technical Notes TN-10.
- [ ] **AC-4**: Given the canonical recompute, when it produces rows, then the column contract is the **Option B superset** (TN-5): its **parity-checked subset** equals ScoutingLoader's exact current set — batting (16) {gp, games_tracked, ab, h, doubles, triples, hr, rbi, r, bb, so, sb, **tb**, hbp, shf, cs}; pitching (14, gs included) {gp_pitcher, games_tracked, ip_outs, h, r, er, bb, so, wp, hbp, pitches, total_strikes, bf, **gs** (NULL-safe CASE)} — EXCLUDING pitching `hr` (member-only; `scouting_loader.py:733-740`); PLUS the dedup-derived extras {batting pa/singles/xbh; pitching w/l/sv} populated for every player. Because `aggregate_parity` diffs only the subset, `bb report verify-aggregates` returns no mismatches on the seeded fixture and `tests/fixtures/parity_consistent.sql` is unchanged — per Technical Notes TN-5, TN-7. If the implementer changes any parity-checked-subset column, adds pitching `hr`, or changes the `gs` definition, the change is flagged as report-visible, verified against Epic A goldens, and the parity script + hand-recomputed fixture are updated in lockstep (Safety Rule 4).
- [ ] **AC-5**: Given the inert `'supplemented'` provenance value, when the canonical recompute runs, then it never writes `'supplemented'` and never touches `full` OR `supplemented` rows (both member-owned); the enum/CHECK + completeness rank (`player_dedup.py:331`) + parity member-scope exclusion (`aggregate_parity.py:348`) are left unchanged (no schema change) — per the epic Non-Goals.
- [ ] **AC-6**: Epic A golden stat tables (`tests/test_report_golden.py`) and aggregate parity remain green; the standalone/quarantined callers of the consolidated recompute keep working with their signatures/behavior preserved and their tests green — the CLI `bb data dedup-players` path (`src/cli/data.py`), the direct `recompute_affected_seasons` CLI caller, and `tests/test_player_dedup.py` (whose `pa`/`w` assertions hold under the Option B superset). **CORRECTNESS (per Technical Notes TN-11)**: the member-sync Hook-2 dedup at `src/pipeline/trigger.py:742` runs AFTER the end-of-load recompute and re-points rows, so it MUST still recompute (default `recompute_aggregates=True`); the embedded suppression must NOT reach it.
- [ ] **AC-7**: **Operator pre-merge gates recorded (user-run, TN-8)**: this story is not marked DONE until (a) a real report generated against production data is eyeballed against prior output with no value change, and (b) `bb report verify-aggregates` on a production DB copy has every pre-existing mismatch resolved or explicitly explained. Both run outside the worktree and are confirmed by the operator/user; PM records the OUTCOMES — the report-eyeball result (no value change) and the parity diff with each pre-existing mismatch's resolution or explanation — as a verification entry in the epic's History at closure (the auditable completion artifact). Per Technical Notes TN-8.
- [ ] **AC-8**: Given a member-provenance `(team_id, season_id)` scope with a stored `full` (or `supplemented`) season row, when a dedup runs on that scope through the canonical recompute, then the member row SURVIVES (is neither deleted nor overwritten) — a regression test asserts this, pinning the latent-data-loss fix that the `boxscore_only`-only ownership guard (AC-3c) provides over today's unconditional dedup DELETE+INSERT (per Technical Notes TN-4).

## Technical Approach
Introduce a single canonical perspective-scoped recompute at scope `(team_id, season_id)` that owns boxscore_only rows and applies the DELETE-for-scope + INSERT shape (TN-4), writing the Option B superset (TN-5), with the call-site topology + double-run collapse mandated by TN-11. Route BOTH `load_team` aggregate call sites (in-memory `:159` and disk `_load_team_from_disk:224`) and the player-dedup path through it, consolidating away the two divergent implementations. Keep the recompute strictly within `boxscore_only` (provenance guard); never touch `full`/`supplemented`; never produce `'supplemented'`. Confirm against the existing parity guard (`src/reports/aggregate_parity.py`) and the seeded fixture — since the superset's parity-checked subset equals ScoutingLoader's current set, no parity-script or fixture change is expected (TN-7).

**Stat-value safety (do not re-litigate — verified PM renderer trace + DE full-`src/` grep, TN-5):** "PA and XBH are presentation-derived in the renderer from canonical columns (`renderer.py:_compute_pa` :95-102 = ab+bb+hbp+shf; `:164-169` `_xbh` = doubles+triples+hr); the schema's stored `pa`/`xbh` columns are member-API-only (`full` rows) and are NOT part of the boxscore_only contract." No live surface (reports, dashboard, or profiles) reads pa/singles/xbh/w/l/sv, so populating them on the ScoutingLoader path (Option B) is number-neutral.

The call-site topology and double-run collapse are MANDATED (TN-11). What remains delegated to the data-engineer: the exact recompute SQL and the canonical function's module placement (DE advisory: likely `src/db/`, e.g. a new `src/db/season_aggregates.py`, to avoid an import cycle — TN-4).

## Dependencies
- **Blocked by**: E-237-02 (shared file `scouting_loader.py`)
- **Blocks**: None

## Files to Create or Modify
- `src/gamechanger/loaders/scouting_loader.py` (route BOTH `load_team:159` and `_load_team_from_disk:224` aggregation through the canonical recompute; remove the divergent `_compute_*_aggregates` implementation as consolidated)
- `src/db/player_dedup.py` (route the dedup sweep through the canonical recompute; remove its divergent `recompute_*` implementation as consolidated; preserve `dedup_team_players` / `recompute_affected_seasons` signatures for standalone callers)
- Possibly a new canonical-recompute module, e.g. `src/db/season_aggregates.py` (DE advisory placement, TN-4) — implementer's call
- `tests/test_scouting_loader.py` and/or `tests/test_player_dedup.py` (determinism test per AC-2; member-`full`-row-survival test per AC-8; consolidation + standalone-caller coverage)
- `src/reports/aggregate_parity.py` + `tests/fixtures/parity_consistent.sql` — ONLY if TN-7 fires (the parity-checked subset deviates from ScoutingLoader's current set); otherwise untouched

## Agent Hint
data-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
DE-verified locations: ScoutingLoader recompute `scouting_loader.py:643-803` (called at `:159` in-memory, `:224` disk path); player-dedup recompute `player_dedup.py:798-944` (called via `dedup_team_players` at `scouting_loader.py:143-157` in-memory, `:217` disk path; standalone web caller `pipeline/trigger.py:742`; direct CLI caller `cli/data.py:1095`); recompute committed atomically with dedup at `scouting_loader.py:160`. PM stat-value audit (TN-5): no report/dashboard/profile surface reads the stored dedup-only columns; the renderer derives `_pa`/`_xbh` from base columns — so the Option B superset is reader-invisible.
