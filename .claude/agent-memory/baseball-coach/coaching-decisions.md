# Coaching Decisions and Data Conventions

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
