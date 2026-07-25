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
- Report-generation-triggers-destructive-reconcile and `bb db purge-scouting` (the clean-slate command) are documented in operations.md: `### Reconcile-at-Load: Generating a Report Can Now Delete Stale Data` (under Standalone Reports, right after "Generating a Report") and `### Purging Scouting and Report Data (bb db purge-scouting)` (under Database Backup and Restore, right after "Development Database Reset"). Source: E-267; reconciled to the E-270-02 hardened surface (guard->preview->confirm->backup->purge sequence, non-overridable `validate_app_env()` typo guard, `--force`/`--yes` split as a **breaking change** for scripted callers, typed production confirmation, fail-closed pre-purge backup) on 2026-07-25. Section-level `Last updated` line AND the file's bottom-of-file provenance trailer (a running per-epic list every prior epic appends to, near the end of the file) both need updating on a purge-behavior change -- don't just touch the section header line.
- Orphan reference-data reclamation (ambient sweep wired into deletion paths + opportunistic `cleanup_expired_reports`/`bb report cleanup` firing, plus the one-time `scripts/reclaim_orphan_reference_data.py` backlog one-shot and its baseline-resnapshot -> run -> verify operator sequence) is documented in operations.md under `### Reclaiming Orphaned Reference Data` (Standalone Reports section, right after `### Cleaning Up Expired Report Files (bb report cleanup)`, before `### Report Generation Run Records`). Source: E-273 (E-273-05). Deliberately did not cite the epic's specific backlog counts (681 teams / 14,326 players) since [[project_e273_orphan_reclamation]] flags them as already stale relative to the live DB -- the doc frames the sequence as count-agnostic instead.

## Feedback
- [Report AC-vs-code mismatches, don't silently resolve them](feedback_report_dont_silently_resolve_ac_mismatch.md) -- even when your own doc correctly favors the code over a wrong AC, flag the divergence to the spawner so the story file itself gets corrected too. Negative-claim ACs ("NOT X") are the ones most worth double-checking.

## Topic File Index
- [feedback_report_dont_silently_resolve_ac_mismatch.md](feedback_report_dont_silently_resolve_ac_mismatch.md) -- report AC/code mismatches even when self-resolved correctly.
