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

## Notes

- The global `codex` binary is still installed the same way in the devcontainer. This setup only changes runtime state placement and checked-in project guidance.
- If you want cross-project continuity later, a host `~/.codex` mount can be added deliberately. It is not part of the default repo setup.
