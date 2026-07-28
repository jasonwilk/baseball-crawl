---
name: e278-game-identity
description: E-278 (game identity / date derivation) — story order, the two opposite-polarity date mechanisms, why GC's record is not ground truth, and the review-process findings worth reusing
metadata:
  type: project
---

**Canonical record is `epics/E-278-game-identity/epic.md`. Prefer pointing at it over
restating.** This file carries only what a cold reader would not get from the epic, plus the
process findings that outlive it.

## State

READY 2026-07-28. 4 stories, SE-only dispatch team. Planning ran through 8 review passes.

**Execution order is FIXED at 04 → 02 → 01 → 05**, not a preference. Three stories share
`tests/test_loaders/test_game_dedup.py`, and 04 moves the `game_date` that 02's dedup groups
candidates by — so dedup behavior must be defined against corrected dates. **01 was
originally listed as independent; that was false.**

## The three things most likely to be destroyed by a later reader

1. **Two date mechanisms with OPPOSITE polarity.** Unresolvable tz alias = **+1 day**;
   full-day date marker localized as an instant = **−1 day**. **A uniform date-shift repair
   fixes one population and corrupts the other.** Any repair keys off the mechanism, never
   the symptom.
2. **GC's own record is NOT ground truth.** A profile record is a raw count of *that team's
   own* schedule listings; the inflation is **per-team**, never global. And **a clean GC
   record is not evidence that no double-scoring occurred** — the opponent side of a
   double-scored game reconciles exactly *because* it received one listing. No AC targets
   matching GC, and none may be added. What survives is the coach's **display-format**
   ruling (always show the trailing `-0`), which is about format, not about the number.
3. **Fail-closed alone is a NO-OP at `_derive_game_date`.** Its existing fallback is
   `last_scoring_update[:10]` — identical *by construction* to the fail-open output, for any
   ISO-8601 string. Proved by execution across six instant shapes. A criterion phrased on the
   return value goes green while the mis-dated rows stay wrong.

## Scope boundaries that were contested and settled

- **Historical repair is a non-goal** (operator ruling); bad rows resolve by reset.
- **`tzdata` does not reach production at closure** — only at the next image rebuild. A green
  suite at closure is not evidence prod is fixed.
- **No `is_full_day` column.** The ingest-time fix reads the flag from the payload; a
  stored-row detector is only needed for historical repair, which is out of scope. One open
  tension: a Live-side recommendation to persist it for *measurement* (routed to api-scout,
  may not actually conflict since the ruling was scoped to the fix).
- **Migrations are data-engineer's domain.** I granted a routing exception for a
  comments-only migration edit and **reversed it** — DE's standing ruling rejects that exact
  rationale. See [[feedback_mechanical_unenforceability_is_not_permission]].

## Process findings worth reusing beyond this epic

- **The three-leg consistency sweep.** Table ↔ story file is not enough. Leg 3 is **prose
  that SUMMARIZES a structure** — execution-order sentences, bullet counts, dependency
  narration. Residue lands wherever a fact is stated a second time in a different notation.
- **Incorporation is itself a defect source.** Repeatedly, a correction landed and its
  predecessor stayed. Run the sweep after *every* incorporation round, not once at the end.
- **Naming sites in an AC caps the sweep at the named set.** Four independent confirmations
  across three agents. The repair: make the AC's pass/fail the **artifact** (a site list that
  must be a *superset* of a named floor), never the method.
- **A "cannot currently fail" label does not repair an unfalsifiable AC.** Re-point it at a
  reachable hazard instead of deleting or annotating it.
- **51 findings across 8 passes, 0 dismissed** — not a boast. A large share were defects my
  own incorporation introduced.

Related: [[feedback_verify_cited_facts_before_approving]],
[[feedback_router_must_not_be_a_source]].
