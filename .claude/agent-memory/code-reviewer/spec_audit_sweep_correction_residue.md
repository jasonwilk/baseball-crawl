---
name: spec-audit-sweep-correction-residue
description: In a spec audit, the surviving defects concentrate in the STALE COPIES of claims corrected elsewhere in the same file — sweep each correction's residue, not whether the correction landed.
metadata:
  type: feedback
---

When auditing an epic that carries dated correction markers ("CORRECTED 2026-xx-xx", "SPLIT",
"RE-ATTRIBUTED", "do not restore this"), do NOT audit whether the correction is present and
right. Audit whether the RETIRED claim survives anywhere else in the same document.

**Why:** E-278 iteration 2. Between my two passes the planning lanes landed substantial,
genuinely good revisions — and **all five surviving MUST FIX items were stale copies of claims
corrected elsewhere in the same file.** One class of defect, not five:

- TN-5 gained an explicit SPLIT (offline discriminator vs. load-time rule) and a story gained an
  AC forbidding the retired rule — while **Success Criterion 2 still stated the retired rule**.
  The criteria are what closure is judged against, so the epic could satisfy its corrected TN and
  fail its own Success Criterion.
- TN-3 carried a correction block refuting a fail-closed mechanism, and OQ-8 later strengthened
  the refutation from "byte-identical on our data" to "identical by construction" — while
  **TN-14's fix-surface list still stated the refuted mechanism verbatim**, and TN-3 itself
  propagated it by saying that item "stands" (endorsing its wording, not just its direction).

The generative asymmetry: a correction is written by someone who has just understood the problem
and is looking at ONE location. The claim's other copies were written earlier, by the same person,
somewhere they are not currently looking. Nobody re-greps their own retired sentence.

**How to apply:** For each correction marker in a spec, extract the retired claim's PROPOSITION
(not its wording — the copies rarely share tokens) and sweep the whole document for it, weighting
Success Criteria, Goals, and fix-surface lists highest, because those are the sections a closure
or an implementer reads as authoritative. Report the residue as its own finding class so triage
sees one sweep rather than five unrelated edits. Related: [[enumerate-backwards-from-the-cited-artifact]],
and `.claude/rules/doc-sweep.md` on judgement-not-wording sweeps.

**A second, separate practice this epic forced — a planning-phase spec audit runs against a MOVING
target.** Four of six E-278 files were rewritten while I audited them (`epic.md` changed 5 seconds
before my re-read), because holistic lanes were revising concurrently. My first report was an audit
of superseded text and I did not notice; **the team lead told me, I did not detect it.** So:
`stat -c '%y' <files>` at the START of the audit and again BEFORE finalizing, and compare. This is
the planning-phase twin of [[closure-diff-growth-after-integration-review]] — same shape, different
phase: the artifact moves after the pass that judged it, by design, and the reviewer is the last to
know. When re-auditing moved text, publish an explicit label map (old finding IDs → new ones, with
FIXED / carried / retracted per item) or triage will double-count.
