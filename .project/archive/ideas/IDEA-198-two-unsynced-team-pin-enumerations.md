# IDEA-198: Two unsynced team-pin enumerations can drift

## Status
`CANDIDATE`

## Summary
`_delete_team_scoped_data` and `_TEAM_PIN_TABLES`, both in `src/reports/lifecycle.py`, are two separately hand-maintained lists of team-scoped pin tables. A new table carrying a `teams(id)` pin must be added to BOTH, and nothing enforces that.

## Why It Matters
This is the canonical-seams "second path" shape CLAUDE.md warns about: two copies drift, and the one nobody updated is the one that runs. The consequence is asymmetric and quiet — a table missing from the sweep's list leaves rows behind after an inferred deletion, and a table missing from the cascade leaves them behind after a deliberate one. Neither raises; both surface later as a foreign-key failure or an orphan count that will not converge.

The failure has already happened once in this exact area. E-273's Codex F1 finding was `game_perspectives` being missed by one of three enumerations that otherwise agreed — so the drift risk is demonstrated, not theoretical.

The divergence itself is deliberate and must be preserved: E-273 TN-4 tailored the sweep's list to omit `opponent_links` and `user_team_access`, because TN-7 makes those reachability ROOTS that the sweep must never delete from. So the fix is not to unify the lists — unifying them would drag the two root tables back into the sweep's delete path and undo TN-7. The fix is to make the relationship legible and the drift detectable.

## Rough Timing
Promote when a new table with a `teams(id)` foreign key is added, which is the moment the drift can actually occur. No urgency otherwise — the current lists are correct as of E-277.

## Dependencies & Blockers
- [ ] None. This is independently actionable.

## Open Questions
- Is a reciprocal docstring cross-reference sufficient, or is a test that asserts the relationship between the two lists worth the machinery? Data-engineer's view during E-277 discovery was that cross-references are adequate and that unifying would fight a deliberate decision; PM agreed. A test would have to encode which tables are legitimately in one list and not the other, which risks becoming a third copy of the same knowledge.
- If a cross-reference is the answer, it should name the RULE rather than merely point — something a reader can act on, such as that a new `teams(id)` pin table belongs in both and that this list deliberately omits the TN-7 roots. A bare "see also" teaches nothing and the next reader will assume one list is stale.

## Notes
Surfaced by data-engineer during E-277 discovery (2026-07-26) as a finding beyond the audit handoff's scope. **Operator explicitly DECLINED building it in E-277** and asked that it be captured here with the drift risk stated, so it is on the record rather than lost. E-277's Technical Notes TN-6 records the decline.

Related: `.claude/rules/canonical-seams.md` is the canonical statement of the second-path defect class.

---
Created: 2026-07-26
Last reviewed: 2026-07-26
Review by: 2026-10-24
