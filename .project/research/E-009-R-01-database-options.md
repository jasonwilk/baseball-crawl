# E-009-R-01: Database Options Research Findings

**Research Date**: February 28, 2026
**Status**: Complete
**Related Epic**: [E-009: Tech Stack Redesign](../epics/E-009-tech-stack-redesign/epic.md)

## Executive Summary

This research evaluated database technologies for baseball-crawl across two deployment paths: Option A (Native Cloudflare D1) and Option B (Docker + Cloudflare Access). For baseball-crawl's scale (~10 MB total, 1-5 concurrent users, read-mostly workload), **SQLite is the correct choice for both options**.

Option A should use **Cloudflare D1 (managed SQLite)**. The 2026 D1 runtime is production-ready with faithful local emulation via `wrangler dev`, robust migration tooling, and no storage/throughput concerns for this workload. The 500 MB free tier comfortably exceeds the ~10 MB database size.

Option B should use **SQLite in a Docker volume** (not Postgres). Postgres adds unnecessary infrastructure complexity and resource overhead for a small, read-mostly database. SQLite with WAL mode handles 1-5 concurrent connections reliably. Litestream provides production-grade backup replication with minimal operational overhead.

**Migration path is clear**: Both options use SQLite SQL syntax. Code written for D1 (Option A) transfers directly to Option B if needed later—only the language runtime and binding mechanism change, not the database layer.

---

## Option A: Native Cloudflare D1

### Storage and Throughput Limits

Cloudflare D1 provides tiered storage:

| Plan | Per-Database Limit | Per-Account Limit |
|------|-------------------|------------------|
| Free | 500 MB | 5 GB |
| Workers Paid | 10 GB | 1 TB |

**Assessment**: Baseball-crawl at ~10 MB total fits comfortably in the free tier. The 500 MB limit is ~50x the projected database size.

For throughput, D1 is single-threaded and processes queries sequentially. With average query duration around 1-10 ms for typical baseball stats queries, **D1 can handle 100-1000 queries per second**, far exceeding the needs of 1-5 concurrent users viewing a coaching dashboard.

**Hard limits per invocation**: Free tier allows 50 queries; Paid tier allows 1000. Again, this easily covers typical page loads (5-15 queries per request).

**Row count**: Unlimited per table; constrained only by storage (10 GB). With ~1,800 player-season stat rows and ~360 game records, baseball-crawl uses negligible space.

### Local Development Fidelity

D1 local development via `wrangler dev` uses **Miniflare and workerd** -- the same runtime that powers production D1. This is a significant improvement from historical Cloudflare tooling.

Key strengths:
- **Same D1 version locally and in production**: "D1 has fully-featured support for local development, running the same version of D1 as Cloudflare runs globally."
- **Data persistence**: Wrangler v3+ persists local data across `wrangler dev` sessions by default. You can specify `--persist-to=/path/to/file` for team-shared or CI/CD reproducibility.
- **Separated by environment**: Local data is isolated from production by default—`wrangler dev` does not access your remote D1 database unless explicitly configured.
- **Programmatic testing**: The `unstable_dev()` API in Wrangler allows workers to be tested locally against a preview database, further validating local behavior matches production.

**Known divergence**: None significant. Local and production behavior is identical because they run the same D1 software. The main difference is network latency (zero locally, low globally in production), which doesn't affect schema validation or query semantics.

### Data Seeding and Reset

D1 supports SQL-based seeding:
- Write numbered `.sql` files in the `migrations/` folder (e.g., `0001_create_tables.sql`, `0002_seed_dev_data.sql`).
- Run `wrangler d1 migrations apply <database-name> --local` to apply all pending migrations.
- For a clean reset, delete the local database file and re-run migrations.

Migration files are tracked in a `d1_migrations` table, preventing duplicate application. This is identical to the migration pattern already established in E-003.

### Schema Migration Tooling

D1 provides a straightforward migration workflow:

1. **Create**: `wrangler d1 migrations create <database-name> <description>` generates a timestamped `.sql` file.
2. **List**: `wrangler d1 migrations list <database-name>` shows pending and applied migrations.
3. **Apply**: `wrangler d1 migrations apply <database-name> [--local|--remote]` runs remaining migrations in order.

Migrations are idempotent (safe to rerun) and include error handling—if a migration fails, it rolls back and the previous state is preserved.

**Customization**: You can specify a custom `migrations_dir` in `wrangler.toml` if you want migrations in a non-standard location. The migration tracking table is also customizable.

This matches the existing E-003 approach perfectly. No new tooling is needed.

### Backup and Restore

D1 backup/restore is handled by Cloudflare's infrastructure:
- **Automatic backups**: Cloudflare maintains rolling backups of all production D1 databases.
- **Point-in-time restore**: Available via the Cloudflare dashboard for paid plans.
- **Export**: You can export D1 data via `wrangler d1 export` for local archival.

