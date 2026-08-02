---
paths:
  - "**"
---

# Worktree Isolation

If your cwd is NOT `/workspaces/baseball-crawl` (e.g., `/tmp/.worktrees/baseball-crawl-E-NNN/`), you are in an epic worktree.

## Epic Worktree

- **Path pattern**: `/tmp/.worktrees/baseball-crawl-E-NNN/` (epic ID suffix, e.g., `baseball-crawl-E-137`)
- **Branch**: `epic/E-NNN`
- **Purpose**: Single shared workspace where all agents (implementers, PM, code-reviewer) work during dispatch. Stories execute serially; **each story is frozen into an addressable tree object on its completion report** (`git add -A && git write-tree`), and that frozen tree is what isolates per-story changes.
- **Who works here**: All agents during dispatch. The main session manages the worktree lifecycle, the freeze, and the staging boundary.

## Hook Enforcement

A PreToolUse hook (`.claude/hooks/worktree-guard.sh`) guards Write and Edit operations on the main checkout. Two modes:

1. **Dispatch active** (`git worktree list` REPORTS an epic worktree at `/tmp/.worktrees/baseball-crawl-E-*`): Blocks ALL Write/Edit to `/workspaces/baseball-crawl/` with no exception. This fails closed -- new paths are automatically protected without hook updates.
2. **No dispatch** (git reports no epic worktree): Blocks Write/Edit to implementation paths only (`src/`, `tests/`, `migrations/`, `scripts/`). All other main-checkout writes are allowed.

**A leftover DIRECTORY that git does not report is NOT a dispatch**, and deleting a directory is NOT how you clear dispatch mode. A crashed dispatch leaves the registry entry standing (git annotates it `prunable`) and mode 1 stays in force; clear it with **`git worktree remove <path>`**, which is scoped to that one entry. Removing the directory by hand leaves you blocked, which is the opposite of what it looks like it does.

**`git worktree prune` is NOT an interchangeable alternative.** It takes **no path argument** -- it cannot be aimed -- and is repo-GLOBAL: one run removes **every** prunable entry at once, including other epics' under concurrent dispatch. Prefer `remove <path>`.

⚠️ **Check, do not classify.** Run `git worktree list`: an entry annotated `prunable` is stale; an entry **without** that annotation is LIVE. **Do not reason from "the guard is blocking me" to "the dispatch must be stale"** -- being blocked is the NORMAL state during a live dispatch. Clearing is the operator's or the main session's action, never an agent's (hence the ban under Epic Worktree Constraints below): if you are an agent, write to the worktree instead and escalate. **The danger is not only deletion.** If a LIVE worktree's directory is even transiently missing, `prune` drops its registry entry, restoring the directory does **not** bring it back, and the guard then falls silently to mode 2 -- leaving the epic unprotected for the rest of the dispatch.

Worktree writes (`/tmp/.worktrees/...`) always pass unconditionally in both modes. The hook intercepts Write and Edit tool calls only (not Bash commands), so git operations are unaffected.

Note: mode 1 has NO agent-memory carve-out. During dispatch, own-memory writes -- dispatch-time deliverables AND closure-time writes (PM's Active→Archived flip and topic-file flushes, claude-architect's codification) -- go to the WORKTREE copy so they ride the closure patch and appear in the operator-approved diff. Consultation-mode own-memory writes are unaffected: they happen when git reports no epic worktree (mode 2), where the hook does not guard `.claude/agent-memory/`.

## Epic Worktree Constraints

- **No Docker/app CLI**: Do NOT run `docker compose`, `bb data`, `bb creds`, `bb db`, `bb status`, or `bb proxy` commands.
- **No credential/data access**: `.env` and `data/` do not exist in worktrees.
- **No committing**: Do NOT run `git commit`. The main session produces a single atomic commit at epic closure.
- **No branch management**: Do NOT run `git merge`, `git rebase`, `git worktree remove`, or `git branch -d/-D`.
- **No cd to main**: Stay in the epic worktree. Do NOT `cd /workspaces/baseball-crawl`.
- **Own-memory deliverables go in the worktree**: a dispatched story that writes an agent's own `.claude/agent-memory/<agent>/` files edits the WORKTREE copy, never the main-checkout copy. Since mode 1 no longer carves out agent-memory, a main-checkout own-memory write during dispatch is now hook-denied outright; it also bypasses the per-story staging boundary and trips the Step 8 clean-tree preflight. **The same rule covers closure-time own-memory writes**: PM's Active→Archived `MEMORY.md` flip and topic-file flushes (`archived-epics.md`, `epic-codifications.md`, numbering-state), and claude-architect's closure codification, are authored in the worktree copy at the Step 8 sub-step-3 authoring window so they ride the closure patch.
- **NEVER restore a working-tree file from the INDEX in a dispatch worktree. The hazard is the OPERATION, not one command's spelling.** The freeze (`git add -A && git write-tree` on every completion report) means the index holds **the last FROZEN state** — prior stories, plus this story as it stood when it was frozen — and never HEAD. **So any index restore silently destroys whatever was written since that freeze**, which is precisely the remediation work a story is most likely to be doing at the moment someone reaches for a quick revert. The mechanism changed and the prohibition did not: before the freeze the index held the previous story's state and a restore destroyed the whole current story; now it holds this story's last frozen state and a restore destroys the round in flight. **Both are silent, and neither is recoverable from git.** **Three spellings, one hazard:** `git checkout -- <file>`, `git checkout-index -f -- <file>`, and `git restore <file>`. **The last is the modern recommended spelling and the one a newer agent reaches for first**: `-W/--worktree` is its DEFAULT and `--source` defaults to the index (`git restore -h`). Assume any further spelling is in the class until you have checked what it restores FROM. This list is open, not exhaustive. It bites hardest on a file several stories all edit, and the mutation-verification practice is what invites it: an agent that just mutated a file to prove a test discriminates is exactly the agent reaching for a quick revert. Instead, `cp` the file to the scratchpad BEFORE mutating and restore from that copy. In E-267 `git checkout --` destroyed an entire story's changes to `src/db/reconcile_at_load.py`; the recovery was a scratchpad backup plus a full re-run of the verification battery, because a restore you did not verify is not a restore. **Naming one spelling was not enough, and the evidence is unusually direct**: in E-278 an implementer who had internalised this rule and had QUOTED it during that very dispatch then ran `git checkout-index` and lost unstaged work — it pattern-matched on the command NAME rather than on what the command does. Nothing was lost permanently only because the change was four reconstructible lines.
- **Use absolute paths**: All file operations use absolute paths under the epic worktree.

Full constraint set (including Bash write prohibitions and pytest limitation) is delivered in your spawn context via the implement skill (`.claude/skills/implement/SKILL.md`).
