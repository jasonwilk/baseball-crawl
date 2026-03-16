# IDEA-028: Loader Stat Population (Per-Game + Season)

## Status
`PROMOTED`

## Summary
Expand game_loader, season_stats_loader, and scouting_loader to populate all E-100 stat columns that the schema supports and the API provides. This includes per-game batting/pitching extras (r, tb, hbp, shf, cs, e, wp, pitches, total_strikes, bf, decision), per-game structural columns (game_stream_id on games, batting_order/positions_played/is_primary on player_game_batting), per-season batting columns (~37 missing), per-season pitching columns (~38 missing), bats/throws on players, and scouting_loader aggregate expansion. Also clean up stale "not in schema" comments in game_loader and expand loader tests to cover all new columns.

## Why It Matters
E-100 created the DDL with complete stat columns per endpoint but explicitly deferred population. Without this work, ~80+ schema columns remain permanently NULL, the coaching dashboard cannot display most stats, and the scouting pipeline produces incomplete opponent profiles. This is the single largest gap between the schema's capability and the data actually available.

## Rough Timing
Promote when:
- E-100 is archived and the team model is stable
- The operator is ready to seed real data (re-crawl after E-100 fresh start)
- Coaching dashboard work begins and needs stat data to display

This is likely the next major data-layer epic after E-100 cleanup.

## Dependencies & Blockers
- [x] E-100 (schema with stat columns) — DONE
- [ ] E-116 (YAML TeamRef fix) — must ship first so `bb data load` works
- [ ] API endpoint documentation should be current (boxscore and season-stats endpoint field lists)

## Open Questions
- Should game_stream_id population be part of this idea or a separate smaller task? (It's a single field on the games table, available from the file stem / summaries index key.)
- For season_stats_loader: the epic Technical Notes list some pitching columns as "expected in API but not yet confirmed in endpoint doc." Should we confirm these via api-scout before implementing, or add them optimistically as nullable?
- Should bats/throws population come from the roster endpoint or the per-player stats endpoint? Neither has been confirmed as a data source for handedness.

## Notes
- DE investigation (E-100 Codex review, 2026-03-16) cataloged all gaps: 12 game_loader columns (6 batting + 6 pitching), ~37 season batting columns, ~38 season pitching columns, plus scouting_loader aggregate cascade.
- Stale loader comments say "not in schema" for columns that E-100-01 added — these are misleading and should be fixed.
- IDEA-009 (spray charts) is related but separate — it covers the spray_charts table and a different API endpoint.
- IDEA-022 (scouting flow doc mismatch) may be resolved or absorbed by this work.
- Loader tests currently only assert the legacy stat subset; test expansion is mandatory in this epic.
- **Promoted to E-117** (2026-03-16).

---
Created: 2026-03-16
Last reviewed: 2026-03-16
Review by: 2026-06-14
