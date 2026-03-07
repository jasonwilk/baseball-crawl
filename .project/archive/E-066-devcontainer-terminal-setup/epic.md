# E-066: Devcontainer Terminal Setup

## Status
`COMPLETED`
<!-- Lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED) -->

## Overview
Improve the devcontainer terminal experience by switching the interactive shell to ZSH, adding VS Code terminal profiles for clarity, and installing tmux for optional advanced use. This gives the operator a better daily shell, eliminates terminal naming confusion, and prepares the environment for split-pane Agent Teams sessions without forcing complexity upfront.

## Background & Context
The operator raised concerns about confusing terminal names in VS Code when running Agent Teams dispatches. Two independent proposals (Claude Code and Codex) were generated, discussed, and merged into a consensus plan documented in `DISCUSSION-terminal-setup.md`. The consensus adopts a phased approach: shell hygiene first, terminal clarity second, tmux as optional third, documentation of advanced workflows fourth.

SE consultation completed (2026-03-07) with key findings:
- Do NOT add `common-utils` devcontainer feature explicitly -- the `devcontainers/base:ubuntu` base image already includes it. Use `chsh` in postCreateCommand instead.
- Modify `post-create-env.sh` to inject into both `.bashrc` and `.zshrc` (touch `.zshrc` first since it may not exist).
- Terminal profiles belong in `devcontainer.json` under `customizations.vscode.settings`, not in a separate `.vscode/settings.json`.
- tmux prefix should be changed from `Ctrl+B` (conflicts with VS Code) to `Ctrl+A`. Set `default-terminal "tmux-256color"` with terminal overrides and `aggressive-resize on`.

The original source documents (`DISCUSSION-terminal-setup.md`, `PROPOSAL-terminal-setup.md`, `CODEX-terminal-agentic-plan.md`) were consumed during planning and have been deleted. All relevant decisions and constraints are captured in the Technical Notes below.

No expert consultation required beyond SE (completed). This is a single-developer devcontainer improvement with no coaching data, API, schema, or agent architecture implications.

## Goals
- ZSH is the default interactive shell in the devcontainer
- Bash remains fully functional for automation, hooks, and Claude Code's Bash tool
- VS Code terminals have clear names, icons, and colors that eliminate confusion
- tmux is installed and configured for optional use
- The host-terminal workflow for heavy Agent Teams sessions is documented
- The operator has a practical reference guide for ZSH, tmux, and the iTerm2 connection workflow

## Non-Goals
- Making tmux mandatory for any workflow
- Heavy Oh My Zsh customization (theme changes, plugin stacks beyond `git` and `z` -- Oh My Zsh is pre-installed in the base image and we preserve its defaults)
- Evaluating or integrating cmux (deferred -- captured as Phase 5 idea)
- Ghostty as an Agent Teams split-pane strategy
- Changing anything about the production Docker image (this is devcontainer-only)

## Success Criteria
- New interactive terminals in the devcontainer open in ZSH
- All existing bash scripts, hooks (PII scan, epic archive check, statusline), and Claude Code's Bash tool work without regression
- Environment variables from `.env` (e.g., `BRIGHT_DATA_TOKEN`) are available in both bash and zsh sessions
- VS Code terminal dropdown shows named profiles with distinct icons/colors
- tmux is available and configured with a project-appropriate minimal config
- Operator-facing terminal guide exists at `docs/admin/terminal-guide.md`
- `pytest` passes with no new failures

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-066-01 | ZSH default shell and env bootstrap | DONE | None | SE |
| E-066-03 | tmux installation and config | DONE | E-066-01 | SE |
| E-066-02 | VS Code terminal profiles | DONE | E-066-03 | SE |
| E-066-04 | CLAUDE.md terminal and dual-shell documentation | DONE | E-066-02 | claude-architect |
| E-066-05 | Terminal and shell user guide | DONE | E-066-02 | docs-writer |

## Dispatch Team
- software-engineer
- claude-architect
- docs-writer

## Technical Notes

