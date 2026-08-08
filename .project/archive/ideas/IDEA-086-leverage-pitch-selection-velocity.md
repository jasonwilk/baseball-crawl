# IDEA-086: Leverage Pitch Selection + Velocity in Scouting

## Status
`CANDIDATE`

## Summary
Now that E-245 STORES per-pitch `pitch_type` and `pitch_speed_mph` on `play_events` (captured from
the plays endpoint's trailing annotation), a future capability could surface pitch-mix, sequencing
tendencies, and velocity in scouting reports — e.g. "this arm throws ~70% fastballs, sits 72-76,
goes to the curve in two-strike counts." Per-pitch timing also exists in the raw events endpoint
(`GET /game-streams/{game_stream_id}/events`) if sequencing-by-time is ever needed.

## Why It Matters
Pitch type and velocity are among the most actionable scouting signals a coach can get on an
opposing pitcher — what's coming, how hard, and in which counts. The data is now captured at no
extra ingestion cost (it rides the same plays payload). This turns a storage byproduct into a
coaching feature.

## Rough Timing
After E-245 ships (storage foundation) AND once enough opponents are scouted by scorekeepers who
chart pitch type/velocity (coverage is scorekeeper-dependent — many teams don't chart type at all,
so the feature is only useful for opponents that do). Promote when a coach asks for pitch-mix, or
when a critical mass of charted-type opponents exists.

## Dependencies & Blockers
- [x] E-245 stores `pitch_type` + `pitch_speed_mph` (storage foundation)
- [ ] Enough scouted opponents with pitch-type/velocity charting for the feature to be useful
- [ ] Coach-defined requirements: which pitch-mix/sequencing/velocity cuts are actionable

## Open Questions
- Which views are worth building first: pitch-mix %, velocity bands, count-based sequencing, or a
  combined pitcher pitch-profile card?
- How to honestly present coverage (this data only exists for opponents whose scorekeepers charted
  type/velocity — most don't), consistent with the data-bearing-coverage and "never suppress,
  always contextualize" principles.
- Is the flattened plays annotation sufficient, or does any cut require the structured/timestamped
  raw events endpoint?
- How does the closed 6-value type vocabulary (incl. `Unclear`) map to coach-facing labels?

## Notes
- Storage foundation: E-245 (high-fidelity play ingestion).
- Grammar / source of truth: `docs/api/endpoints/get-game-stream-processing-event_id-plays.md`
  ("Pitch event grammar"); structured + timestamped pitch fields in
  `docs/api/endpoints/get-game-streams-game_stream_id-events.md`.
- Related: IDEA-030 (Fielding, Catcher, and Pitch Type Tables) overlaps on pitch-type storage —
  reconcile scope if both advance.

---
Created: 2026-06-29
Last reviewed: 2026-06-29
Review by: 2026-09-27
