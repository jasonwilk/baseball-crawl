---
name: public-team-profile-season-shape
description: LIVE-CONFIRMED (2026-07-07) — GET /public/teams/{public_id} returns team_season.season as a bare string and year FLAT at team_season.year, contradicting the doc's team_season.season.year nesting
metadata:
  type: reference
---

# public-team-profile `team_season` shape discrepancy (LIVE-CONFIRMED 2026-07-07)

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

**RE-CONFIRMED AT SCALE 2026-07-25 (E-272 probe).** An 18-team live sweep found
`team_season.season` populated as a bare string on **all 18** (`"summer"` ×17, `"spring"` ×1)
with `team_season.year` a flat int alongside it. So the shape is settled beyond the original
n=1 sample, and `season` is a **discriminating** signal, not a constant. Two adjacent facts
from that sweep: the shape is **identical with and without** the vendor `Accept`
(see [[public-team-accept-header-inert]]), and `POST /search` uses a **different, nested**
season shape (`result.season.{name,year}`) — do not conflate the two
(see [[search-endpoint-notes]]).

**Status: LIVE-CONFIRMED 2026-07-07 (E-255-R-01).** A plain public curl (`GET /public/teams/{public_id}`, 200 OK, no creds) returned `team_season.season` as the bare string `"summer"`, `team_season.year` as the flat int `2025`, and `team_season.record` with singular keys `{win, loss, tie}` — matching the cached sample exactly. The doc's `team_season.season.year` nesting and testing.md's worked example are BOTH wrong; the real path is `team_season.year` (flat) with `team_season.season` a season-name string. Verified fact recorded in `.project/research/E-255-verified-facts.md` (AC-2/G). Feeds E-255-01/02/04's corrections.
