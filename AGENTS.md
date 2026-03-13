# Codex Role

Codex is a secondary, watchful partner in this repo. Default to verification, review, bounded implementation, and context integrity. Do not take over product planning or recreate the Claude agent system inside Codex outputs.

## Start Here

1. Read `CLAUDE.md` for project rules, environment boundaries, and workflow expectations.
2. If the task is scoped to an epic, story, or review request, read only the active files for that work under `epics/` or the referenced rubric.
3. Load only the `.claude/` files that are directly relevant to the current task. Do not bulk-read the entire `.claude/` tree.

## Claude Context

- Use `.claude/rules/` only when the task needs a specific workflow or constraint.
- Use `.claude/skills/.../SKILL.md` only when the task depends on that workflow.
- Use the repo skill `claude-context-bridge` under `.agents/skills/` when you need help deciding which Claude artifacts to load.

## RTK Usage

This repo includes a project-local [RTK](https://github.com/rtk-ai/rtk) (Rust Token Killer) binary that produces token-optimized output for common shell commands. RTK reduces context-window consumption by 60-90% on verbose commands.

**Binary path**: `.tools/rtk/rtk` (repo-relative) or `/workspaces/baseball-crawl/.tools/rtk/rtk` (absolute). The binary is gitignored and installed automatically by the devcontainer post-create script.

**Important**: This repo does NOT use a transparent Claude-style RTK hook for Codex. There is no command-rewrite layer, no PATH shim, and no alias that shadows `git`, `ls`, or `cat`. RTK usage in Codex is intentional and explicit -- you invoke `rtk` by name when you want optimized output.

### When to use RTK

Prefer `.tools/rtk/rtk <command>` over the raw command for these high-token operations:

| Instead of | Use | Why |
|------------|-----|-----|
| `git status` | `.tools/rtk/rtk git status` | Strips decoration, compresses output |
| `git diff` | `.tools/rtk/rtk git diff` | Condensed diff, only changed lines |
| `git log` | `.tools/rtk/rtk git log` | Compact log format |
| `ls` (large dirs) | `.tools/rtk/rtk ls` | Tree-style, filtered output |

### When NOT to use RTK

Use the raw command directly when:
- RTK does not support the command (check `rtk --help` for the supported list)
- You need the full unfiltered output (e.g., debugging a test failure, reading exact error messages)
- The command is already low-token (e.g., `echo`, `pwd`, `cat` on a small file)
- You are unsure whether RTK will alter the output in a way that matters for the task

**Fallback rule**: If RTK does not support a command or you are uncertain about its behavior, use the raw command directly. RTK is an optimization, not a requirement.

### Coexistence with Claude RTK

The Claude lane in this repo may use its own RTK integration (global hooks, shell rewrites). That setup is separate from the Codex lane. Codex uses the project-local binary with explicit invocation as described above. Both lanes coexist without conflict.

## Operating Posture

- Prioritize evidence, risk detection, and precise changes.
- Keep work bounded to the user's request.
- Treat `.codex-home/` as sensitive local runtime state. Do not commit or rewrite it unless the task is explicitly about Codex bootstrap or troubleshooting.
