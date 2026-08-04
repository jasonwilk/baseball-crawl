# Which identifier is valid on which path — the Tier 2 audit

**Date:** 2026-08-04 · **Status:** PARKED — funded by the operator, not started
**Sibling:** `.project/specs/2026-08-04-search-entity-class-filter.md` (the code fix)

## Why this exists

`docs/api` has ~124 files; **29 assert something about how identifiers relate**
(`root_team_id` / `progenitor_team_id` / `gc_uuid` / `public_id` / `event_id` /
`game_stream_id`). They were ranked by blast radius — how much damage a wrong line does.
**Tier 2 is the funded slice.** This file exists so that ranking survives a session
boundary; it was previously only in a conversation.

## The tiers

- **Tier 1 — recipes.** Tell someone how to resolve an ID; a wrong line writes bad data.
  `flows/opponent-resolution.md`, `endpoints/get-teams-team_id-opponents.md`,
  `flows/opponent-scouting.md`, `README.md`. *(First three corrected 2026-08-03/04.)*
- **Tier 2 — access claims. ← FUNDED, this file.** Assert `root_team_id` works somewhere
  but never state the required access level. Six files, below.
- **Tier 3 — storage instructions.** Tell you to save one id into another's field; this
  is the class that caused the E-211 `gc_uuid` contamination.
  `get-public-teams-public_id-games.md`, `get-teams-team_id-game-summaries.md`,
  `get-events-event_id.md`, `get-teams-team_id-schedule.md`,
  `flows/spray-chart-rendering.md`,
  `get-teams-team_id-schedule-events-event_id-player-stats.md`.
- **Tier 4 — schema dumps.** ~13 files describing response fields. Low risk.

## The six Tier 2 files

1. `get-teams-team_id-public-team-profile-id.md` — 403 is confirmed; verify the stated
   REASON is association rather than management.
2. `get-teams-team_id-players.md`
3. `get-teams-team_id-avatar-image.md`
4. `get-teams-team_id-opponents-players.md`
5. `get-teams-team_id-associations.md`
6. `get-public-teams-public_id.md`

Files 2–4 assert `root_team_id` works; none states an access level. **They also
contradict each other**: `opponents-players.md` says `root_team_id` is the local registry
key and *"Do not use for other endpoints"*, while `players.md` and `avatar-image.md` both
say they use it and get 200. All three "confirmed" dates are March 2026.

## Why this tier, and what it is really asking

An untested access claim is a **silent capability loss**: if a doc wrongly says an
endpoint needs management, we never attempt the call, never learn it works, and nothing
ever fails to tell us. That is not hypothetical — `GET /teams/{id}/opponents` carried
*"No association at all: not tested — likely 403"* for months and turned out to be
completely ungated (21/21, then 24/24 on a disjoint sample, with a producible 403 control).

**Reframe the brief from "verify access levels" to: map which identifier is valid on
which path, and report what that unlocks.** That is the question that finally pins down
the identifier namespaces, and it is the same question the entity-class finding answered
in one instance.

**The payoff case:** teams-only, **41.3% of opponent records carry no
`progenitor_team_id`** (62.6% truncation-corrected; per-team median 38.3%, range 0–100%,
n=16). Those opponents have no canonical identity and we currently write them off. But
they DO have a `root_team_id`. If it is valid on sub-resource paths, we can still fetch
roster and avatar for them — real scouting data for teams we presently treat as
unreachable.

## Evidence already in hand (do not re-probe)

- `GET /teams/{id}` — the TEAM RESOURCE — **404s on a `root_team_id`** (16/16), and also
  404s on an organization id. It tests **resolvable**, not **exists**.
- `/teams/{id}/avatar-image` — **404 on 8/8 orgs, 200 on 3/3 teams**; tracks the team
  resource.
- `/teams/{id}/players` — **403 on BOTH orgs and teams** (3/3 controls). Association-gated;
  does not discriminate entity class. ⚠ **The March-2026 claim that
  `GET /teams/{root_team_id}/players` returns 200 for opponent ids DID NOT REPRODUCE on
  non-associated ids.** Flagged as needing re-verification, not asserted wrong — the
  original may have been measured from an associated account.
- `GET /organizations/{id}/opponents` returns a byte-identical registry to the `/teams/`
  path — the `/teams/` prefix serves org ids **without validating entity class**.

## Design requirement — non-negotiable

Every path tested needs a **producible refusal control** in the same session: show that
the endpoint CAN 403/404 for this account, or a 200 proves nothing about access. This is
what made the registry finding credible and what its predecessor lacked.

Also: distinguish **resolvable** from **exists** from **permitted**. Three different
failure modes, three different status codes, and the docs currently blur them.

## Constraints

Read-only. No `bb report generate` / `purge-scouting` / `db reset` / `report cleanup`.
Web profile. Placeholders only in `docs/api` per the team-name posture in memory.
Run `scripts/check_doc_pii.sh docs/api` and `.project` from the repo root before reporting.

## Progress log

- **2026-08-04** — Parked. Funded by the operator during the entity-class investigation,
  deferred until after that work committed (`4c93754`, `9ac686d`). Written down because
  the ranking existed only in a conversation and would not have survived `/clear`.
