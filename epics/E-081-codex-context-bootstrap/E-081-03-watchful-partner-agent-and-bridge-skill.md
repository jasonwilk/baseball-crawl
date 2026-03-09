# E-081-03: Add a lightweight watchful-partner bridge skill

## Epic
[E-081: Codex Context and Agent Bootstrap](epic.md)

## Status
`TODO`

## Description
After this story is complete, Codex will have one lightweight repo-scoped skill that helps it act as Claude's watchful partner. The result is a small, explicit Codex support layer for review and verification without cloning the full Claude ecosystem or depending on experimental Codex features.

## Context
Official Codex docs support repo-scoped skills under `.agents/skills/`. Local CLI inspection shows `multi_agent` is experimental and disabled by default in the current Codex install. The user asked for a very light Codex support system, not a second primary orchestration framework. That means the initial Codex system should stay intentionally narrow:

- one bridge skill, not a library
- review/verification posture, not PM ownership
- selective use of the existing Claude context, not duplication of it

## Acceptance Criteria
- [ ] **AC-1**: A repo-scoped Codex skill exists under `.agents/skills/` and teaches Codex how to bridge into the existing Claude/project context using progressive disclosure.
- [ ] **AC-2**: The skill explicitly frames Codex's role as a watchful partner focused on review, verification, risk detection, and context integrity.
- [ ] **AC-3**: The skill instructs Codex to load only the minimum relevant Claude artifacts for the current task rather than bulk-reading `.claude/`.
- [ ] **AC-4**: The checked-in Codex layer does not require a spawned agent, the `multi_agent` feature flag, or any other experimental Codex feature to use the bridge skill.
- [ ] **AC-5**: Neither the skill nor the surrounding Codex guidance duplicates the Claude PM workflow or recreates the full Claude agent roster inside Codex.
- [ ] **AC-6**: The checked-in skill is purely project-local. It does not depend on host-global Codex skill directories or user-home agent files.

## Technical Approach
The bridge skill should be useful on day one for the specific role the user described: Codex as a watchful partner to Claude. Keep the skill concrete, but avoid building a mini-ecosystem. The safe baseline is a repo skill plus checked-in guidance, not a spawned-agent system.

This story may extend `AGENTS.md` from E-081-01 so the repo-owned Codex layer points at the bridge skill, but it should not introduce any new runtime-state requirements beyond the `CODEX_HOME` bootstrap from E-081-02.

## Dependencies
- **Blocked by**: E-081-01
- **Blocks**: E-081-04, E-081-05

## Files to Create or Modify
- `AGENTS.md`
- `.agents/skills/claude-context-bridge/SKILL.md`

## Agent Hint
claude-architect

## Handoff Context
- **Produces for E-081-04**: The actual skill name, role, and usage pattern that the operator guide must document.
- **Produces for E-081-05**: The bridge-skill role and path that `CLAUDE.md` must describe.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] The bridge skill stays intentionally narrow
- [ ] No second PM system, duplicated Claude roster, or experimental Codex dependency is introduced

## Notes
- "Very light" is the core constraint for this story. If the implementation starts expanding into multiple skills or reintroduces spawned agents, it has missed the point.
