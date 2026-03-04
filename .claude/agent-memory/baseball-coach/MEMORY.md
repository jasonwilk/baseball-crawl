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
