# E-240-07: `bb report morning-run` Orchestration

## Epic
[E-240: Morning-of-Game Scheduled Reports](../E-240-morning-scheduled-reports/epic.md)

## Status
`TODO`

## Description
After this story is complete, `bb report morning-run [--date YYYY-MM-DD]
[--dry-run] <team-urls...>` is the cron-invocable entry point that ties the epic
together: for each team (sequentially), it resolves the team's `gc_uuid`, reads
the schedule + opponents registry, filters to the target LOCAL date and drops
canceled games, runs the resolution ladder per upcoming opponent, calls the
existing `generate_report(public_id)` for auto-resolved opponents, records each
scheduled slot's outcome to `scheduled_report_runs`, and sends an end-of-run
operator summary. This is the integration story and carries the heaviest
error-path and multi-team test obligations.

## Context
This is the forward feature itself. It is an orchestration shell over reused
components: E-240-01 (schedule + opponents crawlers), E-240-04 (resolution
ladder), E-240-03 (`scheduled_report_runs` + `opponent_links`), E-240-06
(operator alerts), and the untouched `generate_report()`. The sequential-execution
invariant (TN-2), the three-way outcome + wrong-mapping mitigation (TN-5), the
outcome→vocabulary mapping (TN-11), the 403 disambiguation (TN-4), the hard gates
(TN-8), and the cron mechanics — preflight cred liveness check, per-game
isolation, idempotency, missed-run summary (TN-9) — all converge here. The
crontab line IS the config (variadic team URLs).

## Acceptance Criteria
- [ ] **AC-1** (CR-inspection item, per Technical Notes TN-2): `bb report
  morning-run <team-urls...>` iterates teams **sequentially** (a plain loop, one
  process, never concurrent — no concurrency primitives introduced). This is a
  negative structural invariant verified by code review, not a test-backed AC.
- [ ] **AC-2**: Per team, the command parses the team URL (`parse_team_url()`),
  resolves the team's `gc_uuid` via the E-240-01 own-team resolver
  (`resolve_team(public_id).name` → `search_teams_by_name` → filter by
  `public_id`; C3 — it fetches the public-profile NAME first, never slug-searches),
  fetches the schedule + opponents registry (E-240-01), and filters to the target
  date —
  deriving each game's LOCAL date from its UTC `start.datetime` + the event
  timezone before comparing to `--date` (default: today) — then drops canceled
  games. (Per Technical Notes TN-9 / B3: a UTC-"today" filter would miss
  late-evening games that roll past UTC midnight.)
- [ ] **AC-3**: Per in-scope upcoming opponent, the command runs the resolution
  ladder (E-240-04) and maps the ladder return to the persisted vocabulary
  (`scheduled_report_runs.resolution_outcome`, `delivery_status`) per the mapping
  table in Technical Notes TN-11 — never a silent skip.
- [ ] **AC-4**: For auto-resolved opponents (non-dry-run), the command calls the
  existing `generate_report(public_id)` and records the produced report's
  slug/id. It does NOT modify `generate_report()` (Technical Notes TN-1).
- [ ] **AC-5**: Each scheduled slot writes one `scheduled_report_runs` row,
  idempotent per `(own_team_id, opponent_root_team_id, game_date)` with UPSERT;
  the loader GUARANTEES a non-NULL key on all three columns (falling back to the
  `opponent_id` token) so the UNIQUE index actually dedupes (Technical Notes
  TN-6). A re-run skips a prior SUCCESS per the idempotency predicate in Technical
  Notes TN-9 (`resolution_outcome='auto_resolved'` AND non-NULL non-expired
  `report_id` → `delivery_status='skipped'`).
- [ ] **AC-6**: `--dry-run` generates NO reports and prints, per opponent, the
  opponent text + `opponent_id` + three-way outcome, and for resolved opponents
  the RESOLVED team name + `public_id` + W-L record (the eyeball verification
  line) per Technical Notes TN-5. The record comes from `resolve_team`'s
  `record_wins`/`record_losses` (no game-count field exists on `TeamProfile`; D4).
