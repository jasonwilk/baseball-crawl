# Baseball Coach -- Agent Memory

## Team Scope

Lincoln Standing Bear High School baseball program:
- Four teams: Freshman, JV, Varsity, Reserve
- Legion teams added later (different competition level, different season)
- 12-15 players per team
- ~30-game seasons
- Jason is the system operator; coaching staff are the end consumers
- Coaches see dashboards and reports -- they do not interact with the system directly

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
- Soft referential integrity: orphaned player IDs in stats tables accepted with WARNING, not rejected
- Key entities: Team, Player, PlayerTeamSeason, Game, Lineup, PlateAppearance, PitchingAppearance
