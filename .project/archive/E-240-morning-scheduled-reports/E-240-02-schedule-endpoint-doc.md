# E-240-02: Schedule Endpoint Doc + Opponent-Resolution Flow-Doc Refresh

## Epic
[E-240: Morning-of-Game Scheduled Reports](../E-240-morning-scheduled-reports/epic.md)

## Status
`DONE`

## Description
After this story is complete, `docs/api/endpoints/get-teams-team_id-schedule.md`
documents that the authenticated schedule endpoint is reachable at fan/follower
level (verified 2026-06-17), that it returns future-dated games with
`pregame_data` (opponent_id + opponent_name), and the doc's `last_confirmed`
date is bumped; AND `docs/api/flows/opponent-resolution.md` is refreshed so it
describes the resolution path E-240 actually uses (Pass 1 progenitor chain) and
no longer presents deleted machinery or the banned follow→bridge→unfollow path
as current. This makes the verified capabilities E-240-01/04 build on documented
API facts rather than tribal knowledge, and removes a stale doc that contradicts
the Non-Goals.

## Context
The live probe (api-scout, 2026-06-17) confirmed `GET /teams/{gc_uuid}/schedule`
(Accept `event:list+json; version=0.2.0`) returns 200 at fan/follower level for
a followed-not-managed team, with future-dated games carrying `pregame_data`
including `opponent_id` + `opponent_name`, and that canceled games appear and
must be filtered. Separately, the flow doc `docs/api/flows/opponent-resolution.md`
is currently STALE (verified): it describes the deleted admin resolve UI, the
deleted two-pass resolver and `bb data resolve-opponents`, and presents the
banned follow→bridge→unfollow path as a "Legacy experimental path" — which
contradicts the epic Non-Goals and `.claude/rules/gc-uuid-bridge.md`. Both files
are api-scout-owned (`docs/api/**`, per `.claude/rules/documentation.md`). This is
a documentation slice grounded entirely on existing probe evidence + the current
repo state — it does not depend on E-240-01's crawler code.

## Acceptance Criteria
- [ ] **AC-1**: `docs/api/endpoints/get-teams-team_id-schedule.md` gains an
  Access Level section stating fan/follower-level access is verified
  (2026-06-17), with the version pin `event:list+json; version=0.2.0`.
- [ ] **AC-2**: The doc records the 2026-06-17 confirmation that the endpoint
  returns future-dated (upcoming) games carrying `pregame_data` with non-null
  `opponent_id` + `opponent_name`. (C5: the schedule doc ALREADY documents
  `opponent_id`=`root_team_id` namespace, nullable `home_away`, canceled
  filtering, and progenitor usage — do NOT re-add those; they are not the delta.
  The only future-games content to touch is the dated confirmation.)
- [ ] **AC-3**: The schedule endpoint doc's `last_confirmed` / staleness date is
  bumped to 2026-06-17 per the staleness convention.
- [ ] **AC-4**: `docs/api/flows/opponent-resolution.md` is refreshed: it scopes
  the reusable resolution mechanism to **Pass 1** (the `opponents` registry →
  `GET /teams/{progenitor_team_id}` progenitor chain) plus the search fallback;
  removes or clearly marks-as-removed the deleted admin resolve UI, the deleted
  two-pass resolver, and `bb data resolve-opponents`; and marks the
  follow→bridge→unfollow path as BANNED (not "legacy"), consistent with
  `.claude/rules/gc-uuid-bridge.md` and the epic Non-Goals.

## Technical Approach
Edit the two existing docs in place. Source the schedule content from the probe
evidence in the epic Background and the consolidated api-scout findings; source
the flow-doc corrections from the current repo state (deleted modules/commands)
and `.claude/rules/gc-uuid-bridge.md` (the banned path). No code, no tests — this
is a documentation slice for api-scout-owned files.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `docs/api/endpoints/get-teams-team_id-schedule.md`
- `docs/api/flows/opponent-resolution.md`

## Agent Hint
api-scout

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Doc follows the staleness convention (`.claude/rules/documentation.md`)
- [ ] No regressions in existing tests (doc-only change)

## Notes
The 1-team/1-call probe sample is the basis; the doc may note that the
future-games observation is a single-team confirmation strengthened by
E-240-01's crawler run.