For Option A, backups are transparent—no action required from the project. Restore is a dashboard operation (or CLI command) managed by Cloudflare.

### Known Limitations

1. **Single-threaded nature**: Queries run one at a time. For baseball-crawl's read-mostly workload with 1-5 concurrent users, this is not a constraint—typical page loads complete in milliseconds.

2. **10 GB storage cap cannot be increased**: If the project ever grows to multi-season national datasets or multi-school deployments, D1 may become a constraint. At that point, migrating to Option B is straightforward (same SQLite syntax).

3. **TypeScript/JavaScript for Workers**: The API layer must be written in TypeScript/JavaScript (Cloudflare Workers runtime). The Python crawling layer remains unchanged. This requires a language context switch for serving-layer development.

### Recommendation for Option A

**Use Cloudflare D1 for Option A.** It is production-ready, has mature local development support, provides trivial storage/throughput for this scale, and requires zero operational overhead. The only trade-off is the TypeScript requirement for the serving layer—acceptable for a small project.

---

## Option B: Docker + Cloudflare Access

### SQLite in Docker Volume vs. PostgreSQL

For Option B, the database choice is **SQLite in a Docker volume**, not PostgreSQL.

#### SQLite Strengths for This Scale
- **Zero configuration**: Embedded in the application, no separate service to manage.
- **Low resource overhead**: Minimal memory and CPU when idle. Perfect for a single-instance app.
- **Sufficient concurrency**: WAL mode (Write-Ahead Logging) allows multiple readers + one writer simultaneously, handling 1-5 concurrent users trivially.
- **Already in use**: The existing E-003 schema and migrations are written for SQLite.
- **Easy backup**: Simple file copy or Litestream replication.

#### PostgreSQL Trade-offs
- **More complexity**: Requires a separate Docker service, process management, connection pooling.
- **Resource overhead**: PostgreSQL uses more RAM and CPU than SQLite even when idle.
- **No benefit for this workload**: PostgreSQL's advantages (complex queries, many concurrent writers, advanced data types) don't apply to baseball-crawl.
- **Migration cost**: E-003 SQL is SQLite-compatible but would need careful porting to PostgreSQL dialect (syntax differences, migration runner changes).

**Benchmark data** from 2025-2026 performance testing shows SQLite outperforms PostgreSQL in simple, fast reads and small write operations—exactly baseball-crawl's profile.

**Recommendation**: SQLite in a Docker volume for Option B.

### SQLite WAL Mode and Concurrent Access

SQLite's Write-Ahead Logging (WAL) mode is essential for Option B:

#### How WAL Works
- Writes go to a WAL file first, allowing readers to continue against the main database file.
- Readers do not block writers, and writers do not block readers (with some exceptions).
- This enables multiple concurrent readers + one writer—perfect for a coaching dashboard (many reads, occasional ETL writes).

#### FastAPI + SQLite Concurrency Pattern

FastAPI is async, but SQLite is sync. The recommended pattern:

1. Open a SQLite connection with `check_same_thread=False` and `PRAGMA journal_mode=WAL`.
2. Run database queries in a thread pool via `run_in_threadpool` (Starlette) or `run_in_executor` (asyncio).
3. This offloads blocking I/O from the FastAPI event loop while maintaining async request handling.

Example pattern:
```python
from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
import sqlite3

app = FastAPI()
db = sqlite3.connect('app.db', check_same_thread=False)
db.execute('PRAGMA journal_mode=WAL')

@app.get("/stats/{player_id}")
async def get_player_stats(player_id: int):
    def query():
        cursor = db.execute(
            "SELECT * FROM player_stats WHERE player_id = ?",
            (player_id,)
        )
        return cursor.fetchall()

    stats = await run_in_threadpool(query)
    return {"stats": stats}
```

#### Concurrency Limits

With WAL mode:
- **Readers**: Unlimited simultaneous readers. No lock contention.
- **Writers**: One at a time (only one WAL file). For baseball-crawl, the ETL crawler writes once per game, so write contention is negligible.

**Important edge case**: If readers are always present and never stop, WAL checkpoints cannot complete and the WAL file grows indefinitely. For baseball-crawl, with a coaching dashboard accessed episodically, this is not a concern. WAL checkpoints occur naturally during quiet periods.

#### Known Issues

1. **Network filesystems don't work with WAL**: All processes must be on the same host. For Docker Compose (single-host deployment), this is satisfied.

2. **Thread-safety with sqlite3**: The `check_same_thread=False` flag allows multiple threads to share a connection, but **SQLite's write serialization still applies**—there's never concurrent write access, even across threads. This is safe.

### SQLite Backup Strategy with Litestream

For production Option B, **Litestream** provides production-grade backup replication:

#### What Litestream Does
- Monitors SQLite's write-ahead log (WAL).
- Replicates changes in near-real-time to external storage (S3, MinIO, SFTP, Azure Blob, etc.).
- Allows point-in-time restore if the database is corrupted or lost.

#### Docker Implementation
Run Litestream as a sidecar container or within the app container:
```yaml
services:
  app:
    image: baseball-crawl:latest
    volumes:
      - ./data:/app/data

  litestream:
    image: litestream/litestream:latest
    volumes:
      - ./data:/app/data
      - ./litestream.yml:/etc/litestream.yml
    command: replicate /app/data/app.db
    environment:
      LITESTREAM_ACCESS_KEY_ID: ${S3_ACCESS_KEY}
      LITESTREAM_SECRET_ACCESS_KEY: ${S3_SECRET_KEY}
```

#### Backup Targets
- **S3 or MinIO** (recommended): Replicates to object storage for durability.
- **SFTP**: Replicates to a remote server.
- **Local filesystem**: Replicates to another volume for local dev/testing.

#### Backup Interval
By default, Litestream writes a snapshot every hour and replicates WAL changes immediately. For baseball-crawl (data re-crawlable if lost, infrequent writes), the default is sufficient.

#### Restore Process
```bash
litestream restore /app/data/app.db -o restored.db
```

Restores the database to a specified point in time or the latest backup.

### Data Seeding and Reset

Option B uses the same SQL-based seeding as Option A:
- Write numbered `.sql` files in `migrations/` and `data/seeds/`.
- Create a simple `apply_migrations.py` script that runs all pending migrations at startup.
- To reset for testing, delete the SQLite file and re-run migrations + seed scripts.

Example bootstrap script:
```python
import sqlite3
import glob

db = sqlite3.connect('app.db')
for migration_file in sorted(glob.glob('migrations/*.sql')):
    with open(migration_file) as f:
        db.executescript(f.read())
db.commit()
```

This is simpler than Alembic for a small project; Alembic adds complexity without benefit at this scale.

### Schema Migration Tooling

For Option B, a **simple numbered SQL script approach** is sufficient and preferable to Alembic:

#### Simple Approach (Recommended)
- Store migrations as numbered `.sql` files: `migrations/001_create_tables.sql`, `migrations/002_add_indexes.sql`, etc.
- Track applied migrations in a `migrations` table (app-managed).
- Run a simple Python script at startup to apply all unapplied migrations.

**Advantages**:
- No ORM dependency. Plain SQL is portable and reviewable.
- Matches E-003's existing pattern.
- Minimal bootstrap code.

#### Alembic Approach (Not Recommended for This Scale)
Alembic would be useful if:
- Using SQLAlchemy ORM extensively and needing auto-generated migrations.
- Complex schema changes requiring rollback/downgrade support.
- Large team with strict schema governance.

Baseball-crawl doesn't need these; the project is small, schema is stable, and manual SQL is fine.

**Decision**: Simple numbered SQL scripts + a bootstrap script. No Alembic.

### Recommendation for Option B

**Use SQLite in a Docker volume for Option B**, configured for WAL mode, backed up with Litestream. The pattern is simple, well-tested, and proven by Fly.io, 37signals (Rails camp), and other 2026 deployments of small-scale applications.

---

## Cross-Path Considerations

### Migration Between Option A and Option B

**Both use SQLite SQL syntax.** The schema, migrations, and queries written for Option A (D1) transfer directly to Option B (Docker SQLite) with **no changes to the SQL itself**.

What changes:
- **Language runtime**: TypeScript/JavaScript (Option A) → Python (Option B)
- **Database binding**: Cloudflare D1 bindings → `sqlite3` module
- **Deployment target**: `wrangler deploy` → `docker compose up`

The SQL migrations in `migrations/` are reusable. If Option A is chosen initially and later switched to Option B (unlikely, but possible), the schema is portable.

### Backup and Restore Comparison

| Aspect | Option A (D1) | Option B (SQLite + Litestream) |
|--------|---------------|---------------------------------|
| Automatic backups | Yes, Cloudflare-managed | Yes, Litestream to S3/SFTP |
| Point-in-time restore | Yes, Cloudflare dashboard | Yes, Litestream restore command |
| Cost | Included | $0-5/month for S3 (minimal usage) |
| Operational overhead | None | Minimal (one Litestream container) |
| Local backup | Export via CLI | Simple file copy |

Both approaches are production-ready.

---

## Testing Recommendations

### Option A Testing Checklist

- [ ] Verify `wrangler dev` local data persists across dev sessions.
- [ ] Confirm D1 migrations apply cleanly locally and produce identical schema in production.
- [ ] Test a sample FastAPI-style endpoint locally (via `wrangler dev`), confirm query latency is acceptable.
- [ ] Verify that seeding test data via SQL migrations works as expected.
- [ ] Test `wrangler d1 export` to confirm backup export mechanism.