### Shell-agnostic env bootstrap
The current `post-create-env.sh` prepends an export block into `~/.bashrc` using a MARKER pattern. The refactored version must:
1. Touch `~/.zshrc` before checking (it may not exist yet)
2. Use the same MARKER-based idempotency check for both files
3. Prepend the same export block to both `~/.bashrc` and `~/.zshrc`
4. Keep the `.bashrc` injection working for non-interactive bash (Claude Code's Bash tool depends on this)

### ZSH default via chsh
The `devcontainers/base:ubuntu` image already has ZSH installed with Oh My Zsh pre-configured (theme: `devcontainers`, plugins: `git`, auto-update disabled at `~/.oh-my-zsh/`). Do NOT add the `common-utils` feature. Instead, add `sudo chsh -s /usr/bin/zsh vscode` to the beginning of `postCreateCommand` in `devcontainer.json`. This is deterministic, avoids feature conflicts, and preserves the existing Oh My Zsh installation.

### Oh My Zsh (pre-installed) and plugins
Oh My Zsh is already fully installed and active in the base image -- it is not something we add. The `devcontainers` theme is purpose-built for this context (shows git branch).

Four plugins in total:
- `git` -- pre-installed, ships with Oh My Zsh
- `z` -- frecency-based directory jumping, ships with Oh My Zsh (no external deps)
- `zsh-autosuggestions` -- ghost text from command history, cloned into Oh My Zsh custom plugins dir
- `zsh-syntax-highlighting` -- colors valid/invalid commands in real time, cloned into Oh My Zsh custom plugins dir

The two external plugins are installed via shallow git clone in postCreateCommand. Do NOT use the `devcontainers-extra/features/zsh-plugins` community feature (fragile sed, unnecessary third-party dependency). Combined startup latency for all four plugins is ~20-50ms (imperceptible). Do not add further plugins or themes.

### Terminal profiles in devcontainer.json
Terminal profiles go under `customizations.vscode.settings` in `devcontainer.json`, not in a separate `.vscode/settings.json`. This keeps container configuration in one place. All profile fields (`overrideName`, `icon`, `color`, `path`, `args`) work correctly in devcontainers.

### tmux configuration
The `.tmux.conf` should address VS Code integrated terminal compatibility:
- Change prefix from `Ctrl+B` to `Ctrl+A` (avoids VS Code conflict)
- Set `default-terminal "tmux-256color"` with `terminal-overrides` for true color
- Enable mouse support (`set -g mouse on`)
- Enable aggressive resize (`set -g aggressive-resize on`)
- Use 1-based indexing for windows and panes
- Bind `|` for horizontal split and `-` for vertical split (both preserving current working directory)
- Keep a clean, minimal status bar with session name

### tmux session convention
The standard project session name is `baseball`. When starting a tmux session for this project, use `tmux new-session -s baseball`. This gives a predictable attach target (`tmux attach -t baseball`) and avoids the default numeric session names that are meaningless.

### Three operating modes (documentation reference)
The documentation story should reference these three modes from the consensus:
- **Solo**: VS Code terminal, ZSH, no Agent Teams complexity
- **Coordinated**: VS Code terminal, Agent Teams in-process mode (current default)
- **Heavy**: Host terminal (iTerm2) + tmux + devcontainer attach, Agent Teams in tmux mode. When attaching via `docker exec`, use `-u vscode` to land as the correct user (e.g., `docker exec -it -u vscode <container> zsh`). Without it, the operator lands as root and misses the `vscode` user's env setup.

### Dual-shell contract (context-layer documentation)
After E-066, the devcontainer has two shells with distinct roles:
- **ZSH**: Default interactive shell for the operator (via `chsh`). Oh My Zsh with `devcontainers` theme and four plugins.
- **Bash**: Automation shell. All hook scripts (`.claude/hooks/statusline.sh`, `.claude/hooks/pii-check.sh`, `.claude/hooks/epic-archive-check.sh`) use bash shebangs intentionally. Claude Code's Bash tool runs bash. All scripts in `scripts/` use bash shebangs.

The `post-create-env.sh` dual-injection pattern (prepending the same export block into both `.bashrc` and `.zshrc`) is a convention that must be maintained when adding new environment variables. CLAUDE.md must document this contract so agents and future contributors don't accidentally break it.

This documentation is a context-layer change and must be implemented by claude-architect (per dispatch-pattern.md routing precedence for CLAUDE.md).

## Open Questions
None -- all questions resolved via SE consultation and consensus discussion.

## History
- 2026-03-07: Created from consensus plan in DISCUSSION-terminal-setup.md. SE consultation completed (chsh over common-utils, dual rc injection, profiles in devcontainer.json, tmux prefix/TERM guidance).
- 2026-03-07: Follow-up SE consultation on Oh My Zsh. Finding: already pre-installed in base image (theme: devcontainers, plugins: git, auto-update disabled). Added `z` plugin to E-066-01.
- 2026-03-07: SE consultation on zsh-autosuggestions and zsh-syntax-highlighting. Both high-value for bash-to-zsh transition. Install via shallow git clone in postCreateCommand, not community feature. E-066-01 AC-5/AC-6 updated. Four plugins total: git, z, zsh-autosuggestions, zsh-syntax-highlighting.
- 2026-03-07: User directive: claude-architect must be involved. E-066-04 expanded to cover dual-shell contract documentation, re-routed from software-engineer to claude-architect. Dispatch Team updated to include claude-architect. Dual-shell contract added to Technical Notes.
- 2026-03-07: User directive: add docs-writer for operator user guide. E-066-05 added (terminal-guide.md in docs/admin/). Runs parallel with E-066-04 after E-066-02 completes. Dispatch Team updated to include docs-writer.
- 2026-03-07: Codex spec review triage. 4 REFINE (F1: fix iTerm2 connect workflow to use devcontainer exec not docker-compose; F4: define tmux session convention `baseball` in Technical Notes; F5: specify `|` and `-` bindings in E-066-03 AC-7; F6: remove stale source doc references from epic + stories). 2 DISMISS (F2/F3: transitive deps already enforced by chain).
- 2026-03-07: Epic completed. All 5 stories DONE. ZSH is the default interactive shell, bash preserved for automation, tmux installed and configured, VS Code terminal profiles added, CLAUDE.md dual-shell contract documented, operator terminal guide published at docs/admin/terminal-guide.md.
