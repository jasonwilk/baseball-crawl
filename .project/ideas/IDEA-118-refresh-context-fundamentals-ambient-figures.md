# IDEA-118: Refresh the stale ambient per-session figures in context-fundamentals

## Status
`CANDIDATE`

## Summary
`.claude/skills/context-fundamentals/SKILL.md` still carries stale ambient per-session context figures outside the `:74-85` table that E-260-04 re-derived: `:28` ("approximately 614-886 lines of always-loaded text"), and the `:185`/`:193` example load-budget illustration. Refresh these to the current ambient subset (~638-910) and drop the "measured post-E-213 (2026-04-05)" provenance so the skill is internally consistent with the re-derived whole-layer table.

## Why It Matters
E-260-04 re-derived the whole-layer table (~12k, with a self-regenerating command) and scoped it correctly, but AC-3 scoped that story to `:74-85`, so the ambient per-session figures elsewhere in the file were left. They are NOT contradicted by the new table (they describe the ambient SUBSET, a different quantity from the whole-layer total — `:76` draws that distinction), but they are mildly stale and referencing a long-past provenance date. A consistency refresh keeps the skill from re-rotting.

## Rough Timing
Low-urgency consistency cleanup. Bundle with IDEA-117 (same file family) or the next context-layer touch.

## Dependencies & Blockers
- [ ] None (prose refresh; the regenerating command E-260-04 added can source the current numbers)

## Open Questions
- Consider giving the ambient-subset figure its own regenerating recipe (the four-subtree `find | wc -l` E-260-04 added measures the whole layer, not the ambient subset).

## Notes
Surfaced during E-260-04 AC-3 verification; PM ruled the `:28` figure non-contradicting (ambient subset, not the whole-layer total) and passed 04 as-is with this follow-up. CA owns `.claude/skills/`.

---
Created: 2026-07-12
Last reviewed: 2026-07-12
Review by: 2026-10-10
