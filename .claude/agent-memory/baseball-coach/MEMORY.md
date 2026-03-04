# Baseball Coach -- Agent Memory

## Team Scope

Lincoln Standing Bear High School baseball program:
- Four teams: Freshman, JV, Varsity, Reserve
- Legion teams added later (different competition level, different season)
- 12-15 players per team
- ~30-game seasons
- Jason is the system operator; coaching staff are the end consumers
- Coaches see dashboards and reports -- they do not interact with the system directly

## Key Reference Documents

- **Stat glossary**: `docs/gamechanger-stat-glossary.md` -- authoritative data dictionary mapping all GameChanger stat abbreviations to definitions (batting, pitching, fielding, catcher, positional innings). Includes API field name mapping table for cases where API abbreviations differ from UI labels (e.g., K-L -> SOL, HHB -> HARD, SAC -> SHB). Use this when validating schemas or consulting on field mappings.

## Established Stat Priorities

### Batting (ranked)
- **OBP** -- the most important offensive stat. Getting on base is the foundation.
- **K%** -- strikeout rate. Identifies swing-and-miss problems.
- **BB%** -- walk rate. Shows plate discipline.
- **BABIP** -- with heavy caveats about sample size at HS level.
- **SLG** -- slugging. Power matters but less than OBP at this level.
- **Splits**: home/away and vs. LHP/RHP. Both stored as nullable columns in season stats tables.

### Pitching (ranked)
- **K/9** -- strikeout rate per 9 innings. Shows dominance.
- **BB/9** -- walk rate per 9. Shows command.
- **K/BB ratio** -- the best single number for pitcher quality at HS level.
- **Pitch counts** -- critical for arm health and compliance.
- **HR/9** -- home run rate (less meaningful in small samples but tracked).
- **FIP** -- if we have the components (K, BB, HR, IP).
- **Splits**: vs. LHB/RHB stored as nullable columns.

### Base Running
- SB success rate
- Extra bases taken

### Fielding
- Error rates by position (advanced fielding metrics rarely meaningful at HS level)

## Sample Size Rules

High school baseball has small samples. These thresholds are firm:
- **Batting**: Flag any stat based on fewer than 20 plate appearances. A 30-game season yields only 80-100 PA total; L/R or home/away splits may have 20-40 PA per bucket.
- **Pitching**: Flag any stat based on fewer than 15 innings pitched. Starters may throw 40-60 IP per season.
- Always present stats with context: "In 23 PA vs lefties, .350 OBP (small sample)"

## Output Format Conventions

- Label every recommendation: **MUST HAVE**, **SHOULD HAVE**, or **NICE TO HAVE**
- Include sample size caveats in every recommendation, every time
- Make outputs bench-ready -- a coach sitting in the dugout 30 minutes before first pitch should be able to act on it
- Show what a result looks like: example scouting reports, example query results, example lineup cards
- Be specific: "Track plate appearance outcomes (H, 2B, 3B, HR, BB, HBP, K, other out) with pitcher handedness, game location, and date" not "track batting stats"

## Multi-Team, Multi-Season Tracking

Players must be tracked across teams and seasons:
- A player may appear on LSB Freshman one year, LSB JV the next, Legion in summer, travel ball elsewhere
- Player identity across teams is a design challenge (same name, different team IDs in GameChanger)
- Different competition levels must be accounted for (Varsity stats are not equivalent to Freshman stats)
- Longitudinal tracking enables: development trajectories, regression detection, promotion readiness
- The data model must support this from day one -- retrofitting cross-team identity is painful

## Per-Game Player Stats and Spray Charts (discovered 2026-03-04)

The GameChanger API has a player-stats endpoint that provides **per-game stat lines** for every game a player appeared in. This is a major upgrade from season-stats (which only had aggregates).

