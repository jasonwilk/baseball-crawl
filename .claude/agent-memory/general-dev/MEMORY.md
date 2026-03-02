# General Dev -- Agent Memory

## Project Code Conventions

### Python Style
- Type hints on ALL function signatures (no exceptions for public functions)
- Google-style docstrings on all public functions and classes
- Prefer dataclasses for structured data; use Pydantic when validation is needed
- `pathlib.Path` for all file paths -- never `os.path`
- `logging` module for operational output -- never `print()` (except CLI user-facing scripts)
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
- `docs/` -- API specs and documentation
- `docs/gamechanger-api.md` -- THE single source of truth for GameChanger API knowledge

### Project Management
- `epics/` -- active epics and story files
- `migrations/` -- numbered SQL migration files (`001_*.sql`, `002_*.sql`, etc.)

## Testing Rules

### Mandatory
- **pytest** is the test runner. No unittest, no nose.
- **NEVER make real HTTP calls** in the test suite. Mock at the transport layer.
- Use `respx` for `httpx` mocking, `responses` for `requests` mocking.
- Test happy path, edge cases (missing fields, empty responses), and error handling.

### Best Practices
- Small, focused test functions over large test classes
- Descriptive names: `test_parse_box_score_handles_missing_hits_field`
- Integration/smoke tests may verify real header profiles; unit tests should not depend on header correctness
- Test data files go in `tests/fixtures/` or inline in the test

## HTTP Request Discipline

### Session Factory
- Location: `src/http/session.py`
- Function: `create_session()` returns a properly configured HTTP client
- Provides: realistic User-Agent, standard browser headers, cookie jar, consistent identity
- **NEVER create raw `httpx.Client()` or `requests.Session()` directly**

### Required Behavior
- Realistic `User-Agent` (Chrome/Firefox on macOS/Windows). Never library defaults.
- Standard browser headers: `Accept`, `Accept-Language`, `Accept-Encoding`, `Referer`/`Origin`
- Cookie jar maintained across requests within a session
- Same User-Agent and header profile for the entire session duration

### Rate Limiting
- 1-2 second delays between sequential requests
- Slight jitter on timing (never exact intervals)
- Exponential backoff on 4xx/5xx errors
- Respect `Retry-After` headers
- No parallel requests unless confirmed safe

### Pattern Hygiene
- Access resources in human-plausible order (list before detail)
- No tight loops requesting the same resource
- Handle redirects and set-cookie like a browser

## Database Conventions (from data-engineer)
- `ip_outs`: Innings pitched as integer outs (1 IP = 3 outs). Always.
- Soft referential integrity: log WARNING on orphaned player IDs, do not reject
- Splits: nullable columns (home_obp, away_obp, vs_lhp_obp, vs_rhp_obp), not separate rows
- Local dev DB path: `data/app.db`

## Security
- NEVER hardcode credentials in code, tests, or docs
- Use `.env` for local dev (always in `.gitignore`)
- Redact auth headers before storing raw API responses
- GameChanger session tokens are sensitive data -- always
