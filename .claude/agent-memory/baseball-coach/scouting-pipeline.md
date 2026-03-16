# Scouting Pipeline -- Endpoint Coaching Implications

## Schedule Endpoint -- Coaching Implications (discovered 2026-03-04)

The schedule endpoint provides the full game calendar with coaching-critical metadata:

- **Automated opponent scouting** (MUST HAVE): `pregame_data.opponent_id` gives the opponent's team UUID for every game. **CONFIRMED** (2026-03-04): opponent_id works as `team_id` in `/teams/{team_id}` -- returns full team metadata (city, state, competition_level, record, innings_per_game). Access level `stat_access_level: confirmed_full` strongly suggests season-stats and players endpoints will also work for opponents (not yet tested). This is the structural foundation for automated opponent scouting.
- **Home/away context** (SHOULD HAVE): `pregame_data.home_away` supports home/away split analysis directly from the schedule -- no need to infer from location data.
- **Pre-planned lineups** (NICE TO HAVE): `pregame_data.lineup_id` is set on 78/103 games. If a lineup endpoint exists, this could show lineup decisions coaches made before each game (batting order, fielding positions). Useful for post-season lineup tendency analysis.
- **Canceled game tracking**: 66 of 228 events are canceled. Tracking cancellation rates by venue, date, or weather (if available) could inform future scheduling.
- **Season history**: Returns full team history (2024-11-08 to 2025-07-15 observed), not just current season. Enables cross-season schedule analysis.

## Team Detail Endpoint -- Coaching Implications (discovered 2026-03-04)

The team-detail endpoint (`GET /teams/{team_id}`) provides per-team settings that directly affect how stats should be interpreted:

- **`innings_per_game` for stat normalization** (MUST HAVE): Travel ball uses 7-inning games; HS varsity uses 9-inning games (likely -- need to confirm with LSB credentials). Rate stats like K/9 and BB/9 must be normalized to the correct game length. A pitcher throwing 7 IP in a 7-inning game is a complete game; in a 9-inning game it is not. This field comes from each team's settings, so it can be applied per-team automatically.
- **`competition_level`** (SHOULD HAVE): Distinguishes `"club_travel"`, `"recreational"`, and (expected) high school tiers. Useful for filtering and comparing like-with-like -- a .400 AVG in recreational ball is not the same as in club travel.
- **`record` (wins/losses/ties)** (NICE TO HAVE): Quick opponent scouting signal. Before a game, coaches can see the opponent's overall record without digging into individual game results.
- **Opponent metadata via `opponent_id`**: **CONFIRMED** (2026-03-04): schedule's `opponent_id` works as `team_id` in `/teams/{team_id}`. Coaches get automated access to opponent team metadata -- city, state, competition level, record, innings_per_game -- for every team on the schedule. The full scouting pipeline is: schedule -> opponent_id -> team-detail (confirmed) -> season-stats + players (expected to work, not yet tested).

## Public Team Profile -- Unauthenticated Opponent Data (discovered 2026-03-04)

A new **public** API endpoint (`GET /public/teams/{public_id}`) requires NO authentication. If opponents have `public_id` values (available from the authenticated team-detail response), the following data is accessible without credential rotation:

- **Opponent name and location** (city, state, country) -- basic scouting context
- **Current season record** (win/loss/tie) -- quick opponent quality signal before a game
- **Coaching staff names** (SHOULD HAVE): Array of coach/manager names (no roles). Useful for pre-game scouting context -- "Who is coaching this team?" Coaches often know opposing coaches and their tendencies.
- **Team avatar** -- visual identification (URL expires, do not rely on it long-term)

### Limitation:
- No `competition_level`, no detailed stats, no player data. This is a lightweight profile only.
- Does not replace the authenticated pipeline for real scouting data (season-stats, players, player-stats).
- The scouting pipeline is still: schedule -> opponent_id -> team-detail (auth) -> season-stats + players (auth). The public endpoint is a supplement, not a replacement.

## Opponents Endpoint -- Opponent Catalog for Batch Scouting (discovered 2026-03-04)

A new opponent registry endpoint (`GET /teams/{team_id}/opponents`) returns all 70 opponents in one call (57 visible, 13 hidden duplicates/bad entries). This is a structural game-changer for the scouting workflow:

- **Complete opponent catalog in one call** (MUST HAVE): Instead of crawling game-by-game through the schedule to collect opponent IDs, this endpoint provides the full list. Each record has a `progenitor_team_id` (the canonical GameChanger UUID) that works with `/teams/{id}/season-stats`, `/teams/{id}/players`, etc.
- **`is_hidden` flag for data quality** (SHOULD HAVE): 13 of 70 records are hidden (duplicates, manual entries, bad data). Filtering these out automatically gives coaches a clean opponent list without manual curation.
- **Batch scouting pipeline** (MUST HAVE): The full opponent scouting pipeline is now: `/opponents` -> enumerate `progenitor_team_id` values -> `/season-stats` for each -> build complete opponent stat database.
- **86% coverage**: 60 of 70 records have `progenitor_team_id`. The remaining 10 are placeholders or manual entries that likely have no GC team profile to scout anyway.

