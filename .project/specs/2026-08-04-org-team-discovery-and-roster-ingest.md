# Organizations as a team-discovery and roster source

**Date:** 2026-08-04 · **Status:** PARKED — ruled by the operator 2026-08-08: bulk org discovery DECLINED (vision non-goal); the narrow opponent roster-recovery framing is funded as a MEASUREMENT-ONLY chunk, queued in README NEXT, not started. Design nothing unless the reach number is material
**Source:** live probes 2026-08-04 (~450 calls, read-only, web profile). Evidence:
`.claude/agent-memory/api-scout/organization-scope.md`.

## What was found

Two org endpoints work on organizations this account has **no relationship with**, and
together they reach teams the current pipeline cannot.

- **`GET /organizations/{id}/teams`** — populated on **27/27** stranger orgs. Every row carries
  `root_team_id` (a canonical `gc_uuid`) **and** `team_public_id`, 100% populated. Verified:
  `GET /teams/{root_team_id}` 200 on **24/24**, returned `public_id` == the row's
  `team_public_id` **24/24**; controls (random UUID, an org id, a fake public_id) all 404.
  **N teams pre-resolved in both namespaces from one call — no name, no search index, no
  association.**
- **`GET /organizations/{id}/opponent-players`** — **460 players across 16 of 18 member teams
  in 2 calls** on a stranger org, per-team count matching
  `GET /teams/public/{public_id}/players` exactly (27 == 27), **while
  `GET /teams/{gc_uuid}/players` 403s for that same team.** It routes around the roster
  association gate.

**The refusal control that makes those 200s mean something:**
`/organizations/{id}/pitch-count-report` — 200 on 4/4 related orgs, **403 on 28/28 strangers**.
Two-sided, same principal and session. The org surface does have a real permission gate; these
grants are genuine, not an instrument that cannot say no.

## The decision owed first — do NOT skip to design

**Does this serve reports-first?** The product is *"generate a one-off scouting report for a
GameChanger `public_id` and share the link."* A bulk discovery-and-ingest path is a different
shape of thing, and `docs/VISION.md` bars the machinery E-239 deleted.

The trap to name explicitly: **multi-program breadth is not license to rebuild multi-season
depth.** Serving any team means the tool works for any team's *current* season, one report at
a time. "We can now enumerate thousands of teams" is not by itself a reason to.

A narrower framing that probably *does* serve reports-first, and should be evaluated on its
own: **roster recovery for an opponent we already care about.** `41.3%` of opponent records
carry no `progenitor_team_id` (62.6% truncation-corrected) and are currently written off. If
such an opponent belongs to a discoverable org, `/opponent-players` may reach its roster
where the per-team endpoint 403s. That is scouting data for a specific upcoming opponent —
not a crawl of the world.

## Open questions

- What fraction of *our actual opponents* are reachable this way? Unmeasured. The bulk numbers
  above say the mechanism works, not that it helps us.
- How do you get from an opponent to its org? Nothing establishes a reverse team → org lookup.
- `/opponent-players`' `team_id` is the member's `proxy_team_id`, **not** its `gc_uuid` — join
  through `/organizations/{id}/teams`.
- Rate/volume posture: bulk enumeration is a different traffic shape from one report at a
  time. `.claude/rules/http-discipline.md` binds either way.

## Out of scope until the decision lands

No schema, no loader, no CLI. **Do not re-probe the mechanism** — it is measured above.

## Progress log

- **2026-08-04** — Stubbed from the org probe. No code, no design. Needs a product call on
  whether bulk org discovery serves reports-first, and a measurement of opponent reachability
  before the narrower roster-recovery framing is worth designing.
