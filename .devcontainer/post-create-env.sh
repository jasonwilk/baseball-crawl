#!/usr/bin/env bash
# Inject project env exports into .bashrc and .zshrc so Claude Code's .mcp.json
# can expand ${VAR} references and Codex can see the project-local CODEX_HOME.
# The .bashrc block runs BEFORE the interactive guard so non-interactive shells
# (Claude Code's Bash tool) also get the vars.
#
# Called from devcontainer.json postCreateCommand.
set -euo pipefail

PROJECT_ROOT="/workspaces/baseball-crawl"
CODEX_HOME_DIR="${PROJECT_ROOT}/.codex-home"
ENV_START_MARKER="# --- baseball-crawl MCP env export ---"
ENV_END_MARKER="# --- end baseball-crawl MCP env export ---"
TRUST_START_MARKER="# --- baseball-crawl Codex trust ---"
TRUST_END_MARKER="# --- end baseball-crawl Codex trust ---"
BASHRC="$HOME/.bashrc"
ZSHRC="$HOME/.zshrc"
CODEX_CONFIG_PATH="${CODEX_HOME_DIR}/config.toml"

strip_managed_block() {
    local target="$1"
    local start_marker="$2"
    local end_marker="$3"
    local tmpfile

    tmpfile=$(mktemp)
    awk -v start="$start_marker" -v end="$end_marker" '
        BEGIN { skip = 0 }
        $0 == start { skip = 1; next }
        $0 == end { skip = 0; next }
        !skip { print }
    ' "$target" > "$tmpfile"
    mv "$tmpfile" "$target"
}

prepend_managed_block() {
    local target="$1"
    local start_marker="$2"
    local end_marker="$3"
    local block="$4"
    local tmpfile

    touch "$target"
    strip_managed_block "$target" "$start_marker" "$end_marker"

    tmpfile=$(mktemp)
    printf '%s' "$block" > "$tmpfile"
    cat "$target" >> "$tmpfile"
    mv "$tmpfile" "$target"
}

append_managed_block() {
    local target="$1"
    local start_marker="$2"
    local end_marker="$3"
    local block="$4"
    local tmpfile

    touch "$target"
    strip_managed_block "$target" "$start_marker" "$end_marker"

    tmpfile=$(mktemp)
    cat "$target" > "$tmpfile"
    if [ -s "$tmpfile" ]; then
        printf '\n' >> "$tmpfile"
    fi
    printf '%s' "$block" >> "$tmpfile"
    mv "$tmpfile" "$target"
}

# Ensure shell rc files exist before checking.
touch "$BASHRC"
touch "$ZSHRC"

# The export block content (same for both shells).
read -r -d '' EXPORT_BLOCK <<'BLOCK' || true
# --- baseball-crawl MCP env export ---
# Export tokens from .env so Claude Code's .mcp.json ${VAR} expansion works.
# Must run before the interactive-shell guard (non-interactive shells need this).
export LANG=en_US.UTF-8
export CODEX_HOME=/workspaces/baseball-crawl/.codex-home
if [ -f /workspaces/baseball-crawl/.env ]; then
    _tok=$(grep -m1 '^BRIGHT_DATA_TOKEN=' /workspaces/baseball-crawl/.env 2>/dev/null | cut -d= -f2-)
    [ -n "$_tok" ] && export BRIGHT_DATA_TOKEN="$_tok"
    unset _tok
fi
# --- end baseball-crawl MCP env export ---

BLOCK

read -r -d '' TRUST_BLOCK <<'BLOCK' || true
# --- baseball-crawl Codex trust ---
[projects."/workspaces/baseball-crawl"]
trust_level = "trusted"
# --- end baseball-crawl Codex trust ---

BLOCK

prepend_managed_block "$BASHRC" "$ENV_START_MARKER" "$ENV_END_MARKER" "$EXPORT_BLOCK"
prepend_managed_block "$ZSHRC" "$ENV_START_MARKER" "$ENV_END_MARKER" "$EXPORT_BLOCK"

mkdir -p "$CODEX_HOME_DIR"
touch "$CODEX_CONFIG_PATH"

if grep -qF "$TRUST_START_MARKER" "$CODEX_CONFIG_PATH"; then
    append_managed_block "$CODEX_CONFIG_PATH" "$TRUST_START_MARKER" "$TRUST_END_MARKER" "$TRUST_BLOCK"
elif grep -qF '[projects."/workspaces/baseball-crawl"]' "$CODEX_CONFIG_PATH"; then
    :
else
    append_managed_block "$CODEX_CONFIG_PATH" "$TRUST_START_MARKER" "$TRUST_END_MARKER" "$TRUST_BLOCK"
fi
