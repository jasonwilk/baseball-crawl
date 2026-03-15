# E-NNN-SS: Story Title

## Epic
[E-NNN: Epic Title](../E-NNN-slug/epic.md)

## Status
`TODO`

## Description
<!-- Two to five sentences. Write from the outcome perspective: "After this story is complete, the system will..." -->

## Context
<!-- Why does this story exist? How does it fit into the epic? What does the agent need to know? -->

## Acceptance Criteria
<!-- ACs verify outcomes, not procedures. If an AC needs to reference a procedure or constraint
     defined in Technical Notes, write "per Technical Notes section X" rather than restating the
     content inline. Restating creates a sync surface that drifts during refinement.
     If an AC has more than 3 sub-clauses, consider decomposing it into separate ACs or converting
     the detailed sub-clauses into a Technical Notes section with a single AC reference. -->
- [ ] **AC-1**: Given [precondition], when [action], then [expected result]
- [ ] **AC-2**: Given [precondition], when [action], then [expected result]

## Technical Approach
<!-- Suggested implementation approach. Guidance, not mandate. -->

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
<!-- List every file this story is expected to touch. Mandatory for parallel execution. -->

## Agent Hint
<!-- Optional. Routing hint for PM -- declares which agent type should implement this story.
     Valid values are agent names as they appear in .claude/agents/ filenames:
     software-engineer, data-engineer, claude-architect, docs-writer, ux-designer, api-scout.
     If the hint disagrees with the routing table in dispatch-pattern.md, the routing table wins.
     Omit this field entirely for stories with no routing preference. -->

## Handoff Context
<!-- Optional. Declares what artifacts this story produces for downstream stories.
     Use a bulleted list where each bullet names a downstream story ID and describes what it needs.
     Omit this section entirely for stories with no downstream consumers.
     Example:
     - **Produces for E-NNN-SS**: Description of artifact and what the downstream story needs from it.
-->

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
<!-- Additional context, links, or reference material. -->
