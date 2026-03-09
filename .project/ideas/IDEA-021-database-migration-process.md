# IDEA-021: Database Migration Process Definition

## Status
`CANDIDATE`

## Priority
HIGH -- the opponent data model epic (E-088) will be the first real migration, and we need a solid process before executing it.

## Summary
Define and document a clear, repeatable database migration process for this project. The current `migrations/` directory exists with `apply_migrations.py` but the process for creating new migrations, testing them, rolling back, and handling production data has not been exercised end-to-end with a real schema change.

## Why It Matters
The opponent data model epic will add the first new table (`opponent_links`) since the initial schema. If the migration process is shaky, we risk data loss or downtime. Better to nail the process on this first migration than discover gaps under pressure.

## Rough Timing
Now -- before or as part of E-088. This should be addressed in E-088's technical approach or as a prerequisite story.

## Dependencies & Blockers
- [ ] None -- the `migrations/` infrastructure already exists
- [ ] E-088 is the forcing function

## Open Questions
- What's the rollback strategy? SQLite doesn't support `ALTER TABLE DROP COLUMN` cleanly.
- Should migrations be numbered sequentially or timestamped?
- How do we test migrations against production data (backup + migrate + verify)?
- Should `bb db reset` be aware of migration history?
- Docker image rebuild required after migration changes?

## Notes
- `migrations/` is a Python package (has `__init__.py`, included in pyproject.toml)
- `apply_migrations.py` exists and is callable via `python migrations/apply_migrations.py`
- `bb db reset` and `bb db backup` exist for dev database management
- SQLite WAL mode is in use -- migrations must be WAL-compatible
- The Dockerfile copies migrations/ into the image -- production migrations happen on container restart

---
Created: 2026-03-09
Last reviewed: 2026-03-09
Review by: 2026-06-07
