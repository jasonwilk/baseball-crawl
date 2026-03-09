#!/usr/bin/env bash
# Inject MCP token exports into .bashrc and .zshrc so Claude Code's .mcp.json
# can expand ${VAR} references. The .bashrc block runs BEFORE the interactive
# guard so non-interactive shells (Claude Code's Bash tool) also get the vars.
#
# Called from devcontainer.json postCreateCommand.
set -euo pipefail

MARKER="# --- baseball-crawl MCP env export ---"
BASHRC="$HOME/.bashrc"
ZSHRC="$HOME/.zshrc"

# Ensure .zshrc exists before checking (it may not exist yet).
touch "$ZSHRC"

# The export block content (same for both shells).
read -r -d '' EXPORT_BLOCK <<'BLOCK' || true
# --- baseball-crawl MCP env export ---
# Export tokens from .env so Claude Code's .mcp.json ${VAR} expansion works.
# Must run before the interactive-shell guard (non-interactive shells need this).
export LANG=en_US.UTF-8
if [ -f /workspaces/baseball-crawl/.env ]; then
    _tok=$(grep -m1 '^BRIGHT_DATA_TOKEN=' /workspaces/baseball-crawl/.env 2>/dev/null | cut -d= -f2-)
    [ -n "$_tok" ] && export BRIGHT_DATA_TOKEN="$_tok"
    unset _tok
fi
# --- end baseball-crawl MCP env export ---

BLOCK

# Inject into .bashrc if not already present (prepend before existing content).
if ! grep -qF "$MARKER" "$BASHRC" 2>/dev/null; then
    TMPFILE=$(mktemp)
    printf '%s' "$EXPORT_BLOCK" > "$TMPFILE"
    cat "$BASHRC" >> "$TMPFILE"
    mv "$TMPFILE" "$BASHRC"
fi

# Inject into .zshrc if not already present (prepend before existing content).
if ! grep -qF "$MARKER" "$ZSHRC" 2>/dev/null; then
    TMPFILE=$(mktemp)
    printf '%s' "$EXPORT_BLOCK" > "$TMPFILE"
    cat "$ZSHRC" >> "$TMPFILE"
    mv "$TMPFILE" "$ZSHRC"
fi
