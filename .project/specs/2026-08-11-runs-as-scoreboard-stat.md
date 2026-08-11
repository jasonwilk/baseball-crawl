<!-- NO REAL NAMES OR IDENTIFIERS — no person's name, ever; for teams, orgs, ids and UUIDs use the PII-Safe Placeholder Taxonomy in `.claude/rules/api-docs.md`. -->

# Runs as a reconciliation-scoreboard stat

**Date**: 2026-08-11 · **Status**: `STUB` — chunk 2 of the final-score work. **Source**:
`.project/specs/done/2026-08-10-plays-final-score-recovery.md` §Out of scope, routed at that
chunk's handoff.

## Why this is owed

The scoreboard measures **no runs stat** — `PITCHING_STATS` / `BATTING_STATS`
(`src/reports/recon_scoreboard.py:92-93`) carry no R. That is precisely why the recovery chunk's
before/after readings were byte-identical, and why "identical" was the passing result there. It
also means **the north-star instrument is blind to the defect that chunk just fixed**: 102 runs
were missing across 91 units and the scoreboard could not see any of it.

## Two constraints, both load-bearing

1. **Add it UNGATED first.** Gating it immediately raises `BaselineError` (exit 4) against a
   baseline that lacks the key. Add the measurement, let a baseline capture it, gate later — if at
   all (see below).
2. **It must treat legitimate disagreement as legitimate.** Two populations are NOT defects and
   must not be scored as such: the **9 two-scorebook units** where plays EXCEED the boxscore
   (documented behavior — `.claude/rules/perspective-provenance.md` fn.1, E-261's 12-4 vs 12-5),
   and the **non-monotone** units where a scorekeeper entered and then rescinded a run. A naive
   `|plays − boxscore|` sum scores both as error and the stat becomes noise.

## Read this before gating anything

A STANDING RESIDUAL says the reconciliation gate **cannot work on a growing corpus** —
`evaluate_gate` ratchets on ABSOLUTE deltas, so data growth alone fails it, and an operator ruling
on rate-based thresholds vs. retiring the gate half is still owed. Do not add a new gated stat on
top of an unresolved gate design. The measurement is worth having either way.

## Progress log

- **2026-08-11** — Stubbed at the recovery chunk's handoff. No code.
