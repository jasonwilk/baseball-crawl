---
method: GET
path: /teams/{team_id}/opponents
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: 70 records across 2 pages confirmed 2026-03-04.
  mobile:
    status: observed
    notes: >
      2 hits, HTTP 200. Observed 2026-03-09 (session 063531). Called with opponent
      progenitor_team_id (14fd6cb6) -- confirms the endpoint works for opponent teams.
accept: "application/vnd.gc.com.opponent_team:list+json; version=0.0.0"
gc_user_action: "data_loading:opponents"
query_params:
  - name: start_at
    required: false
    description: Pagination cursor. Use the full URL from x-next-page response header.
pagination: true
response_shape: array
response_sample: data/raw/opponents-sample.json
raw_sample_size: "70 records across 2 pages combined, 17 KB"
discovered: "2026-03-04"
last_confirmed: "2026-06-12"
tags: [team, opponent]
caveats:
  - >
    Three UUID fields with DIFFERENT semantics -- CRITICAL: root_team_id is the local
    registry key. owning_team_id always equals the path team_id (informational only).
    progenitor_team_id is the CANONICAL GC team UUID.
  - >
    ID USAGE BY ENDPOINT (confirmed 2026-03-09):
    root_team_id: use with GET /teams/{team_id}/opponent/{id},
    GET /teams/{root_team_id}/players, GET /teams/{root_team_id}/avatar-image.
    progenitor_team_id: use with GET /teams/{progenitor_team_id} (team metadata, public_id, record).
    public_id (from GET /teams/{progenitor_team_id} response): use with all /public/ endpoints.
    The pattern root_team_id for roster/avatar, progenitor_team_id for metadata was
    confirmed by observing GC web app traffic against Nighthawks Navy AAA 14U.
related_schemas: []
see_also:
  - path: /teams/{team_id}/opponent/{opponent_id}
    reason: Single opponent lookup by root_team_id (singular /opponent/ path)
  - path: /teams/{team_id}/opponents/players
    reason: Bulk opponent roster with handedness across all opponents in one call
  - path: /teams/{team_id}
    reason: Team detail using progenitor_team_id as the team_id
  - path: /organizations/{org_id}/opponents
    reason: Org-level opponent list (returns same fields, larger scope)
---

# GET /teams/{team_id}/opponents

**Status:** CONFIRMED LIVE -- 200 OK. Last verified: 2026-06-12 (49 records, team qKrZuhgV6eke; previously 70 records across 2 pages, 2026-03-04).

Returns the complete opponent registry for a team. Each record represents one opponent team that this team has played against. Paginated with page size 50 (same cursor pattern as game-summaries). **The `progenitor_team_id` field is the manual-vs-lookup entry-mode signal** -- see the Entry-Mode Signal section.

**CRITICAL -- Three UUID fields with different semantics (confirmed 2026-03-09):**
- `root_team_id`: Local registry key. Use with: `GET /teams/{team_id}/opponent/{root_team_id}`, `GET /teams/{root_team_id}/players`, `GET /teams/{root_team_id}/avatar-image`.
- `owning_team_id`: Always equals the path `team_id`. Informational only -- never use as a team_id parameter elsewhere.
- `progenitor_team_id`: **Canonical GC team UUID.** Use with: `GET /teams/{progenitor_team_id}` (returns team metadata including `public_id`). The `public_id` from that response is then used for all `/public/teams/{public_id}` endpoints.

