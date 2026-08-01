# E-279-05: Reconcile software-engineer memory to the deleted hook

## Epic
[E-279: Closure machinery](../E-279-closure-machinery/epic.md)

## Status
`DONE`

## Description
After this story is complete, `.claude/agent-memory/software-engineer/dispatch-git-gotchas.md` no longer prescribes a remedy for a mechanism that does not exist. The passage currently tells the reader to raise a `DENY_AT` threshold and describes a hard `SendMessage` deny — the operator removed both by hand at `c990446`, and E-279-02 deletes the hook outright. What replaces that advice is software-engineer's call, not a mechanical strike.

## Context
This is its own story rather than an acceptance criterion inside E-279-02, and the reason is an ownership rule rather than sizing.

`.claude/rules/context-layer-assessment.md` (Learning-Loop Lifecycle → Deletion-Side Eviction → Ownership) reserves each agent's memory directory to that agent: whoever runs the deletion-side sweep "MAY read ANY dir to IDENTIFY hits and report them as the closure seed, but only the owning agent edits its own content." **Dispatch assigns stories, not criteria.** So an SE-owned criterion inside claude-architect's story either puts two implementers on one story or puts claude-architect over the ownership line. claude-architect raised this as a positive objection on 2026-07-28 and PM adopted it.

**Why this became a judgement call, which is the part worth understanding before editing.** Under the DELETE ruling the entire hard-send-cap subsection loses its referent, while the surrounding material about `SendMessage` receipts lying in both directions stays true and independently valuable. Deciding what survives that cut is a judgement about software-engineer's own memory, which is exactly the class the rule reserves.

⚠️ **CORRECTED 2026-08-01 — do not restore the struck sentence.** This paragraph previously read: *"While the telemetry disposition was still open, this was arguably a numbers correction — the file cites `DENY_AT=60` and `WARN_AT=40`, which are simply wrong."* **The numbers were CORRECT for the mechanism as it stood** (`c990446` removed `WARN_AT=40` and `DENY_AT=60`; the retirement note it added records the same pair). The *"simply wrong"* verdict belongs to **E-271-03's AC** (`DENY_AT=25` / `WARN_AT=15`) and drifted onto this file — see epic TN-8b and the epic's Dispatch Team correction. **The judgement-call conclusion above stands on the DELETE ruling alone and never needed the struck premise.**

## Acceptance Criteria
- [ ] **AC-1** (the dead remedy is gone): In `.claude/agent-memory/software-engineer/dispatch-git-gotchas.md`, the passage at approximately lines 169-177 no longer prescribes "raising `DENY_AT`", and no longer describes a hard `SendMessage` deny at `DENY_AT=60` / `WARN_AT=40` or any other threshold, as a live mechanism. **RED state:** any surviving sentence that instructs a reader to act on a send threshold. Verify by grep that `DENY_AT`, `WARN_AT`, and `sends.count` appear nowhere in the file except inside explicitly dated historical framing.
- [ ] **AC-1b** (the SECTION HEADING carries the retired predicate, and no grep token reaches it): The heading at approximately `:169` currently reads **"## A `SendMessage` receipt lies in BOTH directions, and there is a hard send cap."** Its **second clause must go**; its **first clause must survive** (AC-2 protects it). After the edit the heading asserts nothing about a send cap.
  - **This is named explicitly because it is the single most likely miss in the file, and it sits exactly on the AC-1/AC-2 boundary.** AC-1's grep tokens (`DENY_AT`, `WARN_AT`, `sends.count`) **do not appear in the heading at all**, so a token-driven pass clears the body and leaves the title asserting a mechanism that no longer exists. AC-4 covers it in principle — a title carrying a retired claim in none of its words is the characteristic failure `.claude/rules/doc-sweep.md` names — but naming it costs one clause and closes the likeliest gap. **RED state:** the body reconciled while the heading still says "and there is a hard send cap."
