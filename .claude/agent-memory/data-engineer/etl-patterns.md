# ETL Patterns, Pagination, and Token Scheduling

## Token Refresh (programmatic — no manual capture needed)

- **Programmatic refresh IS implemented.** The `gc-signature` HMAC-SHA256 algorithm was
  reverse-engineered (2026-03-07) and lives in `src/gamechanger/signing.py`, using a known
  Base64 client key. An earlier note here claimed the signing algorithm could not be reproduced
  and that manual browser captures were the only path — that is FALSE and has been corrected.
- **`src/gamechanger/token_manager.py`** exchanges the refresh token for a short-lived access
  token via `POST /auth` (signed by `signing.py`), caches it in memory, and auto-refreshes
  before expiry (`get_access_token()` refreshes when within the expiry safety margin), with a
  login fallback for the web profile. Rotated refresh tokens are persisted back to `.env`.
- **Implication for ETL**: batch ingestion jobs (opponent scouting, full-season box score
  crawls, the boxscores/plays pipeline) do not need manual browser re-captures — the token
  manager refreshes transparently mid-run. Do NOT assert a specific token lifetime here (any
  concrete figure is unmeasured against the current auth flow); rely on the auto-refresh.

## ETL Patterns

- **There is no raw-to-processed pipeline.** The live ingestion paths (ScoutingLoader -> GameLoader, morning-run, `bb report generate`) crawl-to-load in memory and transform API JSON in flight straight into schema tables, with no on-disk raw stage and no audit-trail blob. This entry said the opposite until 2026-07-26; following it would rebuild the file-reading loader twin that E-256 deleted. Raw bytes persist only on the out-of-band capture paths -- mitmproxy's `proxy/data/`, and one redacted documentation sample per endpoint under `data/raw/`. See `.claude/rules/architecture-subsystems.md` and `http-discipline.md`.
- Ingestion must be idempotent: `INSERT OR IGNORE` or `INSERT ... ON CONFLICT` patterns
- Bulk-load a full game's worth of data in a single transaction
- Handle missing/null fields gracefully: log warnings, do not crash

### Pagination (confirmed 2026-03-04)
- game-summaries uses cursor-based pagination via `x-next-page` response header
- End-of-pagination signal: `x-next-page` header absent from response (do NOT check for empty body)
- Page size: 50 records max; final page may have fewer
- Full season for one team: 92 game records across 2 pages
- Working pagination loop pattern with code is in `docs/api/pagination.md`

## Project File Paths

- Migrations: `migrations/`
- Database: `./data/app.db`
- API spec (source of truth for response shapes): `docs/api/README.md` (index), `docs/api/endpoints/` (per-endpoint files)
- Stat glossary (authoritative stat abbreviation definitions): `docs/gamechanger-stat-glossary.md`
  - Includes API field name mapping table (UI abbreviation -> API field name) -- critical for mapping season-stats API fields to schema columns
  - Covers: batting (standard + advanced), pitching (standard + advanced), pitch types, fielding, catcher, positional innings
- Source code: `src/`
- Tests: `tests/`