### Option B Testing Checklist

- [ ] Run FastAPI with SQLite + WAL mode locally in Docker Compose.
- [ ] Verify `run_in_threadpool` database queries don't block the event loop (measure P50/P99 latencies under concurrent load).
- [ ] Confirm SQLite WAL checkpoints complete normally (check WAL file size doesn't grow unbounded).
- [ ] Test Litestream replication to a local MinIO instance.
- [ ] Verify `litestream restore` recovers a backup cleanly.
- [ ] Confirm migrations apply cleanly in a fresh Docker container (startup bootstrap).

---

## Open Questions and Follow-Up Research

1. **Option A: TypeScript capability for serving layer**: Does the team have TypeScript expertise, or is learning required? R-02 should address API layer choices for Option A.

2. **Option B: VPS provider and sizing**: What is the minimum viable VPS (CPU, RAM, storage) for Option B? Hetzner CX11 (~$4/month, 2 vCPU, 2 GB RAM, 40 GB storage) is the likely answer, but R-04 should confirm for this specific workload.

3. **Option B: Service-to-service auth with Cloudflare Access**: The Python crawlers must authenticate to the API in production (Option B). Do they use service tokens in the `Authorization: Bearer` header? Cloudflare Access setup details are for R-04.

4. **Local vs. production data alignment**: For both options, is there a test that verifies local development schema matches production? (Schema validation test recommended for E-009-02 or E-009-03.)

5. **Monitoring and observability**: Neither option has been evaluated for logging, metrics, or health checks. That's likely E-009-02/03 scope or a future E-010 epic.

---

## Sources and References

### Cloudflare D1 Documentation
- [Cloudflare D1 Limits](https://developers.cloudflare.com/d1/platform/limits/)
- [Cloudflare D1 Local Development](https://developers.cloudflare.com/d1/best-practices/local-development/)
- [Cloudflare D1 Migrations](https://developers.cloudflare.com/d1/reference/migrations/)
- [Cloudflare D1 FAQs](https://developers.cloudflare.com/d1/reference/faq/)

### SQLite and Concurrency
- [SQLite Write-Ahead Logging (WAL)](https://sqlite.org/wal.html)
- [SQLite Threadsafe Mode](https://sqlite.org/threadsafe.html)
- [Charles Leifer: Going Fast with SQLite and Python](https://charlesleifer.com/blog/going-fast-with-sqlite-and-python/)
- [SQLite Concurrency: Thread Safety, WAL Mode, and Beyond](https://iifx.dev/en/articles/17373144)

### FastAPI and Concurrency
- [FastAPI: Concurrency and async/await](https://fastapi.tiangolo.com/async/)
- [How to Use Async Database Connections in FastAPI](https://oneuptime.com/blog/post/2026-02-02-fastapi-async-database/view)
- [FastAPI: Thread Pool and Event Loop](https://medium.com/@saveriomazza/fastapi-thread-pool-and-event-loop-97242f98c506)
- [Sentry: FastAPI run_in_executor vs run_in_threadpool](https://sentry.io/answers/fastapi-difference-between-run-in-executor-and-run-in-threadpool/)

### Litestream and Backup
- [Litestream Getting Started](https://litestream.io/getting-started/)
- [Litestream Docker Guide](https://litestream.io/guides/docker/)
- [Going Production-Ready with SQLite: How Litestream Makes It Possible](https://medium.com/@cosmicray001/going-production-ready-with-sqlite-how-litestream-makes-it-possible-74f894fc96f0)
- [GitHub: Litestream](https://github.com/benbjohnson/litestream)

### Schema Migration Tools
- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [Alembic PyPI](https://pypi.org/project/alembic/)
- [Choosing the Right Schema Migration Tool](https://www.pingcap.com/article/choosing-the-right-schema-migration-tool-a-comparative-guide/)

### Database Comparisons
- [SQLite vs PostgreSQL: Key Differences](https://airbyte.com/data-engineering-resources/sqlite-vs-postgresql)
- [SQLite in Docker: A Comprehensive Guide](https://tutorial.sejarahperang.com/2026/02/sqlite-in-docker-comprehensive-guide.html)
- [PostgreSQL vs. MariaDB vs. SQLite: A Performance Test](https://deployn.de/en/blog/db-performance/)

---

## Author Notes

This research confirms the product manager's prior for Option B (SQLite in Docker) as viable and appropriate for baseball-crawl's scale. Option A (Cloudflare D1) is equally viable and removes operational overhead entirely. The key difference is deployment environment (managed vs. self-hosted) and serving-layer language (TypeScript vs. Python), not the database layer itself.

Both options are production-ready. The choice should be made in E-009-01 based on team preference (zero-ops cloud vs. proven on-premise pattern with full source control), not on database capability constraints.
