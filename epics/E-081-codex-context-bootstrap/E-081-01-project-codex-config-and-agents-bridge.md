# E-081-01: Add project Codex config and repo AGENTS bridge

## Epic
[E-081: Codex Context and Agent Bootstrap](epic.md)

## Status
`TODO`

## Description
After this story is complete, the repo will contain the minimum checked-in Codex entry points: a real root `AGENTS.md` file and a project `.codex/config.toml`. Together they define how Codex should work in this repository, with Codex framed as a secondary/watchful partner to Claude rather than a second primary orchestration system.

## Context
The repo currently has Codex review scripts and prompt-generation workflows, but it does not have an actual Codex project context layer. The current session receives AGENTS instructions externally, which is not the same as having a checked-in repo `AGENTS.md` that future Codex sessions can discover automatically. Official Codex docs support both `AGENTS.md` and project-scoped `.codex/config.toml`, so those should become the project's durable, versioned Codex entry points.

## Acceptance Criteria
- [ ] **AC-1**: A root-level `AGENTS.md` file exists and explicitly defines Codex's role in this repo as a secondary/watchful partner to Claude, prioritizing verification, review, bounded implementation, and context integrity over product ownership.
- [ ] **AC-2**: The `AGENTS.md` guidance tells Codex to consult `CLAUDE.md`, the active epic/story files, and only the task-relevant `.claude/` files instead of bulk-loading the entire Claude context tree.
- [ ] **AC-3**: A checked-in `.codex/config.toml` file exists and contains only project-owned defaults. It must not contain credentials, tokens, auth artifacts, session IDs, or paths outside the workspace.
- [ ] **AC-4**: The checked-in Codex files do not require a host `~/.codex` mount or host-global config to function; they are valid repo-local inputs on their own.
- [ ] **AC-5**: The checked-in config parses as valid TOML and does not cause `codex --help` or `codex exec --help` to fail when run from the repo.

## Technical Approach
This story creates the durable, versioned Codex layer only. It should not create or seed local runtime state such as trust entries, auth files, session history, or caches. Those belong to the gitignored project-local runtime directory handled by E-081-02.

The `AGENTS.md` file should be intentionally small and directional. It should explain how Codex uses the existing repo context, not restate every Claude rule file. The `.codex/config.toml` file should establish project-safe defaults and leave user-local trust/auth concerns to the runtime layer.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-081-03, E-081-04

## Files to Create or Modify
- `AGENTS.md`
- `.codex/config.toml`

## Agent Hint
claude-architect

## Handoff Context
- **Produces for E-081-03**: The checked-in config file that will register the lightweight spawned agent and any repo skill defaults.
- **Produces for E-081-04**: The canonical checked-in Codex entry points that the operator guide must describe.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] `AGENTS.md` is clear and scoped to Codex
- [ ] `.codex/config.toml` is valid TOML with no secrets or host-specific paths

## Notes
- Keep this story lean. The goal is a real Codex project entry point, not a second full context framework.
