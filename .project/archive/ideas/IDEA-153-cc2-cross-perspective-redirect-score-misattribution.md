# IDEA-153: CC-2 — Cross-Perspective Redirect Flips Home/Away While Freezing Scores (silent score misattribution)

## Status
`PROMOTED`
<!-- Two-channel validation COMPLETE (2026-07-19): CONFIRMED / high by BOTH Codex gpt-5.6-terra xhigh
     AND the independent subagent, each with an executable in-memory repro against the migrated schema
     through the real ScoutingLoader. Promoted to E-268 (targeted fix, SEPARATE from E-267 — distinct
     COALESCE-asymmetry mechanism). -->

## Summary
On a cross-perspective redirect, `_upsert_game` (`src/gamechanger/loaders/game_loader.py:1373-1378`) overwrites `home_team_id`/`away_team_id` UNCONDITIONALLY from `excluded.*`, while `home_score`/`away_score` are gated on `preserve_scores` (`CASE WHEN ? THEN COALESCE(...)`). The team-ids and the scores are thus written from DIFFERENT orientations → runs silently re-credited to the wrong team. Corrupts W-L, recent form, and runs-for/against on BOTH reports; poisons `plays.batting_team_id` and home/away splits. HIGH severity, low likelihood.

## Why It Matters
Coach-facing and HIGH severity: the most-read game-level numbers (record, runs-for/against, recent form) get silently attributed to the wrong team, on both teams' reports. An active mis-credit, not a stale-row inflation — the scores stay but point at the flipped orientation.

## Verdict (two-channel, 2026-07-19)
- **CONFIRMED / high** by both channels, each with a runnable in-memory repro against the migrated schema through the real `ScoutingLoader`.
- **Contrast**: `game_stream_id` at `:1391` already correctly keeps-existing — the asymmetry is specifically the two team-id assignments.

## Notes
- Promoted to **E-268** (Cross-Perspective Redirect Score-Misattribution Fix), READY 2026-07-19. Kept SEPARATE from E-267 — different mechanism (COALESCE asymmetry vs retire-absent).
- Related: [[IDEA-147]] (H4 orientation staleness — shares the `_upsert_game` orientation-rewrite root; a combined fix at that site may be cheaper — flagged in E-268).
- Source: 2026-07-19 accumulate-only re-run audit, corner case CC-2. Master record: `.project/research/2026-07-19-rerun-accumulate-only-audit.md`.

---
Created: 2026-07-19
Last reviewed: 2026-07-19
Review by: 2026-10-17 (promoted to E-268)
