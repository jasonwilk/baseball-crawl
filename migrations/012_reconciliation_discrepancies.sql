-- E-198-01: Reconciliation discrepancies table for plays-vs-boxscore comparison.
--
-- One row per signal per player per team per run.
-- Game-level signals use '__game__' as player_id sentinel.

CREATE TABLE IF NOT EXISTS reconciliation_discrepancies (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id           TEXT    NOT NULL REFERENCES games(game_id),
    run_id            TEXT    NOT NULL,
    team_id           INTEGER NOT NULL REFERENCES teams(id),
    player_id         TEXT    NOT NULL,
    signal_name       TEXT    NOT NULL,
    category          TEXT    NOT NULL,
    boxscore_value    INTEGER,
    plays_value       INTEGER,
    delta             INTEGER,
    status            TEXT    NOT NULL CHECK(status IN ('MATCH', 'CORRECTABLE', 'CORRECTED', 'AMBIGUOUS', 'UNCORRECTABLE')),
    correction_detail TEXT,
    created_at        TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(run_id, game_id, team_id, player_id, signal_name)
);

CREATE INDEX IF NOT EXISTS idx_recon_game_id ON reconciliation_discrepancies(game_id);
CREATE INDEX IF NOT EXISTS idx_recon_run_id ON reconciliation_discrepancies(run_id);
CREATE INDEX IF NOT EXISTS idx_recon_status ON reconciliation_discrepancies(status);
