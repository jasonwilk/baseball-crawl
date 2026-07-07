---
name: public-team-profile-season-shape
description: Cached public-team-profile sample contradicts documented team_season.season.year nesting — season is a bare string, year is flat at team_season.year (UNVERIFIED, single sample)
metadata:
  type: reference
---

# public-team-profile `team_season` shape discrepancy (flag, not yet confirmed)

`GET /public/teams/{public_id}` — the cached sample `data/raw/public-team-profile-sample.json` shows:

```json
"team_season": {
  "record": {"win": 61, "loss": 29, "tie": 2},
  "season": "summer",   // bare STRING, not an object
  "year": 2025          // year is a SIBLING of season → team_season.year (FLAT)
}
```

This CONTRADICTS:
- `docs/api/endpoints/get-public-teams-public_id.md`, which documents `team_season.season` as an object `{"year": 2024, "name": "summer"}` (i.e. year at `team_season.season.year`).
- `.claude/rules/testing.md` worked example, which asserts the public endpoint nests year at `team_season.season.year`.

If the cached sample is current, the real path is `team_season.year` (flat) and `team_season.season` is a season-name string — so both the endpoint doc example and testing.md's example are wrong.

**Status: UNVERIFIED — single cached sample, possibly a stale API version.** Per the never-update-spec-on-single-observation rule, do NOT rewrite the docs until confirmed across ≥3 live calls. This endpoint is PUBLIC (no auth, no gc-signature), so it is cheaply live-verifiable with any valid `public_id`. Surfaced 2026-07-07 during E-255 (CE-5) planning. Feeds claude-architect's testing.md correction — CA must not fix testing.md until this shape is confirmed live.
