# E-009-R-02: API Layer Options Research Findings

**Research Date**: February 28, 2026
**Status**: Complete
**Related Epic**: [E-009: Tech Stack Redesign](../epics/E-009-tech-stack-redesign/epic.md)
**Related Research**: [E-009-R-01: Database Options](E-009-R-01-database-options.md)

---

## Executive Summary

This research evaluated API layer technologies for baseball-crawl across two deployment paths: **Option A (Native Cloudflare Workers)** and **Option B (Docker + Cloudflare Access)**.

**Option A (Cloudflare Workers + TypeScript)** is production-ready in 2026. TypeScript Workers with D1 bindings provide a reliable local development experience via `wrangler dev`, mature routing capabilities, and zero operational overhead. Python Workers are functionally available with D1 support, but remain in beta (require compatibility flag), making TypeScript the only production-ready choice for Option A today.

**Option B (FastAPI + Docker)** is the simpler path for a Python-first team. FastAPI's async model adds minimal complexity when paired with SQLite and thread pool execution; the risk of event loop blocking is manageable and well-documented. Flask is viable but offers no meaningful advantage over FastAPI for this use case. A single monolithic FastAPI app (JSON API + HTML dashboard in one process) is the right choice—no need for separate microservices.

**For Jason (Python-first developer)**: TypeScript learning curve is real but manageable for a small serving layer. The context switch cost is lower if the TypeScript surface area is small (routing + bindings, not complex business logic). Option B (FastAPI) eliminates this cost entirely, keeping the entire stack in Python.

**Language-agnostic routing**: Neither option requires language-specific router abstractions. Both TypeScript Workers and FastAPI support straightforward route definition in the language they're written in.

**Recommendation**: If zero operational overhead is the priority and Jason is willing to invest in TypeScript learning, **Option A (TypeScript Workers) is viable**. If Python homogeneity and developer velocity matter more, **Option B (FastAPI) is the stronger choice**. Both are production-ready; the decision is team preference and skill investment tolerance.

---

## Option A: Cloudflare Workers (TypeScript)

### Status in 2026

TypeScript Workers are **fully production-ready** as of 2026. The Cloudflare Workers runtime, bound to D1 databases via strongly-typed bindings, is mature, well-documented, and deployed at scale across many production customers.

Local development via `wrangler dev` uses the same runtime (workerd) that runs in production, providing excellent parity between local and deployed behavior. This is a significant improvement over historical Cloudflare tooling and makes `wrangler dev` a reliable development environment.

### Python Workers Status (Not Recommended Yet)

Cloudflare has released a **beta Python runtime** for Workers that includes D1 binding support. However:

