# General Dev -- Agent Memory

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
- `docs/` -- API specs and documentation
- `docs/gamechanger-api.md` -- THE single source of truth for GameChanger API knowledge
- `docs/gamechanger-stat-glossary.md` -- authoritative data dictionary for all GameChanger stat abbreviations (batting, pitching, fielding, catcher, positional innings). Includes API field name mapping table for abbreviations that differ between UI and API. Reference when parsing season-stats response fields.

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

## Database Conventions (from data-engineer)
- `ip_outs`: Innings pitched as integer outs (1 IP = 3 outs). Always.
- FK-safe orphan handling: when a player_id is not in `players`, insert a stub row (first_name='Unknown', last_name='Unknown') before writing the stat row. Log a WARNING for operator backfill.
- Splits: nullable columns (home_obp, away_obp, vs_lhp_obp, vs_rhp_obp), not separate rows
- Local dev DB path: `data/app.db`

## Security
- NEVER hardcode credentials in code, tests, or docs
- Use `.env` for local dev (always in `.gitignore`)
- Redact auth headers before storing raw API responses
- GameChanger session tokens are sensitive data -- always

## FastAPI Patterns
- Routes returning `HTMLResponse | RedirectResponse` MUST use `response_model=None` on the decorator
  (otherwise FastAPI tries to make a Pydantic model from the Union and raises FastAPIError)
- `Form(...)` parameters require `python-multipart` installed -- add to requirements.txt
- `BaseHTTPMiddleware` from starlette: use `app.add_middleware(MyMiddleware)` before routers

## Auth System (E-023)
- `src/api/auth.py` -- SessionMiddleware + hash_token + create_session helpers
- `src/api/routes/auth.py` -- /auth/* routes (login/verify/logout)
- `src/api/email.py` -- Mailgun helper (stdout when MAILGUN_API_KEY not set)
- `src/api/templates/auth/` -- login.html, check_email.html, verify_error.html
- DEV_USER_EMAIL bypasses login; auto-creates is_admin=1 user if missing
- Session cookie: name=session, HttpOnly, SameSite=Lax, Max-Age=604800
- Tokens: token_urlsafe(32) for magic links (43 chars), token_hex(32) for sessions (64 chars)
- DB only stores SHA-256 hashes of tokens, never the raw value

## Test Database Pattern (auth-aware)
- Tests that touch the app must include auth tables in schema SQL (users, user_team_access,
  magic_link_tokens, passkey_credentials, sessions) for SessionMiddleware to not raise errors
- Set DEV_USER_EMAIL in test env_overrides to bypass auth for endpoint tests
