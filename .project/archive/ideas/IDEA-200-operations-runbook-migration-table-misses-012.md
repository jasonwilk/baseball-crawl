# IDEA-200: Operations runbook's migration table stops at 011

## Status
`CANDIDATE`

## Summary
`docs/admin/operations.md` ("Schema Migrations") states "The current set is `001`-`011`" and its per-migration table ends at 010/011. `migrations/012_teams_innings_per_game.sql` exists, so both the count and the table are one behind.

## Why It Matters
Small, but it is the operator-facing runbook, and the section it sits in tells the operator how to inspect applied migrations against the live database. A count that disagrees with `ls migrations/*.sql` invites exactly the wrong conclusion during an incident — that a migration failed to apply, or that the database is ahead of the code — at the moment the operator is least able to afford a false lead.

The failure is self-repeating rather than one-off: the section carries a hand-maintained count AND a hand-maintained row per migration, so every future migration must update two places in this file plus the file itself. It fell behind once and will again.

## Rough Timing
Fold into the next docs-writer pass that touches `docs/admin/operations.md`. Does not earn a dispatch of its own.

## Dependencies & Blockers
- [ ] None.

## Open Questions
- Is the hardcoded range worth keeping at all? `.claude/rules/migrations.md` already tells readers to `ls migrations/*.sql` rather than trust a written number, on the explicit grounds that such lists rot — and this is that rot. Dropping the range and keeping the table would remove one of the two things needing maintenance; dropping both in favour of pointing at the directory would remove the drift surface entirely, at the cost of the at-a-glance summary the table provides.

## Notes
Surfaced by data-engineer as a drive-by during E-277 discovery (2026-07-26) and independently verified by PM: `migrations/` contains twelve files (`001`-`012`), and the runbook's own table has no `012` row. Out of E-277's scope — that epic touches no documentation.

Owner when promoted: `docs-writer`.

---
Created: 2026-07-26
Last reviewed: 2026-07-26
Review by: 2026-10-24
