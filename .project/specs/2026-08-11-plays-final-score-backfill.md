<!-- NO REAL NAMES OR IDENTIFIERS — no person's name, ever; for teams, orgs, ids and UUIDs use the PII-Safe Placeholder Taxonomy in `.claude/rules/api-docs.md`. -->

# Backfill the plays-derived final score into already-loaded games

**Date**: 2026-08-11 · **Status**: `STUB` — the fix landed; the stored data still carries the
defect. **Source**: `.project/specs/done/2026-08-10-plays-final-score-recovery.md` §Out of scope,
routed at that chunk's handoff.

## Why this is owed

The parser and loader now recover the game-ending run and persist it to
`game_perspectives.plays_final_{home,away}_score`. **Nothing already in the DB moved.** Measured
immediately after the fix landed: the detection query still returns **91** units, and all 2,464
`game_perspectives` rows read NULL for both new columns. That is the designed behavior, not a
failure — the columns are proven by test, not by the dev DB.

**Plain regeneration cannot repair these games.** Whole-game plays idempotency
(`plays_loader.py`, the `SELECT 1 FROM plays WHERE game_id = ? AND perspective_team_id = ?`
precheck) skips any game that already has plays, so the new code never runs against them.

## Shape of the work

Per the seed's §5 sequence: back up (`python3 scripts/backup_db.py`) → reset → re-scout.

⚠️ **`bb report generate` is DESTRUCTIVE** — reconcile-at-load and orphan reclamation both
hard-delete (`CLAUDE.md`, two destructive seams). Name that before running it, not after.

## The success criterion, stated so it is not misread

**91 → the abandoned-charting residual (≥1), NOT → 0.** Measured expectation: **87 of the 88
affected games recover.** One game cannot: its play-by-play is complete and internally consistent
ending at inning 4 bottom / 3 outs / `8-12` while the official is `8-13`, with the inert phantom
sitting at inning **5** top — the scorekeeper stopped charting and the run is simply absent from
the payload. No seeding rule recovers it. A session that treats a nonzero residual as failure will
chase a defect that does not exist.

Expect WARNINGs from the loader during the backfill: the 9 two-scorebook units (plays EXCEED
boxscore) and the non-monotone units are legitimate disagreement, and the warning is the standing
detector, not an error.

## Progress log

- **2026-08-11** — Stubbed at the recovery chunk's handoff. No data touched.