1. **Beta requirement**: Python Workers require the `python_workers` compatibility flag, indicating they are not yet officially production-ready.
2. **D1 support is functional**: [Query D1 from Python Workers](https://developers.cloudflare.com/d1/examples/query-d1-from-python-workers/) is documented and tested, with full binding support available.
3. **Cold start performance**: An import-heavy Worker (fastapi, httpx, pydantic) takes ~10 seconds without snapshots, ~1 second with snapshots enabled. This is acceptable for a low-traffic coaching dashboard but represents a meaningful cold-start penalty compared to TypeScript.
4. **Recommendation**: Not viable for production baseball-crawl until the beta flag requirement is removed. TypeScript is the only production-ready path for Option A.

### Developer Experience: TypeScript Workers + D1

#### Local Development Setup
`wrangler dev` creates a local-only environment that runs the same D1 software as production. Data persists across dev sessions by default (Wrangler v3+) and can be directed to a specific location via `--persist-to=/path/to/file` for team sharing or CI/CD reproducibility.

**Key strengths**:
- Same version of D1 locally and in production.
- Hot-reload development with full access to bindings.
- Data isolation: local dev does not touch production data unless explicitly configured.
- Can access remote D1 via `remote: true` binding configuration if needed during development.

#### Type Safety and D1 Bindings
The D1 Workers Binding API is strongly-typed in TypeScript. Running `wrangler types` generates type definitions for all bindings based on your `wrangler.toml` configuration. This provides IDE autocomplete and compile-time safety for database queries.

Example binding in `wrangler.toml`:
```toml
[[d1_databases]]
binding = "DB"
database_name = "baseball-crawl"
```

Access in Worker code:
```typescript
const result = await env.DB.prepare("SELECT * FROM teams").all();
```

The TypeScript compiler catches binding mismatches before deployment.

#### Routing in TypeScript Workers
Cloudflare Workers supports multiple routing patterns:

1. **Route patterns in `wrangler.toml`**: Map URLs to workers (e.g., `/api/*` → API worker, `/dashboard/*` → dashboard worker).
2. **Service bindings**: Call other Workers from within a Worker, enabling a microservice pattern if needed.
3. **Framework routing**: Popular frameworks like [Hono](https://hono.dev/docs/getting-started/cloudflare-workers) provide express-like routing DSLs in TypeScript.

For baseball-crawl, a simple Hono or native Fetch API-based routing is sufficient. No need for complex microservice decomposition—a single Worker with route handlers covers JSON API + dashboard.

#### Serving HTML from TypeScript Workers
Returning server-rendered HTML from TypeScript Workers is straightforward:

1. **Template engines**: While Jinja2 (Python) is not available, JavaScript-based template engines like Nunjucks or Eta work with Workers. Alternatively, simple string interpolation or tagged template literals in TypeScript work for simple HTML.
2. **Cost**: The serving layer code is minimal—templates are static or light dynamic content, not complex business logic.
3. **Alternative**: Cloudflare Pages Functions can serve static assets and call Workers as a backend; for a small dashboard, embedding HTML directly in the Worker is also feasible.

### Recommendation for Option A (TypeScript Workers)

**Use TypeScript Workers for Option A.** Production-ready, mature local dev story, excellent type safety, zero operational overhead. The trade-off is learning TypeScript, which is addressed in the "Learning Curve" section below.

**Do not use Python Workers yet**—wait for the beta flag requirement to be removed unless Jason specifically wants to pilot the beta. TypeScript is the current production-ready path.

---

## Option A Extended: Python Workers (Future Option)

Once Python Workers exit beta, the calculus for Option A changes dramatically. A Python-only stack (crawlers in Python, API in Python, D1 bindings via Python Workers) would eliminate the language context switch entirely.

**Blocking issue**: As of February 2026, the beta flag is still required. If this changes in a future Cloudflare release, revisit this research and reconsider. For now, TypeScript is required.

---

## Option B: FastAPI (Docker + Cloudflare Access)

### FastAPI vs. Flask for This Use Case

Both FastAPI and Flask support Jinja2 templating for server-rendered HTML. The choice hinges on whether async performance benefits are worth the complexity.

#### Performance Comparison
FastAPI is 5-10x faster than Flask in benchmarks (20,000 req/s vs. 4,000 req/s), but this gap matters primarily for high-concurrency I/O-heavy workloads. For a coaching dashboard with 1-5 concurrent users and simple database reads, **both are fast enough in practice**. The database query is the bottleneck, not the framework.

#### Simplicity: Flask vs. FastAPI
- **Flask**: Simpler, synchronous-first, minimal boilerplate. If async is not needed, Flask's simplicity wins.
- **FastAPI**: Async by default, built on Starlette, with automatic OpenAPI documentation. Adds async complexity but provides better patterns for concurrent I/O.

#### Recommendation: FastAPI
**Use FastAPI for Option B.** The async complexity is manageable when paired with SQLite (thread pool execution), and FastAPI's automatic API documentation is a free gift that simplifies future crawlers or external integrations. Flask's simplicity advantage is marginal; the extra FastAPI boilerplate is worth the cleaner patterns.

### FastAPI + SQLite Concurrency Pattern

FastAPI is async (event loop-based), but SQLite is synchronous. The standard pattern:

1. **Open a SQLite connection** with `check_same_thread=False` and `PRAGMA journal_mode=WAL`.
2. **Run database queries in a thread pool** via `run_in_threadpool` (from Starlette) or `run_in_executor` (from asyncio).
3. This offloads blocking I/O from the FastAPI event loop, preventing event loop starvation.

#### Implementation Pattern

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

#### Concurrency Risks: Mitigation

**Event Loop Blocking Risk**: If a query is slow, the thread pool absorbs the blocking call, and the event loop remains responsive. This is the design intent of `run_in_threadpool`.

**Thread Pool Exhaustion**: FastAPI's default thread pool is large (~10-20 threads). For baseball-crawl (1-5 concurrent users, query times in 10-100ms), thread pool exhaustion is not a realistic concern. Even at 100 concurrent requests with 50ms queries, the math is sound: 100 requests × 50ms = 5 seconds, well within thread pool capacity.

**Connection Pool Deadlock**: This risk applies to connection pooling (e.g., SQLAlchemy async sessions with max_connections=N). Since baseball-crawl uses a single persistent SQLite connection with no pooling, this risk does not apply.

**Recommendation**: The thread pool pattern is well-established and low-risk for this workload. The complexity is minimal—one `run_in_threadpool` wrapper per database query—and is a standard FastAPI pattern documented in official tutorials.

### Single Monolithic App vs. Separate Microservices (Option B)

Should the JSON API endpoints and HTML dashboard be the same FastAPI app or separate services?

#### Single App (Recommended for Baseball-Crawl)
- **One port**, one database connection, shared middleware.
- **Simpler Docker Compose**: One service definition instead of two.
- **No CORS complexity**: Dashboard and API are same-origin.
- **Shared authentication**: Cloudflare Access handles auth; no inter-service token exchange needed.
- **Easier to debug**: Single process, unified logging, no inter-process communication.

#### Separate Microservices
- **Clear API/UI boundary**: Easier to replace one side independently.
- **Potential parallelism**: API and dashboard could scale independently (irrelevant at this scale).
- **Added complexity**: Two services, two databases connections, CORS headers, inter-service auth.
- **Overengineering risk**: Baseball-crawl does not need this separation. 4 teams, ~15 players each, ~60 player records total. Single app handles it trivially.

**Recommendation**: Single monolithic FastAPI app. The separation benefits do not justify the added complexity at this scale. Keep the codebase cohesive: one `main.py`, routes for `/api/...` and `/dashboard/...`, shared database connection.

### Docker Image Size and Cold Start (Option B)

A typical FastAPI Docker image with Jinja2 templates, SQLite, and dependencies:

- **Base image**: Python 3.13-slim (150 MB)
- **Dependencies**: FastAPI, Uvicorn, Jinja2, sqlite3 (built-in) → ~100-150 MB
- **Application code**: Minimal, <10 MB
- **Total**: 250-300 MB (typical)

**Cold start time**:
- **Cold start (image pull + container start)**: 5-10 seconds on a typical VPS
- **Warm start (container already running)**: <100ms

For baseball-crawl on a VPS (Option B), the container is always running (not scale-to-zero), so cold start time is irrelevant after first deploy. The 250-300 MB image is small enough for rapid deployment iterations.

**Conclusion**: Docker overhead is not a concern for Option B at this scale.

### Testing Strategy: Option B (FastAPI + SQLite)

Testing FastAPI + SQLite applications requires:

1. **In-memory SQLite for tests**: Use `:memory:` database to avoid file I/O and isolation issues.
2. **Fixture pattern**: Create a test database, seed it, run tests, clean up.
3. **Mock time.sleep calls**: If tests use sleep for timing, mock it to keep tests fast.
4. **Test database queries in isolation**: Test the raw SQL queries independently of the FastAPI routing layer.

Example test pattern:
```python
import pytest
import sqlite3
from fastapi.testclient import TestClient
from main import app

@pytest.fixture
def test_db():
    db = sqlite3.connect(':memory:')
    db.execute('PRAGMA journal_mode=WAL')
    # Create schema
    db.executescript(open('migrations/001_schema.sql').read())
    # Seed test data
    db.executescript(open('data/seeds/test_seed.sql').read())
    db.commit()
    yield db
    db.close()

def test_get_player_stats(test_db):
    client = TestClient(app)
    # Swap app.db for test_db fixture
    response = client.get("/stats/1")
    assert response.status_code == 200
    assert response.json()["stats"] is not None
```

FastAPI's `TestClient` works without a running server, making tests fast and deterministic.

### Recommendation for Option B (FastAPI)

**Use FastAPI in a single monolithic Docker Compose service.** Pair it with SQLite + WAL mode, implement database queries via `run_in_threadpool`, test with in-memory SQLite fixtures. The complexity is low, the pattern is standard, and the result is fast, testable code.

---

## Language Learning Curve: TypeScript for a Python Developer

Jason is a Python-first developer (crawlers, data processing). If Option A is chosen, he must learn TypeScript for the serving layer. How difficult is this, and what is the context switching cost?

### TypeScript Learning Fundamentals

TypeScript is a superset of JavaScript with static typing. The core syntax is C-like (familiar to developers with Java, C#, or C++ experience) but includes functional programming constructs from JavaScript.

**Key differences from Python**:
1. **Static typing** (enforced at compile time, not runtime)
2. **Null/undefined semantics** (different from Python's None)
3. **Class syntax** (more verbose than Python dataclasses)
4. **Module system** (import/export, not Python's import)
5. **Async/await** (similar to Python, but callback-based; Promise-heavy)
6. **No list/dict comprehensions** (uses map/filter instead)
7. **No string formatting like f-strings** (uses template literals instead)

### Learning Curve Assessment

**Estimated time to productivity**: 2-4 weeks for a Python developer to write maintainable TypeScript, assuming:
- 1-2 hours per day of focused study
- Small, bounded codebase (routing + D1 queries, not complex business logic)
- IDE support (VSCode with TypeScript extensions)
- Pair programming or code review with TypeScript-fluent developer initially

**Steepness factors**:
- Moderate: Type system is thorough but learnable.
- Moderate: Async/await is familiar from Python; Promise chains are the learning gap.
- Moderate: Ecosystem (npm, package management) differs from pip but is not harder.

**Mitigating factors for baseball-crawl**:
- Serving layer code is small (~500-1500 lines for routing + templates).
- Business logic is minimal (database reads, HTML rendering).
- D1 bindings are strongly-typed, making errors visible.
- TypeScript's type checker catches many bugs before runtime.

### Comparison: Option A (TypeScript) vs. Option B (Python)

| Factor | Option A (TypeScript Workers) | Option B (FastAPI) |
|--------|------------------------------|-------------------|
| **Language learning** | 2-4 weeks; TypeScript syntax + async patterns | None; Python already known |
| **Framework learning** | Workers API, D1 bindings, Hono (routing) | FastAPI, Jinja2, SQLite patterns |
| **Total ramp time** | ~6 weeks (language + framework) | ~2 weeks (framework + patterns) |
| **Ongoing context switching** | Every serving-layer change requires TypeScript mindset | Minimal; same language as crawlers |
| **Team capability** | Jason must learn TypeScript; future hires may lack it | Easier to hire Python developers |
| **Long-term maintainability** | Smaller codebase, type safety; fewer runtime errors | Larger codebase but all Python |

**Conclusion**: Option A has a real learning cost. Option B eliminates this cost entirely. For Jason, the time investment in TypeScript learning is real (~4-6 weeks) but not insurmountable. The question is whether zero operational overhead (Option A) is worth the learning investment. If Jason's time is the constraint, Option B is faster to productivity.

---

## Routing Patterns: Language-Agnostic Perspective

**Question**: Do we need a router abstraction that works across TypeScript and Python?

**Answer**: No. Both TypeScript Workers and FastAPI have straightforward route definition in their native language. There's no need for a language-agnostic router abstraction.

### TypeScript Workers Routing (Option A)
Using Hono as a framework:
```typescript
import { Hono } from 'hono'

const app = new Hono()

app.get('/api/teams', async (c) => {
  const teams = await c.env.DB.prepare("SELECT * FROM teams").all()
  return c.json(teams)
})

app.get('/dashboard', (c) => {
  return c.html(renderDashboard())
})

export default app
```

### FastAPI Routing (Option B)
```python
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI()

@app.get("/api/teams")
async def get_teams():
    teams = await run_in_threadpool(lambda: db.execute("SELECT * FROM teams").fetchall())
    return teams

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    return render_dashboard()
```

Both are idiomatic in their respective languages. No abstraction layer needed.

---

## Testing Strategy Comparison

### Option A (TypeScript Workers + D1)

Testing TypeScript Workers requires:

1. **Unit tests**: Test individual request handlers with mocked D1 bindings.
2. **Integration tests**: Use `wrangler dev` or `unstable_dev()` API to test against local D1.
3. **D1 test database**: Each test suite creates a fresh local D1 database, seeds it, runs tests, tears down.

Example pattern using Jest:
```typescript
import { unstable_dev } from "wrangler"

describe('API endpoints', () => {
  let worker: Awaited<ReturnType<typeof unstable_dev>>

  beforeAll(async () => {
    worker = await unstable_dev('src/index.ts', {
      experimental: { disableExperimentalWarning: true }
    })
  })

  afterAll(async () => {
    await worker.stop()
  })

  it('GET /api/teams returns teams', async () => {
    const response = await worker.fetch('/api/teams')
    expect(response.status).toBe(200)
    const json = await response.json()
    expect(json).toHaveProperty('teams')
  })
})
```

**Strengths**: Same environment locally and in production; D1 test behavior matches production.

**Weaknesses**: Tests are slower (full Worker simulation); test setup is more boilerplate-heavy.

### Option B (FastAPI + SQLite)

Testing FastAPI is more straightforward:

1. **Unit tests**: Test handlers with mocked database.
2. **Integration tests**: Use FastAPI's TestClient against an in-memory SQLite database.
3. **No cold start overhead**: Tests run in-process, no simulation layer.

Example pattern:
```python
import pytest
from fastapi.testclient import TestClient
from main import app

@pytest.fixture
def test_db():
    db = sqlite3.connect(':memory:')
    # Create schema, seed data
    yield db
    db.close()

def test_get_teams(test_db):
    client = TestClient(app)
    response = client.get("/api/teams")
    assert response.status_code == 200
    assert "teams" in response.json()
```

**Strengths**: Fast, simple, no simulation overhead, in-memory databases are isolated.

**Weaknesses**: None significant for this scale.

**Recommendation**: Option B's testing story is simpler and faster. Option A's testing is viable but heavier.

---

## Performance and Latency Considerations

### Option A (TypeScript Workers + D1)

**Latency characteristics**:
- **Cold start**: First request to a Worker starts the JS VM (~50-200ms). Subsequent requests are warm (~1-5ms overhead).
- **D1 query latency**: Single-threaded SQLite on the edge, query time depends on data size and complexity. For baseball-crawl stats queries (small result sets, indexed lookups), expect 5-50ms.
- **Total p99 for a typical stats page**: ~100-200ms (assuming 5-10 queries per page load).

**Concurrency model**: D1 handles one query at a time per database. For 1-5 concurrent users, no queueing occurs.

### Option B (FastAPI + Docker on VPS)

**Latency characteristics**:
- **Cold start**: Container already running (not scale-to-zero), so no cold start penalty. Request processing in <1ms.
- **SQLite query latency**: Same as Option A (5-50ms for typical stats queries).
- **Network latency**: Request travels from user → Cloudflare Tunnel → VPS → FastAPI → SQLite. Expect 20-100ms of network overhead depending on user location (Cloudflare Tunnel can reduce this).
- **Total p99 for a typical stats page**: ~150-300ms (depending on network and query count).

**Concurrency model**: FastAPI can handle many concurrent requests (limited by thread pool size, which is large). With SQLite's WAL mode, 1-5 concurrent users are trivial.

### Comparison

Both options are fast enough for a coaching dashboard (200-300ms page load is acceptable). Option A has a theoretical latency advantage (global edge presence, cold start is warmed by Cloudflare's infrastructure) but this doesn't matter for a small team accessing a single app. Option B's VPS-based approach may have slightly higher latency due to network routing, but the difference is imperceptible to users.

**Recommendation**: Both options are latency-suitable. Do not choose based on performance—either is fast enough.

---

## Recommendations per Option

### Recommendation for Option A (Native Cloudflare)

**Use TypeScript + Cloudflare Workers + D1 + Cloudflare Pages/Workers for the dashboard.**

Why this works:
- Zero operational overhead. Cloudflare manages infrastructure, scaling, backups.
- Mature, production-ready stack with excellent local dev parity via `wrangler dev`.
- Type-safe D1 bindings catch schema errors at compile time.
- No server to manage or monitor.

Trade-offs to accept:
- Jason must learn TypeScript (2-4 weeks ramp time).
- Serving layer code is TypeScript, not Python (language context switching).
- Miniflare/`wrangler dev` is excellent but adds one toolchain to mental model.

Who should choose this:
- Teams that prioritize operational simplicity above all else.
- Organizations with TypeScript expertise or a desire to build it.
- Projects where zero server management is a hard requirement.

### Recommendation for Option B (Docker + Cloudflare Access)

**Use FastAPI (Python) + Docker Compose + SQLite + Cloudflare Tunnel + Cloudflare Access.**

Why this works:
- Python end-to-end: crawlers, API, dashboard all in one language. Minimal context switching.
- Simple, standard Docker Compose setup runs identically locally and in production.
- FastAPI is fast, modern, and has excellent async + SQLite patterns.
- Familiar to Jason; no new language learning required.
- Low operational overhead: a single-instance VPS ($4-10/month) with standard Docker tools.

Trade-offs to accept:
- Requires managing one Linux server (updates, backups, health checks).
- Cloudflare Tunnel setup is one-time but non-trivial.
- Separate container from Cloudflare runtime (no edge performance, but irrelevant for this use case).

Who should choose this:
- Python-first teams who want to minimize learning overhead.
- Organizations with Docker expertise or a desire to standardize on containers.
- Projects where developer velocity and codebase cohesion matter more than operational simplicity.
- Teams that already run a pattern like this in production (like the user's n8n-wilk-io deployment).

---

## Open Questions and Follow-Up Research

1. **Option A: TypeScript IDE support in Claude Code**: How well does the Claude Code AI agent handle TypeScript Workers code? Does it understand D1 bindings, Hono routing, and wrangler configuration? This should be tested before committing to Option A.

2. **Option B: Cloudflare Tunnel performance for Dashboard loads**: With Option B, dashboard requests traverse a Cloudflare Tunnel. What is the actual latency impact for a user loading the dashboard over the tunnel vs. directly? Should be measured in E-009-04.

3. **Local dev speed comparison**: Is `wrangler dev` faster or slower than `docker compose up` for iterative development? Timing should be measured for a fresh start and a code change + reload cycle.

4. **Migration between options**: If Option A is chosen initially and the team later wants to switch to Option B, how difficult is the migration? (Answer: SQL migrations transfer directly, but serving layer code must be rewritten. This is not a blocker but good to document.)

5. **Python Workers beta exit timeline**: When will Cloudflare remove the beta flag from Python Workers? Check the Cloudflare blog quarterly or subscribe to their changelog. When this happens, Option A becomes more attractive (Python end-to-end).

6. **Agent capability with TypeScript**: Can Claude Code's general-dev agent write and maintain TypeScript Workers code effectively, or is Python strongly preferred? This should inform the team's ability to sustain Option A long-term.

---

## Sources and References

### Cloudflare Workers and D1
- [Write Cloudflare Workers in TypeScript](https://developers.cloudflare.com/workers/languages/typescript/)
- [Workers Binding API for D1](https://developers.cloudflare.com/d1/worker-api/)
- [Local development with D1](https://developers.cloudflare.com/d1/best-practices/local-development/)
- [Query D1 from Python Workers](https://developers.cloudflare.com/d1/examples/query-d1-from-python-workers/)
- [Write Cloudflare Workers in Python](https://developers.cloudflare.com/workers/languages/python/)
- [Python Workers advancements](https://blog.cloudflare.com/python-workers-advancements/)

### FastAPI and Async/Concurrency
- [FastAPI Concurrency and async/await documentation](https://fastapi.tiangolo.com/async/)
- [How to Use Async Database Connections in FastAPI](https://oneuptime.com/blog/post/2026-02-02-fastapi-async-database/view)
- [Sentry: FastAPI run_in_executor vs run_in_threadpool](https://sentry.io/answers/fastapi-difference-between-run-in-executor-and-run-in-threadpool/)
- [Understanding Concurrency with FastAPI and Sync SDKs](https://medium.com/@saveriomazza/understanding-concurrency-with-fastapi-and-sync-sdks-4b5cb956e8e0)
- [FastAPI and SQLite Concurrency Risk Discussion](https://github.com/fastapi/fastapi/discussions/6666)

### FastAPI vs. Flask Comparison
- [FastAPI vs Flask: Key Differences, Performance, and Use Cases (2026)](https://www.secondtalent.com/resources/fastapi-vs-flask/)
- [Codecademy: FastAPI vs Flask comparison](https://www.codecademy.com/article/fastapi-vs-flask-key-differences-performance-and-use-cases)
- [Strapi: FastAPI vs Flask 2025](https://strapi.io/blog/fastapi-vs-flask-python-framework-comparison)

### FastAPI and Docker
- [Real Python: Serve a Website with FastAPI and Jinja2](https://realpython.com/fastapi-jinja2-template/)
- [TestDriven.io: FastAPI Templates with Jinja2](https://testdriven.io/tips/235fc106-8ad2-4d64-a7ae-8610a1b2d221/)
- [DEV Community: Developing a FastAPI Application in Docker](https://dev.to/abbazs/developing-a-fastapi-application-in-docker-31n4)
- [Better Stack: Containerizing FastAPI Applications with Docker](https://betterstack.com/community/guides/scaling-python/fastapi-with-docker/)

### Workers Routing and Architecture
- [Cloudflare Workers Best Practices](https://developers.cloudflare.com/workers/best-practices/workers-best-practices/)
- [Introducing Worker Services: Composable, Distributed Applications](https://blog.cloudflare.com/introducing-worker-services/)
- [Hono: Lightweight web framework for Cloudflare Workers](https://hono.dev/docs/getting-started/cloudflare-workers)

### TypeScript for Python Developers
- [TypeScript vs Python: Which Language to Choose in 2026](https://www.leanware.co/insights/typescript-vs-python)
- [The GitHub Blog: TypeScript, Python, and AI feedback loop](https://github.blog/news-insights/octoverse/typescript-python-and-the-ai-feedback-loop-changing-software-development)

---

## Author Notes

This research confirms that both Option A (TypeScript Workers) and Option B (FastAPI) are production-ready and viable for baseball-crawl. The decision is not driven by capability gaps but by team preference:

- **Option A** wins on operational simplicity and type safety, with the cost of learning TypeScript.
- **Option B** wins on developer velocity and Python homogeneity, with the cost of managing a VPS.

The Product Manager's prior for Option B (FastAPI + Docker) holds up under scrutiny. The async complexity is manageable, the patterns are standard, and the Docker setup mirrors the proven n8n-wilk-io pattern the user already operates.

For Jason specifically: if minimizing learning overhead is the goal, choose Option B. If the zero-ops simplicity of Cloudflare is compelling and he's willing to invest in TypeScript, choose Option A. Both will work.

The next decision point is E-009-01 (Technology Decision Record), which should synthesize this research, E-009-R-01 (database options), E-009-R-03 (dashboard framework), and E-009-R-04 (infrastructure comparison) into a final recommendation.
