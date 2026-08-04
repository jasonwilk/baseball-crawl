---
name: organization-scope
description: What is org-scoped in the GC API, that orgs DO enumerate member teams (a discovery path to strangers, ids are canonical gc_uuid + public_id), that the org "opponents" registry is the MEMBERSHIP roster not opponents-faced, and an undocumented unauthenticated /public/organizations surface.
metadata:
  type: reference
---

# Organizations: scope, member enumeration, and the public org surface

Measured live 2026-08-04, web profile, read-only, ~450 calls, 0 fetch errors.
Population: 4 orgs the account is *related to* (`/me/related-organizations`) and
~300 stranger orgs harvested from `POST /search`. `/me/organizations` returns
**0** -- the account is a direct member of no organization, so "related" is the
strongest association available and everything else is a stranger.

## The refusal control (what makes every 200 below mean something)

**`GET /organizations/{id}/pitch-count-report` is the discriminator: 200 on 4/4
related orgs, 403 on 28/28 strangers.** Two-sided, same principal, same session,
same path family. So the org surface DOES have a real permission gate -- the
other endpoints' 200s on strangers are a genuine grant, not an instrument that
cannot say no. Pair any new org access claim with this control.

## ESTABLISHED

- **12 live org sub-resources; 22 probed team-surface analogs 404** (counts corrected
  2026-08-04 by review: the originals read "13" and "25" and were not producible from the
  lists below -- re-derive from the enumeration, never restate the headline). Live:
  `(bare)`, `/avatar-image`, `/events`, `/game-summaries`, `/opponents`,
  `/opponent-players`, `/pitch-count-report`, `/scoped-features`, `/standings`,
  `/team-records`, `/teams`, `/users`. Absent (404): `/players`, `/schedule`,
  `/season-stats`, `/associations`, `/external-associations`, `/relationships`,
  `/public-url`, `/public-team-profile-id`, `/import-summary`,
  `/lineup-recommendation`, `/video-stream-*`, `/web-widgets`, `/users-count`,
  `/share-with-opponent/opt-outs`, `/team-notification-setting`, `/members`,
  `/rosters`, `/divisions`, `/seasons`, `/tournaments`, `/brackets`, `/leagues`.
  The 404 is unambiguous ROUTE-not-found here because bare `/organizations/{id}`
  200s for the same id in the same sweep.

- **YES, an organization enumerates its member teams, for STRANGERS.**
  `GET /organizations/{id}/teams` returned a populated list on **27/27** stranger
  orgs across all three subtypes. Every row carries **`root_team_id` AND
  `team_public_id`, 100% populated** (18/18, 28/28, 50/50, 7/7).
  - WARNING **Despite the field NAME, this `root_team_id` is a canonical `gc_uuid`,
    not a local registry key.** `GET /teams/{root_team_id}` -> **200 on 24/24**, and
    the returned `public_id` equalled the row's `team_public_id` **24/24**.
    `GET /public/teams/{team_public_id}` -> **200 on 24/24**. Controls: random
    UUID 404, org id 404, fake public_id 404. **This is the opposite of the
    opponents-registry `root_team_id`**, which is a local key that 404s on
    `GET /teams/{id}` -- same field name, two namespaces, one endpoint apart.
  - **This is a genuine DISCOVERY PATH**: no name needed, no search index, no
    association. One call yields N teams already resolved in BOTH namespaces.

- **The org "opponents" registry is the org's MEMBERSHIP ROSTER, not opponents
  faced.** Measured on 3 orgs: registry `root_team_id` == member team's
  `proxy_team_id` (18/18, 26/27, 7/7); registry `progenitor_team_id` == member
  team's `root_team_id`/`gc_uuid` (same ratios); names match. Intersection with
  the UNION of member teams' own `/teams/{id}/opponents` registries is **ZERO**
  in all three orgs (org 18 vs union 520; 27 vs 841; 7 vs 381).
  - **This EXPLAINS the previously-unattributed "orgs are 100% linked (131/131)"
    contamination artifact** in [[opponent-registry-access]]: every org registry
    row is a member team auto-linked at org join, so a progenitor is always
    present by construction. Mechanism now known, not just observed.
  - Consequence: **org registries are NOT a broader bulk opponent source.** The
    per-team registries are strictly where opponents-faced live.

- **The real bulk lever is `/organizations/{id}/opponent-players`, and it works
  on strangers.** Full paging on one stranger org: **460 players across 16 of 18
  member teams in 2 calls.** Per-team count matched
  `GET /teams/public/{public_id}/players` **exactly** (27 == 27) for the team
  checked. Meanwhile `GET /teams/{gc_uuid}/players` returned **403** for that
  same stranger team. **So the org path routes around the association gate on
  team rosters.** Its `team_id` field is the member's `proxy_team_id`
  (8/8, 10/10), NOT the `gc_uuid` -- join through `/organizations/{id}/teams`.

