# Undocumented unauthenticated `/public/organizations/` surface

**Date:** 2026-08-04 · **Status:** PARKED — audit-5 ruling 2026-08-16: rides the API-doc
corrections chunk (README NEXT); no standalone chunk.
**Source:** live probes 2026-08-04, verified on a **no-auth** session (no `gc-token`, no
`gc-device-id`). Evidence: `.claude/agent-memory/api-scout/organization-scope.md`.

## What exists

`GET /public/organizations/{org_public_id}` — six live sub-resources, none documented:
`(bare)`, `/teams`, `/standings`, `/team-records`, `/events`, `/scoped-features`.
404: `/games`, `/schedule`, `/opponents`, `/players`, `/avatar-image`, `/game-summaries`,
`/users`, `/pitch-count-report`, `/opponent-players`, `/divisions`.

- **Strictly the `public_id` namespace.** The bare `id` is a slug; `/teams` rows carry `id` =
  the team's `public_id` (**10/10** resolve on `/public/teams/{id}`; fake → 404). The same
  org's **UUID** on this path 404s (n=1 org, 3 calls).
- **Two-sided entity-class control:** a TEAM `public_id` on `/public/organizations/` 404s while
  the same id 200s on `/public/teams/`.
- Public rows carry a `record` string (e.g. `"0-0"`) the authenticated org `/teams` does not.
- The public list is a **strict subset**: 26 public rows vs 28 authenticated; the 2 missing are
  the `status: "org_invite"` teams.

## Why it might matter

It is an **unauthenticated** path to org membership. Every other discovery route we have needs
a live session. Whether that is useful depends entirely on the product call in
`.project/specs/2026-08-04-org-team-discovery-and-roster-ingest.md` — if bulk org discovery is
not wanted, this is documentation for its own sake, which is still worth having but is not
urgent.

## Work

Six endpoint files per `.claude/rules/api-docs.md` naming and frontmatter conventions, plus
`docs/api/README.md` index rows. PII-safe placeholders only — and note the standing corpus
issue in `.project/specs/2026-08-04-docs-api-redacted-prefix-corpus.md`: **do not seed new
files with real UUID prefixes inside `-REDACTED` placeholders.**

## Progress log

- **2026-08-04** — Stubbed. Surface measured, not documented. No code implicated.
