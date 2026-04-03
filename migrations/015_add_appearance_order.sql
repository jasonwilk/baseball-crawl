-- Migration 015: Add appearance_order column to player_game_pitching.
-- Tracks pitcher appearance order within a game (1 = starter, 2+ = relievers).
-- Supports E-204: Starter vs. Relief Appearance Tracking.
--
-- Nullable: existing rows remain NULL until backfill (E-204-02).

ALTER TABLE player_game_pitching ADD COLUMN appearance_order INTEGER;
