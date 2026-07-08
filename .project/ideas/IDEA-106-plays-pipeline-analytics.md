# IDEA-106: Plays-Pipeline Analytics Opportunities

## Status
`CANDIDATE` (renumbered + indexed 2026-07-08, E-255-06 — was the unnumbered `plays-pipeline-analytics.md`)

## Summary
A menu of derived analytics the pitch-by-pitch plays data can feed into scouting reports. The plays pipeline now EXISTS (`GET /game-stream-processing/{event_id}/plays` → `src/gamechanger/parsers/plays_parser.py` + `src/gamechanger/loaders/plays_loader.py`; landed in E-195, in-place repair + per-pitch `pitch_type`/`pitch_speed_mph` in E-245), and the headline first targets have SHIPPED — so this idea is now the forward-analytics menu on top of a working pipeline, not a "build the pipeline" idea.

## Source
Discovered during the E-194 spray-chart experiment session (2026-03-30). The GC plays endpoint provides full pitch-by-pitch data per at-bat for both own teams and opponents.

## Already delivered (was "First Targets")
- **FPS%** (First Pitch Strike %) — derived from the first pitch of each at-bat. Shipped (honest FPS denominators landed in E-245).
- **QAB** (Quality At-Bat) — shipped (`is_qab` OR-merge in E-245).

## Forward analytics menu (the remaining value)
- Pitch count per at-bat (approach analysis)
- Situational hitting (RISP, 2 outs, etc.)
- Baserunning events (stolen bases, advances on wild pitches, passed balls)
- Contact quality per at-bat (hard ground ball, line drive, fly ball)
- Scoring plays (who drove in which runs)
- Pitcher workload tracking (pitch-by-pitch stress indicators)
- Two-strike approach analysis (foul-ball rate, chase rate)
- Count-specific batting splits (0-2 vs 3-1, etc.)

## Key Constraint
Accuracy above all. Derived stats require careful template-string parsing and game-state tracking (current pitcher, baserunner positions). Binds the CLAUDE.md "always get closer to byte-identical play ingestion" North Star — the ingestion/storage layer must reconcile before derived stats are trusted.

## Rough Timing
Scorekeeper-coverage dependent (per-pitch fields are only as good as the opponent's scorekeeping). Promote a specific slice when a coach names the analytic they want or when pitch-mix work (IDEA-086) begins.

## Overlaps / related ideas
- IDEA-086 (leverage pitch selection + velocity — pitch-mix/sequencing/velocity)
- IDEA-030 (fielding, catcher, pitch-type tables)
- IDEA-038 (query-time splits and streaks)
- IDEA-041 (play-by-play stat compilation pipeline)
- IDEA-062 (plays-vs-boxscore reconciliation — the accuracy foundation, now delivered)

## Notes
- Renumbered from the unindexed `plays-pipeline-analytics.md` during E-255-06 AC-2 (ideas README ↔ files reconciliation). Content refreshed to reflect that the pipeline + FPS%/QAB shipped.

---
Created: 2026-03-30
Last reviewed: 2026-07-08
Review by: 2026-10-06
