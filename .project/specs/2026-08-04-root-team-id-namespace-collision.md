# `root_team_id` means two different things — the rule reads as universal and is not

**Date:** 2026-08-04 · **Status:** STUB — context-layer correction, not code
**Source:** live probes 2026-08-04. Evidence:
`.claude/agent-memory/api-scout/organization-scope.md`.

## The collision

The field name `root_team_id` carries **two different namespaces** one endpoint apart:

| Endpoint | What `root_team_id` is | `GET /teams/{that_id}` |
|---|---|---|
| `/teams/{team_id}/opponents` | a **local registry key** | **404** |
| `/organizations/{org_id}/teams` | a canonical **`gc_uuid`** | **200** (24/24, `public_id` round-trips 24/24) |

Controls on the org side: random UUID 404, an organization id 404, a fake `public_id` 404.

## Why this needs a rule-layer edit rather than just a doc edit

CLAUDE.md states:

> **Gotcha — `root_team_id` is a different namespace from `gc_uuid`.** NEVER store one in the
> other's column.

That is **correct about the opponents registry** — and it is the shape that caused the E-211
`gc_uuid` contamination, so it must not be weakened. But it **reads as universal**, and a
reader who applies it to `/organizations/{id}/teams` will discard a perfectly good `gc_uuid`,
or fail to recognize one they are already holding. Same failure class, opposite direction.

`.claude/rules/gc-uuid-bridge.md` carries the same universal-sounding phrasing in its
BANNED-PATH section.

## What to change

State the rule as **endpoint-scoped, both halves together** — the registry key is not a
`gc_uuid` *and* the org-teams field is one. Neither half is safe alone: the first without the
second strands a usable identifier; the second without the first re-opens E-211.

Files: `CLAUDE.md` (GameChanger API gotchas), `.claude/rules/gc-uuid-bridge.md`. The endpoint
docs were corrected in the same pass that produced this stub.

## ⚠ Not a new discovery — do not write it up as one

`docs/api/endpoints/get-organizations-org_id-teams.md` has carried the caveat
*"root_team_id IS THE TEAM UUID"* since **2026-03-07**. What is new is (a) that it holds for
**stranger** orgs, not just related ones, and (b) the framing as a *collision* with the
identically-named registry field. The doc was right and the rule layer never absorbed it —
which is the actual defect here, and the reason a doc-only fix would not have closed it.

## Progress log

- **2026-08-04** — Stubbed. Endpoint docs corrected; rule layer NOT touched (owned by
  claude-architect). No code implicated: no current code path reads
  `/organizations/{id}/teams`.
