# E-240-05: `bb report map-opponent` CLI Command

## Epic
[E-240: Morning-of-Game Scheduled Reports](../E-240-morning-scheduled-reports/epic.md)

## Status
`DONE`

## Description
After this story is complete, the operator can run
`bb report map-opponent <root_team_id> <public_id | GC team URL>` to manually
resolve an unresolved-but-mappable opponent. The command locates the pending
not-resolved `opponent_links` row(s) by `root_team_id` (those the resolution
ladder persisted in rung (d)), derives `our_team_id` + `opponent_name` from them,
and UPDATEs them to resolved-positive — setting `public_id`,
`resolution_method='operator'`, and `resolved_at` — so every future scheduled
game against that opponent auto-resolves. A `--no-presence` form (no target)
instead UPDATEs them to the operator-declared resolved-negative state
(`resolution_method='no_presence'`, `public_id` NULL) — this is the ONLY way
`no_gc_presence` is ever set (the auto-ladder never sets it; C1 decision). This is
the operator's one-time resolution action for ladder rung (d).

## Context
The unresolved opponent has no `public_id` yet and its free-text name is the
least reliable field in the system (coaches type opponent names by hand). Keying
on the stable `root_team_id` registry identifier (operator decision #2,
`docs/ROADMAP.md` §5) avoids the name-matching trap. Both the `root_team_id`
(copied off the `--dry-run` line) and the target (`public_id` or full GC team
URL) are copy-paste. `root_team_id` is a separate namespace from `gc_uuid` and
MUST NOT land in a `gc_uuid` column (CLAUDE.md "Opponent entry duality").
**Critical mechanics (per B4):** `opponent_links.our_team_id` and `opponent_name`
are NOT NULL (and `our_team_id` is in the UNIQUE key), but the command's
signature supplies neither — so map-opponent CANNOT blindly INSERT. It must
UPDATE the pending row(s) the ladder (E-240-04) already wrote, deriving the
NOT NULL columns from them. Because `opponent_links` is keyed per owning-team, a
single `root_team_id` can have a pending row for MULTIPLE LSB teams — map-opponent
resolves ALL of them at once.

## Acceptance Criteria
- [ ] **AC-1**: `bb report map-opponent <root_team_id> <target>` locates the
  pending not-resolved `opponent_links` row(s) by `root_team_id` and UPDATEs each
  to resolved-positive: sets `public_id` (from `<target>`),
  `resolution_method='operator'`, and `resolved_at`; deriving `our_team_id` +
  `opponent_name` from the existing pending row (NOT from the command args).
- [ ] **AC-2**: When multiple LSB teams have a pending row for the same
  `root_team_id`, ALL of them are updated in one invocation (resolve every team
  facing that opponent at once).
- [ ] **AC-3**: If NO pending row exists for the `root_team_id`, the command
  errors clearly (e.g. "no pending opponent for that root_team_id — run
  `bb report morning-run --dry-run` first") and makes no write — it does NOT blind
  INSERT a row with unknown `our_team_id`/`opponent_name`.
- [ ] **AC-4**: The `<target>` accepts either a bare `public_id` or a full GC
  team URL, reusing the existing `parse_team_url()` to extract the `public_id`
  from a URL.
- [ ] **AC-5**: The command displays the resolved opponent's team name (for
  confirmation) but KEYS the located/updated rows on `root_team_id`, not the name.
  The `root_team_id` value is never written to a `gc_uuid` column (namespace
  separation).
- [ ] **AC-6**: A `--no-presence` form — `bb report map-opponent <root_team_id>
  --no-presence` (no `<target>`) — UPDATEs the same pending row(s) by
  `root_team_id` to the operator-declared resolved-negative state
  (`resolution_method='no_presence'`, `public_id` NULL, `resolved_at` set),
  deriving `our_team_id`/`opponent_name` from the pending row and updating ALL LSB
  teams' rows for that `root_team_id`. Same no-pending-row error path as AC-3.
  This is the ONLY producer of `no_gc_presence` (C1; per Technical Notes TN-3 /
  TN-11 — the auto-ladder never sets it).
- [ ] **AC-7**: A subsequent resolution attempt (the E-240-04 ladder, exercised
  in test) finds the operator-supplied mapping and does NOT re-attempt it for BOTH
  forms: a positive mapping (`resolution_method='operator'`, `public_id` set)
  auto-resolves; a `no_presence` mapping (`resolution_method='no_presence'`,
  `public_id` NULL) is treated as terminal and is NOT re-queued — the terminality
  gate keys on `resolution_method IS NOT NULL` (Technical Notes TN-3; the
  resurrection-bug guard).
- [ ] **AC-8**: Tests (mocked/fixtured) seed a pending not-resolved row and cover:
  the positive UPDATE, the `--no-presence` UPDATE, the multi-team update, the
  no-pending-row error path (both forms), URL-vs-bare-`public_id` target parsing,
  `resolved_at` being set, the name-display-but-id-key behavior, and the
  terminality of a `no_presence` row on a subsequent ladder run.
- [ ] **AC-9**: No change to `generate_report()`; Epic A goldens unchanged. Per
  Technical Notes TN-1.

## Technical Approach
Add a `map-opponent` subcommand to the `bb report` CLI group in
`src/cli/report.py` (the existing `generate` / `list` / `cleanup` commands are
the pattern reference). Reuse `parse_team_url()` for the target. The DB write is
an UPDATE of `opponent_links` pending rows located by `root_team_id` (the schema
+ revival convention come from E-240-03; the pending-row shape from E-240-04 rung
(d)). Resolving the target's display name for confirmation may reuse an existing
public-team lookup; the SE chooses the lightest path that confirms the operator
picked the right team. Keep it a small Typer command.

## Dependencies
- **Blocked by**: E-240-03 (`opponent_links` revival), E-240-04 (the ladder
  persists the pending not-resolved row this command UPDATEs; E-240-04 defines the
  pending-row shape)
- **Blocks**: E-240-07 (both add `bb report` subcommands to `src/cli/report.py`
  — E-240-07 depends on this story to serialize that shared-file edit)

## Files to Create or Modify
- `src/cli/report.py` — add the `map-opponent` subcommand (positive +
  `--no-presence` forms)
- `tests/test_cli_report.py` — extend with the `map-opponent` tests (per AC-8)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-240-07**: an operator-resolved `opponent_links` mapping the
  orchestration's ladder call will find on the next run, plus the established
  `src/cli/report.py` subcommand pattern E-240-07 follows for `morning-run`.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
This command and E-240-07's `morning-run` both edit `src/cli/report.py`; the
E-240-07 → E-240-05 dependency serializes those edits (this story runs first).
The B4 mechanics (UPDATE a pending row, never blind INSERT) exist because
`opponent_links` requires `our_team_id` + `opponent_name`, which the command's
two-argument signature does not carry.
