# Codex Guide

## Overview

This repo uses a small Codex layer that is split between checked-in project context and gitignored local runtime state.

## Checked-In Layer

These files are part of the repo and define the project-owned Codex context:

- `AGENTS.md`
- `.codex/config.toml`
- `.agents/skills/claude-context-bridge/SKILL.md`

This layer is intentionally small. It tells Codex how to work in this repo without recreating the Claude PM system or depending on experimental Codex features.

## Local Runtime Layer

The default runtime path is:

```bash
/workspaces/baseball-crawl/.codex-home
```

This directory is pointed to by `CODEX_HOME` and is gitignored. It may contain:

- `config.toml`
- `auth.json`
- `history.jsonl`
- `sessions/`
- sqlite state and other caches

These files are sensitive local artifacts. Do not commit them, paste them into tickets, or rewrite them casually.

## Bootstrap and Trust

`.devcontainer/post-create-env.sh` is the bootstrap source of truth.

It does three things:

1. injects the same managed env block into both `.bashrc` and `.zshrc`
2. exports `CODEX_HOME=/workspaces/baseball-crawl/.codex-home`
3. seeds a minimal trust entry in `$CODEX_HOME/config.toml` for `/workspaces/baseball-crawl`

That trust entry matters because Codex only loads the checked-in `.codex/config.toml` for trusted repos.

## Default Operator Model

- The default workflow is project-local. A host `~/.codex` bind is optional and not required.
- The checked-in repo layer stays in git; runtime state stays under `.codex-home/`.
- The baseline Codex lane does not require spawned agents, `multi_agent`, or other experimental Codex features.

## Repo Skill

Use `claude-context-bridge` when Codex needs to pull in existing Claude context for a task.

The skill teaches progressive disclosure:

1. start with `CLAUDE.md`
2. read the active epic or story files when the task is scoped
3. read only the specific `.claude/` artifacts the task needs

Do not bulk-read `.claude/`.

## Smoke Checks

Run these inside the devcontainer:

```bash
codex --version
echo "$CODEX_HOME"
test -d "$CODEX_HOME" && echo "CODEX_HOME exists"
grep -n 'projects.\"/workspaces/baseball-crawl\"' "$CODEX_HOME/config.toml"
codex features list
codex exec --help
```

Expected results:

- `echo "$CODEX_HOME"` prints `/workspaces/baseball-crawl/.codex-home`
- the `grep` command shows a trust entry for `/workspaces/baseball-crawl`
- `codex features list` and `codex exec --help` complete without TOML or config errors

## RTK Integration (Codex Lane)

RTK (Rust Token Killer) reduces token usage for high-output shell commands. The Codex lane has its own RTK operating model that differs materially from the Claude RTK lane.

### Operating Model

The Codex RTK integration is explicit, not transparent:

- Codex uses the full path `.tools/rtk/rtk <command>` directly -- e.g., `.tools/rtk/rtk git status`, `.tools/rtk/rtk git diff`.
- There is no automatic command-rewriting hook in the Codex lane. Every RTK call is intentional.
- The AGENTS.md guidance lists the commands where RTK is preferred and explains the fallback rule.

**Fallback rule**: when RTK does not support a command or a raw command is clearer, Codex uses the raw command directly. Using `rtk` is an optimization, not a requirement.

### Binary Location

The RTK binary is installed at:

```
/workspaces/baseball-crawl/.tools/rtk/rtk
```

This path is:

- Inside the project directory -- no global PATH addition is needed.
- Gitignored -- it is local state, not a committed project artifact.
- Installed at devcontainer bootstrap time by `.devcontainer/post-create-env.sh` (idempotent, non-blocking if it fails).

The bootstrap script pins the version via `RTK_CODEX_VERSION` and selects the correct architecture at install time (AMD64 or ARM64). Current pinned version: `v0.29.0`.

### What This Lane Does NOT Use

- **No `rtk init -g` or `--auto-patch`**: Those commands patch Claude's global settings/hook system. The Codex lane does not write to `~/.claude/settings.json` or any Claude hook.
- **No PATH shims**: `git`, `ls`, `cat`, and similar binaries are not shadowed. The Codex lane uses the full binary path (`.tools/rtk/rtk <command>`), not bare `rtk`.
- **No additional `~/.codex` requirement**: The Codex RTK lane adds nothing to the existing `~/.codex` optional mapping. Host-global setup is not required or assumed.

### Coexistence with the Claude RTK Lane

Claude (the Claude Code CLI) uses a separate RTK lane established in E-070:

- **Claude lane**: host/global RTK install, hook-based automatic command rewriting, `rtk init -g`.
- **Codex lane**: project-local binary at `.tools/rtk/rtk`, checked-in AGENTS.md guidance, explicit invocation.

Both lanes can be active at the same time. They are independent and do not interfere with each other. An operator who has completed Claude RTK setup does not need to undo anything for the Codex lane to work -- and an operator who has only the Codex lane set up does not need to run `rtk init -g`.

### RTK Smoke Check

To verify the Codex RTK setup, run:

```bash
python scripts/check_codex_rtk.py
```

Expected output when all checks pass:

```
[OK  ] binary present: /workspaces/baseball-crawl/.tools/rtk/rtk
[OK  ] rtk --version: rtk 0.29.0
[OK  ] rtk git status: <first line of git status output>
```

Exit code is `0` on success. Any `[FAIL]` line means that check did not pass; exit code is `1`. Common failure causes:

- Binary not present: devcontainer bootstrap did not complete, or RTK install failed (non-blocking -- check bootstrap logs).
- Version mismatch: `RTK_CODEX_VERSION` in `post-create-env.sh` and the installed binary differ.
- `rtk git status` fails: the binary is present but not executable, or RTK has a bug with the current git state.

## Notes

- The global `codex` binary is still installed the same way in the devcontainer. This setup only changes runtime state placement and checked-in project guidance.
- If you want cross-project continuity later, a host `~/.codex` mount can be added deliberately. It is not part of the default repo setup.
