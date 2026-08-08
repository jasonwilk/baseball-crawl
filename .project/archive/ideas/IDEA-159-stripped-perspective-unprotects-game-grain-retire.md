# IDEA-159: A Stripped Perspective Un-Protects the Game-Grain Retire — live mechanism, currently zero instances

## Status
`CANDIDATE`
<!-- Surfaced during E-267 closure (2026-07-20) by code-reviewer, with the live-data question settled
     by api-scout before merge. Deliberately labelled "LIVE MECHANISM, CURRENTLY ZERO INSTANCES" —
     this is NOT hypothetical, and it is NOT currently occurring. Both halves matter. -->

## Summary
The game-grain retire's last-resort safety net is `_other_perspectives()` in `src/db/reconcile_at_load.py`, which refuses to hard-delete a `games` row that another perspective also loaded. **That protection holds only while the game carries ≥2 perspectives**, and an ordinary operation can strip it to one:

1. A cross-perspective twin is merged, so one `games` row carries two `game_perspectives` rows.
2. The counterpart team is later deleted — an ordinary report deletion. `cascade_delete_team` (`src/reports/lifecycle.py:451`) deletes that team's `game_perspectives` rows, while `:353-356` deliberately KEEPS the `games` row because another perspective remains.
3. The game now carries ONE perspective. `_other_perspectives()` returns empty and refuses nothing.
4. On the survivor's next re-scout, if the redirect ALSO misses, the game is absent from the fresh set and is hard-deleted with its full child surface.

Step 4's redirect miss is the realistic part: a doubleheader date, or the **~30-minute per-perspective `start_time` disagreement GameChanger produces routinely**, is enough.

## Live-data status (api-scout, 2026-07-20, pre-merge)
- **Q1: zero rows.** All 22 perspective-artifact games carry exactly two perspectives — every one protected by `_other_perspectives()` today.
- **Q3: zero instances** of the unprotected shape across all 561 stored games, with complete coverage (17 perspective teams, all probed).
- **Q2 denominator note:** the 22 figure is already **perspective-scoped**, using the same predicate as `_prior_loaded_game_ids`, so it is the correct retire-candidate count. A membership-scoped count would have been 41. An early concern that 22 was the wrong denominator was inverted — 22 is right.

**All 17 teams are `tracked`, so an ordinary report deletion is the trigger for step 2.** Nothing exotic is required.

## Why it is worth filing despite zero instances
Four conditions must coincide, so it is not likely. But **every individual step is a normal operation**, and the outcome is hard-deleting a real game plus its child surface — the exact false-delete class the whole epic exists to prevent. Zero instances today is a fact about the current database, not a property of the design.

## Two premises corrected during investigation — do not re-derive them wrongly
- **Layer 1 (`_find_duplicate_game`) DOES re-derive the redirect for prior-run merges** via the natural key. A concern that it would not was wrong. The failure is specifically **the short-circuit not firing**, not an absent redirect path.
- `cascade_delete_team` keeping the `games` row (`:353-356`) is CORRECT behavior — it prevents destroying the surviving team's data. The gap is that keeping the row while dropping the perspective silently removes the retire's protection; the deletion is not the defect.

## Scope note
The fix is NOT to widen `_other_perspectives()` — a game with one legitimate perspective must stay retirable, or removed single-perspective games become permanently unretirable (the same trap E-267-04 hit with fork members). Candidate directions: make the redirect short-circuit robust to the `start_time` disagreement, or record that a game was once cross-perspective so the refusal survives a perspective being stripped.

## Notes
- E-267-05 records the operator-facing half: the AC-5 cross-perspective refusal is also the last-resort false-delete guard for ~4% of stored game ids, so a future change narrowing it does not silently remove the only protection.
- Related: [[IDEA-154]] (the complementary residual — cross-perspective games are never RETIRED; this idea is about them being WRONGLY retired once a perspective is stripped), [[IDEA-158]] (the other game-grain retire-coverage finding from closure).
- Source: E-267 closure review, 2026-07-20. Mechanism traced by code-reviewer; live-data status established by api-scout.

---
Created: 2026-07-20
Last reviewed: 2026-07-20
Review by: 2026-10-18
