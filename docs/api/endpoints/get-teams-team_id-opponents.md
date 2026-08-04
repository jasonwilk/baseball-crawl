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
last_confirmed: "2026-08-04"
tags: [team, opponent]
caveats:
  - >
    NO ASSOCIATION REQUIRED (confirmed 2026-08-03, independently re-verified on a
    disjoint sample 2026-08-04): a valid gc-token is the ONLY gate for THIS
    endpoint. 200 OK with the full field set for teams the account neither manages,
    nor is family on, nor follows -- 21/21 scouted teams, 6/6 teams a further hop
    out, and 24/24 stranger teams on the replication. The earlier "likely 403
    (untested)" row is RETIRED. Control: in the same session, against the same team
    UUID, GET /teams/{id}/public-team-profile-id returned 403 (reproduced 10/10) --
    a refusal IS producible, so these 200s are real access. NOTE: this "token is
    the only gate" finding is scoped to /opponents; it does NOT generalize to
    GET /teams/{id}, which 404s on ~33% of search-sourced ids (see the bridge
    subsection).
  - >
    A WELL-FORMED UNKNOWN team_id RETURNS 200 WITH AN EMPTY ARRAY, NOT 404. An
    empty response is AMBIGUOUS -- "team has no opponents" and "team does not
    exist" are indistinguishable. A NON-UUID path segment returns 403 instead
    (2026-08-04). Do NOT use this endpoint as a team-UUID validity test.
  - >
    CRITICAL -- THE BARE CALL IS SILENTLY TRUNCATED AT 100 RECORDS (2026-08-04).
    Omitting the x-pagination: true request header caps the response at 100
    records WITH NO x-next-page HEADER AND NO OTHER TRUNCATION SIGNAL. One team
    returned exactly 100 bare (reproduced 3x) but 517 records over 11 pages with
    the header. SEND x-pagination: true FOR ANY REGISTRY THAT MIGHT EXCEED 100 --
    a consumer following the bare call drops records with no error. Bare equals
    the full registry only BELOW the cap (69/69, 64/64, 63/63 verified). Registries
    over 100 are rare (1 of 31 teams observed), which is exactly why the cap is
    easy to miss.
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

**Status:** CONFIRMED LIVE -- 200 OK. Last verified: 2026-08-03 (21 teams with no user association, 874 records; previously 49 records 2026-06-12, and 70 records across 2 pages 2026-03-04).

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

## Authentication / Access Level (verified 2026-08-03)

This endpoint requires `gc-token` + `gc-device-id`. **A valid token is the ONLY gate** -- the authenticated user needs no relationship of any kind to the team.

| User role on team (`user_team_associations` from `GET /me/teams?include=user_team_associations`) | `GET /teams/{team_id}/opponents` | Response shape |
|------------------------------------------------------------------------------------------------|----------------------------------|----------------|
| `manager` (+ `family`) | 200 OK | Full -- all fields incl. `progenitor_team_id` |
| `fan` (follower) | 200 OK | Full -- identical shape, incl. `progenitor_team_id` |
| `family` | not isolated in this probe (co-occurred with manager) | assumed full |
| **No association at all** | **200 OK** (2026-08-03: 21/21; independently replicated 2026-08-04: 24/24) | Full -- identical shape, incl. `progenitor_team_id` |

⚰ **RETIRED 2026-08-03** -- this table previously read `No association at all: not tested -- likely 403 (untested)`. That guess was **wrong**. Measured live against 21 scouted teams the authenticated account neither manages, is `family` on, nor follows: **21/21 returned 200** with the full field set. Extended a further hop out to 6 teams that are merely *opponents of* those scouted teams -- teams two removes from the account -- **6/6 also returned 200**.

**Control (why these 200s are access and not a permissive instrument):** in the same session, against the same team UUID, `GET /teams/{team_id}/public-team-profile-id` returned **403** — reproduced **10/10** on the replication sample. A refusal IS producible on this account against these teams, so the 200s here are a real grant rather than an instrument that cannot say no.

**Scope this finding to THIS endpoint.** "A valid token is the only gate" holds for `/opponents`; it does **not** generalize across the API. `GET /teams/{id}` — the very next hop in the resolution chain — **404s on ~33% of search-sourced team ids** because its gate is *resolvability*, not association. See the bridge subsection.