### What this unlocks for coaches:
- **Game-by-game performance tracking**: See a player's batting line for every game, not just season totals. Identify hot/cold streaks, performance after rest days, multi-hit games vs. hitless stretches.
- **Per-game pitching lines**: IP, ER, K, BB, pitch count for each outing. Track workload, recovery patterns, and performance trends.
- **Spray chart data**: Ball-in-play direction with x/y field coordinates, play type (ground ball, line drive, fly ball), play result (hit, out), and fielder position. This is **unique data not available in season-stats**.
  - **Batting tendencies**: Where does this hitter put the ball? Pull-heavy? Opposite field? Ground ball tendency?
  - **Fielding positioning**: Where should we play our defenders against this batter?
  - **Opponent scouting**: Opponent team_id access confirmed (2026-03-04). If opponent player-stats also work (untested), spray charts become a scouting weapon for opponent batters and pitchers.
- **Rolling cumulative stats**: See how a player's season line evolved over time (performance trajectory).

### Priority for coaching:
- **MUST HAVE**: Per-game batting lines (streak detection, recent form for lineup decisions)
- **MUST HAVE**: Per-game pitching lines (workload tracking, arm health compliance)
- **SHOULD HAVE**: Spray chart analysis (batting tendencies, fielding positioning)
- **NICE TO HAVE**: Cumulative trend visualization (development tracking over season)

## Boxscore Endpoint -- Game-Level Scouting Weapon (discovered 2026-03-04)

A new **boxscore** endpoint (`GET /game-stream-processing/{game_stream_id}/boxscore`) returns the complete per-player box score for BOTH teams in a single API call. This is the most coaching-impactful endpoint discovered to date.

### What this unlocks for coaches:

- **Complete opponent box scores in one call** (MUST HAVE): Every batter's line (AB/R/H/RBI/BB/SO + extras) and every pitcher's line (IP/H/R/ER/BB/SO + pitch count/strikes/BF) for BOTH teams. Before a game, coaches can review the opponent's recent box scores to identify: who's hot, who's cold, who's pitching well, who's giving up walks.
- **Pitch count tracking per pitcher** (MUST HAVE): `#P` (total pitches) and `TS` (strikes thrown) per pitcher per game. Critical for arm health compliance, workload monitoring, and identifying when a pitcher was laboring (high pitch count, low strike %). This data is NOT in season-stats -- only available per-game via boxscore or player-stats.
- **Batting order and lineup construction** (SHOULD HAVE): Batters listed in batting order, with `is_primary: false` flagging substitutes. Track opponent lineup tendencies: who bats leadoff? Who's in the 3-4 hole? Does the coach change the lineup against lefties?
- **Position history per game** (SHOULD HAVE): `player_text` shows every position a player played (e.g., `"(SS, P)"` = played shortstop then moved to pitcher). Track defensive flexibility and pitcher usage patterns.
- **Pitcher decisions** (SHOULD HAVE): `player_text` in pitching group shows `"(W)"`, `"(L)"` -- track which pitchers carry the wins/losses, identify aces and closers.
- **Errors by player** (NICE TO HAVE): `E` in batting extras identifies who committed errors and how many. Fielding weakness detection for opponent scouting.

### Priority for coaching:
- **MUST HAVE**: Per-game opponent batting and pitching lines (the core of pre-game scouting)
- **MUST HAVE**: Pitch count + strike count per pitcher per game (arm health, workload)
- **SHOULD HAVE**: Batting order tracking and lineup tendencies
- **SHOULD HAVE**: Position history for defensive positioning and versatility assessment
- **NICE TO HAVE**: Error tracking for fielding weakness identification

### Comparison with player-stats endpoint:
- **Boxscore**: Both teams in one call, batting order included, pitch counts per pitcher, team totals. Best for game-level scouting and opponent analysis.
- **Player-stats**: One player at a time, 80+ stat fields per game, spray charts, cumulative trends. Best for deep individual player analysis and development tracking.
- **Use both**: Boxscore for pre-game scouting (quick opponent review), player-stats for deep dives on specific players.

### Pipeline dependency:
Box score data requires a two-step fetch: game-summaries (to get `game_stream.id`) then boxscore. Schedule alone is NOT sufficient -- it does not expose the required ID.

