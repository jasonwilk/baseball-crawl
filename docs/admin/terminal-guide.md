# Terminal and Shell User Guide

Practical reference for the ZSH and tmux setup in the baseball-crawl devcontainer. Covers what changed, ZSH differences from bash, tmux key bindings, connecting from iTerm2, and operating modes.

## Table of Contents

1. [What Changed](#what-changed)
2. [ZSH for Bash Users](#zsh-for-bash-users)
3. [tmux Quick Reference](#tmux-quick-reference)
4. [Connecting from iTerm2](#connecting-from-iterm2)
5. [Terminal Modes](#terminal-modes)
6. [Troubleshooting](#troubleshooting)

---

## What Changed

| Component | Before | After |
|-----------|--------|-------|
| Default interactive shell | bash | ZSH |
| Shell framework | none | Oh My Zsh (devcontainers theme) |
| Multiplexer | none | tmux (pre-configured) |
| Automation/hooks/agents | bash | bash (unchanged) |

**ZSH is the interactive shell.** When you open a terminal in VS Code or attach via `docker exec`, you land in ZSH.

**Bash is preserved for automation.** Scripts, pre-commit hooks, and agent tooling continue to run under bash. Claude Code's Bash tool also runs bash -- this is expected behavior, not a regression.

**Oh My Zsh** is pre-installed with the `devcontainers` theme. Configuration lives in `~/.zshrc`.

---

## ZSH for Bash Users

### Syntax Differences

Most bash syntax works unchanged in ZSH. The common gotchas:

| Situation | Bash | ZSH |
|-----------|------|-----|
| Array indexing | `${arr[0]}` (0-based) | `${arr[1]}` (1-based) |
| Glob patterns | `echo *.txt` (fails silently if no match) | `echo *.txt` (errors if no match) |
| Glob in loops | works | wrap in `setopt NULL_GLOB` or quote |
| `[[ ]]` tests | supported | supported (same syntax) |
| Process substitution `<(...)` | supported | supported |
| `source` vs `.` | both work | both work |

For interactive use (running commands, navigating, using the CLI), there are no meaningful differences. The table above matters for scripts -- and scripts in this project run under bash explicitly.

### Installed Plugins

| Plugin | Source | What it does |
|--------|--------|--------------|
| `git` | Ships with Oh My Zsh | Git aliases (`gst`, `gco`, `glog`, etc.) and prompt completions |
| `z` | Ships with Oh My Zsh | Frecency-based directory jumping: `z baseball` jumps to the most-visited path containing "baseball" |
| `zsh-autosuggestions` | Installed separately | Ghost text after your cursor showing the most likely completion from history; press `→` or `End` to accept |
| `zsh-syntax-highlighting` | Installed separately | Colors commands green (valid) or red (not found) as you type, before hitting Enter |

### Falling Back to Bash

When you need bash explicitly:

```bash
bash          # start a bash subshell
exec bash     # replace the current shell process with bash
```

To return to ZSH from a bash subshell: `exit`

---

## tmux Quick Reference

### Sessions

| Action | Key / Command |
|--------|---------------|
| Start new session | `tmux new-session -s baseball` |
| Attach to existing session | `tmux attach -t baseball` |
| Detach from session | `Ctrl+A d` *(default: `Ctrl+B d`)* |
| List sessions | `tmux ls` |
| Kill session | `tmux kill-session -t baseball` |

The standard session name for this project is `baseball`.

### Panes

| Action | Key | Note |
|--------|-----|------|
| Split horizontally (side by side) | `Ctrl+A \|` *(default: `Ctrl+B %`)* | Preserves current directory |
| Split vertically (top/bottom) | `Ctrl+A -` *(default: `Ctrl+B "`)* | Preserves current directory |
| Move to pane (arrow key) | `Ctrl+A ←/→/↑/↓` *(default: `Ctrl+B ←/→/↑/↓`)* | |
| Resize pane | hold `Ctrl+A` then arrow | |
| Close pane | `exit` or `Ctrl+D` | |
| Zoom pane (full screen) | `Ctrl+A z` *(default: `Ctrl+B z`)* | Press again to unzoom |

### Windows

| Action | Key |
|--------|-----|
| New window | `Ctrl+A c` *(default: `Ctrl+B c`)* |
| Next window | `Ctrl+A n` *(default: `Ctrl+B n`)* |
| Previous window | `Ctrl+A p` *(default: `Ctrl+B p`)* |
| Select window by number | `Ctrl+A 1`, `Ctrl+A 2`, etc. |
| Rename window | `Ctrl+A ,` *(default: `Ctrl+B ,`)* |

### Project Configuration Summary

| Setting | Value | Default |
|---------|-------|---------|
| Prefix | `Ctrl+A` | `Ctrl+B` |
| Mouse | enabled | disabled |
| Window/pane indexing | 1-based | 0-based |
| Horizontal split binding | `\|` | `%` |
| Vertical split binding | `-` | `"` |
| Color | 256-color + true color | terminal-dependent |
| Aggressive resize | enabled | disabled |

Every customized binding in this guide shows its default in italics so you can read external tmux resources without confusion.

### Copy Mode

| Action | Key |
|--------|-----|
| Enter copy mode | `Ctrl+A [` *(default: `Ctrl+B [`)* |
| Exit copy mode | `q` |
| Scroll up/down | arrow keys or `PgUp/PgDn` |

---

## Connecting from iTerm2

This is the Mode C (Heavy) workflow: host iTerm2 terminal, tmux running inside the devcontainer.

### Steps

1. **Open iTerm2** on the Mac host.

2. **Find the devcontainer name:**
   ```bash
   docker ps --format '{{.Names}}'
   ```
   Look for a container name containing `baseball-crawl` or `devcontainer`.

3. **Attach to the devcontainer as the vscode user:**
   ```bash
   docker exec -it -u vscode <container-name> zsh
   ```
   The `-u vscode` flag is required. Without it, you land as root and miss the environment variable setup (the `~/.zshrc` and project dotfiles are owned by vscode, not root).

4. **Start or attach to the tmux session:**
   ```bash
   tmux new-session -s baseball    # if no session exists
   # or
   tmux attach -t baseball         # if session already running
   ```

5. **Run Claude Code in tmux mode** (for Agent Teams / Heavy mode):
   ```bash
   claude --dangerously-skip-permissions
   ```
   Claude Code detects it is inside tmux and uses tmux mode for Agent Teams.

### Verifying the Environment

After attaching, confirm the environment is correct:

```bash
echo $SHELL          # should be /bin/zsh
echo $USER           # should be vscode
echo $HOME           # should be /home/vscode
pwd                  # should be /workspaces/baseball-crawl (or navigate there)
```

---

## Terminal Modes

Choose the mode that matches what you are doing.

| Mode | Environment | Agent Teams | When to Use |
|------|-------------|-------------|-------------|
| **Solo** | VS Code integrated terminal | Not applicable | Routine development: running tests, making edits, checking status, running `bb` commands |
| **Coordinated** | VS Code integrated terminal | In-process mode | Standard multi-agent work: dispatching epics, running the PM and implementing agents together |
| **Heavy** | iTerm2 + tmux + devcontainer | tmux mode | Long-running or complex dispatch sessions where persistent windows and pane isolation are valuable |

**Tradeoffs:**

- **Solo**: Simplest setup. VS Code handles the terminal. No tmux overhead. Best for single-stream work.
- **Coordinated**: Current default for AI-assisted work. Still in VS Code, still simple. In-process Agent Teams avoids the tmux requirement.
- **Heavy**: More setup, more power. tmux panes give you persistent windows that survive VS Code disconnects. Useful for multi-hour dispatch sessions or when running Claude Code alongside other terminals simultaneously. Requires the iTerm2 connection workflow above.

---

## Troubleshooting

### Which shell is running?

```bash
echo $0           # shows the current shell name
echo $SHELL       # shows the default login shell
ps -p $$          # shows the process name for the current PID
```

Claude Code's Bash tool reports `bash` -- this is expected. The Bash tool explicitly invokes bash regardless of the interactive shell.

### Falling back to bash

```bash
bash     # subshell; exit to return to ZSH
```

Or prefix any one-off command: `bash -c 'your command here'`

### Missing environment variables in ZSH

If a variable is set in `~/.bashrc` or `~/.bash_profile` but not in `~/.zshrc`, ZSH will not see it. Check:

```bash
cat ~/.zshrc | grep -i your_variable
```

Project environment variables (`.env`) are loaded by Docker Compose and available in the devcontainer's environment regardless of shell. If a `.env` variable is missing, check that the devcontainer was built after the variable was added.

### tmux key binding conflicts

If `Ctrl+A` is intercepted by the application running inside the pane (e.g., a text editor using `Ctrl+A` for "select all"), press `Ctrl+A Ctrl+A` to pass a literal `Ctrl+A` through to the application.

If `Ctrl+A` is not working at all from VS Code's integrated terminal, switch to Mode C (iTerm2 + tmux) where the terminal handles key events directly without VS Code interception.

### Landed as root in the devcontainer

If `docker exec` was run without `-u vscode`, you are root. Exit and reconnect with the correct flag:

```bash
exit
docker exec -it -u vscode <container-name> zsh
```

### tmux session not found

```bash
tmux ls    # list existing sessions
```

If no sessions exist, create one: `tmux new-session -s baseball`

---

*Last updated: 2026-03-07 | Story: E-066-05*
