<!-- NO REAL NAMES OR IDENTIFIERS — no person's name, ever; for teams, orgs, ids and UUIDs use the PII-Safe Placeholder Taxonomy in `.claude/rules/api-docs.md`. -->

# Roster dedup runs only for the generated team; opponent rosters re-split

**Date**: 2026-08-10 · **Status**: `STUB` — measured under controlled serial conditions; needs a
small code chunk. **Source**: the 13-team serial regeneration repair (backup
`app-2026-08-10T145722.db`; per-team before/after table in the repair agent's report, logs in
the trainer session's scratchpad `gen-*.log`).

## The defect, measured clean of concurrency

All 13 teams healed to rows == names immediately after their OWN generation (dedup ran for
them). Five were RE-BLOATED before the pass finished — by later runs of teams they played.
Direct case: one team read 16/16 after its own run; an opponent generated two positions later
(its log carries a reconciliation line for the first team's id); final reading 28/16. Total
stock: 895 roster rows → 383 against 279 distinct names — **616 split rows healed, 104
re-created by the healing pass itself.**

Mechanism (inference; loaders do not log opponent-side roster upserts): generating team A
writes roster rows for A's opponents during the crawl, and `dedup_team_players` runs only for
A. Opponent-side writes can re-split identities that were just collapsed. League play is
cyclic, so NO generation order converges — set-wide convergence requires dedup to cover every
team whose roster rows a load touched, not just the generated team.

Coach-visible: a split identity divides one player's stats across two roster rows in that
team's report.

## Shape of the fix (spec decides)

Run the dedup pass for every team_id whose `team_rosters`/`players` rows the load wrote —
likely a loop over the load's touched-team set at the same point the generated team's dedup
runs today. Verify with the 5-team residual (ids 47, 49, 61, 43, 293 at stub time): one
serial pass after the fix should converge the whole set with zero re-bloat, measured
rows == names across ALL 13 repaired teams simultaneously.

## Deliberately not done at stub time

No second serial pass — without the fix it is whack-a-mole (heals the 5, re-splits whichever
teams they played). The 104-row residual stands until the chunk lands, then one regeneration
pass over the residual teams converges.

## Progress log

- **2026-08-10** — Stubbed from the controlled serial repair. No code, no second pass.
