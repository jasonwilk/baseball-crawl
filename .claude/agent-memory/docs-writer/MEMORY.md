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
- `docs/coaching/README.md` -- Entry point for coaching staff (reports-first; links to standalone-reports.md and understanding-stats.md as of E-239)
- `docs/coaching/standalone-reports.md` -- Shareable scouting snapshots: when to use, how to use, 14-day expiry, no-data guidance (scouting-reports.md removed in E-239)
- `docs/coaching/understanding-stats.md` -- Plain-language stats glossary (OBP, SLG, K%, BB%, BABIP, K/9, BB/9, K/BB, FIP) with sample size guidance

## Conventions
- **Last updated line format**: `*Last updated: YYYY-MM-DD | Source: E-NNN (description), E-NNN-SS (description)*`
- Pipeline commands documented in operations.md under `## Data Maintenance` (Admin Team Management section removed in E-239)
- Schema changes go in architecture.md under `## Schema Changes`, newest first
- Standalone report run-record / trust-flag operator docs live in operations.md under `### Report Generation Run Records` (inside Standalone Reports section, after `bb report cleanup` -- the `verify-aggregates` subsection it used to sit after was removed in E-259, the stored `player_season_*` tables it checked having been dropped)
- Coaching explanations should not mention technical details (routes, SQL, Python modules)
- Coaching docs use plain prose and "what it means in practice" examples, not formulas
- Audience: coaching docs assume zero technical knowledge; admin docs assume Python/Docker/SQL competence
- **N vs M (report coverage)**: N = `completed_games_with_data` (games with stat rows loaded); M = `completed_games` (games with final score). N ≤ M. Always document as "N of M games with data", never conflate with score-only coverage.

## Topic File Index
- No separate topic files yet -- Conventions above (this file) is the sole reference.
