# IDEA-063: /dump-game Diagnostic Skill

## Status
`CANDIDATE`

## Summary
A `/dump-game <game-id>` skill that pulls every API endpoint for a single game (boxscore, plays, spray charts, line scores, game details) and dumps the raw responses to a local directory for offline investigation of data quality gaps.

## Why It Matters
During E-198 reconciliation accuracy investigation, diagnosing discrepancies required manually fetching multiple endpoints per game and cross-referencing responses. A single command that captures all game data would dramatically accelerate gap exploration and future data quality debugging. Also useful for investigating scorekeeper corrections (Error→Hit), missing pitch events, and courtesy runner edge cases.

## Rough Timing
After E-201 (reconciliation accuracy) ships. The accuracy gaps investigation surfaced the need; the skill would make future investigations much faster.

## Dependencies & Blockers
- [ ] E-198 (reconciliation engine) -- COMPLETED
- [ ] Authenticated GameChanger client available in CLI context
- [ ] Knowledge of all per-game endpoints (boxscore, plays, spray, line scores, game-stream events)

## Open Questions
- Should it also fetch the raw game-stream events endpoint (`GET /game-streams/gamestream-viewer-payload-lite/{event_id}`)? This is the most complete pitch-level data source but requires authenticated access.
- Output format: flat directory of JSON files per endpoint, or a single merged JSON?
- Should it work for both member and tracked teams, or only games where we have auth?

## Notes
- User requested this during E-201 planning (2026-04-02)
- Related to API Note C in the E-198 research doc: the raw game-stream events endpoint is the most promising source for missing pitch events
- Endpoints to include: boxscore, plays, spray chart player-stats, public game details (line scores), and optionally raw game-stream events

---
Created: 2026-04-02
Last reviewed: 2026-04-02
Review by: 2026-07-01
