# IDEA-025: Migration-Driven Test Fixtures

## Status
`CANDIDATE`

## Summary
Replace inline `_SCHEMA_SQL` DDL strings in test files with a shared `conftest.py` fixture that applies the real migration SQL via `apply_migrations()`. Tests consume the same schema definition as production -- no duplicate DDL to maintain.

## Why It Matters
Every test file currently embeds its own copy of the schema DDL. When a migration story changes the schema, every test file with inline DDL must be manually updated. This is the same drift pattern that motivated E-100's schema rewrite -- just one layer up. A single `db_conn` fixture built from real migrations eliminates the sync surface entirely.

## Rough Timing
After E-100 completes. E-100 is rewriting the schema and all test files from scratch (fresh start), which is the natural moment to establish the new pattern. If not done during E-100, the first post-E-100 migration story will recreate the drift problem.

## Dependencies & Blockers
- [ ] E-100 (Team Model Overhaul) must be complete -- test files are being rewritten there
- [ ] `apply_migrations.py` must work correctly on in-memory or tmp_path SQLite databases

## Open Questions
- Should the fixture use `apply_migrations.py` directly, or execute the SQL file contents? The former is more end-to-end but couples tests to the migration runner; the latter is simpler but still a form of duplication.
- How to handle seed data -- should the fixture also run `seed_dev.sql`, or should each test file seed its own data?

## Notes
- Originated from E-100 codex review triage (2026-03-14). SE proposed this as the "structurally correct" fix for the HIGH finding about test fixtures breaking across wave boundaries.
- DE supported the approach (Option B) but all three agents (PM, SE, DE) agreed it was wrong timing to absorb into E-100.
- The user approved fresh-start for E-100 specifically, making this a clean follow-up rather than a mid-dispatch change.

---
Created: 2026-03-14
Last reviewed: 2026-03-14
Review by: 2026-06-14
