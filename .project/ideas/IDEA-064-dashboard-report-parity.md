# IDEA-064: Dashboard-Report Feature Parity

## Status
`CANDIDATE`

## Summary
The dashboard opponent detail page is missing several data points that standalone reports already display. A feature parity audit (2026-04-04) identified 7 gaps where reports have data the dashboard lacks. The most significant gaps are plays-derived pitching and batting stats (FPS%, QAB%, P/BF, P/PA) -- FPS% is explicitly called out as a coaching priority ("first stat coaches look at").

## Why It Matters
Coaches use both scouting surfaces. When the dashboard lacks FPS% and QAB% but the standalone report has them, the dashboard feels incomplete for pre-game prep. Closing the plays-derived stats gap makes the dashboard a self-sufficient scouting tool without requiring a report generation step.

## Rough Timing
Immediately promotable -- all data and queries already exist in the reports flow. This is a wiring/display task, not a data collection task. Promote when the predicted starter feature (E-212) ships, since E-212 establishes the shared-query pattern between reports and dashboard.

## Dependencies & Blockers
- [x] Plays pipeline (E-195) -- complete
- [x] FPS% formula correction (E-203) -- complete
- [x] Shared query pattern established (E-212-01 sets the precedent)
- [ ] E-212 should ship first to validate the shared-query-to-dashboard pattern

## Open Questions
- Should plays-derived stats be computed at scouting-load time (like season aggregates) or at query time (like report generation)? Query-time is simpler but adds latency to page loads.
- Should recent form (last 5 games) and key player callouts share logic with the report renderer, or be dashboard-specific implementations?

## Parity Gaps (from audit)

| Gap | Report Source | Dashboard Impact | Priority |
|-----|--------------|-----------------|----------|
| FPS%, P/BF (plays-derived pitching) | `_query_plays_pitching_stats()` in generator.py | HIGH -- "first stat coaches look at" | HIGH |
| QAB%, P/PA (plays-derived batting) | `_query_plays_batting_stats()` in generator.py | HIGH | HIGH |
| Team-level FPS%, P/PA | `_query_plays_team_stats()` in generator.py | Team summary enrichment | MEDIUM |
| Recent form (last 5 games) | `_query_recent_games()` in generator.py | Context for opponent strength | MEDIUM |
| Key player callouts (ace/top bat) | Renderer logic in renderer.py | Quick-scan identification | MEDIUM |
| Throws/Bats indicators | Player table columns | Handedness for lineup prep | MEDIUM |
| Roster grid | `_query_roster()` in generator.py | Roster context | LOW |

## Notes
- Surfaced during E-212 planning (2026-04-04). User confirmed this should be a separate epic, not bundled into E-212.
- The plays-derived stats queries already exist in `src/reports/generator.py`. Promoting to a shared location (like E-212 did for pitching history) would enable dashboard consumption.
- Related: IDEA-038 (Query-Time Splits and Streaks) covers more advanced analytics. This idea covers basic parity only.

---
Created: 2026-04-04
Last reviewed: 2026-04-04
Review by: 2026-07-03
