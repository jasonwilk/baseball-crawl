# E-002: GameChanger Data Ingestion Pipeline

## Status
`ACTIVE`

## Overview
Build the pipeline that crawls GameChanger API endpoints, stores raw JSON responses on disk, and loads normalized records into the SQLite database. When this epic is complete, coaches will have up-to-date game and player stats for their teams -- and their opponents -- persisted in a queryable database.

## Background & Context
With API access established (E-001), the next step is actually pulling data. The pipeline has two responsibilities that must be kept separate per the project architecture:

1. **Raw crawling**: Fetch data from the GameChanger API and write unmodified JSON to the local filesystem. This is the "raw" layer. It is idempotent and can be re-run safely.
2. **Loading/normalization**: Read raw JSON files and insert/upsert normalized records into the database. This is the "processed" layer.

Keeping these separate means: if the database schema changes, we can re-process from raw without re-crawling. If the API changes, we can re-crawl without touching the schema.

Scope for this epic covers Lincoln Standing Bear High School teams (Freshman, JV, Reserve, Varsity) and the opponents they play. Legion teams are explicitly out of scope but the design should not prevent adding them later.

**This epic is DRAFT until E-001-03 (API spec) is complete.** Stories will be finalized once the exact endpoint shapes are known.

## Goals
- A crawl script that fetches team roster, schedule, and game stats for all configured teams and writes raw JSON to `data/raw/`
- A load script that reads raw JSON and upserts records into the SQLite database
- Opponent data is captured: when our team plays a game, the opponent's stats for that game are also pulled
- The pipeline is idempotent: re-running does not create duplicate records
- A manifest/log of what was crawled and when, so we know what data is fresh

## Non-Goals
- Real-time or event-driven ingestion (batch only)
- Automatic scheduling (cron) -- that's a separate story
- Any dashboard or visualization of the ingested data
- Stats computation or derived metrics -- only store what the API provides
- Legion/travel team ingestion (out of scope for this epic; designed to be extensible)

## Success Criteria
- Running `python scripts/crawl.py --teams all` for a configured season produces JSON files in `data/raw/` for every team, game, and player in scope
- Running `python scripts/load.py` after a crawl populates the database with records that match the raw JSON (verify with spot-check queries)
- Re-running both scripts produces no duplicates and no errors
- Opponent stats are present in the database for all games in the schedule
- A `data/raw/manifest.json` file records the crawl timestamp and count of records fetched per endpoint

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-002-01 | Crawl team roster and write raw JSON | TODO | E-001-02, E-001-03 | - |
| E-002-02 | Crawl game schedule and write raw JSON | TODO | E-001-02, E-001-03 | - |
| E-002-03 | Crawl game stats (box score) and write raw JSON | TODO | E-002-02 | - |
| E-002-04 | Crawl player season stats and write raw JSON | TODO | E-002-01 | - |
| E-002-05 | Crawl opponent team data for all scheduled games | TODO | E-002-02 | - |
| E-002-06 | Load raw roster JSON into database | TODO | E-002-01, E-003-01 | - |
| E-002-07 | Load raw game and stats JSON into database | TODO | E-002-03, E-003-01 | - |
| E-002-08 | Write crawl manifest and orchestration script | TODO | E-002-01, E-002-02, E-002-03, E-002-04, E-002-05 | - |

## Technical Notes

### Directory Structure for Raw Data
```
data/
  raw/
    {season}/
      teams/
        {team_id}/
          roster.json
          schedule.json
          stats.json
          games/
            {game_id}.json
      manifest.json
```

### Idempotency
Each crawl target should check: does a file for this team/game/season already exist and is it less than N hours old? If yes, skip. If no (or stale), fetch and overwrite. The freshness threshold should be configurable (default: 24 hours).

### Opponent Data
When crawling a game, we know the opponent's team ID from the schedule. Crawl the opponent's public profile using the same endpoints used for our own teams. Opponent data goes in the same directory structure under their team ID.

### Config File
A `config/teams.yaml` file (gitignored? or committed?) lists the team IDs we own and want to track. Example:
```yaml
season: "2025"
owned_teams:
  - id: "abc123"
    name: "Lincoln Freshman"
    level: "freshman"
  - id: "def456"
    name: "Lincoln Varsity"
    level: "varsity"
```

### Relationship to E-003
Load stories (E-002-06, E-002-07) depend on the database schema being established in E-003. The crawl stories (E-002-01 through E-002-05) can proceed independently.

## Open Questions
- What is the GameChanger API endpoint for opponent/away team stats? (Answered by E-001-03)
- Are all opponent team stats visible, or only stats from games where our team was involved?
- What seasons of historical data are available? (One season back? Multiple?)
- Does GameChanger provide play-by-play data, or only aggregate game stats?

## History
- 2026-02-28: Created as DRAFT pending E-001-03 completion
- 2026-03-01: Clarify pass -- replaced all Cloudflare D1 references with SQLite per E-009 tech stack decision. The crawl stories (E-002-01 through E-002-05) are unaffected. The load stories (E-002-06, E-002-07) now target SQLite via apply_migrations.py schema instead of D1.
