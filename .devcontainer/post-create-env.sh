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

ALIAS_START_MARKER="# --- baseball-crawl aliases ---"
ALIAS_END_MARKER="# --- end baseball-crawl aliases ---"

read -r -d '' ALIAS_BLOCK <<'BLOCK' || true
# --- baseball-crawl aliases ---
alias tbb='d=$(tmux ls -F "#{session_name} #{?session_attached,attached,detached}" 2>/dev/null | grep "^baseball" | grep detached | head -1 | cut -d" " -f1); if [ -n "$d" ]; then tmux attach-session -t "$d"; else n=0; s=baseball; while tmux has-session -t "$s" 2>/dev/null; do n=$((n+1)); s="baseball-$n"; done; tmux new-session -s "$s"; fi'
alias cbb='claude --dangerously-skip-permissions'
cd /workspaces/baseball-crawl 2>/dev/null
# --- end baseball-crawl aliases ---

BLOCK

prepend_managed_block "$BASHRC" "$ENV_START_MARKER" "$ENV_END_MARKER" "$EXPORT_BLOCK"
prepend_managed_block "$ZSHRC" "$ENV_START_MARKER" "$ENV_END_MARKER" "$EXPORT_BLOCK"
append_managed_block "$BASHRC" "$ALIAS_START_MARKER" "$ALIAS_END_MARKER" "$ALIAS_BLOCK"
append_managed_block "$ZSHRC" "$ALIAS_START_MARKER" "$ALIAS_END_MARKER" "$ALIAS_BLOCK"

mkdir -p "$CODEX_HOME_DIR"
touch "$CODEX_CONFIG_PATH"

if grep -qF "$TRUST_START_MARKER" "$CODEX_CONFIG_PATH"; then
    append_managed_block "$CODEX_CONFIG_PATH" "$TRUST_START_MARKER" "$TRUST_END_MARKER" "$TRUST_BLOCK"
elif grep -qF '[projects."/workspaces/baseball-crawl"]' "$CODEX_CONFIG_PATH"; then
    :
else
    append_managed_block "$CODEX_CONFIG_PATH" "$TRUST_START_MARKER" "$TRUST_END_MARKER" "$TRUST_BLOCK"
fi

# ---- Project-local RTK install for Codex lane (E-082-01) ----
# Pins RTK to a specific release so upgrades are deliberate.
# To upgrade: update RTK_CODEX_VERSION below and rebuild the devcontainer.
# This is separate from the global Claude RTK lane in devcontainer.json postCreateCommand.
RTK_CODEX_VERSION="v0.29.0"
RTK_CODEX_DIR="${PROJECT_ROOT}/.tools/rtk"

_install_rtk_codex() {
    local version="$1"
    local install_dir="$2"

    # Idempotent: skip if the correct version is already installed.
    if [ -x "${install_dir}/rtk" ]; then
        local installed_ver
        installed_ver=$("${install_dir}/rtk" --version 2>/dev/null | awk '{if (NF>=2) print "v" $2; else print ""}')
        if [ "$installed_ver" = "$version" ]; then
            echo "rtk-codex: ${version} already installed at ${install_dir}/rtk"
            return 0
        fi
    fi

    # Detect Linux architecture and map to the RTK release target triple.
    # Triples confirmed against v0.29.0 release assets: x86_64 uses musl (static),
    # aarch64 uses gnu -- the asymmetry is intentional upstream.
    local arch
    case "$(uname -m)" in
        x86_64|amd64)  arch="x86_64-unknown-linux-musl";;
        arm64|aarch64) arch="aarch64-unknown-linux-gnu";;
        *) echo "rtk-codex: unsupported architecture $(uname -m) -- skipping"; return 1;;
    esac

    local url="https://github.com/rtk-ai/rtk/releases/download/${version}/rtk-${arch}.tar.gz"
    local tmpdir
    tmpdir=$(mktemp -d)

    echo "rtk-codex: downloading ${version} (${arch})..."
    if ! curl -fsSL "$url" -o "${tmpdir}/rtk.tar.gz" 2>/dev/null; then
        echo "rtk-codex: download failed -- skipping"
        rm -rf "$tmpdir"
        return 1
    fi

    if ! tar -xzf "${tmpdir}/rtk.tar.gz" -C "$tmpdir" 2>/dev/null; then
        echo "rtk-codex: extraction failed -- skipping"
        rm -rf "$tmpdir"
        return 1
    fi

    # RTK release tarball contains a single top-level `rtk` binary (no subdirectory).
    mkdir -p "$install_dir"
    if ! mv "${tmpdir}/rtk" "${install_dir}/rtk"; then
        echo "rtk-codex: mv failed -- skipping"
        rm -rf "$tmpdir"
        return 1
    fi
    if ! chmod +x "${install_dir}/rtk"; then
        echo "rtk-codex: chmod failed -- skipping"
        rm -rf "$tmpdir"
        return 1
    fi
    rm -rf "$tmpdir"
    echo "rtk-codex: installed ${version} -> ${install_dir}/rtk"
}

_install_rtk_codex "$RTK_CODEX_VERSION" "$RTK_CODEX_DIR" || echo "rtk-codex install failed -- rest of devcontainer setup continues"
