# Software Engineer -- Agent Memory

## Project Code Conventions

### Python Style
See CLAUDE.md Code Style section and `.claude/rules/python-style.md`.
- Conventional commits: `feat(E-NNN-SS):`, `fix(E-NNN-SS):`, `test(E-NNN-SS):`, etc.

### Data Handling
- Parse defensively: missing fields produce warnings, not crashes
- Loaders must be idempotent -- re-running the same data must not create duplicates
- Store raw API responses before transforming (raw -> processed pipeline)
- Use dataclasses or Pydantic models between functions, not raw dicts

## Key File Paths

### Source Code
- `src/` -- all source modules (crawlers, parsers, loaders, utilities)
- `src/http/session.py` -- HTTP session factory (`create_session()`). ALWAYS use this for HTTP clients.
- `tests/` -- all test files, mirroring `src/` structure
- `scripts/` -- utility and operational scripts (e.g., `scripts/refresh_credentials.py`)

### Data and Docs
- `data/` -- local dev data outputs, SQLite database (`data/app.db`)
- `data/raw/` -- raw API response samples (gitignored). Inventory: game-summaries (2 pages), me-teams, me-user (PII-redacted), player-stats (80 records, 387 KB), schedule (228 events, 134 KB), team-detail (own + opponent), boxscore (13 KB, both teams), game-plays (37 KB, 58 plays), public-team-profile, public-team-games (32 records, 25.7 KB), public-team-games-preview (prefer `/games` sample), opponents (70 records, 17 KB), public-game-details (~500 bytes), players-roster (20 players, LSB JV, 2.3 KB), best-game-stream-id (58 bytes), team-users (PII-redacted, no coaching value), public-team-profile-id (~20 bytes), auth-refresh (annotated schema, no live tokens)
- `docs/` -- API specs and documentation
- `docs/api/README.md` -- API documentation index; per-endpoint files in `docs/api/endpoints/`
- `docs/gamechanger-stat-glossary.md` -- authoritative data dictionary for all GameChanger stat abbreviations. Reference when parsing season-stats response fields.

### API Parsing Quirks
- `/me/teams` and `/teams/{team_id}` `ngb` field: **JSON-encoded string**, not a native JSON array. Must double-parse: `json.loads(team["ngb"])`.

### Project Management
- `epics/` -- active epics and story files
- `migrations/` -- numbered SQL migration files (`001_*.sql`, `002_*.sql`, etc.)

## Testing Rules
See CLAUDE.md Testing section and `.claude/rules/testing.md`.
- Use `respx` for `httpx` mocking, `responses` for `requests` mocking.
- Test data files go in `tests/fixtures/` or inline in the test.

## HTTP Request Discipline
See CLAUDE.md HTTP Request Discipline section.
- Session factory: `src/http/session.py`, function `create_session()`
- **NEVER create raw `httpx.Client()` or `requests.Session()` directly** -- always use `create_session()`

## Topic File Index

- [endpoint-parsing-notes.md](endpoint-parsing-notes.md) -- Detailed parsing guidance for all GameChanger API endpoints: token health check, credential management (two-token architecture, JWT fields, headers), team-detail, pagination, player-stats, schedule (location polymorphism, full-day format), opponents (three UUID semantics), boxscore (asymmetric keys, sparse extras, batting order), plays (UUID templates, pitch sequences, lineup changes, edge cases), bridge endpoints, roster (URL pattern warning), public endpoints (no-auth client, record key normalization, avatar_url patterns)
- [app-conventions.md](app-conventions.md) -- Database conventions (ip_outs, FK-safe orphans, splits), security rules, FastAPI patterns (response_model=None, Form, middleware), auth system (E-023: SessionMiddleware, magic links, DEV_USER_EMAIL bypass), test database pattern (auth-aware schema)
