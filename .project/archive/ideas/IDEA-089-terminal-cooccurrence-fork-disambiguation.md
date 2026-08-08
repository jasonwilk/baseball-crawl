# IDEA-089: Terminal Co-occurrence Fork Disambiguation (auto-collapse same-human forks)

## Status
`CANDIDATE`

## Summary
Use same-game co-occurrence between the *terminals* of a prefix-connected player component to safely auto-collapse a genuine same-human fork (e.g. "Jo" prefixing both "John" and "Jon" where all three are one kid) while still refusing a true two-human fork (e.g. "O" prefixing both "<NAME-REDACTED>" and "Owen" — two distinct kids). This is the Tier 2 follow-on to E-249, which deliberately refuses ALL forks (leaving same-human residuals unmerged) because prefix matching alone cannot distinguish the two cases.

## Why It Matters
E-249 (Tier 1) stops the dedup error cascade and closes the silent cross-merge (Mode B) by refusing every fork. But that conservatism leaves a residual: a roster where one real human appears under a forking prefix structure (Jo/John/Jon) stays split into multiple `players` rows → multiple `player_season_*` rows → split/halved stat lines and a phantom extra "player" in the opponent scouting report (the visible Mode A symptom — e.g. "51 players on a 19-man roster"). Coach confirmed Mode A is self-revealing and operator-recoverable, tolerable for one follow-up sprint, but it still degrades the report. Tier 2 recovers the same-human forks automatically and safely, getting the roster count closer to truth without reintroducing the cross-merge regression.

The disambiguation signal already exists in the codebase: `_check_game_overlaps` / `has_overlapping_games` in `src/db/player_dedup.py` detects whether two player_ids appear in the same game from the team's own perspective. Two terminals that NEVER co-occur in a game are plausibly the same human (one person cannot bat/pitch as two players in one game); two terminals that DO co-occur are provably distinct humans (both appeared in the same game). Today this overlap is computed per detected pair; Tier 2 needs it computed between component TERMINALS to drive the collapse/refuse decision.

## Rough Timing
Next sprint after E-249 ships. Trigger: E-249 is merged and the live `team_id=196` data has been re-run through the fixed dedup (the E-249 operator follow-up), so we have a concrete count of how many refused-fork residuals actually remain in production and whether they are genuine same-human forks. Validate the co-occurrence heuristic against that live data BEFORE building the auto-collapse.

## Dependencies & Blockers
- [ ] E-249 (connected-components dedup fix with fork refusal) must be COMPLETED.
- [ ] The E-249 operator follow-up (re-run dedup on the live DB, inspect `team_id=196` refused-fork residuals) must be done, to validate the co-occurrence heuristic against real data.

## Open Questions
- Is "terminals never co-occur in any game" a sufficient signal to auto-collapse, or does it produce false collapses (two genuinely distinct kids who happen never to have shared a game in the loaded data — e.g. a backup who only played when the starter sat)? What confidence threshold / minimum games-loaded gate is needed?
- When a fork has 3+ terminals with mixed co-occurrence (A and B never co-occur, but A and C do), how is the component partitioned — which terminals collapse together and which stay separate?
- Does the durable/queryable operator surfacing of refused forks belong here (a small review table or surfacing on the report run record), now that the WARN-log-only Tier 1 decision is in place? E-249 deferred durable surfacing to this idea.
- How does the canonical-name choice interact with collapse (which terminal's name wins when two same-human terminals merge)?

## Notes
Split out of E-249 (the stale-worklist dedup fix) during E-249 discovery, 2026-06-30. E-249's Non-Goals explicitly carve this out. The conservative refuse-all-forks rule in E-249 is intentionally the floor; this idea raises it. Related prior art: IDEA-043 (fuzzy duplicate detection), IDEA-082 (twin-athlete UUID resolution). Coaching-impact framing from baseball-coach: silent wrong attribution (Mode B) is the trust-killer and must never be reintroduced — any Tier 2 auto-collapse MUST preserve E-249's no-cross-merge guarantee for true two-human forks.

---
Created: 2026-06-30
Last reviewed: 2026-06-30
Review by: 2026-09-28 (90 days from created)
