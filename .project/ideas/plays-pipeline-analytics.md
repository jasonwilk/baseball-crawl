# Plays Pipeline Analytics Opportunities

## Source
Discovered during E-194 spray chart experiment session (2026-03-30). The GC plays endpoint (`GET /game-stream-processing/{event_id}/plays`) provides full pitch-by-pitch data per at-bat for both own teams and opponents.

## First Targets (being planned as epic)
- **FPS%** (First Pitch Strike %) -- derivable from first entry in each at-bat's pitch sequence
- **QAB** (Quality At-Bat) per game/per at-bat -- derivable from pitch counts, outcomes, contact quality

## Future Analytics (once plays pipeline exists)
- Pitch count per at-bat (approach analysis)
- Situational hitting (RISP, 2 outs, etc.)
- Baserunning events (stolen bases, advances on wild pitches, passed balls)
- Contact quality per at-bat (hard ground ball, line drive, fly ball)
- Scoring plays (who drove in which runs)
- Pitcher workload tracking (pitch-by-pitch stress indicators)
- Two-strike approach analysis (foul ball rate, chase rate)
- Count-specific batting splits (0-2 vs 3-1 etc.)

## Key Constraint
Accuracy above all. The plays data requires careful parsing of template strings and game state tracking (who is currently pitching, baserunner positions). The ingestion and storage layer must be rock-solid before any derived stats are computed.

## Status
CANDIDATE -- first epic (FPS% + QAB) being planned now.
