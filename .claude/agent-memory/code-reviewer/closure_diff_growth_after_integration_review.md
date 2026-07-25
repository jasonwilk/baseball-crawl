---
name: closure-diff-growth-after-integration-review
description: The Step 1c closure diff can grow substantially after you approve it; re-run the diffstat at Step 1b/1d and compare against what you actually reviewed.
metadata:
  type: feedback
---

Re-run `git diff --cached --stat $(git merge-base epic/E-NNN main)` at the Step 1b / Step 1d gates and compare the file count and line totals against the diff you reviewed at Step 1c. State the delta explicitly in your gate report, and say which parts of it you have and have not reviewed.

**Why:** in E-272 the closure diff grew from 15 files / +1108 at my Step 1c APPROVED to 35 files / +1747 by the Step 1d trigger read, and to 37 / +1799 by the final gate — including `src/reports/generator.py` going from +5 to +51. The main session twice stated "everything is staged; nothing further will be added," in good faith, and was wrong both times: remediation, PM closure bookkeeping, agent-memory flushes, and new IDEA files all land AFTER the last pre-merge review by design. Nobody is doing anything wrong; the sequence simply guarantees it. An approval that silently stretches to cover files you never read is the failure mode.

**How to apply:** the Step 1d trigger read already gives you a fresh diffstat for free — diff it against your Step 1c numbers rather than only reading it for trigger paths. If `src/` grew, review the new hunks then and there (they are usually small, and in E-272 they were sound). If only context-layer/`.project/` files grew, say so and mark them unreviewed rather than sampling a few and implying coverage. When the lead writes the operator's diff record, give them the precise line: "src/ delta reviewed in full; the N non-src/ files sampled, not reviewed."

Related: [[reconcile_whole_file_revert_vs_ancillary]] (staged-state surprises at closure), and the sibling staging defect this same epic produced twice — an untracked IDEA file plus unstaged README index rows that `git diff --cached` would have dropped from the closure patch entirely. Check `git status --short` for `??` and `MM` before trusting "everything is staged."
