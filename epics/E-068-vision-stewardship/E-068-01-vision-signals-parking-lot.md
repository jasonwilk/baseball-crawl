# E-068-01: Create Vision Signals Parking Lot and Seed First Signal

## Epic
[E-068: Vision Stewardship](epic.md)

## Status
`TODO`

## Description
After this story is complete, `docs/vision-signals.md` will exist as an ultra-lightweight parking lot for raw vision signals. It will contain a brief header explaining the file's purpose and format, plus one seed signal capturing the LLM-powered coaching chat agent idea that Jason mentioned in conversation. The format is intentionally minimal -- no frontmatter, no template, no ceremony.

## Context
Vision signals are statements about what the project will become or how it will be used. They currently evaporate when sessions end. This file is the first of two vision artifacts (the other being the already-existing `docs/VISION.md`). The parking lot must be so simple that any agent can append a line without friction. Jason specifically mentioned wanting an LLM-powered chat agent built into the dashboard where coaches can ask questions about matchups and get strategy insights -- this signal needs to be captured as the seed entry so it does not get lost.

## Acceptance Criteria
- [ ] **AC-1**: `docs/vision-signals.md` exists with a brief header (2-4 lines) explaining what the file is, who writes to it, and the expected entry format
- [ ] **AC-2**: The entry format shown in the header is minimal: date, one or two sentences, optional source context. No structured template or frontmatter.
- [ ] **AC-3**: The file contains at least one seed signal capturing the LLM-powered coaching chat agent idea (date: 2026-03-07, content: Jason envisions an LLM-powered chat agent built into the dashboard where coaches can ask questions about matchups and get strategy insights)
- [ ] **AC-4**: The file uses a clear visual separator between the header and the signals section (e.g., a markdown heading like `## Signals`)

## Technical Approach
This is a new markdown file in `docs/`. The header should explain the purpose (raw parking lot for vision signals), who appends (any agent), and the format convention (date + brief description). The signals section follows. The seed signal captures the coaching chat agent idea with a 2026-03-07 date. Keep the whole file under 20 lines.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-068-05

## Files to Create or Modify
- `docs/vision-signals.md` (new)

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] File is valid markdown
- [ ] No regressions in existing tests

## Notes
The seed signal text should be concise -- one or two sentences capturing the essence of what Jason described. Do not elaborate or speculate beyond what was said.
