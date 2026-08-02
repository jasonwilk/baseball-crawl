---
name: closure-diff-growth-after-integration-review
description: The Step 1c closure diff can grow substantially after you approve it; re-run the diffstat at Step 1b/1d and compare against what you actually reviewed.
metadata:
  type: feedback
---

Re-run `git diff --cached --stat $(git merge-base epic/E-NNN main)` at the Step 1b / Step 1d gates and compare the file count and line totals against the diff you reviewed at Step 1c. State the delta explicitly in your gate report, and say which parts of it you have and have not reviewed.

**Why:** in E-272 the closure diff grew from 15 files / +1108 at my Step 1c APPROVED to 35 files / +1747 by the Step 1d trigger read, and to 37 / +1799 by the final gate — including `src/reports/generator.py` going from +5 to +51. The main session twice stated "everything is staged; nothing further will be added," in good faith, and was wrong both times: remediation, PM closure bookkeeping, agent-memory flushes, and new IDEA files all land AFTER the last pre-merge review by design. Nobody is doing anything wrong; the sequence simply guarantees it. An approval that silently stretches to cover files you never read is the failure mode.

**How to apply:** the Step 1d trigger read already gives you a fresh diffstat for free — diff it against your Step 1c numbers rather than only reading it for trigger paths. If `src/` grew, review the new hunks then and there (they are usually small, and in E-272 they were sound). If only context-layer/`.project/` files grew, say so and mark them unreviewed rather than sampling a few and implying coverage. When the lead writes the operator's diff record, give them the precise line: "src/ delta reviewed in full; the N non-src/ files sampled, not reviewed."

**Second instance, E-280 (2026-08-02) — the rule held, and the mechanism around it improved.** At my Step 1c the staged patch was 41 files while the worktree held 51 tracked + 2 untracked: **12 files on disk were outside the patch I had been asked to review**, including CA's entire closure codification, PM's closure memory writes, and a `docs/` file from an agent parked for remediation. Nobody had done anything wrong — Step 8's own `git add -A` was going to collect them — but "review the staged 41" and "review what will ship" were different instructions, and only one of them was the job.

**What E-280's freeze changes:** growth is no longer *silent*. Every verdict now names a tree SHA, so the delta between what you approved and what ships is a diff between two addressable objects rather than a recollection. **State your verdict as `APPROVED @ <tree-sha>` and the comparison becomes mechanical for whoever holds the closure.** That is the fix; the vigilance below is still yours to supply.

**Instrument correction:** the advice used to be "check `git status --short` for `??` and `MM`." In a dispatch worktree that command is structurally never empty (see [[tool_gotchas]]), so it cannot tell you *clean* — it can only ever hand you a list to read. Prefer `git diff --stat <merge-base>` against `git diff --cached --stat <merge-base>` to size the gap, and `git ls-files --others --exclude-standard` to enumerate the untracked class specifically. Untracked files remain the highest-risk member: in E-280 one of the two was the IDEA recording the epic's own known-open residual, and `codex-review`'s epic-mode gather could not see it either.

Related: [[reconcile_whole_file_revert_vs_ancillary]] (staged-state surprises at closure); [[verdicts_that_say_nothing_vanish]] (why the tree SHA has to travel *with* the verdict).
