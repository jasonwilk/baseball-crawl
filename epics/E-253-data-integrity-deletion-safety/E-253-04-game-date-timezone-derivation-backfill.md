# E-253-04: `game_date` Operating-Timezone Derivation (+ helper relocation)

## Epic
[E-253: Data-Integrity & Deletion Safety](epic.md)

## Status
`TODO`

## Description
After this story is complete, a newly-loaded game's stored `game_date` will reflect the venue-local calendar date rather than the UTC date, so evening games no longer file under the next day (skewing rest math, the 7-day window, and cross-perspective dedup at UTC midnight). As the enabling step, the existing `derive_local_date` conversion helper is relocated to a neutral shared module so the game loader can import it without a layering inversion. The one-time backfill of existing rows is a separate story (E-253-11).

## Context
See epic Technical Notes **TN-5**. `game_loader.py:594` derives `game_date` from a UTC instant (`last_scoring_update[:10]`); an evening game files under tomorrow's UTC date. This is one of three systemic UTC-date sites (audit finding 4); E-253 owns ONLY the stored `game_date` site. Two existing pieces are reused (per SE's Q2 resolution, TN-5):
- The **operating-timezone seam from E-252-05 (TN-4)** — an env-configured `ZoneInfo` (IANA, `America/Chicago` default). E-253 REUSES it as the FALLBACK tz; it must NOT define a second convention. Reference it abstractly (the import path is left to the E-252 implementer).
- The existing **`derive_local_date(start_datetime, tz_name)`** helper (currently `src/reports/morning_run.py:150`) for the instant→local-date conversion, using the game's own `timezone` when present.

Layering smell (SE-flagged): `src/gamechanger/loaders/game_loader.py` importing from `src/reports/morning_run.py` inverts the dependency direction (loaders are lower-layer than reports). This story relocates `derive_local_date` to a neutral shared module both `game_loader` and `morning_run` import.

## Acceptance Criteria
- [ ] **AC-1**: `derive_local_date` is relocated to a neutral shared module lower in the layering than `src/reports/` and importable by `src/gamechanger/loaders/`; both `morning_run.py` and `game_loader.py` import it from there. This is a pure move (no behavior change) — existing `derive_local_date` tests pass against the new location.
- [ ] **AC-2**: Given a game whose UTC instant falls in the evening local time but the next day in UTC, when the game loader derives `game_date`, then `game_date` is the venue-local calendar date via `derive_local_date(instant, game_timezone)` — proven by a test with a known evening instant.
- [ ] **AC-3**: When a game has no `timezone`, the derivation falls back to the operating-timezone seam from E-252-05 (the `America/Chicago` default) — no second, divergent timezone convention is introduced. The seam returns a `ZoneInfo` object; the derivation bridges it to the IANA tz-name expected by `derive_local_date` per epic TN-5 (ZoneInfo → tz-name), never passing the `ZoneInfo` object into `derive_local_date`.
- [ ] **AC-4**: Existing tests that assert `game_date` values are updated to the corrected local-date contract (per `.claude/rules/testing.md` "when you change a production contract, stale tests are MUST-FIX"), and the `derive_local_date` import sites are updated.

## Technical Approach
See epic Technical Notes **TN-5**. Reference the E-252-05 seam abstractly (path not yet pinned). The implementing agent chooses the neutral module for `derive_local_date` and owns the derivation wiring. Coordinate with E-252 (which also touches this seam and `morning_run.py`); since epics run serially with E-252 first, the relocation lands cleanly after E-252 merges.

## Dependencies
- **Blocked by**: E-252 (specifically E-252-05 — the operating-timezone seam; E-252 is sequenced before E-253 and also touches `morning_run.py`)
- **Blocks**: E-253-06 (also modifies `src/gamechanger/loaders/game_loader.py`); E-253-11 (backfill depends on the corrected derivation + relocated helper)

## Files to Create or Modify
- `src/gamechanger/loaders/game_loader.py` (the `game_date` derivation site, ~line 594)
- `src/reports/morning_run.py` (remove `derive_local_date`, import from the new location)
- New neutral shared module for `derive_local_date` (implementer chooses; must be importable by loaders without layering inversion)
- `tests/` — timezone-derivation test, relocated-helper import tests, `game_date` fixtures/assertions encoding the old UTC contract

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-253-11**: the corrected derivation logic and the relocated `derive_local_date` helper that the backfill subcommand reuses for its 3-tier re-derivation.
- **Produces for the epic close**: the `derive_local_date` relocation is an architecture change (new canonical shared-helper location) — flag it for the closure context-layer assessment (a CLAUDE.md canonical-helper note may be warranted; CA owns any such edit).

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Cross-reference: `.claude/rules/data-model.md` (Game-ordering convention, 7-day rolling window, Game time data ownership — `game_date`/`start_time`/`timezone` columns).
