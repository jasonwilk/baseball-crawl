# E-252-05: Operating-timezone default target date (+ shared seam for CE-3)

## Epic
[E-252: Scheduled-Reports Reliability (Cron-Grade Morning-Run)](../E-252-scheduled-reports-reliability/epic.md)

## Status
`TODO`

## Description
After this story is complete, `bb report morning-run`'s default target date is the venue-local operating date (not the container's UTC date), so an evening cron or an evening manual run no longer defaults to tomorrow's games. The date is derived through a single, reusable operating-timezone seam that CE-3/E-253 will reuse for `game_date`.

## Context
`run_morning` computes its default target date as `date.today()` when `--date` is not supplied. In the production Docker container the system clock is UTC, so after ~19:00 venue time the UTC date has already rolled to tomorrow — an evening scheduled run (or an evening manual run) filters to tomorrow's games instead of today's. The product reasons in venue-local dates everywhere else; the per-game filter already derives each game's local date via `derive_local_date(start_datetime, tz_name)` in `morning_run.py`. The default target "today" must use the same venue-local reasoning.

This is one of three sites in the audit's "systemic UTC-date derivation" family. Per the epic's non-goals and TN-4, **CE-2 fixes only the morning-run default target date** and **introduces the shared operating-timezone seam**; CE-3/E-253 reuses that seam for `game_date` (the other two sites — stored `game_date` and the report reference date — are out of scope here).

## Acceptance Criteria
- [ ] **AC-1**: Given no `--date` argument and a fixed wall-clock instant that is "today" in the operating timezone but already "tomorrow" in UTC (e.g. an evening run), when `run_morning` computes the default target date, then it resolves to the operating-timezone local date (today), not the UTC date (tomorrow).
- [ ] **AC-2**: The operating timezone is read from a single env-configured IANA timezone through ONE reusable helper (the seam), defaulting to `America/Chicago` (the venue) when the env var is unset or invalid, per Technical Notes TN-4. An explicit `--date YYYY-MM-DD` continues to override and is unaffected.
- [ ] **AC-3**: The seam is a single reusable unit (one helper, one env read) that CE-3/E-253 can consume for `game_date` without redefining the timezone convention — it is NOT inlined into `run_morning`. Its name and location are the implementer's choice per TN-4.
- [ ] **AC-4**: An unknown/invalid operating-timezone env value degrades safely (falls back to the `America/Chicago` default with a logged warning), mirroring the existing `derive_local_date` unknown-timezone handling — it does not crash the run.
- [ ] **AC-5**: Tests cover: the evening-run UTC-rollover case (AC-1) with the wall clock injected/frozen (no dependence on real time), the env-override path, the unset-default path, and the invalid-value fallback (AC-4). Per Technical Notes TN-8, no real time or HTTP dependence.

## Technical Approach
Introduce a single operating-timezone seam (one helper that returns the configured `ZoneInfo`, reading one env var with an `America/Chicago` default), and use it to compute the default target date as the operating-timezone "today" instead of `date.today()`. Mirror the unknown-timezone degradation already in `derive_local_date`. Make the wall-clock instant injectable (or otherwise mockable) so AC-1/AC-5 are deterministic. Place the seam where CE-3 can import it without re-deriving the convention (TN-4). Do NOT apply the seam to the report reference date or `game_date` — those are CE-3's scope.

Coordinate the env var name and seam location with the CE-3 boundary (see epic Open Questions); if the user has not confirmed a name at dispatch, default to `America/Chicago` with an env override and document the seam clearly.

## Dependencies
- **Blocked by**: E-252-02 (same file: `src/reports/morning_run.py`; the morning_run.py chain is 01→02→05→07)
- **Blocks**: E-252-07 (same file)

## Files to Create or Modify
- `src/reports/morning_run.py` (default `target_date` derivation in `run_morning`)
- A shared helper module for the operating-timezone seam (implementer's choice of location per TN-4 — e.g. a small helper in `src/reports/` or a shared util; MUST be importable by CE-3)
- `tests/test_morning_run.py` (or the existing morning-run test module) — the AC-5 tests

## Agent Hint
software-engineer

## Handoff Context
- **Produces for CE-3/E-253**: The reusable operating-timezone seam. E-253 reuses it for `game_date` and MUST NOT introduce a second timezone convention.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Audit one-liner (part of the systemic UTC-date family): "morning-run's default target date uses UTC while the product reasons in venue-local dates; evening manual morning-runs use tomorrow's date" — `src/reports/morning_run.py:447`. CE-3 boundary: the seam introduced here is reused by E-253 for `game_date` (TN-4).
