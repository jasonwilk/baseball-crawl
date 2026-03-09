# E-081-03: Add a lightweight watchful-partner agent and bridge skill

## Epic
[E-081: Codex Context and Agent Bootstrap](epic.md)

## Status
`TODO`

## Description
After this story is complete, Codex will have one lightweight spawned agent plus one repo-scoped skill that help it act as Claude's watchful partner. The result is a small, explicit Codex support layer for review and verification without cloning the full Claude ecosystem.

## Context
Official Codex docs support repo-scoped skills and spawned agents configured from checked-in files. The user asked for a very light Codex agent system, not a second primary orchestration framework. That means the initial Codex system should stay intentionally narrow:

- one spawned agent, not a roster
- one bridge skill, not a library
- review/verification posture, not PM ownership
- selective use of the existing Claude context, not duplication of it

## Acceptance Criteria
- [ ] **AC-1**: `.codex/config.toml` registers at least one spawned agent via a checked-in prompt file, with a description and nickname candidates suitable for Codex routing.
- [ ] **AC-2**: The spawned agent's prompt explicitly frames the role as a watchful partner focused on review, verification, risk detection, and context integrity.
- [ ] **AC-3**: A repo-scoped Codex skill exists under `.agents/skills/` and teaches Codex how to bridge into the existing Claude/project context using progressive disclosure.
- [ ] **AC-4**: The skill instructs Codex to load only the minimum relevant Claude artifacts for the current task rather than bulk-reading `.claude/`.
- [ ] **AC-5**: Neither the skill nor the spawned agent duplicates the Claude PM workflow or recreates the full Claude agent roster inside Codex.
- [ ] **AC-6**: The checked-in skill/agent files are purely project-local. They do not depend on host-global Codex skill directories or user-home agent files.

## Technical Approach
The spawned agent and skill should be useful on day one for the specific role the user described: Codex as a watchful partner to Claude. Keep the names and prompts concrete, but avoid building a mini-ecosystem. This story may extend the checked-in `.codex/config.toml` created by E-081-01, but it should not introduce any new runtime-state requirements beyond the `CODEX_HOME` bootstrap from E-081-02.

## Dependencies
- **Blocked by**: E-081-01, E-081-02
- **Blocks**: E-081-04

## Files to Create or Modify
- `.codex/config.toml`
- `.codex/agents/watchful-partner.md`
- `.agents/skills/claude-context-bridge/SKILL.md`

## Agent Hint
claude-architect

## Handoff Context
- **Produces for E-081-04**: The actual skill/agent names, roles, and usage patterns that the operator guide must document.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] The spawned agent and skill stay intentionally narrow
- [ ] No second PM system or duplicated Claude roster is created

## Notes
- "Very light" is the core constraint for this story. If the implementation starts expanding into multiple agents or many skills, it has missed the point.
