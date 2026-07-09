# IDEA-114: Clarify CLAUDE.md's morning-run --dry-run summary-email prose

## Status
`CANDIDATE`

## Summary
CLAUDE.md's `bb report morning-run` description couples "`--dry-run` … generates nothing" with "an always-sent end-of-run operator summary email is the missed-run signal" in a way that reads as if dry-run ALSO sends the summary email. The code is unambiguous the other way: `src/cli/report.py:571` `_emit_summary_if_needed` returns early on `if dry_run:` (line 581), and line 666 states "Dry-run sends no summary, so it is exempt." Add a short clarifying clause so the prose matches the code — dry-run sends no summary.

## Why It Matters
Not hypothetical: this exact ambiguity misled the CR spec-audit during E-256/E-259 planning into flagging (finding 6) that the Step 1d closure smoke's `morning-run --dry-run` would email the operator on every run — a false positive that would have triggered a needless design consult and possibly a real behavior change, caught only by reading the code. Prose that misleads a careful reviewer is worth one sentence to fix.

## Rough Timing
Low urgency, one-line edit. Could ride any future CLAUDE.md-touching context-layer epic opportunistically, or a standalone context-layer tidy pass. Deliberately NOT folded into E-256/E-259 — it lives in a different CLAUDE.md section than those epics' eviction edits, and folding it would be opportunistic scope creep.

## Dependencies & Blockers
- [ ] None. Pure doc clarification.

## Open Questions
- Is the whole "always-sent summary" sentence worth rewording, or just adding "(real runs only; dry-run sends no summary)"?

## Notes
Surfaced during the E-256/E-259 internal review cycle (2026-07-09) when the CR spec audit's finding 6 was refuted by the code. Context-layer prose → claude-architect owns CLAUDE.md. Sibling capture to [[IDEA-113-season-aggregates-module-misnomer]]. Anchors: CLAUDE.md `bb report morning-run` Commands prose; `src/cli/report.py:571` (`_emit_summary_if_needed`, `if dry_run:` at :581, comment at :666).

---
Created: 2026-07-09
Last reviewed: 2026-07-09
Review by: 2026-10-07
