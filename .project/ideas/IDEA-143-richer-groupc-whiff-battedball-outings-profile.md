# IDEA-143: Richer Group-C whiff / batted-ball profile for the Outings Breakdown

## Status
`CANDIDATE`

## Summary
Extend the E-265 Pitcher Outings Breakdown with the richer play-by-play-derived stats that E-265 v1 deliberately left out: swinging-strike%, K-looking vs K-swinging split, and GO/AO (ground-out / air-out). These are the "how does this arm miss bats and get outs" signals beyond the raw counts + FPS% that v1 ships.

## Why It Matters
E-265 v1's stat set was curated by baseball-coach down to the per-outing row (Date | Opp | IP | BF | H | HR | BB | K | R | FPS% | ERA) plus a season K-rate line (K/BF | BB/INN | K/BB). The aspirational Group-C set in the original E-265 TN-2 (swinging-strike%, K-looking, GO/AO, GB/FB%) was trimmed OUT of v1 for two reasons: (1) coach's curation did not include them in the shipped columns, and (2) data-engineer flagged GO/AO as a taxonomy-parsing investment (trajectory lives only in `plays.outcome` free text like "Ground Out"/"Fly Out") and true GB/FB% as unreliable (a hit's trajectory is frequently absent from the outcome string — "Single" doesn't say ground vs line — yielding a biased denominator). This idea is the follow-on that adds the derivable subset once v1 proves out and the outcome-string classifier is worth building.

## Rough Timing
After E-265 (Pitcher Outings Breakdown) ships and is validated in real reports. Promote when a coach asks for the whiff/batted-ball detail, or when the outcome-string taxonomy classifier is built for another reason and GO/AO becomes cheap.

## Dependencies & Blockers
- [ ] E-265 (Pitcher Outings Breakdown) ships (this extends its section + `src/reports/pitcher_outings.py` derivation module)
- [ ] A batted-ball outcome-string classifier (Ground Out / Fly Out / Line Out / Pop Out from `plays.outcome`) — the GO/AO parsing investment E-265 v1 declined

## Open Questions
- Swinging-strike% and K-looking/K-swinging are CLEAN (`play_events.pitch_result` enum: `strike_swinging` / `strike_looking`) — could ship those first without the batted-ball classifier. Split into two tiers?
- GO/AO (outs only) is derivable-with-taxonomy; true GB/FB% (all balls in play incl. hits) is NOT reliable in our data — ship GO/AO and permanently drop true GB/FB%?
- Per-appearance plays aggregation inherits the ~90-95% pitcher-attribution caveat (`plays.pitcher_id` nullable, reconciliation-corrected) — acceptable as a directional whiff read, but state it.

## Notes
Raised during E-265 refinement (2026-07-15) by baseball-coach (column curation) + data-engineer (derivation-risk assessment). Related: E-265 (parent), `.claude/rules/key-metrics.md` (FPS% / pitcher-attribution-accuracy), `.claude/agent-memory/baseball-coach/pitcher-outings-scouting-consultation.md`.

---
Created: 2026-07-15
Last reviewed: 2026-07-15
Review by: 2026-10-13
