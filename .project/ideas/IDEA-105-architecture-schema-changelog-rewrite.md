# IDEA-105: Full Rewrite of `architecture.md` "Schema Changes" Historical Changelog

## Status
`CANDIDATE`

## Summary
`docs/admin/architecture.md` carries a "Schema Changes" changelog section that still cites pre-E-220 migration numbers which no longer map to real `migrations/*.sql` files (the E-220 rewrite squashed all prior migrations into `001_initial_schema.sql` and later real migrations 002–010 reused some numbers). E-255-05 added a clarifying note atop the section and fixed the one false "plays removed" claim in it, but did NOT rewrite the full historical changelog.

## Why It Matters
A historical changelog that cites migration numbers no reader can resolve to a file is confusing, though lower-severity than a phantom migration presented as CURRENT/operational (E-255-05 AC-1 fixed those in the operations.md live migration table). This is polish on reference material, not an executable-runbook defect — which is why E-255-05 scoped it to a clarifying note (TN-2: keep history as history; correct the load-bearing accuracy).

## Rough Timing
Promote when docs/admin is next touched for a larger pass, or bundle with any future migration-numbering documentation cleanup. Low priority.

## Dependencies & Blockers
- [ ] Decide the target: rewrite each historical entry to reference the consolidated `001_initial_schema.sql` (with a "pre-E-220 numbering" note), or collapse the pre-E-220 entries into a single "squashed at E-220" line and keep only the real 002–010 entries as discrete rows.

## Notes
- Surfaced by docs-writer during E-255-05 (item 1); PM ruled the clarifying-note approach sufficient for E-255-05 and captured this for a follow-up.
- Related: the operations.md live "Schema Migrations" table (real 001–010) landed in E-255-05 AC-1 and is the canonical current-state reference; this idea is only about the architecture.md HISTORICAL changelog.

---
Created: 2026-07-08
Last reviewed: 2026-07-08
Review by: 2026-10-06
