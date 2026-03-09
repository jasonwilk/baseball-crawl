# E-081-02: Bootstrap project-local CODEX_HOME in the devcontainer

## Epic
[E-081: Codex Context and Agent Bootstrap](epic.md)

## Status
`TODO`

## Description
After this story is complete, Codex runtime state will live in a gitignored project-local directory inside the workspace rather than defaulting to host-global `~/.codex`. This gives the project a durable local Codex home for trust, auth, sessions, and caches without committing those artifacts to git.

## Context
Official Codex docs and local CLI behavior show two distinct layers: checked-in project config under `.codex/`, and user-level runtime state under `CODEX_HOME` (defaulting to `~/.codex`). The user wants to minimize host dependency and keep as much as possible inside the project. The right split is to keep the checked-in config in `.codex/` and move the mutable runtime layer to a gitignored project directory such as `.codex-home/`.

Project-scoped `.codex/config.toml` only loads for trusted repos, so the local runtime bootstrap must also seed a minimal user-level config with a trust entry for `/workspaces/baseball-crawl`. That trust entry belongs in the local runtime layer, not in checked-in files.

## Acceptance Criteria
- [ ] **AC-1**: The devcontainer configuration sets `CODEX_HOME` to a gitignored project-local directory inside `/workspaces/baseball-crawl`, rather than relying on host-global `~/.codex`.
- [ ] **AC-2**: Devcontainer bootstrap creates the `CODEX_HOME` directory if it does not exist.
- [ ] **AC-3**: Devcontainer bootstrap creates or updates a minimal `${CODEX_HOME}/config.toml` so `/workspaces/baseball-crawl` is trusted and can load the checked-in `.codex/config.toml`.
- [ ] **AC-4**: The bootstrap is idempotent. Re-running post-create setup does not duplicate trust entries or overwrite existing auth/session artifacts.
- [ ] **AC-5**: `.gitignore` excludes the local Codex runtime directory and its contents.
- [ ] **AC-6**: Running `codex --version` and `codex exec --help` inside the devcontainer works with the project-local `CODEX_HOME` path in place.
- [ ] **AC-7**: The existing global `codex` binary install remains unchanged; this story only relocates runtime state, not the executable itself.

## Technical Approach
The bootstrap may live in `.devcontainer/post-create-env.sh`, a new helper script called from there, or another project-owned devcontainer setup path. The implementation should seed only the minimum required user-level state: directory creation plus trust configuration. It must not hard-reset or delete existing local Codex state.

This story should not add a host mount for `~/.codex`. Host mapping remains optional and should be documented as an alternative only if the operator wants cross-project or host/container continuity.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-081-03, E-081-04

## Files to Create or Modify
- `.devcontainer/devcontainer.json`
- `.devcontainer/post-create-env.sh`
- `.gitignore`

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-081-03**: A working project-local Codex runtime environment that can load the checked-in `.codex/config.toml`.
- **Produces for E-081-04**: The actual runtime directory pattern and trust bootstrap behavior the operator guide must document.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Local Codex runtime state is project-local and gitignored
- [ ] Bootstrap is idempotent and does not overwrite user secrets

## Notes
- The runtime directory is local state, not versioned state. Treat its contents as sensitive.