**Implication for opponent scouting / scheduler design:** auto-resolution via `progenitor_team_id` works for **any team whose `gc_uuid` you can name**, not merely teams the operator manages or follows. Registry resolution is therefore a **BULK** operation -- one **paginated** fetch per team of interest (send `x-pagination: true`; see the truncation warning below) -- rather than a per-game lookup driven by individual `root_team_id`s. (Contrast: the `progenitor_team_id` → public_id bridge's `public-team-profile-id` variant IS association-gated and 403s -- but the alternative `GET /teams/{progenitor_team_id}` bridge path works regardless; see the bridge subsection.)

### A well-formed unknown `team_id` returns `200 []`; a non-UUID returns 403

| Path segment | Response |
|--------------|----------|
| Well-formed UUID, no such team | **200 with an empty array** (2/2, 2026-08-03) |
| Not a UUID at all | **403** (2026-08-04) |

An empty response is therefore **ambiguous**: "this team has no opponent records" and "this team does not exist" are indistinguishable from the response alone. **Do NOT use this endpoint as a team-UUID validity test.**

⚰ **CORRECTED 2026-08-04** — this section previously said the fallback instrument, `GET /teams/{team_id}`, *"404s on an unknown UUID and is the right instrument for that question."* It is not. That endpoint **404s on known-but-unresolvable teams as well as on unknown ones**, so it tests **resolvable**, not **exists** — see the bridge subsection below. There is no cheap instrument here that answers "does this team exist".

This also bounds the access finding above: a 200 on its own does not prove the path team exists, so the 21/21 result rests on the responses being **non-empty and well-formed** (22-69 records each), not on the status code alone.

The role itself is read from `GET /me/teams?include=user_team_associations` (`user_team_associations` array: `"manager"`, `"player"`, `"family"`, `"fan"`). The bare `GET /me/teams` requires `Accept: application/vnd.gc.com.team:list+json; version=0.10.0` (an older version string returns 403, easily mistaken for a permission error).

## Pagination Response Header

```
x-next-page: https://api.team-manager.gc.com/teams/{team_id}/opponents?start_at={cursor}
```

When `x-next-page` is absent, you are on the last page — **but only when the request sent `x-pagination: true`.** On a bare call the header is always absent, including on a response truncated at 100 records. See the truncation warning immediately below.

### ⚠ The bare call is SILENTLY TRUNCATED at 100 records (corrected 2026-08-04)

**Send `x-pagination: true` for any registry that might exceed 100 records.** Without it the response is capped at 100 with **no `x-next-page` header and no other truncation signal** — a consumer following the bare call **drops records silently, with no error to catch**.

| Call | Result |
|------|--------|
| Bare (no `x-pagination`), registry ≤ 100 | Full registry in one response, no `x-next-page`. Verified exact: 69/69, 64/64, 63/63. |
| Bare, registry > 100 | **Exactly 100 records, no `x-next-page`.** One team returned 100 bare (reproduced 3×) against **517 records over 11 pages** with the header. |
| `x-pagination: true` | Correct, complete, 50-record pages via `x-next-page`. |

⚰ **RETIRED 2026-08-04** — this section previously read *"Omit the header and the entire registry comes back in a single response"*, citing single responses of 72, 69 and 68 records. Those three observations were real but **all sat below the 100 cap**, and the conclusion generalized from them was wrong. Registries above 100 are **rare (1 of 31 teams observed)**, which is precisely why the cap survives casual sampling: you can measure this endpoint repeatedly and never see it.

**This was a documentation defect only.** The project client's `get_paginated()` sends `x-pagination: true` on every request, so the crawler was never affected.

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

**Observed linked-vs-manual ratio varies widely by team and coach habit -- there is no single "typical" ratio.**

### Sizing the fallback path — use the per-team distribution, not the aggregate

**Size against the per-team range and median.** Two independent samples agree closely on the record-weighted aggregate and **disagree on the distribution**, and the distribution is what a scheduler actually experiences.

| Sample (both 2026-08) | Teams | Records | Record-weighted missing | Per-team missing: median (range) |
|---|---|---|---|---|
| A (scouted teams, from our DB) | 21 | 852 visible / 874 raw | **33.6%** | **30.0%** (0–58.7%) |
| B (disjoint, from search, **teams only**) | 16 | — | **41.3%** bare · 62.6% truncation-corrected · 31.4% outlier-dropped | **38.3%** (0–100%) |

**The two samples AGREE once entity class is controlled for.** Per-team median missing is **30.0%** (A) against **38.3%** (B) — broadly consistent.

⚰ **WITHDRAWN 2026-08-04** — an earlier revision of this section claimed *"aggregate agreement did not mean the distributions agree,"* citing medians of 30.0% vs 7.4%. **That contrast was an artifact.** Sample B as first reported included **8 organizations among its 24 ids**, and organizations are **100% linked** (131/131 records carry `progenitor_team_id`), which dragged its median toward zero — 8 of the 10 "teams at 0% missing" were organizations. Cleaned of orgs, the disagreement disappears. Do not reintroduce the distribution-disagreement framing.

**The real lesson is one layer down: a heterogeneous result set silently contaminated a distribution.** `POST /search` mixes teams and organizations (see the entity-class warning in the bridge subsection), and because organizations are uniformly linked they bias any linked-share statistic computed over unfiltered search output. **Filter on the envelope `type` before computing anything about teams.**

**Sample A is NOT org-diluted — do not "correct" it.** Its 21 teams came from our own database, and **all 28 stored `gc_uuid`s return 200 on `GET /teams/{id}` (28/28 checked)**, so every one is a real team. Its 33.6% stands as measured.

**The aggregate is still leverage-dominated, so prefer the per-team median.** One team supplies **508 of 694** missing records when fully paged; dropping it moves sample B's rate to 31.4%, and truncation-correcting it moves the same sample to 62.6%. A number that swings 31.4% → 41.3% → 62.6% on one team's handling is not a stable planning criterion.

**Denominator matters — state which one you mean.** Sample A's 33.6% is over **visible** records (22 of 874 were `is_hidden` and excluded). `src/gamechanger/crawlers/opponents.py` returns hidden records **unfiltered**, so a crawler author's working denominator is the **raw** count, not the visible one.

**Cap exposure:** sample A's largest raw registry was 69 records, entirely below the 100-record bare-call cap — so its figures are not truncation-affected, though that is also precisely why the cap went unnoticed there.

Both supersede the `~14% missing` figure that [opponent-resolution.md](../flows/opponent-resolution.md) carried, which was a single-team baseline.

The earlier 5-team measurement is preserved below as the 2026-06-12 observation it was. Across those 5 teams the search-linked share ranged from **27% to 100%**:

| Team (role) | Total visible | Linked (`progenitor`) | Manual | % linked |
|-------------|---------------|------------------------|--------|----------|
| Non-LSB Example Team (n/a) | 49 | 13 | 36 | 27% |
| LSB Example Team A (fan) | 32 | 16 | 16 | 50% |
| LSB Example Team B (fan) | 54 | 27 | 27 | 50% |
| LSB Example Team C 18U (fan) | 33 | 25 | 8 | 76% |
| LSB Example Team D (manager+family) | 23 | 23 | 0 | 100% |
| **Aggregate (4 LSB teams)** | **142** | **91** | **51** | **64%** |

A scheduler that relies on `progenitor_team_id` for auto-resolution must therefore plan for a name-search + operator-input fallback path as a first-class case, not an exception -- some teams are fully linked, others are majority-manual. The manual share correlates with how many opponents are **not in GC's searchable team index at all** (e.g., HS varsity programs): these cannot be search-linked by any coach, so they are manual everywhere and unresolvable to a `public_id`.

Ground-truth case: game `b5c0e6c2-REDACTED`'s opponent "Anytown" (root_team_id `a8ab985f-REDACTED`) carries NO `progenitor_team_id` -- confirmed manual entry. (That team also had a separate "Anytown East" entry, also manual -- distinct `root_team_id`.)

**Cross-team sibling recovery does NOT help (verified 2026-06-12).** Across the 4 LSB teams, 15 opponent names were shared by 2+ teams, but **0** were manual on one team yet linked on a sibling -- shared names were uniformly linked-everywhere (findable club teams) or manual-everywhere (unindexed HS programs). So a scheduler cannot borrow a sibling team's `progenitor_team_id` to resolve another team's manual entry; the manual entries are unindexed, not merely un-linked-by-this-coach.

**Few manual entries are TBD/bracket placeholders (verified 2026-06-12).** Of the 51 manual LSB entries, only ~3 were placeholder-style (tournament/event labels: "Papio Tournament" x2, "Tri-Cities Tournament"); ~46 were real (unindexed) team names and ~2 ambiguous/truncated ("East", "Carpet"). **Zero** classic `TBD`/`TBA`/`Winner Game N`/seed/bracket entries were present in these registries. Excluding placeholders barely moves the auto-resolution ratio (64% → 65% linked). A scheduler can detect placeholders by name heuristic (`TBD|TBA|Winner|Loser|Seed|Game \d|Pool|Bracket|Tournament|Invitational|Classic|Showcase`) and **defer + re-poll near game time** rather than queue for operator input -- but expect this to cover only a small slice; the dominant cost is unindexed real teams.

**There is NO structural placeholder flag.** Manual records carry only `{root_team_id, owning_team_id, name, is_hidden}` -- the *sole* structural difference from a linked record is the absence of `progenitor_team_id`. No `event_type`, no `is_tbd`, no game-link field exists. Placeholder vs. real-team classification is name-heuristic only.

**The opponent registry is cumulative/historical, NOT schedule-synced.** Most registry-manual names map to no current schedule game (e.g., Example Team A: 13/16 manual registry names appear on no scheduled game), and a scheduled game's `pregame_data.opponent_name` often differs from the registry `name` (game: "Anytown Post 216 Reserve" vs registry: "Anytown"). **Resolve opponents from the schedule/game record** (`pregame_data.opponent_name` + `opponent_id` → join to `root_team_id` here → read `progenitor_team_id`), not by iterating the whole registry. The registry is a join target, not the scheduler's work queue.

### progenitor_team_id → public_id bridge (for `bb report generate`)

To turn a search-linked opponent's `progenitor_team_id` into a `public_id` you can feed to public endpoints / `bb report generate`:

- **WORKS FROM A `progenitor_team_id`:** `GET /teams/{progenitor_team_id}` (team metadata; `Accept: application/vnd.gc.com.team:read+json; version=0.0.0`) returns `public_id` directly, even though the opponent is NOT operator-managed. Verified 2026-06-12, and re-verified 2026-08-03/04 at **18/18** and **20/20** on two independent samples. A `progenitor_team_id` taken from an opponents registry is reliably resolvable.

> ⚠ **`GET /teams/{id}` is NOT universally 200 — because `POST /search` returns ORGANIZATIONS as well as teams (measured 2026-08-04).** On 24 ids drawn from `POST /search`, **16 returned 200 and 8 (33%) returned 404**. **All 8 were organizations; all 16 were teams.** An organization id is not a team id. Not an `Accept` artifact — reproduced with no `Accept`, with `version=0.0.0`, and with `application/json`.
>
> **Filter on the ENVELOPE `type`** (`"team"` | `"organization"`). Do **not** test `result.type` — it is present only on organizations and absent on teams, so the check inverts. Coextensive symptoms usable as a cross-check: `number_of_players` null 93/93 on orgs vs non-null 506/506 on teams; `staff` null on orgs, present on teams (n=599 hits).
>
> **`public_id` does NOT discriminate** — organizations carry one (93/93), as do `season`, `avatar_url` and `location`. **A consumer filtering search hits by `public_id` alone can select an organization**, and an org `public_id` fed to the public pipeline 404s (3/3).
>
> **Not dead, not transient** (both refuted): org ids return populated `/opponents` registries with identical counts ~5h apart, `GET /organizations/{id}` returns 200 on 8/8 (vs 404 on 3/3 real teams), and `GET /teams/{org_id}/opponents` serves a **byte-identical** registry to the `/organizations/` form (2/2) — **the `/teams/` prefix serves org ids without validating entity class**, which is why they look alive until team fields are needed.
>
> **Predictive power:** 58/58 orgs 404, 86/86 teams 200 on a stratified set (PPV/NPV 1.00). Honest bound: no counterexample **yet** is not proof — rule of three gives a ~5.2% / ~3.5% 95% ceiling on the error rate.
>
> **Consumer hazard:** `src/gamechanger/search.py::resolve_gc_uuid_by_public_id` yields `POST /search` `result.id` *as* a `gc_uuid`, so **a stored `gc_uuid` can be an organization id** — the wrong entity class, not a corrupt or dead id, and detectable at resolution time at zero extra cost.

- **DOES NOT WORK for opponents:** `GET /teams/{progenitor_team_id}/public-team-profile-id` returns **403 Forbidden** for non-managed teams. Use it only for teams the authenticated user manages. (Confirmed 403 on the same opponent progenitor as the bullet above, 2026-06-12.)

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

**Discovered:** 2026-03-04. **Schema confirmed:** 2026-03-04. **Entry-mode signal + bridge path verified:** 2026-06-12. **Access level (no association required), unknown-id behavior, opt-in pagination, and the n=852 linked/manual population rate verified:** 2026-08-03.
