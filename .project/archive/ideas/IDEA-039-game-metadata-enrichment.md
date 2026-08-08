# IDEA-039: Game Metadata Enrichment

## Status
`CANDIDATE`

## Summary
Enrich the `games` table with additional metadata: `venue_name` (likely available in GC data), `is_doubleheader` / `doubleheader_game_num` (derivable from schedule or GC data), and `game_num_in_week` (computed from schedule). These enable workload tracking, doubleheader splits, and venue-aware analysis.

## Why It Matters
Baseball-coach consultation (2026-03-16) identified game-level metadata as SHOULD HAVE:

- **venue_name:** Where a game was played. Useful for neutral-site tournaments (common in USSSA/travel ball). May also help with home/away disambiguation when the "home" field in GC data is ambiguous.
- **is_doubleheader / doubleheader_game_num:** Enables IDEA-038's doubleheader fatigue splits. Game 2 pitching decisions are critical.
- **game_num_in_week:** Workload tracking signal. "This is our 4th game this week — adjust pitching plan."

## Rough Timing
After E-117 ships. May require schema migration (new columns on `games` table). Promote when:
- IDEA-038 (query-time splits) needs doubleheader metadata
- Coach asks about workload tracking
- api-scout confirms whether venue_name is in GC game data

## Dependencies & Blockers
- [ ] E-117 (base stat population) — establishes the game data flow
- [ ] Schema migration for new `games` columns (venue_name, is_doubleheader, doubleheader_game_num, game_num_in_week)
- [ ] api-scout: confirm whether venue_name is in game-summaries or public game data
- [ ] Doubleheader detection: confirm whether GC has an explicit field or if it must be derived from schedule (same date + same opponent)

## Open Questions
- Does the game-summaries endpoint include venue/location data?
- Does GC flag doubleheaders explicitly, or do we derive from schedule?
- Is `game_num_in_week` a stored column or a query-time computation from game dates? (Stored is simpler for queries; computed avoids schema change.)
- Should this include `weather` or `field_condition` if GC provides them? (Probably over-engineering for HS.)

## Notes
- Coach priority (2026-03-16): SHOULD HAVE. Supports workload tracking and doubleheader splits.
- `venue_name` is likely in GC game data but hasn't been confirmed.
- `game_num_in_week` could be computed at query time from game dates without a schema column. May not need migration.
- Related: IDEA-038 (query-time splits) depends on doubleheader metadata from this idea.

---
Created: 2026-03-16
Last reviewed: 2026-03-16
Review by: 2026-06-14
