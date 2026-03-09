# E-068-05: Update CLAUDE.md with Vision System References

## Epic
[E-068: Vision Stewardship](epic.md)

## Status
`DONE`

## Description
After this story is complete, CLAUDE.md will reference the vision system in two places: (1) the Workflows section will include "curate the vision" as a trigger phrase that invokes the PM, and (2) the docs/vision files will be discoverable through existing documentation references. This ensures agents and users know the vision system exists and how to invoke it.

## Context
CLAUDE.md is the project's top-level instruction file, loaded for every agent in every session. It already has a Workflows section listing trigger phrases ("implement", "ingest endpoint", "review epic", "spec review"). Adding "curate the vision" to this section follows the established pattern. The vision files (`docs/VISION.md` and `docs/vision-signals.md`) should also be referenced so they are discoverable.

This story depends on all other E-068 stories being complete so that CLAUDE.md references are accurate -- the rule, closure step, PM definition, and parking lot file all need to exist before CLAUDE.md points to them.

## Acceptance Criteria
- [ ] **AC-1**: The Workflows section of `CLAUDE.md` includes a "Curate the vision" entry following the pattern of existing workflow entries. It should state the trigger phrase, name the PM as the responsible agent, and briefly describe what happens (review signals, discuss with user, refine vision document).
- [ ] **AC-2**: `docs/VISION.md` and `docs/vision-signals.md` are referenced in the `## Project Management > ### Key Directories` section of CLAUDE.md.
- [ ] **AC-3**: The Workflows entry follows the structure of existing entries (trigger phrase, agent/skill reference, brief description). The docs reference is a single line or table row, not a multi-paragraph explanation. Total additions are under 15 lines.
- [ ] **AC-4**: No existing CLAUDE.md content is removed or altered beyond the targeted additions.

## Technical Approach
Two targeted additions to `CLAUDE.md`. The Workflows section already has four entries with a consistent format (trigger phrase, skill/agent reference, brief description). Add a fifth entry for "curate the vision" following the same pattern. For file discoverability, add the vision files to the Key Directories table in the Project Management section of CLAUDE.md.

## Dependencies
- **Blocked by**: E-068-01, E-068-02, E-068-03, E-068-04
- **Blocks**: None

## Files to Create or Modify
- `CLAUDE.md`

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] CLAUDE.md remains well-structured and readable
- [ ] No regressions in existing tests

## Notes
This is the final story in the epic. It exists to ensure the vision system is discoverable from the top-level project instructions. The actual mechanics are established by stories 01-04.
