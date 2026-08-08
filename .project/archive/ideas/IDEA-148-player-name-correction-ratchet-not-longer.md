# IDEA-148: Player-Name Corrections That Are Not Strictly Longer Are Permanently Blocked

## Status
`CANDIDATE`

## Summary
`ensure_player_row` uses a longer-name-wins ratchet (`src/db/players.py:41-64`, "Unknown" treated as length 0). Any name correction that is NOT strictly longer than what we already stored never propagates: "Jon"→"Jim", or a wrong-long name → a correct-short name, is permanently ignored. The stale name feeds the report roster grid and the LLM narrative. Allow a genuine correction to overwrite even when it is the same length or shorter. (Corner case CC-4.)

## Why It Matters
Coach-facing: a coach sees the wrong player name on the report (and in the generated narrative) with no way to fix it short of a DB edit. The ratchet was designed to prefer a fuller name over a stub ("J. Smith" < "John Smith"), which is the right instinct — but it over-fires on same-length and legitimate-shorter corrections. Cheap, standalone, coach-visible.

## Rough Timing
Promote on pain (a wrong name observed on a report that won't self-correct) or as a cheap quick-win alongside other player-data hygiene.

## Dependencies & Blockers
- [ ] None hard-blocking. `ensure_player_row` is the canonical player upsert seam — the fix lives there.

## Open Questions
- How to distinguish a real correction from noise without reintroducing the stub-clobbers-full-name regression the ratchet was built to prevent (e.g., trust a correction only when the incoming name differs by more than truncation, or gate on a fresher-source signal)?

## Notes
- Source: 2026-07-19 accumulate-only re-run audit, corner case CC-4 (single-channel fable sweep). Master record: `.project/research/2026-07-19-rerun-accumulate-only-audit.md`.
- **Standing test requirement (operator directive 2026-07-19):** any future promotion MUST ship a regression test that reproduces the blocked correction (fails pre-fix — a not-longer name is ignored) and asserts the corrected name propagates (passes post-fix), WITHOUT regressing the stub-does-not-clobber-full-name behavior. Gate every ingestion change against the E-257 reconciliation-scoreboard ratchet.

---
Created: 2026-07-19
Last reviewed: 2026-07-19
Review by: 2026-10-17 (suggest 90 days from created)
