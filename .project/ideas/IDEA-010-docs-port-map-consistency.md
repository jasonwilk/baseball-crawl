# IDEA-010: Docs Port Map Consistency for Devcontainer + Compose

## Status
`CANDIDATE`

## Summary
Create a focused docs cleanup pass to align all local URL/port references with the current devcontainer + Docker Compose networking model, especially Traefik dashboard on `8180` and mitmproxy/mitmweb on `8080/8081`.

## Why It Matters
Outdated port references cause false troubleshooting paths and wasted time. This directly impacts onboarding, local debugging, and proxy setup reliability.

## Rough Timing
Near-term. Promote when networking/mitmproxy docs are touched again or when the next devcontainer/compose port change lands.

## Dependencies & Blockers
- [ ] Confirm canonical local port map remains: app direct `8001`, app via Traefik `8000`, Traefik dashboard `8180`, mitmproxy `8080`, mitmweb `8081`
- [ ] Confirm docs scope for this pass (at minimum `docs/admin/getting-started.md` and `docs/agent-browsability-workflow.md`)

## Open Questions
- Should this be a one-time patch or a repeatable "docs port audit" checklist in docs standards?
- Should URLs in docs prefer "host LAN IP" wording for phone/proxy flows to avoid container-IP confusion?

## Notes
Context from mitmproxy troubleshooting identified stale references showing Traefik dashboard at `http://localhost:8080` in:
- `docs/admin/getting-started.md`
- `docs/agent-browsability-workflow.md`

Related artifact:
- `MITM-TROUBLESHOOTING.md`

---
Created: 2026-03-05
Last reviewed: 2026-03-05
Review by: 2026-06-03
