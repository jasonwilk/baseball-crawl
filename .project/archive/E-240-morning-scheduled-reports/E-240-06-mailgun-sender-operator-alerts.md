# E-240-06: Generic Mailgun Sender Extraction + Operator Alerts

## Epic
[E-240: Morning-of-Game Scheduled Reports](../E-240-morning-scheduled-reports/epic.md)

## Status
`DONE`

## Description
After this story is complete, `src/api/email.py` exposes a generic async email
sender (subject + body provided by the caller), the existing magic-link email is
re-expressed as a thin caller of it (behavior preserved), and there are
operator-alert helpers the morning-run uses for preflight-failure,
unresolved-but-mappable, and end-of-run-summary notifications. This is the
delivery substrate for E-240-07 — operator-only, no coach-facing content.

## Context
`src/api/email.py` today hardcodes the magic-link subject/body inside
`send_magic_link_email`. The morning-run needs to send operator alerts, so the
generic sender must be extracted first (operator decision: coach delivery is
deferred — IDEA-080 — but operator alerts ship now). The three alerts and the
sync-CLI/async-sender wrapper are specified in Technical Notes TN-7; the
always-sent end-of-run summary is the minimal missed-run signal (TN-9). The
no-`MAILGUN_API_KEY` stdout fallback (local dev) must be preserved.

## Acceptance Criteria
- [ ] **AC-1**: `src/api/email.py` exposes a generic async sender taking
  recipient, subject, and body, preserving the current Mailgun behavior including
  the no-`MAILGUN_API_KEY` stdout fallback and the success/failure return
  semantics.
- [ ] **AC-2**: `send_magic_link_email` is re-expressed as a thin caller of the
  generic sender with no change to its observable behavior — its existing tests
  pass unmodified (or only with mechanical import/call-shape updates that assert
  the same outcomes).
- [ ] **AC-3**: EXACTLY three operator-alert helpers exist (per Technical Notes
  TN-7 — no fourth): (a) preflight credential-refresh failure, (b)
  unresolved-but-mappable opponent — the body carries a TEMPLATE
  `bb report map-opponent <root_team_id> <PASTE-GC-TEAM-URL>` command with the
  `root_team_id` pre-filled and the URL an explicit placeholder the operator
  completes after looking up the team (the URL is unknown by definition for an
  unresolved opponent; per Technical Notes TN-5/TN-7), and (c) an end-of-run
  summary with success/fail counts (per
  Technical Notes TN-9). All are operator-only (no coach content). There is NO
  per-game-failure helper — a per-game failure (e.g. all-boxscores-blocked →
  `failed`) is surfaced via the end-of-run summary (c), not a dedicated alert.
- [ ] **AC-4**: All three operator alerts are addressed to `ADMIN_EMAIL` (the
  established operator-identity env var — no new config var), per Technical Notes
  TN-7 (C2). When `ADMIN_EMAIL` is unset, the alert helper logs a visible warning
  and SKIPS sending — it does NOT crash the run (alerting is a side channel).
- [ ] **AC-5**: A sync wrapper allows the synchronous `morning-run` CLI to invoke
  the async sender (per Technical Notes TN-7).
- [ ] **AC-6**: Tests (mocked, never real HTTP per `.claude/rules/testing.md`)
  cover the generic sender (both the configured-Mailgun and stdout-fallback
  paths), the preserved magic-link behavior, the three operator-alert helpers'
  content (including the embedded `map-opponent` command), the `ADMIN_EMAIL`-unset
  warn-and-skip path, and the sync wrapper. Error-path test: a sender failure is
  surfaced, not silently swallowed (`.claude/rules/testing.md` Error-Path Testing).
- [ ] **AC-7**: No change to `generate_report()`; Epic A goldens unchanged. Per
  Technical Notes TN-1.

## Technical Approach
Refactor `src/api/email.py`: lift the Mailgun POST + stdout-fallback logic into a
generic sender, and make `send_magic_link_email` build the magic-link subject/body
and delegate. Add operator-alert helpers (thin functions composing
subject/body for the three alert types) in `src/api/email.py` or an adjacent
module per the SE's judgement. Provide an `asyncio.run()`-style sync entry the CLI
can call. Run the discovered test scope for `src.api.email` per
`.claude/rules/testing.md` (Test Scope Discovery) — grep `tests/` for importers
of the email module and run them all.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-240-07 (orchestration calls the operator-alert helpers)

## Files to Create or Modify
- `src/api/email.py` — extract generic sender; add the three operator-alert
  helpers (→ `ADMIN_EMAIL`) + sync wrapper
- `tests/test_email.py` — extend with generic-sender, preserved-magic-link,
  three-alert, `ADMIN_EMAIL`-unset, and sync-wrapper tests (plus any importer
  tests surfaced by Test Scope Discovery)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-240-07**: the generic sender, the three operator-alert
  helpers, and the sync-CLI wrapper the orchestration uses for preflight-failure,
  unresolved-but-mappable, and end-of-run-summary notifications.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests (magic-link login behavior preserved)

## Notes
Coach-facing email delivery (subject/body content for coaches,
`report_subscriptions`) is explicitly OUT of scope — deferred to IDEA-080. This
story ships only the operator-facing substrate and alerts.
