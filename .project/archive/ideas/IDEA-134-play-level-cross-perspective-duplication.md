# IDEA-134: Play-level cross-perspective duplication (17/404 games)

## Status
`CANDIDATE`

<!--
Status definitions:
  CANDIDATE  -- Active idea, worth revisiting. Default status for new ideas.
  PROMOTED   -- Became an epic. Record which one in the Notes section.
  DEFERRED   -- Deliberately set aside. Include a reason and a re-review date.
  DISCARDED  -- Decided against. Include a reason so we don't re-propose it.
-->

## Summary
17 of 404 games in the dev DB have their `plays` (and `play_events`) rows double-loaded under TWO different `perspective_team_id`s — e.g. game `035d97e2` carries 67 + 67 identical inning/half/play_order rows. This is the play-level member of the same cross-perspective duplicate family that E-261 addresses at the game-ROW level. It is NOT a correctness bug for perspective-scoped aggregates (a query that filters to a single `perspective_team_id` counts each event once — the E-263 TN-3 discipline), but it is redundant storage and a standing double-count trap for any future aggregate that forgets the perspective filter.

## Why It Matters
Surfaced by the 2026-07-13 Fable-scout discovery pass. Two open threads: (1) it confirms the perspective-scoping discipline (E-263 TN-3) is load-bearing — a naive union over these games double-counts steals/backpicks/SB; (2) it raises whether anything SHOULD collapse the redundant play rows. E-261 dedups game rows via the natural key; it does not (and arguably should not, under perspective provenance) delete one perspective's plays. So the question — is the double-load expected-and-fine (both perspectives legitimately retained) or worth a cleanup pass — falls outside E-261's game-row scope and is captured here rather than silently folded.

## Rough Timing
Low urgency — no report-correctness impact given the perspective filter. Revisit if: a future aggregate is found NOT filtering by perspective, storage/complexity becomes a concern, or E-261's dispatch surfaces a related decision about play-row handling on collapse.

## Dependencies & Blockers
- [ ] Clarify with E-261's scope: does its game-dedup leave both perspectives' plays under the canonical `game_id` (expected), or is there a genuine same-perspective duplicate hiding in the 17?
- [ ] Decide whether the double-load is by-design (perspective provenance retains both) or a load-path defect worth a one-time cleanup

## Open Questions
- Are all 17 cases two DIFFERENT `perspective_team_id`s (expected two-perspective state), or does any game have exact duplicate `plays` under the SAME `perspective_team_id` (a real UNIQUE-constraint escape / bug)?
- If cleanup is wanted, what is canonical — keep the scouted team's own perspective, keep MIN(perspective_team_id), or keep both (status quo)?
- Does E-261's `bb data merge-duplicate-games` already touch these on regen, or are they untouched?

## Notes
- Verified live on game `035d97e2` (67 + 67 identical rows). Same duplicate-identity family as E-261 (cross-perspective game-dedup) and the §8d attribution rule.
- E-263 TN-3 makes every rollup perspective-scoped, so E-263 reports are already neutralized against this — this idea is about the underlying data, not the reports.
- Source: 2026-07-13 Fable-scout discovery pass, Note A.

---
Created: 2026-07-13
Last reviewed: 2026-07-13
Review by: 2026-10-11
