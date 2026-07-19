# IDEA-150: Outings Card vs. Headline FPS% Read Different Plays Scopes (same report, two numbers)

## Status
`CANDIDATE`

## Summary
The Pitcher Outings card and the headline FPS% compute over different plays scopes: the outings card keys on this-run canonical game ids, while the headline reads whole-season plays (`src/reports/pitcher_outings.py:311-314`). When the DB carries a game the current crawl no longer returns, the same report shows two different first-pitch-strike numbers for the same pitcher. Feature-flagged behind `FEATURE_PITCHER_OUTINGS`. Make the two surfaces read the same scope. (Corner case CC-9.)

## Why It Matters
Coach-facing (only when the flag is ON): an internal contradiction on one page — two FPS% for one pitcher — erodes trust in the report. Low severity/likelihood today because the flag is off by default and the trigger (a DB game the fresh crawl dropped) is itself one of the accumulate-only hazards E-267 addresses. Worth fixing before the outings flag is turned on for real.

## Rough Timing
Promote when `FEATURE_PITCHER_OUTINGS` is being turned on, or if E-267's game-grain retire changes which games are live and exposes the divergence. Cheap coherence fix.

## Dependencies & Blockers
- [ ] Interacts with E-267 (the game-set-vs-crawl mismatch is the trigger) and with the outings flag rollout decision.

## Open Questions
- Which scope is canonical — this-run game ids or whole-season — and should BOTH surfaces adopt it?

## Notes
- Source: 2026-07-19 accumulate-only re-run audit, corner case CC-9 (single-channel fable sweep). Master record: `.project/research/2026-07-19-rerun-accumulate-only-audit.md`.
- Related: E-267 (game grain determines which games are live), E-265/E-266 (Pitcher Outings feature — archived).
- **Standing test requirement (operator directive 2026-07-19):** any future promotion MUST ship a regression test that reproduces the divergence (fails pre-fix — outings FPS% ≠ headline FPS% for one pitcher) and asserts a single coherent number (passes post-fix). Gate every ingestion change against the E-257 reconciliation-scoreboard ratchet.

---
Created: 2026-07-19
Last reviewed: 2026-07-19
Review by: 2026-10-17 (suggest 90 days from created)
