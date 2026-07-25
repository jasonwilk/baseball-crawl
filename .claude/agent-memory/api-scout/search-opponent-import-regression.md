---
name: search-opponent-import-regression
description: GET /search/opponent-import returned HTTP 400 on 2026-07-25 for four param variants including the doc's own documented example, while its endpoint doc still reads CONFIRMED LIVE 2026-03-09 — needs re-verification
metadata:
  type: reference
---

# `GET /search/opponent-import` now 400s (observed 2026-07-25)

`docs/api/endpoints/get-search-opponent-import.md` reads **CONFIRMED LIVE — 200 OK, last
verified 2026-03-09**, with the response body never captured. On **2026-07-25** it returned
**HTTP 400** for every variant tried, with valid credentials (`GET /me/user` 200 OK in the
same session, refresh token ~13 days remaining):

| variant | result |
|---|---|
| the doc's own example — `name` + `sport` + `age_group` + `include_avatar` | **400** |
| `name` + `sport` | **400** |
| `name` alone | **400** |
| `name` + `sport` + a guessed vendor `Accept` (`...search_opponent_import+json; version=0.0.0`) | **415** |

The **415** on the guessed `Accept` is informative: the endpoint *does* react to content
negotiation, so the 400 is plausibly a missing/changed required `Accept` version rather than
a bad query string. Note `GameChangerClient.get` also sets a `Content-Type` on GETs, which
could itself provoke the 415.

**Status: NOT confirmed broken — confirmed NOT-200 under four guesses.** Per the
never-update-on-a-single-anomaly rule this is a flag, not a spec rewrite. The correct next
step is a **captured browser curl** of the real GC "add opponent" import flow to recover the
exact `Accept` version and param set, then re-test. Do not mark the endpoint dead on this
evidence.

**Low urgency:** E-168 already moved both the admin resolve workflow and the automated
opponent resolver off this endpoint onto [[search-endpoint-notes]] (`POST /search`), so
nothing in the pipeline depends on it.

## Spec now RECONCILED (2026-07-25) — the doc no longer overstates it

The endpoint doc and the `docs/api/README.md` index row were corrected the same day:
`status: CONFIRMED` → **`OBSERVED`** (profile `confirmed` → `observed`), a Regression section
carrying the four-variant table, and a caveat. The downgrade is the factually right one
independent of the 400: the original 200s were **proxy observations of the GC UI**, never a
direct call by us, and the response body was never captured — which is exactly the definition
of `OBSERVED`. Only the open action remains: capture a browser curl of the real "add opponent"
flow.

Also unresolved and worth pairing with any re-probe: the doc's **inferred** response schema
claims hits carry `age_group` and `competition_level`. That schema was never verified — both
rows were inferred purely from the existence of same-named **query parameters**, which is not
evidence of a response field.

**There is now counter-evidence, and it is recorded in the doc.** `POST /search` definitively
does not carry either key (59 hits / 6 queries, 2026-07-25, zero occurrences), and its
`result` key set — `avatar_url, id, location, name, number_of_players, public_id, season,
sport, staff` — matches every *other* row of this endpoint's inferred table while omitting
exactly these two. Most likely reading: the inference is simply wrong. **Do not plan a level
source around it** ([[public-team-age-group-level-field]] is the confirmed one).
