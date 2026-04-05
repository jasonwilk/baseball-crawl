---
paths:
  - "src/api/**"
  - "src/reports/**"
  - "src/charts/**"
  - "src/gamechanger/loaders/**"
  - "src/gamechanger/parsers/**"
  - "src/reconciliation/**"
---

# Key Metrics We Track

These are the statistics and dimensions that matter for coaching decisions:
- **Batting**: OBP, strikeout rate, home/away splits, left/right pitcher splits
- **Pitching**: K/9, BB/9, left/right batter splits, home/away splits, GS/GR (games started / games relieved)
- **GS/GR (games started / games relieved)**: Combined display format `{gs}/{g-gs}` (e.g., `8/5` = 8 starts, 5 relief appearances). Placement: after G, before IP. Zero is data (`0/5` for pure reliever, `8/0` for pure starter) -- never use `—` for zero. NULL `gs` (unknown) displays `—`. Member teams get GS from the GC season-stats API; scouting/tracked teams compute GS from `appearance_order = 1` in boxscores. **Coaching priority**: GS is the single most actionable pitching stat for staff composition ("Martinez has 8 starts in 10 appearances -- he is your ace"). Workload interpretation depends on role: a starter at 85 pitches is normal, a reliever at 85 is a red flag.
- **Per-game splits**: Game-by-game batting and pitching lines for streak detection, recent form, and workload tracking
- **Box scores**: Per-player batting and pitching lines for both teams per game, including batting order, pitch counts, strike counts, and defensive positions -- from a single API call per game
- **Pitch-by-pitch plays**: Full pitch sequence per at-bat (balls, strikes, fouls, in-play), contact quality descriptions, baserunner events, fielder identity on outs, and in-game substitutions -- from a single API call per game via the plays endpoint. Stored in `plays` + `play_events` tables with pre-computed `is_first_pitch_strike` and `is_qab` flags.
- **FPS% (first pitch strike %)**: Pitching stat computed from plays data as `FPS / BF` (first pitch strikes divided by total batters faced) with no query-time exclusions -- HBP, Intentional Walk, and all other PA outcomes are included in the denominator. This matches GameChanger's calculation method. The `is_first_pitch_strike` flag records the actual first-pitch result for ALL PAs. **Coaching priority**: FPS% is the first stat coaches look at when scouting a pitching staff -- always surface it prominently.
- **QAB (quality at-bat)**: Batting stat. 7 qualifying conditions: 2S+3 (3+ pitches after 2-strike count), 6+ pitches, XBH, hard-hit ball (line drive / hard ground ball), walk (not IBB), sacrifice bunt, sacrifice fly. Intentional Walk, Dropped 3rd Strike, and Catcher's Interference are explicitly NOT QABs.
- **Spray charts**: Ball-in-play direction (x/y coordinates), play type, play result, fielder position -- for batting tendency analysis and defensive positioning
- **Players**: Key player identification (aces, closers, leadoff), lineup position history
- **Opponents**: Lineup patterns and changes, tendencies, roster composition, opponent season stats and boxscores (via scouting pipeline)
- **Longitudinal**: Player development across seasons, teams, and levels
- **Pitching workload**: 4-field model: `last_outing_date`, `last_outing_days_ago`, `pitches_7d` (rolling 7-day pitch count), `span_days_7d` (days covered in window). `pitches_7d` has 3 states: 0 (pitched but zero pitches recorded), NULL (no outings in window), SUM (normal). Shared query function `get_pitching_workload()` in `src/api/db.py` serves both dashboard and standalone reports (parity requirement). Display formats vary by surface: dashboard uses relative ("Xd ago"), report PDF uses absolute dates ("Mar 28"), report web uses JS-upgraded relative with absolute tooltip.
- **Pitcher attribution accuracy**: Coaching thresholds from domain consultation -- 90%+ accuracy required for FPS% reporting, 95%+ for pitch count reporting, 80%+ useful for development context. The reconciliation engine measures and corrects pitcher attribution using boxscore BF counts as ground truth.
- **Predicted starter**: Deterministic prediction of the opponent's probable starting pitcher for upcoming games, based on rotation patterns and availability. Domain heuristics: HS rotations are mostly ace-plus-committee or 2-man (true 3-man at competitive varsity; 4-man rare, mostly Legion). Availability exclusions: pitched within 1 day, 75+ pitches with <4 days rest, 10+ day gap = "availability unknown." Matchup deviation rate is ~20-30% (coaching decisions override rotation patterns). Prediction confidence is communicated to coaches as a qualitative signal, not a percentage.

The authoritative data dictionary mapping all GameChanger stat abbreviations to their definitions is at `docs/gamechanger-stat-glossary.md`. It includes batting, pitching, fielding, catcher, and positional innings stats, plus an API field name mapping table for cases where the API uses different abbreviations than the UI.