### Updated scouting pipeline:
1. `/teams/{team_id}/opponents` -- get all opponent UUIDs (filter `is_hidden=false`)
2. `/teams/{progenitor_team_id}` -- get opponent metadata (city, state, record, competition_level, innings_per_game) -- **CONFIRMED** working
3. `/teams/{progenitor_team_id}/season-stats` -- get opponent batting/pitching/fielding stats -- **expected** to work (not yet tested)
4. `/teams/{progenitor_team_id}/players` -- get opponent roster -- **expected** to work (not yet tested)
5. `/teams/{progenitor_team_id}/players/{id}/stats` -- get opponent per-game stats + spray charts -- **expected** to work (not yet tested)

## Public Team Games -- Passive Opponent Scouting (discovered 2026-03-04)

A new **public** API endpoint (`GET /public/teams/{public_id}/games`) delivers opponent game results with **zero credential dependency**.

### What this unlocks for coaches:
- **Opponent season game scores at zero operational cost** (MUST HAVE): For any team with a known `public_id`, the full game history with final scores is available without credential rotation.
- **Home/away patterns** (SHOULD HAVE): `home_away` is embedded per game, so coaches can assess how an opponent performs at home vs. on the road from public data alone.
- **Film review candidates** (NICE TO HAVE): `has_videos_available` boolean identifies games with video.
- **Win/loss margin analysis** (SHOULD HAVE): `score.team` and `score.opponent_team` give exact run totals.

### Passive scouting pipeline (no credentials needed after discovery):
1. **Get opponent `public_id`** via `/teams/{opponent_uuid}/public-team-profile-id` (one auth call, returns slug)
2. `GET /public/teams/{public_id}` -- name, location, record, staff names
3. `GET /public/teams/{public_id}/games` -- full game history with scores, opponents, home/away

## Public Game Details -- Inning-by-Inning Scoring Analysis (discovered 2026-03-04)

A new **public** API endpoint (`GET /public/game-stream-processing/{game_stream_id}/details?include=line_scores`) delivers inning-by-inning scoring with **zero credential dependency**.

### What this unlocks for coaches:
- **Inning-by-inning scoring patterns** (MUST HAVE): The `line_score` field breaks each game into per-inning run totals for both teams. Coaches can analyze: Does this opponent score early or late? Do they have big innings?
- **Late-inning tendencies** (SHOULD HAVE): By aggregating across games, coaches can see whether an opponent finishes strong or fades. This informs bullpen management decisions.
- **Blowout vs. close game detection** (SHOULD HAVE): R/H/E totals give a compact scoreboard summary. Combined with the inning-by-inning data, coaches can distinguish between teams that win blowouts vs. teams that win close games.
- **Mercy rule / shortened game detection** (NICE TO HAVE): The `scores` array length reveals innings played.
- **R/H/E line as scouting summary** (MUST HAVE): Errors in particular are a coaching-relevant signal.

### Pipeline integration:
- Same `game_stream_id` links to authenticated boxscore. For a complete game picture: public details for the scoreboard line, authenticated boxscore for per-player stats.
- No credentials needed -- supplements the passive scouting pipeline.

### Updated passive scouting pipeline (no credentials needed after discovery):
1. **Get opponent `public_id`** via `/teams/{opponent_uuid}/public-team-profile-id` (one auth call, returns slug)
2. `GET /public/teams/{public_id}` -- name, location, record, staff names
3. `GET /public/teams/{public_id}/games` -- full game history with scores, opponents, home/away
4. `GET /public/game-stream-processing/{game_stream_id}/details?include=line_scores` -- inning-by-inning scoring per game (requires `game_stream_id` from game-summaries)

**Note**: Step 4 requires the `game_stream_id` which comes from the **authenticated** game-summaries endpoint, not from public-team-games. The public games endpoint returns `id` (which is `event_id`), not `game_stream_id`.

## Players/Roster Endpoint -- First LSB Team Data (discovered 2026-03-04)

A new **roster** endpoint (`GET /teams/public/{public_id}/players`) returned the **first actual LSB team data** -- the Lincoln Standing Bear JV Grizzlies roster. 20 players, jersey numbers 1-25.

### What this unlocks for coaches:
- **Player UUID list** (MUST HAVE): The **missing link** between knowing which team to scout and actually pulling per-player stats.
- **Jersey number to player mapping** (SHOULD HAVE): Coaches reference players by jersey number during games.
- **Roster size confirmation** (NICE TO HAVE): 20 players on the JV roster -- slightly above the expected 12-15 range.

### First names as initials:
The LSB JV roster returned first names as single initials -- likely a data-entry choice, not an API limitation.

### Updated scouting pipeline:
1. `/teams/{team_id}/opponents` -- get all opponent UUIDs (filter `is_hidden=false`)
2. `/teams/{progenitor_team_id}` -- get opponent metadata -- **CONFIRMED**
2a. `/teams/{progenitor_team_id}/public-team-profile-id` -- get opponent `public_id` slug -- **CONFIRMED** (own team; **opponent UUID behavior unverified**)
3. `/teams/{progenitor_team_id}/players` -- get opponent roster with player UUIDs -- **CONFIRMED** (via public variant on LSB JV)
4. `/teams/{progenitor_team_id}/season-stats` -- get opponent batting/pitching/fielding stats -- **expected**
5. `/teams/{progenitor_team_id}/players/{id}/stats` -- get opponent per-game stats + spray charts -- **expected**
