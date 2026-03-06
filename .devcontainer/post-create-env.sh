#!/usr/bin/env bash
# Inject MCP token exports into .bashrc so Claude Code's .mcp.json can
# expand ${VAR} references. This block runs BEFORE the interactive guard
# so non-interactive shells (Claude Code's Bash tool) also get the vars.
#
# Called from devcontainer.json postCreateCommand.
set -euo pipefail

MARKER="# --- baseball-crawl MCP env export ---"
BASHRC="$HOME/.bashrc"

# Skip if already injected (idempotent).
if grep -qF "$MARKER" "$BASHRC" 2>/dev/null; then
    exit 0
fi

# Prepend the export block before the existing content.
TMPFILE=$(mktemp)
cat > "$TMPFILE" <<'BLOCK'
# --- baseball-crawl MCP env export ---
# Export tokens from .env so Claude Code's .mcp.json ${VAR} expansion works.
# Must run before the interactive-shell guard (non-interactive shells need this).
if [ -f /workspaces/baseball-crawl/.env ]; then
    _tok=$(grep -m1 '^BRIGHT_DATA_TOKEN=' /workspaces/baseball-crawl/.env 2>/dev/null | cut -d= -f2-)
    [ -n "$_tok" ] && export BRIGHT_DATA_TOKEN="$_tok"
    unset _tok
fi
# --- end baseball-crawl MCP env export ---

BLOCK
cat "$BASHRC" >> "$TMPFILE"
mv "$TMPFILE" "$BASHRC"
