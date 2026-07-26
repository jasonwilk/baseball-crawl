---
name: e276-health-gate-triage
description: E-276 (reconcile-at-load health gate) — the defect, what is settled, the OPEN blocking finding, and the process traps its triage rounds produced. Read before touching E-276 or any prior-vs-fresh ratio gate.
metadata:
  type: project
---

# E-276 — Reconcile-at-Load Health Gate: Prior Capture

Status **READY** as of 2026-07-25, awaiting operator dispatch authorization. 5 stories (01 SE primitive + player-line, 02 SE game, 03 SE roster, 04 SE e2e, 05 CA prose); Dispatch Team SE + CA. Full spec: `/workspaces/baseball-crawl/epics/E-276-reconcile-health-gate-prior-capture/`.

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

[[IDEA-185]] partial id churn still retires · [[IDEA-186]] roster retire lock (now carrying the retraction) · [[IDEA-187]] DE's health-gate memory states the invariant in the superseded pre-conjunction form and carries the refuted count reconciliation — routed out on **ownership**, since only DE may edit its own memory and DE is not on the dispatch team.

Related: [[lessons-learned]], [[operator-followups]].
