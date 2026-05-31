---
name: feedback-acceptance-command-surface-scope
description: When a dispatch-time failure lands inside an AC's named test command/file, it is in-scope for that story, not scope expansion
metadata:
  type: feedback
---

When a failure surfaces during dispatch that is NOT in the documented discovery baseline, decide scope by whether it falls inside an existing AC's acceptance surface — specifically a named pytest command or named file in an AC. If an AC already requires file X at 0-failed and a new failure lives in file X, fixing it is satisfying the existing AC, not expanding scope. Authorize the in-story fix rather than deferring to a new story.

**Why:** During E-230-01 dispatch (2026-05-31), SE found 2 stale-assertion failures in `tests/test_report_workload.py` not in the documented 56-failure baseline. They were already inside AC-5's named command (which required that file at 0-failed). Deferring to a new story would have been pure churn: same file, same epic theme (template correct/assertion stale/RTK-hidden), same decision-framework verdict, two-token fix, and the epic's own full-suite-green closure gate (Story 04) required them cleared anyway. Folded in as AC-7; baseline restated to 58.

**How to apply:** On a dispatch-time scope question, first check the story's ACs for named commands/files. In-surface + same theme + trivial + blocks closure regardless → authorize the in-story fix, add an AC capturing it, and note the baseline correction in epic History with the first-hand pre-existence evidence. Out-of-surface or different theme → route elsewhere. See [[feedback_no_preexisting_excuse]].