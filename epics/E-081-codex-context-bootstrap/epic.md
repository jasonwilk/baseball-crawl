# E-081: Codex Context and Agent Bootstrap

## Status
`READY`

## Overview
Bootstrap a very light, project-owned Codex layer that can operate inside the devcontainer without depending on host-global Codex state. Codex remains secondary to Claude: a watchful partner for verification, review, and bounded implementation, not a parallel product-management system.

## Background & Context
Codex is already installed globally in the devcontainer (`npm i -g @openai/codex` in `.devcontainer/devcontainer.json`), and this repo already has two Codex review workflows from E-034 and E-074. What is missing is a real project-local Codex context layer:

- There is no checked-in repo `AGENTS.md` file for Codex to read.
- There is no checked-in `.codex/config.toml` with project defaults.
- There are no project-local Codex skills or spawned agent definitions.
- Codex runtime state currently defaults to `~/.codex/`, which is outside the project's versioned context layer.

Research completed on 2026-03-08 using official Codex documentation plus local CLI inspection in this devcontainer:
- Codex supports project-scoped configuration in `.codex/config.toml`.
- Codex searches upward from the working directory for `AGENTS.md` and merges instructions from nested to root files.
- Codex supports repo-scoped skills under `.agents/skills/`.
- Codex supports lightweight spawned agents via config entries pointing at checked-in prompt files.
- Codex runtime state (config, auth, sessions, history, sqlite state) defaults under `~/.codex/`, but the CLI honors `CODEX_HOME`, making a project-local runtime directory feasible.
- `codex exec --ephemeral` exists for non-interactive runs when we want to avoid session persistence.

The user's stated preference is to keep as much Codex state as possible in the project itself, while keeping Claude as the primary system. This epic implements that split directly: checked-in Codex context stays in the repo, local runtime state moves to a gitignored project directory, and Codex is explicitly framed as Claude's watchful partner.

No Claude-agent consultation required. This epic is Codex-native configuration work based on official Codex docs and direct CLI inspection, not Claude workflow design.

## Goals
- Codex loads a project-owned context layer from checked-in repo files
- Devcontainer sessions can use a gitignored project-local `CODEX_HOME` instead of host-global `~/.codex`
- Codex has a very light review/verification agent pattern that reinforces, rather than duplicates, the existing Claude system
- Codex can consume the project's existing Claude context selectively, without copying the entire `.claude/` ecosystem into Codex-owned files

## Non-Goals
- Recreating the full Claude agent roster or PM workflow inside Codex
- Moving Claude-owned files into Codex-owned paths
- Committing Codex auth, session, or cache artifacts to git
- RTK integration for Codex (handled separately in E-082)

## Success Criteria
- A checked-in `.codex/config.toml` exists with project-safe defaults only
- A checked-in repo `AGENTS.md` exists and defines Codex as a secondary/watchful partner
- A gitignored project-local runtime directory strategy exists for `CODEX_HOME`
- At least one repo-scoped Codex skill exists under `.agents/skills/`
- At least one lightweight spawned Codex agent is registered from checked-in project files
- A human-readable operator guide documents the checked-in vs gitignored Codex split, trust/bootstrap expectations, and smoke checks

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-081-01 | Add project Codex config and repo AGENTS bridge | TODO | None | - |
| E-081-02 | Bootstrap project-local CODEX_HOME in the devcontainer | TODO | None | - |
| E-081-03 | Add a lightweight watchful-partner agent and bridge skill | TODO | E-081-01, E-081-02 | - |
| E-081-04 | Document the Codex operator model and smoke checks | TODO | E-081-01, E-081-02, E-081-03 | - |

## Dispatch Team
- claude-architect
- software-engineer

## Technical Notes

### Layer Split
The Codex bootstrap should use three layers:
1. **Checked-in project layer**: `AGENTS.md`, `.codex/config.toml`, `.codex/agents/**`, `.agents/skills/**`
2. **Gitignored project-local runtime layer**: `.codex-home/**` (or equivalent), containing auth, session, history, caches, and the user-level trust entry
3. **Global binary layer**: the already-installed `codex` executable from the devcontainer setup

This keeps the durable project context under version control while keeping secrets and high-churn runtime artifacts out of git.

### Trust Model
Codex only loads project-scoped `.codex/config.toml` for trusted repos. The project-local `CODEX_HOME` bootstrap therefore needs to seed a minimal user-level config inside the gitignored runtime directory with a trust entry for `/workspaces/baseball-crawl`. This trust entry belongs in the local runtime layer, not in checked-in files.

### Relationship to Claude Context
Codex should not get its own copy of the full Claude ecosystem. The bridge pattern is:
- `AGENTS.md` tells Codex which existing files matter (`CLAUDE.md`, active epic/story files, selected `.claude` rules when relevant)
- the repo skill teaches progressive disclosure rather than bulk-reading `.claude/`
- the spawned Codex agent is narrowly scoped to review/verification/risk detection

### Spawned Agent Scope
The initial Codex agent system should stay intentionally tiny:
- one spawned agent, not a roster
- review/verification posture, not roadmap ownership
- no Codex PM clone

### Local State Hygiene
The runtime directory must be gitignored and documented as sensitive. It will likely contain:
- `config.toml` (user-level trust and local overrides)
- `auth.json`
- `history.jsonl`
- `sessions/`
- sqlite state and caches

These are project-local by placement, but not project-owned by version control.

### Suggested Wave Structure
- Wave 1: E-081-01 + E-081-02 in parallel
- Wave 2: E-081-03
- Wave 3: E-081-04

## Open Questions
None. The project-local bootstrap shape is clear from the documented Codex surfaces and the user's storage preference.

## History
- 2026-03-08: Created from direct Codex research. Research findings incorporated: project-scoped `.codex/config.toml`, repo `AGENTS.md`, repo skills under `.agents/skills/`, project-registered spawned agents, `CODEX_HOME` override support, and `--ephemeral` non-interactive mode. Set to READY.
