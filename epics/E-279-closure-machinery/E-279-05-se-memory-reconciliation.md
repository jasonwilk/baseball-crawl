# E-279-05: Reconcile software-engineer memory to the deleted hook

## Epic
[E-279: Closure machinery](../E-279-closure-machinery/epic.md)

## Status
`TODO`

## Description
After this story is complete, `.claude/agent-memory/software-engineer/dispatch-git-gotchas.md` no longer prescribes a remedy for a mechanism that does not exist. The passage currently tells the reader to raise a `DENY_AT` threshold and describes a hard `SendMessage` deny — the operator removed both by hand at `c990446`, and E-279-02 deletes the hook outright. What replaces that advice is software-engineer's call, not a mechanical strike.

## Context
This is its own story rather than an acceptance criterion inside E-279-02, and the reason is an ownership rule rather than sizing.

`.claude/rules/context-layer-assessment.md` (Learning-Loop Lifecycle → Deletion-Side Eviction → Ownership) reserves each agent's memory directory to that agent: whoever runs the deletion-side sweep "MAY read ANY dir to IDENTIFY hits and report them as the closure seed, but only the owning agent edits its own content." **Dispatch assigns stories, not criteria.** So an SE-owned criterion inside claude-architect's story either puts two implementers on one story or puts claude-architect over the ownership line. claude-architect raised this as a positive objection on 2026-07-28 and PM adopted it.

**Why this became a judgement call, which is the part worth understanding before editing.** While the telemetry disposition was still open, this was arguably a numbers correction — the file cites `DENY_AT=60` and `WARN_AT=40`, which are simply wrong. Under the DELETE ruling the entire hard-send-cap subsection loses its referent, while the surrounding material about `SendMessage` receipts lying in both directions stays true and independently valuable. Deciding what survives that cut is a judgement about software-engineer's own memory, which is exactly the class the rule reserves.

## Acceptance Criteria
- [ ] **AC-1** (the dead remedy is gone): In `.claude/agent-memory/software-engineer/dispatch-git-gotchas.md`, the passage at approximately lines 169-177 no longer prescribes "raising `DENY_AT`", and no longer describes a hard `SendMessage` deny at `DENY_AT=60` / `WARN_AT=40` or any other threshold, as a live mechanism. **RED state:** any surviving sentence that instructs a reader to act on a send threshold. Verify by grep that `DENY_AT`, `WARN_AT`, and `sends.count` appear nowhere in the file except inside explicitly dated historical framing.
- [ ] **AC-1b** (the SECTION HEADING carries the retired predicate, and no grep token reaches it): The heading at approximately `:169` currently reads **"## A `SendMessage` receipt lies in BOTH directions, and there is a hard send cap."** Its **second clause must go**; its **first clause must survive** (AC-2 protects it). After the edit the heading asserts nothing about a send cap.
  - **This is named explicitly because it is the single most likely miss in the file, and it sits exactly on the AC-1/AC-2 boundary.** AC-1's grep tokens (`DENY_AT`, `WARN_AT`, `sends.count`) **do not appear in the heading at all**, so a token-driven pass clears the body and leaves the title asserting a mechanism that no longer exists. AC-4 covers it in principle — a title carrying a retired claim in none of its words is the characteristic failure `.claude/rules/doc-sweep.md` names — but naming it costs one clause and closes the likeliest gap. **RED state:** the body reconciled while the heading still says "and there is a hard send cap."
- [ ] **AC-2** (the still-true material survives): The `SendMessage` receipt-lies-in-both-directions material in the same section is present and unweakened after the edit. It is independently true, has nothing to do with the counter, and was demonstrated repeatedly during this very session. **RED state:** this material removed or softened as collateral. Verify by diff.
- [ ] **AC-3** (the replacement is authored, not merely deleted): The passage currently instructs the reader to "stop and surface it." With nothing left to surface, software-engineer states what a reader should do instead, or records that no action replaces it. **This is software-engineer's judgement and MUST NOT be pre-empted by another agent.** An edit that deletes the instruction and leaves a gap fails this criterion; so does one that leaves a dangling "surface it" with no referent.
- [ ] **AC-4** (no claim about the hook survives anywhere in the file): Sweep the whole file — not only the 169-177 region — for `.dispatch-log`, `sends.count`, `rounds`, the TSV, and the "rides the closure patch" assertion, plus any *judgement* that rested on the telemetry being readable. Per `.claude/rules/doc-sweep.md`, a retired claim survives in forms carrying none of its tokens, so enumerate what would have been written differently had the mechanism never existed. Every surfaced line gets a written verdict, "no change needed" included.
  - **Expect false positives on `rounds`, and disposition them rather than editing them.** The token has an unrelated ordinary-English use in this file — approximately `:176` reads "several review **rounds**" — which has nothing to do with the TSV's never-produced `rounds` column. It earns a written "no change needed." This is the same over-match shape as E-279-02 AC-3's `archived-epics.md:85` worked example: the sweep tokens over-match by design, an over-match arrives visibly, and the verdict is the deliverable — never a reflex edit.

## Technical Approach
Read epic TN-13 for the deletion scope and `.claude/rules/doc-sweep.md` before editing — this is a retirement sweep, and its characteristic failure is a title, rating, or summary line that carries the retired claim without any of its words.

The hook file will be gone by the time this story runs (E-279-02), so cite it as dated evidence-of-what-was rather than as a live pointer. The operator's own retirement note recorded the removed values as 40 and 60, which is a third set of numbers matching neither this file nor E-271's research file — a detail worth stating precisely rather than approximating.

**Own-memory carve-out:** software-engineer edits this file directly. claude-architect may read it to identify hits and may report them, but does not edit it (`.claude/rules/agent-routing.md` Routing Precedence; `.claude/rules/context-layer-assessment.md` Ownership).

## Dependencies
- **Blocked by**: E-279-02. Reconciling before the hook is deleted would have software-engineer writing against an interim state that story 02 then removes.
- **Blocks**: None.

## Files to Create or Modify
- `.claude/agent-memory/software-engineer/dispatch-git-gotchas.md` (modify)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] No regressions in existing tests

## Notes
Source: epic TN-13 item 4 and the 2026-07-28 claude-architect objection recorded in the epic's Dispatch Team section. The lesson this story carries forward is the one the ownership rule encodes: a sweep may find a hit in anyone's memory, but only the owner may decide what replaces it.
