# IDEA-187: data-engineer's Health-Gate Memory States the Invariant in E-276's Superseded Form

## Status
`CANDIDATE`

## Summary

`.claude/agent-memory/data-engineer/health_gate_prior_set_must_be_temporal.md` states the reconcile-at-load health-gate invariant in a **superseded** form — the same framing E-276 had to correct in its own TN-10 before it could ship. Two separable defects in one file, and **E-276 structurally cannot fix either**, because agent-memory content is edited only by the owning agent and data-engineer is not on E-276's dispatch team.

> **⚠️ DO NOT CALL IT "the pre-conjunction form."** E-276 **ships no conjunction** — that interim design was dropped 2026-07-25. Describing the memory as pre-conjunction measures it against a design that does not exist, which is the same class of error as the staleness this idea reports. **The baseline is the CURRENT TN-10: one gate per grain** — the corrected (pre-upsert snapshot) gate on game and player-line, and **no floor gate at all on roster**, whose permit is a non-empty fresh payload AND `MAX_ROSTER_DEPARTURES`. E-276's story 05 AC-9 carries this same prohibition.

**Defect 1 — the invariant.** The file's opening claim and its "required wording" say a prior-vs-fresh ratio gate "must specify **when** `prior` was captured", as though the temporal clause were the whole answer. Under the shape E-276 actually ships, the temporal clause is **necessary but NOT sufficient**, and the file states only the necessary half. Two things it therefore gets wrong. **First**, a set read *after* the fresh upsert satisfies "same population on both sides" perfectly while measuring `|fresh| >= |stale|` — which is not a health gate at all, and is exactly why the original defect survived four review layers. **Second**, the shape is **per grain**: game and player-line run the corrected gate over the pre-upsert snapshot, while **roster runs no floor gate whatsoever** — so a required wording phrased as one rule for all three is wrong on the third regardless of how the temporal clause is stated. TN-10's replacement paragraph carries both halves and the per-grain scope; that is the text to copy.

**This is worse than ordinary staleness: the file is internally inconsistent.** Its later paragraph ("Prefer a gate whose safety does not depend on your own reasoning being right") states a **conjunction**, names it as E-276's landing point, and gives what was then the right reason. So the file contains two different framings three paragraphs apart with nothing marking which supersedes which — and the superseded one is the *headline*, carried in the `description:` frontmatter that decides whether the memory is recalled at all. **⚠️ And the design has moved again since: with the conjunction dropped, BOTH paragraphs are now wrong in different ways**, so this cannot be resolved by preferring the later one. That is what makes it a rewrite rather than a deletion.

**Defect 2 — the refuted count reconciliation.** The same file's "Quantified" failure-shape bullet records the divergence-count dispute as one population over four sweep bounds — *"the same criteria give 15 / 26 / 100 / 222 as the sweep range moves 0..3 / 0..4 / 0..8 / 0..12"* and *"a colleague's independently-bounded sweep collapsed to the identical 3 shapes."* That reconciliation was **contested during E-276's final triage — and the outcome is substantially more favourable to the memory than this idea first claimed. Defect 2 is hereby DEFLATED, not merely reworded.**

⛔ **The check this idea previously cited as decisive is itself REFUTED, as a UNIT ERROR, and must not be cited by anyone.** It read: *"had the 222 population carried the cap it could not have reached 222, since `a < b` with `b ≤ 2` forces `p ≤ 3` at any sweep range."* That inequality bounds the **pre-load roster size** — it says nothing about the number of swept parameter *combinations* realising those shapes, because the remaining swept parameters still range freely. **222 counts combinations; 3 counts shapes.** The counterexample was in everyone's hands the whole time: the colleague's own sweep **does** carry the cap and still scales 20 → 26 → 44 across three spaces with a byte-identical shape set.

**What survives, and it is a framing rather than a refutation**: always name **which** divergence a count measures — corrected-gate refusal, gate-VALUE difference, or observable-outcome difference. Of that account's three row assignments, one is now source-verified (the colleague's sweep measures the **observable-outcome** population, not corrected-gate refusal) and **what the 222 measured remains OPEN.** Meanwhile the memory's own reading — one criteria set over four sweep bounds — is the **artifact-of-bounds** account, which is the **best-supported** one on the evidence: the four figures fit a single enumeration `c(n) = (3n−2)(n−1)/2` exactly at four points.

