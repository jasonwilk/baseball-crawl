# Removed/rewritten text snapshot — mode-1 agent-memory exemption + closure-sequence relocation

- **Story:** E-260-05 (Drop the worktree-guard mode-1 agent-memory exemption + relocate closure-time own-memory writes)
- **Date:** 2026-07-11
- **Defect citation:** Dropping the mode-1 agent-memory exemption makes the first post-merge closure hook-block PM's own closure memory writes — sub-step 7 (and the topic-file flushes / CA codification) direct a main-checkout `MEMORY.md` Write/Edit while the epic worktree still exists, which the de-exempted hook denies, deadlocking the next epic's (E-256's) closure. Relocating all closure-time own-memory writes into the sub-step-3 worktree patch removes the main-checkout writes entirely.

---

## `.claude/hooks/worktree-guard.sh`

### Header comment (:7-10) — agent-memory allowlist bullet removed

```
# 1. DISPATCH ACTIVE (epic worktree at /tmp/.worktrees/baseball-crawl-E-* exists):
#    Blocks ALL Write/Edit to /workspaces/baseball-crawl/ EXCEPT the allowlist:
#      - .claude/agent-memory/*  (agents write to their own memory in main checkout)
#    This fails closed -- any new path added to the project is automatically protected.
```

### `..`-handling comment (:64-65) — agent-memory-allowlist rationale removed

```
# dispatch mode ".claude/agent-memory/../src/foo.py" would match the agent-memory
# allowlist glob yet land outside it. No legitimate main-checkout Write/Edit uses
```

### `..` deny reason (:77)

```
permissionDecisionReason: "Path contains a \"..\" segment, which can resolve past the worktree guard. Write to a clean, fully-resolved path (under the epic worktree during dispatch, or .claude/agent-memory/ in the main checkout)."
```

### Mode-1 allowlist block (:88-92) — DELETED

```
  # --- DISPATCH ACTIVE: allowlist mode ---
  # Only agent-memory writes are permitted in the main checkout during dispatch.
  if [[ "$REL_PATH" == .claude/agent-memory/* ]]; then
    exit 0
  fi
```

### Mode-1 deny reason (:98) — allowlist clause removed

```
permissionDecisionReason: ("Dispatch is active (worktree: " + $worktree + "). During dispatch, Write/Edit to the main checkout is blocked -- use the epic worktree path instead. Only .claude/agent-memory/ is allowed in the main checkout during dispatch.")
```

---

## `.claude/rules/worktree-isolation.md`

### :21 (mode-1 description)

> 1. **Dispatch active** (epic worktree at `/tmp/.worktrees/baseball-crawl-E-*` exists): Blocks ALL Write/Edit to `/workspaces/baseball-crawl/` except `.claude/agent-memory/*`. This fails closed -- new paths are automatically protected without hook updates.

### :26 (carve-out note — REWRITTEN)

> Note: the `.claude/agent-memory/*` carve-out in mode 1 exists for CONSULTATION-mode own-memory writes (no worktree active). A dispatched story whose deliverable IS an agent's own memory MUST instead edit the worktree copy (see Epic Worktree Constraints), so it rides the closure patch.

### :35 ("Own-memory deliverables go in the worktree" — EXTENDED by one line)

> - **Own-memory deliverables go in the worktree**: a dispatched story that writes an agent's own `.claude/agent-memory/<agent>/` files edits the WORKTREE copy, never the main-checkout copy. The worktree-guard own-memory carve-out is for consultation-mode only; using it for a story deliverable bypasses the per-story staging boundary and trips the Step 8 clean-tree preflight.

---

## `.claude/skills/implement/SKILL.md` (closure-sequence relocation)

### :32 (Enforcement model) — exception removed
> **Enforcement model**: A PreToolUse hook (`.claude/hooks/worktree-guard.sh`) blocks Write and Edit operations to the main checkout during dispatch (all paths except `.claude/agent-memory/`). ...

### :462 / :472 (COMPLETED-flip explainers) — "(except `.claude/agent-memory/*`)" parentheticals removed; extended so PM authors BOTH the COMPLETED flip AND the MEMORY.md flip in the worktree at sub-step 3. (Full pre-edit text captured in git history; the load-bearing removed token is "(except `.claude/agent-memory/*`)".)

### :552 (Step-8 intro)
> Merge the epic worktree's accumulated changes into the main checkout and produce a single atomic commit that contains the applied patch, the archive rename, and the PM memory update.

### :571 (sub-step 5 red path) — clause about sub-step-7 PM memory "NOT run yet"
> ...the archive rename in sub-step 6 and PM memory update in sub-step 7 have NOT run yet...

### :577 (sub-step 7) — REWRITTEN to a pointer + generalized
> 7. **PM memory update:** PM moves the epic from "Active Epics" to "Archived Epics" in `.claude/agent-memory/product-manager/MEMORY.md`. PM writes to the main-checkout path; `.claude/hooks/worktree-guard.sh` exempts `.claude/agent-memory/*` from the dispatch-active denylist, so this Write/Edit passes the hook while the epic worktree still exists.

### :579 (sub-step 8) — "and the PM memory update" dropped
> 8. **Stage on main:** `cd /workspaces/baseball-crawl && git add -A` (stage the applied patch, the archive rename, and the PM memory update together)...

### :587 (sub-step 9 preamble) — "the PM memory update happened in sub-step 7" removed
> **User rejects**: The main checkout is half-closed at this point (the patch was applied in sub-step 4, the full-suite gate passed in sub-step 5, the archive rename happened in sub-step 6, and the PM memory update happened in sub-step 7 -- all before the gate). Three reject paths:

### :591 (abort path) — "three Step-8 closure actions" incl. the sub-step-7 PM-memory edit
> - (c) **'abort'**: Individually reverse the three Step-8 closure actions -- the applied patch (sub-step 4), the archive rename (sub-step 6), and the sub-step-7 PM-memory Active->Archived edit -- while PRESERVING every Step 7a ancillary edit...

### :599 (surgical PM-memory reversal paragraph) — DELETED IN FULL
> **Reverse the sub-step-7 PM-memory edit surgically (not with `git checkout`).** The main session does NOT `git checkout -- .claude/agent-memory/product-manager/MEMORY.md` -- a whole-file revert to HEAD cannot distinguish the two hunks that MEMORY.md may carry at this point: (i) a legitimate Step 7a `.claude/agent-memory/` edit (e.g. a PM numbering-state flush), which MUST be preserved, and (ii) the sub-step-7 Active->Archived flip, which MUST be reversed. A whole-file checkout would destroy both -- the exact ancillary-destruction class this reset was corrected to eliminate. Instead, the main session directs PM (still on the team -- PM is not shut down until Step 10) via SendMessage to reverse its OWN sub-step-7 edit: move epic E-NNN from "Archived Epics" back to "Active Epics" in `.claude/agent-memory/product-manager/MEMORY.md`. Because PM edits only the lines it wrote at sub-step 7, this undoes hunk (ii) while leaving any Step 7a hunk (i) intact. This respects ownership boundaries: PM owns its memory file (the main session cannot edit it, and `worktree-guard.sh` exempts `.claude/agent-memory/*`), and the reversal is the exact inverse of the edit PM authored. The PM-memory flip MUST be reversed, not left in place: `git apply -R` flips `epic.md` back to ACTIVE, so a surviving "Archived" PM-memory entry would strand memory in an inconsistent state against an ACTIVE epic.

### :601 (post-reset summary) — "and the sub-step-7 PM-memory flip" dropped from the reversed list
> After the reset, the applied patch (including any files it created), the archive rename, and the sub-step-7 PM-memory flip are all reversed, and every Step 7a ancillary edit (vision-signals, ideas, and any agent-memory edit) remains...

### :605 (sub-step 10 commit) — "and the PM memory update" reworded (now inside the patch)
> 10. `git commit -m "feat(E-NNN): <epic title>"`. The single commit atomically contains the applied patch, the archive rename, and the PM memory update.

### :627 (Step 11) — "its Active→Archived MEMORY.md update is sub-step 7" reworded
> PM writes `.claude/agent-memory/**` during closure (its Active→Archived `MEMORY.md` update is sub-step 7, captured by the closure commit)...

### Step 7a item 1 agent-memory bullet (:526) — ANNOTATED (narrowed to pre-dispatch plan leftovers)
> - `.claude/agent-memory/` (leftover planning artifacts not committed by plan skill Step 2a, if any)...

### Step 3a (:494-496) — generalization note ADDED (CA closure codification incl. own agent-memory authored in worktree)

### PM spawn context (:160) — 6th same-class site found while editing (AC-8), same treatment + same citation
> Do NOT use Write/Edit on paths starting with `/workspaces/baseball-crawl/` -- that is the main checkout, not your worktree. Exception: `.claude/agent-memory/product-manager/` (your persistent memory in the main checkout).

This is a dispatch-time own-memory-write allowance (PM told it may write its memory to the MAIN checkout during dispatch) — the exact class the de-exemption closes. Relocated to the WORKTREE copy under the same defect citation.
