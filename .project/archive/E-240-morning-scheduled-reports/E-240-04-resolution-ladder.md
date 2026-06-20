# E-240-04: Opponent Resolution Ladder (Rungs a–d)

## Epic
[E-240: Morning-of-Game Scheduled Reports](../E-240-morning-scheduled-reports/epic.md)

## Status
`DONE`

## Description
After this story is complete, the system can take an upcoming game's
`opponent_id` + `opponent_name` (from E-240-01's schedule crawler) plus the
team's opponents-registry records (from E-240-01's opponents crawler) and resolve
the opponent to a GameChanger `public_id` (or a deferred-placeholder /
unresolved-but-mappable outcome) via the ordered resolution ladder, persisting
the result in the revived `opponent_links` table so each opponent is resolved
once **per team-opponent pairing** and cached. (The ladder never produces
`no_gc_presence` — that is operator-declared only via `map-opponent
--no-presence`; C1.)

## Context
This is the heart of the morning-run feature's correctness. The
`opponent_id → root_team_id → progenitor_team_id` join is verified 54/54; the
schedule cannot shortcut to a canonical UUID because `progenitor_team_id` is
absent from `pregame_data`, so rung (a) reads it from the LIVE authenticated
opponents registry (built in E-240-01) — the old `opponent_resolver.py` bridging
code was DELETED in E-239 and must NOT be "reused." The full ladder (rungs a–d),
the namespace rules, the key-absent eligibility test, the search-helper routing,
the unambiguous-single-match rule, the placeholder name patterns (and the
by-design fall-through for event names that escape them), and the three persisted
`opponent_links` states are specified in Technical Notes TN-3; the 403
disambiguation and version pins (opponents `0.0.0`, reverse-bridge `team+json
0.10.0`, search `0.0.0`) in TN-4; the outcome→vocabulary mapping in TN-11. This
story implements that ladder as a reusable resolution function E-240-07 calls per
upcoming opponent, and it persists the pending not-resolved row that
`bb report map-opponent` (E-240-05) later UPDATEs.

## Acceptance Criteria
- [ ] **AC-1**: Given an upcoming game's `opponent_id`, the ladder joins it as a
  `root_team_id` against the opponents-registry records (from E-240-01) and reads
  `progenitor_team_id` using a **key-absent** eligibility test
  (`"progenitor_team_id" in record`), never a truthiness/null check. Per Technical
  Notes TN-3 rung (a).
- [ ] **AC-2**: When `progenitor_team_id` is present, the ladder calls
  `GET /teams/{progenitor_team_id}` (NOT `…/public-team-profile-id`) with the
  correct version pin per Technical Notes TN-4 (`team+json; version=0.10.0`) to
  obtain `public_id`, and records resolution method `progenitor`. Per TN-3 rung (a).
- [ ] **AC-3**: `opponent_id` is NEVER passed to `GET /teams/{id}` (wrong
  namespace) — verified by test. When `opponent_id` is wholly absent from the
  registry records, the ladder falls through gracefully (defensive guard, rare per
  the F4 probe). Per TN-3 / TN-4.
- [ ] **AC-4**: Placeholder opponents (name matching the TN-3 pattern set) are
  classified as deferred and persist NO `opponent_links` row. Event/tournament
  names that escape the pattern set are NOT chased — they fall through to rung
  (c)/(d) by design (Technical Notes TN-3 rung b).
- [ ] **AC-5**: The search rung routes exclusively through
  `search_teams_by_name()` (never `client.post_json("/search", …)`), uses a real
  `name` field as the query (never a URL slug), auto-ingests ONLY on an
  unambiguous single match, and treats a zero-hit as ambiguous → falls to the
  operator-queue outcome rather than a hard failure. Per TN-3 rung (c).
- [ ] **AC-6**: Each resolution writes the correct `opponent_links` state per
  TN-3 via `INSERT ... ON CONFLICT(our_team_id, root_team_id) DO UPDATE`, setting
  `resolved_at` on a positive resolution. The ladder writes ONLY two states:
  - resolved-positive (`public_id` set, method `progenitor`/`search`),
  - **not-resolved/pending for unresolved-but-mappable (rung d): a row with
    `our_team_id` + `root_team_id` + `opponent_name`, `public_id` NULL,
    `resolution_method` NULL** — this is the pending row `map-opponent` (E-240-05)
    UPDATEs.
  The ladder NEVER writes the resolved-negative `no_presence` state — that is
  operator-declared only via `map-opponent --no-presence` (C1 decision; per
  Technical Notes TN-3 / TN-11). A zero-hit/no-match leaves the opponent
  `unresolved_mappable`, not `no_gc_presence`.
