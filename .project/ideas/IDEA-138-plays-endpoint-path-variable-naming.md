# IDEA-138: Normalize `/game-stream-processing/{...}/plays` endpoint-doc path-variable naming

## Status
`CANDIDATE`

## Summary
The IDEA-107-class path-variable inconsistency, but for the `/plays` endpoint: multiple `docs/api/` files still reference `/game-stream-processing/{game_stream_id}/plays` in `see_also`/prose even though the plays endpoint takes `event_id` (its own doc is already `get-game-stream-processing-event_id-plays.md` with path `{event_id}`). E-262-09 fixed the sibling `.../boxscore` rename but deliberately did NOT touch the `/plays` references (out of scope). This is a **7-file surface** (not the 4 a Codex pass initially cited) — fixing a subset would itself be a half-fix.

## Why It Matters
Same footgun as IDEA-107: a doc that names `{game_stream_id}` for an endpoint that actually takes `event_id` trains the wrong param and can send an integrator down a needless `best-game-stream-id` lookup. The E-262-09 boxscore rename made the surviving `/plays` contradiction MORE CONSPICUOUS by contrast (a now-consistent `.../boxscore` `see_also` sitting directly above a still-contradictory `.../plays` one in the same file), which is exactly why it keeps getting re-flagged. Codex independently corroborated the surface at E-262 closure (Phase 4 review, gpt-5.6-terra) and confirmed via `git diff HEAD` that it is byte-for-byte PRE-EXISTING — not introduced by story 09.

## Rough Timing
Low urgency / cosmetic-correctness — fold opportunistically into any epic already touching `docs/api/`, or promote if it re-surfaces in another review. Do it as a single atomic pass across all 7 files (a subset is a half-fix).

## Dependencies & Blockers
- [ ] None. api-scout owns `docs/api/**`; the fix is mechanical.

## Open Questions
- Confirm the exact 7-file set at execution time (grep `docs/api/` for `game-stream-processing/{game_stream_id}/plays` and `game_stream_id}/plays` see_also/prose refs) — token-scope like IDEA-107 did, do NOT blanket-replace `game_stream_id` (the distinct `/game-streams/{game_stream_id}/...` endpoints and the public-details endpoint legitimately keep it).

## Notes
Source: E-262-09 dispatch (2026-07-13, api-scout) + Codex Phase-4 closure review corroboration. Exact fix pattern (immediately actionable): `{game_stream_id}/plays` → `{event_id}/plays` + filename check — the plays endpoint file is already `get-game-stream-processing-event_id-plays.md` with path `{event_id}`. Same class as **IDEA-107** (boxscore path-variable rename, PROMOTED → E-262-09). Domain: api-scout.

---
Created: 2026-07-13
Last reviewed: 2026-07-13
Review by: 2026-10-11
