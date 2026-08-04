---
name: opponent-registry-access
description: GET /teams/{id}/opponents needs NO association (a valid gc-token is the only gate), so registry resolution is BULK not per-game; an unknown team_id returns 200 [] not 404; the progenitor chain buys determinism, NOT search-index reach.
metadata:
  type: reference
---

# Opponent registry access, and what the root_team_id -> public_id chain is actually worth

Measured live 2026-08-03, web profile, read-only, ~160 calls, 0 fetch errors.

## ESTABLISHED

- **`GET /teams/{team_id}/opponents` requires NO association at all.** A valid
  `gc-token` is the only gate. 200 OK with the full field set (`root_team_id`,
  `owning_team_id`, `name`, `is_hidden`, `progenitor_team_id`) for **21/21**
  scouted teams the account neither manages, is `family` on, nor follows, and for
  **6/6** teams a further hop out (opponents OF those teams). The doc's old
  "No association at all -- likely 403 (untested)" row was a **guess**, and wrong.
  **Control:** in the same session, against the same team UUID,
  `GET /teams/{id}/public-team-profile-id` returned **403** -- a refusal IS
  producible, so the 200s are a real grant, not an instrument that cannot say no.
  Consequence: registry resolution is a **BULK** operation (one call per team),
  not a per-game lookup driven by individual `root_team_id`s.
- **A WELL-FORMED unknown `team_id` returns `200 []`, not 404** (2/2); a
  **non-UUID path segment returns 403** instead. Empty is ambiguous -- "no
  opponents" vs "no such team". ⚰ I wrote that `GET /teams/{id}` "404s and is the
  right instrument" for existence -- **wrong**: it 404s on known-but-unresolvable
  teams too, so it tests **resolvable**, not **exists**. There is no cheap
  existence test here. This also **bounds the access finding**: a bare 200 proves
  nothing about the path team, so the 21/21 rests on the bodies being non-empty
  and well-formed, not on the status alone.
- **`POST /search` RETURNS ORGANIZATIONS AS WELL AS TEAMS -- that is the whole
  mechanism.** The hit **envelope** carries `type` in {`team`, `organization`}.
  `GET /teams/{org_id}` 404s because an org id is not a team id: on 24 search ids,
  16/24 200 and **8/24 404, and all 8 were organizations**; on a stratified set,
  **58/58 orgs 404 / 86/86 teams 200**. Controls: `GET /organizations/{id}` 200 on
  8/8 of the failures and 404 on 3/3 real teams. Orgs are **15.5% of hits, 19.5%
  of baseball hits** (n=599: 506 team / 93 org).
  - **Test the ENVELOPE `type`, NOT `result.type`** -- `result.type` exists only
    on orgs, so testing it inverts the check.
  - **`public_id` does NOT discriminate** (orgs carry one, 93/93), nor do `season`,
    `avatar_url`, `location`. Coextensive symptoms only: `number_of_players` and
    `staff` null 93/93 on orgs, populated 506/506 on teams.
  - ⚰ I first documented **`number_of_players: null` as THE predictor**. It is a
    **symptom** ("this object has no team fields"), coextensive but not causal.
    Leading with a symptom hides that the fix is a one-field entity-class filter.
  - **NOT dead ids, NOT transient** (both refuted): org ids return populated
    registries with identical counts ~5h apart, and `GET /teams/{org_id}/opponents`
    is **byte-identical** to `GET /organizations/{org_id}/opponents` (2/2) -- the
    `/teams/` prefix serves org ids **without validating entity class**, which is
    why they look alive.
  - **Consumer hazard: a STORED `gc_uuid` can be an ORGANIZATION id**, because
    `search.py::resolve_gc_uuid_by_public_id` yields `result.id` as the `gc_uuid`.
    Wrong entity class, not a corrupt or dead id -- detectable at resolution time
    from a field already in the response, at zero cost.
  - The narrow claim that DOES hold: a `progenitor_team_id` from an opponents
    registry resolves reliably -- 18/18 (mine) and 20/20 (independent). Registry
    progenitors are teams.
- **THE BARE CALL IS SILENTLY TRUNCATED AT 100 RECORDS.** ⚰ I originally wrote
  "pagination is opt-in, the bare call returns the ENTIRE registry (72/69/68
  observed)". **WRONG, and it would cause silent data loss.** Without
  `x-pagination: true` the response caps at 100 with **no `x-next-page` and no
  other truncation signal**: one team returned exactly 100 bare (reproduced 3x)
  against **517 records over 11 pages** with the header. Bare equals full only
  BELOW the cap (69/69, 64/64, 63/63). **My three samples all sat below it** --
  my whole sample's max raw registry was 69. Registries over 100 are rare (1 of
  31 teams), so the cap survives casual sampling indefinitely. Doc-only defect:
  `client.get_paginated` already sends the header.
