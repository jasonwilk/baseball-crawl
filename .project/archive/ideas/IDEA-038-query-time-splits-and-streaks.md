# IDEA-038: Query-Time Splits and Streaks

## Status
`CANDIDATE`

## Summary
Implement query-time computation of coaching-priority splits and streaks from per-game stat data: recent form (last 5-7 games vs. season), doubleheader splits (game 1 vs. game 2), and season phase splits (early/mid/late/playoffs). All are computed at query time from `player_game_batting` and `player_game_pitching` rows — no schema changes needed, no pre-aggregated columns.

## Why It Matters
Baseball-coach consultation (2026-03-16) identified these as the highest-value splits for HS/youth coaching, above traditional home/away or L/R splits:

- **Recent form (MUST HAVE per coach):** "Is this kid hot or cold right now?" Last 5-7 games vs. full season. Streak detection (hitting streak, slump). The single most actionable split for lineup decisions and player confidence.
- **Doubleheader splits (SHOULD HAVE):** Game 1 vs. Game 2 performance as a fatigue/workload signal. Critical for pitching decisions ("don't start him Game 2 if he threw 80+ pitches in Game 1").
- **Season phase splits (SHOULD HAVE):** Early/mid/late/playoff performance for development tracking. "Is this kid getting better as the season goes on?"

The key insight: the most valuable HS coaching splits are query-time computations over per-game data, not pre-aggregated columns. E-117 (per-game stat population) is the prerequisite for all of them.

## Rough Timing
After E-117 ships and per-game stat data is flowing. Promote when:
- E-117 is complete (per-game stats populated)
- Dashboard development begins (needs query endpoints to power views)
- Coach asks for "how is [player] doing lately?"

## Dependencies & Blockers
- [ ] E-117 (per-game stat population) — all computations rely on populated `player_game_batting` and `player_game_pitching` rows
- [ ] For doubleheader splits: need `is_doubleheader` / `doubleheader_game_num` metadata on games (see IDEA-039) OR ability to derive from schedule (same opponent, same date)
- [ ] For season phase splits: need a definition of early/mid/late/playoffs (date ranges or game count thresholds per season)
- [ ] Dashboard query layer must exist to serve these computations

## Open Questions
- **Recent form window:** Coach said 5-7 games. Should this be configurable, or fixed at 7?
- **Streak detection:** What constitutes a "streak"? Multi-hit games in a row? OBP above .400 for N games? Need coach to define thresholds.
- **Season phase boundaries:** Date-based (first third / middle third / last third of schedule)? Or game-count-based (games 1-10, 11-20, 21-30)? Or milestone-based (pre-conference, conference, playoffs)?
- **Doubleheader derivation:** Can we detect doubleheaders from the game schedule (same date, same opponent)? Or does GC provide an explicit field?
- **Small sample flag (coach requirement):** Any sub-split must be flagged as small sample. HS seasons are 80-100 PA; 5-7 game windows have 15-25 PA. Dashboard must communicate confidence level.

## Notes
- All three splits are pure query-time computations — no schema migration, no new columns, no pre-aggregation.
- Implementation is likely query functions in `src/api/db.py` (or a new queries module) that dashboard routes call.
- Related: IDEA-029 (L/R splits) is the handedness-dependent split work — lower priority, blocked by data availability. IDEA-037 (scouting report redesign) would consume these splits in report output.
- **Coach priority (2026-03-16):** Recent form = MUST HAVE. Doubleheader + season phase = SHOULD HAVE.

---
Created: 2026-03-16
Last reviewed: 2026-03-16
Review by: 2026-06-14
