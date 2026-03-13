# E-104-02: Document player_id to athlete_profile_id Lookup Path

## Epic
[E-104: Athlete Profile Endpoint Probe -- Opponent Player Access](epic.md)

## Status
`TODO`

## Description
After this story is complete, the `docs/api/` documentation will include a flow document describing the confirmed path from a boxscore `player_id` to an `athlete_profile_id` (or document that no such path exists for opponents). The API README index will be updated with cross-references, and any schema gaps discovered during the probe will be documented in the relevant endpoint files.

## Context
E-104-01 produces a probe summary with raw findings about which endpoints work for opponents and how the ID bridge works. This story takes those findings and integrates them into the project's API documentation structure -- the flow doc, the README index, and any endpoint file updates that go beyond status/last_confirmed changes (e.g., new fields discovered, caveats refined, cross-references added).

## Acceptance Criteria
- [ ] **AC-1**: A new flow document is created at `docs/api/flows/athlete-profile-resolution.md` describing: (a) the step-by-step path from `player_id` to `athlete_profile_id`, (b) which endpoints are called in what order, (c) auth requirements at each step, (d) whether the path works for opponent players or only own-team, (e) any rate/size considerations (the career-stats endpoint returns ~31KB per player).
- [ ] **AC-2**: `docs/api/README.md` is updated: (a) the four athlete-profile endpoint rows reflect their confirmed status, (b) a cross-reference to the new flow doc is added in the appropriate section.
- [ ] **AC-3**: If the probe found that `person_id` == `athlete_profile_id` (or discovered a different bridge), the `get-players-player_id.md` doc is updated with a note explaining the relationship and a `see_also` entry pointing to the athlete-profile endpoints.
- [ ] **AC-4**: If the probe found that opponent access is restricted, a caveat is added to each affected athlete-profile endpoint doc specifying the restriction (e.g., "Returns HTTP 403 for players not linked to the authenticated user's family/guardian account").
- [ ] **AC-5**: If the probe discovered any new fields not in the existing endpoint docs (e.g., `athlete_profile_id` appearing in roster or boxscore responses), those fields are added to the relevant endpoint doc's response table.

## Technical Approach
Read the probe summary at `/.project/research/E-104-athlete-profile-probe.md` (produced by E-104-01) for all findings. The flow doc should follow the style of the existing `docs/api/flows/opponent-scouting.md`. The README update should follow existing patterns for flow doc cross-references.

## Dependencies
- **Blocked by**: E-104-01
- **Blocks**: None

## Files to Create or Modify
- `docs/api/flows/athlete-profile-resolution.md` (new)
- `docs/api/README.md` (update status rows, add flow doc reference)
- `docs/api/endpoints/get-players-player_id.md` (conditional -- if bridge relationship discovered)
- `docs/api/endpoints/get-athlete-profile-athlete_profile_id.md` (conditional -- if caveats or new fields)
- `docs/api/endpoints/get-athlete-profile-athlete_profile_id-players.md` (conditional)
- `docs/api/endpoints/get-athlete-profile-athlete_profile_id-career-stats-association.md` (conditional)
- `docs/api/endpoints/get-athlete-profile-athlete_profile_id-career-stats.md` (conditional)

## Agent Hint
api-scout

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Flow doc follows existing conventions in `docs/api/flows/`
- [ ] README index reflects current endpoint statuses
- [ ] No credentials, tokens, or PII in any committed files

## Notes
- Several ACs are conditional on what E-104-01 discovers. If opponent access is fully open with no restrictions, AC-4 becomes N/A. If no new fields are discovered, AC-5 becomes N/A. The api-scout should note "N/A -- [reason]" for any non-applicable ACs.
