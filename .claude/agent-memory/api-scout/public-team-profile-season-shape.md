---
name: public-team-profile-season-shape
description: SETTLED — GET /public/teams/{public_id} returns team_season.season as a bare string with year FLAT at team_season.year; the team_season.season.year nesting is a fabrication. Docs and testing.md are now corrected; no open action.
metadata:
  type: reference
---

# public-team-profile `team_season` shape — SETTLED

`GET /public/teams/{public_id}` returns:

```json
"team_season": {
  "season": "spring",              // bare STRING, not an object
  "year": 2026,                    // FLAT sibling of season
  "record": {"win": 12, "loss": 8, "tie": 0}   // SINGULAR keys
}
```

**The path `team_season.season.year` does not exist on any endpoint.** It was a fabrication that
had propagated into both the endpoint doc and a worked example. Do not reintroduce it.

## Evidence trail (n is now large; stop re-probing)

| date | evidence |
|---|---|
| 2026-07-07 | n=1 live public curl (E-255-R-01) + cached sample agree: bare string + flat year |
| 2026-07-25 | 18-team live sweep — bare string on **all 18** (`summer` ×17, `spring` ×1), flat year alongside |
| 2026-07-25 | 7 **opponent** teams (E-274 probe) — all `{"season": "spring", "year": 2026, "record": {win,loss,tie}}` |

Treat the vocabulary as **OPEN** (`spring`/`summer` observed, `fall` documented on the
authenticated endpoints).

**`season` and `age_group` are INDEPENDENT AXES — season says WHEN a team plays, `age_group`
says its LEVEL. Never infer one from the other.** Two measurements pin this down: all 73
opponents on a spring school schedule returned `"spring"`, which tempts the reading that
season tracks the family — but a summer-schedule population of 134 contained **13
school-family teams carrying `"summer"`** and **4 non-school teams carrying `"spring"`.**
So a school team can be a summer team, and season is NOT a family signal
(see [[public-team-age-group-level-field]]).

**Presence is reliable:** across those 73, `team_season` was present and non-null and both its
`season` and `year` keys were present on **73/73** — zero absent, null, or empty-string. A
"season-absent" branch is not a live case for this family.

## Both downstream corrections have LANDED — this memory has no open action

- `docs/api/endpoints/get-public-teams-public_id.md` — corrected; documents the flat shape and
  explicitly warns off the nesting.
- `.claude/rules/testing.md` — corrected; its worked example now states that **neither** endpoint
  nests the year and names the path a fabrication.

Earlier versions of this memory said these two files CONTRADICTED the observation. That is
**no longer true** and was itself stale by 2026-07-25. If you find yourself about to "fix" either
file for this, re-read it first.

## Adjacent facts, so you do not re-derive them

- The shape is **identical with and without** the vendor `Accept` — that header is inert on this
  endpoint (see [[public-team-accept-header-inert]]).
- `POST /search` uses a **different, NESTED** season shape (`result.season.{name, year}`). Do not
  carry a parser between the two endpoints (see [[search-endpoint-notes]]).
- The public profile's `record` uses **singular** keys (`win`/`loss`/`tie`); the authenticated
  `GET /teams/{team_id}` uses **plural** (`wins`/`losses`/`ties`) in a top-level `record`.
- Full stable key set of the public profile: `age_group, avatar_url, id, location, name, ngb,
  player_count, sport, staff, team_season` — identical across all 7 teams sampled 2026-07-25.
  `ngb` has two empty forms, one of which (`""`) is **not valid JSON**
  (see [[public-team-age-group-level-field]]).
