# IDEA-147: Re-derive plays.batting_team_id on a Home/Away Orientation Correction

## Status
`CANDIDATE`

## Summary
`_upsert_game` rewrites `home_team_id`/`away_team_id` unconditionally on re-run (`src/gamechanger/loaders/game_loader.py:1370-1374`), including correcting a run-1 orientation that defaulted own-team-to-home (`home_away=None` case, `:568-573`). But plays derive `batting_team_id` at first-parse and are never touched again (the H3 whole-game skip), so after an orientation flip the batting-side plays queries key on a now-swapped `batting_team_id` → silently swapped batting splits. Re-derive `plays.batting_team_id` whenever a game's orientation actually changes. (Hazard H4.)

## Why It Matters
Coach-facing (narrow): batting-side splits (who batted, spray-by-side, plays-derived hitter metrics) silently swap after a real orientation correction. Only manual `bb data reload-annotated-pitches` fixes it today. Narrow trigger — needs a genuine orientation flip, most often `home_away=None`→resolved on a re-run.

## Rough Timing
Promote on pain, or fold alongside CC-2's fix (IDEA-153) — both stem from the `_upsert_game` orientation-rewrite site and both poison `batting_team_id`, so a combined fix may be cheaper. Distinct enough to track separately.

## Dependencies & Blockers
- [ ] Overlaps CC-2's root (IDEA-153, `_upsert_game` orientation handling). Coordinate so the two fixes don't collide.

## Open Questions
- Trigger the re-derive from the orientation-change detection in `_upsert_game`, or as part of E-267's per-run reconciliation? (E-267 does not currently own this — it retires MISSING rows, not orientation-stale ones.)
- Re-derive from stored `raw_template` (like `reload_game_plays`) so no re-fetch is needed.

## Notes
- Source: 2026-07-19 accumulate-only re-run audit, hazard H4 (Codex CONFIRMED/high, subagent CONFIRMED/medium). Master record: `.project/research/2026-07-19-rerun-accumulate-only-audit.md`.
- Related: [[IDEA-153]] (CC-2 orientation-flip score misattribution — shared root), [[IDEA-146]] (frozen-plays refresh — shared H3 root).
- **Standing test requirement (operator directive 2026-07-19):** any future promotion MUST ship a regression test that reproduces the swap (fails pre-fix — an orientation flip on an already-charted game leaves `batting_team_id` stale) and asserts the re-derived value (passes post-fix). Gate every ingestion change against the E-257 reconciliation-scoreboard ratchet.

---
Created: 2026-07-19
Last reviewed: 2026-07-19
Review by: 2026-10-17 (suggest 90 days from created)
