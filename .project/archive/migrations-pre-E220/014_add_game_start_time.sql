-- Migration 014: Add start_time and timezone columns to games table.
-- Supports chronological game ordering (E-196).
--
-- start_time: ISO 8601 datetime string (e.g., "2025-04-26T16:00:00.000Z")
-- timezone: IANA timezone identifier (e.g., "America/Chicago")
--
-- Both columns are nullable. Existing rows remain NULL until next sync.

ALTER TABLE games ADD COLUMN start_time TEXT;
ALTER TABLE games ADD COLUMN timezone TEXT;