## Plays Endpoint -- Pitch-by-Pitch Game Reconstruction (discovered 2026-03-04)

A new **plays** endpoint (`GET /game-stream-processing/{game_stream_id}/plays`) returns the complete pitch-by-pitch play log for both teams in a single API call. This is the most granular game data in the entire API -- every pitch, every baserunner event, every substitution.

### What this unlocks for coaches:

- **Full pitch sequence per at-bat** (MUST HAVE): Ball 1, Strike 1 (looking/swinging), Foul, In play -- the complete pitch-by-pitch sequence for every plate appearance. Coaches can analyze: Does this batter chase first-pitch strikes? Does he fight off two-strike counts? Is he a patient hitter (high pitch counts) or aggressive (first-pitch swinger)? This is granularity that boxscore and season-stats cannot provide.
- **Contact quality classification** (SHOULD HAVE): Hit descriptions include "hard ground ball", "line drive", "fly ball", "bunt" -- batted ball type is embedded in the narrative. Combined with the outcome (hit, out, error), coaches can assess contact quality beyond just batting average. A batter who lines out three times is hitting the ball well despite the 0-for-3; a batter who goes 2-for-3 on bloopers is getting lucky.
- **Pitcher approach analysis** (MUST HAVE): By tracking pitch sequences against specific batters, coaches can see how pitchers attack hitters: Do they start with strikes? Do they waste pitches? How do they respond when behind in the count? This is the foundation of advanced scouting.
- **Baserunner intelligence** (SHOULD HAVE): Stolen bases, caught stealing, balks, pickoff attempts, wild pitch advances, and courtesy runners are all embedded in the play sequence. Coaches can assess: How aggressive are baserunners? Does this pitcher have a slow move to first? Does the catcher throw out runners?
- **Fielder identity on every out** (SHOULD HAVE): Every defensive out includes the fielder's identity ("grounds out to shortstop ${uuid}"). Track which fielders make plays and where -- useful for identifying defensive strengths and weaknesses.
- **In-game substitution tracking** (NICE TO HAVE): Lineup changes and pinch runners appear inline with the at-bats where they occurred. Coaches can see when opponents make substitutions and in what situations (defensive replacement in late innings, pinch runner for a slow catcher, etc.).

### Priority for coaching:
- **MUST HAVE**: Pitch sequence per at-bat for approach analysis (most granular scouting data available)
- **MUST HAVE**: Pitcher approach patterns (how they work through counts)
- **SHOULD HAVE**: Contact quality classification from hit descriptions
- **SHOULD HAVE**: Baserunner event tracking (SB, CS, pickoffs, WP advances)
- **SHOULD HAVE**: Fielder identity on defensive plays
- **NICE TO HAVE**: Substitution timing and situational patterns

### Comparison with other endpoints:
- **Plays**: Every pitch, every baserunner event, contact quality descriptions. Best for deep game analysis, approach scouting, and pitch sequence patterns.
- **Boxscore**: Per-player stat lines with pitch counts and batting order. Best for quick pre-game scouting.
- **Player-stats**: Per-game stat lines with spray charts and 80+ stat fields. Best for individual player development tracking.
- **Use all three**: Boxscore for pre-game scouting overview, plays for deep game film replacement (pitch-by-pitch reconstruction), player-stats for longitudinal development.

### Pipeline dependency:
Same two-step fetch as boxscore: game-summaries (to get `game_stream.id`) then plays. Same `game_stream_id` links plays, boxscore, and public game details -- three complementary views of the same game.

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

### Priority for coaching:
- **SHOULD HAVE**: Staff names for scouting context (coach identification)
- **NICE TO HAVE**: No-auth access to record/name/location (already available via authenticated endpoint; the value is removing the credential dependency for basic info)

