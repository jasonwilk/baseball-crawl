# Search returns two entity classes — filter for teams

**Date:** 2026-08-04 · **Status:** STUB — needs planning before execution
**Source:** live probes 2026-08-03/04 (~630 calls, read-only, web profile)

## Goal

`POST /search` returns a **heterogeneous** result set. Each hit's **envelope** carries
`type` ∈ `{"team", "organization"}`. Two call sites consume search hits and filter only
on `public_id`, so an **organization** can be selected where a team is required.

Add an entity-class check at both. This is the first behavioral change to come out of
the boxscore/registry investigation; everything before it was documentation.

## The finding (measured, do not re-derive)

- Envelope `type` separates the classes perfectly at **n=599 hits** (506 team / 93 org).
- **`GET /teams/{org_id}` → 404.** An organization id is not a team id. Controls both
  ways: `GET /organizations/{id}` → **200 on 8/8** orgs and **404 on 3/3** teams.
- Predictive power at scale: **58/58 orgs → 404, 86/86 teams → 200.** PPV/NPV 1.00.
  **Honest bound:** rule of three gives a ~5.2% / ~3.5% 95% ceiling on the error rate —
  *no counterexample yet*, not proven.
- **Base rate is not marginal: 15.5% of search hits are organizations (19.5% among
  baseball hits).**
- **Organizations carry a `public_id`** (93/93), so a `public_id`-only filter cannot
  exclude them. An org `public_id` fed to the public pipeline 404s (3/3).
- Key sets are **disjoint and OMITTED, not null** — teams always carry
  `number_of_players` + `staff` and never `type`/`tournament_dates`; orgs are the
  inverse. Same key-omission convention as `progenitor_team_id`; `is None` is the wrong
  test.

## Files

- `src/gamechanger/search.py` — `resolve_gc_uuid_by_public_id` filters on
  `result.get("public_id") != public_id` with no type check, then yields `result.id`
  **as the `gc_uuid`**.
- `src/gamechanger/opponent_ladder.py` — rung (c) `resolve_public_id_by_search` gates on
  `len(hits) != 1` then takes `hits[0]`. ⚠ **The uniqueness guard gives NO protection
  here** — it fires exactly when a name matches one thing, which is when an org name
  matches uniquely. Measured: 2 of 15 org names returned a single hit; both were the org.
- `tests/` — new cases (see Verification).

## Design

Require the **envelope's** `type == "team"`.

⚠ **Check the envelope, NOT `result.type`.** `result.type` is the ORG SUBTYPE
(`travel` / `tournament` / `league`) and is **absent on teams** — testing it inverts the
check and rejects every real team.

Prefer an explicit shared predicate over two inline checks; both sites want the same
rule and this repo's recurring defect is a second copy that drifts.

Open design question for planning: **skip** a non-team hit and keep paging, or **refuse**
the resolution outright? Skip-and-continue is probably right for
`resolve_gc_uuid_by_public_id` (an org sharing a `public_id` with the sought team is not
a reason to abandon the search), but rung (c)'s uniqueness contract may want refusal.
Decide deliberately.

## Out of scope

- The mechanism is settled — do NOT re-probe it.
- No change to `is_gc_uuid`.
- No historical repair: **28/28 stored `gc_uuid`s are teams today**, so there is no
  live contamination to clean. Verify that still holds before assuming it.
- The wider organization exploration (below) — separate work.

## Verification

- A search-hit fixture containing an org and a team with the SAME `public_id` → only the
  team is yielded.
- Rung (c) with a single org hit → does not return the org's `public_id`.
- **A test that fails if someone "fixes" the check to `result.type`** — that inversion is
  the likeliest wrong edit, and it must not pass.
- Fixtures must mirror the real shape: **keys OMITTED, not null** (teams have no `type`
  key at all).
- `python -m pytest tests/ > /tmp/out.txt 2>&1; echo "RC=$?" >> /tmp/out.txt`, then read
  the file. **Never pipe pytest.** Full suite green before commit.

## Follow-on — organizations are barely documented

The operator wants to probe this properly and view real examples in the UI. Known so far:

- `GET /organizations/{id}` → 200, carries `type` (`travel`/`tournament`/`league`).
- `GET /organizations/{id}/opponents` → **byte-identical** registry to the `/teams/`
  path (2/2). The `/teams/` prefix serves org ids **without validating entity class** —
  which is why these ids looked alive.
- `GET /organizations/{id}/avatar-image` → 200/404 tracking avatar presence (2/2).
- `tournament_dates` (start/end pair) on 45/93 orgs, 0/506 teams.
- Existing docs: `get-organizations-org_id-opponents.md`,
  `get-organizations-org_id-opponent-players.md`.

Open: what else is org-scoped, whether org membership enumerates teams (a possible
discovery path), and whether org registries are a better bulk source than per-team ones.

## Also flagged, feeds the Tier 2 audit

`/teams/{id}/players` returned **403 on both** orgs and teams (3/3 controls) — it is
association-gated and does not discriminate entity class. **Our March-2026 doc claim
that `GET /teams/{root_team_id}/players` returns 200 for opponent ids did NOT reproduce
on non-associated ids.** Flagged as needing re-verification, not asserted wrong.

## Progress log

- **2026-08-04** — Stub written from the probe evidence. Both defects confirmed by
  direct read of the two call sites. No code written. Needs planning: the skip-vs-refuse
  decision, and whether the shared predicate lives in `search.py` or alongside
  `is_gc_uuid`.
