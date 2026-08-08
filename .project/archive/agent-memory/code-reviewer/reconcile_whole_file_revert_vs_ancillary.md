---
name: reconcile-whole-file-revert-vs-ancillary
description: Two review checks from the E-251 Codex reconciliation — (1) whole-file git checkout in a reset/abort path destroys same-file ancillary edits staged elsewhere; (2) to judge a guard/hook "fix", run pre-vs-post AND the single-slash/negative control to prove which vector actually moved.
metadata:
  type: feedback
---

Two reusable review checks surfaced when reconciling Codex Priority-1 findings against E-251 dispatch-machinery repair (2026-07-05). I ran the real hook + a faithful no-dispatch harness + read the actual skill text rather than trusting my own prior APPROVED pass — and my Phase 4a APPROVED was wrong on one of them.

## Check 1 — Whole-file revert in a reset/abort path destroys same-file ancillary edits (VALID defect class)
When a closure/abort/reset sequence reverts a file with a WHOLE-FILE command (`git checkout -- <file>`, `git checkout -- .`), verify no OTHER step in the same flow legitimately stages a DIFFERENT edit to that SAME file. A whole-file revert cannot distinguish hunks: it destroys the intended-to-revert hunk AND the ancillary-to-preserve hunk together.

**Why:** E-251-01 was chartered to stop the abort path destroying ancillary edits. It fixed `git checkout -- .` → surgical reverts and preserved vision-signals/ideas, but left `git checkout -- .../product-manager/MEMORY.md` (whole-file) in the abort. Meanwhile Step 7a of the SAME skill explicitly STAGES `.claude/agent-memory/` edits as a recognized ancillary class, and sub-step 7 writes the Active→Archived flip to that SAME MEMORY.md. So on abort the whole-file checkout nukes both — reintroducing the exact bug class the story was meant to kill. The story's AC enumerated the survivor set as only "vision-signals/ideas" and thus missed the same-file overlap the closure design itself creates.

**How to apply:** For any reset/abort/rollback step, cross-reference every file it reverts against every file any staging/sweep step writes. Flag whole-file reverts on files that another step edits for a distinct purpose. Fix direction: reverse only the specific hunk, or stash/restore the ancillary state — never whole-file revert a file that carries two independent edits. Relates to [[feedback_staged_diff_verification]].

## Check 2 — To rule on a guard/hook "fix", prove which VECTOR moved (pre-vs-post + negative control)
Don't rule a guard fix effective/ineffective from prose or one input. Run: (a) the input WITH the fix, (b) the same input WITHOUT the fix (revert the one line / harness it), and (c) the benign/single-slash CONTROL. The delta between (a) and (b) is what the fix actually closes; (c) tells you whether the disputed input was ever in the guard's scope at all.

**Why:** Codex claimed worktree-guard's double-slash fix was ineffective because relative `src//foo.py` returns no denial. True — but its single-slash sibling `src/foo.py` is ALSO allowed: the guard only acts on the main-checkout ABSOLUTE prefix (a gate that predates the fix), and the Write/Edit tool only ever emits absolute paths, so the relative form is unreachable. The fix's real, reachable effect is on ABSOLUTE `/workspaces/baseball-crawl//src/foo.py`: pre-fix that leaves REL_PATH=`/src/foo.py` (leading slash) which misses the `src/*` denylist → BYPASS in no-dispatch mode; post-fix it normalizes → DENY. Codex never ran the single-slash control, so it mistook "guard doesn't cover relative paths by design" for "the fix failed." An AC's parenthetical `(e.g. src//foo.py)` is illustrative; the BINDING clause was "blocked where the single-slash form would be blocked" — and the single-slash form wasn't blocked either.

**How to apply:** When a finding says a fix "doesn't work," reproduce with the fix reverted to see the real delta, and always run the negative/sibling control. Distinguish "the guard's pre-existing scope" from "what this fix changed." Read the AC's binding clause, not just its example. Ties to `.claude/rules/tool-output-integrity.md` (verify against real output, don't relay a prior pass).
