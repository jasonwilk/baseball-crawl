---
name: cr-codex-gap-remeasurement
description: Deferred PM process obligation (agentic-flow-review item 25) — re-tally the CR-vs-Codex finding gap once ≥5 epics have closed under the canonical Review Scorecard schema; installed by E-258-04, NOT yet run.
metadata:
  type: project
---

# Deferred obligation: CR-vs-Codex gap re-measurement (agentic-flow-review item 25)

Installed by **E-258-04** (2026-07-08). This is a tracked PM process/measurement obligation, NOT a product idea and NOT a per-closure context-layer gate (a gate that no-ops for five epics then fires once would be recurring noise). It is self-triggering under PM's existing every-closure cadence.

**What to do when it fires:** re-tally the CR-vs-Codex finding gap across the qualifying epics and report whether the **routing-era hypothesis** (AGENTIC-FLOW-REVIEW.md §3.3) held — namely that after E-251 replaced bare `general-purpose` review spawns with defined agents, the **reviewer-quality** defect classes narrowed while the **structural** classes (cross-cutting integration / mirror-path drift, concurrency, security) did NOT. Compare per-class CR-missed-but-Codex-caught counts pre- vs post-E-251, drawing from each qualifying epic's Review Scorecard table.

**Countable fire-condition:** ≥5 epics **archived after 2026-07-08** carrying the **canonical Review Scorecard schema** (the schema landed in E-255). How to count it: enumerate `/.project/archive/` for epics closed after 2026-07-08 and count those whose `epic.md` contains a Review-Scorecard table under `## History` (the canonical schema). When that count reaches 5, run the tally in that closure.

**Not run at E-258 closure — precondition unmet.** As of 2026-07-08 the count is definitively **zero**: only four epics (E-252/253/254/255) have closed since E-251, and the canonical scorecard schema landed only in E-255 (2026-07-08) — so no epic has yet closed *under* it. E-258 INSTALLS the trigger; the tally executes in the future closure at which the count reaches 5. **Do not fabricate tally figures before then** — there is no data to report yet.

**How it surfaces:** PM's mandatory every-closure memory-retirement / backlog review reads MEMORY.md (always loaded) where this obligation is pointed to under "Pending Process Obligations." At each closure, re-check the count; execute the tally in the closure where it first reaches 5, then retire this obligation.

Related: this closes the empirical loop behind the E-258 structural rubric edits (E-258-01/02/03) — those edits ASSUME the structural classes need direct rubric coverage; this measurement is the check on whether that assumption (and the routing-era prediction) was borne out. See the E-258 epic and AGENTIC-FLOW-REVIEW.md §3.2/§3.3.