- [ ] **AC-2** (the still-true material survives): The `SendMessage` receipt-lies-in-both-directions material in the same section is present and unweakened after the edit. It is independently true, has nothing to do with the counter, and was demonstrated repeatedly during this very session. **RED state:** this material removed or softened as collateral. Verify by diff.
- [ ] **AC-3** (the replacement is authored, not merely deleted): The passage currently instructs the reader to "stop and surface it." With nothing left to surface, software-engineer states what a reader should do instead, or records that no action replaces it. **This is software-engineer's judgement and MUST NOT be pre-empted by another agent.** An edit that deletes the instruction and leaves a gap fails this criterion; so does one that leaves a dangling "surface it" with no referent.
- [ ] **AC-4** (no claim about the hook survives anywhere in the file): Sweep the whole file — not only the 169-177 region — for `.dispatch-log`, `sends.count`, `rounds`, the TSV, and the "rides the closure patch" assertion, plus any *judgement* that rested on the telemetry being readable. Per `.claude/rules/doc-sweep.md`, a retired claim survives in forms carrying none of its tokens, so enumerate what would have been written differently had the mechanism never existed. Every surfaced line gets a written verdict, "no change needed" included.
  - **Expect false positives on `rounds`, and disposition them rather than editing them.** The token has an unrelated ordinary-English use in this file — approximately `:176` reads "several review **rounds**" — which has nothing to do with the TSV's never-produced `rounds` column. It earns a written "no change needed." This is the same over-match shape as E-279-02 AC-3's `archived-epics.md:85` worked example: the sweep tokens over-match by design, an over-match arrives visibly, and the verdict is the deliverable — never a reflex edit.
- [ ] **AC-5** (the auto-loading INDEX no longer asserts the mechanism is live) — **ADDED 2026-08-01 by PM ruling; see the scope note below for why this is a correction and not a widening.** `.claude/agent-memory/software-engineer/MEMORY.md` contains no clause presenting a hard `SendMessage` cap as a current control. The line at approximately `:41` reads, in part, *"a hard `SendMessage` cap (`DENY_AT=60` per staging boundary) is an OPERATOR decision point — surface it, never route around it"*. **RED state:** any surviving text in `MEMORY.md` that a reader would act on as a live threshold. Replace the clause with a dated retirement pointing at this topic file's tombstone.
  - ⚠️ **The clause to strike and a live clause share ONE LINE. A line-level edit destroys the half that must survive.** The same `:41` entry continues *"and a send receipt lies BOTH ways: success ≠ delivered, and denied ≠ not delivered (E-278-04 hit both in one story; only comparing CONTENT settled it)"* — that is independently true and stays. **Edit the clause, not the line.** This is the disposition standard `:53` states in its own words: ***"Reconcile-not-strike: a hit is a candidate for eviction, not an automatic strike; preserve still-valid guidance."***
    - **Precision note, because the first draft of this bullet mis-cited its own protection.** It said *"the material AC-2 protects"*. **AC-2 does not reach this line** — AC-2 is scoped to the receipt material *in the topic file's section*. The `MEMORY.md` sentence is a **second copy** of that guidance in a different file, and **AC-5 is what protects it**. A reviewer verifying AC-2 will be reading `dispatch-git-gotchas.md` and would never look here.
  - **Why the index and not only the topic file:** `MEMORY.md` **auto-loads into software-engineer's system prompt every session**; the topic file is the one a reader has to go looking for. An index row still asserting what its own topic file has retracted is the named shape at `.claude/rules/doc-sweep.md:35`, and leaving it would put E-279 in direct violation of its own Success Criterion — *"no committed file is left asserting that it works."*

## Technical Approach
Read epic TN-13 for the deletion scope and `.claude/rules/doc-sweep.md` before editing — this is a retirement sweep, and its characteristic failure is a title, rating, or summary line that carries the retired claim without any of its words.

The hook file will be gone by the time this story runs (E-279-02), so cite it as dated evidence-of-what-was rather than as a live pointer.