- **UNDOCUMENTED PUBLIC ORG SURFACE: `GET /public/organizations/{org_public_id}`,
  unauthenticated.** Verified with the no-auth session (no `gc-token`,
  no `gc-device-id`). Live: `(bare)`, `/teams`, `/standings`, `/team-records`,
  `/events`, `/scoped-features`. 404: `/games`, `/schedule`, `/opponents`,
  `/players`, `/avatar-image`, `/game-summaries`, `/users`,
  `/pitch-count-report`, `/opponent-players`, `/divisions`.
  - Everything is in the **public_id namespace** -- bare `id` is a slug, and
    `/teams` rows carry `id` = the team's `public_id` (**10/10** resolve on
    `/public/teams/{id}`; fake 404). Public rows also carry a `record` string
    (`"0-0"`) the authenticated org `/teams` does not.
  - The public list is a **subset**: 26 public rows vs 28 authenticated, and the
    26 are a strict subset -- the 2 missing are the `status: "org_invite"` teams.
  - **Entity-class control, two-sided:** a TEAM `public_id` on
    `/public/organizations/` 404s while the SAME id on `/public/teams/` 200s.

## Three failure modes, three status codes -- do not blur them

| Question | Instrument | Behavior |
|---|---|---|
| **resolvable / entity class** | `GET /organizations/{id}` bare | 200 on real orgs (31/31); **404 on 9/9 team ids** and on a random UUID |
| **permitted** | `/organizations/{id}/pitch-count-report` | 200 related 4/4, **403** stranger 28/28 |
| **exists** | *no cheap test* | **BOTH directions are live, so a list result proves nothing either way.** SOME list sub-resources return **`200 []` for a team id (9/9) and for a random UUID** -- so EMPTY is ambiguous. But OTHERS serve the team's OWN data under the org prefix (bullet below: `/organizations/{team_id}/opponents` returned that team's 56-record registry, `/opponent-players` 106 players) -- so POPULATED is ambiguous too, and is the **more dangerous** direction: it attributes a team's records to an organization, the E-211 contamination shape. Never infer entity class from a list sub-resource; use bare `/organizations/{id}`. |

- **The non-validating prefix runs BOTH directions.** [[opponent-registry-access]]
  recorded `/teams/{org_id}/...` serving org ids. The mirror is also true:
  `GET /organizations/{team_id}/opponents` returned that TEAM's own 56-record
  registry, and `/organizations/{team_id}/opponent-players` returned 106 players.
  Only `(bare)` and `/avatar-image` validate entity class.
- **A malformed (non-UUID) org segment returns HTTP 500**, not 403/404 -- e.g.
  `/organizations/not-a-uuid`. Note this DIFFERS from `/teams/{non-uuid}/opponents`,
  which returns 403. Do not generalize the 403 across prefixes.

## Gotchas that will cost a call

- **`/organizations/{id}/teams` needs the `x-pagination: true` HEADER, and the
  query params are OPTIONAL.** Measured: header alone -> 200; `page_starts_at` +
  `page_size` WITHOUT the header -> **500** (`Cannot read properties of undefined
  (reading 'page_size')`). The doc's "requires the params AND the header" gets
  the causation backwards. `page_size` is server-capped at **50** regardless of
  what you ask for; follow `x-next-page`.
- Same for `/organizations/{id}/opponent-players`: **bare call 500s today, 2/2.**
  The doc's 2026-03-11 "the 500 bug appears resolved server-side" does not hold.
  Send `x-pagination: true`.
- **`x-next-page` OVER-REPORTS.** The last populated page still carried the
  header; the following call returned `200 []`. **Terminate on an empty body OR
  on the header's absence -- whichever comes first; check both.** (Corrected
  2026-08-04: this read "never on the header's absence", which is unimplementable
  -- with no header there is no cursor to follow and so no way to continue.)
- Org `ngb` is a JSON-encoded **string** (`"[\"usssa\"]"`), not an array as on
  teams. See [[public-team-age-group-level-field]] for the ngb enum caveats.
- `/organizations/{id}/standings` and `/team-records` returned identical data on
  every org tested -- the March "may be semantic" note still stands unresolved.

See [[opponent-registry-access]] for the team-side registry facts this extends,
and [[measurement-discipline]] for why the pitch-count-report control is the
load-bearing part of all of the above.
