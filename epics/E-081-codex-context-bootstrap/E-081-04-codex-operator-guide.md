# E-081-04: Document the Codex operator model and smoke checks

## Epic
[E-081: Codex Context and Agent Bootstrap](epic.md)

## Status
`TODO`

## Description
After this story is complete, a human operator will have a clear guide for how Codex is set up in this repo: what is checked in, what is local-only, where runtime state lives, how trust/bootstrap works, and how to smoke-test the setup inside the devcontainer.

## Context
E-081 establishes a split between checked-in Codex context and gitignored project-local runtime state. That split will be easy to forget unless it is written down clearly. The user also explicitly cares about minimizing host storage, so the documentation needs to explain the default project-local path and position host mapping as optional, not required.

## Acceptance Criteria
- [ ] **AC-1**: A project document explains the checked-in Codex layer (`AGENTS.md`, `.codex/config.toml`, spawned agent files, repo skills) versus the gitignored runtime layer (`CODEX_HOME`, auth, sessions, history, caches).
- [ ] **AC-2**: The document explains the trust/bootstrap requirement for project-scoped Codex config and how the devcontainer satisfies it.
- [ ] **AC-3**: The document explains that host `~/.codex` mapping is optional and is not required for the default project-local workflow.
- [ ] **AC-4**: The document includes smoke checks for the devcontainer setup, including at minimum `codex --version`, `echo $CODEX_HOME`, and one command that confirms the project-local runtime path is being used without config errors.
- [ ] **AC-5**: The document explicitly warns that `auth.json`, session history, and other runtime artifacts in the local Codex home are sensitive and must stay gitignored.
- [ ] **AC-6**: The document names the lightweight spawned agent and repo skill added by E-081-03 and explains when to use them.

## Technical Approach
This should be a small operator-facing guide, not a platform manual. It can live under `docs/admin/` or another clearly human-facing documentation path. The guide should describe implemented reality only.

## Dependencies
- **Blocked by**: E-081-01, E-081-02, E-081-03
- **Blocks**: None

## Files to Create or Modify
- `docs/admin/codex-guide.md`

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] The guide reflects implemented reality only
- [ ] Sensitive local-state boundaries are explicit

## Notes
- This guide is for humans operating the repo, not for Codex itself. Keep it concise and concrete.