- [ ] **AC-7**: Re-running the ladder for an already-terminal opponent reuses the
  cached mapping and does NOT re-attempt resolution. The terminality gate keys on
  `resolution_method IS NOT NULL` (covers BOTH resolved-positive AND the
  operator-declared `no_presence` row), NEVER on `public_id IS NOT NULL` — a
  `no_presence` row has `public_id` NULL, so a public_id-based gate would
  re-queue and re-attempt it every run (the resurrection bug). Per Technical Notes
  TN-3 (Terminality gate).
- [ ] **AC-8**: The three `opponent_links` states are read from `public_id` +
  `resolution_method` ONLY; a NULL `resolved_team_id` on a resolved-positive row
  is NOT treated as "not resolved" (per Technical Notes TN-3).
- [ ] **AC-9**: Every authenticated call uses the correct version pin per
  Technical Notes TN-4 and does not collapse all 403s into "auth expired".
- [ ] **AC-10**: The follow→bridge→unfollow resolver path is NOT used anywhere in
  this story (banned per epic Non-Goals / `.claude/rules/gc-uuid-bridge.md`).
- [ ] **AC-11**: No change to `generate_report()`; Epic A goldens +
  `bb report verify-aggregates` parity unchanged. Per Technical Notes TN-1.
- [ ] **AC-12**: Tests (mocked/fixtured, never real HTTP) cover each rung
  including: key-absent vs. null `progenitor_team_id`; the `opponent_id` namespace
  guard; the registry-absent fall-through; placeholder classification + the
  escaped-event-name fall-through; unambiguous-single-match vs.
  multiple-match/zero-hit (the latter → `unresolved_mappable`, NOT
  `no_gc_presence`); the persisted pending (not-resolved) row for rung (d); the
  terminality gate keyed on `resolution_method IS NOT NULL` (incl. that a
  `no_presence` row is NOT re-attempted — the resurrection-bug regression); and
  the persisted states read from `public_id`/`resolution_method`.

## Technical Approach
Build a reusable resolution function/module that takes the upcoming-game record
shape and the opponents-registry records from E-240-01, plus the `opponent_links`
store from E-240-03, and returns a structured outcome (resolved `public_id` +
method, or one of the non-auto-resolved outcomes per TN-11). For rung (a), build
the live `opponents`-registry → `GET /teams/{progenitor_team_id}` chain per
`docs/api/flows/opponent-resolution.md` **Pass 1 ONLY** — do NOT reuse the deleted
`opponent_resolver.py` logic, and do NOT touch the banned follow→bridge→unfollow
path. Reuse `search_teams_by_name()` (`src/gamechanger/search.py`) for rung (c)
and the project `GameChangerClient`. Keep this a pure resolution seam; generation,
run-record writes, and operator surfacing belong to E-240-07. Reference
`.claude/rules/gc-uuid-bridge.md` (search-helper quirks, namespaces, reverse
bridge).

## Dependencies
- **Blocked by**: E-240-01 (upcoming-game + opponents-registry record shapes),
  E-240-03 (`opponent_links`)
- **Blocks**: E-240-05 (map-opponent UPDATEs the pending not-resolved row this
  ladder persists), E-240-07 (orchestration calls the ladder)

## Files to Create or Modify
- `src/gamechanger/opponent_ladder.py` — new opponent resolution ladder module
  (suggested path; SE may place it alongside the gc-uuid bridge / search seams,
  but name a specific module — do not leave it as a bare `src/`)
- `tests/test_opponent_ladder.py` — new test file covering all four rungs, the
  terminality gate, and the persisted states

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-240-05**: the pending not-resolved `opponent_links` row (keyed
  on `our_team_id` + `root_team_id`, carrying `opponent_name`) that
  `map-opponent` locates by `root_team_id` and UPDATEs.
- **Produces for E-240-07**: the per-opponent resolution outcome (resolved
  `public_id` + method, or deferred-placeholder / unresolved-mappable) that the
  orchestration maps to a `scheduled_report_runs` outcome per TN-11 and either
  generates a report or surfaces for `map-opponent`. (The ladder never returns
  no_gc_presence — operator-declared only; C1.)

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
A wrong-team false-positive in the search rung silently scouts the wrong
opponent — the unambiguous-single-match rule (AC-5) plus the `--dry-run`
resolved-name eyeball verification line (E-240-07, TN-5) are the two mitigations.
