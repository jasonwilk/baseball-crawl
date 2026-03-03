# Claude Code Hooks

## Statusline (`statusline.sh`)

A custom status bar displayed at the bottom of the Claude Code terminal. It shows
at-a-glance session information so you always know what model you are using, how
much context remains, what you have spent, and how long you have been working.

### What It Displays

**Line 1:** Model name, current directory, and git branch (if in a repo).

**Line 2:** A 10-segment context window progress bar, context percentage, session
cost in USD, and elapsed time in minutes and seconds.

The progress bar is color-coded:
- **Green** -- context usage below 70%
- **Yellow** -- context usage between 70% and 89%
- **Red** -- context usage at 90% or above (consider running `/clear`)

### How It Works

Claude Code pipes a JSON blob to the script's stdin after each assistant message.
The script parses the JSON with `jq`, extracts the relevant fields, and prints two
lines to stdout. Claude Code renders whatever the script prints as the status bar.

The JSON schema includes fields like `model.display_name`, `workspace.current_dir`,
`cost.total_cost_usd`, `context_window.used_percentage`, and `cost.total_duration_ms`.
See the official docs for the full schema:
https://code.claude.com/docs/en/statusline

### Configuration

The statusline is configured in `.claude/settings.json`:

```json
{
  "statusLine": {
    "type": "command",
    "command": ".claude/hooks/statusline.sh",
    "padding": 1
  }
}
```

The `command` path is relative to the project root. This ensures it works in both
local development and devcontainer environments without any path adjustment.

### Dependencies

| Dependency | Purpose                         | Install                          |
|------------|---------------------------------|----------------------------------|
| `bash`     | Script interpreter              | Included in all Linux/macOS      |
| `jq`       | JSON parsing                    | `apt install jq` or `brew install jq` |
| `git`      | Branch detection (optional)     | `apt install git` or `brew install git` |

If `jq` is not installed, the script will fail silently and the status bar will be
blank. If `git` is not installed or the directory is not a repo, the branch segment
is simply omitted.

### Devcontainer Notes

When running in a devcontainer:
- The script path is relative, so it resolves correctly regardless of where the
  project is mounted (e.g., `/workspaces/baseball-crawl/`)
- Ensure `jq` is included in the devcontainer image or installed via a feature/postCreateCommand
- The `git` binary is typically available in devcontainers by default

### Customization

**Change the progress bar width:** Edit the `FILLED` and `EMPTY` calculations.
Currently `PCT / 10` yields a 10-segment bar. Use `PCT / 5` for 20 segments.

**Change color thresholds:** Edit the `if/elif/else` block that sets `BAR_COLOR`.

**Add more fields:** The JSON input includes many other fields -- `session_id`,
`context_window.total_input_tokens`, `cost.total_api_duration_ms`,
`cost.total_lines_added`, `cost.total_lines_removed`, `agent.name`, etc.
Extract them with `jq` and add them to the `echo` lines.

**Remove git branch:** Delete the `BRANCH=""` block and `$BRANCH` from the first
`echo` line.

**Switch to Python:** You can rewrite the script in Python (use `#!/usr/bin/env python3`)
and read stdin with `json.load(sys.stdin)`. Update the `command` in settings.json
to point to the new script.

### Testing

Test the script locally with mock data:

```bash
echo '{"model":{"display_name":"Opus"},"workspace":{"current_dir":"/workspace/baseball-crawl"},"cost":{"total_cost_usd":1.23,"total_duration_ms":185000},"context_window":{"used_percentage":42}}' | .claude/hooks/statusline.sh
```

### Disabling

To disable the statusline, remove the `statusLine` key from `.claude/settings.json`
or run `/statusline clear` in Claude Code.

---

## PII Check (`pii-check.sh`)

A Claude Code PreToolUse hook that intercepts `git commit` commands and scans
staged files for PII and credential patterns before allowing the commit.

### When It Fires

Before any `Bash` tool call in Claude Code. The script checks whether the
command is a `git commit`. If not, it exits immediately with no overhead. If it
is a git commit, the script runs `src/safety/pii_scanner.py --staged` against
the staged files.

### What It Does

- **No PII detected**: Exits silently, commit proceeds (the Git pre-commit hook
  will also run as a second layer).
- **PII detected**: Outputs a JSON denial response that blocks the tool call and
  tells Claude why the commit was blocked. The agent receives the scanner output
  as feedback.
- **Scanner not installed**: Exits silently (fail open until E-019-03 delivers
  the scanner).
- **`jq` not available**: Exits silently (fail open -- `jq` is required to parse
  the input JSON).

### Configuration

Configured in `.claude/settings.json` under `hooks.PreToolUse`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/pii-check.sh",
            "timeout": 10,
            "statusMessage": "Checking staged files for PII..."
          }
        ]
      }
    ]
  }
}
```

### Dependencies

| Dependency | Purpose                         | Install                          |
|------------|---------------------------------|----------------------------------|
| `bash`     | Script interpreter              | Included in all Linux/macOS      |
| `jq`       | JSON parsing (input from Claude Code) | `apt install jq` or `brew install jq` |
| `python3`  | Runs the PII scanner            | Required by the project          |

### Bypass

This hook cannot be bypassed by an agent. Only a human can disable it by
removing the hook from `.claude/settings.json` or setting `"disableAllHooks": true`.

---

## Epic Archive Check (`epic-archive-check.sh`)

A Claude Code PreToolUse hook that intercepts `git commit` commands and blocks
them if any completed or abandoned epics remain in the `/epics/` directory.
Epics with status `COMPLETED` or `ABANDONED` must be archived to
`/.project/archive/` before committing.

### When It Fires

Before any `Bash` tool call in Claude Code. The script checks whether the
command is a `git commit`. If not, it exits immediately with no overhead. If it
is a git commit, the script scans all `epics/*/epic.md` files for backtick-wrapped
`COMPLETED` or `ABANDONED` status markers.

### What It Does

- **No stale epics found**: Exits silently, commit proceeds.
- **Stale epics found**: Outputs a JSON denial response that blocks the tool call
  and lists the epic directories that need to be archived.
- **No `/epics/` directory**: Exits silently (nothing to check).
- **`jq` not available**: Exits silently (fail open -- `jq` is required to parse
  the input JSON).

### Configuration

Configured in `.claude/settings.json` under `hooks.PreToolUse`, as a second
entry in the `Bash` matcher's hooks array:

```json
{
  "type": "command",
  "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/epic-archive-check.sh",
  "timeout": 10,
  "statusMessage": "Checking for unarchived completed epics..."
}
```

### Dependencies

| Dependency | Purpose                              | Install                          |
|------------|--------------------------------------|----------------------------------|
| `bash`     | Script interpreter                   | Included in all Linux/macOS      |
| `jq`       | JSON parsing (input from Claude Code) | `apt install jq` or `brew install jq` |
| `grep`     | Scanning epic.md files for status    | Included in all Linux/macOS      |

### Bypass

This hook cannot be bypassed by an agent. Only a human can disable it by
removing the hook from `.claude/settings.json` or setting `"disableAllHooks": true`.