- **Linked-vs-manual: prefer the PER-TEAM median to the record-weighted
  aggregate.** Sample A, mine (21 teams, 852 visible / 874 raw): aggregate 33.6%
  missing, **per-team median 30.0%** (0-58.7%). Sample B, independent, **teams
  only** (16 teams): 41.3% bare / 62.6% truncation-corrected / 31.4%
  outlier-dropped, **per-team median 38.3%** (0-100%). **The two AGREE.**
  - ⚰ I recorded "**the aggregates replicated and the distributions did not**"
    (medians 30.0 vs 7.4) as a transferable lesson. **WITHDRAWN** -- an artifact.
    B originally mixed **8 organizations** into 24 ids, and orgs are **100% linked**
    (131/131), so 8 of its 10 "0% missing" entries were not teams. Cleaned, the
    disagreement vanishes. **The real lesson is one layer down: a HETEROGENEOUS
    result set silently contaminated a distribution** -- filter on entity class
    before computing any statistic over search output.
  - **My 33.6% is NOT org-diluted** -- its teams came from our DB and all 28
    stored `gc_uuid`s return 200 on `GET /teams/{id}` (28/28). Do not "correct" it.
  - Leverage still stands: one team supplies **508 of 694** missing when fully paged.
  - **Denominator:** mine excluded `is_hidden`; `crawlers/opponents.py` does NOT
    filter hidden, so a crawler author's denominator is the raw count.
  (The old `~14%` figure this replaced was a single-team baseline, corrected
  across seven sites 2026-08-03.)
- **The chain validates end-to-end.** boxscore UUID-form key -> registry
  `root_team_id` -> `progenitor_team_id` -> `GET /teams/{progenitor}` ->
  `public_id`: **18/18**, **18/18**, **18/18**. Singular
  `/opponent/{root_team_id}` agreed with the bulk registry **6/6**. Slug-form
  boxscore keys matched no registry `root_team_id` (0/5) -- correct, they are
  already `public_id`s in a different namespace.
- **A malformed `opponent_id` yields HTTP 500**, not 400/404 (a stored non-UUID
  sentinel). Bad input surfaces as a server error, so a 500 here means validate
  the identifier, not "GC is down / retry".

## OBSERVED OUTCOME, UNTESTED MECHANISM (downgraded 2026-08-04)

**"A registry entry does not depend on GC's search index, so a team `POST /search`
cannot find may still be resolvable via `progenitor_team_id`."** FALSE.
**16/16** chain-resolved teams were also findable by search on the canonical name,
and **10/10** using the coach's LOCAL registry label -- label was byte-identical
to canonical **10/10**, because GC copies the canonical name in at link time.

⚰ I claimed the populations **"coincide by construction"** and wrote **"do not
re-run this probe"** into the flow doc. **Both overreached.** The OUTCOME
replicated (10/10 independently), but the MECHANISM was never tested: two link
paths that could set `progenitor_team_id` -- `GET /search/opponent-import`, and
league/organization schedule links -- can only be excluded with **write actions
nobody has taken**. And querying a name-indexed search with a team's own exact
canonical name is near-tautological, so the hit rate is weak evidence FOR the
mechanism even while it is solid evidence ABOUT the outcome. The "do not re-run"
instruction is removed; it foreclosed an open question.

**Keep the two failure modes distinct** even though they select the same records
here: *search-index absence* and *hand-typed entry* are different things. A
hand-typed opponent has no `progenitor_team_id` at all, so no registry access
manufactures one -- a hard ceiling on the chain, unrelated to indexing.

## What the chain IS worth (measured -- reach is not it)

1. **Determinism.** Only **7/16** name searches returned exactly one hit; the rest
   2-25, two saturated at 25. Disambiguating needs the `public_id` you are trying
   to resolve. The chain returns one answer 16/16.
2. **No name needed.** It runs from a `root_team_id` -- what a boxscore key or
   `pregame_data.opponent_id` actually gives you. Search cannot start without a name.
3. **It clears rows search left behind.** 2 of 3 `opponent_links` rows with
   `public_id IS NULL` resolved first try; the third had the malformed sentinel root.

## Method notes worth reusing (2 of my 10 claims were REFUTED on re-verification)

**A cap you never hit is invisible, so probe for the BOUNDARY, not the value.**
My three bare-call samples returned 72/69/68 records and I concluded "the bare
call returns everything". All three sat below a 100-record cap I never saw,
because registries over 100 are ~3% of teams. **When a response's size is itself
the observation, find the largest instance you can and test THAT** -- an
unbounded claim needs a case that would break it, not three that agree.

⚰ **"An aggregate replicating is not a distribution replicating" -- WITHDRAWN.**
I promoted it to a reusable lesson off medians of 30.0% vs 7.4%. The gap was
**entity-class contamination**, not a real distributional difference: the other
sample mixed 8 organizations into 24 ids, orgs are 100% linked, and cleaned of
them the medians are 30.0% vs 38.3% -- agreement. **A memorable lesson drawn from
an artifact is worse than no lesson**, because it gets cited later by people who
cannot see the artifact.

**The lesson that IS supported, one layer down: a HETEROGENEOUS result set will
silently contaminate any statistic computed over it.** `POST /search` returns
teams AND organizations; orgs are uniformly linked, so they bias linked-share
downward. **Establish what KIND of thing each row is before aggregating rows.**
The tell was available in the response the whole time -- an envelope `type` field
nobody read.

**Say what N=1-ish leverage can move.** Before quoting an aggregate as a planning
number, ask what dropping the single biggest contributor does to it (one team
holds 508 of 694 missing records here).

## Method note worth reusing

The finding that mattered was a **negative-control design**, not a bigger sample:
21/21 200s prove nothing until you show the same session CAN be refused. Pair any
"access is broader than documented" claim with a refusal produced against the same
principal and the same resource. See [[measurement-discipline]].

See [[boxscore-key-form]] for what a boxscore key IS, and
[[search-endpoint-notes]] for the search quirks that bound path 1 above.
