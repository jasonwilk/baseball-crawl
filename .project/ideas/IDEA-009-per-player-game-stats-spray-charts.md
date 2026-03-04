# IDEA-009: Per-Player Per-Game Stats and Spray Charts

## Status
`CANDIDATE`

## Summary
Crawl per-player per-game statistics and spray chart data via `GET /teams/{team_id}/players/{player_id}/stats`. This endpoint was discovered 2026-03-04 and returns comprehensive per-game batting/fielding stats, rolling cumulative season stats, and ball-in-play location coordinates (spray charts) for a single player across all their games. Not covered by E-002.

## Why It Matters
- **Spray charts**: Ball-in-play direction data (x/y coordinates, play type, result, fielder position) enables batting tendency analysis and defensive positioning recommendations. This is the only known source of spray chart data in the API.
- **Comprehensive per-game stats**: 25+ batting fields per game (vs boxscore's core 6 + sparse extras). Includes all counting stats the boxscore omits.
- **Rolling cumulative stats**: Season totals as of each game date -- enables trend visualization (e.g., "OBP rising over the last 10 games").
- **Season trajectory**: Combined with the per-game breakdowns, this powers player development tracking across seasons.

## Rough Timing
After E-002 is complete and boxscore data is flowing. The per-player endpoint requires one call PER player -- for 15 players x 4 teams = 60 API calls per crawl (manageable but nontrivial). Promote when:
- E-002 boxscore pipeline is working
- Coaches want spray chart / defensive positioning data
- Dashboard (E-004) is ready for player trend views
- Rate limiting characteristics are understood from E-002 crawl experience

## Dependencies & Blockers
- [ ] E-002-01 (roster crawl) must be DONE -- provides player UUIDs needed as path parameters
- [ ] E-002 boxscore pipeline should be validated -- confirms the API access pattern works
- [ ] Schema expansion needed -- no current tables for spray chart data or per-game comprehensive stats beyond the boxscore-derived rows
- [ ] Rate limiting assessment needed -- 60 calls is more than E-002's team-level endpoints; need to confirm this volume is safe

## Open Questions
- What schema should store spray chart data? Separate table with x/y coordinates per ball-in-play event?
- Should the full response be stored as raw JSON (large: 387 KB per player observed), or should the crawler extract and store only the fields of interest?
- The endpoint returns stats for ALL games a player has played (across the season). Is there a query parameter to limit to specific games or date ranges? None observed.
- `offensive_spray_charts` was null for 30% of games, `defensive_spray_charts` null for 84% of games. What determines whether spray data is present?
- The `stats.defense` section combines pitching and fielding (same as season-stats). Do we need to separate them for the per-game level?
- Does this endpoint work for opponent team players, or only for owned teams?

## Notes
- Endpoint: `GET /teams/{team_id}/players/{player_id}/stats` (auth required). Full spec at `docs/gamechanger-api.md` (line ~1197).
- Accept header: `application/vnd.gc.com.player_stats:list+json; version=0.0.0`
- gc-user-action: `data_loading:player_stats`
- Response is a bare JSON array of per-game objects; 80 records observed for one player.
- No pagination observed -- all 80 records returned in single response.
- Records are NOT in strict chronological order -- sort by `game_date` before interpreting cumulative trajectory.
- `cumulative_stats` is rolling (season totals through each game date).
- Player names not included in response -- UUID-only. Cross-reference with roster data.

---
Created: 2026-03-04
Last reviewed: 2026-03-04
Review by: 2026-06-02
