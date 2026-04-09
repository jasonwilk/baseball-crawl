---
paths:
  - "migrations/**"
---

# Migration Conventions

## Numbering Scheme

- Sequential, zero-padded to 3 digits: `001`, `002`, `003`, etc.
- Never reuse a migration number, even if a slot is unused.
- Current sequence: `001` only. `001_initial_schema.sql` is the consolidated schema rewrite from E-220 (old migrations 001-015 archived in `.project/archive/migrations-pre-E220/`). The E-220 rewrite folded all prior migrations into a single initial-schema file with `perspective_team_id` as a first-class concept on stat tables.
- Next migration: `002`.

## Naming Pattern

`NNN_descriptive_name.sql` -- e.g., `002_add_something.sql`.

## Idempotency Requirements

All migrations MUST be idempotent:
- Use `CREATE TABLE IF NOT EXISTS` for table creation.
- Use `CREATE INDEX IF NOT EXISTS` for index creation.
- Use `INSERT OR IGNORE` or `INSERT ... ON CONFLICT DO NOTHING` for seed data.
- Re-running a migration must not fail or duplicate data.
- **ALTER TABLE exception**: SQLite has no `ALTER TABLE ADD COLUMN IF NOT EXISTS` syntax. `ALTER TABLE ADD COLUMN` migrations are safe without DDL-level idempotency because `apply_migrations.py` tracks applied migrations in `_migrations` and runs each exactly once.

## Seed Data

Seed data (reference data that the application requires at startup) belongs in migration files alongside the schema it depends on. Use `INSERT OR IGNORE` to make seed inserts idempotent.

## SQLite `datetime('now')` Format

`datetime('now')` in SQLite produces `'YYYY-MM-DD HH:MM:SS'` format -- space separator, no `T`, no `Z`. This is NOT ISO 8601 with `T`/`Z`. When comparing or parsing timestamps from SQLite, account for this format.

## `executescript()` and PRAGMAs

SQLite's `executescript()` implicitly commits any open transaction and resets connection state. A `PRAGMA foreign_keys=ON` set on the connection before `executescript()` has **no effect** on the SQL it runs. If a script needs FK enforcement, prepend `PRAGMA foreign_keys=ON;\n` to the SQL string passed to `executescript()`.

## Application

Migrations are applied via `python migrations/apply_migrations.py`. The `migrations/` directory is a Python package (`__init__.py` exists) because `src/db/reset.py` imports from it.
