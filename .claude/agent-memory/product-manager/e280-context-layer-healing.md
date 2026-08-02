# E-280: Context-Layer Healing — what PM must carry forward

**COMPLETED 2026-08-02.** Epic file (archived) is canonical for everything; this holds only
what PM specifically needs and would otherwise re-derive. TN-20's 63 dispatch findings are
the durable record — cite them, do not restate them.

## 1. What LANDED that changes how PM works in every future dispatch

- **Verdict economy is ONE-OF-EACH, not one-in-total.** Operator verbatim: *"pm owns
  acceptance."* PM issues the single AC verdict, code-reviewer the single review verdict,
  both against a **frozen story state**, neither re-askable. **Dual approval SURVIVES; only
  RE-ISSUANCE died.** ⚠️ Anyone reading the old TRIM-1 design as "collapse to one issuer"
  ships the design the operator refused.
- **The review surface is a FROZEN TREE.** Completion report → `git add -A && git write-tree`
  → reviewer diffs two tree SHAs. **"Unstaged = the current story" is RETIRED**, everywhere.
  Two verdicts may not cite the same tree SHA.
- **Per-story review depth is tiered by FILE-PATH CLASS**, never by an agent's risk judgment.
  Unmatched paths default to tier A (fails safe).
- **The context-layer size GATE is RETIRED** (operator: *"I don't think gating and ratchets
  are working. I think we just need periodic refinement."*). No baseline, no offset, no
  exception, no re-snapshot. `context-ratchet.sh` survives as an **on-demand diagnostic**;
  trigger 7 now records a reading and routes a "yes" to the periodic pass.
- **Two new cadences, counted in EPIC CLOSURES** (not weeks), checkable from `.project/archive/`:
  **batched adversarial audit per THREE closures**, **periodic context-layer refinement per
  FIVE**. The refinement pass produces a dated record in the History of the epic whose closure
  triggers it; a pass that retires nothing records why.
- **Long-lived agents carry a 6,000-char report ceiling, labelled an ESTIMATE.**
  **`code-reviewer` is deliberately EXCLUDED** — a length cap is a conservatism instruction,
  and that model may follow one literally and report less. There is **no measured
  report-length regression**; the cap is a tail guard, not a repair (TN-19).

## 2. PM's OWN recurring AC defects, mechanised — the most reusable thing in the epic

**⭐ A RED written as an ENUMERATION OF FAILURE FORMS is narrower than the body it tests BY
DEFAULT, not by accident** (TN-20 item 24). The body states the requirement; the RED states
the failures the author happened to think of. The gap is invisible *because* the RED is the
mechanically checkable half — so it is the half that gets run, and running it feels like
verification. **Four instances in one epic, all PM's.**

- **Remedy: phrase the RED as a PROPERTY OF THE OUTCOME, not a list of forms.** Worked case:
  *"no verdict is issued against a diff containing changes already covered by a prior
  verdict"* catches the procedural and textual forms alike.
- **Normative rule when body and RED disagree: the BODY defines the requirement, the RED is a
  possibly-incomplete TEST for it. An under-enumerating RED does NOT shrink the requirement.**
- **A THIRD variant, worse than both: the RATIONALE BROADER THAN THE CRITERION** (item 49).
  Body and RED agreed on *"no tier row states review depth"* while five rationale bullets
  argued about the seam generally — seven sites, three were tier rows. **Only comparing the
  criterion against its own justification finds it.** Ask of every AC: *does the argument I
  just wrote justify something wider than the RED I just wrote?*
- **The sharpened remedy, and it CHANGES the answer** (item 24, second half): a requirement
  restated at N layers narrows at each one **independently**, so the narrowings correlate
  without causing each other. **So the fix is not a better RED — it is one fewer restatement.**

**⭐ PM's criteria need a HARMFUL-THING-vs-CATEGORY calibration at FIRST APPLICATION, and it
is not discoverable earlier** (item 45). Three times: AC-9b (a grouping *untrue of any
member*, not grouping itself), AC-18 (a second *authoritative declaration*), AC-3 (a second
*declaration*, not a second appearance of the string). Each was written correctly against the
defect its author had seen, and each named a category broader than that defect.
**All three were caught only because an implementer FLAGGED rather than complying
conservatively** — and the flags came from a warning PM had put in the story's Status block
telling them to flag. **That intervention is the single most effective thing tried in this
dispatch; keep using it.** An implementer who reads conservatively and complies silently
produces the over-broad outcome and nobody ever learns.

**A story's dependencies follow from what its ACs READ, not only from what its edits WRITE.**
Made twice, at both ends of the epic: E-280-07's AC-1 was unsatisfiable because seven sites
lived in files owned by later stories, and E-280-08 declared itself independent while its
verifications were global. **A verification story looks independent until you ask what must be
true for its checks to mean anything.**

## 3. Two rules about FIGURES that this epic paid for twice each

**⭐ A FIGURE WITH ITS TREE ATTACHED CANNOT GO STALE — IT CAN ONLY BECOME HISTORICAL.** Write
every measured figure as `<value> @ <tree-or-date>`. E-280's `84,388` was a **true** measurement
of tree `fb15272`; it became false only when quoted **without its tree**, under a heading
claiming it was the epic's end-state. It then propagated into an orchestrator's report and was
twice misdiagnosed as a bad derivation before anyone checked what it had actually measured.
**The label is the whole fix**, and it is cheaper than any amount of care about staleness.

**⭐ WHEN TWO INSTRUMENTS DISAGREE, THE DISCREPANCY IS DATA — normalizing to one destroys it.**
The reflex on finding two counts of the same thing is to pick the correct one and discard the
other. In E-280 a uniform +3/+4 gap between an AC-only checkbox count and an all-checkbox count
**was** the Definition-of-Done block, unchecked in six of seven stories — a second instance of
the very defect the ruling was about, in the same files. **Neither count alone contained the
finding; only the gap did.** Reconcile before you normalize, and ask what the gap is made of.

**Companion, for a claim rather than a figure — [[e280-context-layer-healing]] item 46a:**
**a heading is not a claim a reader checks, it is the INDEX ENTRY they quote**, so a body's
qualifiers do not travel with it and cannot repair it. Pairs with item 49 (*rationale broader
than the criterion*) at the opposite end of an entry: **49 is the argument overreaching the
rule below it; 46a is the title overreaching the evidence beneath it — and both are invisible
to any check that reads the operative text.**

## 4. Dispositions a successor will otherwise re-litigate

- **TOMBSTONE a retired CLAIM; DELETE a relocated CRITERION** (item 41). They look identical
  and the rule points opposite ways. Discriminator: *is the text still asserting something*
  (tombstone it, struck, correction attached) *or is it now asserted somewhere else* (delete,
  leave a pointer)? A tombstone carrying a full criterion is a second copy.
- **A FLOOR is written from what its author could find BY TOKEN**, so it systematically names
  the token-reachable sites and misses the ones sharing no token — which are the sites the
  sweep exists for (item 44). **A floor whose every site resolves to `no change needed` is a
  SUCCESSFUL sweep, not a wasted one.** An implementer reporting only floor-site verdicts has
  not swept.
- **State negative results AS results** (item 61). *"I looked and found nothing"* and *"I did
  not look"* are indistinguishable in a record unless one is stated. A count that did not move
  is EVIDENCE, not a non-event.
- **Do NOT re-open**: OQ-1 through OQ-5 and OQ-A are all operator-ruled and CLOSED. TN-11's
  site list is a **FIND-list, never a delete-list**.

## 4. Open at closure — carried, not discharged

- ⚠️ **The AC-1c layer-wide SEMANTIC residual.** Layer-wide semantic coverage of the retired
  "unstaged = current story" invariant was **NOT established** — it rests on doc-sweep steps
  1+2 over five literals, with step 3 covering three files only. **The bound that produced it
  is the durable part: a positive control proves the instrument EXECUTED; it does NOT prove
  the pattern is WIDE ENOUGH** (item 59, where PM's own PASS was retracted). PM deliberately
  did **not** order a 199-file semantic read — a judgment, priced against a residual four
  independent checks failed to surface any instance of. **Do not re-litigate it silently and
  do not report it as coverage.**
- ⚠️ **BOTH CADENCES ARE OWED. E-280 discharged NEITHER, and there is no epoch line.** The
  epoch gap PM raised at closure was answered by CA writing an origin **RULE** rather than an
  origin value — *"where a cadence has no run on record, the next closure owes one"*, which is
  self-starting and cannot go vacuous. Then CA ruled that **E-280 discharges neither cadence**:
  no Fable audit ran (Codex is a separate instrument, not a substitute), and the refinement
  pass did **not** run because AC-9's dated artifact does not exist, because `.claude/agent-memory/`
  — **89% of the measured growth** — got append-only bookkeeping rather than a prune, and
  decisively because **E-280 FOUND refinement work in that subtree and routed it to [[IDEA-234]]
  instead of doing it.** ⚠️ **Do NOT write a refinement record retroactively; CA ruled that out
  explicitly.** The next closure inherits the pass with its worklist already assembled.
  **PM briefly recorded the refinement pass as RUN on a report that the question was settled —
  it was not, and the ruling went the other way. Check a ruling against the design owner's own
  words, not a summary of them.**
- **[[IDEA-234]]** — software-engineer's memory rests on the retired invariant in two files
  (topic file **and** its `MEMORY.md` index row, which restates rather than points). Resolution
  trigger: next SE spawn. code-reviewer's equivalent was **not** an idea — it was on the team
  and reconciled its own directory.

## 5. Process facts worth keeping

- **34 findings across 8 review passes at planning, 30 accepted; 63 dispatch findings.** The
  epic ran under its own trims by operator order (single verdicts against frozen files, one
  internal review iteration planned rather than three). **If anyone compares this epic's
  review-pass count against E-271's four or E-276's six, the difference is deliberate.**
- **Three structural defects, each found by a different party, none by more than one**
  (CR, CA, Codex) — all the same shape: *an AC whose reachability depends on something the
  decomposition did not encode.*
- **Execution beats reading, and the reason is COST, not virtue** (item 15). Every party
  re-read carefully and still missed things; every catch came when checking got cheap enough
  to actually do. **Elegance does not make a claim wrong — it makes it expensive to question.**

Related: [[lessons-learned]], [[archived-epics]], [[e279-planning-state]], [[IDEA-234]].
