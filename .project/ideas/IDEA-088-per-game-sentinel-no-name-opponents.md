# IDEA-088: Per-game sentinel for genuinely no-name unresolvable opponents

## Status
`CANDIDATE`

## Summary
The E-245-04 self-game fix routes a truly-unresolvable opponent (no stat-block key, no
UUID, no schedule name) to a SHARED "Unknown Opponent" sentinel team. If two genuinely
no-name opponents played the SAME tracked team on the SAME date, both would resolve to
`{own, shared-sentinel}`, and `_find_duplicate_game`'s natural-key dedup (`game_date` +
unordered `{home_team_id, away_team_id}`) would treat them as one game and merge/redirect —
conflating two distinct games' plays. Closing this would give the no-name path a per-game
sentinel (the loader already uses a game-suffixed sentinel for the pathological "own team is
itself named the sentinel" case — same technique), so each no-name game gets a distinct
opponent row.

## Why It Matters
Prevents silent cross-game plays conflation for a remote-but-real data shape. The sentinel
path is already strictly better than the self-game (`home == away`) bug it replaced, and the
real 23 self-games this epic fixed do NOT hit this edge (they all resolve by NAME → distinct
opponent rows). This is hardening for a corner the current data never exercises — capture
now so it is not rediscovered later, but no present pain.

## Rough Timing
Someday / nice-to-have. Promote if/when the no-name-opponent path actually occurs in live
data (two no-name opponents, same tracked team, same date) — or if a coach reports a game's
plays looking merged. No urgency; the 23 known self-games are fixed by name resolution.

## Dependencies & Blockers
- [x] E-245-04 (self-game fix) merged — establishes the shared-sentinel path this refines.
- [ ] Evidence the no-name-opponent shape occurs more than once per team+date (today it does
      not — all real self-games resolve by name).

## Open Questions
- Does the no-name path ever actually fire in production, or do all opponents carry at least
  a schedule name? (If the latter, this edge is unreachable and the idea can be DISCARDED.)
- Per-game sentinel naming: reuse the `"Unknown Opponent (<event_id>)"` suffix pattern the
  loader already uses for the pathological case, or a different distinct key?
- Does a per-game sentinel create a proliferation of one-off opponent rows worth a periodic
  cleanup pass, or is it acceptable as-is?

## Notes
Source: code-reviewer SHOULD-FIX on E-245-04, explicitly framed as awareness-only (NOT a
within-AC defect — AC-2 sanctioned the shared sentinel stub). PM concurs: out of E-245-04
scope, captured as an idea rather than a fix; E-245-04 closure is not blocked on it. The
loader's existing game-suffixed sentinel fallback (the `_resolve_team_ids` pathological-case
branch) is the proven technique for the close. Related: [[IDEA-044]] (prevent duplicate team
creation), [[IDEA-087]] (cause-4 attribution drift, also scoped out of E-245).

---
Created: 2026-06-29
Last reviewed: 2026-06-29
Review by: 2026-09-27 (90 days from created)
