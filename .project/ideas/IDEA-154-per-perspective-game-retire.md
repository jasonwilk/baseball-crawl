# IDEA-154: Per-Perspective Game Retire — the cross-perspective removed-game gap left open by E-267-02

## Status
`CANDIDATE`
<!-- Surfaced during E-267-02 AC verification (2026-07-19) and investigated by baseball-coach
     (severity) + data-engineer (mechanism) during dispatch. Document-and-defer was the agreed
     outcome — E-267-05 documents the limitation, E-267 scope unchanged. -->

## Summary
E-267-02's game-grain retire REFUSES to retire any game that carries another perspective's `game_perspectives` row (`_other_perspectives` guard in `src/db/reconcile_at_load.py`). The refusal is CORRECT — a whole-game hard delete would destroy a second team's load — but it means a game genuinely removed/voided upstream, which BOTH perspectives loaded, is never retired by any grain. This idea is the narrower per-perspective retire that would close it: retire one perspective's contribution to a shared game without deleting the `games` row another perspective still owns.

## Why It Matters
Priority order is deliberate and NOT interchangeable — do not re-file this as a generic "nice to have someday":

1. **Recent form (HIGHEST)** — a stale removed game sits in the recent-form window a coach leans on for today's matchup decisions. Real decision corruption.
2. **Season lines (HIGH)** — the query-time season aggregates (`get_season_batting`/`get_season_pitching`) keep summing the retired game's `player_game_*` rows, driving lineup and pitch-selection calls off inflated totals.
3. **W-L record and freshness game count (COSMETIC)** — wrong but not decision-driving.
4. **Pitcher rest/workload safety (LEAST URGENT — downgraded MUST-CLOSE → SHOULD-HAVE by baseball-coach, 2026-07-19)** — see the error-direction rationale below.

## Error-direction rationale (RECORD THIS ONE — the intuitive rationale is FALSE)
**Do NOT record the reason as "the workload reads are perspective-scoped and therefore insulated." That is false and would mislead whoever picks this up.** The workload reads ARE perspective-scoped, but in the dual-perspective case one of the two perspectives IS LSB's own, so `perspective_team_id = :team_id` SELECTS the stale rows. Data-engineer asked explicitly that this false rationale not be written down.

The CORRECT reason the safety angle is the least urgent is **error direction**. A stale game can only ADD an appearance, never remove one:
- `MAX(game_date)` moves LATER
- `LAG` rest gaps NARROW
- 7-day totals INFLATE

Every direction biases toward MORE flagging. The failure mode is a false POSITIVE (holding a pitcher who was actually fine), never masking. A masking scenario requires a MISSING appearance, which an accumulate-only pipeline structurally cannot produce. **The compliance guarantee is therefore preserved: a real rest violation is never hidden — the gap can only manufacture extra caution, never extra permission.**

baseball-coach attempted to break this claim and could not, then corrected its own earlier position: the property is monotonic addition (a structural property), not a baseball fact, so it holds regardless of where the stale row's date falls. Three placements were verified — between real outings, before the earliest, after the latest — all biasing toward more caution.

**Doubleheader edge case checked and closed**: coach asked whether a same-date collision could UNDERCOUNT appearances. DE checked the actual SQL in `src/api/db.py` — no `DISTINCT` anywhere, every `GROUP BY` is on a player key, `LAG` operates over rows. Per-row across the board; no undercount path exists.

## Frequency: CONTINGENT, not modal (unmeasured)
DE found the gap is narrower than first feared. Dual-perspective loading requires a case-insensitive NAME match between how the opponent's schedule spells our team and our own `teams` row, PLUS a matching season year. Divergent spellings produce two independent single-perspective rows, each individually retirable — the guard never fires and no gap exists.

Neither expert could measure real frequency (dev DB is absent from the worktree). **The operator can settle it with one query**: game_ids with more than one `game_perspectives` row, joined to `teams.membership_type`. Do that before costing this idea — the answer decides whether this is worth an epic at all.

## Costing warning (DE, structural — do not underestimate)
**A refused game has NO grain positioned to retire it.** E-267-03 only reconciles player lines WITHIN games the fresh crawl still returns; a game absent from the fresh array never reaches that grain at all. So this is NOT a small extension of an existing grain — it needs its own retire path with its own perspective-scoped delete surface and its own bias-to-refuse corroboration. Cost it as new work, not as a parameter change.

## Notes
- Source: E-267-02 AC verification, 2026-07-19. The guard being worked around is intentional and must NOT be removed — any fix retires the perspective's contribution, never the shared `games` row.
- E-267-05 documents the limitation operator-facing; this idea is the eventual fix.
- Related: [[IDEA-147]] (H4 orientation staleness), [[IDEA-146]] (H3 frozen-plays refresh) — both REFRESH changed rows where this RETIRES missing ones.
- Master record for the parent audit: `.project/research/2026-07-19-rerun-accumulate-only-audit.md`.

---
Created: 2026-07-19
Last reviewed: 2026-07-19
Review by: 2026-10-17
