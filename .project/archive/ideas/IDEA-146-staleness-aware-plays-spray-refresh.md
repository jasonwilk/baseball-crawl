# IDEA-146: Staleness-Aware Plays & Spray Refresh (unfreeze the first-scout whole-game gate)

## Status
`CANDIDATE`

## Summary
Plays and spray are frozen at first scout: the loader skips the whole game if ANY row already exists (`PlaysLoader._load_game` `src/gamechanger/loaders/plays_loader.py:141-152`; generator gate `src/reports/generator.py:888-895`; `ScoutingSprayChartLoader._load_game_data` `scouting_spray_loader.py:183-192` + `INSERT OR IGNORE`). Once a game is charted, GC post-game chart edits, corrected pitch counts, and spray partial-first-pass never refresh — plays-derived FPS%/QAB/P-PA drift from the boxscore that DOES upsert. Add a staleness-aware refresh so an already-charted game re-derives when GC's chart has changed. (Hazard H3.)

## Why It Matters
Coach-facing: plays-derived pitcher/hitter metrics (first-pitch-strike%, QAB, pitches-per-PA) drift from truth when a scorekeeper edits a chart after we first loaded it. NARROWED scope: an uncharted→charted game self-heals today (the gate keys on row existence), so the freeze bites only two cases — (1) an edit AFTER the game was already charted, and (2) spray charts loaded on a partial first pass (the loader comment `scouting_spray_loader.py:178-182` admits this trap). The whole-game skip is GOOD at preventing cross-perspective duplication; the goal is to keep that protection while adding a refresh trigger. `reload_game_plays` already re-derives from stored `raw_template` but is operator-manual — this is about a per-run staleness signal, not a manual pass.

## Rough Timing
Promote on pain — when an observed plays-derived number is seen drifting from the boxscore on a re-scouted, already-charted game. Distinct mechanism from the E-267 reconcile-against-crawl family (that retires MISSING rows; this refreshes CHANGED-in-place rows), so it stays a standalone idea.

## Dependencies & Blockers
- [ ] None hard-blocking. Interacts with the whole-game skip gate that E-267's game grain also touches — coordinate if both are in flight.

## Open Questions
- What is the cheap change-detection signal (chart version / pitch-count delta / play-count delta) that says "GC's chart changed, re-derive"?
- Re-derive from stored `raw_template` (like `reload_game_plays`) vs. re-fetch? Must not regress the E-257 reconciliation-scoreboard ratchet either way.
- How to keep the cross-perspective duplication protection intact while allowing an in-place refresh.

## Notes
- Source: 2026-07-19 accumulate-only re-run audit, hazard H3 (two-channel CONFIRMED). Master record: `.project/research/2026-07-19-rerun-accumulate-only-audit.md`.
- Related: [[IDEA-147]] (batting_team_id orientation staleness — same frozen-plays root), E-267 (reconcile-against-crawl retire-absent family), [[IDEA-134]] (play-level cross-perspective dup).
- **Standing test requirement (operator directive 2026-07-19):** any future promotion MUST ship a regression test that reproduces the drift (fails pre-fix — a charted game whose GC chart changed) and asserts the refreshed value (passes post-fix). And every ingestion change must be gated against the E-257 reconciliation-scoreboard ratchet.

---
Created: 2026-07-19
Last reviewed: 2026-07-19
Review by: 2026-10-17 (suggest 90 days from created)
