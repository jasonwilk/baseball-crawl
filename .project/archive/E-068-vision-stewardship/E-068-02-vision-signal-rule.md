# E-068-02: Create Vision Signal Recognition Rule

## Epic
[E-068: Vision Stewardship](epic.md)

## Status
`DONE`

## Description
After this story is complete, a new rule file at `.claude/rules/vision-signals.md` will instruct all agents to recognize vision signals during conversations and append them to the parking lot at `docs/vision-signals.md`. The rule should be concise, explain what a vision signal is, and make capture as frictionless as possible.

## Context
Vision signals are statements about what the project will become, new capabilities it should have, how it will be used, or strategic direction it should take. These signals emerge naturally in conversation but currently evaporate. The rule needs to reach all agents (hence a `.claude/rules/` file with broad glob coverage), and it needs to lower the activation energy for capture to near-zero. Agents should err on the side of capturing -- signals can be discarded during curation, but lost signals cannot be recovered.

## Acceptance Criteria
- [ ] **AC-1**: `.claude/rules/vision-signals.md` exists with appropriate YAML frontmatter (glob pattern that covers all working directories -- `**`)
- [ ] **AC-2**: The rule defines what a vision signal is: a statement about what the project will become, new capabilities, user scenarios, strategic direction, or how the project will be used in ways not yet captured in `docs/VISION.md`
- [ ] **AC-3**: The rule instructs agents to append signals to `docs/vision-signals.md` using the format established in that file (date + brief description)
- [ ] **AC-4**: The rule explicitly states that capture should be low-friction and that agents should err on the side of capturing rather than filtering
- [ ] **AC-5**: The rule clarifies that agents should NOT modify `docs/VISION.md` directly -- that file is updated only during deliberate curation sessions with the user
- [ ] **AC-6**: The rule is concise (under 40 lines including frontmatter)

## Technical Approach
Create a new rule file in `.claude/rules/`. The frontmatter should use a broad glob pattern (`**`) so all agents see it. The body should define vision signals, give 2-3 examples of what qualifies, explain the capture mechanics (append to `docs/vision-signals.md`), and note the boundary (never edit `docs/VISION.md` directly). Keep it short -- agents will see this in every session, so brevity matters.

## Dependencies
- **Blocked by**: E-068-01
- **Blocks**: E-068-05

## Files to Create or Modify
- `.claude/rules/vision-signals.md` (new)

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Rule file has valid YAML frontmatter
- [ ] No regressions in existing tests

## Notes
The glob pattern `**` ensures all agents in all directories see the rule. This is intentional -- vision signals can emerge in any context (API exploration, coaching consultation, implementation work, etc.).