⚠️ **CORRECTED 2026-08-01 — the struck sentence was DIRECTIVE, which is why it is the most dangerous of the three.** It read: *"The operator's own retirement note recorded the removed values as 40 and 60, which is a third set of numbers matching neither this file nor E-271's research file — a detail worth stating precisely rather than approximating."* **It instructed the implementer to state a falsehood precisely.** The note's `{40, 60}` matches **this file exactly**; there are two sets, not three (`{40, 60}` = hook, note, this memory file; `{15, 25}` = E-271-03's AC and E-271's research file). **The sentence was also self-refuting on its own text** — it asserted the note reads 40/60 while the paragraph above asserted this file cites 60/40, then claimed the two do not match. **That contradiction was decidable from the story file alone, with no git access, and nobody decided it.**

**What to state instead:** the removed values were `WARN_AT=40` / `DENY_AT=60`, this file recorded them correctly, and they died with the mechanism rather than because they were wrong.

**The hook had THREE vintages** — `15/25` (E-256 placeholder) → `40/60` (operator, `dc1cc9e`) → deny retired (`c990446`) → deleted (E-279-02). **E-271-03's AC was correct when written and went STALE**, rather than being wrong; see the epic's Dispatch Team correction for the verification. Stating it as *"the AC was wrong"* would replace one false claim with another.

**Own-memory carve-out:** software-engineer edits this file directly. claude-architect may read it to identify hits and may report them, but does not edit it (`.claude/rules/agent-routing.md` Routing Precedence; `.claude/rules/context-layer-assessment.md` Ownership).

## Dependencies
- **Blocked by**: E-279-02. Reconciling before the hook is deleted would have software-engineer writing against an interim state that story 02 then removes.
- **Blocks**: None.

## Files to Create or Modify
- `.claude/agent-memory/software-engineer/dispatch-git-gotchas.md` (modify)
- `.claude/agent-memory/software-engineer/MEMORY.md` (modify) — **ADDED 2026-08-01, PM ruling. This is a CORRECTION of an under-specified list, not a widening of scope.**

⚠️ **The scope ruling, recorded because a later reader will otherwise read it as diff creep.** `se-e279` surfaced the `MEMORY.md:41` hit and deliberately did **not** self-authorize the edit — the Files list named one file and AC-4 was scoped *"anywhere in the file"* (singular). Ownership was never in question; it is software-engineer's own directory. **Scope was, and scope is PM's call** (`.claude/rules/agent-routing.md`, Decision Routing → work definition / acceptance criteria / story scope).

**Ruled: in scope, because the governing rule already required it and this list simply failed to say so.** `.claude/rules/context-layer-assessment.md:53` (Deletion-Side Eviction) requires sweeping *"every agent's own `.claude/agent-memory/<agent>/` directory -- the `MEMORY.md` index AND its topic files, not just the index"* — verified verbatim on disk before ruling. The story therefore always covered this file; only its Files list was short. **E-259's lesson was that index-only sweeps ship false-cleans; this is the inverse — a topic file reconciled while its index still asserts the retired mechanism — and it is the same defect.**

**The stronger half of that citation, added after `se-e279` pointed it out.** `:53`'s decisive clause is not the one first quoted but *"and for each **CLAIM it RETIRED**, which no identifier grep reaches"* — and a retired claim is exactly what `MEMORY.md:41` carries. The identifier-grep framing understates the case: **this hit would still be in scope if the string `DENY_AT` appeared nowhere in it.**

