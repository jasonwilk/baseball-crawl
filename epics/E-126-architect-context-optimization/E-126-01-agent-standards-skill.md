# E-126-01: Create Agent-Standards Skill and Refactor Agent Definition

## Epic
[E-126: Optimize Claude-Architect Context Footprint](epic.md)

## Status
`TODO`

## Description
After this story is complete, the claude-architect agent definition will be ~90 lines shorter. The Standards and Design Methodology sections will live in a new `agent-standards` skill that loads on demand when the architect creates or modifies agents. The agent roster duplication will be replaced with a pointer to CLAUDE.md.

## Context
The architect's agent definition is 227 lines -- the second largest. ~96 lines are reference material (Standards ~85 lines, Design Methodology ~11 lines) used only during agent creation/modification sessions (~20% of interactions). An additional ~9 lines duplicate the Agent Ecosystem table already in CLAUDE.md. Deferring this content to a skill and removing duplication reduces ambient load without losing any capability.

## Acceptance Criteria
- [ ] **AC-1**: A skill file exists at `.claude/skills/agent-standards/SKILL.md` containing the Standards section content and Design Methodology section content currently in the agent definition.
- [ ] **AC-2**: The agent definition at `.claude/agents/claude-architect.md` no longer contains the Standards section or Design Methodology section. A Skills section entry references `agent-standards` with a load trigger broad enough to cover all agent-related work (creating, modifying, and auditing agent definitions).
- [ ] **AC-3**: The agent roster in the Identity section of the agent definition is replaced with a single-line reference to CLAUDE.md's Agent Ecosystem table.
- [ ] **AC-4**: The agent definition is under 140 lines.
- [ ] **AC-5**: Every section removed from the agent definition exists verbatim (or with only formatting changes) in the skill file, or is covered by an explicit reference to CLAUDE.md. Verified by diff comparison of removed content against skill file contents.

## Technical Approach
The architect should read its own agent definition, identify the exact line ranges for Standards, Design Methodology, and the agent roster, extract them into the new skill file, and update the agent definition with references. Per TN-1 and TN-2 in the epic.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `.claude/skills/agent-standards/SKILL.md` (create)
- `.claude/agents/claude-architect.md` (modify)

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] No regressions in existing agent behavior
- [ ] Code follows project style (see CLAUDE.md)

## Notes
Line counts are approximate -- the architect should use actual content boundaries when extracting.