### Limitation:
- No `competition_level`, no detailed stats, no player data. This is a lightweight profile only.
- Does not replace the authenticated pipeline for real scouting data (season-stats, players, player-stats).
- The scouting pipeline is still: schedule -> opponent_id -> team-detail (auth) -> season-stats + players (auth). The public endpoint is a supplement, not a replacement.

## Opponents Endpoint -- Opponent Catalog for Batch Scouting (discovered 2026-03-04)

A new opponent registry endpoint (`GET /teams/{team_id}/opponents`) returns all 70 opponents in one call (57 visible, 13 hidden duplicates/bad entries). This is a structural game-changer for the scouting workflow:

- **Complete opponent catalog in one call** (MUST HAVE): Instead of crawling game-by-game through the schedule to collect opponent IDs, this endpoint provides the full list. Each record has a `progenitor_team_id` (the canonical GameChanger UUID) that works with `/teams/{id}/season-stats`, `/teams/{id}/players`, etc.
- **`is_hidden` flag for data quality** (SHOULD HAVE): 13 of 70 records are hidden (duplicates, manual entries, bad data). Filtering these out automatically gives coaches a clean opponent list without manual curation.
- **Batch scouting pipeline** (MUST HAVE): The full opponent scouting pipeline is now: `/opponents` -> enumerate `progenitor_team_id` values -> `/season-stats` for each -> build complete opponent stat database. This replaces the previous approach of: schedule -> extract opponent_id game-by-game -> deduplicate. Both paths reach the same canonical UUID, but `/opponents` is simpler and more complete.
- **86% coverage**: 60 of 70 records have `progenitor_team_id`. The remaining 10 are placeholders or manual entries that likely have no GC team profile to scout anyway.

### Updated scouting pipeline:
1. `/teams/{team_id}/opponents` -- get all opponent UUIDs (filter `is_hidden=false`)
2. `/teams/{progenitor_team_id}` -- get opponent metadata (city, state, record, competition_level, innings_per_game) -- **CONFIRMED** working
3. `/teams/{progenitor_team_id}/season-stats` -- get opponent batting/pitching/fielding stats -- **expected** to work (not yet tested)
4. `/teams/{progenitor_team_id}/players` -- get opponent roster -- **expected** to work (not yet tested)
5. `/teams/{progenitor_team_id}/players/{id}/stats` -- get opponent per-game stats + spray charts -- **expected** to work (not yet tested)

## Public Team Games -- Passive Opponent Scouting (discovered 2026-03-04)

A new **public** API endpoint (`GET /public/teams/{public_id}/games`) delivers opponent game results with **zero credential dependency**. This is the second unauthenticated endpoint (after public-team-profile).

### What this unlocks for coaches:
- **Opponent season game scores at zero operational cost** (MUST HAVE): For any team with a known `public_id`, the full game history with final scores is available without credential rotation. Before a game, coaches can see the opponent's recent results -- wins, losses, margins, and opponents faced -- without consuming any authentication budget.
- **Home/away patterns** (SHOULD HAVE): `home_away` is embedded per game, so coaches can assess how an opponent performs at home vs. on the road from public data alone.
- **Film review candidates** (NICE TO HAVE): `has_videos_available` boolean identifies games with video. If coaches want to study an upcoming opponent, they can target games with available film.
- **Win/loss margin analysis** (SHOULD HAVE): `score.team` and `score.opponent_team` give exact run totals. Coaches can see if an opponent wins close games or blows teams out -- an indicator of depth and clutch performance.

### Passive scouting pipeline (no credentials needed after discovery):
1. **Get opponent `public_id`** via `/teams/{opponent_uuid}/public-team-profile-id` (one auth call, returns slug) -- or from authenticated `/teams/{team_id}` response's `public_id` field
2. `GET /public/teams/{public_id}` -- name, location, record, staff names
3. `GET /public/teams/{public_id}/games` -- full game history with scores, opponents, home/away

### Limitation:
- No per-player stats, no opponent team UUID (only opponent name). Real scouting depth (season-stats, player-stats, spray charts) still requires the authenticated pipeline.
- The public pipeline is a **lightweight, always-available complement** -- not a replacement for authenticated scouting.

