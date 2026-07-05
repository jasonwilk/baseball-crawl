# E-252-03: Guarantee the end-of-run summary email (missed-run signal)

## Epic
[E-252: Scheduled-Reports Reliability (Cron-Grade Morning-Run)](../E-252-scheduled-reports-reliability/epic.md)

## Status
`TODO`

## Description
After this story is complete, the always-sent end-of-run summary email — the system's only missed-run signal — is guaranteed to be attempted on every non-dry-run (including when the run body crashes), a misconfigured alerting channel is caught loudly before the run rather than silently after, and the operator can tell a real send from a silently-dropped one.

## Context
The summary email is the heartbeat: its ABSENCE is how the operator learns a run failed (silence = something failed). The audit found three gaps that let the heartbeat lie or vanish (TN-7):
- **(a) The send result is discarded.** `bb report morning-run` calls `send_end_of_run_summary_sync(...)` and ignores the returned bool; the CLI exits 0 even if the send failed.
- **(b) An unset `ADMIN_EMAIL` silently disarms the heartbeat forever.** `_send_operator_alert` (`src/api/email.py`) warns and returns `False` when `ADMIN_EMAIL` is unset — the run proceeds and no one is ever emailed, indistinguishable from a healthy quiet day.
- **(c) An unset `MAILGUN_API_KEY` returns a false "sent".** `send_email` logs the body to stdout and returns `True` when Mailgun is unconfigured — correct for local dev, but in production it reports success while sending nothing.

Additionally, a crash in the run body (before E-252-02's isolation catches it, or from a path it doesn't cover) escapes to the CLI and skips the summary entirely — the run dies silently.

## Acceptance Criteria
- [ ] **AC-1**: Given a non-dry-run whose run body raises an unexpected exception, when the CLI handles it, then the end-of-run summary is still attempted (via a try/finally around the run body) and the operator receives a summary reflecting the failure; the CLI then exits non-zero. A dry-run does NOT send a summary (unchanged).
- [ ] **AC-2**: Given a non-dry-run, when the alerting channel is misconfigured such that no operator email can be delivered (per Technical Notes TN-7 — e.g. `ADMIN_EMAIL` unset, or `MAILGUN_API_KEY` unset while `APP_ENV` is production), then the preflight validation detects it and aborts the run loudly (non-zero exit, clear operator-facing message) BEFORE the run body executes — rather than running to completion with a silently-disarmed heartbeat.
- [ ] **AC-3**: Given a non-dry-run where the summary send is attempted and the underlying send fails or is skipped, when the CLI finishes, then it does not report false success: the failed/skipped send exits NON-ZERO and logs a clear error line (the non-zero exit is the contract — a cron/monitor captures it; the log line accompanies it, it is not the sole signal). The send is retried per the story's chosen retry shape before being declared failed. (Contract unified with AC-6.)
- [ ] **AC-4**: Given a production environment (`APP_ENV` production) with `MAILGUN_API_KEY` unset, when an operator email would be sent, then the stdout fallback does NOT report the message as sent — the dev-stdout path is tri-stated so "logged to stdout" is treated as success only in non-production; in production an unconfigured Mailgun is a failure/misconfiguration, not a silent success.
- [ ] **AC-5**: The local-dev experience is preserved: with `APP_ENV` development (or unset) and no Mailgun configured, operator alerts and the summary continue to log to stdout and are treated as sent (no crash, no abort) — the tri-state must not break local dev.
- [ ] **AC-6**: Error-path tests (per Technical Notes TN-8) cover: a crashing run body still emails a summary and exits non-zero (AC-1); a misconfigured channel aborts in preflight (AC-2); a failed send surfaces non-zero (AC-3); production-unset-Mailgun is not a false success (AC-4); dev-stdout still works (AC-5).

## Technical Approach
Close the three TN-7 gaps together because they share the alerting surface:
- Wrap the run body at the CLI (`morning_run_cmd` in `src/cli/report.py`) so the summary is attempted in a `finally` and a body crash yields a summary + non-zero exit.
- Add an alerting-config validation to the non-dry-run preflight (alongside the existing credential preflight) that fails loudly when no operator email can be delivered, per TN-7. Distinguish dev (stdout is fine) from production (unconfigured Mailgun is a misconfiguration).
- Check the send result (with a retry) and surface a failed/skipped send rather than exiting 0.
- Tri-state the `send_email` dev fallback in `src/api/email.py` so "logged to stdout" counts as sent only outside production. For production detection, add a shared `is_production()` helper to `src/api/helpers.py` (the canonical env-read seam that already holds `get_app_url()`; a leaf util importing only `datetime`+`os`, so no import cycle — note that importing `routes/auth.py::_is_dev_mode` directly WOULD cycle, since `routes/auth.py` already imports from `email.py`). `email.py`'s tri-state and `cli/report.py`'s preflight both call `is_production()`, and `routes/auth.py::_is_dev_mode` is repointed to `return not is_production()` so prod detection is single-sourced (eliminating the two-idiom smell). Semantics: `is_production()` returns `os.environ.get("APP_ENV","development") == "production"`, mirroring the existing `== "production"` idiom in `csrf.py`/`auth.py`/`main.py`.

Keep the operator-only, no-coach-content invariant of the alerts (E-240-06 TN-7). Reuse the existing sync wrappers; do not change the async alert signatures unless necessary.

## Dependencies
- **Blocked by**: E-252-02 (per-team isolation shapes what the summary reports — the `rate_limited`/transient tallies are surfaced in the summary), E-252-06 (both restructure the `src/cli/report.py:438` connection block: E-252-06 routes it through the factory / GAP A, this story wraps it in try/finally — E-252-06 must land first to avoid a collision on the same lines)
- **Blocks**: None

## Files to Create or Modify
- `src/api/helpers.py` (new `is_production()` helper — the single-source prod-detection seam)
- `src/api/email.py` (`send_email` tri-state dev fallback using `is_production()`; any preflight-validation helper for alerting config)
- `src/cli/report.py` (`morning_run_cmd` — try/finally around the run body; preflight alerting-config validation via `is_production()`; check/retry the summary send)
- `src/api/routes/auth.py` (repoint `_is_dev_mode` to `return not is_production()` — behavior-preserving single-source)
- `tests/test_helpers.py` (new — `is_production()` for production / development / unset `APP_ENV`)
- `tests/test_cli_report.py` and/or `tests/test_email.py` (or the existing modules) — the AC-6 error-path tests
- Per test-scope-discovery (`.claude/rules/testing.md`): grep `tests/` for files importing `routes.auth` / exercising `_is_dev_mode` and run them (the delegation is behavior-preserving, but the discipline applies)

Routing note: all source files here are under `src/` (implementation, software-engineer domain) — no context-layer path is touched.

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Audit one-liner (MEDIUM): "Nothing guarantees the summary email — send result discarded (exit 0 on failure); unset `ADMIN_EMAIL` silently disarms the heartbeat; unset `MAILGUN_API_KEY` logs the body and returns True ('sent')" — `src/cli/report.py:507`, `src/api/email.py:52/148`.
