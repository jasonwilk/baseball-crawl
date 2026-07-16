# E-264-04: Endpoint-doc — authoritative ERA basis + K/G mislabel fix

## Epic
[E-264: League-Aware ERA Basis Fix](epic.md)

## Status
`DONE`

## Description
After this story is complete, the API docs will correctly document `settings.scorekeeping.bats.innings_per_game` as the authoritative per-team-season ERA (and K-per-game) basis reflecting the live empirical findings, and the `K/G` field will no longer be mislabeled as a per-9-innings rate in EITHER doc where it appears. This keeps our maintained API spec truthful to what GameChanger actually returns.

## Context
The api-scout investigation that motivated this epic established (against live GC data) that `innings_per_game` is a per-team-season configured integer (observed 6 or 7), does NOT map to age/league (two 12U teams differ; a 10U is 7), is readable from the authenticated `GET /teams/{gc_uuid}`, and is the basis GC uses for ERA and K/G. The current docs contradict this in three places — the `get-teams-team_id` `innings_per_game` speculation and the `K/G` mislabel in two separate endpoint docs (season-stats and player-stats) — and also imply GC exposes K/9 and BB/9 (it does not). This is a documentation-truth correction owned by api-scout (API behavior / endpoint schemas). It is independent of the code stories and can run in any order.

## Acceptance Criteria
- [ ] **AC-1**: `docs/api/endpoints/get-teams-team_id.md` documents `settings.scorekeeping.bats.innings_per_game` as the authoritative per-team-season ERA/K-per-game basis, reflecting the empirical findings in epic Technical Notes TN-1: a configured integer observed as 6 or 7, NOT an age/league mapping. The existing age/league speculation is corrected in FULL — both "likely 9 for HS varsity" AND "7 for travel ball" (currently at ~lines 91 and 104) — since the value is empirically per-team (HS observed as 7; travel-ball teams observed at 6), not age-derived. Given a reader of the endpoint doc, when they look up `innings_per_game`, then they learn it is the read-from-GC ERA basis, per-team, not age-derived.
- [ ] **AC-2**: The same doc no longer implies GameChanger exposes `K/9` or `BB/9` as stats (the current annotation at ~line 104 references them); it reflects that GC's game-length-based rate is K/G, and that K/9 as a per-9 rate is our own derived stat, not a GC field. (Reconcile with api-scout's authoritative knowledge of the season-stats field set.)
- [ ] **AC-3**: The `K/G` field description is corrected in BOTH docs where it appears — `docs/api/endpoints/get-teams-team_id-season-stats.md:212` (`Strikeouts per 9 innings`) AND `docs/api/endpoints/get-teams-team_id-schedule-events-event_id-player-stats.md:223` (`Strikeouts per game (9 innings)`) — to strikeouts per game-length, i.e. `innings_per_game × SO / IP`, matching GC's actual computation and NOT fixed at 9. (Complete audit, api-scout-confirmed: these are the only two K/G-mislabel occurrences in `docs/api`; the neighboring `K/BF` / `K/BB` / `BB/INN` labels in both docs are already accurate and must be left as-is.)
- [ ] **AC-4**: No real GameChanger identifiers (names, UUIDs, public_ids) are introduced into the docs (per `.claude/rules/pii-safety.md`). Any example values remain illustrative/sanitized.

## Technical Approach
Update the two endpoint docs named above to match the empirical findings (TN-1). api-scout owns the exact wording and any adjacent field-description reconciliation, since it holds the authoritative endpoint schema knowledge. Keep the factual API-endpoint description (what the API OFFERS) accurate; this is a factual correction, not a softening of a value verdict.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `docs/api/endpoints/get-teams-team_id.md` (modify — `innings_per_game` annotation; remove the "likely 9 for HS varsity" speculation and the K/9/BB/9 implication)
- `docs/api/endpoints/get-teams-team_id-season-stats.md` (modify — `K/G` field description at line 212)
- `docs/api/endpoints/get-teams-team_id-schedule-events-event_id-player-stats.md` (modify — `K/G` field description at line 223)

## Agent Hint
api-scout

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Code follows project style (see CLAUDE.md)
- [ ] Docs are factually accurate to the live API findings

## Notes
Independent of the code stories (E-264-01/02/03). Purely a docs-truth correction.
