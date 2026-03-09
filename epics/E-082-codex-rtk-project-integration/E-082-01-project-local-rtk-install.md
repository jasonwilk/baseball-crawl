# E-082-01: Install RTK into a project-local devcontainer path

## Epic
[E-082: Codex RTK Project-Level Integration](epic.md)

## Status
`TODO`

## Description
After this story is complete, RTK will be installed into a gitignored project-local directory inside the workspace so Codex can use it without relying on host-global install paths. The install lives with the project and survives devcontainer rebuilds because it is stored in the workspace, not the container home.

## Context
RTK's quick-start path is global, not repo-local. The user wants Codex integration to be as project-local as possible, so the Codex lane should install the binary into a project-owned tool cache under `/workspaces/baseball-crawl` and leave host-global locations untouched.

This story depends on E-081-02 because the project-local Codex runtime/home strategy should exist before RTK is added to the Codex lane.

## Acceptance Criteria
- [ ] **AC-1**: Devcontainer bootstrap installs RTK into a gitignored project-local directory inside `/workspaces/baseball-crawl`.
- [ ] **AC-2**: The bootstrap does not install RTK into `/usr/local/bin`, `~/.local/bin`, host-mounted paths, or any other host-global location.
- [ ] **AC-3**: The bootstrap does not invoke `rtk init -g`, `rtk init --auto-patch`, or any other global hook-patching flow.
- [ ] **AC-4**: The install path survives devcontainer rebuilds because it lives in the workspace.
- [ ] **AC-5**: The bootstrap is idempotent and non-blocking: if RTK install fails, the rest of the devcontainer setup still completes.
- [ ] **AC-6**: The project records the RTK version or release source explicitly so future updates are deliberate rather than implicit.

## Technical Approach
Because the upstream RTK install path is global-oriented, the implementation will likely need to fetch a pinned release artifact directly rather than using the global quick-start installer unchanged. The binary should be placed in a repo-local tool cache directory and marked executable during devcontainer setup.

The exact directory is an implementation choice, but it must be project-local and gitignored. Avoid mixing the binary with checked-in text config unless the directory structure remains clean and obvious.

## Dependencies
- **Blocked by**: E-081-02
- **Blocks**: E-082-02, E-082-03, E-082-04

## Files to Create or Modify
- `.devcontainer/devcontainer.json`
- `.devcontainer/post-create-env.sh`
- `.gitignore`

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-082-02**: The actual repo-local RTK binary path that Codex config and guidance must expose.
- **Produces for E-082-03**: The binary that the smoke-check path will verify.
- **Produces for E-082-04**: The implemented install location and bootstrap behavior that documentation must describe.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Project-local RTK install is gitignored and durable across rebuilds
- [ ] RTK install failure cannot break the broader devcontainer setup

## Notes
- This story is intentionally about binary placement, not Codex behavior. Codex guidance comes later.
