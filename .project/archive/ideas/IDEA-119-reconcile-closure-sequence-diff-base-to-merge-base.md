# IDEA-119: Reconcile the whole Step 8 closure sequence to a single merge-base diff base (post-E-260 residual)

## Status
`DISCARDED` — **MOOT / already landed (2026-07-12).** Team-lead confirmed against main that **E-260-01 AC-6 already shipped the merge-base closure-diff reconciliation this idea proposes** — the whole Step 8 closure sequence on main uses `$(git merge-base epic/E-NNN main)`, not just sub-step 3. The residual this idea named (sub-step 9's `--stat main` at `SKILL.md:646`) was a **stale pre-E-260-worktree reading** — the E-256 worktree branched before E-260, so its `:646` still showed `--stat main`, exactly the same landmine that produced story-11 finding #1's `:480` false positive (a worktree-copy read of an already-fixed-on-main artifact). Nothing to do; discharged. *(Verification note: PM recorded this on the team-lead's `git show main:` check of E-260-01 AC-6; PM could not run git against main from the worktree.)*

## Summary
E-260 moved `implement/SKILL.md` Step 8 **sub-step 3** (the closure patch build) from `git diff --binary --cached main` to `git diff --binary --cached $(git merge-base epic/E-NNN main)`, so the closure patch reflects only the epic's own changes when main has diverged post-branch. But the OTHER `main`-based reads in the same closure sequence were **not** reconciled — sub-step 9's present-diff still reads `git diff --cached --stat main` (`SKILL.md:646`), and any other `main`-based closure read is likewise unchanged. The sequence is therefore **internally inconsistent about its own diff base**: the patch is built against merge-base, but the operator-facing "here is what will be committed" summary is computed against `main`, so on a diverged main the two describe different filesets. This idea reconciles the whole sequence to one base.

## Why It Matters
A closure summary (sub-step 9) that diffs against `main` while the patch (sub-step 3) diffs against merge-base shows the operator a **different** change set than what is actually being committed whenever main has diverged since the worktree branched — exactly the E-256-over-E-260 case. The operator approves the commit off that summary, so a mismatched base undermines the approval gate: post-branch divergence appears as spurious adds/deletes in the summary that are not in the patch (or vice-versa). Aligning every closure-sequence diff to the merge-base makes the summary the operator approves byte-consistent with the patch that lands.

This surfaced during E-256 story 11 (the Step 1d smoke), whose trigger read is correctly authored against merge-base and whose rationale cross-references sub-step 3 — a cross-reference CR verified is TRUE in the shipped (post-E-260) skill, so story 11 needs no fix. The residual is NOT in story 11's Step 1d text; it is that sub-step 9's present-diff was left at `--stat main` when E-260 moved sub-step 3 to merge-base. This idea removes that surviving inconsistency in the shipped closure sequence.

## Rough Timing
Fold into the next `implement/SKILL.md` closure-sequence revision, or a context-layer-discipline pass. No urgency — the divergence only produces a *misleading summary*, not a wrong commit (the patch itself is correct against merge-base). Promote when the next epic branches long before it closes (a long-lived worktree over a moving main), which is when the summary/patch base mismatch is most visible.

## Dependencies & Blockers
- [ ] None hard. A `.claude/skills/implement/SKILL.md` edit (CA-owned, context-layer).

## Open Questions
- Enumerate every `main`-based read in the Step 8 sequence (at least sub-step 9's `git diff --cached --stat main`; audit sub-steps 2, 4, and the clean-tree preflight for any others) and decide which must move to merge-base vs. which are legitimately main-relative (e.g. `git apply --check` targets the main working tree, not a diff base).
- Should the merge-base be computed once and reused as a variable across the sequence, rather than re-invoking `$(git merge-base epic/E-NNN main)` at each site (avoids drift and repeated subshells)?
- Does the archive-check / PII hooks assume a `main` base anywhere that a switch would perturb?

## Notes
Surfaced by PM during E-256 story-11 (Step 1d) AC verification, 2026-07-09, and confirmed by the team-lead: E-260 ALREADY moved sub-step 3 to `$(git merge-base epic/E-NNN main)` in the main-checkout skill governing this dispatch; sub-step 9's `--stat main` and peers were not reconciled. **This is a post-E-260, defect-cited observation — it does NOT reopen E-260 broadly (the meta-layer is frozen except defect-cited changes).** **Out of scope for E-256 story 11** (that story is the Step 1d smoke, not the closure-merge mechanics). **Domain: claude-architect** (`implement/SKILL.md` is the context layer). Related: `.claude/rules/dispatch-pattern.md` (closure merge sequence), `.claude/agent-memory/product-manager/feedback_plan_into_epic_worktree.md` ("closure diff base must be merge-base, not main").

---
Created: 2026-07-09
Last reviewed: 2026-07-09
Review by: 2026-10-07
