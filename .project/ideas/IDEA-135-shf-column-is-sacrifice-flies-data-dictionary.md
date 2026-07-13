# IDEA-135: Data-dictionary correction — `shf` is sacrifice FLIES, not sac bunts

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
The `player_game_batting.shf` column holds sacrifice FLIES, not sacrifice bunts. The GameChanger stat glossary / data dictionary should state this explicitly so no future signal computes bunt tendencies from it. A one-line data-dictionary correction to whichever file owns column semantics (`docs/gamechanger-stat-glossary.md` and/or `.claude/rules/data-model.md`).

## Why It Matters
Surfaced by the 2026-07-13 Fable-scout discovery pass, which verified per-team `shf` sums match Sacrifice-Fly play counts almost exactly (Bayport 23=23, Griffs 12=12, Five Star 10=10) and do NOT match sac-bunt counts. Anyone reaching for `shf` to build a bunt-tendency / small-ball signal silently gets flies instead — a subtle wrong-stat bug. The E-263 small-ball work correctly uses `plays.outcome` + spray bunt detection rather than `shf`, so E-263 is not affected; this correction protects future work.

## Rough Timing
Cheap and actionable now. Do it as a standalone one-line docs/context fix, or fold into the next housekeeping/truth-sweep pass (e.g. an E-262-style epic) — no dependency, just shouldn't be lost.

## Dependencies & Blockers
- [ ] None — factual correction with verified evidence.

## Open Questions
- Owner/home: `docs/gamechanger-stat-glossary.md` (the authoritative data dictionary per `.claude/rules/key-metrics.md`) is the natural home (docs-writer / the file's maintainer); if `.claude/rules/data-model.md` also names `shf` semantics, correct it there too (claude-architect). Confirm which files currently reference `shf`.

## Notes
- Evidence: per-team `shf` sums matched Sacrifice-Fly play counts (Bayport 23, Griffs 12, Five Star 10) exactly, not sac-bunt counts.
- Source: 2026-07-13 Fable-scout discovery pass, Note B.

---
Created: 2026-07-13
Last reviewed: 2026-07-13
Review by: 2026-10-11
