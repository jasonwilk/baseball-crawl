# E-082: Codex RTK Project-Level Integration

## Status
`READY`

## Overview
Integrate RTK into the Codex workflow in a project-local way, without relying on host-global installs or Claude-specific hook wiring. The design target is explicit Codex usage of a project-local RTK binary, not transparent command interception.

## Background & Context
E-070 integrated RTK for Claude Code by using RTK's Claude-specific initialization path and the host-mounted `~/.claude/` directory. The user now wants the Codex side to be as project-local as possible and asked whether the same host-level pattern is required.

Research completed on 2026-03-08 using official Codex docs, local Codex CLI inspection, and RTK upstream documentation:
- Codex supports project-owned config, instructions, skills, and spawned agents, but current public Codex docs do not describe a Claude-style PreToolUse hook or shell-command rewrite surface.
- Local Codex CLI inspection (`codex --help`, `codex exec --help`) shows project config, profiles, `CODEX_HOME`, and non-interactive `--ephemeral` support, but no documented RTK-style hook/init mechanism.
- RTK's documented automatic integration path is Claude-specific (`rtk init -g --auto-patch` against `~/.claude/settings.json`).
- RTK's upstream installer is not shaped for repo-local Codex bootstrap. The current quick-start/install path is global, not project-scoped.

The conclusion is clear: **Codex does not need the same host-level setup pattern as Claude, but it also cannot currently use the same transparent RTK hook pattern.** The right Codex design is:
- install RTK into a gitignored project-local tool directory
- expose that binary to Codex shell commands from checked-in project config
- teach Codex explicitly when to prefer `rtk <command>`
- avoid shell shims that shadow `git`, `ls`, `cat`, or other core binaries

If E-081 is implemented first, Codex runtime state can remain project-local via `CODEX_HOME` and host `~/.codex` mapping stays optional. No host mount is required for the Codex RTK lane.

No Claude-agent consultation required. This epic is based on Codex-native docs/behavior plus RTK's published integration shape.

## Goals
- RTK is available inside the devcontainer from a project-local, gitignored install path usable by Codex
- Codex can resolve and intentionally use the project-local RTK binary without host-global PATH setup
- The repo documents when Codex should prefer RTK and when it should fall back to raw commands
- No host-global `~/.codex`, `~/.local/bin`, or Claude hook writes are required for Codex RTK support

## Non-Goals
- Transparent interception of every Codex shell command
- Shadowing core commands with wrapper binaries or aliases
- Installing RTK on the host machine
- Replacing the existing Claude RTK integration from E-070

## Success Criteria
- A project-local RTK binary install path exists and is gitignored
- Devcontainer bootstrap can install or refresh that project-local RTK binary without writing to host-global paths
- Codex shell commands can resolve the project-local RTK binary from checked-in project config
- Repo instructions/skills explicitly describe when Codex should use `rtk <command>` and when it should use the raw command instead
- A smoke-check path verifies the project-local RTK binary and at least one supported RTK command from within the repo
- Documentation states clearly that no host `~/.codex` mount or Claude-style `rtk init -g` step is required for the Codex lane

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-082-01 | Install RTK into a project-local devcontainer path | TODO | E-081-02 | - |
| E-082-02 | Expose project-local RTK to Codex and add explicit usage guidance | TODO | E-081-01, E-081-03, E-082-01 | - |
| E-082-03 | Add a Codex RTK smoke-check path | TODO | E-082-01 | - |
| E-082-04 | Document the Codex RTK operating model | TODO | E-082-01, E-082-02, E-082-03 | - |

## Dispatch Team
- software-engineer
- claude-architect

## Technical Notes

### Integration Model
The Codex RTK model is intentionally explicit, not transparent:
- Codex sees `rtk` on PATH from project-owned config
- Codex instructions/skill teach it to prefer `rtk` for supported high-token shell reads/status/diff commands
- when RTK lacks support or a raw command is clearer, Codex uses the raw command directly

No command-rewrite hook is assumed because none is documented for Codex.

### Install Location
The RTK binary should live in a gitignored project-local tool directory, not in:
- `/usr/local/bin`
- `~/.local/bin`
- host-mounted paths

The exact path is an implementation decision, but it must be:
- inside `/workspaces/baseball-crawl`
- stable across container rebuilds
- excluded from git

### Why Not Use `rtk init -g`
`rtk init -g --auto-patch` is designed to patch Claude's global settings/hook system. This epic is specifically for Codex, which has a different extension surface. The Codex lane should not write to `~/.claude/settings.json`, `~/.codex`, or host-global hook locations as part of RTK enablement.

### Why Not Use Shell Shims
Shadowing `git`, `ls`, `cat`, or similar binaries in PATH would create surprising behavior for both humans and agents. That is too invasive for a light Codex companion lane. Explicit `rtk <command>` usage is the safer pattern.

### Relationship to E-081
E-081 establishes the project-local Codex layer (`AGENTS.md`, `.codex/config.toml`, repo skill, project-local `CODEX_HOME`). E-082 builds on that layer by adding a project-local RTK binary and Codex-specific RTK guidance. This ordering is intentional.

### Suggested Wave Structure
- Wave 1: E-082-01
- Wave 2: E-082-02 + E-082-03 in parallel
- Wave 3: E-082-04

## Open Questions
None. The research outcome is clear: project-local Codex RTK integration is feasible, but transparent Claude-style hooking is not the target.

## History
- 2026-03-08: Created from Codex + RTK research. Key conclusion: Codex does not require the same host-level integration pattern as Claude, but current public Codex surfaces also do not expose a Claude-style automatic rewrite hook. Epic scoped to project-local RTK install plus explicit Codex usage guidance. Set to READY.