**So Defect 2 shrinks to one narrow claim that does hold**: the bullet's *"a colleague's independently-bounded sweep collapsed to the identical 3 shapes"* **overstates independence.** That sweep pre-filters on DE's own boundary, so it explores *within* the derivation rather than arriving at it independently — accurate wording is *an analytic derivation confirmed by execution over an added axis*. **The magnitude claim ("the reconciliation was refuted") is withdrawn.**

The *lesson* the bullet teaches — a sweep count carries its bounds, say the frame or drop the count — is **correct and worth keeping**, and so now is most of its worked example. **Recorded at this strength deliberately**: E-276 spent four successive wrong reconciliations on this gap, each adopted because it corrected its predecessor, and *refuting a counter-argument supplies no argument for the original account*. An idea that reports a defect larger than the one that exists is unusable in the same way an inflated tally is.

## Why It Matters

Agent memory is recalled and acted on without the epic that produced it. A data-engineer instance consulted on any future ratio/parity/retire gate loads this file and gets the superseded invariant as the headline claim, with the corrected version buried below it and unmarked. E-276's whole thesis is that a locally-true claim propagates unverified because its truth-condition lives elsewhere — **this file is that thesis pointed at the record of itself.**

The second defect compounds it: a memory that teaches "state the frame, not the number" while carrying a worked example whose frame is wrong is the most persuasive possible form of the error, because the surrounding lesson vouches for it.

## Rough Timing

Not blocking, and deliberately not folded into E-276. Resolve at the **earliest** of:

- **E-276 closure.** The Learning-Loop Lifecycle's Deletion-Side Eviction sweep (`.claude/rules/context-layer-assessment.md`) fires here by construction: E-276 retires two claims that live in this file. The rule's ownership clause is the operative one — whoever runs the sweep MAY read any agent's directory to identify hits, but **only the owning agent edits its own content**, and E-276's Dispatch Team is software-engineer + claude-architect. So the sweep produces a *flag*, and this is the follow-up that flag lands in.
- The next time data-engineer is spawned for any reason — a short correction message is far cheaper than an epic, and DE is the only party who can make the edit.
- Any future work on a prior-vs-fresh ratio gate, where the file would be recalled and acted on.

## Dependencies & Blockers

- [ ] E-276 lands first. Correcting the file to describe a design that has not shipped would swap one inaccuracy for another, and the corrected wording to copy is E-276's TN-10 replacement paragraph.
- [ ] Requires **data-engineer** specifically. Not a blocker on evidence or scope — a blocker on ownership.

## Open Questions

- Does the `description:` frontmatter need rewriting too, or only the body? It currently front-loads the superseded claim, and the description is what decides recall — so a body-only fix leaves the misleading half in the position that matters most.
- Keep the temporal clause as the headline with "necessary but **not sufficient**" attached, and add the per-grain shape (roster has no floor gate). E-276's TN-10 chose exactly that for the module docstring, on the grounds that the sufficiency note is the transferable part. The same reasoning probably applies here, but it is DE's call. *(An earlier form of this question offered "state the conjunction as the headline" as the alternative — that option no longer exists.)*
- Are there sibling memories with the same inheritance? The file links `[[games_row_vs_stat_rows_coupling]]`, `[[schema_drop_test_blast_radius]]` and `[[scouting_query_role_vs_dedup_filters]]`, none of which has been checked against E-276's settled shape.

## Notes

**Found by reading the file, not by grepping for the claim** — and that is the part worth carrying. The superseded invariant shares most of its vocabulary with the corrected one ("prior", "captured", "before this run's writes"), so a token grep for the retired claim returns the *corrected* passages too and reads as clean. This is `.claude/rules/doc-sweep.md`'s retired-claims-survive-in-forms-carrying-none-of-their-tokens case, in its hardest variant: the retirement was a **narrowing**, not a deletion, so the retired and surviving forms are near-homographs.

Related: [[IDEA-185]] and [[IDEA-186]], the two residuals routed out of E-276 on substance. This one is routed out on **ownership** instead — the epic knows about it and is not permitted to fix it.

---
Created: 2026-07-25
Last reviewed: 2026-07-25
Review by: 2026-10-23
