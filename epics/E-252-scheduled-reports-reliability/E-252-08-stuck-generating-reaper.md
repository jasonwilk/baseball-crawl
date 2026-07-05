# E-252-08: Stuck-'generating' report reaper

## Epic
[E-252: Scheduled-Reports Reliability (Cron-Grade Morning-Run)](../E-252-scheduled-reports-reliability/epic.md)

## Status
`TODO`

## Description
After this story is complete, a report whose generation process died mid-flight (leaving its `reports` row stuck at `status='generating'`) is eventually reaped to a terminal `failed` state, so the admin page stops meta-refreshing on it forever and the row becomes deletable through the normal admin UI instead of requiring raw SQL.

## Context
`_create_report_row` inserts a `reports` row with `status='generating'` before the crawl/load/render pipeline runs; `_update_report_ready` / `_update_report_failed` transition it at the end. If the process dies mid-generation (SIGKILL, container restart, an uncaught crash outside the failure handler), the row stays `generating` forever. Consequences the audit found: the admin `/admin/reports` page meta-refreshes indefinitely waiting for a status that will never change, and the delete button is hidden for `generating` rows, so recovery requires raw SQL. Orphan HTML is possible. This is especially relevant to the unattended path — a morning-run-generated report that dies leaves a stuck row no one is watching.

Audit fix direction: a stale-run reaper in the app lifespan and/or `cleanup_expired_reports`, transitioning reports that have been `generating` past a staleness threshold to `failed`.

## Acceptance Criteria
- [ ] **AC-1**: Given a `reports` row stuck at `status='generating'` whose `generated_at` (start) is older than a staleness threshold, when the reaper runs, then the row is transitioned to `status='failed'` with an operator-readable error message indicating it was reaped as a stale/incomplete generation.
- [ ] **AC-2**: Given a `reports` row at `status='generating'` that is WITHIN the staleness threshold (a genuinely in-progress generation), when the reaper runs, then the row is left untouched (still `generating`) — the reaper must not kill a live generation.
- [ ] **AC-3**: The reaper is reachable on a real trigger that fires without operator action — the app lifespan startup and/or the opportunistic `cleanup_expired_reports` path (which already runs at the start of `bb report generate`) — so a stuck row is eventually reaped without a dedicated manual command. The chosen trigger(s) are documented in the story.
- [ ] **AC-4**: After a row is reaped to `failed`, it renders in `/admin/reports` as a terminal failed report (no indefinite meta-refresh) and is deletable through the normal admin flow (the delete affordance is available for `failed` rows). Verify against the admin template/route behavior; do not regress the meta-refresh behavior for genuinely-generating rows.
- [ ] **AC-5**: The staleness threshold is a single named constant `STALE_GENERATING_SECONDS = 3600` (1 hour). Derivation rule (recorded in code so a reviewer can tell what passes): the value MUST be ≥ the max realistic single-report end-to-end generation wall-time (crawl + load + spray + plays + render — "a few minutes" per the `bb report generate` CLI help) PLUS a large safety margin, and MUST be well below the 14-day report expiry. The reaper compares a `generating` row's age (`generated_at`, the generation START) against this constant, so it bounds ONE report's generation, not the whole multi-team run; 1 hour is ~10-20× a real single-report generation and safely clears a live CROSS-PROCESS generation (the app-lifespan reaper firing while a CLI/cron generation is mid-flight in a different process), so the reaper never kills an actively-generating report. The constant is operator-tunable.
- [ ] **AC-6**: Tests cover: a stale `generating` row is reaped to `failed` (AC-1); a fresh `generating` row within the threshold is left alone (AC-2); the reaper fires on its real no-operator-action trigger (`cleanup_expired_reports` and/or the app lifespan — AC-3), asserted by invoking that trigger and observing the stale row transition; the reaper is idempotent (running it twice does not corrupt an already-`failed` or already-`ready` row). For AC-4 (reaped `failed` row renders terminal + deletable in `/admin/reports`): assert the delete-affordance/status gating at the route or template level where testable, and record an explicit manual-verification note for the pure admin-UI render that is not unit-testable.

## Technical Approach
Add a reaper that selects `reports` rows in `status='generating'` older than a staleness threshold and transitions them to `failed` with a clear reaped-message, reusing the existing `_update_report_failed` shape where practical. Wire it into a no-operator-action trigger — the app lifespan startup in `src/api/main.py` and/or the opportunistic `cleanup_expired_reports` in `src/reports/generator.py` (which already runs at `bb report generate` start). Confirm the admin `/admin/reports` route/template shows failed rows as terminal and deletable (the delete affordance is gated on status). Keep the threshold as a single named constant (AC-5). Verify the `reports` status lifecycle against `src/reports/generator.py` and the admin route in `src/api/routes/reports_admin.py`.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/reports/generator.py` (reaper function; wire into `cleanup_expired_reports` if chosen)
- `src/api/main.py` (lifespan startup trigger if chosen)
- `tests/test_report_generator.py` (or the existing generator test module) — reaper tests
- (Read-only verification, modify only if needed) `src/api/routes/reports_admin.py` / the admin template for the deletable-failed-row behavior

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Audit one-liner (MEDIUM): "Process death mid-generation leaves reports stuck at 'generating' forever — no reaper; admin page meta-refreshes indefinitely; delete button hidden for generating rows, so recovery requires raw SQL; orphan HTML possible" — `src/reports/generator.py:241`.
