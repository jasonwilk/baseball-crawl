# E-102: Pipeline INTEGER PK Migration

## Status
`ABANDONED`
<!-- Reason: Codex spec review revealed no valid intermediate state between INTEGER PK schema and TEXT-based code. All 3 stories absorbed into E-100 (stories 02-05). -->

## Overview
Migrate all pipeline code (crawlers, loaders, config, CLI) from TEXT `team_id` references to the INTEGER PK (`teams.id`) introduced by E-100. Introduces a `TeamRef` dataclass pattern to separate internal DB identity from external GC identifiers (gc_uuid, public_id) throughout the pipeline.

## Background & Context
E-100 rewrites the schema with `teams.id INTEGER PRIMARY KEY AUTOINCREMENT`, but E-100-02 only handles the `is_owned` → `membership_type` column rename in pipeline code. The existing pipeline code still uses TEXT `team_id` values (GC UUIDs) as both DB foreign keys and API identifiers interchangeably. With INTEGER PKs, these two roles must be separated: DB operations use the integer `id`, while API calls use `gc_uuid` or `public_id`. SE designed a `TeamRef` dataclass pattern to cleanly separate these concerns.

**Expert consultation completed:**
- **Software Engineer**: Designed `TeamRef(id: int, gc_uuid: str, public_id: str | None)` dataclass. Identified 3 story scopes: (1) TeamRef resolution layer + CrawlConfig changes, (2) stub-insert refactor across 6 loader/crawler files, (3) admin URL routing from TEXT to INTEGER. Estimated ~3 stories.

**No expert consultation required for:**
- Data Engineer: Schema is already delivered by E-100-01 — no additional schema changes needed.
- UX Designer: No UI changes — admin URLs change from TEXT to INTEGER which is a backend concern.

## Goals
- All pipeline SQL uses INTEGER `teams.id` for FK references and lookups
- `TeamRef` dataclass provides clean separation of DB identity (int) from GC identity (gc_uuid, public_id)
- `CrawlConfig.TeamEntry` gains `internal_id: int` for DB FK operations
- All stub-INSERT patterns in crawlers/loaders use `lastrowid` / lookup-by-external-id patterns
- Admin URL routes use INTEGER team IDs

## Non-Goals
- **Schema changes**: E-100-01 delivers the INTEGER PK schema; this epic only migrates code to use it
- **Multi-credential support**: Deferred per E-100 decision
- **Dashboard query changes**: Dashboard program-awareness is a separate epic

## Success Criteria
- All `team_id TEXT` references in pipeline SQL replaced with `teams.id INTEGER` references
- `TeamRef` dataclass exists and is used throughout crawlers and loaders
- All existing tests pass with INTEGER PK schema
- No remaining TEXT `team_id` FK usage in pipeline code

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-102-01 | TeamRef resolution layer and CrawlConfig changes | TODO | E-100 (completed) | - |
| E-102-02 | Stub-insert refactor across crawlers and loaders | TODO | E-102-01 | - |
| E-102-03 | Admin URL routing — TEXT to INTEGER team IDs | TODO | E-102-01 | - |

## Dispatch Team
- software-engineer (E-102-01, E-102-02, E-102-03)

## Technical Notes

### TeamRef Pattern (SE Design)
```
@dataclass
class TeamRef:
    id: int           # internal DB PK (teams.id)
    gc_uuid: str      # GC UUID for authenticated API calls
    public_id: str | None  # GC slug for public API calls
```

Pipeline code receives `TeamRef` objects from config/resolution, uses `.id` for all DB operations, and `.gc_uuid` / `.public_id` for API calls. This eliminates the dual-meaning `team_id` that previously served as both DB key and API identifier.

### CrawlConfig Changes
- `TeamEntry` gains `internal_id: int` field populated by `load_config_from_db()` from `teams.id`
- `load_config()` (YAML path) needs a DB lookup step to resolve team entries to internal IDs
- Crawlers receive `TeamRef` (or equivalent) instead of raw `team_id: str`

### Stub-Insert Refactor (6 Files)
Files that INSERT stub team rows for unknown opponents/teams currently use TEXT `team_id`. With INTEGER PKs, these must:
1. Check if team exists by `gc_uuid` or `public_id` (UNIQUE columns)
2. If not, INSERT and capture `lastrowid` for the new INTEGER PK
3. Use the INTEGER PK for subsequent FK references

Affected files: `game_loader.py`, `roster.py`, `season_stats_loader.py`, `scouting_loader.py`, `scouting.py`, `opponent_resolver.py`

### Admin URL Routing
Admin routes currently use TEXT `team_id` in URL paths (e.g., `/admin/teams/{team_id}/edit`). With INTEGER PKs, these become `/admin/teams/{id:int}/edit`. The route parameter type changes from `str` to `int`.

### Wave Plan
- **Wave 1**: E-102-01 (TeamRef + CrawlConfig foundation)
- **Wave 2**: E-102-02 + E-102-03 (parallel — 02 touches crawlers/loaders, 03 touches admin routes, minimal file overlap)

## Open Questions
- None. Design decisions resolved during E-100 consultation.

## History
- 2026-03-13: Created as follow-on to E-100 (team model overhaul). SE scoped during E-100 INTEGER PK consultation.
