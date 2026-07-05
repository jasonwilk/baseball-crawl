# E-252-02: Broaden per-team isolation (transient + rate-limit) with systemic 429 escalation

## Epic
[E-252: Scheduled-Reports Reliability (Cron-Grade Morning-Run)](../E-252-scheduled-reports-reliability/epic.md)

## Status
`TODO`

## Description
After this story is complete, a transient failure on one team's schedule/opponents crawl (a 5xx server error, a connection error, or a rate-limit error) is isolated to that team: the run records the failure, moves on to the remaining teams, and the always-sent summary still fires. A recurring rate-limit condition escalates to an early, deliberate stop rather than hammering GameChanger. Today only `ForbiddenError` (403) is isolated; any other exception aborts teams 2–4, records nothing, and suppresses the summary.

## Context
In `run_morning`, the per-team block catches only `ForbiddenError` (a legitimate per-team 403 denial, counted into `result.denied`). A transient `GameChangerAPIError` (5xx after retries), an `httpx` connection error, or a `RateLimitError` (429) on team 1's `resolve_own_team_gc_uuid` / `fetch_schedule` / `fetch_opponents` propagates out of the loop, aborts the remaining teams, records nothing for them, and — because it escapes to the CLI — suppresses the always-sent summary that is the system's only missed-run signal. This contradicts the isolation claim in `operations.md`.

This story owns the morning-run **per-team seam**. The client-level 429 cap and the scouting-crawler per-game 429 isolation are E-252-04 (different files); the 02↔04 co-design boundary is in Technical Notes TN-6: team-level 429s (schedule/roster) must still surface HERE so the systemic escalation (TN-9) can see recurring 429s.

Two invariants to preserve (TN-3, and the existing code comments):
- `CredentialExpiredError` (a true token death, HTTP 401) affects EVERY team and MUST remain run-fatal — never swallowed into per-team isolation. `ForbiddenError` (403) is a subclass and is already caught first; the broadened transient/rate-limit catch must be ordered so it never swallows a bare `CredentialExpiredError` (401). Catch order is load-bearing (`.claude/rules/auth-module.md`).
- The shared-connection partial-commit footgun (TN-10): the broadened catch-and-continue runs on the shared `conn`, so the except branch must `conn.rollback()` before the next team.

## Acceptance Criteria
- [ ] **AC-1**: Given a multi-team run where team 1's schedule/opponents crawl raises a transient error (a 5xx `GameChangerAPIError` or an `httpx` connection error), when the run proceeds, then teams 2..N are still processed, the run does not abort, and team 1's failure is recorded in a DISTINCT run-level per-team transient-failure counter on `MorningRunResult` (a `transient` tally parallel to `denied` (403) and `rate_limited` (429) — NOT the slot-level `failed`, which is per-slot generation) and surfaced in the summary detail line.
- [ ] **AC-2**: Given a bare `CredentialExpiredError` (HTTP 401, token death) raised from a per-team crawl, when it occurs, then it is NOT swallowed by per-team isolation and remains run-fatal (propagates so the operator learns the whole run's credentials died), preserving the 401-vs-403 distinction. A `ForbiddenError` (403) continues to be isolated and counted into the `denied` tally exactly as today.
- [ ] **AC-3**: Given a `RateLimitError` (429) surfacing to the per-team seam (e.g. from a schedule/roster fetch) on ONE team, when it occurs, then it is isolated (that team is skipped, the run continues, the always-sent summary still fires) and recorded as a distinct run-level `rate_limited` outcome — mirroring the existing `denied` (403) tally on `MorningRunResult` with a parallel counter and summary line, per Technical Notes TN-9. It is NOT written as a CHECK-constrained `scheduled_report_runs` value.
- [ ] **AC-4**: Given a `RateLimitError` that RECURS across teams (a 2nd occurrence in the same run), when the escalation fires, then the run STOPS making further GameChanger calls for the remaining teams and the summary reports "rate-limited — aborted early" (per Technical Notes TN-9), rather than grinding through the rest.
- [ ] **AC-5**: Given any broadened catch-and-continue branch added by this story (transient, 403, 429), when it catches on the shared connection, then it calls `conn.rollback()` before the next team, per Technical Notes TN-10 (the E-245 partial-commit footgun) — verified by a test that a partially-written failed team does not leave DML that the next successful team's commit persists.
- [ ] **AC-6**: The preflight liveness catch is broadened consistently so a transient (non-auth) preflight failure surfaces as a preflight failure (operator alert + abort) rather than an unhandled crash, without collapsing a genuine 403/401 into the wrong meaning (the existing `PreflightError` 403-vs-401 distinction is preserved).
- [ ] **AC-7**: Error-path tests (per Technical Notes TN-8) cover: transient per-team error isolated AND counted in the `transient` tally (AC-1); 401 run-fatal, 403 isolated-and-counted (AC-2); single 429 isolated + `rate_limited`-tallied (AC-3); recurring 429 escalates to early stop (AC-4); the rollback-in-except behavior (AC-5). Multi-team fixtures (2+ teams) so the audit key `(own_team_id, opponent_root_team_id, game_date)` is exercised without a vacuous pass.

## Technical Approach
Broaden the per-team `except` in `run_morning`'s crawl block to isolate transient errors (5xx `GameChangerAPIError`, `httpx` connection/request errors) and `RateLimitError`, ordered AFTER the existing `ForbiddenError` branch and BEFORE letting a bare `CredentialExpiredError` (401) propagate (catch ordering is load-bearing — `ForbiddenError` subclasses `CredentialExpiredError`; confirm against `src/gamechanger/exceptions.py`). Mirror the existing `denied` (403) tally pattern on `MorningRunResult` for TWO new run-level per-team counters + summary lines: a `transient` counter (5xx/connect failures, AC-1) and a `rate_limited` counter (429, AC-3/TN-9) — both distinct from the slot-level `failed`. Add the recurring-429 escalation (early stop) as run-level control flow. Put a `conn.rollback()` in each broadened except branch (TN-10). Broaden the preflight catch consistently. Coordinate the team-level-vs-per-game 429 boundary with E-252-04 per TN-6. (Counter names are the implementer's choice; the constraint is two distinct per-team tallies mirroring `denied`.)

## Dependencies
- **Blocked by**: E-252-01 (same file: `src/reports/morning_run.py`)
- **Blocks**: E-252-03 (its summary reflects this story's `rate_limited`/transient tallies), E-252-04 (co-design of the 429 isolation seam per TN-6), E-252-05 (same file)

## Files to Create or Modify
- `src/reports/morning_run.py` (per-team `except` block in `run_morning`; `MorningRunResult` `transient` + `rate_limited` tallies + summary lines; escalation control flow; preflight catch; `conn.rollback()` in the broadened branches)
- `tests/test_morning_run.py` (or the existing morning-run test module) — the AC-7 error-path tests

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-252-04**: The per-team 429 seam (rate_limited tally + escalation). E-252-04 isolates per-game 429s at the scouting crawler and must NOT swallow team-level 429s in a way that blinds this escalation (TN-6).
- **Produces for E-252-05, E-252-07**: The current `run_morning` loop structure they build on (same file).

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Audit one-liner (MEDIUM): "Per-team failure isolation covers only 403 — a transient 5xx/429/connect error on team 1 aborts teams 2-4, records nothing, and suppresses the 'always-sent' summary" — `src/reports/morning_run.py:483`. The 429 isolation + escalation (TN-9) is designed against UNOBSERVED GC 429 behavior (TN-6 caveat) — document that in the code.