## Public Game Details -- Inning-by-Inning Scoring Analysis (discovered 2026-03-04)

A new **public** API endpoint (`GET /public/game-stream-processing/{game_stream_id}/details?include=line_scores`) delivers inning-by-inning scoring with **zero credential dependency**. This is the fourth unauthenticated endpoint. Uses the same `game_stream_id` as the authenticated boxscore, so the two endpoints are complementary views of the same game.

### What this unlocks for coaches:
- **Inning-by-inning scoring patterns** (MUST HAVE): The `line_score` field breaks each game into per-inning run totals for both teams. Coaches can analyze: Does this opponent score early or late? Do they have big innings? Are they a comeback team or do they fold when behind? For example, in the sample game, the opponent scored 11 runs in a single inning -- a sign of either a pitching collapse or a very dangerous middle-of-order.
- **Late-inning tendencies** (SHOULD HAVE): By aggregating across games, coaches can see whether an opponent finishes strong (late-inning rallies) or fades (scoring front-loaded). This informs bullpen management decisions: if the opponent tends to rally late, save the closer for the 7th rather than using a mop-up arm.
- **Blowout vs. close game detection** (SHOULD HAVE): R/H/E totals (`totals = [R, H, E]`) give a compact scoreboard summary. Combined with the inning-by-inning data, coaches can distinguish between teams that win blowouts (dominate weak opponents) vs. teams that win close games (competitive in tough matchups). This matters for scouting -- a team with a good record built on blowouts of weak teams is a different challenge than one with a .500 record in close games against strong opponents.
- **Mercy rule / shortened game detection** (NICE TO HAVE): The `scores` array length reveals innings played. A 5-inning game (like the sample) likely ended via mercy rule. Tracking this helps coaches assess opponent strength -- teams that get mercy-ruled are weaker opponents, teams that play full games are competitive.
- **R/H/E line as scouting summary** (MUST HAVE): The `[R, H, E]` totals are the classic scoreboard line. Errors in particular are a coaching-relevant signal: a team with consistently high error totals has defensive weaknesses to exploit (bunt for hits, run on grounders, pressure the defense).

### Priority for coaching:
- **MUST HAVE**: R/H/E line per game (compact scouting summary, error pattern detection)
- **MUST HAVE**: Inning-by-inning scoring for opponent pattern analysis
- **SHOULD HAVE**: Late-inning tendency aggregation across games
- **SHOULD HAVE**: Blowout vs. close game classification
- **NICE TO HAVE**: Mercy rule / shortened game detection from innings count

### Pipeline integration:
- Same `game_stream_id` links to authenticated boxscore. For a complete game picture: public details for the scoreboard line, authenticated boxscore for per-player stats.
- No credentials needed -- supplements the passive scouting pipeline (public-team-profile + public-team-games + public-game-details).

### Updated passive scouting pipeline (no credentials needed after discovery):
1. **Get opponent `public_id`** via `/teams/{opponent_uuid}/public-team-profile-id` (one auth call, returns slug) -- or from authenticated `/teams/{team_id}` response
2. `GET /public/teams/{public_id}` -- name, location, record, staff names
3. `GET /public/teams/{public_id}/games` -- full game history with scores, opponents, home/away, `id` for each game
4. `GET /public/game-stream-processing/{game_stream_id}/details?include=line_scores` -- inning-by-inning scoring per game (requires `game_stream_id` from game-summaries, NOT from public-team-games `id`)

**Note**: Step 1 uses the new public-team-profile-id bridge endpoint -- one lightweight auth call per opponent to get the slug, then steps 2-3 are fully unauthenticated. Step 4 requires the `game_stream_id` which comes from the **authenticated** game-summaries endpoint, not from public-team-games. The public games endpoint returns `id` (which is `event_id`), not `game_stream_id`. So step 4 is "public" in that it requires no auth to call, but it requires an authenticated data source to discover the IDs.

