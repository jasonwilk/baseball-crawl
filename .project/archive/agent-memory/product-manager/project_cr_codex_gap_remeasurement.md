---
name: cr-codex-gap-remeasurement
description: PM process obligation (agentic-flow-review item 25). RETIRED 2026-07-13 (operator-confirmed) — E-251-pivot hypothesis permanently unanswerable (schema postdates E-251) + no live decision consumes a re-armed trigger under the E-260 freeze. Corrected forward design (post-E-260, Codex-running, N=5) preserved DORMANT + non-self-triggering.
metadata:
  type: project
---

# RETIRED 2026-07-13 (operator-CONFIRMED; corrected forward design kept DORMANT)

**Operator confirmed 2026-07-13: RETIRE + keep the corrected forward design DORMANT.** An interim run happened 2026-07-13; its report is kept as the honest record (`.project/research/2026-07-13-cr-codex-gap-remeasurement.md`, banner "record of a one-time interim run — does NOT close item 25"). Best-available answer: **structural-class CR-misses dominate the post-E-251 gap; the reviewer-quality "narrowing" claim is unprovable with ANY scorecard cohort.**

## Why RETIRED (not re-armed)

1. **The pre/post-E-251 pivot is permanently unanswerable.** Item 25 wanted a pre-E-251 vs post-E-251 per-class comparison. The canonical Review Scorecard schema landed at E-255 (2026-07-08), which POSTDATES E-251 (2026-07-05). Every canonical-scorecard epic is already post-E-251; there is NO pre-E-251 canonical-scorecard cohort and there never can be. Waiting produces more post-E-251 epics, never the missing "pre" term. No future run rescues the hypothesis as written.
2. **Proportionality — a re-armed trigger would feed no live decision.** Item 25's stated purpose (E-258-04) was to calibrate *further rubric spend*. Under the E-260 meta-layer freeze (except defect-cited changes), no rubric epic is planned, so a standing re-armed trigger would inform nothing; the interim report's own forward lever — the fix is *coverage* (run Codex on more epics), not more rubric edits — holds regardless of any future tally. Proportionality bars standing machinery that informs nothing.

(For the record, the original trigger also counted the wrong thing — *scorecard-bearing* epics, not Codex-RUNNING ones; only 3 of 6 in the just-tripped cohort ran Codex — and its cohort was confounded by the 2026-07 platform-program burst, E-258 rubric-hardening + E-260 meta-epic mid-sample. The dormant design below corrects both.)

## Corrected forward design — DORMANT, NON-self-triggering

Preserved so it can be pulled **deliberately** if — and ONLY if — a future defect-cited review-quality problem justifies a rubric edit (the E-260 freeze's own exception). It does NOT self-trigger; PM's every-closure backlog review must NOT re-arm it on epic-count alone.

- **Reframed question:** not "did E-251 help" (dead), but "on a review-system-STABLE, post-freeze cohort, what is the residual CR-vs-Codex gap and which classes does it live in?"
- **Corrected condition (N=5):** ≥5 epics closed AFTER E-260 (COMPLETED 2026-07-12) that EACH ran a Codex dispatch/closure pass (plain-"implement"/per-story-CR-only does NOT count — fixes the count-the-wrong-thing defect; post-E-260 anchoring removes the burst confound). E-261 + E-262 (both ran Codex) already = 2 toward that 5, if ever pulled.
- **Report shape:** per-class CR-missed / Codex-caught, structural vs reviewer-quality buckets per AGENTIC-FLOW-REVIEW §3.3; state plainly the pre-E-251 comparison is unmeasurable (the §3.2 taxonomy is the only "before" that exists).
- **Unavoidable population bound:** only measurable where Codex ran (operator opted into "and review") — the definition of the measurable population, not a bias to fix.

**Status: RETIRED. Not armed, not self-triggering. Promote the dormant design above only on a fresh defect-cited rubric decision.**

---

# (Historical) Original deferred obligation: CR-vs-Codex gap re-measurement (agentic-flow-review item 25)

Installed by **E-258-04** (2026-07-08). This is a tracked PM process/measurement obligation, NOT a product idea and NOT a per-closure context-layer gate (a gate that no-ops for five epics then fires once would be recurring noise). It is self-triggering under PM's existing every-closure cadence.

**What to do when it fires:** re-tally the CR-vs-Codex finding gap across the qualifying epics and report whether the **routing-era hypothesis** (AGENTIC-FLOW-REVIEW.md §3.3) held — namely that after E-251 replaced bare `general-purpose` review spawns with defined agents, the **reviewer-quality** defect classes narrowed while the **structural** classes (cross-cutting integration / mirror-path drift, concurrency, security) did NOT. Compare per-class CR-missed-but-Codex-caught counts pre- vs post-E-251, drawing from each qualifying epic's Review Scorecard table.

**Countable fire-condition:** ≥5 epics **archived after 2026-07-08** carrying the **canonical Review Scorecard schema** (the schema landed in E-255). How to count it: enumerate `/.project/archive/` for epics closed after 2026-07-08 and count those whose `epic.md` contains a Review-Scorecard table under `## History` (the canonical schema). When that count reaches 5, run the tally in that closure.

**Not run at E-258 closure — precondition unmet.** As of 2026-07-08 the count is definitively **zero**: only four epics (E-252/253/254/255) have closed since E-251, and the canonical scorecard schema landed only in E-255 (2026-07-08) — so no epic has yet closed *under* it. E-258 INSTALLS the trigger; the tally executes in the future closure at which the count reaches 5. **Do not fabricate tally figures before then** — there is no data to report yet.

**How it surfaces:** PM's mandatory every-closure memory-retirement / backlog review reads MEMORY.md (always loaded) where this obligation is pointed to under "Pending Process Obligations." At each closure, re-check the count; execute the tally in the closure where it first reaches 5, then retire this obligation.

Related: this closes the empirical loop behind the E-258 structural rubric edits (E-258-01/02/03) — those edits ASSUME the structural classes need direct rubric coverage; this measurement is the check on whether that assumption (and the routing-era prediction) was borne out. See the E-258 epic and AGENTIC-FLOW-REVIEW.md §3.2/§3.3.
