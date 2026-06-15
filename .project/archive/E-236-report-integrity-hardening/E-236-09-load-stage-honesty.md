# E-236-09: Load-stage honesty — write load_errors + classify load_status (#6)

## Epic
[E-236: Report Self-Reporting Integrity Hardening](epic.md)

## Status
`DONE`

## Description
After this story is complete, the scouting-LOAD stage will record an honest `load_status` (`completed`/`partial`/`failed`) and write the `load_errors` count, instead of hardcoding `load_status="completed"` even when the loader reported errors. This closes the 6th self-reporting gap (#6), surfaced during the internal review — the same bug class as #1, one stage over.

## Context
The load stage (`generator.py:1507-1520`) hardcodes `load_status="completed"` (line 1520) / `"failed"` (line 1510). A PARTIAL load — some rows loaded AND `ScoutingLoader.LoadResult.errors > 0` — records `"completed"`, overstating success. Review (SE-C + CR MUST-2) also flagged that `load_errors` (added by migration 003, story 01) would otherwise be an orphan column written by no story. See epic Technical Notes TN-11 (resolution), TN-1 (classifier + error-driven guardrail), TN-2 (`load_errors` column). This is the load-stage analogue of stories 02 (plays) and 03 (crawl).

## Acceptance Criteria
- [ ] **AC-1**: The load stage writes the `load_errors` run-record column from `ScoutingLoader.LoadResult.errors` — an honest RECORD-level error tally (DE: it can be per-player, `scouting_loader.py:841`) for operator drill-down (Technical Notes TN-2/TN-11).
- [ ] **AC-2**: `load_status` is ERROR-driven (per Technical Notes TN-1 guardrail + DE CAUTION 1). The classifier's `loaded` MUST NOT be bound to `LoadResult.loaded` — that is a RECORD count (+1 per game AND +1 per player stat row, `scouting_loader.py:673`), dimensionally incoherent as a coverage numerator (a scored-but-empty game has `loaded=1`, a normal game `1+N` — comparing against an "expected players" number would falsely mark the empty game partial). The status truth table (AC-3/4/5) is what matters; the implementer derives `load_status` from the error signal with GAME-level (not record-level) coverage if the classifier's coverage arm is used (this requires a per-game "processed-without-error" tally, which does not exist today — see Technical Approach), confirmed with DE/SE.
- [ ] **AC-3**: Given a load where boxscores process but `LoadResult.errors > 0` (e.g. a per-player `sqlite3.Error`), when the report generates, then `load_status == "partial"` and `load_errors > 0` (was `"completed"` before this story).
- [ ] **AC-4**: Given a clean load with `LoadResult.errors == 0` — INCLUDING the realistic scored-but-empty boxscore (sub-case A: team keys present, stat groups empty/absent → `loaded` counts the game, `errors=0`) — when the report generates, then `load_status == "completed"` (NOT "partial"). DE + SE confirmed (consensus, code-cited) that `LoadResult.errors` does NOT increment for sub-case A — see Notes.
- [ ] **AC-5**: Given a total load failure (the existing failure path at `generator.py:1510`, OR DE sub-case B — a degenerate boxscore with no identifiable team keys → `LoadResult(errors=1)` at `scouting_loader.py:503-505`), when the report generates, then `load_status == "failed"` (the explicit total-failure signal maps to `"failed"` BEFORE the classifier, per Technical Notes TN-1 precedence). NOTE: sub-case B is DEFENSIVE coverage — api-scout confirmed GC's real "missing game" is an HTTP 404 (no game-stream record) that the crawler raises on and SKIPS (so it never reaches the loader's keyless early-return); the keyless-body→errors=1 path is correct defensive code but not GC's actual shape. Keep the code; frame the test as defensive.
- [ ] **AC-6**: An error-path test (testing.md Error-Path Testing) proves a partial load (some processed, `errors>0`) records `"partial"`, not `"completed"`; and a separate test proves the scored-but-empty sub-case-A load records `"completed"` (the false-alarm guard).

## Technical Approach
Thread `ScoutingLoader.LoadResult.errors` into the load-stage status write at `generator.py:1507-1520`; replace the hardcoded `"completed"`. The status must be ERROR-driven (DE CAUTION 1): do NOT compute `loaded < expected` from `LoadResult.loaded` (a record count). Two acceptable mechanisms (implementer's choice, confirm with DE/SE): (a) add a per-GAME "processed-without-error" tally in the loader's per-game loop (`_load_boxscores_from_data`, `scouting_loader.py:480-496`) and feed game-level `loaded`/`expected` to `classify_stage_status`; or (b) drive `load_status` directly off `LoadResult.errors` (errors==0 → completed; errors>0 with some loaded → partial; total game-upsert/unreadable failure → failed). Either way, preserve the existing total-failure path (line 1510 → `"failed"`) by mapping it before the classifier. Discover and run all test files importing from the modified modules (testing.md scope discovery).

## Dependencies
- **Blocked by**: E-236-01, E-236-06
- **Blocks**: E-236-07, E-236-08

## Files to Create or Modify
- `src/reports/generator.py` (modify — load-stage status write at ~1507-1520)
- `src/gamechanger/loaders/scouting_loader.py` (modify ONLY if mechanism (a) is chosen — add a per-game processed-without-error tally in `_load_boxscores_from_data`)
- Load-stage tests (modify/add — locate via `grep -rl` per testing.md)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing (including the partial-load error-path test)
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
SE-C + CR MUST-2 (review-surfaced 6th gap). Jason approved INCLUDE 2026-06-14 (5→6 same-class gaps, TN-11). Error-driven per the TN-1 guardrail.
**DE + SE CONSENSUS (2026-06-14, both code-cited):** `LoadResult.errors` increments ONLY on genuine parse/insert failure — malformed JSON / non-dict / unidentifiable team keys (the keyless early-return), game-row upsert failure, per-player `sqlite3.Error`. It does NOT increment for the realistic scored-but-empty boxscore (sub-case A: team keys present, groups empty → game counted, `errors=0`). So AC-4's empty-but-clean → `completed` holds. **SE structural proof:** the scored-but-empty GAMES ROW (the very thing that creates N<M) is written ONLY on the error-free, keys-present branch (after the keyless early-return is NOT taken) — so the existence of a scored-but-empty games row PROVES the load took the error-free branch. The binding (`errors = LoadResult.errors`) is therefore correct EITHER WAY; the SQ2 api-scout fixture is a fixture-FIDELITY confirm, not a correctness blocker. (Open Question CLOSED.)
**Story 08 ↔ 09 coupling (DE CAUTION 2):** the "scored-but-empty → completed" guarantee holds ONLY for sub-case A. If the api-scout-confirmed degraded boxscore (SQ2) turns out to be sub-case B (no identifiable team keys → `errors=1`), the correct `load_status` is `failed`, not `completed`. Stories 08 and 09 MUST use the SAME api-scout-confirmed boxscore shape, and story 08's asserted `load_status` must match the confirmed sub-case. The SQ2 ask is sharpened to pin sub-case A vs B (epic TN-9 / Open Questions).
