# E-240-01: Authenticated List-Crawlers (Schedule + Opponents-Registry) + Probe-Confirmation Tests

## Epic
[E-240: Morning-of-Game Scheduled Reports](../E-240-morning-scheduled-reports/epic.md)

## Status
`DONE`

## Description
After this story is complete, the system can fetch, for an LSB team, BOTH (1) its
GameChanger schedule via authenticated `GET /teams/{gc_uuid}/schedule` — returning
its upcoming games (opponent text + `opponent_id` + game date + the raw
UTC datetime/timezone needed for local-date derivation), canceled games filtered
— AND (2) its opponents registry via authenticated `GET /teams/{gc_uuid}/opponents`
(paginated), returning per-opponent records keyed by `root_team_id` and carrying
`progenitor_team_id` when present. Both are genuinely new code: no authenticated
schedule crawler survived the E-239 removal (only public, free-text-name readers
remain), and the opponent-discovery machinery (`opponent_resolver.py`,
`opponent_seeder.py`) was DELETED in E-239. The 2026-06-17 probe findings are
pinned as regression tests so both contracts are guarded.

## Context
The morning-run feature (E-240-07) reads each team's schedule to discover
upcoming opponents, and the resolution ladder (E-240-04) consumes BOTH the
per-upcoming-game record (`opponent_id` + `opponent_name`) from the schedule
crawler AND the opponents-registry records (to read `progenitor_team_id` for
rung (a) — the registry is the ONLY live source of `progenitor_team_id`;
`pregame_data` lacks it and `opponent_links` has no column for it). The live
schedule probe (api-scout, 2026-06-17, against MBA Top Dogg Gold 14U
`public_id=dD9PtF0YbKad`, followed-not-managed) confirmed: **200 at fan/follower
level**; future-dated games carrying `pregame_data` with non-null `opponent_id` +
`opponent_name`; canceled games present and MUST be filtered; `home_away` can be
null. The F4 registry probe (2026-06-17) confirmed the opponents endpoint returns
upcoming opponents (6/6 present, 3/6 with `progenitor_team_id`). See Technical
Notes TN-4 (version pins + 403 disambiguation), TN-2 (sequential, no concurrency),
and the epic Background.

## Acceptance Criteria
- [ ] **AC-1**: A new authenticated schedule crawler fetches
  `GET /teams/{gc_uuid}/schedule` with the correct version pin per Technical
  Notes TN-4 and returns the team's games as structured records each carrying at
  least `opponent_id`, `opponent_name`, the game date, and the raw UTC
  `start.datetime` + timezone fields (so E-240-07 can derive the LOCAL date).
- [ ] **AC-2**: The schedule crawler's date boundary is INCLUSIVE of the run/target
  date — it returns games on AND after the run date (or all non-canceled games),
  never pre-filtering to strictly future dates; the exact same-day filter is
  E-240-07's job. (Per Technical Notes TN-9 / B2: a strict `> today` pre-filter
  would drop the very games the morning run targets.)
- [ ] **AC-3**: Games with a canceled status are filtered out of the returned
  set; non-canceled games (including same-day) are retained. The crawler does not
  depend on `home_away` (a null `home_away` is acceptable, not an error).
- [ ] **AC-4**: A new authenticated opponents-registry crawler fetches
  `GET /teams/{gc_uuid}/opponents` with the correct version pin per Technical
  Notes TN-4 and returns per-opponent records keyed by `root_team_id`, exposing
  `progenitor_team_id` when the key is present (and distinguishing key-absent).
- [ ] **AC-5**: The opponents-registry crawler PAGINATES — it follows the
  `start_at` cursor from the `x-next-page` response header until exhausted, so a
  multi-season team whose registry exceeds the ~50-record page size returns ALL
  records. (Per Technical Notes TN-4: pagination is load-bearing, not optional.)
- [ ] **AC-6**: A 403 from either endpoint is surfaced so the caller can
  distinguish auth-expiry from a version-pin / legitimate-denial case per
  Technical Notes TN-4 — it is NOT collapsed into a single "auth expired" meaning.
