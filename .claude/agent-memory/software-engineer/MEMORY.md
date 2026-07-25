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

## Working as a Dispatched Subagent

- [dispatch-git-gotchas.md](dispatch-git-gotchas.md) -- `git rm` stages the deletion, hiding it from CR's unstaged `git diff` (hid 97 lines in E-256-03); new untracked files are invisible to `git diff --stat`; mid-epic the baseline is `git show :<file>`, never `HEAD:<file>`
- [feedback_dead_symbol_deletion.md](feedback_dead_symbol_deletion.md) -- A lint-flagged unused binding can be an unfinished intent (found the WebAuthn `exclude_credentials` gap, E-256-08). Check for evidence outside the code; delete by literal block, never by symbol name (two `all_dates`, one live)

## Topic File Index

- [endpoint-parsing-notes.md](endpoint-parsing-notes.md) -- Detailed parsing guidance for all GameChanger API endpoints: token health check, credential management (two-token architecture, JWT fields, headers), team-detail, pagination, player-stats, schedule (location polymorphism, full-day format), opponents (three UUID semantics), boxscore (asymmetric keys, sparse extras, batting order), plays (UUID templates, pitch sequences, lineup changes, edge cases), bridge endpoints, roster (URL pattern warning), public endpoints (no-auth client, record key normalization, avatar_url patterns)
- [app-conventions.md](app-conventions.md) -- Database conventions (ip_outs, FK-safe orphans, splits), security rules, FastAPI patterns (response_model=None, Form, middleware), auth system (E-023: SessionMiddleware, magic links, DEV_USER_EMAIL bypass), test database pattern (auth-aware schema)
- [module-global-seams.md](module-global-seams.md) -- Moving a function re-binds every module global it reads (`get_connection`, `_REPO_ROOT`) to the NEW module — detaching test patches. A seam behind a swallowed exception detaches with ZERO failures. Inject the dependency; never use failures as the search method.
- [name-matching-gotchas.md](name-matching-gotchas.md) -- Free-text team/age_group matching fails SILENTLY to a suppressed card or wrong rest table: `\b` does not fire against `_` (`high_freshman`), plurals need `s?` (`\breserve\b` missed "Reserves"), first-match tables hide precedence (`varsity` beats `legion`); reconstruct the OLD table and diff to find the real blast radius
- [testing-gotchas.md](testing-gotchas.md) -- In an epic worktree `pytest` loads WORKTREE src (`_EditableFinder` is appended after `PathFinder`; needs `tests/__init__.py` + repo root on `sys.path`) — the spawn note says otherwise and is wrong; never trust a `pytest | tail` exit code (capture real RC); three ways a tool silently reports zero (`$(git ls-files)` doesn't word-split; ruff `include` filters walks not explicit paths; `.pyc` invisible to `git status`); ruff parses `# noqa` in prose; `db.backup()` onto the same path deadlocks in test_report_generator.py
