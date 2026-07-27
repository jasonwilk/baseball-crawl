---
name: e277-reclamation-followups
description: E-277 state, and the dispatch-process findings that are NOT recoverable from the epic file
metadata:
  type: project
---

**Do not re-derive this epic's content from here — `epics/E-277-reclamation-followups/epic.md` is canonical**, and its **TN-15** carries ~23 dispatch findings each marked ESTABLISHED or ASSERTED with its source. This file holds only what the epic does not, plus pointers.

## State at PM drain (2026-07-27)
- **Story 01 DONE** — keep-root, per-root rationale, three-round remediation. Its `## PM AC Verdict` section carries the verdicts AND a provenance split (what PM read vs. took from `se`/`cr`). **AC-9 was ruled PASS → FAIL → PASS by one reviewer; the split is what makes that verdict usable.**
- **Story 02 — implementation DELIVERED and green, ACs REVISED AFTER delivery** from a pre-implementation spec audit (8 findings). So its gaps are **remediation, not fresh work**.
- **Story 03 — AC-2.1 rewritten** around the invariant `_RECLAIM_CHUNK <= limit < seeded_count`. **04 and 05 unstarted.**

## The three things most likely to be destroyed by a well-meaning successor
1. **Story 02 AC-5b's ORDER is the entire mechanism**: derive the hand-off matrix from code and record it, THEN read the reference list as a floor against shrinkage. **Collapsing it back into "measure these eight" destroys it** — that hands over the enumeration, which is the defect AC-5b exists to prevent. I authored exactly that contradiction in my first draft.
2. **AC-5b does NOT deliver two independent measurements and says so.** The implementer's six-shape pre-question run was independent; its re-derivation is **prompted**, because clarifying questions encoded shapes from the reviewer's matrix. **Do not "restore" the stronger claim.**
3. **Whether the DELIVERED guard is inert on live shapes is UNMEASURED.** The measurement that exists is pre-guard. No AC may assume otherwise.

## Deferred deliberately — do not "fix" early
**`MEMORY.md`'s numbering advance and the Active→Archived flip wait for closure**, because a sibling epic was concurrently consuming epic and idea numbers and any counter written mid-flight is stale on arrival. **This file and `feedback_decide_and_disclose.md` both still need `MEMORY.md` index lines** — a memory with no index entry is a memory that will not be recalled.

## Process findings that are mine rather than the epic's
- **The seam for draining a PM is between "ACs written" and "implementation verified"**, not at a story boundary. Writing ACs needs the AC history and does not transfer; verifying an implementation against complete property-shaped criteria does. Draining at a story boundary puts the hard-to-transfer work at the PM's weakest point.
- **"Durable" is not being on disk — it is being inside the artifact that ships.** A carry-forward brief in a session scratchpad never rides the closure patch. Cost measured: a pattern-narrowing I found and reported *in a message* recurred hours later and nearly produced a fabricated finding.
- **A status carried across a handover must carry what would CHANGE it.** "HELD" without its release condition can be closed by nobody but its author — the state a drain destroys.
- **Withdrawing an authority and rescinding its instructions are two acts.** A lead withdrew a takeover that had also assigned a completed story for re-implementation; only the first act happened. Confirm the second explicitly.
- **Conceding is not automatically the rigorous move** — giving up a correct position because giving it up feels disciplined is a way of being wrong that looks like being careful. Fired twice in one exchange, once in me.

Related: [[feedback_decide_and_disclose]].
