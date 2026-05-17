# IDEA-077: Season-Modal Batting Order from Boxscore Backfill

## Status
`CANDIDATE`

## Summary
Populate batting order data for opponent rosters by extracting `batting_order` from boxscore JSON during boxscore loading, then aggregating a season-modal (most-common) batting position per batter. This enables E-229's call sheet to sort by batting order (matching the coach's pocket lineup card) instead of falling back to alphabetical-by-name, which is the documented E-229 production sort.

## Why It Matters
E-229 ships with **alphabetical-by-name** as the call-sheet row sort because `team_rosters.batting_order` doesn't exist as a schema column and `player_game_batting.batting_order` is schema-ready but unpopulated. Coach explicitly flagged batting-order sort as a MUST-HAVE in E-229 Q-D consultation — "the coach is tracking 'who's batting third?' not 'who's #8?' The lineup card in the coach's back pocket is sorted by order. If the call sheet is sorted by order too, the coach can glance between the two artifacts without scanning for a jersey number." Alphabetical is the documented fallback coach accepted, but the primary path delivers materially better in-game ergonomics.

This idea also unlocks broader value beyond E-229: any future surface that wants to display opponent lineups in batting order (pre-game cards, mid-game tracking sheets, post-game reports) benefits from the same backfill.

## Rough Timing
**Trigger**: Coach validates after first E-229 deployment that alphabetical sort is insufficient AND the boxscore JSON path is confirmed available by api-scout.

If E-229's first-real-opponent calibration pass surfaces "alphabetical works fine, no problem" — defer indefinitely. If coach surfaces "alphabetical is materially slowing in-game calls" — promote within 90 days as IDEA-077's own epic (per DE's guidance: NOT absorbed into E-229).

## Dependencies & Blockers
- [ ] E-229 must be deployed and run against at least one real opponent (coach validates alphabetical-vs-batting-order pain)
- [ ] api-scout verifies the boxscore JSON carries `batting_order` field per batter (prerequisite — DE round-2 followup raised this as the unknown). If the boxscore JSON lacks the field, this idea is blocked on a different data source.
- [ ] The boxscore loader path (where game stats are written to `player_game_batting`) must be willing to be extended with a new field write — likely cheap, but verify.

## Open Questions
- Does the GameChanger boxscore JSON expose `batting_order` per batter? api-scout consultation is the gate.
- Where should the aggregated season-modal value live? Three candidate shapes: (a) new column `team_rosters.batting_order` (denormalized per roster row; updates whenever the season-modal value shifts); (b) view that joins `team_rosters` to a `season_modal_batting_order(team_id, season_id, player_id)` rollup table; (c) compute at query time without persistence (cheap query, no schema change).
- How to aggregate season-modal? Simple `MODE()` over `player_game_batting.batting_order` per `(team_id, season_id, player_id)`? Or weighted by recency? Edge case: a batter who hit leadoff for half the season and 9th for the other half — what's the displayed value?
- Does this idea ALSO populate the field for member-team rosters (where the operator manages the GC team and might have richer data), or only opponent rosters (E-229's actual use case)? The two have different data paths.

## Notes
- **Origin**: surfaced during E-229 Phase 3 iteration 1 review. DE B-5 caught that the call sheet was sorting on a column that doesn't exist (`team_rosters.batting_order`) and PM had fabricated a "DE round-2 confirmation" citation that DE never gave. DE's recommendation during followup was: lock E-229 alphabetical-only, capture this idea, and if user later wants the data-driven sort, make it its own epic — NOT a story inside E-229.
- **Per DE: if promoted, this should be its OWN epic**, not absorbed into E-229. Reasons: (1) requires loader work + ETL not just a column add; (2) the aggregation method needs design (which season-modal aggregation, edge cases); (3) the storage shape decision (a/b/c above) needs DE design; (4) test surface is broad (loader tests + aggregation tests + query consumer tests).
- **Verification prerequisite**: api-scout consultation must verify the boxscore JSON carries `batting_order` BEFORE this idea is promoted. If the field is absent, this idea pivots to a different data source (manual entry per opponent? GC lineup endpoint? — both have issues per DE round-2: manual is low-signal, GC lineup endpoints are ownership-gated 403 for opponents).
- **Related**: this is independently valuable beyond E-229. Any future surface that displays opponent lineups by batting order benefits from the same backfill. Pre-game scouting cards, mid-game tracking sheets, post-game reports could all consume it.
- **Anti-fabrication lesson**: PM captured the lesson from the fabricated "DE round-2 confirmation" citation in `.claude/agent-memory/product-manager/feedback_no_fabricated_expert_confirmation.md`. Future planning stories must verify expert input before citing it.

---
Created: 2026-05-16
Last reviewed: 2026-05-16
Review by: 2026-08-14
