# E-081-05: Update CLAUDE.md for the Codex bootstrap model

## Epic
[E-081: Codex Context and Agent Bootstrap](epic.md)

## Status
`TODO`

## Description
After this story is complete, `CLAUDE.md` will describe the repo's Codex bootstrap model accurately: the checked-in Codex layer, the gitignored runtime layer, the default project-local `CODEX_HOME` path, and where to find the human-facing operator guide.

## Context
E-081 adds new live workflow surfaces to the repo: `AGENTS.md`, `.codex/config.toml`, `.agents/skills/`, a project-local `CODEX_HOME` pattern, and a new operator guide. `CLAUDE.md` is a live context-layer contract for agents and operators, so it must reflect those additions once they exist. This story keeps `CLAUDE.md` aligned with the implemented Codex baseline rather than leaving the Codex lane implicit.

## Acceptance Criteria
- [ ] **AC-1**: `CLAUDE.md` contains a concise section describing the checked-in Codex layer (`AGENTS.md`, `.codex/config.toml`, `.agents/skills/`) and the gitignored runtime layer (`CODEX_HOME`, local auth/session/history/cache artifacts).
- [ ] **AC-2**: `CLAUDE.md` states that the default Codex workflow uses a project-local `CODEX_HOME` inside the workspace and that host `~/.codex` mapping is optional, not required.
- [ ] **AC-3**: `CLAUDE.md` points readers to `docs/admin/codex-guide.md` for the full operator-facing setup and smoke-check instructions.
- [ ] **AC-4**: `CLAUDE.md` does not describe spawned agents, `multi_agent`, or other experimental Codex features as part of the baseline Codex lane.
- [ ] **AC-5**: The new Codex guidance in `CLAUDE.md` reflects implemented file paths and behavior only; it does not speculate about future Codex hardening work.

## Technical Approach
This is a context-layer alignment story, not a user manual rewrite. Keep the `CLAUDE.md` addition short and directional: enough for future agents and operators to understand the Codex layer and find the full guide, without duplicating the whole `docs/admin/codex-guide.md` document.

## Dependencies
- **Blocked by**: E-081-01, E-081-02, E-081-03, E-081-04
- **Blocks**: None

## Files to Create or Modify
- `CLAUDE.md`

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] `CLAUDE.md` reflects implemented Codex reality only
- [ ] The Codex guidance is concise and points to the operator guide for detail

## Notes
- This story exists because `CLAUDE.md` is a live contract. New repo workflow surfaces should not be left undocumented there.
