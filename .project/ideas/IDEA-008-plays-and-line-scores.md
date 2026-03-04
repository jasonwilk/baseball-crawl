# IDEA-008: Pitch-by-Pitch Plays and Inning Line Scores Crawling

## Status
`CANDIDATE`

## Summary
Crawl per-game pitch-by-pitch play data (`GET /game-stream-processing/{game_stream_id}/plays`) and inning-by-inning line scores (`GET /public/game-stream-processing/{game_stream_id}/details?include=line_scores`) for all completed games. These endpoints were discovered 2026-03-04 and are not covered by E-002.

## Why It Matters
- **Plays endpoint**: Provides the most granular game narrative data available -- every pitch sequence, stolen base attempt, balk, lineup change, and baserunner advancement. Enables pitch-by-pitch sequence reconstruction, stolen base analysis, pitcher effectiveness by at-bat, contact quality classification, and lineup change tracking. Critical for advanced scouting.
- **Public game details endpoint**: Provides inning-by-inning scoring (comeback patterns, late-inning scoring) and R/H/E totals. Complements the boxscore endpoint (which has player stats but no line score). No auth required.

Both use the same `game_stream_id` as the boxscore endpoint (E-002-03), so the data pipeline is already established.

## Rough Timing
After E-002 is complete (the boxscore pipeline must be working first). The plays data enriches game analysis but is not required for the MVP coaching dashboard. Promote when:
- E-002-03 (boxscore crawl) is DONE and validated
- Coaches express need for pitch-level scouting or inning-by-inning patterns
- Dashboard (E-004) is ready for advanced game analysis views

## Dependencies & Blockers
- [ ] E-002-03 (boxscore crawl) must be DONE -- establishes the `game_stream_id` pipeline
- [ ] E-002-02 (game-summaries) must be DONE -- provides `game_stream_id` values
- [ ] Schema expansion may be needed -- no tables currently exist for plays or line scores
- [ ] Plays endpoint uses template strings with UUID references that need a resolution layer

## Open Questions
- What schema should store play-by-play data? A `plays` table with per-at-bat records? Or raw JSON storage?
- Should the plays endpoint response be parsed into structured data or stored as raw JSON for ad-hoc querying?
- How large is the data volume? 37 KB per 6-inning game; ~30 games per team x 4 teams = ~120 games = ~4.4 MB raw JSON. Manageable.
- Does the `messages` array in plays ever contain data? All 58 records in the observed sample had empty arrays.
- The public game details endpoint requires no auth -- should it be crawled for opponent games too (expanding coverage beyond our owned teams)?

## Notes
- Plays endpoint: `GET /game-stream-processing/{game_stream_id}/plays` (auth required). Full spec at `docs/gamechanger-api.md` (line ~2178).
- Public details: `GET /public/game-stream-processing/{game_stream_id}/details?include=line_scores` (no auth). Full spec at `docs/gamechanger-api.md` (line ~2475).
- The plays endpoint uses `${uuid}` template strings for player references; a `team_players` dictionary in the response provides name resolution.
- Same asymmetric key format as boxscore (own team = public_id slug, opponent = UUID).

---
Created: 2026-03-04
Last reviewed: 2026-03-04
Review by: 2026-06-02
