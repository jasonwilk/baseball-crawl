# E-072-02: Register Skill in CLAUDE.md and Update Context Layer

## Epic
[E-072: Proxy Session Ingestion Skill](epic.md)

## Status
`TODO`

## Description
After this story is complete, the `ingest-session` skill is registered in `CLAUDE.md`'s Workflows section so the main session knows to load it when the operator uses the trigger phrases. Any other context-layer files that reference skill inventory or workflow triggers are updated to include the new skill.

## Context
Skills are discoverable through CLAUDE.md's Workflows section. Without this registration, the main session will not know to load `.claude/skills/ingest-session/SKILL.md` when the operator says "ingest session." This story follows the same pattern established when `ingest-endpoint`, `implement`, `review-epic`, and `spec-review` skills were each registered in CLAUDE.md.

## Acceptance Criteria
- [ ] **AC-1**: Given the CLAUDE.md Workflows section, when this story is complete, then a new entry exists for "Ingest session" (or equivalent) with: (a) the trigger phrases from E-072-01's Activation Triggers section, (b) the skill file path `.claude/skills/ingest-session/SKILL.md`, (c) a brief description of the workflow (processes a proxy session, identifies unknown endpoints, guides selective capture).
- [ ] **AC-2**: Given the Workflows entry, when the main session encounters a trigger phrase like "ingest session" or "process proxy session", then the entry clearly directs the main session to load the skill file.
- [ ] **AC-3**: Given any other context-layer files that enumerate skills or workflow triggers (check `.claude/rules/dispatch-pattern.md`, agent definitions that reference skill inventories), when this story is complete, then the new skill is included where appropriate.

## Technical Approach
The implementer should read the existing Workflows section in `CLAUDE.md` to see the pattern for skill registration entries. Each entry has: a workflow name, trigger phrases (with examples in parentheses), a skill file path, and a brief description of what the skill does. The new entry follows this exact pattern.

Check whether any other context-layer files need updating:
- `CLAUDE.md` Workflows section (required)
- `.claude/rules/dispatch-pattern.md` -- check if it references skill inventory
- Agent definitions -- check if any agent references a skill list that should include the new skill

Reference files:
- `CLAUDE.md` (the Workflows section, around the existing ingest-endpoint entry)
- `.claude/skills/ingest-session/SKILL.md` (created by E-072-01 -- read the Activation Triggers section for trigger phrases)

## Dependencies
- **Blocked by**: E-072-01 (needs the skill file to read trigger phrases from)
- **Blocks**: None

## Files to Create or Modify
- `CLAUDE.md` (modify -- Workflows section)
- Potentially `.claude/rules/dispatch-pattern.md` or agent definitions (modify -- only if they enumerate skills)

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] CLAUDE.md Workflows entry follows existing format conventions
- [ ] No regressions in existing tests

## Notes
- This is a small story -- primarily a single CLAUDE.md edit plus a sweep of related context-layer files.
