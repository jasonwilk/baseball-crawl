---
paths:
  - "**"
---

# Worktree Isolation -- Agent Constraints

When you are spawned with `isolation: "worktree"`, you are working in a temporary git worktree outside the main checkout. This changes what you can and cannot do.

## How to Know You Are in a Worktree

Your working directory will be something like `/tmp/.worktrees/baseball-crawl-abc123/` instead of `/workspaces/baseball-crawl`. If your cwd is not the main checkout, assume worktree constraints apply.

## What You MUST NOT Do

### No Docker Interaction
- Do NOT run `docker compose` commands (up, down, restart, ps, logs, build)
- Do NOT run `curl localhost:8001` or any health checks against the app
- Do NOT attempt to rebuild or restart the app container
- The Docker stack reads from the main checkout, not from your worktree

### No App/Credential/Database CLI Commands
- Do NOT run `bb data sync`, `bb data crawl`, `bb data load`
- Do NOT run `bb creds check`, `bb creds refresh`, `bb creds import`
- Do NOT run `bb db reset`, `bb db backup`
- Do NOT run `bb status`
- These commands assume the main checkout and interact with the live app, credentials, or database

### No Proxy Commands
- Do NOT run `bb proxy *` commands (`bb proxy report`, `bb proxy endpoints`, `bb proxy check`, etc.)
- Do NOT run `./scripts/proxy-*.sh` scripts
- These assume main-checkout paths for `proxy/data/`

### No Credential or Data File Access
- `.env` is gitignored and **does not exist** in your worktree
- `data/` is gitignored and **does not exist** in your worktree
- Do NOT attempt to read credentials, access the app database, or reference data files
- If your code needs `.env` values, use `__file__`-relative path resolution (not cwd-relative)

### No Context-Layer Modifications (Unless Assigned)
- Do NOT modify `CLAUDE.md`, `.claude/agents/*.md`, `.claude/rules/*.md`, `.claude/skills/**`, `.claude/hooks/**`, `.claude/settings.json`, or `.claude/agent-memory/**`
- Context-layer files are shared infrastructure and must be modified in the main checkout
- Exception: if your story is explicitly a context-layer story assigned to you in the main checkout (pure context-layer stories are never dispatched to worktrees)
- Exception: mixed stories (context-layer + code files) are dispatched to `claude-architect` WITH worktree isolation. In this case, the architect edits both context-layer and code files from the worktree, and changes are merged back like any other worktree story.

### No Branch or Worktree Management
- Do NOT run `git merge`, `git rebase`, `git worktree remove`, or `git branch -d`
- Do NOT attempt to merge your work back into the main branch
- Branch management, merging, and worktree cleanup are handled by the main session

## What You CAN Do

### Run Tests
- `pytest` is safe to run from worktrees
- Tests use `tmp_path`, `:memory:` SQLite databases, and mocked HTTP -- they do not depend on `.env`, `data/`, or Docker

### Read and Write Source Code
- Edit files in `src/`, `tests/`, `migrations/`, `scripts/`, `docs/`, and other tracked directories
- Your changes are on an isolated branch and will be merged by the main session after review

### Use Git for Inspection
- `git status`, `git diff`, `git log` are safe
- Committing your changes is fine -- the main session handles the merge

## File Paths in Reports

When reporting `## Files Changed`, use **absolute paths** (e.g., `/tmp/.worktrees/baseball-crawl-abc123/src/foo.py`). The main session and code-reviewer need these paths to locate your work in the worktree.
