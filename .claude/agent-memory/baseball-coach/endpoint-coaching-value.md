# Endpoint Coaching Value -- Per-Game Stats, Boxscore, and Plays

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
