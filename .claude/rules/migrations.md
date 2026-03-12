---
paths:
  - "migrations/**"
---

# Migration Conventions

## Numbering Scheme

- Sequential, zero-padded to 3 digits: `001`, `003`, `004`, etc.
- Never reuse a migration number, even if a slot is unused.
- Current sequence: 001, 003, 004, 005, 006 (slot 002 is unused -- do not backfill).
- Next migration: `007`.

## Naming Pattern

`NNN_descriptive_name.sql` -- e.g., `006_opponent_links.sql`.

## Idempotency Requirements

All migrations MUST be idempotent:
- Use `CREATE TABLE IF NOT EXISTS` for table creation.
- Use `CREATE INDEX IF NOT EXISTS` for index creation.
- Use `INSERT OR IGNORE` or `INSERT ... ON CONFLICT DO NOTHING` for seed data.
- Re-running a migration must not fail or duplicate data.
- **ALTER TABLE exception**: SQLite has no `ALTER TABLE ADD COLUMN IF NOT EXISTS` syntax. `ALTER TABLE ADD COLUMN` migrations are safe without DDL-level idempotency because `apply_migrations.py` tracks applied migrations in `_migrations` and runs each exactly once. Precedent: migration 005 (`ALTER TABLE teams ADD COLUMN public_id TEXT`).

## Seed Data

Seed data (reference data that the application requires at startup) belongs in migration files alongside the schema it depends on. Use `INSERT OR IGNORE` to make seed inserts idempotent.

## SQLite `datetime('now')` Format

`datetime('now')` in SQLite produces `'YYYY-MM-DD HH:MM:SS'` format -- space separator, no `T`, no `Z`. This is NOT ISO 8601 with `T`/`Z`. When comparing or parsing timestamps from SQLite, account for this format.

## Application

Migrations are applied via `python migrations/apply_migrations.py`. The `migrations/` directory is a Python package (`__init__.py` exists) because `src/db/reset.py` imports from it.
