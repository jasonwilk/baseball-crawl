-- Migration 008: Create reports table for standalone scouting reports
--
-- Tracks generated scouting report metadata: slug-based public URLs,
-- generation status, expiration, and file path on disk.

CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT UNIQUE NOT NULL,
    team_id INTEGER NOT NULL REFERENCES teams(id),
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'generating',
    generated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    expires_at TEXT NOT NULL,
    report_path TEXT,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_reports_slug ON reports(slug);
CREATE INDEX IF NOT EXISTS idx_reports_team_id ON reports(team_id);
