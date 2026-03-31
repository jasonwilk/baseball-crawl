# Docs Writer -- Agent Memory

## Documentation Structure
- `docs/admin/` -- Admin/developer documentation (audience: Jason)
- `docs/coaching/` -- End-user documentation (audience: coaching staff)
- `docs/api/` -- API spec directory (owned by api-scout, read-only for docs-writer). Index at `docs/api/README.md`, per-endpoint files in `docs/api/endpoints/`.

## Admin Docs -- File Map
- `docs/admin/README.md` -- Index of all admin docs
- `docs/admin/architecture.md` -- System overview, components, data flow, directory structure, schema changes
- `docs/admin/operations.md` -- Deployment, CLI pipeline reference, admin UI reference, credential rotation, backup/restore, troubleshooting
- `docs/admin/getting-started.md` -- Dev environment setup, credentials, running tests
- `docs/admin/agent-guide.md` -- Agent ecosystem overview and workflow guide

## Coaching Docs -- File Map
- `docs/coaching/README.md` -- Entry point for coaching staff (dashboard is live; includes auto-sync and game coverage intro as of E-181)
- `docs/coaching/scouting-reports.md` -- Dashboard layout, schedule/scouting views, game coverage indicator, empty states, spray charts, printing, reading rate stats
- `docs/coaching/standalone-reports.md` -- Shareable scouting snapshots: when to use, how to use, 14-day expiry, comparison table vs. dashboard
- `docs/coaching/understanding-stats.md` -- Plain-language stats glossary (OBP, SLG, K%, BB%, BABIP, K/9, BB/9, K/BB, FIP) with sample size guidance

## Conventions
- **Last updated line format**: `*Last updated: YYYY-MM-DD | Source: E-NNN (description), E-NNN-SS (description)*`
- Pipeline commands documented in operations.md under the Admin Team Management section (CLI subsections follow the UI section)
- Schema changes go in architecture.md under `## Schema Changes`, newest first
- Coaching explanations should not mention technical details (routes, SQL, Python modules)
- Coaching docs use plain prose and "what it means in practice" examples, not formulas
- Audience: coaching docs assume zero technical knowledge; admin docs assume Python/Docker/SQL competence

## Topic File Index
- [Conventions file](conventions.md) -- (this MEMORY.md serves as the index; no separate topic files yet)
