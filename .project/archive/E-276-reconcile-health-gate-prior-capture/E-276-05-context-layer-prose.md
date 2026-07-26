# E-276-05: Correct the Context-Layer Prose the Fix Falsifies

## Epic
[E-276: Reconcile-at-Load Health Gate — Capture the Prior Set Before the Run's Own Writes](epic.md)

## Status
`DONE` — 2026-07-26. All 9 ACs PM-verified. **Context-layer-only, so per the dispatch protocol PM verified alone**; per-story code review is skipped and the whole diff is picked up at the unconditional **Closure CR Integration Review**. The last of five stories.

**Two things this story produced that outlived it, both found by sweeping OUTSIDE its declared scope:**
1. **`docs/admin/operations.md` promises the opposite of what ships** — an operator-facing runbook stating a partial crawl *"never causes data loss"*, **false precisely where the operator inverted the bias**. TN-9 now carries a `docs/` row routed to **docs-writer at closure**. **This is the only defect the epic found that would have reached the OPERATOR rather than an agent, and Success Criterion 4 would have passed with it standing.**
2. **F-7** — a `src/` prose qualifier on `permit_empty_prior`, reported not fixed because it belongs to story 01, which was already DONE. Routed as a **closure remediation to software-engineer**, NOT a reopening.

**The scope widening in the Files list below was RATIFIED, not tolerated** — see its entry.

**⛔ THIS EPIC CORRECTED ITS OWN SPEC ~12 TIMES WHILE SHIPPING. Do not describe the design from the epic's Goals or from any story's Description — read the CODE and the Technical Notes banners.** Several ACs across stories 01–03 describe pre-correction states in passing; every one that mattered has a correction note beside it, and **the correction is the current text.**

**Three specific traps for this story**, all of which have already caught someone:
1. **Never write "all three grains now read their prior correctly."** The roster grain has **no gate at all** — the epic's own Goal 2 says so and AC-3 forbids the smoothed phrasing.
2. **TN-9 is the inventory, and it grew FOUR times during dispatch** — three of them found by a reviewer, not by a sweep. Read it as it now stands, including its **construction rule** and that rule's **stopping condition**.
3. **The `permit_empty_prior` sentence below is 0-for-2 and on its third version.** See the carried note.

**⛔ CARRY THIS INTO ANY `permit_empty_prior` PROSE — a sentence with a 0-for-2 record just got its third version, and code-reviewer flagged the third as STILL a shade strong** *(CR's observation, not a finding; recorded here 2026-07-26 so it does not evaporate between stories)*.

The shipped line reads *"the default protects the next one that does."* CR's point: for a **single-population live-fed caller, refusing and permitting are both harmless** — so the default does not *protect*, it **forces the next caller to choose explicitly.** That is the honest floor.

**Why this needs a stranger's eye rather than a quick edit**: this exact sentence has been **false twice, in opposite directions**, and both times it read as reasonable to whoever wrote it. **A third confident rewrite by someone close to it is the pattern, not the fix.** Check the mechanism before restating the claim, and if the weaker form is right, take the weaker form.

**Related, do NOT fold in**: [[IDEA-190]] proposes replacing this paragraph's guarantee with an executable caller-set pin. **Deliberately out of this epic** — it is a `tests/` file, and this story is context-layer prose routed to claude-architect.

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

      **The report MUST distinguish three outcomes, not two**, or "left alone" silently merges a deliberate preservation with an unexamined hit: **(i) CORRECTED** (in a file this story owns), **(ii) LEFT ALONE DELIBERATELY** with the reason (still-valid guidance, a finding-record, or a preservation copy — `.claude/rules/context-layer-assessment.md`'s reconcile-not-strike), and **(iii) FLAGGED, NOT EDITED** because the file belongs to another agent (AC-9's three flags on the data-engineer memory are the known instances — **only the first is IDEA-187**).

      **If the sweep finds a hit needing correction in a file NOT on this story's Files list, it is category (iii) — flag it, do not edit it, and do not silently widen the file list.** That is a finding for PM to route, and it is the same boundary AC-9 draws for one known file, generalized to any the sweep turns up.

- [ ] **AC-7**: Every symbol, path, and heading cited in the new prose resolves against the repo, per `.claude/rules/tool-output-integrity.md`. Citations are by **stable anchor** — symbol, function, or heading — never by line number.

- [ ] **AC-9 (known hits that this story must FLAG and MUST NOT EDIT)**: `.claude/agent-memory/data-engineer/health_gate_prior_set_must_be_temporal.md` carries **exactly three** residuals worth flagging, listed below. **Flag these three and nothing else in this file.** All three are of different kinds — a structural gap, a content residue, and a retired-prediction residue — and none is a licence to sweep the file generally.

      **⚠️ THIS AC PREVIOUSLY SAID "one residual … Flag that, and nothing else in this file" AND THEN SANCTIONED A SECOND ONE FOUR PARAGRAPHS LATER.** The count and the prohibition were both written before the third was found, and **the prohibition was the active harm**: an implementer following it literally would have suppressed a flag this AC now requires. Corrected at the R2–R5 red-team repairs, 2026-07-26. **A closed-set instruction ("and nothing else") has to be re-counted every time the set grows, and nothing in the sentence signals when it has** — the same shape as TN-13's count, falsified by an edit that never touched it.

      **FLAG 1 — the missing cross-reference (structural). Filed as [[IDEA-187]].** The file's per-grain shape — **the paragraph opening *"Where E-276 actually landed (corrected…)"***, which states *"roster gets NO floor ratio at all"* — sits **below the midpoint with several substantive sections beneath it**, while its rule, its **"Required wording"** and its recall-deciding `description:` frontmatter sit at the top **with no pointer down to it**. A recall that stops at the description learns the rule and not its scope. **The flag is a pointer request, not a correction request**, and IDEA-187 records it as DE's call including "not worth it."

      **📌 IDENTIFIED BY ITS OPENING WORDS, NOT BY COORDINATES — the form was changed because the values kept rotting.** *(As of 2026-07-26 it is **line 21 of 41**, recorded as dated evidence rather than as the address. IDEA-187 carries the identical wording; **both artifacts were changed in the same pass specifically so they cannot drift apart again**, which is the failure mode their earlier agreement already demonstrated.)*

      **⛔ THE DENOMINATOR ROTTED DURING THIS EPIC AND THE NUMERATOR DID NOT — a shape worth naming, because the obvious check passes.** This read **"line 21 of 35"** until 2026-07-26, when data-engineer legitimately appended to its own memory file (lines 29 and 31, both **below** the cited paragraph). PM re-verified line 23 and line 21 and both were byte-identical and correctly positioned — **and the file was 41 lines, not 35.** *(PM-VERIFIED by count, 2026-07-26.)*

      **An APPEND below a cited line invalidates a positional claim's DENOMINATOR while leaving its NUMERATOR correct.** So a check that asks *"is the cited line still where we said?"* — the natural check, and the one that was run — **passes**, while "of 35" silently becomes false. **A position stated as a fraction has two independently rotting halves, and verifying the interesting one certifies nothing about the other.** This is the third time this epic's positional claim about this same paragraph has been wrong, each time differently: first *"the bottom"*, then *"the last third"*, now a stale denominator.

      **⚠️ AND THE REPAIR ITSELF LEAKED, WHICH IS THE 10th MECHANISM ARRIVING ON SCHEDULE.** The stale denominator occurred in **four** places in this one AC. The first repair pass fixed **three** and missed the fourth — inside a paragraph that is *itself* a correction of an earlier wrong positional claim, so the sweep's own eye slid over it as already-handled. Caught by a follow-up grep for the literal `35`. **Enumerations drift downward-only: the site that RESTATES a value is rarely the site you are looking at when you fix it**, and a correction paragraph is the most camouflaged host of all, because it already reads as the place where this was dealt with.

      **⛔ THIS AC PREVIOUSLY ASSERTED TWO FURTHER CLAIMS. BOTH WERE FALSE ABOUT THE COMMITTED FILE, AND FLAGGING EITHER WOULD MISDIRECT DE.** Corrected at the pre-dispatch amendment, 2026-07-25, after a full read of the file plus a second-channel grep:

      1. ~~"the health-gate invariant stated as though the temporal clause were the whole answer… where TN-10's current form keeps the temporal clause **and** the necessary-but-not-sufficient note"~~ — **INVERTED.** TN-10 attaches *necessary but NOT sufficient* to **same-population**, and calls **the temporal clause the load-bearing half**. The file's opening paragraph already states exactly that, near-verbatim, including TN-10's own `|fresh| >= |stale|` counterexample; the `description:` is correct in direction for the same reason. **Flagging this would have asked DE to move a sufficiency note onto the clause TN-10 does not put it on — introducing an inversion into a memory that does not have one.**
      2. ~~"the refuted one-population-over-four-sweep-bounds account of the divergence-count dispute"~~ — **DEFLATED.** That reading is the **artifact-of-bounds** account and is the **best-supported** one on the evidence (four-point exact fit `c(n) = (3n−2)(n−1)/2`). The one narrow claim that holds is that *"a colleague's independently-bounded sweep collapsed to the identical 3 shapes"* overstates independence. **Not worth a flag on its own.**

      **FLAG 2 — the roster-exemption rationale, which restates BOTH framings this epic retires (content residue). NOT covered by IDEA-187** *(added at the R2–R5 red-team repairs, 2026-07-26; quoted from a clean read of the committed file)*. The file's line 23 reads:

      > **Why the roster grain is exempt — the reasoning, because the conclusion does not travel.** `team_rosters` is fully re-derivable from the roster crawl plus the jersey backfill, so **a wrong delete self-heals** while a wrong refusal compounds; **the operator ruled prefer-deleting on that basis.**

      Both emphasised halves are framings the epic **explicitly retires**, and each has a named counter-statement in the epic's own roster banner:

      1. *"a wrong delete self-heals"* — the banner reads *"**do NOT soften this to 'self-healing.'** V1's pre-existing loss is **permanent-while-broken, not self-healing**"*, because re-derivability is conditional on a subsequent healthy crawl and **sustained truncation has none** — the mechanism that would restore the row is the thing that is broken. That input is precisely the one the ruling turned on. *(The banner records that the team lead's own ruling used "self-healing" and that the artifact carries the corrected form — so this is a retirement the epic already had to make once.)*
      2. *"the operator ruled prefer-deleting on that basis"* — i.e. on re-derivability. The banner reads *"**re-derivability is NOT what carries the case, and leading with it over-claims in the very input the ruling turned on**"*. The load-bearing argument is **which-wrongness**: a wrong delete converges on the only evidence available, while a strand persists *against* evidence. Re-derivability is the **supporting** argument.

      A third, smaller point rides along: *"fully re-derivable"* is unqualified, and the banner's carve-out holds that **the row is re-derivable while the delete's downstream effect on the identity graph is not** — a delete collapsing a refused dedup fork triggers a merge in the same run, and a later crawl restores the roster row without un-merging the identity or restoring the merged-away stat row.

      **⛔ THIS IS A CLAUSE-LEVEL EDIT REQUEST, NOT A LINE-LEVEL STRIKE — AND BOTH WRONG MOVES ARE AVAILABLE** *(sharpened 2026-07-26 after DE-R1 re-read the file at PM's request; PM-VERIFIED by an independent read of lines 19-31, line 23 byte-identical and still at line 23)*. Line 23 is **two clauses of opposite status**, and whoever executes this at closure works from **this wording**, not from the conversation that produced it:

      - **RETIRED** — everything up to and including *"the operator ruled prefer-deleting on that basis"*: the re-derivability premise, the self-heals claim, and the attribution of the ruling to that basis.
      - **LIVE, and now independently corroborated** — everything from *"**Do NOT port this to `player_game_*`**"* onward.

      **Striking the sentence deletes live, load-bearing guidance. Keeping it intact preserves the retired premise. Name the split or one of those two happens.**

      **The LIVE half got stronger, not weaker.** DE's own new line 29 (added 2026-07-26, its own directory, legitimately) **measured that transfer failing**: on `player_game_*` a refused delete leaves the union of stale and fresh — *"18 rows / 54 AB, a permanent 2× inflation of the query-time season line"* — and states that the roster grain's *"grid clutter, never a corrupted stat"* residual **does not transfer, because here the retained row IS the corrupted stat.** The clause line 23 warns with is now backed by execution.

      **⚠️ AND THAT ADDITION CARRIES A COST DE NAMED AGAINST ITS OWN EDIT, which is why it belongs in the flag.** Fresh supporting evidence now sits adjacent to the retired clause, so a reader arriving at line 23 is **likelier to read the whole hit as accounted for** — `.claude/rules/doc-sweep.md`'s *"error hiding behind a legitimate neighbouring use"* shape. **The live half got harder to lose and the retired half got harder to see.**

      **✅ THE WARRANT IS STRONGER THAN "A RETIRED FRAMING SURVIVES", and the stronger form predates this session's edits: LINE 23 IS ALREADY REFUTED IN PLACE BY LINE 27 OF ITS OWN FILE.** Line 27 is the `MAX_ROSTER_DEPARTURES`-sets-a-**RATE**-not-a-bound material, ending *"**The protection runs backwards with respect to severity**"* — which is exactly what makes *"a wrong delete self-heals"* false. **Four paragraphs apart, in a 41-line file, with no cross-reference and no shared token**: line 27 never says "self-heal" or "re-derivable".

      **That is this project's doc-sweep rule running in REVERSE, and it is worth stating as its own shape.** The catalogued case is *a retired claim surviving in forms carrying none of its tokens*. Here it is **the REFUTATION carrying none of the claim's tokens** — so no grep for the retired claim can ever surface the sentence that kills it, and the contradiction sat unnoticed inside one short file. **Report FLAG 2 as "a sentence refuted by its own file, four paragraphs down, in a way no token search connects" — not as staleness.**

      **Scope, so this is not worded off a single hit** *[DE-R1's sweep of its own directory, reported before standing down]*: it swept for the retired claim's tokens **and** for token-free carriers (`self-heal`, `re-deriv`, `recoverable`, `restor`). **Line 23 is the ONLY carrier.** Every other hit is an unrelated domain or a different sense of the word, and **`MEMORY.md`'s index hook for this file does not carry the claim** — so the index-row position `.claude/rules/doc-sweep.md` warns about is clean here.

      **This remains a re-scoping request, not a challenge to the design.** The conclusion — roster is exempt, prefer-delete — is what shipped and is correct. Only the stated REASON is retired. Report it that way or DE reads it as a reopening.

      **Why this is a genuine SECOND item rather than part of FLAG 1**: IDEA-187 was deflated across two passes down to *"a cross-reference"*, and its surviving scope is **structural** — where the per-grain paragraph sits relative to the rule. **It says nothing about line 23's content**, and its Rough Timing describes E-276 as retiring "two claims that live in this file." **Do not file this under IDEA-187 on the assumption that it is covered; it is not.** Record it as its own category-(iii) entry in the sweep report and leave the filing decision to PM at closure — assigning it an idea number is not this story's call.

      **The transferable shape, which is this epic's own**: a **correct verdict resting on a retired reason** passes every "was the call right?" check, because the verdict is right. Only reopening the cited sentence catches it. `.claude/rules/tool-output-integrity.md` records exactly this, and `.claude/rules/doc-sweep.md` adds why a token grep will not find it: the retired claim survives here as *the justification for a decision*, sharing none of the vocabulary of the sentence that retired it.

      **FLAG 3 — retired-prediction residue.** The file carries the *"a guard whose only protection is a second, **tunable** guard is not a guard"* wording — ancestor of story 03's *"independently-owned policy constant"*, and **retired residue** (the *"someone will tune the cap"* prediction was pre-registered as a falsifier and falsified). Flag it as residue, not as a discrepancy.

      **⚠️ Why this defect survived the final term sweep, which reported "not one was in an AC".** It carried **none of the eleven swept terms** — it is the structural blind spot that same sweep names one subsection later, landing this time on an **acceptance criterion** rather than on an Overview or a Goal. **The sweep's own reported scope was accurate and its conclusion did not transfer.**

      **⚠️ Do NOT characterise ANY of these flags — or the two retired claims in the ⛔ block above — as "the pre-conjunction form."** That phrasing measures the file against a design that **does not ship**, and it was itself stale text in this story until the sweep caught it. The baseline is the **current** TN-10, one gate per grain.

      **It is data-engineer's own memory directory, and data-engineer is not on this epic's Dispatch Team.** Per the ownership clause in the Learning-Loop Lifecycle (`.claude/rules/context-layer-assessment.md`) and the own-memory carve-out in `.claude/rules/agent-routing.md`, the agent running the sweep MAY read any directory to identify hits but **only the owning agent edits its own content**. So this AC is satisfied by recording **all three flags** as AC-6 **category (iii) — FLAGGED, NOT EDITED** — entries in **`.project/research/E-276-residue-sweep.md`** (see AC-6 for the destination and the three categories), and confirming the file was left unmodified. **Editing it fails this AC.**

      **⛔ THE POSITION CLAIM WAS WRONG AND THE WAY IT WAS WRONG IS THE FINDING.** This AC and IDEA-187 both said *"last third"* / *"bottom."* The paragraph is at **line 21 of a 41-line file** — comfortably above the midpoint. *(It was **line 21 of 35** when this correction was written; the denominator moved on 2026-07-26 when DE appended below it. **Three wrong positional claims about one paragraph, each wrong differently** — see FLAG 1's denominator note.)* **The substantive claim is unaffected** (there is genuinely no pointer down from the top-of-file rule, the "Required wording", or the `description:`), **but two artifacts agreed on a false detail because one was derived from the other, not because two people checked.** Agreement between an artifact and something written from it is not corroboration — the same trap recorded at the ideas-index repair, where index and file agreed and both were wrong. **Verify the position by opening the file, not by consulting its summary.**

      **The durable destination matters most for THESE entries.** A category-(iii) flag is a **handoff to an agent who is not on this team and may not be spawned for weeks** — IDEA-187 records the resolution as "the next time data-engineer is spawned for any reason." A flag that lives only in a dispatch-session message is a handoff to nobody. **This binds hardest on FLAG 2, which has no idea file at all** — IDEA-187 does not cover it, so the sweep report is its *only* durable record until PM routes it at closure.

      Stated as its own criterion rather than left to AC-6's judgment because the natural move on finding a stale claim mid-sweep is to fix it, and here that is a boundary violation rather than diligence. **A token grep will not surface any of the three** — which is why each is named here explicitly instead of being left to the sweep to find. FLAG 1 is an **absence** (no string to match), FLAG 2 is a **justification** sharing none of the vocabulary of the sentence that retired it, and FLAG 3 is a **retired prediction** surviving as an adjective.

      **⚠️ THE VERDICT ABOVE SURVIVES; ITS STATED REASON DID NOT, AND IS CORRECTED HERE** *(pre-dispatch amendment, 2026-07-25)*. It previously read: *"E-276 narrowed the invariant rather than deleting it, so the retired and surviving forms are near-homographs sharing most of their vocabulary."* **That reason belonged to the claims this AC no longer asks you to flag.** **FLAG 1** — the residual this correction was written about — is a **missing cross-reference**: a correct rule at the top of a file with its per-grain scope at **line 21 of 41** and no pointer between them. **An absence is ungreppable for a simpler reason than homography: there is no string to match.** *(This paragraph is scoped to FLAG 1 and was written when it was the only one; FLAG 2 was added later and is ungreppable for a different reason, given above.)* Recorded rather than silently swapped, because a correct verdict standing on a rotted reason passes every "was the call right?" check and is only caught by reopening the cited file — which is the failure this whole AC exists to record.

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

- `.claude/rules/python-style.md` — **ADDED 2026-07-26, RATIFYING claude-architect's declared scope widening.** TN-9 assigns this row to story 05 and **Success Criterion 4 measures against TN-9**, but the row was added *after* this Files list was written — and **story 05 is LAST, so flagging rather than fixing would have left SC-4 structurally unsatisfiable.** CA read that correctly and made the edit as **SCOPE-IT, not delete**: the policy-hook carve-out and the EVIDENCE-versus-hook distinction survive untouched; only the "universal floor still applies underneath" reassurance is qualified. It **re-executed** the supporting evidence rather than relaying it.

      ⚠️ **This is the THIRD time in this epic that a Files list went stale against an inventory that grew after it** (story 03's `scouting_loader.py`, story 01's `player_dedup.py`, now this). **A story's Files list and the inventories its ACs delegate to are two artifacts that drift apart silently** — the AC stays satisfiable-looking while the work becomes unreachable. **PM ratified rather than reverted**: the alternative was an SC-4 that could not be met by the last story in the epic.

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