## Players/Roster Endpoint -- First LSB Team Data (discovered 2026-03-04)

A new **roster** endpoint (`GET /teams/public/{public_id}/players`) returned the **first actual LSB team data** -- the Lincoln Standing Bear JV Grizzlies roster. 20 players, jersey numbers 1-25.

### What this unlocks for coaches:
- **Player UUID list** (MUST HAVE): This is the **missing link** between knowing which team to scout and actually pulling per-player stats. Each player's UUID (`id` field) is the key needed for `/teams/{team_id}/players/{player_id}/stats` (per-game stats, spray charts) and for matching against `season-stats` per-player breakdowns. Without this endpoint, the only way to get player IDs was from boxscore data (which requires knowing `game_stream_id` from game-summaries first).
- **Jersey number to player mapping** (SHOULD HAVE): Coaches reference players by jersey number during games. The roster provides the number-to-name-to-UUID mapping needed for quick lookups ("Who is #15?" -> two players share it, both identified by UUID).
- **Roster size confirmation** (NICE TO HAVE): 20 players on the JV roster -- slightly above the expected 12-15 range. This affects workload estimates for per-player stat ingestion (20 API calls per team instead of 12-15).

### First names as initials:
The LSB JV roster returned first names as single initials ("A", "B", "C") rather than full names. This is likely a data-entry choice by the team administrator in GameChanger, not an API limitation. For coaching purposes, last names with jersey numbers are sufficient for identification. If full first names are needed, the boxscore endpoint may have them (boxscore embeds player names from a potentially different data source).

### Updated scouting pipeline:
1. `/teams/{team_id}/opponents` -- get all opponent UUIDs (filter `is_hidden=false`)
2. `/teams/{progenitor_team_id}` -- get opponent metadata -- **CONFIRMED**
2a. `/teams/{progenitor_team_id}/public-team-profile-id` -- get opponent `public_id` slug -- **CONFIRMED** (own team; **opponent UUID behavior unverified -- highest priority follow-up**)
3. `/teams/{progenitor_team_id}/players` -- get opponent roster with player UUIDs -- **CONFIRMED** (via public variant on LSB JV)
4. `/teams/{progenitor_team_id}/season-stats` -- get opponent batting/pitching/fielding stats -- **expected**
5. `/teams/{progenitor_team_id}/players/{id}/stats` -- get opponent per-game stats + spray charts -- **expected**

Step 2a is the **UUID-to-public_id bridge**: once an opponent's `public_id` is known, all public endpoints (games, profile, roster, line scores) become available without auth. If confirmed working for opponent UUIDs, this closes the last gap in the opponent scouting pipeline -- every scheduled opponent gets full public API access automatically.

Step 3 is now **CONFIRMED** working -- the roster endpoint returns player UUIDs that are usable in downstream stat endpoints.

## Coaching Decisions This System Serves

These are the actual decisions coaches make that this system should support:
- **Who starts today?** (opponent pitcher handedness, recent performance, health/rest)
- **What's the batting order?** (OBP at top, power in middle, hot/cold streaks)
- **Who pitches today?** (matchups vs. opponent lineup, pitch count budget, rest days)
- **When do we bunt/steal/hit-and-run?** (opponent catcher arm, pitcher attention to runners)
- **What do we know about this opponent?** (tendencies, key players, weaknesses)
- **Is this player improving?** (season-over-season trends, level-appropriate benchmarks)

## Data Storage Conventions

Decisions established with data-engineer:
- Innings pitched stored as integer outs (ip_outs): 1 IP = 3 outs. Always.
- Splits stored as nullable columns (home_obp, away_obp, vs_lhp_obp, vs_rhp_obp), not separate rows
- FK-safe orphan handling: when a player_id is not in `players`, insert a stub row (first_name='Unknown', last_name='Unknown') before writing the stat row. Log a WARNING for operator backfill.
- Key entities: Team, Player, PlayerTeamSeason, Game, Lineup, PlateAppearance, PitchingAppearance
