# ETL Patterns, Pagination, and Token Scheduling

## Token Lifetime and ETL Scheduling (confirmed 2026-03-04)

- **Token lifetime is 14 days** (JWT `exp - iat = 1,209,600 seconds`). Previous assumption of ~1 hour was wrong.
- **Implication for ETL**: A single browser capture can power up to 14 days of authenticated API calls. Batch ingestion jobs (opponent scouting across 50+ teams, full season box score crawls) are feasible within a single token lifetime without credential rotation.
- **Programmatic refresh NOT possible**: The `POST /auth` endpoint requires a `gc-signature` HMAC with an unknown signing key. Token rotation still requires manual browser captures, but at ~2-week intervals rather than hourly.
- **ETL scheduling recommendation**: Plan ingestion runs as batch jobs within a token's lifetime window. A single token can support the full ingestion pipeline (opponents enumeration -> team-detail per opponent -> season-stats per opponent -> game-summaries -> boxscores -> plays) without expiring mid-run.

## ETL Patterns

- Raw-to-processed pipeline: (1) store raw API JSON blobs as audit trail, (2) parse and normalize into schema tables
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
