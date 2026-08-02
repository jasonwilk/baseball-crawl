# E-280-09: Strip review depth from the routing seam, and scope the frozen-state check

## Epic
[E-280: Context-Layer Healing](./epic.md)

## Status
`DONE`
<!-- DONE 2026-08-02 against frozen tree `3d2274cead16c460108ac6f680b4927b9c1ec0df`. Both gates: code-reviewer APPROVED (no MUST FIX, no SHOULD FIX; tested the fix as a REFERENT problem — vocabulary and addressability now disambiguate independently), PM AC verdict PASS on AC-1 (as widened), AC-2, AC-3. PM read CR's findings list, not a characterization of it. CR's earlier MUST FIX was affirmed at MUST FIX rather than downgraded: CR made the misreading itself on first pass, so reachability was observed rather than hypothesized, and the failure was silent on two of four outside-scope write shapes. -->
<!-- Findings: epic TN-20 items 49, 50, 51, 52, 54. Item 50 is the epic's first real BOUND on TN-7 — a fact must live where its consumer reads it, and "don't restate" cannot override that. -->
<!-- SUPERSEDED: -->
<!-- IN_PROGRESS 2026-08-02, assigned to claude-architect. Review base is E-280-06's frozen tree `fb1527279bc291a6170197534c079bd4fae0d5d6`. -->
<!-- ⚠️ Read epic TN-20 item 44 before starting: A FLOOR NAMES THE TOKEN-REACHABLE SITES AND MISSES THE ONES SHARING NO TOKEN, which are the sites the sweep exists for. Two consecutive stories (04's AC-15, 06's AC-9) had their floor point at CORRECT text while the real defect sat a paragraph away. A floor whose every site resolves to `no change needed` is a SUCCESSFUL sweep, not a wasted one — do not read an all-clear floor as evidence the sweep was pointless. -->
<!-- ⚠️ And item 45: if either AC here reads broader than the defect it targets, FLAG IT rather than complying conservatively. Three criteria in this epic needed a harmful-thing-versus-category calibration at first application, and all three were caught only because the implementer flagged instead of resolving. Silent conservative compliance produces the over-broad outcome and nobody learns. -->
<!-- Created 2026-08-02 by PM, splitting E-280-06. Both criteria were written into 06 during dispatch (AC-10 from E-280-04's unsatisfiable AC-8 limb, AC-11 from the TN-20 item 22 mechanism gap) and 06 became four distinct bodies of work. See epic TN-20 item 35 for the split reasoning. -->
<!-- ⚠️ This story is NARROW AND DEEP. AC-2 is a MECHANISM DESIGN, not an edit. Do not treat either criterion as a text substitution — both have property-shaped REDs precisely because the form-shaped versions failed in this epic six times. -->

## Description
After this story, `.claude/skills/implement/SKILL.md`'s tier table names tiers and points at `code-reviewer.md` for what each tier means, stating no review depth itself; and the frozen-state check is scoped to the paths a review was routed with, with movement inside and outside those paths carrying different, stated consequences.

Both are seam work on one file. Neither is the wide mechanical work E-280-06 carries.

## Context
Epic TN-20 items 22, 24 and 31 are the background and should be read before starting.

**Why this story exists separately.** E-280-06 accumulated these two criteria during dispatch while already owning frontmatter across ten skills plus the CLAUDE.md Workflows compression. Wide-and-shallow and narrow-and-deep work in one story is how the deep half gets squeezed — and **06 is this epic's pinch point: E-280-07's layer-wide check and E-280-08's terminal verifications both read what these stories write, so a partial landing here is the most expensive failure available.**

**The freeze-scope mechanism was designed by claude-architect and measured rather than reasoned.** `git diff --quiet --cached <tree> -- <paths>` is supported and gives per-path answers. PM found the gap and **declined to adjudicate the mechanism it trips**, on the same ground code-reviewer does not approve its own exemption.

## Acceptance Criteria

- [x] **AC-1**: **No SITE in the routing seam states review DEPTH** (widened from "tier row" — see the calibration note below). **No tier row in the routing seam states review DEPTH.**
  - ⚠️ **CALIBRATED 2026-08-02 by PM, on the implementer's flag. TWO rulings.**
  - **(1) AC-1 is WIDENED from "tier row" to "any site", because its RATIONALE was broader than its CRITERION — a new variant of this epic's pattern.** Seven sites in the seam state review depth; only three are tier rows. **Literal compliance would have left four standing, including *"Tier C stories skip the code-reviewer"* — the exact bare absolute E-280-04 removed from `code-reviewer.md`, and the subject of this AC's own argument (ii).** Items 4/8/18/24 are REDs narrower than their bodies; **here body AND RED were narrower than the arguments justifying them, so the rationale persuades a reader the criterion covers more than it does.** Widening is a tightening, which needs less justification than a narrowing — and the story already satisfies the wider form, so this **records the criterion the work met.**
  - **(2) THE LINE BETWEEN RUBRIC CONTENT AND ROUTING FACTS IS CONFIRMED, and the discriminator is a property: DOES THE ORCHESTRATOR NEED THIS FACT AT ROUTING TIME TO DECIDE WHAT TO DO?**
    - **Rubric content → DELETE.** *What a reviewer does once engaged* — the depth column, the worked example's *"receives the full rubric"*. Consumed by the reviewer, so it lives in `.claude/agents/code-reviewer.md`.
    - **Routing facts → KEEP, corrected.** *Whether a per-story reviewer pass happens at all* is decided by the orchestrator at routing time, **and it cannot be delegated to a file the orchestrator does not read then.** Pointing at `code-reviewer.md` for it would make the seam **unusable**, not non-restating. Corrected form: **"skips the code-reviewer FOR THE PER-STORY VERDICT"**, naming Step 1c — which matches what E-280-04 landed one file over and kills the bare absolute.
    - **This is not a convenience carve-out: the two are DIFFERENT FACTS WITH DIFFERENT CONSUMERS**, so keeping the routing fact in the seam is not restatement. Test each site by asking **which party consumes it and when** — a mechanical join, not a judgment. Each row names the tier and points at `.claude/agents/code-reviewer.md` for what that tier means. **RED**: any tier row stating what a reviewer does at that tier. (A property, deliberately: *"row B's clause is deleted"* rots the moment a fourth tier appears; *"no tier row states review depth"* survives.)
  - **All THREE rows carry depth text today, and the narrow reading fails on two of them:**

    | Row | Depth text in the seam | State |
    |---|---|---|
    | **A** | `Code-reviewer full rubric + PM AC verdict` | **currently TRUE** — and therefore invisible to a staleness sweep |
    | **B** | `skipping rubric priorities 2, 4 and 5` | wrong **and** misplaced |
    | **C** | `PM AC verdict alone -- no code-reviewer pass` | **CONTRADICTED by E-280-04** — `code-reviewer.md` states tier C content *does* reach the reviewer at the unconditional Step 1c closure review |

  - **(i) Row A is currently TRUE, which is exactly why a sweep aimed at *wrong* text leaves it standing.** A correctly-stated instance of the pattern being removed is invisible to a staleness search.
  - **(ii) Row C is the same bare absolute E-280-04 removed from `code-reviewer.md`, surviving one file over.** "Correcting" it rather than **removing its depth claim** would carry that absolute into the seam immediately after the rubric shed it.
  - **(iii) ⚠️ DELETE the depth text; do NOT transcribe a corrected version.** E-280-04's remediation makes row B's numbers "2 and 5" — **an implementer who updates the clause instead of removing it has made the story that exists to stop the seam restating rubric content faithfully restate a wrong version of it**, and it goes stale again at the next renumbering.
  - **(iv) code-reviewer's warning, kept verbatim: *"taking them one at a time is how 06 under-enumerates."*** This epic's own pattern aimed at the story written to fix it.
  - **(v) The strongest argument for the wider scope is the seam author's own, and it belongs here because it tells you WHY three rows rather than merely THAT it is three.** The implementer that wrote the seam's bare tier C absolute in E-280-02 is the one that fixed its twin in `code-reviewer.md` in E-280-04 — *"one author fixing a claim in one file and leaving its twin in another, in the same epic, days apart."* It survived because **surfacing is not ruling**: the author ruled on one instance and never asked where else it had asserted the same sentence. **Generalizable: fixing an instance does not discharge the claim; the author must enumerate where else they asserted it.**

- [ ] **AC-2**: **The frozen-state check is scoped to the paths the review was routed with, and movement inside versus outside those paths has different, stated consequences.** Three REDs, each a property of the outcome:
  - **RED (a) — safety, unchanged in force**: a verdict issued against a **reviewed surface that moved after the freeze**. Movement inside the routed paths voids the verdict in flight: re-freeze, re-issue.
  - **RED (b) — no-swallow**: movement **outside** the routed paths silently discarded — not reported, or not distinguished from movement inside. It does **not** void the verdict, and it must still surface, because it is either PM performing its role (expected, no action) or **an implementer writing outside its Files list (a finding)**.
  - **RED (c) — no-rot**: the scope stated as an **enumerated path list** rather than as *the paths this review was routed with*. An enumeration rots the next time the repo gains a directory; the routed paths are already an input to every review assignment.
  - ⚠️ **It must key on WHAT MOVED, never on WHO MOVED IT.** An actor-based exception ("PM's writes don't count") would require recovering authorship from a tree, which nobody can do.
  - **Why the obvious fix is wrong.** The check as written is unscoped, so it fires on **correct PM behavior** — status flips and AC rulings land in `epics/`, outside every reviewed surface, and move the worktree. Across this dispatch, **100% of half-(1) failures were PM's `epics/` writes with zero lines under `.claude/`.** But loosening the check **trades away a real true positive**: an unscoped check also catches an implementer writing outside its Files list. **The check is correct and its DOMAIN is wrong**, which is why the repair is scoping plus a report, never relaxation. (Epic TN-20 item 31.)

- [ ] **AC-3**: Both edits are verified by **absence**, not by presence. **RED**: a verification confirming the new text arrived without confirming the old form is gone. (Per `tool-output-integrity.md`: a botched edit leaving both forms standing reads fine to a skimmer.)

## Technical Approach
Cite by phrase and heading, never by line number — E-280-02, E-280-04 and E-280-06 all edit this file before this story runs, and anchors in it went stale inside a week during E-271.

The tier table and `#### THE FROZEN-STATE CHECK` are both under Step 5. AC-2's edit touches the check block and Step 5a's confirmation step; AC-1's touches the tier table only.

The mechanism for AC-2 is claude-architect's to choose; the ACs state properties, not commands. `git diff --quiet --cached <tree> -- <paths>` was measured to work and is offered as a starting point, not a requirement.

## Dependencies
- **Blocked by**: **E-280-06** (both stories modify `.claude/skills/implement/SKILL.md`; 06's edit is line-1 frontmatter plus trigger-body removal, this story's is body seam work — 06 lands first so this story sees its final text)
- **Blocks**: **E-280-07** (its AC-1c verifies layer-wide against the finished state of this file)

## Files to Create or Modify
- `.claude/skills/implement/SKILL.md` (modify)

## Agent Hint
claude-architect

## Handoff Context
- **Produces for E-280-07**: the final shape of the routing seam and the frozen-state check, which 07's layer-wide verification reads.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Both edits verified by absence, with the old forms shown gone
- [ ] No regressions in existing tests
