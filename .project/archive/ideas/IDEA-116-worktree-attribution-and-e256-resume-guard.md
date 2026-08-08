# IDEA-116: cwd-based worktree attribution for the dispatch hooks (+ E-256 resume guard)

## Status
`CANDIDATE`

## Summary
Both dispatch hooks that detect the active epic worktree — `.claude/hooks/context-ratchet.sh` (E-260-07) and `.claude/hooks/worktree-guard.sh` — locate it with `ls -d /tmp/.worktrees/baseball-crawl-E-* | head -1`. When two or more epic worktrees exist at once, `head -1` picks one arbitrarily (lexical-ish), so the counter/guard can mis-attribute to the wrong epic. Replace the `head -1` glob with cwd-based attribution (derive the epic from the caller's working directory / the file path being written), so each hook acts on the epic it's actually operating in. The E-260-06 `send-message-counter.sh` shares the same `head -1` pattern and should be included.

## Why It Matters
The operator accepted shipping E-260 with the `head -1` limitation (single-worktree is the normal case), but the multi-worktree case is real and live: E-256 is parked with its worktree potentially present while other epics dispatch. Mis-attribution silently writes a counter/log into the wrong epic's `.dispatch-log/`, or evaluates the ratchet against the wrong tree.

**Coupled operational guard (must ship with, or before, this):** once E-260 merges and `send-message-counter.sh` goes live, a new epic dispatching while **E-256 stays parked** would mis-write `.dispatch-log/{sends.count,E-*.tsv}` into the E-256 worktree (via `head -1`). On E-256 resume, its `git add -A` would sweep those stray files into E-256's commit (E-256's `.gitignore` lacks the `.dispatch-log/sends.count` rule, and the `.tsv` is tracked-by-design). **Operator action before resuming E-256:** `rm -rf` the E-256 worktree's `.dispatch-log/` and confirm `git status` is clean. (E-256 is verified clean NOW — this guards against future mis-writes once the hook is live post-merge.)

## Rough Timing
Before the next time two epic worktrees coexist during dispatch — most concretely, before E-256 is resumed after E-260 merges. The resume guard is the near-term operator action; the cwd-attribution fix is the durable engineering fix.

## Dependencies & Blockers
- [ ] E-260 merged (the hooks go live from the main checkout on merge)
- [ ] Decide the cwd/path-derivation mechanism for epic attribution (the hooks receive the tool input JSON — the written file path or command string can carry the worktree prefix)

## Open Questions
- Can the hook reliably derive the epic from the PreToolUse input (file_path / command) in every case, or is an env/cwd signal needed?
- Should `worktree-guard.sh` change at all, or only the two counting/logging hooks? (worktree-guard denies all main-checkout writes regardless of WHICH worktree is active, so its `head -1` is only used for the deny message — lower stakes.)

## Notes
Surfaced during E-260-06/07 dispatch; operator ruled ship-06/07 as-is with this follow-up. Related to the worktree-isolation machinery (`.claude/rules/worktree-isolation.md`) and IDEA-054 (worktree-guard cross-contamination). CA owns the hooks.

---
Created: 2026-07-12
Last reviewed: 2026-07-12
Review by: 2026-10-10