```
GET https://api.team-manager.gc.com/teams/{team_id}/opponents
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `team_id` | UUID | Team UUID |

## Headers (Web Profile)

```
gc-token: {GC_TOKEN}
gc-device-id: {GC_DEVICE_ID}
gc-app-name: web
Accept: application/vnd.gc.com.opponent_team:list+json; version=0.0.0
gc-user-action: data_loading:opponents
gc-user-action-id: {UUID}
x-pagination: true
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36
```

## Authentication / Access Level (verified 2026-06-12)

This endpoint requires `gc-token` + `gc-device-id`, but does **NOT** require the authenticated user to be a manager of the team. **Fan/follower-level association is sufficient** to read the full opponents registry, including `progenitor_team_id`.

| User role on team (`user_team_associations` from `GET /me/teams?include=user_team_associations`) | `GET /teams/{team_id}/opponents` | Response shape |
|------------------------------------------------------------------------------------------------|----------------------------------|----------------|
| `manager` (+ `family`) | 200 OK | Full -- all fields incl. `progenitor_team_id` |
| `fan` (follower) | 200 OK | Full -- identical shape, incl. `progenitor_team_id` |
| `family` | not isolated in this probe (co-occurred with manager) | assumed full |
| No association at all | **not tested** -- likely 403 (untested) |

Verified across 4 LSB teams: 1 manager-role team and 3 fan-role teams all returned 200 with the identical full field set (`root_team_id`, `owning_team_id`, `name`, `is_hidden`, `progenitor_team_id`). Fan-level access showed **no degradation** -- the entry-mode signal is available to followers.

**Implication for opponent scouting / scheduler design:** auto-resolution via `progenitor_team_id` works for ANY team the operator follows (fan), not only teams they manage. This widens Epic-E rung-(a) coverage well beyond managed teams -- the operator only needs to *follow* a team to read its opponent registry. (Contrast: the `progenitor_team_id` → public_id bridge's `public-team-profile-id` variant IS manager-gated and 403s for non-managed teams -- but the alternative `GET /teams/{progenitor_team_id}` bridge path works regardless; see the bridge subsection.)

The role itself is read from `GET /me/teams?include=user_team_associations` (`user_team_associations` array: `"manager"`, `"player"`, `"family"`, `"fan"`). The bare `GET /me/teams` requires `Accept: application/vnd.gc.com.team:list+json; version=0.10.0` (an older version string returns 403, easily mistaken for a permission error).

## Pagination Response Header

```
x-next-page: https://api.team-manager.gc.com/teams/{team_id}/opponents?start_at={cursor}
```

When `x-next-page` is absent, you are on the last page.

## Response

Bare JSON array of opponent records. Page size 50. 70 records across 2 pages (50 + 20) observed.

| Field | Type | Notes |
|-------|------|-------|
| `root_team_id` | UUID | Local registry key. Use ONLY as `opponent_id` in `GET /teams/{team_id}/opponent/{opponent_id}`. Do NOT use with other team endpoints. |
| `owning_team_id` | UUID | Always equals the path `team_id`. Informational only. |
| `name` | string | Opponent display name |
| `is_hidden` | boolean | Whether hidden from UI. 57 visible, 13 hidden (dupes/bad entries) in observed data. Filter `is_hidden=true` in ETL. |
| `progenitor_team_id` | UUID or **absent** | **Canonical GC team UUID.** Use THIS with `/teams/{id}`, `/season-stats`, `/players`, etc. **This field is the manual-vs-lookup entry-mode signal** -- see below. When absent, the opponent was typed manually and has no canonical GC UUID. |

**`root_team_id` == `pregame_data.opponent_id`** from schedule (confirmed 2026-03-24, re-confirmed 2026-06-12). The opponent UUID a game record carries is the `root_team_id` (local registry key), NOT `progenitor_team_id`. To get the canonical UUID for a game's opponent, join the game's `pregame_data.opponent_id` to `root_team_id` in this list, then read that record's `progenitor_team_id` (which may be absent).

### Entry-Mode Signal: `progenitor_team_id` present vs. absent (verified 2026-06-12)

GameChanger has two opponent entry modes, and this field is the reliable single-season signal distinguishing them:

| Entry mode | How coach added opponent | `progenitor_team_id` | Auto-resolvable to a public_id? |
|------------|--------------------------|----------------------|---------------------------------|
| **Team lookup** | Searched GC and selected a real team | **present** (UUID) | Yes -- bridge to public_id (see below) |
| **Manual entry** | Typed the opponent name free-text | **absent** (key omitted, not null) | No -- name-only; needs `POST /search` resolution or operator input |

**`progenitor_team_id` is absent (key omitted), not null**, on manual-entry records. Use `o.get("progenitor_team_id")` and treat falsy as "manual."

**Observed linked-vs-manual ratio varies widely by team and coach habit -- there is no single "typical" ratio.** Across 5 teams verified 2026-06-12, the search-linked share ranged from **27% to 100%**:

| Team (role) | Total visible | Linked (`progenitor`) | Manual | % linked |
|-------------|---------------|------------------------|--------|----------|
| Bennington D1 Training Reserves (n/a) | 49 | 13 | 36 | 27% |
| LSB Example Team A (fan) | 32 | 16 | 16 | 50% |
| LSB Example Team B (fan) | 54 | 27 | 27 | 50% |
| LSB Example Team C 18U (fan) | 33 | 25 | 8 | 76% |
| LSB Example Team D (manager+family) | 23 | 23 | 0 | 100% |
| **Aggregate (4 LSB teams)** | **142** | **91** | **51** | **64%** |

A scheduler that relies on `progenitor_team_id` for auto-resolution must therefore plan for a name-search + operator-input fallback path as a first-class case, not an exception -- some teams are fully linked, others are majority-manual. The manual share correlates with how many opponents are **not in GC's searchable team index at all** (e.g., HS varsity programs like "Bellevue West", "Millard West", "Elkhorn South"): these cannot be search-linked by any coach, so they are manual everywhere and unresolvable to a `public_id`.

Ground-truth case: game `b5c0e6c2-REDACTED`'s opponent "Anytown" (root_team_id `a8ab985f-REDACTED`) carries NO `progenitor_team_id` -- confirmed manual entry. (That team also had a separate "Anytown East" entry, also manual -- distinct `root_team_id`.)

**Cross-team sibling recovery does NOT help (verified 2026-06-12).** Across the 4 LSB teams, 15 opponent names were shared by 2+ teams, but **0** were manual on one team yet linked on a sibling -- shared names were uniformly linked-everywhere (findable club teams) or manual-everywhere (unindexed HS programs). So a scheduler cannot borrow a sibling team's `progenitor_team_id` to resolve another team's manual entry; the manual entries are unindexed, not merely un-linked-by-this-coach.

**Few manual entries are TBD/bracket placeholders (verified 2026-06-12).** Of the 51 manual LSB entries, only ~3 were placeholder-style (tournament/event labels: "Papio Tournament" x2, "Tri-Cities Tournament"); ~46 were real (unindexed) team names and ~2 ambiguous/truncated ("East", "Carpet"). **Zero** classic `TBD`/`TBA`/`Winner Game N`/seed/bracket entries were present in these registries. Excluding placeholders barely moves the auto-resolution ratio (64% → 65% linked). A scheduler can detect placeholders by name heuristic (`TBD|TBA|Winner|Loser|Seed|Game \d|Pool|Bracket|Tournament|Invitational|Classic|Showcase`) and **defer + re-poll near game time** rather than queue for operator input -- but expect this to cover only a small slice; the dominant cost is unindexed real teams.

**There is NO structural placeholder flag.** Manual records carry only `{root_team_id, owning_team_id, name, is_hidden}` -- the *sole* structural difference from a linked record is the absence of `progenitor_team_id`. No `event_type`, no `is_tbd`, no game-link field exists. Placeholder vs. real-team classification is name-heuristic only.

**The opponent registry is cumulative/historical, NOT schedule-synced.** Most registry-manual names map to no current schedule game (e.g., Example Team A: 13/16 manual registry names appear on no scheduled game), and a scheduled game's `pregame_data.opponent_name` often differs from the registry `name` (game: "Anytown Post 216 Reserve" vs registry: "Anytown"). **Resolve opponents from the schedule/game record** (`pregame_data.opponent_name` + `opponent_id` → join to `root_team_id` here → read `progenitor_team_id`), not by iterating the whole registry. The registry is a join target, not the scheduler's work queue.

### progenitor_team_id → public_id bridge (for `bb report generate`)

To turn a search-linked opponent's `progenitor_team_id` into a `public_id` you can feed to public endpoints / `bb report generate`:

- **WORKS:** `GET /teams/{progenitor_team_id}` (team metadata; `Accept: application/vnd.gc.com.team:read+json; version=0.0.0`) returns `public_id` directly, even though the opponent is NOT operator-managed. Verified 2026-06-12: progenitor `895fa512-REDACTED` (Berthoud Badgers 15U) → `public_id` `xXxXxXxXxXxX`, which then returns 200 on `GET /public/teams/{public_id}`.
- **DOES NOT WORK for opponents:** `GET /teams/{progenitor_team_id}/public-team-profile-id` returns **403 Forbidden** for non-managed teams. Use it only for teams the authenticated user manages. (Confirmed 403 on the same Berthoud progenitor, 2026-06-12.)

For manual-entry opponents (no `progenitor_team_id`), there is no bridge: resolve by `name` via `POST /search` (the gc-uuid bridge, `.claude/rules/gc-uuid-bridge.md`) -- noting that the canonical indexed name may differ from the web URL slug -- or fall back to operator input.

## Example Response

```json
[
  {
    "root_team_id": "00000000-0000-0000-0000-000000000001",
    "owning_team_id": "72bb77d8-REDACTED",
    "name": "Anytown Eagles 12U",
    "is_hidden": false,
    "progenitor_team_id": "00000000-0000-0000-0000-000000000002"
  },
  {
    "root_team_id": "00000000-0000-0000-0000-000000000003",
    "owning_team_id": "72bb77d8-REDACTED",
    "name": "Example Team 14U",
    "is_hidden": false
  }
]
```

The first record is a **team-lookup** opponent (`progenitor_team_id` present); the second is a **manual-entry** opponent (`progenitor_team_id` key omitted entirely).

## Known Limitations

- `progenitor_team_id` is **absent** (key omitted, not null) on manual-entry opponents -- 10/70 (2026-03-04) and 36/49 (2026-06-12) across observed teams. The manual fraction can be the majority. Manual-entry opponents have no canonical GC UUID and cannot be used for cross-endpoint lookups without a name-based `POST /search` resolution.
- Filter `is_hidden=true` records in ETL. Hidden opponents are duplicates or erroneous entries. (0 hidden observed on team qKrZuhgV6eke; 13 hidden on the 2026-03-04 team.)
- `root_team_id` and `progenitor_team_id` look like UUIDs but have completely different semantics. Confusing the two is a common mistake. A game record's `pregame_data.opponent_id` is in the `root_team_id` namespace, NOT `progenitor_team_id`.
- The `progenitor_team_id` → public_id bridge for non-managed opponents goes through `GET /teams/{progenitor_team_id}` (returns `public_id`), NOT `GET /teams/{id}/public-team-profile-id` (403 for non-managed teams). See the bridge subsection above.

**Discovered:** 2026-03-04. **Schema confirmed:** 2026-03-04. **Entry-mode signal + bridge path verified:** 2026-06-12.