- [ ] **AC-7**: A preflight credential liveness check runs ONCE at the top
  (Technical Notes TN-9); on an unrecoverable auth failure the command sends the
  preflight-failure operator alert (E-240-06) and aborts early and visibly. The
  preflight-refreshed credentials feed the SAME client/session the crawlers and
  ladder use. A failure-path test mocks the refresh failure explicitly.
- [ ] **AC-8**: Per-game failures are isolated with try/except — one opponent's
  failure records to `scheduled_report_runs` (with `error_message`) and the loop
  continues; it never aborts the run. Per Technical Notes TN-9.
- [ ] **AC-9**: The command honors the hard gates' outcomes (zero completed
  games → `no_games`; all-boxscores-blocked → `failed`, surfaced via the
  end-of-run summary — there is NO dedicated per-game-failure alert helper, per
  Technical Notes TN-7; placeholder → `deferred_placeholder`) per Technical Notes
  TN-8 — recording them in the run record, not re-implementing them.
- [ ] **AC-10**: An unresolved-but-mappable opponent emits a prominent CLI line
  AND an operator alert carrying a TEMPLATE `map-opponent` command with the
  `root_team_id` pre-filled and the URL an explicit placeholder —
  `bb report map-opponent <root_team_id> <PASTE-GC-TEAM-URL>` — since the target
  URL is exactly what the operator must look up (E-240-06 / TN-5).
- [ ] **AC-11**: An end-of-run operator summary email (success/fail counts) is
  always sent when `ADMIN_EMAIL` is configured (warn+skip if unset, per E-240-06
  AC-4) — "always" means not gated on run outcome, the missed-run signal. Per
  Technical Notes TN-9.
- [ ] **AC-12**: Authenticated calls use correct version pins and the command
  does not collapse all 403s into "auth expired" / "no report possible" — a real
  auth failure is distinguished from a legitimate denial, per Technical Notes
  TN-4.
- [ ] **AC-13**: No change to `generate_report()` or generator stages; Epic A
  golden stat tables and `bb report verify-aggregates` parity are unchanged
  (proven by running the guards). Per Technical Notes TN-1.
- [ ] **AC-14**: Tests cover (mocked/fixtured, never real HTTP): multi-team
  sequential iteration; LOCAL-date filter (incl. a late-evening game crossing UTC
  midnight) + canceled drop; each three-way outcome + the TN-11 mapping;
  idempotent re-run (UPSERT dedupe incl. the non-NULL-key fallback and the skip
  predicate); `--dry-run` produces no reports and prints the verification line;
  preflight failure path (alert + early exit, refresh mocked to fail); per-game
  isolation (one failure does not abort the loop); the always-sent end-of-run
  summary; the unresolved-mappable CLI line + alert with embedded command. Error-
  path tests per `.claude/rules/testing.md`.

## Technical Approach
Add the `morning-run` subcommand to the `bb report` CLI group in
`src/cli/report.py` (after E-240-05's `map-opponent`, since both edit this file).
Compose the reused seams: `parse_team_url()` + the search bridge for the
team's `gc_uuid`; the E-240-01 schedule + opponents crawlers; the E-240-04
resolution ladder; `generate_report()` for auto-resolved opponents; the E-240-03
run-record table; the E-240-06 operator alerts and sync wrapper. Keep generation
calls SEQUENTIAL (TN-2). Structure the per-opponent body so a thrown exception is
caught, recorded, and the loop continues (TN-9). The local-date derivation (TN-9)
turns each game's UTC `start.datetime` + timezone into a local date before the
`--date` comparison.

## Dependencies
- **Blocked by**: E-240-01, E-240-03, E-240-04, E-240-05, E-240-06
- **Blocks**: None

## Files to Create or Modify
- `src/cli/report.py` — add the `morning-run` subcommand (orchestration loop)
- `src/reports/morning_run.py` — orchestration helper module (suggested path; the
  SE may name it, but name a specific module — keep generation logic out of
  `generator.py` per TN-1)
- `tests/test_morning_run.py` — new morning-run test file (multi-team +
  error-path coverage per AC-14)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
This is the integration story — it should be the last dispatched. Its safety
rests on TN-1 (it never enters the generator's internals) and TN-2 (sequential,
single-process, respecting the Epic B concurrency lock and orphan attribution).
The `--date` override + an operator runbook note (a closure docs obligation, not
code) handle early-start tournaments.
