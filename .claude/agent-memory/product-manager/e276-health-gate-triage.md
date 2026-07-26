---
name: e276-health-gate-triage
description: E-276 (reconcile-at-load health gate) — the defect, what is settled, the OPEN blocking finding, and the process traps its triage rounds produced. Read before touching E-276 or any prior-vs-fresh ratio gate.
metadata:
  type: project
---

# E-276 — Reconcile-at-Load Health Gate: Prior Capture

Status **READY** as of 2026-07-25 **but AMENDED AFTER READY, and READY is deliberately NOT re-affirmed** — that call is the operator's/team-lead's, and the epic Status field says so. 5 stories (01 SE primitive + player-line, 02 SE game, 03 SE roster, 04 SE e2e, 05 CA prose); Dispatch Team SE + CA. Full spec: `/workspaces/baseball-crawl/epics/E-276-reconcile-health-gate-prior-capture/`.

## Fifth pass — the edge-walk, and CR-3's independent enumeration (2026-07-25). **The two lessons here are about MY verification, not the artifact.**

Operator authorized an edge-walk scoped to cross-artifact relations. **I enumerated 47 edges; a fresh reviewer independently enumerated 78 and returned 6 findings, none of which my pass surfaced.** All 6 verified and accepted; all fixed on the closing route, not the self-consistency route.

**⛔ THE ONE THAT MATTERS: I marked an edge ✅ that did not exist, and the disproof was inside my own report.** TN-19 said *"Cited by story 03 AC-6 and AC-7"*; **no story file contained the string `TN-19`.** I verified the SOURCE end (TN-19 names real ACs; the ACs carry their requirements) and marked both-ends done. **My own Section 1.B listed story 03's citations with no TN-19 — two sections of one document contradicted each other and the ✅ stood.** The failure was not missing information; it was **not running a check my own deliverable's structure made available.**

> **A ✅ FORECLOSES the re-check. An unverified edge is safer than a wrongly-verified one — a gap invites a look, a false clear repels one.**