- [ ] **AC-7**: Regression tests (mocked/fixtured, never real HTTP per
  `.claude/rules/testing.md`) pin the probe assertions for BOTH crawlers: schedule
  200 fan-level shape parses, future + same-day games returned with `opponent_id`
  + `opponent_name`, canceled filtered, null `home_away` tolerated; opponents 200
  shape parses with `root_team_id` + present/absent `progenitor_team_id`, and a
  multi-page fixture proves pagination across the page boundary. Fixtures mirror
  the authoritative endpoint shapes per Test-Validates-Spec.
- [ ] **AC-8**: This story owns the own-team `public_id → gc_uuid` resolver (the
  prerequisite to calling both endpoints), built as: `resolve_team(public_id)`
  (`src/gamechanger/team_resolver.py`, which calls `GET /public/teams/{public_id}`)
  to obtain the real `name` → `search_teams_by_name(client, name)`
  (`src/gamechanger/search.py`) → filter hits by `public_id` → that hit's `.id` is
  the `gc_uuid`. The resolver MUST pass a real `name` to search, NEVER a URL slug
  (slug → 0 hits, per `.claude/rules/gc-uuid-bridge.md`). It does NOT extract or
  modify the generator's `_fetch_public_team_info` (protected core, per TN-1; C3).
- [ ] **AC-9**: No change to `generate_report()` or any generator stage; Epic A
  golden stat tables and `bb report verify-aggregates` parity are unchanged (this
  story adds crawlers + a resolver + tests only). Per Technical Notes TN-1.

## Technical Approach
Build the two authenticated list-crawlers under `src/gamechanger/crawlers/` (the
surviving authenticated crawlers in that package are the pattern reference for the
client + version-pin + pagination mechanics). Use the project `GameChangerClient`
and its existing auth/version-pin/pagination support. This story also owns the
own-team `public_id → gc_uuid` resolver (AC-8): compose the EXISTING
`resolve_team(public_id)` (`src/gamechanger/team_resolver.py`) and
`search_teams_by_name()` (`src/gamechanger/search.py`) — name both explicitly so
the implementer does not reinvent the public-profile fetch or pass a slug to
search. Do NOT extract `_fetch_public_team_info` from `generator.py` (it is a
protected-core stage method, instance-coupled — reuse would trip TN-1 for zero
gain). The crawlers take a `gc_uuid` (or `TeamRef`) and return their records; keep
each crawler a thin fetch+parse+paginate seam — outcome classification, the
registry join, and orchestration live in E-240-04 / E-240-07. Reference the
endpoint contracts in `docs/api/endpoints/get-teams-team_id-schedule.md` and
`docs/api/endpoints/get-teams-team_id-opponents.md` (the latter already documents
the `0.0.0` pin and pagination), the flow `docs/api/flows/opponent-resolution.md`
(Pass 1), and the probe evidence in the epic Background.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-240-04 (resolution ladder consumes both the upcoming-games shape
  and the opponents-registry records), E-240-07 (orchestration calls the crawlers)

## Files to Create or Modify
- `src/gamechanger/crawlers/schedule.py` — new authenticated schedule crawler
  (suggested path; SE may name it, but name a specific module)
- `src/gamechanger/crawlers/opponents.py` — new authenticated opponents-registry
  crawler (suggested path) + the own-team `public_id → gc_uuid` resolver (AC-8),
  or a small adjacent module the SE names — not a bare `src/`
- `tests/test_schedule_crawler.py`, `tests/test_opponents_crawler.py` — new test
  files for the crawlers + resolver (probe-confirmation + pagination regression
  tests)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-240-04**: (1) the per-upcoming-game record shape and (2) the
  opponents-registry record shape. PIN the per-game record's field names and
  container type so 04/07 do not drift (per B11): at minimum `opponent_id`
  (root_team_id namespace), `opponent_name`, the game date, and the raw UTC
  `start.datetime` + timezone for local-date derivation — declared as a named
  dataclass/TypedDict (SE chooses the container type but MUST declare it here).
- **Produces for E-240-07**: the schedule-fetch and opponents-fetch entry points,
  AND the own-team `public_id → gc_uuid` resolver (AC-8) the orchestration loop
  calls per team (E-240-07 AC-2 references it).

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
The 1-team probe samples are strong enough to commit the design; this story's own
crawler runs against real response shapes are the second confirmation. Never feed
`opponent_id` to `GET /teams/{id}` — it is the `root_team_id` namespace (the
registry→progenitor join is E-240-04's job; do not introduce the misuse here).
