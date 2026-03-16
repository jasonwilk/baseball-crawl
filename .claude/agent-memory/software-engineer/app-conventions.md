# App Conventions -- DB, Security, FastAPI, Auth, and Testing

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
