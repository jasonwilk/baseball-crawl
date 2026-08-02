# E-280-07: TRIM 1 rule-side — bound verdict re-issuance and reduce the insurance prose

## Epic
[E-280: Context-Layer Healing](./epic.md)

## Status
`TODO`
<!-- Unblocked 2026-08-02: OQ-5 ruled (PM retains AC authority; one-of-each). Still sequenced after E-280-02, which defines the mechanism this file states. -->

## Description
After this story, `dispatch-pattern.md` and `worktree-isolation.md` state the same answer as the implement skill on **who issues which verdict and how many times**, and the delivery-insurance paragraph is reduced to its mechanism plus the bound that keeps it honest. This is the rule-side half of TRIM 1; E-280-02 is the skill-side half.

## Context
⚠️ **This story's target reversed on 2026-08-02 and the earlier version is preserved below because a reader who skims will otherwise implement it.** It used to read *"retire dual approval and the insurance prose"*, and its AC-1 required verifying by **absence** that no sentence asserts dual approval or PM AC-authority. The operator ruled the opposite: **"pm owns acceptance"**, verdict economy is **one-of-each**. ⚰ **RETIRED, do not implement:** ~~strike "Both PM and code-reviewer must approve before the staging boundary advances" and "PM is authoritative on ACs" from `dispatch-pattern.md`~~. **Both sentences are TRUE under one-of-each and must SURVIVE this story.** Deleting either is the single clearest way to fail it.

What remains genuinely in scope is narrower and still real. `dispatch-pattern.md` and `worktree-isolation.md` carry the **"unstaged = current story"** invariant, which E-280-02's freeze retires — that is a mechanism statement made false by the freeze, not an authority statement made false by a ruling. And the delivery-insurance prose exists because delivery was unverifiable; the freeze gives the dispatch case a mechanical substitute for part of it.

Leaving a genuinely stale mechanism statement standing is worse than not making the change at all: an instruction pair in tension is the named cause of the harm this epic treats, and the vendor's own 80%-removal result attributes the benefit to removing conflicting guidance rather than to removing volume. **That argument cuts both ways here** — it is the same reason not to delete a sentence the operator ruled is correct.

The insurance paragraph is a different case and needs care rather than deletion. `dispatch-pattern.md`'s "Effect in the artifact is a receipt" exists because delivery was unverifiable; the freeze gives the dispatch case a mechanical substitute. But its ⚠ bound — that questions, rulings, holds and status reports cause no artifact effect and so remain unverifiable by this method — has no substitute and must survive. That bound is the half that stops the technique failing silently on exactly the classes that went missing in E-277.

## Acceptance Criteria

- [ ] **AC-1**: **Verify by absence, and the absent thing is the STALE MECHANISM, not the authority.** Zero occurrences remain **in the files this story owns** of a sentence defining the review surface as unstaged working-directory state, or equating unstaged content with the current story's changes. **RED**: any occurrence in `dispatch-pattern.md`, `worktree-isolation.md` or `workflow-discipline.md`. (Grep for the false forms and require zero; do not confirm the replacement arrived. A botched edit leaving both forms standing reads fine to a skimmer.)
- [ ] **AC-1b**: **PM's AC authority and the two-approver requirement SURVIVE.** `dispatch-pattern.md` still states that PM is authoritative on ACs and that both PM and code-reviewer approve before the staging boundary advances. **RED**: either statement deleted, weakened to advisory, or reassigned to another agent. (This AC exists because this story's own earlier text instructed the opposite, and because an implementer working from TN-11's site list — compiled to find dual-approval text to delete — will be holding a worklist that points the wrong way.)
- [ ] **AC-1c**: **The layer-wide check, run LAST and as a verification rather than a licence to edit.** Across `CLAUDE.md`, `.claude/rules/`, `.claude/skills/` and `.claude/agents/`, zero occurrences of the invariant remain. **RED**: any occurrence. **This story is sequenced last precisely so this AC is reachable** — the out-of-owner sites are removed by the stories that own their files (E-280-02 for `implement/SKILL.md`, E-280-04 AC-15 for `code-reviewer.md`, E-280-06 AC-9 for `plan/SKILL.md` and `codex-review/SKILL.md`). **If a site remains, the finding is reported, not fixed here** — editing another story's file to pass this AC breaks the epic's file-disjointness and hides which story failed.
  - **Two sites are `no change needed` and must NOT be struck**, both independently confirmed: `implement/SKILL.md`'s Step 8 clean-tree preflight (*"Verify the main checkout has no unstaged or untracked changes"*) is about the **main checkout at closure**, a correct and unrelated use; and `worktree-isolation.md`'s `git checkout --` prohibition, which AC-6 preserves with updated reasoning.
  - **`.claude/agent-memory/` is deliberately OUT of this AC's scope.** Several memory files rest on the retired invariant — software-engineer's `dispatch-git-gotchas.md` is built on it end to end — but each agent's memory is reconciled by its owning agent at closure under the deletion-side eviction discipline, never edited by another agent. Recorded as **item (4) of TN-15's closure-obligations block**, where all four memory-reconciliation obligations sit together.