⚠️ **A THIRD path was raised (`se-e279`, via main) and REJECTED AS A SUBSTITUTE while ADOPTED AS A COMPLEMENT. Read this before proposing it again.** `context-layer-assessment.md:55` obliges an agent **on the dispatch team** to reconcile its **own dir** at closure, edits riding the closure patch — software-engineer is on the Dispatch Team (`epic.md` Dispatch Team section), so the proposal was to let `:55` close this at Step 8 sub-step 3 and leave the Files list alone.
- **It was offered as dissolving the scope question. It does not — it answers a DIFFERENT one, and the two are not alternatives.** `:55` binds regardless of what this story says; adopting AC-5 does not repeal it. So the real choice was never *"story or closure"* but *"which known hits are reviewed."*
- **REJECTED as a substitute on REVIEW COVERAGE, which is the whole difference.** The sub-step 3 authoring window falls **after the last story review**: closure-window writes ride the operator's diff but no code-reviewer gates them and no AC covers them. This edit is a **compound-clause rewrite where half must survive** — precisely the kind that benefits from a reviewer.
- **The governing discriminator, stated so it is reusable: a CLOSURE OBLIGATION is for work whose SCOPE cannot be known until closure. This work's scope is fully known NOW** — one identified line, one rewrite. E-279's four gate-blocking sites are genuinely closure-class because the set of blocking sites is not closed until closure; this is not that. **Deferring known, reviewable work into an unreviewed window trades review coverage for nothing.**
- **A second cost, specific to this epic:** sub-step 3 is where the ordering hazard already lives — *a sweep run before the last artifact certifies a tree that no longer exists.* Loading more content into that window increases exactly the risk this epic is managing.
- **ADOPTED as a complement:** `:55` governs the **residual** directory sweep (see the closure obligation in Notes). AC-5 takes the one known hit into the reviewed story; `:55` takes whatever the sweep turns up. **Both, covering different things — strictly stronger than either alone.**

**It also gates the epic, which is why it could not be deferred to an idea.** Epic Success Criterion: *"no committed file is left asserting that it works."* Left as-is, E-279 ships a committed, **auto-loading** file asserting a hard send cap is live. A follow-up idea would satisfy nobody — *"a flag that lives only in a completion report reaches nobody"* is this epic's own recorded rejection of that move.

**Bound on this ruling — it covers software-engineer's OWN directory only.** Hits in any other agent's memory dir are NOT in this story: the ownership clause reserves each dir to its owner, and this story has one owner. Those are a **closure obligation** (see Notes).

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] No regressions in existing tests

## Notes
Source: epic TN-13 item 4 and the 2026-07-28 claude-architect objection recorded in the epic's Dispatch Team section. The lesson this story carries forward is the one the ownership rule encodes: a sweep may find a hit in anyone's memory, but only the owner may decide what replaces it.

⚠️ **CLOSURE OBLIGATION opened 2026-08-01 by the AC-5 ruling — NOT part of this story, and it does not block it.** The Success Criterion says *"no **committed file**"*, which is wider than one agent's directory: `context-layer-assessment.md:53` scopes the deletion-side sweep to `.claude/rules/`, `.claude/agents/`, `CLAUDE.md`, **and every agent's memory dir**. The `MEMORY.md` hit was found only because software-engineer happened to be reading its own index — **nobody has swept the other five agents' directories for a live send-cap claim, and an unswept dir is an unknown, not a clean.**

**Disposition — `context-layer-assessment.md:55` supplies the mechanism, so this does not need inventing.** Verbatim: *"Each agent's memory dir is reconciled by the OWNING agent. An agent ON the dispatch team reconciles its own dir at closure (its edits ride the closure patch); a hit in the dir of an agent NOT on the team is flagged by the main session as a follow-up sweep. Whoever runs the deletion-side sweep ... MAY read ANY dir to IDENTIFY hits and report them as the closure seed, but only the owning agent edits its own content."* Applied here:
- **Identification** may be run by anyone and is the cheap half — one reader, every dir.
- **On-team owners repair their own dirs at Step 8 sub-step 3**, riding the closure patch: claude-architect and software-engineer (Dispatch Team), plus product-manager and code-reviewer, who are on the team operationally as dispatch infrastructure and can write in the worktree. **`:55`'s rationale is that the writer must be the owner, and that is satisfied for all four.**
- **Off-team owners** — baseball-coach, api-scout, data-engineer, docs-writer, ux-designer — are a **main-session follow-up sweep** under `:55`'s own clause, NOT an E-279 closure blocker. **This bound matters: without it the Success Criterion reads as requiring edits to five dirs nobody on this team may touch.**
- **software-engineer's residual dir sweep is `:55`-obligated independent of AC-5** — AC-5 takes the one known hit into the reviewed story; `:55` takes anything else the sweep finds.

**PM owns the sweep's completeness and PM's own dir.** Recorded here rather than in a completion report for the reason this epic already gives: a flag that lives only in a completion report reaches nobody.
