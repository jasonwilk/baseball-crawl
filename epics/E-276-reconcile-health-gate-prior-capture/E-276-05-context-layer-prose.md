# E-276-05: Correct the Context-Layer Prose the Fix Falsifies

## Epic
[E-276: Reconcile-at-Load Health Gate — Capture the Prior Set Before the Run's Own Writes](epic.md)

## Status
`TODO`

## Description

After this story is complete, no context-layer file still states the claims this epic's fix falsifies. CLAUDE.md's reconcile-at-load bullet describes the shipped behaviour instead of a defect in flight, and the claude-architect codification record's refuted "benign" ruling is corrected in place rather than left standing as a judgment the evidence has overturned.

## Context

Two context-layer files carry claims about this seam that the fix makes false. One is a known-defect notice written while the fix was still in flight; the other is subtler and more instructive.

`.claude/agent-memory/claude-architect/epic-codifications.md` identified this exact mechanism at E-267 closure — it correctly worked out that the prior set is `old ∪ fresh` — and then ruled it **"benign, since dedup would have merged the rows anyway."** The audit refutes that by execution: nine lines hard-deleted. SE gave three independent reasons the assessment is wrong in general, and they are in the epic's Background; the first is decisive on its own, because the retire runs *before* the dedup sweep by explicit design, so dedup cannot have merged anything yet.

The same file pins the health-gate invariant as "numerator and denominator drawn from the SAME population". That statement is **true of the broken code** — both sides are drawn from the polluted set. It needs the temporal clause and, per the epic's TN-10, the necessary-but-not-sufficient note, or a future reviewer concludes "same population, therefore sound" and passes the same defect again.

**⚠️ TN-10's wording CHANGED after this story was first written, and AC-2 / AC-2b / AC-5 bind it verbatim.** The version drafted during the conjunction design described the gate as *"a conjunction of two gates over two different populations"* and named a live legacy conjunct. **The conjunction does not ship.** The current TN-10 text describes one gate per grain, notes that roster has none, and keeps **both** load-bearing halves — the temporal clause and the necessary-but-not-sufficient note. **Read TN-10 fresh rather than from any cached copy of it**, and carry the current text.

This story is sequenced **last** so the prose describes what shipped rather than what was planned.

## Acceptance Criteria

- [ ] **AC-1**: CLAUDE.md's "KNOWN DEFECT (2026-07-25 audit, fix in flight)" paragraph — inside the **Canonical reconcile-at-load (retire-absent)** Architecture bullet — is replaced with a description of the shipped behaviour. The replacement states the corrected gate population, and does **not** leave a reader instructed to distrust a gate that now works.

- [ ] **AC-2**: The replacement paragraph carries the necessary-but-not-sufficient formulation from Technical Notes TN-10, not only the temporal clause. Per TN-10 the sufficiency note is the transferable part: the clause fixes this instance, the note is what stops the next reviewer accepting a same-population argument as proof of soundness.

- [ ] **AC-2b (the second copy, in the same bullet — this is the one a paragraph-scoped edit misses)**: The **same** CLAUDE.md reconcile-at-load bullet contains a second statement of the falsified invariant — *"the health-gate ratio's numerator and denominator MUST be drawn from the same population"* — outside the KNOWN-DEFECT paragraph AC-1 replaces. It MUST be brought to TN-10's necessary-but-not-sufficient wording, **not merely deleted**: the sentence is not false, it is insufficient, and deleting it removes a real invariant instead of completing it.

      **Why this is called out rather than left to AC-6's sweep**: AC-1 is scoped to a *paragraph*, and this copy sits two paragraphs away inside the same bullet — close enough that an editor working on AC-1 has it on screen, and far enough that a paragraph-scoped edit steps over it. A retired claim surviving in the same bullet as its own replacement, in the file every session loads, is the worst possible resting place for it.

- [ ] **AC-3**: The replacement is accurate about **all three** grains, **which no longer means describing one design three times.** The defect was live at game, player-line and roster; a paragraph naming only the two the original handoff covered would be a fresh false claim in the same sentence position as the one being corrected. What shipped is:

      - **game and player-line** — the **corrected gate alone**, computing the floor ratio over the pre-upsert snapshot population. The legacy live-population gate is replaced, not conjoined.
      - **roster** — **no floor gate at all.** `permit = (fresh payload non-empty) AND (|absent ∩ previously| ≤ MAX_ROSTER_DEPARTURES)`. The cap is the **sole** guard.

      **⚠️ The roster grain ends this epic with LESS gating than it started with, deliberately, on an operator ruling to invert the bias on that grain.** A CLAUDE.md paragraph that describes the fix as "the gate now reads its prior correctly on all three grains" would be **false on roster** — there is no gate there to read anything. **Do not smooth the three grains into one sentence**; the asymmetry is the design, and the discriminator (`W ⊆ fresh` holds on two grains and fails on the third) is what makes it principled rather than arbitrary.

- [ ] **AC-4**: In `.claude/agent-memory/claude-architect/epic-codifications.md`, the E-267 entry's **"benign, since dedup would have merged the rows anyway"** ruling is corrected in place, recording that it was refuted by execution and why — ordering being the decisive reason, per the epic's Background. The entry's surrounding record of what was codified stays intact; this corrects a judgment, it does not rewrite history.

- [ ] **AC-5**: In the same file, the pinned "same population" invariant in the E-267 T1/T2 bullet is brought to the corrected wording per TN-10.

- [ ] **AC-6 (residue sweep, per `.claude/rules/doc-sweep.md`)**: A retirement sweep is run for the falsified claims across `CLAUDE.md`, `.claude/rules/`, and `.claude/agent-memory/`, covering all three steps — token grep, synonym expansion, and a semantic read of the touched sections. Because this is a **retirement**, the synonym step MUST enumerate the *judgements that depended on the claim* — ratings, priorities, and risk adjectives that share none of its words — not merely rephrasings. Report what was found and what was left alone, with reasons.

      **⚠️ WHERE THE REPORT GOES: `.project/research/E-276-residue-sweep.md`, a DURABLE FILE on this story's Files list.** *(Undefined originally; answered "the completion report to PM" at the second Codex pass; **corrected to a file at the third pass, which was right and I was wrong** — see below.)* The report is written there, and PM verifies AC-6 and AC-9 by opening it.

      **⛔ WHY THE EARLIER "COMPLETION REPORT TO PM" ANSWER WAS WRONG, recorded because I chose it deliberately and it does not survive this epic's own rule.** A completion report is **ephemeral agent output**. It is available to PM during dispatch and to nobody afterwards — so an AC verifiable only against it is verifiable only *once*, by one party, in one session, and whoever re-checks this story at closure, at archive, or in six months **has nothing to open.** This epic already has the governing rule and it is TN-16's: **"a construction that exists only in a transcript is not a regression test."** A residue sweep that exists only in a completion message is not a sweep record, for exactly the same reason. **I applied that rule to test constructions and then failed to apply it to the verification artifact for a doc sweep, one pass later.**

      *(Codex's supporting detail at the second pass was imprecise — it said the Files list names "only itself"; it named two files — but the finding was right both times, and the third pass sharpened it to the point that identified my error. **A verdict can be right on an imprecise premise; two independent passes landing on the same AC is the signal, not the premise quality.**)*

      **⚖️ THE RULING, WITH WHAT IT REJECTED — recorded because the losing case is genuinely good and a future editor will re-propose it.** The question: *must a sweep whose whole product is "what I found and deliberately left alone" survive the session that produced it?*

      **AGAINST a durable artifact (the rejected case, stated at full strength):** the project's **simple-first** principle is the house rule and it points this way; **every other story in this epic reports through its completion report** and none needs a file; and a per-story artifact is **real weight** in an epic already criticised for its size. **If the report were only categories (i) — things corrected — this case would win outright**, because a correction is verifiable from the diff and the report merely narrates it.

      **FOR, and it is category (iii) that decides it:** a **flagged-not-edited** entry is not a narration of work done, it is a **standing obligation on an agent who is not on this team.** [[IDEA-187]] is the live instance and its own resolution trigger is *"the next time data-engineer is spawned for any reason"* — which may be weeks out, long after this session's output is gone. **An obligation recorded only in a completed session's transcript is an obligation on nobody.** Category (ii) — *left alone deliberately, with reason* — is the second-strongest: it is the only record distinguishing a considered preservation from an unexamined hit, and it is precisely what a re-opener six months on needs and cannot reconstruct.

      **The deciding asymmetry**: the cost of the file is one small artifact; the cost of no file is that the two categories carrying **forward obligations** evaporate silently, and nothing signals they did. **That is this epic's own subject** — a requirement that quietly stops existing.

      **`.project/research/` rather than the epic directory** is part of the ruling, not incidental: the epic is **archived at closure**, and the obligation outlives the epic. **A durable artifact filed in a directory that gets archived would satisfy the letter of this AC and lose the reason for it.**

      **The report MUST distinguish three outcomes, not two**, or "left alone" silently merges a deliberate preservation with an unexamined hit: **(i) CORRECTED** (in a file this story owns), **(ii) LEFT ALONE DELIBERATELY** with the reason (still-valid guidance, a finding-record, or a preservation copy — `.claude/rules/context-layer-assessment.md`'s reconcile-not-strike), and **(iii) FLAGGED, NOT EDITED** because the file belongs to another agent (AC-9's IDEA-187 case is the known instance).

      **If the sweep finds a hit needing correction in a file NOT on this story's Files list, it is category (iii) — flag it, do not edit it, and do not silently widen the file list.** That is a finding for PM to route, and it is the same boundary AC-9 draws for one known file, generalized to any the sweep turns up.

- [ ] **AC-7**: Every symbol, path, and heading cited in the new prose resolves against the repo, per `.claude/rules/tool-output-integrity.md`. Citations are by **stable anchor** — symbol, function, or heading — never by line number.

- [ ] **AC-9 (a known hit that this story must FLAG and MUST NOT EDIT)**: `.claude/agent-memory/data-engineer/health_gate_prior_set_must_be_temporal.md` carries **one** residual worth flagging, filed as **IDEA-187**: the file's per-grain shape (*"roster gets NO floor ratio at all"*) sits at **line 21 of 35, with four substantive sections below it**, while its rule, its **"Required wording"** and its recall-deciding `description:` frontmatter sit at the top **with no pointer down to it** — so a recall that stops at the description learns the rule and not its scope. Flag that, and nothing else in this file. **The flag is a pointer request, not a correction request**, and IDEA-187 records it as DE's call including "not worth it."

      **⛔ THIS AC PREVIOUSLY ASSERTED TWO FURTHER CLAIMS. BOTH WERE FALSE ABOUT THE COMMITTED FILE, AND FLAGGING EITHER WOULD MISDIRECT DE.** Corrected at the pre-dispatch amendment, 2026-07-25, after a full read of the file plus a second-channel grep:

      1. ~~"the health-gate invariant stated as though the temporal clause were the whole answer… where TN-10's current form keeps the temporal clause **and** the necessary-but-not-sufficient note"~~ — **INVERTED.** TN-10 attaches *necessary but NOT sufficient* to **same-population**, and calls **the temporal clause the load-bearing half**. The file's opening paragraph already states exactly that, near-verbatim, including TN-10's own `|fresh| >= |stale|` counterexample; the `description:` is correct in direction for the same reason. **Flagging this would have asked DE to move a sufficiency note onto the clause TN-10 does not put it on — introducing an inversion into a memory that does not have one.**
      2. ~~"the refuted one-population-over-four-sweep-bounds account of the divergence-count dispute"~~ — **DEFLATED.** That reading is the **artifact-of-bounds** account and is the **best-supported** one on the evidence (four-point exact fit `c(n) = (3n−2)(n−1)/2`). The one narrow claim that holds is that *"a colleague's independently-bounded sweep collapsed to the identical 3 shapes"* overstates independence. **Not worth a flag on its own.**

      **A third claim DOES hold and stays**: the file carries the *"a guard whose only protection is a second, **tunable** guard is not a guard"* wording — ancestor of story 03's *"independently-owned policy constant"*, and **retired residue** (the *"someone will tune the cap"* prediction was pre-registered as a falsifier and falsified). Flag it as residue, not as a discrepancy.

      **⚠️ Why this defect survived the final term sweep, which reported "not one was in an AC".** It carried **none of the eleven swept terms** — it is the structural blind spot that same sweep names one subsection later, landing this time on an **acceptance criterion** rather than on an Overview or a Goal. **The sweep's own reported scope was accurate and its conclusion did not transfer.**

      **⚠️ Do NOT characterise those claims as "the pre-conjunction form."** That phrasing measures the file against a design that **does not ship**, and it was itself stale text in this story until the sweep caught it. The baseline is the **current** TN-10, one gate per grain.

      **It is data-engineer's own memory directory, and data-engineer is not on this epic's Dispatch Team.** Per the ownership clause in the Learning-Loop Lifecycle (`.claude/rules/context-layer-assessment.md`) and the own-memory carve-out in `.claude/rules/agent-routing.md`, the agent running the sweep MAY read any directory to identify hits but **only the owning agent edits its own content**. So this AC is satisfied by recording the hit as an AC-6 **category (iii) — FLAGGED, NOT EDITED** — entry in **`.project/research/E-276-residue-sweep.md`** (see AC-6 for the destination and the three categories), and confirming the file was left unmodified. **Editing it fails this AC.**

      **⛔ THE POSITION CLAIM WAS WRONG AND THE WAY IT WAS WRONG IS THE FINDING.** This AC and IDEA-187 both said *"last third"* / *"bottom."* The paragraph is at **line 21 of a 35-line file** — just past the midpoint. **The substantive claim is unaffected** (there is genuinely no pointer down from the top-of-file rule, the "Required wording", or the `description:`), **but two artifacts agreed on a false detail because one was derived from the other, not because two people checked.** Agreement between an artifact and something written from it is not corroboration — the same trap recorded at the ideas-index repair, where index and file agreed and both were wrong. **Verify the position by opening the file, not by consulting its summary.**

      **The durable destination matters most for THIS entry.** A category-(iii) flag is a **handoff to an agent who is not on this team and may not be spawned for weeks** — IDEA-187 records the resolution as "the next time data-engineer is spawned for any reason." A flag that lives only in a dispatch-session message is a handoff to nobody.

      Stated as its own criterion rather than left to AC-6's judgment because the natural move on finding a stale claim mid-sweep is to fix it, and here that is a boundary violation rather than diligence. **A token grep will not surface the surviving residual either** — which is why it is named here explicitly instead of being left to the sweep to find.

      **⚠️ THE VERDICT ABOVE SURVIVES; ITS STATED REASON DID NOT, AND IS CORRECTED HERE** *(pre-dispatch amendment, 2026-07-25)*. It previously read: *"E-276 narrowed the invariant rather than deleting it, so the retired and surviving forms are near-homographs sharing most of their vocabulary."* **That reason belonged to the claims this AC no longer asks you to flag.** The residual that remains is a **missing cross-reference** — a correct rule at the top of a file with its per-grain scope at **line 21 of 35** and no pointer between them. **An absence is ungreppable for a simpler reason than homography: there is no string to match.** Recorded rather than silently swapped, because a correct verdict standing on a rotted reason passes every "was the call right?" check and is only caught by reopening the cited file — which is the failure this whole AC exists to record.

- [ ] **AC-8**: Archived epic files under `.project/archive/` are **not** modified. They are frozen historical records; the E-267 and E-270 archives carry the original claim and correctly continue to.

## Technical Approach

The full list of prose sites, with stable anchors, is Technical Notes TN-9. The corrected invariant wording is TN-10. The refutation of the "benign" ruling, with its three reasons in order of decisiveness, is in the epic's Background.

Two findings from PM's own sweep during discovery, so they are not re-derived:

`.claude/agent-memory/claude-architect/MEMORY.md`'s per-epic index line mentions the reconcile seam and its health gate but does **not** restate the false claim — the literal line was read and ruled clean. Re-check it, but the expected outcome is no change.

In-module prose in `src/` is **not** this story's scope. Those corrections ship inside the grain stories that change the behaviour, per the same-commit rule in `.claude/rules/tool-output-integrity.md` ("prose you author is a claim"). If a `src/` prose site is still stale when this story runs, that is a defect in the earlier story, not work to absorb here — report it.

Why this file set routes here: `CLAUDE.md` and `.claude/agent-memory/` are context-layer paths, so per the Routing Precedence in `.claude/rules/agent-routing.md` they route to claude-architect regardless of any other consideration. The claude-architect memory file is another agent's own directory from PM's perspective but is claude-architect's own, so this agent editing it is the own-memory case, not a cross-agent write.

## Dependencies
- **Blocked by**: E-276-01, E-276-02, E-276-03
- **Blocks**: None

## Files to Create or Modify
- `CLAUDE.md`
- `.claude/agent-memory/claude-architect/epic-codifications.md`
- `.project/research/E-276-residue-sweep.md` — **NEW.** The durable destination for AC-6's residue-sweep report and AC-9's category-(iii) flag. Added 2026-07-25 at the third Codex pass; without it AC-6, AC-9 and the Definition-of-Done line below are verifiable only against ephemeral agent output. **It lives in `.project/research/` rather than in the epic directory deliberately** — the epic is archived at closure, while the flag it carries is a handoff to data-engineer that outlives this epic.

## Agent Hint
claude-architect

## Handoff Context
- **Produces for**: nothing — this story is sequenced last and blocks no other.
- **Consumes from E-276-01/02/03**: the corrected invariant wording (TN-10) and each grain's shipped behaviour. The CLAUDE.md replacement must describe **all three** grains as they actually landed, which is why this story runs last rather than in parallel.
- **Reports back, does not fix**: any `src/` prose site still stale when this story runs is a defect in the earlier grain story (see Technical Approach), and `.claude/agent-memory/data-engineer/` is another agent's own directory (AC-9).

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Every cited symbol, path, and heading verified to resolve against the repo
- [ ] The doc-sweep residue check is **written to `.project/research/E-276-residue-sweep.md`**, in AC-6's three categories (corrected / left-alone-deliberately-with-reason / flagged-not-edited) — not merely performed, and not merely narrated in a completion message. **This line previously said only "is reported, not merely performed"**, which is why the destination gap survived: the DoD repeated the requirement without adding a target, so it read as a second check and was a second copy of the same ambiguity.
- [ ] No regressions in existing tests

## Notes

The general shape this epic produced is worth preserving in whatever form claude-architect judges right — it is more transferable than the specific defect:

**A mitigation named in prose, never executed, protecting a path it structurally cannot reach.** "Dedup would have merged the rows anyway" was written by someone who had correctly diagnosed the mechanism and then reasoned about a safety net without checking whether it was downstream of the harm. It was not.

And its companion, from TN-10: **an invariant that holds while the thing it guards is meaningless.** Same-population-on-both-sides was satisfied throughout. Four review layers read it, found it satisfied, and moved on.

**One case that is explicitly NOT part of that generalization, so it does not arrive here needing a rule it already has.** The epic's Background originally counted `crawl_is_authoritative`'s docstring — documented as "size of the fresh payload" while all three callers have passed the overlap since E-267 — as a third instance of the mechanism above. **It has been reclassified out.** It is a **stale contract**, and `.claude/rules/python-style.md` already carries that class along with the action it requires: *"when a contract changes, sweep the IDENTIFIER across the module graph, not the phrasing of the claim."* That rule found it.

The distinction is here rather than in the Background alone because this story is where the generalization gets codified, and **a three-instance pattern that silently includes a case an existing rule covers is how the context layer pays twice for one class** — a second rule, and a future reader having to work out which of the two applies. What should arrive here is two instances of a mechanism with no rule yet, and one case routed to the rule that has it.