- [ ] **AC-2**: Every site is reached by a **regenerated** sweep whose list is a superset of epic TN-11's floor, and every listed site carries a written verdict including `no change needed`. **RED**: a TN-11 site missing from the regenerated list, or a listed site with no verdict. (⚠ TN-11 is a floor for FINDING sites, never a list of sites to change. Under OQ-5 most of its entries should resolve to `no change needed`; `.claude/rules/workflow-discipline.md`'s statement of PM's dispatch-time AC role is the clearest expected instance.)
- [ ] **AC-3**: The layer contains no instruction pair in tension on who issues which verdict — every site assigning verdict authority states the same answer, and the same answer as `implement/SKILL.md` in its post-E-280-02 shape: **PM issues the AC verdict, code-reviewer issues the review verdict, each once.** **RED**: two sites assigning it differently.
- [ ] **AC-4**: The "Effect in the artifact is a receipt" paragraph is reduced to its mechanism plus its bound, and **the ⚠ bound survives in force**: that questions, rulings, holds and status reports cause no artifact effect and are unverifiable by this method. **RED**: the bound absent, demoted to a parenthetical, or the whole paragraph deleted. (Both halves required — the technique without its bound is worse than none.)
- [ ] **AC-5**: `worktree-isolation.md` no longer defines the review surface by staging state. **RED**: any surviving sentence equating unstaged content with the current story's changes.
- [ ] **AC-6**: The `git checkout --` prohibition in `worktree-isolation.md` survives, with its reasoning updated to the freeze mechanism rather than deleted. **RED**: the prohibition removed. (Its hazard is unchanged by the freeze — a staged prior story is still what `checkout --` restores — so this is a rule that must survive a change to the surrounding mechanism.)
- [ ] **AC-7**: The per-claim verification discipline is intact. **RED**: any edit reducing what a single verdict must establish, as opposed to how many verdicts are issued. See epic TN-3, "The residual floor."
- [ ] **AC-8**: `.claude/rules/workflow-discipline.md` states **no numeric count** of the context-layer assessment's triggers. Its Context-Layer Assessment Gate section refers to them without a number. **RED**: any numeral or number-word quantifying the triggers in that file. (One of four sites carrying the count; the edit lands here because no other story owns this file, and E-280-08 AC-11 verifies globally. See epic TN-16. **This is why `workflow-discipline.md` is now an unconditional entry in the Files list rather than the conditional one it was on 2026-08-02 — it has a definite edit, independent of the AC-2 sweep's verdict on PM's AC role, which remains `no change needed`.**)

## Technical Approach
Sweep for the invariant and for the judgements that depended on it, not for the phrase — `.claude/rules/doc-sweep.md` governs, and its warning is directly on point: a retired claim survives as a rating, a risk adjective, or a summary line sharing none of its tokens. The merge-base warnings in these files exist only because the review surface is currently defined by staging state; check each one rather than assuming.

Take `implement/SKILL.md` in its post-E-280-02 shape and match it. Where the two disagree, the skill is the mechanism and this file is the statement about it.

## Dependencies
- **Blocked by**: E-280-02 (this file must match the skill's final shape), **E-280-04** and **E-280-06** (both remove out-of-owner instances of the invariant that AC-1c verifies are gone). OQ-5 is closed.
- **Blocks**: **E-280-08** — its AC-11 verifies layer-wide that no numeric trigger count survives, and AC-8 here removes `workflow-discipline.md`'s.

**This story moved to LAST-but-one in the serial order on 2026-08-02.** It previously ran second, which made AC-1's layer-wide zero-check unsatisfiable: seven instances of the invariant live in files owned by E-280-04 and E-280-06, both of which ran after it. Moving 07 last costs nothing — it had no reason to precede either — and converts an impossible AC into a reachable verification.

## Files to Create or Modify
- `.claude/rules/dispatch-pattern.md` (modify)
- `.claude/rules/worktree-isolation.md` (modify)
- `.claude/rules/workflow-discipline.md` (modify — the AC-8 trigger-count de-restatement is a definite edit. Note the two concerns are independent: on the AC-2 verdict-authority sweep this file's expected verdict is `no change needed` under OQ-5, and that expectation is unchanged. No other story owns this file.)

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] The AC-2 regenerated site list committed as an artifact
- [ ] No regressions in existing tests

## Notes
Story number 07 rather than 03 or 05: those numbers were consumed by earlier drafts of this decomposition and are tombstoned in place. Numbers are never reused.
