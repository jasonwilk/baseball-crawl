# IDEA-139: Refresh the stale figures in the context-fundamentals worked-example block

## Status
`CANDIDATE`

## Summary
The worked-example budget block in `.claude/skills/context-fundamentals/SKILL.md` (`:160-190`) carries its own internally-consistent-but-stale figures (~697 ambient subtotal, ~1,715 total) that E-260-04 and E-262-05 both deliberately left untouched. After E-262-05 refreshed the ambient figures at `:28` (→ "730-1,000") and `:193` (→ "~780"), this block is now mildly inconsistent with them. Refresh the worked example's interdependent figures together so the whole section reflects current ambient/demand numbers.

## Why It Matters
The worked example is a teaching artifact — a reader uses it to build intuition for context budgeting, so stale figures quietly mislead. It was scoped OUT of both IDEA-118 (which E-262-05 executed for `:28`/`:193` only) and E-260-04 because it is not a one-line fix: the block sums multiple interdependent figures (ambient subtotal + demand subtotal → total) that must be re-derived together and cross-checked against the `:70-90` whole-layer budget table. The `:193`-vs-worked-example inconsistency actually PRE-EXISTED E-262-05 (was ~750 vs ~697; E-262-05 widened it to ~780 vs ~697 by refreshing `:193` alone) — so this is a genuine standing refresh, not a regression E-262 introduced.

## Rough Timing
Low urgency / cosmetic-doc accuracy. Fold into any epic already touching `context-fundamentals/SKILL.md`, or do standalone when the figures drift far enough to mislead. All context-layer line-count figures are point-in-time snapshots (the file itself says so) — use the regenerating command in the `:70-90` Context Budget section to re-derive.

## Dependencies & Blockers
- [ ] None. claude-architect owns the skill; the regenerating `find ... | wc -l` command is already in the file.

## Open Questions
- Refresh the worked example in place, or replace the hardcoded totals with a pointer to the regenerating command (so it can't re-rot)? The latter matches the `:74`/`:86` treatment E-260-04 already applied to the whole-layer figure.

## Notes
Source: E-262-05 dispatch (2026-07-13) — surfaced by claude-architect as the "#2 doc-sweep sibling" while executing IDEA-118's `:28`/`:193` refresh; ruled OUT of E-262-05 scope by PM (deliberately-deferred block, pre-existing inconsistency, coordinated multi-figure refresh). Related: IDEA-118 (ambient-figure refresh, PROMOTED → E-262-05), and E-260-04 which re-derived the `:70-90` whole-layer budget section. Domain: claude-architect.

---
Created: 2026-07-13
Last reviewed: 2026-07-13
Review by: 2026-10-11
