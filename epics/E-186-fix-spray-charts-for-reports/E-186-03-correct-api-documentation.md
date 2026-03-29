# E-186-03: Correct API Documentation and CLAUDE.md

## Epic
[E-186: Fix Spray Charts for Standalone Reports](epic.md)

## Status
`TODO`

## Description
After this story is complete, all active documentation accurately describes the spray endpoint's asymmetric behavior. The false "both teams regardless of which UUID" claim is replaced with the verified behavior: returns both teams' data only when called with the owning team's UUID.

## Context
The incorrect claim that the spray endpoint returns both teams' data regardless of which UUID is used originated in E-158 and was reinforced in E-176. Live API verification on 2026-03-29 proved this false (see `.project/research/spray-endpoint-asymmetry.md`). Three active documentation files contain this claim and must be corrected per TN-5.

## Acceptance Criteria
- [ ] **AC-1**: `CLAUDE.md` spray chart pipeline bullet accurately describes the asymmetric behavior -- specifically that the endpoint returns both teams' data only when called with the owning team's gc_uuid.
- [ ] **AC-2**: `docs/api/endpoints/get-teams-team_id-schedule-events-event_id-player-stats.md` is corrected in all locations where "both teams" is stated without qualification. The frontmatter `notes`, status line, overview paragraph, and comparison table all reflect asymmetric behavior. A new caveat is added explaining the asymmetry with the date of verification (2026-03-29).
- [ ] **AC-3**: `docs/api/flows/spray-chart-rendering.md` Section 1 ("Per-Game: All Players, One Call") is corrected. The line "both teams' all players in a single API call" is qualified with "when called with the owning team's UUID." Section 8 ("What Was Validated") is updated to note the asymmetry discovery.
- [ ] **AC-4**: No archived files are modified (E-158, E-176 epic files remain frozen).
- [ ] **AC-5**: All documentation corrections use the canonical vocabulary defined in TN-1: "owning team" for the team whose schedule contains the game, "participant" for a team that played but does not own the schedule entry.

## Technical Approach
Read each file, identify all instances of the "both teams" claim, and replace with accurate descriptions of the asymmetric behavior. Use consistent terminology: "owning team" = the team whose schedule contains the game; "participant" = a team that played but does not own the schedule entry. Reference the 2026-03-29 verification date. Preserve the structure and formatting of each document.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-186-04

## Files to Create or Modify
- `CLAUDE.md` (spray chart pipeline bullet)
- `docs/api/endpoints/get-teams-team_id-schedule-events-event_id-player-stats.md` (multiple locations)
- `docs/api/flows/spray-chart-rendering.md` (Sections 1 and 8)

## Agent Hint
claude-architect

## Handoff Context
- **Produces for E-186-04**: Corrected documentation that E-186-04 can reference when codifying the bridge pattern. E-186-04 should use the same terminology for endpoint behavior.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The endpoint doc also has a correct caveat about "TEAM_ID SCOPE CONFIRMED BROAD" (line 49-54) noting the endpoint works with opponent `progenitor_team_id` values. This caveat is accurate and should be preserved -- the endpoint DOES work with any team's UUID, it just returns different data depending on whose UUID is used.
- The comparison table row "Both teams: Yes" (line 279) needs the most careful correction -- it should say something like "Both teams when called with owning team's UUID; single team otherwise."
