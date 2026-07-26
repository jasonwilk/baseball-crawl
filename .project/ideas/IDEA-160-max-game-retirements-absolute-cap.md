# IDEA-160: `MAX_GAME_RETIREMENTS` — give the game grain the absolute cap the roster grain already has

## Status
`IMPLEMENTED` — **shipped in E-270-01, 2026-07-25.** `MAX_GAME_RETIREMENTS` exists in `src/db/reconcile_at_load.py`, composed into the game grain's `extra_guard` alongside the boxscore-completeness signal.

**⚠️ The status read `CANDIDATE / READY TO IMPLEMENT` until 2026-07-26** — nine months of ledger drift in one week. **It was never formally promoted**: it landed as one of the four blocking envelope fixes the E-267 Fable audit required, inside another epic, and nothing closed the loop back to this file. *(Found by code-reviewer during story E-276-03's TN-9 sweep of `.project/`, not by any ideas-backlog review. **Filing the idea and shipping the idea were done by different epics, and only the second one knew.**)*

<!-- HISTORICAL, kept as the reasoning that made it bundle-ready — superseded by the IMPLEMENTED status above.
     READY TO IMPLEMENT — this needs NO further scoping or research. It is one story, so it cannot be
     an epic under the two-story rule, but it does not fit the research/idea profile either: it is
     fully specified and unblocked. BUNDLE-READY, following the E-262 Post-Program Housekeeping
     precedent where small concrete items accumulate as ideas and ship together.
     Surfaced by the independent Fable review at E-267 closure, 2026-07-20. Deferred deliberately —
     it is HARDENING, not a defect fix. -->

## Summary
E-267's roster grain got an absolute drop cap (`MAX_ROSTER_DEPARTURES = 2`) on top of the universal `FLOOR_RATIO`, on the reasoning that "a 12-15 player roster makes the flat 0.5 floor far too loose." **A 20-30 game season is equally small and equally bounded, and the game grain got no equivalent cap.** Give it one: `MAX_GAME_RETIREMENTS`, supplied through the existing `extra_guard` seam.

**⚠️ "on top of the universal `FLOOR_RATIO`" IS NO LONGER TRUE OF THE ROSTER GRAIN** *(scoped 2026-07-26; **do NOT delete this Summary — its requirement is still valid**)*. **E-276-03 REMOVED the roster grain's floor entirely**, so `MAX_ROSTER_DEPARTURES` is now that grain's **sole** guard, not a cap layered over a floor. **The argument survives the correction and is in fact strengthened**: the game grain still HAS a floor, so this idea's original case — *a small bounded population needs an absolute cap that a ratio cannot provide* — now has a worked precedent where the ratio was removed as unfit for exactly that reason. **What is dead is the phrase "on top of"; what is alive is everything the phrase was supporting.**

## Why It Matters — the severity ordering of the mitigations is INVERTED
This is the core of the argument and the reason it is worth doing:

- The **roster** grain — which received the stricter protection — fails as *"grid clutter, never a corrupted stat"* **by the code's own words**. A stale roster row is cosmetic.
- The **game** grain — which received only the flat ratio — hard-deletes a `games` row plus its **full child surface**: batting and pitching lines, `plays`, `play_events`, spray charts, reconciliation records. That is irreversible stat-data destruction.

The grain with the milder failure mode has the stronger guard. That asymmetry is not defensible on its own terms.

## Worked scenario
A truncated-but-HTTP-200 schedule returns 12 of 20 prior-loaded games:
- `comparable = 12`, `prior_count = 20`
- floor test: `12 >= 0.5 * 20 = 10` → **PASSES** → crawl judged authoritative
- **8 live games hard-deleted with their full child surface** — including every `plays` / `play_events` row feeding the E-257 reconciliation scoreboard.

No cap exists to stop it.

## This is HARDENING, not a defect fix
The floor ratio is weaker protection, not absent protection — which is precisely why this was deferred at E-267 closure rather than fixed there. Do not file or prioritize it as an active data-loss bug.

## Implementation shape (fully specified — no design work needed)
- `extra_guard` on `classify_absences` is the already-sanctioned narrowing seam, and its narrowing-only property is structural (E-267-01 AC-2).
- `roster_departure_guard` in `src/db/reconcile_at_load.py` is the working precedent to mirror.
- So: one constant + one guard function + tests. Calibrate the constant against a real season length; the roster cap of 2 was DE-locked per TN-12 and the game-grain number needs its own justification, not a copied value.

## THE TRAP TO AVOID — count the right population
**The roster cap hit this exact problem and had to be corrected.** It initially counted backfill churn alongside genuine departures and **deadlocked permanently** for any team with 3+ cut-but-already-played players — the guard restored the very hazard it was meant to prevent. Whatever the game-grain cap counts, verify it measures the thing the cap exists to detect (genuine removals), not an inflated population that includes rows some other mechanism re-creates every run.

## Test requirements (non-negotiable — this pattern caught three false-confidence tests in E-267)
1. **The cap must fire where the floor would NOT.** Size the fixture so the floor ratio PASSES and only the cap refuses. A fixture that also fails the floor proves nothing about the cap. **⚠️ The roster analogy this bullet used — *"14 prior / 9 fresh / 5 absent: `9 >= 7` clears the floor, `5 > 2` trips the cap"* — is STALE and must not be copied** *(scoped 2026-07-26)*: **E-276-03 removed the roster floor**, so on that grain there is no longer a floor for a fixture to clear, and the two-guard sizing it illustrates no longer exists there. **The requirement is unchanged and still applies to the GAME grain, which does still have a floor** — construct the sizing against the game grain's own numbers rather than porting these.
2. **The two refusal causes must stay distinguishable in the WARN** — assert `floor_ratio` in the floor case and the cap constant in the cap case, so the two guards cannot mask each other in the suite and an operator can tell a truncated crawl from a legitimate bulk change.

## Notes
- Source: independent Fable review at E-267 closure, 2026-07-20.
- Related: [[IDEA-158]] and [[IDEA-159]] (the other two game-grain retire findings from E-267 closure) — if any of the three is picked up, review all three together, since they all touch the same retire path.
- Precedent for the bundle container: E-262 Post-Program Housekeeping.

---
Created: 2026-07-20
Last reviewed: 2026-07-20
Review by: 2026-10-18
