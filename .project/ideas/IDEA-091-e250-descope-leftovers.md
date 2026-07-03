# IDEA-091: E-250 de-scope leftovers — programs/org-hierarchy machinery + `_derive_season_id` min-years rule

## Status
`CANDIDATE`

## Summary
Two pieces of dead-or-purposeless machinery deliberately scoped OUT of E-250 (the root cross-season de-scope) and parked here: (a) the never-read `programs` org-hierarchy machinery plus `detect_league_level`'s unused `program_type`/`classification` params, and (b) the `_derive_season_id` `min(years)` rule, which has no driving problem on single-season data.

## Why It Matters
E-250 removed the cross-season *logic* at the root (unscoped dedup corner, identity column/table, `season_type` footgun, compound-slug fixtures, stale prose). These two items are adjacent dead-code/vestigial-logic surfaces that E-250 chose not to touch to keep its blast radius bounded. Removing them later continues the "simple first, remove what isn't earning its keep" discipline and shrinks the hallucination/footgun surface, but neither is causing active harm today.

## Rough Timing
Someday / low urgency. Promote if: the `programs` machinery starts drawing agent attention or causing confusion, `detect_league_level` is revisited (overlaps IDEA-066), or a second season of data ever makes the `min(years)` rule behave surprisingly (it won't on the current single-season DB).

## Dependencies & Blockers
- [ ] E-250 (root cross-season de-scope) complete — these were carved off from it.
- [ ] For the `min(years)` rule: no driving problem exists until/unless multi-season data appears, which is a permanent non-goal — so this half may be DISCARD-worthy rather than promotable.

## Open Questions
- Is `programs` fully write-orphaned, or does any live path still populate it? (Needs a read-path/write-path trace before removal.)
- Does removing `detect_league_level`'s unused params interact with IDEA-066 (league-level detection)? Coordinate so the two don't conflict.
- Is the `_derive_season_id` `min(years)` rule better DISCARDED (dead branch on single-season data) than removed via an epic?

## Notes
Carved out of E-250 during planning (2026-07-03). The third E-250 out-of-scope item — season-agnostic overlap-confidence — was already addressed inside E-250 as the `seen_collapse_keys` comment tweak (E-250-01), so it is NOT captured here. Related: IDEA-066 (league-level detection), IDEA-081 (post-E-241 dead-code/stale-example sweep).

---
Created: 2026-07-03
Last reviewed: 2026-07-03
Review by: 2026-10-01
