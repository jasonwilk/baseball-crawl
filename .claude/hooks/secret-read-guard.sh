#!/bin/bash
# .claude/hooks/secret-read-guard.sh
# Claude Code PreToolUse hook: denies Read/Bash access to credential files.
#
# Threat (agentic-flow-review §4.2, item 13): nothing else stops a `cat .env`
# or a Read of `secrets/**` from pulling live GameChanger tokens into the model's
# context. The only other credential control (pii-check.sh) fires at commit time,
# which a READ never reaches -- so a token can enter context and be relayed,
# cached, or compacted long before any commit-time gate could see it.
#
# Denies Read and Bash operations that target:
#   - any `.env` / `.env.*` file           (**/.env*)
#   - anything under a `secrets/` directory (secrets/**)
# EXCLUDING template files whose basename carries the `.example` marker
# (e.g. `.env.example`, `secrets/pii-denylist.example.txt`) -- those are PII-free
# by construction and must stay readable.
#
# Denial is communicated via JSON output (permissionDecision: deny), NOT via exit
# code. Always exits 0. Fails OPEN (announced to stderr) if jq is unavailable --
# a guard must not become a hard blocker on its own missing dependency, but the
# gap must be visible.
#
# COVERAGE AND RESIDUAL LIMITATIONS (stated honestly -- a stateless PreToolUse
# hook scans the command STRING; it cannot sandbox every exfiltration form):
#   COVERS: literal references in the Read path or the Bash command text to a
#     `.env*` file, a file/dir under `secrets/`, or the `secrets` directory
#     itself -- including forms split out by tokenization such as
#     `cd secrets && cat creds.txt`, `source .env`, and quoted literals like
#     `open('secrets/x')`.
#   DOES NOT COVER (accepted): paths that are not present literally in the command
#     text -- e.g. runtime-computed or obfuscated paths
#     (`cat $(printf secre""ts)/x`, base64-decoded names), variable indirection
#     resolved by a subshell, or a path handed to a long-running process by
#     non-literal means. This hook RAISES THE BAR against the common accidental
#     or casual read (`cat .env`); it is not a sandbox. Defense-in-depth: the
#     commit-time PII scanner still gates what can be committed.

if ! command -v jq &>/dev/null; then
  echo "secret-read-guard: jq not found -- credential read guard INACTIVE" >&2
  exit 0
fi

INPUT=$(cat)
TOOL=$(echo "$INPUT" | jq -r '.tool_name // ""')

# path_is_protected <path>
# Returns 0 (protected -> deny) when the path targets a guarded credential file
# and is NOT an `.example` template; returns 1 otherwise. Operates on the string
# only (no filesystem access) so it is robust for both real and hypothetical
# paths named in a Bash command.
path_is_protected() {
  local p="$1"
  [ -z "$p" ] && return 1
  local base="${p##*/}"      # basename after the last slash
  # Exclusion FIRST: any `.example` template, whether the marker is a suffix
  # (`.env.example`) or an infix (`pii-denylist.example.txt`).
  case "$base" in
    *.example|*.example.*) return 1 ;;
  esac
  # .env family: basename begins with `.env` -- matches the AC glob `**/.env*`
  # verbatim (covers `.env`, `.env.local`, `.envrc`, `.env-prod`, ...). The
  # `.example` exclusion above runs first, so `.env.example` still passes.
  case "$base" in
    .env*) return 0 ;;
  esac
  # secrets/ tree: match the `secrets` directory as a WHOLE path component --
  # either a file/dir UNDER it (`*/secrets/*`) OR the directory itself
  # (`*/secrets`), so a bare `cd secrets` / `pushd ./secrets` token is caught too
  # (the caller strips a leading `./`; `secrets/` with a trailing slash is caught
  # by the `*/secrets/*` arm). The leading "/" prefix makes the glob match
  # `secrets` only as a whole component, so a sibling like `mysecrets` is NOT
  # falsely matched.
  case "/$p" in
    */secrets/*|*/secrets) return 0 ;;
  esac
  return 1
}

deny() {
  jq -n --arg t "$1" '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: ("Blocked: \"" + $t + "\" targets a credential file (.env* or secrets/**). Reading it would pull live secrets into context, where they can be relayed, cached, or compacted. Only *.example templates are readable. If you need a configuration value, ask the operator -- do not read the secret file directly.")
    }
  }'
  exit 0
}

case "$TOOL" in
  Read)
    FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // ""')
    if path_is_protected "$FILE_PATH"; then
      deny "$FILE_PATH"
    fi
    ;;
  Bash)
    COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // ""')
    # Tokenize the command so each candidate path is tested independently: a
    # command that touches ONLY an `.example` template must still pass, while
    # `cat .env` (or `... secrets/creds`) is denied. Translate shell separators
    # and metacharacters to newlines (deliberately NOT `/` or `.`, which are part
    # of paths). Built via printf so the single-quote and backtick separators are
    # included without breaking the shell quoting here.
    SEPARATORS=$(printf ' \t\n;|&<>()"=`,'; printf "'")
    TOKENS=$(printf '%s' "$COMMAND" | tr "$SEPARATORS" '\n')
    while IFS= read -r tok; do
      tok="${tok#./}"                 # normalize a leading ./
      [ -z "$tok" ] && continue
      if path_is_protected "$tok"; then
        deny "$tok"
      fi
    done <<< "$TOKENS"
    ;;
  *)
    exit 0
    ;;
esac

exit 0
