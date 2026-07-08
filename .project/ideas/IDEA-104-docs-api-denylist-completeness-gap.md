# IDEA-104: `docs/api/` Byte-Gate Denylist-Completeness Gap

## Status
`CANDIDATE`

## Summary
The `docs/api/` doc-PII byte-gate (`scripts/check_doc_pii.sh docs/api`) passes GREEN on real-LOOKING identifiers that are present in committed endpoint docs — meaning those identifiers are NOT on the denylist. If any of them are genuinely real (a real `public_id`, a real athlete/team UUID, or a real team name), the gate has a completeness gap: it only catches identifiers someone explicitly added to `secrets/pii-denylist.txt`, and the pattern PII scanner does not catch names/slugs at all.

## Why It Matters
The byte-gate is the LAST line of defense for real identifiers the pattern scanner structurally cannot detect (names, UUIDs, public_ids). If real identifiers sit in committed docs that the gate passes green on, the protection is illusory for exactly the class it exists to catch. This is a governance/coverage gap in the safety tooling, not a one-off scrub.

## Concrete surfacing (E-255-04, 2026-07-08)
During E-255-04, api-scout observed real-looking identifiers PRE-EXISTING in `docs/api` files it did not edit — e.g. public_ids `smgRExWHuBJJ` / `QTiLIb2Lui3b` / `WThfCgtHecNF`, full UUIDs, and the team name "Kearney Mavericks 14U" (in `get-public-game-stream-processing-game_stream_id-details.md`, boxscore, plays samples). The authoritative baseline gate in main (`scripts/check_doc_pii.sh docs/api`, 22 patterns, REAL mode) returned PASS (0 matches) — so none of these are denylisted. E-255-04 introduced none of them; this idea is about whether the denylist SHOULD cover them.

## Distinct from IDEA-102
IDEA-102 covers UNGATED paths (`epics/`/`.project/` idea/epic/note files are in the scanner's SKIP_PATHS and outside the byte-gate). THIS idea is about GATED `docs/api/` where the gate runs but the denylist is incomplete for real-looking corpus identifiers.

## Rough Timing
Fold into the E-254 PII-scanner/denylist follow-up cluster (IDEA-096 systematic docs/api PII sweep is adjacent). Promote when someone next touches the PII tooling or when a real leak is confirmed.

## Dependencies & Blockers
- [ ] First: determine which of the flagged identifiers are actually REAL vs. fake/example (some `docs/api` samples use generalized values by design). If all fake → this idea is moot.
- [ ] If real: add them to `secrets/pii-denylist.txt` (the uncommitted real denylist) AND establish a positive rule that endpoint-doc samples use taxonomy placeholders (overlaps IDEA-096).

## Notes
- Surfaced by api-scout during E-255-04; PM ruled it non-blocking for E-255-04 (that story's AC-7 is non-reintroduction, satisfied) but a real finding worth capturing.
- Related: IDEA-096 (systematic docs/api PII sweep), IDEA-102 (committed-artifact PII gap), IDEA-004 (PII protection lineage).

---
Created: 2026-07-08
Last reviewed: 2026-07-08
Review by: 2026-10-06
