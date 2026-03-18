# E-110-02: CLAUDE.md Workflows Entry

## Epic
[E-110: Iterative Review Rounds Convention](epic.md)

## Status
`TODO`

## Description
After this story is complete, the CLAUDE.md Workflows section will contain an entry for the review rounds pattern, mapping trigger phrases to the skill file created in E-110-01. This gives the main session the activation path to load the skill when the user requests iterative review loops.

## Context
CLAUDE.md's Workflows section is the canonical trigger-phrase-to-skill mapping. Every skill with user-facing activation phrases needs a corresponding Workflows entry so the main session knows when to load it. This story adds the entry for the review-rounds skill.

## Acceptance Criteria
- [ ] **AC-1**: A new entry exists in CLAUDE.md's `## Workflows` section for review rounds.
- [ ] **AC-2**: The entry lists trigger phrases that match the skill's Activation Triggers (e.g., "N rounds of refinement", "refine N times", "review with N rounds").
- [ ] **AC-3**: The entry references `.claude/skills/review-rounds/SKILL.md` as the skill to load.
- [ ] **AC-4**: The entry is a single markdown bullet matching the format of existing Workflows entries (bold workflow label, trigger phrase description, skill file path reference).
- [ ] **AC-5**: No other Workflows entries are modified.

## Technical Approach
Read the existing Workflows section in CLAUDE.md to match the established format (trigger phrase description, skill file reference, brief behavioral note). Add the new entry in a logical position relative to the existing review-related entries.

## Dependencies
- **Blocked by**: E-110-01
- **Blocks**: None

## Files to Create or Modify
- `CLAUDE.md` (modify -- Workflows section only)

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Entry follows the style of existing Workflows entries
- [ ] No regressions in existing Workflows entries

## Notes
- This is a small, focused edit -- a single new entry in an existing section.