**🔧 THE TECHNIQUE, and it is two greps not one** (CR-3's, with my precision): **discovery** — grep the *target population* for the source's identifier (all ideas for `E-276`; that is how IDEA-189's total absence surfaces). **Verification** — grep the *named consumer* for the citing note's identifier (`TN-19` in story 03). **Enumerating an edge backward is NOT verifying it backward**: my walk listed `TN-19 → 03 AC-6/AC-7` in the backward direction and verified it by reading the ACs' *content*. **The test is "does the target contain the source's NAME?", never "does the target say something sensible?"** No careful read substitutes for it.

**⛔ THIRD LESSON, and it is the one I got wrong TWICE: FIX THE CLAIM, NOT THE SITES THE FINDING FORWARDS.** CR-3's F4 named two artifacts carrying a retired positional claim. I corrected **those two** — and the re-verify found **three more copies live**, including the ideas **index row** and the Open-Questions entry **stating the edit DE would actually make**. Sweeping the claim's forms afterwards found a **fourth** CR-3 had not named (story 05 AC-9's own correction note restated "at the bottom" one paragraph below its own correction). **IDEA-187 ended up contradicting itself three times in one file.**

> **A fix scoped to a finding's cited sites is the same defect one level up.** The finding tells you where it *looked*, never where the claim *lives*. **Grep the claim's forms across every tree before calling it fixed** — and expect the surviving copies to sit in structural positions: index rows, summaries, and the sentence stating the actionable edit.

**Worse: the correction note I wrote cited the ideas-index repair as its precedent while the ideas index still carried the claim.** `doc-sweep.md`'s named shape — an index row asserting what its own topic file retracted — occurring **inside the note citing that precedent.** Fourth time this epic produced the fix-the-cited-sites shape.

**Second recurring lesson: agreement with a DERIVATIVE is not corroboration** (third instance this epic). Story 05 AC-9 and IDEA-187 both put a paragraph in the DE file's *"last third"*; it is at **line 21** (**of 35 then; of 41 after DE appended on 2026-07-26 — the denominator rotted under an append while the numerator held, and the claim is now stated by the paragraph's opening words in all three artifacts**). They agreed because one was written from the other. **Tell: two sources agreeing on a detail NEITHER NEEDED** — the signature of copying, not observation. Open the primary; never consult a summary of it.

**Fix-route discipline worth keeping**: F1 admitted two fixes — add the citation to story 03, or delete TN-19's claim to cite it. **The second makes the document self-consistent and leaves the relation broken**, passes every consistency check, and is the fix a sweep rewards. **Removing a false claim about a relation is not repairing the relation.** Same on F3: correcting the count closes it; re-scoping the sentence closes it *legitimately* while leaving a retired figure unmarked in `.project/research/`, which is **outside story 05's sweep scope**.

**Also found: two `E-276-*` research files nothing in the epic accounted for**, one carrying two retired figures (`13 direct crawl_is_authoritative calls` → 7; `exactly one assertion inverts` → two). **Supersession headers added, bodies untouched** — correcting a historical record in place destroys the evidence the figures were once believed, and the 13 is itself one of this epic's findings.

## Third/fourth Codex passes (2026-07-25) — the unscoped pass found what no sweep could, and overturned one of my fixes

**Audit 4 (unscoped) returned 3: one corroboration, one new, one that OVERTURNED MY OWN FIX.**

- **NEW — TN-9's prose-site inventory shipped KNOWN-INCOMPLETE.** Story 03 AC-9(c) recorded a required site as *"NEW, and it is not in TN-9's table"* — and left it out — while **story 05's Technical Approach AND Success Criterion 4 both treat TN-9 as the complete inventory.** **Durable, and it is `.claude/rules/testing.md`'s *annotating a limitation is not covering it* landing on a SPEC inventory**: an accurate scope note substitutes for closing the gap because accuracy about a gap reads as management of it. **Sharper half — an annotation only reaches whoever reads the file it is in.** Story 05 never reads story 03, so a gap annotated in one artifact and depended on in another is not merely uncovered, it is *unreachable*. **No sweep this epic ran could find it: nothing was stale or self-contradictory in either file alone; the defect existed only in the RELATION between them.** Fixed by adding the row (three consumers want an inventory, not a partial list). Bonus find in the same TN: the neighbouring retraction's closing clause *"the roster docstring is clean"* was falsified by that very site — a **reason rotting independently of its verdict, inside a retraction**.
- **OVERTURNED MY FIX — the sweep-report destination.** I had answered audit 3 with *"the completion report to PM — not a file."* **Wrong**: that makes an AC verifiable only in-session, by one party, once. **The governing rule was this epic's own TN-16 — "a construction that exists only in a transcript is not a regression test" — which I applied to test constructions and failed to apply to a verification artifact one pass later.** Now `.project/research/E-276-residue-sweep.md`, on story 05's Files list, with three outcome categories. **Note it matters most for the category-(iii) flag**, which is a handoff to an agent not on the team who may not be spawned for weeks.
- **CORROBORATION, not a new site.** Audit 4 re-found the suite-bookkeeping P1 independently — the strongest signal in either report. ⚠️ **But the relayed framing that its Success-Criterion site was "a site F4 did not name" DID NOT VERIFY**: my F4 sweep had already named and fixed that Success Criterion. Union is **four** sites, not five; audit 4 ran against the pre-amendment file. **Separating a real corroboration from a false "new site" framing is the whole of the check** — and it is the second relay claim in this epic that needed checking at the point of restatement.

**Audit 4 explicitly CLEARED** dependency sequencing, file-overlap/parallelism, agent routing, consultation coverage, repo-reality spot checks. **Recorded as a result, not as silence.**

## Second Codex spec pass (2026-07-25) — 4 findings, ALL 4 verified and ACCEPTED, 0 dismissed

Ran against the amended epic. **Every finding checked out against the file**, and two were **larger than reported**:

- **F1 (P1) — the `refused_by` enum was internally inconsistent across THREE sources.** TN-11's enum omitted `skipped_no_exemption_plan` while TN-11's *own later subsection* required the wrapper to synthesize it, and story 03 AC-3 named a third, different set. **Fix: a per-grain membership TABLE in TN-11**, now the single source, restated by story 03. **Durable: `refused_by == "gate"` is unreachable on roster and `"cap"` is unreachable on player-line — a flat list invited tests asserting states the code cannot produce.** ⚠️ **This is the SECOND drift of this same enum**: the T6 round added `boxscores_incomplete` after CR-2 found it non-exhaustive, SE repaired, CR-2 verified — and the repair was **correct and incomplete**, because `skipped_no_exemption_plan` was introduced in a later subsection of the same note and never propagated up. **A verified repair verifies what it was pointed at. Enumerations drift downward-only: the site that ADDS a member is rarely the site that LISTS them.**
- **F4 — the "no existing assertion changed" claim was stale in FOUR sites, not the two Codex cited.** The sweep found it in **Success Criterion 2** (a structural field) and **TN-13** as well as stories 01/02. **Epic-wide total is TWO expected assertion changes**, now tabulated in SC-2. **Durable, and it is a new shape: a count can be falsified by an edit that never touches it** — TN-13's "exactly one" was correct for its space (the fourth file) and was invalidated when the roster reversal added a second change *in a different story*. Nothing in the sentence signals it happened.
- **F2 — story 02 AC-11 was provisional, not settled.** My own escape hatch made an amended READY-surface AC self-cancelling and contradicted the epic's "no open questions". **SETTLED rather than deferred**: the operator's conditional (*"if the DESIGN makes it unconstructible"*) was discharged on evidence I already had (gate computed before per-id protection; fixture pattern in-tree). What remained was **fixture engineering, which is ordinary difficulty and does not license dropping an AC**. Escalation path kept, self-authorized deferral removed. **Lesson: an AC carrying its own opt-out is a suggestion, not a criterion.**
- **F3 — story 05's sweep-report destination was undefined.** Now: the completion report to PM, with **three outcome categories** (corrected / left-alone-deliberately / flagged-not-edited), because two categories silently merge a deliberate preservation with an unexamined hit. **Codex's supporting detail was slightly off** (it said the file list "names only itself"; it has two entries) — **a correct verdict on an imprecise premise**, which is this epic's own named pattern and worth reporting as such rather than letting the imprecision discredit the finding.

**Method note for the next pass**: my own verification grep returned **zero** for the twin-accumulation threshold because I searched `permit iff` against literal text reading `permits iff`. Re-searching on the formula found 8. **An unexpected count is a cross-check trigger, never a finding** — held, and it would have produced a fabricated "missing threshold" report. Also: `output_mode=count` counts matching LINES while `-o` counts MATCHES (19 vs 33 for the same pattern) — compare like with like or the sweep looks like it moved.

## Pre-dispatch amendment (2026-07-25) — an ABSENCE, which no sweep below could reach

An independent READY verification returned five items. **Four actioned, one DECLINED on the file's own evidence.** No design change.

**The gap: TN-16 promised a multi-run construction at every grain and only story 03 delivered one.** Now **01 AC-14** (player-line no-ratchet, N ≥ 4 invocations, per-run prior count) and **02 AC-11** (game grain, cross-perspective twin accumulation). ⚠️ **Neither Codex pass covers these — both predate them, and they land on the implementer surface. A third pass is the cheap check before dispatch.**

**The durable finding, and it is the counterpart to the structural blind spot recorded below:** every sweep this epic ran hunts for **text that is present and wrong**. This defect was **text that was never written** — three ACs that did not exist. **No term sweep, no normalization, and no two-axis adjudication can detect an absence.** The final sweep's *"not one was in an AC"* was **accurate and did not transfer.**

Two structural causes, both in assignment fields:

1. **TN-16's Story column said *"each grain story"* — a story CLASS, not named ACs.** Every other row in that table named a construction and a story; this one named a pattern and a category, so there was nothing to tick off and three stories could each assume another carried it. **A requirement addressed to a category is a requirement nobody owns.** Fixed by naming all four ACs individually.
2. **The row's own title said *"at every grain that keeps one"*** — and this epic's idiom for "keeps a gate" is exactly that ("the two grains that keep a gate"). Under that reading the row promised the construction at **precisely the two grains that omitted it** while excluding the one that delivered. **Three words in a table cell, ambiguous in the direction that hid the gap.**

**The DECLINED item is the other half of the lesson.** The brief held that a game-grain accumulation shape refutes story 01 AC-9b's *"the roster grain is the only one where the slip's consequence is demonstrable."* It does not: the slip differs from the correct form by exactly `W − fresh`, **empty on game and player-line** under the epic's own `W ⊆ fresh` discriminator, so the slip is a strict no-op there. The two mechanisms are different objects — twin accumulation is the gate's **denominator**, the slip is the **classification universe**. **A verification brief is a claim too; verify each item against the file before acting, and the file wins.** The rationale now carries its premise in both places, converting an assertion into a derivation.

**Also landed**: the twin-accumulation threshold `permit iff P >= X + g` in TN-16 [DERIVED, PM, not executed] with its space and the ~4% measured occupancy that puts production far from it; the `0..8` roster-sweep range disclosure (**a short range flatters a zero count and deflates a non-zero one — the limitation binds both directions**); and IDEA-187's **second** deflation (see below).

**IDEA-187 deflated twice, and the second pass is a specimen worth keeping.** Its Defect 1 quoted a paragraph of DE's memory file **that does not exist in it**, and stated the sufficiency direction **backwards against TN-10** — attaching "necessary but not sufficient" to the temporal clause where TN-10 attaches it to same-population. **Acting on the idea as written would have introduced an inversion into a memory that did not have one.** The idea credited its own method as *"found by reading the file, not by grepping"* — **and reading is where it failed**; a grep for the quoted paragraph returns zero. **Near-homographs defeat readers and greps in different ways; neither instrument covers the other.** Story 05 AC-9 had inherited the same characterization and is corrected — an AC-surface defect carrying **none** of the eleven swept terms.

## The final consistency sweep — the durable lesson (2026-07-25)

Eleven prohibited terms, three normalizations (strip `**`/`__`, hyphenation, case-insensitive), grep to enumerate and a **read of every hit's surrounding prose** to adjudicate on two axes (live assertion vs finding-record × pre-existing vs written-since). Only the top-left cell is actionable.

**Result: the top-left cell was NOT empty — 26 live assertions in `epic.md` carried superseded design, plus 4 repairs each to IDEA-186 and IDEA-187 in BOTH index row and file.**

**The transferable finding: every single hit was in a TECHNICAL NOTE or a tracking artifact, and NOT ONE was in an acceptance criterion.** When the conjunction was dropped mid-planning, the stories were swept and their upstream was not — so a reviewer checking the ACs (the natural surface, and the one the epic's own banner pointed at) would have found them clean and concluded the epic was consistent. **Sweep the UPSTREAM of an edited artifact, not just the artifact. The surface that gets swept is the surface someone thought to sweep.**

Three specimens worth carrying:

1. **An inverted INSTRUCTION, not a stale description.** TN-16 told an implementer to assert *refused, zero deleted, two pre-existing rows surviving* for the whole-set construction — the conjunction-era outcome — where story 03 AC-2 requires **22 retired including exactly 2 pre-existing**. Following the Technical Note writes a test that fails.
2. **Adjacent-line miss.** Precondition (c) stated the prohibited conjunction shape as a live precondition, **four lines below precondition (a), which had been rescoped in the same edit pass.** An edit's blast radius is the section, not the passage.
3. **A retired claim in a second location.** TN-16 contrasted the 862 sweep as *"now historical, since the conjunction closed those cases"* — the exact phrasing TN-5 retracts two Technical Notes away.

### ⛔ The term sweep's structural blind spot — the most transferable part

**After the eleven-term sweep finished clean, three more top-left hits were found**: the epic's **Overview**, **Goal 1** and **Success Criterion 3** all asserted the fix across *"all three grains"* — false on roster, and the exact smoothing story 05 AC-3 forbids. **None contained any of the eleven swept terms**, so no normalization could have reached them.

**The rule to carry**: a term sweep bounds *the terms you searched*, never the concept. The retired claim was *uniformity across three grains*; what survived it was **a scope word in a structural field** ("all three", "each grain") — ordinary summary language, and the last thing anyone re-reads.

### THE METHOD — 31 of 31, strong enough to stop being a heuristic

> **Every top-left hit in this epic was in a STRUCTURAL position. Not one was in body prose.**

**Thirty-one of thirty-one** — PM3's story sweep (2: a Files-to-Modify list, an AC's characterising clause) plus this one (29: 26 term-sweep hits in `epic.md` + the 3 token-free top-matter hits). *Counted as hits; the 4-each repairs to IDEA-186 and IDEA-187 are a separate tracking-artifact surface and are excluded from the 31, so the number carries its space.*

**So: sweep the structural fields FIRST and EXHAUSTIVELY — tables, file lists, bullet indexes, headings, goal and criterion lists, characterising clauses, index rows. The prose is the low-yield surface.** It follows from the mechanism: **prose gets rewritten when the design changes because it is *about* the design; structural fields get updated only if someone remembers they exist.**

### The best single specimen, because it is the rule demonstrating itself

The team lead reported story 05 AC-9's *"pre-conjunction form"* wording as **fixed**. It was — **in the story. The identical claim was still live in IDEA-187's README row AND in the idea file.**

**The defect was fixed on the surface someone swept and survived on the two nobody did** — the lead's own example demonstrating the lead's own point, unnoticed by the person citing it. Better evidence than any abstract statement of the same rule, and the reason to prefer this specimen when teaching it.

### Corroboration is a result, not waste

Re-sweeping the story files after PM3 had already swept them was **an independent re-run of another agent's verification rather than acceptance of its result** — the practice this epic's scorecard credits with catching two of the day's checking failures. It came back **clean, 0 top-left across all five**, corroborating PM3 and independently reaching the same adjudication of story 05's legitimate own-memory `carve-out`. **A confirming result from an independent channel is a result.**

**Two method notes.** A `conjunction` count of 55 against a relayed ~54 was resolved by enumerating and adjudicating all 55, never by reconciling the number — the gap is a **units artifact** (the Grep tool's count mode reports matching *lines*, not occurrences). And **reading a line back after editing it caught a second stale claim in the same line**, on the half the edit had not touched — block-edit hygiene found a sweep defect the sweep had missed.

## The defect

The health gate reads its "prior" id-set AFTER the same run's own writes, so the executed gate is `|old ∩ fresh| + |new| >= 0.5(|old| + |new|)` — every row written this run relaxes the floor by half a row, reducing to `|fresh| >= |stale|` at zero overlap. Live data loss on a routine `bb report generate`: 9 stored lines vs 9 brand-new ids hard-deletes all 9, uncapped.

**All THREE grains are polluted.** The commissioning handoff claimed two; data-engineer executed the roster case (`roster_db_count=4` on a 3-row roster is the tell). Roster is inert today only because `MAX_ROSTER_DEPARTURES` fires first — **masking, not protection**.

5 stories: 01 SE primitive+player-line, 02 SE game, 03 SE roster, 04 SE e2e churn, 05 CA prose. **02 blocks 03** (shared file; plain grain first so roster's deliberate divergence reads as a divergence).

## Settled — do NOT relitigate

- Pre-upsert capture is the only honest shape (timestamp discrimination and subtract-the-writes both rejected, with reasons, in TN-1).
- The snapshot is a **REQUIRED kwarg**, no default (evidence-parameter rule).
- Gate = **conjunction** of the legacy live-population gate AND the corrected snapshot-population gate. Candidates stay `live_prior` uniformly, **no intersection on any grain**.
- **Caps untouched** — `MAX_GAME_RETIREMENTS` is doing the masking the before/after evidence depends on.
- Roster's CANDIDATE set stays `live_prior`; only its GATE moves. SE reproduced the E-267 deadlock a uniform fix causes.
- `not_final ∩ fresh` → **file nothing** (provably a no-op; two SE instances agreed independently).

## ⛔ OPEN BLOCKING FINDING — needs an operator call

**The roster-lock fix-neutrality claim is RETRACTED. E-276 CREATES a new route into the permanent roster lock** — no truncated crawl and no churn required. `DB {a,b,c}`, cap 2, run 1 `fresh {a,n1}`: legacy PERMITs, cap PERMITs, corrected REFUSEs. Today retires `b,c` and converges clean; the fix strands them, and two runs later `absent ∩ previously = 3 > 2` so **the cap refuses forever**.

Retracted in TN-5, IDEA-186 and its README row; *"clutter identical to today"* struck from the under-deletion comparison — that dismissive adjective is what made the direction sound not worth checking.

**Deletion-neutrality is UNTOUCHED and still holds** (it is only ever about never *permitting* what today refuses; survived five attacks). **Do not conflate the two — that conflation is how this survived.**

Two admissible outcomes: close it (a story-03 AC requiring a three-run test that a refused run cannot push the next over the cap), or accept it as a named residual with the harm stated (permanent stale coach-facing roster + all future genuine departures blocked). Leaving it described as fix-neutral is not admissible.

## Durable findings worth more than the fix

1. **The stated invariant is TRUE of the broken code.** Same-population-on-both-sides holds while the gate is meaningless — which is why four review layers passed it. The transferable fix is *"necessary but NOT sufficient"*, not merely the temporal clause.
2. **A mitigation named in prose, never executed, protecting a path it structurally cannot reach.** The E-267 "benign, dedup would have merged them anyway" ruling, refuted because the retire runs BEFORE dedup by explicit design.
3. **Existing tests missed it because every shrink test uses `fresh ⊆ prior`**, where pre- and post-upsert prior are identical. The churn shape was untested at every grain.
4. **Byte-identical behaviour on one executed input is not a universally-quantified neutrality property.** A trace is one input; the quantifier attaches silently. This is how the roster-lock claim above survived.
5. **Adding a mechanism to a guarded path silently degrades every message and comment that enumerated the old mechanisms.** Nothing fails — the enumeration just stops being exhaustive. "We are adding a refuser" is a searchable trigger.

## Process traps from the triage rounds

- **A brief generated from a growing handoff artifact.** The successor PM's brief was cut from `.project/research/E-276-triage-handoff.md`; an entire second audit (7 MUST / 7 SHOULD, including the blocking finding above) landed in that file afterwards, and PM found it only via an unrelated grep. **Re-issue BOTH the artifact and any prompt built from it when you correct a handoff; check its mtime against your own start when you receive one.**
- **The 20-vs-222 divergence gap has produced THREE wrong reconciliations, each accepted because it corrected the last.** The surviving account is the ORIGINAL artifact-of-bounds one, confirmed by a four-point exact fit `c(n) = (3n−2)(n−1)/2` → 15/26/100/222 at n = 4/5/9/13. PM implemented the third — a shapes-vs-**combinations** unit error — before checking. **Fitting reported figures to a curve beat three method-level arguments and took one minute: reconciling two measurements by reasoning about their METHODS is far more error-prone than testing whether one arithmetic relation reproduces the reported values.**
- **Correcting a count is exactly when a fresh one gets asserted unchecked.** TN-13 exists to record an inherited-and-never-measured count; its own correction asserted "13 direct calls" where there are 7.
- **`def test_` counts and COLLECTION counts diverge wherever `parametrize` appears** (30 vs 34, 17 vs 19 here). A reviewer counting `def test_` would have "refuted" two correct claims and missed the wrong one. **A count's UNIT is as load-bearing as its space.**

## Residuals filed out

[[IDEA-185]] partial id churn still retires · [[IDEA-186]] roster retire lock (now carrying the retraction) · [[IDEA-187]] DE's health-gate memory — **deflated TWICE; the residual is one cross-reference**, routed out on **ownership** since only DE may edit its own memory and DE is not on the dispatch team. [[IDEA-188]] roster delete converting a refused fork to an executed merge · [[IDEA-189]] a failing dedup collapse is invisible through `LoadResult.errors`.

## 2026-07-26 rounds — R2–R5 and R1. Epic is STILL READY, NOT dispatched.

**State, so a future instance does not act on the stale summary above**: `epic.md` **~2,180 lines**. Story 01 now runs to **AC-15**; story 03 gained **AC-5b**. **R1 verdict: DIAGNOSTIC ONLY, NO GATE** on the player-line grain — three mechanisms (cap, `extra_guard`, churn-signature) were evaluated **by construction** and none adopted, because **every mechanism that closes the sustained-churn window closes it by refusing forever, and a permanent refusal DOUBLES the coach-facing season aggregate** (27→54 AB, measured). Residual accepted and surfaced; closer is [[IDEA-185]].

**The epic's headline is true for ONE RUN.** A refusal still WRITES, so the gate's own population grows until it permits at the floor and deletes the prior generation, uncapped. **`W ⊆ fresh` constrains the CANDIDATE set, not the GATE POPULATION** — and it is the population that grows. Two agents reached that independently; it is the crux.

## Durable lessons from those rounds — the ones that generalize past this epic

- **⛔ ANSWERING FROM A RECONSTRUCTION WHILE THE PRIMARY SITS ON DISK. Four parties, one session, same mechanism.** I numbered a finding off `epic.md`'s **partial copy** of a findings index and collided with an existing number (the canonical series lives in `.project/research/E-276-process-findings.md`); SE presented a sweep as 5-tuples when its harness printed 3-tuples; SE then left a superseded form in its own heading *one hour after telling me to write the corrected form*; the team lead relayed **six** figures/paths/strings that did not survive contact with the file. **The reconstruction is always more available than the source, and always confident.** Every instance was caught by someone opening the primary. **Mechanical rule: if you are quoting a figure, open the file — including your own output.**
- **Take no number, formula, or literal string from a router.** Standing instruction that emerged mid-session and caught two false claims before they entered ACs — including a relayed `24 × 13 × 3 = 72` that computes to 936. **Refusing to restate arithmetic that does not compute is a real detector.**
- **An APPEND BELOW a cited line invalidates a positional claim's DENOMINATOR while leaving its NUMERATOR correct.** So the natural check — *is the cited line still where we said?* — **passes**. Two parties ran exactly that check and both got a pass. **A position stated as a fraction has two independently rotting halves.** Fix: state the claim by the paragraph's **opening words**; demote coordinates to dated evidence.
- **A correction paragraph is the most camouflaged host of a stale value**, because it already reads as the place this was dealt with. I fixed 3 of 4 copies and missed the one inside a paragraph correcting an earlier positional error.
- **Scope a repair from a GREP, not from the conversation.** The denominator repair was framed as "two artifacts"; a repo-wide grep found **six**. Fixing only the discussed two would have manufactured a fresh instance of the derivative-divergence the fix documents.
- **A closed-set instruction ("flag this and nothing else") must be re-counted whenever the set grows** — nothing in the sentence signals when it has. Story 05 AC-9's prohibition would have SUPPRESSED a flag the same AC later required.
- **Checked-against-data and EXECUTED are different epistemic states.** SE offered a predicate labelled honestly as the former; holding it out and asking for execution is what revealed it needed a *previous invocation's record*, which nothing in production retains — disqualifying it from the AC it was headed for. **The defect this epic fixes survived six review passes because a property was reasoned to rather than run.**
- **Self-reported defects were the session's most valuable findings and are undiscoverable from artifacts** — DE's mislabelled baseline and swallowed `TypeError`, SE's inferred tuples and its own stale heading. **Sole detector is the actor volunteering it.**
- **Don't edit quoted output to match a later refinement** — that falsifies the record. Annotate beneath it instead. (SE's call on the `bloat` label; CR reached the same rule independently on a quoted regex.)

Related: [[lessons-learned]], [[operator-followups]].
