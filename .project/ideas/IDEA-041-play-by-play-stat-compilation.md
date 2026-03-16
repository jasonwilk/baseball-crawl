# IDEA-041: Play-by-Play Stat Compilation Pipeline

## Status
`CANDIDATE`

## Summary
Parse play-by-play data from the plays endpoint to derive advanced per-game stats (QAB, pitches seen per batter, contact quality, swing metrics, etc.), validate derived counting stats against boxscore data, and compile game-level results into season aggregates. This achieves full stat parity between owned teams (season-stats API) and opponent teams (our own compilation).

## Why It Matters
After E-117, member teams get full stat coverage via the season-stats API — GC does the compilation for us. But opponent teams only get basic counting stats from boxscore aggregation. Advanced stats that coaches value (QAB, contact quality, pitch discipline metrics, etc.) are missing for opponents. The plays endpoint already captures this data pitch-by-pitch — we just need to compile it.

This is the path to full opponent data parity: same advanced stats, just computed by us instead of GC. It also enables validation: derived counting stats (H, BB, SO, etc.) should match boxscore data, giving confidence in the compilation logic.

## Rough Timing
After E-117 is complete (boxscore foundation must be solid first). This is a major epic — likely the largest data pipeline work in the project. Promote when:
- E-117 is shipped and a full data re-seed has run
- Coaching staff requests advanced opponent stats (scouting reports, matchup prep)
- The gap between member and opponent stat coverage becomes a real coaching pain

## Dependencies & Blockers
- [ ] E-117 (Loader Stat Population) must be complete — boxscore foundation
- [ ] Plays endpoint already documented (`docs/api/endpoints/get-game-stream-processing-game_stream_id-plays.md`)
- [ ] Stat glossary has play event types documented (`docs/gamechanger-stat-glossary.md` — Play Event Types section)
- [ ] May need baseball-coach consultation on which advanced stats matter most for scouting

## Open Questions
- Which advanced stats should be prioritized? QAB, PS/PA, contact quality, and swing metrics are likely top candidates. Baseball-coach should weigh in.
- How to handle stat definitions precisely? E.g., QAB has a specific multi-condition definition (3+ pitches after 2 strikes, 6+ pitch ABs, XBH, HHB, BB, SAC Bunt, SAC Fly). Need to match GC's definitions exactly for validation to work.
- What's the validation tolerance? Should derived counting stats match boxscore data exactly, or is some tolerance acceptable (e.g., for edge cases in play-by-play parsing)?
- Should this pipeline run alongside boxscore loading or as a separate pass? Play-by-play data is much larger than boxscores.
- Would this also benefit member teams? Running compilation on member team play-by-play data and comparing against the season-stats API would be a powerful validation of both our logic and GC's compilation.

## Notes
The plays endpoint (`GET /game-stream-processing/{game_stream_id}/plays`) uses the same `game_stream_id` as the boxscore endpoint — no additional ID resolution needed. The endpoint returns full pitch sequences per at-bat with contact quality descriptions, baserunner events, and fielder identity.

The user's key insight: the season-stats API for member teams is essentially "GC did the compilation for us." For opponents, we do it ourselves. This pipeline is the "do it ourselves" path.

Related ideas:
- IDEA-009 (Per-Player Game Stats + Spray Charts) — spray chart data comes from a different endpoint but serves a similar "enrich opponent data" goal
- IDEA-038 (Query-Time Splits and Streaks) — depends on per-game data being available, which this pipeline would enrich
- IDEA-040 (Optimistic Pitching Column API Audit) — less relevant for opponents since we'd compute those stats ourselves via this pipeline

---
Created: 2026-03-16
Last reviewed: 2026-03-16
Review by: 2026-06-14
