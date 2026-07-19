# IDEA-151: Morning-Run opponent_links Resolve-Once Permanence (wrong link reused forever)

## Status
`CANDIDATE`

## Summary
Morning-run resolves an opponent once and reuses that link permanently (`src/reports/opponent_ladder.py:329-368`). A wrong auto single-hit match, or a correct link that later goes stale, is reused every game morning — the wrong-team scouting report is delivered until the operator manually runs `bb report map-opponent`. Add a way to detect/expire a stale-or-wrong resolved link rather than trusting it forever. (Corner case CC-10.)

## Why It Matters
Coach-facing: coaches receive a scouting report for the WRONG opponent every game morning once a bad link is cached, with no automatic correction. Medium impact if it fires (a whole game's prep is wrong), low likelihood (needs a wrong single-hit auto-resolve or a link that later drifts). Morning-run is the forward feature, so a silently-wrong delivery is especially costly there.

## Rough Timing
Promote on pain (a wrong-opponent report delivered) or as a morning-run reliability follow-on alongside IDEA-080 (coach-facing scheduled delivery). Design-adjacent — needs a deliberate re-validation policy, not just a code tweak.

## Dependencies & Blockers
- [ ] Design-adjacent to the morning-run resolution ladder and `opponent_links` state machine (resolved-positive / no_gc_presence / pending).

## Open Questions
- When should a resolved link be re-validated instead of trusted — every run, on a confidence signal, on a schedule-name-change signal?
- How to detect a wrong single-hit auto-resolve without forcing the operator to confirm every match (which would defeat automation)?
- Should a low-confidence auto-resolve be surfaced for operator eyeball rather than silently cached?

## Notes
- Source: 2026-07-19 accumulate-only re-run audit, corner case CC-10 (single-channel fable sweep). Master record: `.project/research/2026-07-19-rerun-accumulate-only-audit.md`.
- Related: [[IDEA-080]] (coach-facing scheduled report delivery — morning-run family).
- **Standing test requirement (operator directive 2026-07-19):** any future promotion MUST ship a regression test that reproduces the stale-link reuse (fails pre-fix — a wrong/stale link is reused) and asserts re-validation/expiry (passes post-fix). Gate every ingestion change against the E-257 reconciliation-scoreboard ratchet.

---
Created: 2026-07-19
Last reviewed: 2026-07-19
Review by: 2026-10-17 (suggest 90 days from created)
