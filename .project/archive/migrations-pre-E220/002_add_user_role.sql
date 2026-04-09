-- Migration 002: Add role column to users table
--
-- Adds a `role` column to distinguish admin users from regular users.
-- Valid role values: 'admin', 'user'
-- All existing users default to 'role = user' via the DEFAULT clause.
-- Application-layer validation enforces role values (SQLite cannot add
-- CHECK constraints to existing columns via ALTER TABLE).

ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user';
