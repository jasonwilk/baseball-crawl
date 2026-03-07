# Deep Research: API Documentation Format for GameChanger API

**Date:** 2026-03-07
**Context:** ~88 reverse-engineered endpoints currently in a single 8,100-line markdown file. Three documentation quality tiers. Need a format that serves both agents and humans.

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Evaluation Criteria](#evaluation-criteria)
3. [Option Analysis](#option-analysis)
   - [Option A: OpenAPI 3.1 + Redoc](#option-a-openapi-31--redoc)
   - [Option B: OpenAPI 3.1 + Swagger UI](#option-b-openapi-31--swagger-ui)
   - [Option C: Structured Markdown with YAML Frontmatter](#option-c-structured-markdown-with-yaml-frontmatter)
   - [Option D: MCP Server](#option-d-mcp-server)
   - [Option E: Stoplight / Mintlify / Hosted Platforms](#option-e-stoplight--mintlify--hosted-platforms)
   - [Option F: Hybrid -- OpenAPI + Markdown Extensions](#option-f-hybrid----openapi--markdown-extensions)
4. [Comparison Matrix](#comparison-matrix)
5. [OpenAPI Prototype -- Proving the Hard Cases](#openapi-prototype)
6. [MCP Assessment -- Complementary or Standalone?](#mcp-assessment)
7. [Recommendation](#recommendation)

---

## Executive Summary

After researching all options against the specific characteristics of this project -- a reverse-engineered API with partial documentation, free-text behavioral caveats, web/mobile profile differences, and agent-first consumption -- **structured markdown with YAML frontmatter (Option C) is the right choice, and it is already well underway via E-062.**

OpenAPI 3.1 with Redoc or Swagger UI was the most seriously considered alternative. It can technically represent most of what we need through vendor extensions (`x-*` fields) and markdown `description` fields. But the gap between "technically possible" and "natural fit" is large. The core tension: OpenAPI was designed for APIs you control and fully understand. This is an API we are reverse-engineering incrementally, where "we don't know yet" is a first-class documentation state.

An MCP server is a compelling complementary layer that could sit in front of the markdown files. It is not a replacement for the format choice, but it could dramatically improve agent access patterns if the per-file approach proves insufficient. Recommendation: build the markdown split first, evaluate whether agents struggle with file discovery, and add MCP only if they do.

---

## Evaluation Criteria

These come directly from the user's request, restated for clarity:

| # | Criterion | What It Means |
|---|-----------|---------------|
| 1 | **Agent usability** | How well can Claude Code agents consume this to write crawlers and parsers? Token efficiency -- can an agent load one endpoint without loading all 88? |
| 2 | **Zero information loss** | Can it capture everything in the monolith -- including caveats, partial status, behavioral notes, profile-specific quirks, "we don't know yet" states? |
| 3 | **Header/payload/response detail** | Can it document every header, response field, query param with full fidelity? Including vendor-typed Accept headers and per-endpoint header overrides? |
| 4 | **Web vs. mobile separation** | Can it cleanly separate profile-specific behavior per endpoint? Not just "which profile works" but "what differs"? |
| 5 | **Ecosystem fit** | Python-only, Docker Compose, "simple first" project. What dependencies does it add? Does it require npm/Node? |
| 6 | **Maintainability** | How hard is it to add a new endpoint? Update an existing one? Can agents (especially api-scout) maintain it? |
| 7 | **Searchability** | Can you find endpoints by tag, path, status? Without loading everything into context? |
| 8 | **Intuitiveness** | Is it obvious how to use? For both humans reading docs and agents consuming them programmatically? |

---

## Option Analysis

### Option A: OpenAPI 3.1 + Redoc

**What this is:** Write the API spec as an OpenAPI 3.1 YAML document (potentially split across multiple files using `$ref`). Render it as a browsable HTML doc using Redoc.

**How it handles the hard cases:**

*Partial/uncertain documentation:* OpenAPI has a `deprecated: true` field but no concept of "OBSERVED" or "PARTIAL" status. You would need vendor extensions: `x-status: OBSERVED`, `x-caveats: ["HTTP 500 without pagination params"]`. These are valid OpenAPI but invisible to Redoc unless you put them in the `description` field as markdown text. Redoc renders `description` fields as CommonMark, so the information is preservable -- but it lives in free-text, defeating the purpose of structured documentation.

*Free-text behavioral notes:* OpenAPI `description` fields support CommonMark markdown. You can put anything there. But "Known Limitations", "Key Observations", "Coaching Relevance" -- these are paragraphs of prose that sit awkwardly in a spec designed for request/response schemas. You end up with a YAML file where 60% of the content is multi-line markdown strings inside `description` fields.

*Web vs. mobile profiles:* OpenAPI has no native concept of "the same endpoint behaves differently depending on which client calls it." You could model this as:
- Two separate operations (clutters the spec, implies two different endpoints)
- Vendor extensions: `x-profiles: {web: {status: confirmed}, mobile: {status: unverified}}`
- Per-profile header parameters with `x-profile: web` metadata

None of these are natural. The OpenAPI spec assumes a single canonical behavior per operation.

*Vendor-typed Accept headers:* OpenAPI can document custom Accept headers as parameters or in the `requestBody` media type. The vendor media types (`application/vnd.gc.com.event:list+json; version=0.2.0`) are representable but require careful use of `content` negotiation fields.

*Cross-references (ID chains):* OpenAPI has `links` objects that can express "the response from operation A provides an ID used in operation B." This is actually a genuine strength -- it was designed for this. But the syntax is verbose and rarely used well in practice.

*Multi-file split:* OpenAPI supports `$ref` for splitting across files. Redocly CLI provides a `split` command. A per-endpoint file structure is achievable: one YAML file per path, `$ref`'d from a root `openapi.yaml`. However, agents would need to either (a) read the assembled spec, or (b) read individual YAML path files -- and YAML path files are less readable than markdown for humans.

**Redoc-specific vendor extensions:** Redoc supports `x-tagGroups` (menu organization), `x-codeSamples` (code snippets), `x-displayName` (tag labels), `x-logo`, `x-badges`, `x-enumDescriptions`. These help with presentation but don't solve the core "partial/uncertain documentation" problem.

**Rendering:** Redoc can produce a zero-dependency standalone HTML file via `redocly build-docs`. This HTML can be served by Python's `http.server` or the existing FastAPI app. But generating it requires `npm`/`npx` (Redocly CLI is a Node.js tool). Alternatively, a CDN-loaded `<script>` tag in a static HTML page can render the spec live, but this requires internet access.

**Pros:**
- Industry-standard format; anyone who has worked with APIs recognizes it
- The `links` feature genuinely handles cross-endpoint ID chains well
- Redoc produces beautiful, searchable, three-panel HTML documentation
- Schema validation tooling exists (openapi-spec-validator, Redocly CLI lint)
- Could generate Python client stubs (though we don't need this)

**Cons:**
- Requires npm/Node.js for Redoc CLI -- breaks the Python-only ecosystem
- "OBSERVED", "PARTIAL", "caveats" all live in vendor extensions or free-text descriptions -- structured in name only
- Web vs. mobile profiles have no natural representation
- YAML is noisier than markdown for the free-text-heavy content this API doc contains
- Maintaining YAML indentation for deeply nested schemas is error-prone
- Agents would consume raw YAML, which is less token-efficient than the equivalent markdown (YAML structural overhead: `operationId`, `responses.200.content.application/json.schema`, etc.)
- The spec assumes you know the API; it has no concept of "we haven't confirmed this yet"

**Token efficiency estimate:** A fully-documented endpoint in OpenAPI YAML would be roughly 1.5-2x the token count of the equivalent structured markdown, due to YAML structural boilerplate (`paths:`, `responses:`, `content:`, `schema:`, `properties:` nesting).

---

### Option B: OpenAPI 3.1 + Swagger UI

**What this is:** Same OpenAPI 3.1 spec as Option A, but rendered with Swagger UI instead of Redoc.

**Key differences from Redoc:**
- Swagger UI is interactive -- you can send requests from the browser (not useful for this project; the API requires captured `gc-token` credentials)
- Swagger UI has weaker rendering of long-form descriptions (no three-panel layout)
- Swagger UI is also Node.js based but has a Docker image available
- Swagger UI ignores most vendor extensions; it renders the standard spec only

**Assessment:** Everything said about Option A applies. Swagger UI is strictly worse for this use case -- it adds interactivity we don't need, renders free-text descriptions poorly, and ignores the vendor extensions we would need for partial/uncertain documentation. Redoc is the better renderer if going the OpenAPI route.

**Verdict:** Eliminated. If OpenAPI, use Redoc.

---

### Option C: Structured Markdown with YAML Frontmatter

**What this is:** Per-endpoint `.md` files in `docs/api/endpoints/`. Each file has YAML frontmatter (machine-parseable metadata: method, path, status, auth, profiles, tags, pagination, Accept header) and a markdown body (human/agent-readable prose: description, headers, response schema tables, examples, known limitations, caveats).

**This is what E-062 has already designed and prototyped.** The research spike (E-062-R-01) is DONE and produced three working prototypes covering all three documentation tiers.

**How it handles the hard cases:**

*Partial/uncertain documentation:* First-class. The `status` frontmatter field has five values: `CONFIRMED`, `OBSERVED`, `PARTIAL`, `UNTESTED`, `DEPRECATED`. The `caveats` array field captures blocking issues. Minimal endpoints are simply short files with sparse frontmatter -- no boilerplate required.

*Free-text behavioral notes:* This is markdown's home territory. "Known Limitations", "Key Observations", profile-specific behavioral notes, coaching relevance assessments -- all live naturally as markdown sections. No fighting with YAML indentation for multi-paragraph prose.

*Web vs. mobile profiles:* The frontmatter has `profiles.web.status`, `profiles.web.notes`, `profiles.mobile.status`, `profiles.mobile.notes`. The body has a "Headers (Web Profile)" section. This design was refined through the E-062-R-01 spike with input from api-scout.

*Vendor-typed Accept headers:* `accept` is a frontmatter field per endpoint. Simple, direct, no nesting.

*Cross-references:* `see_also` frontmatter array with `path` and `reason`. Inline markdown links in the body for narrative cross-references.

*Multi-file split:* This IS the multi-file split. Each endpoint is its own file. An index (`docs/api/README.md`) lists all endpoints with method, path, status, and auth.

**Prototype evidence (from E-062-R-01):**

The three prototypes at `.project/research/E-062-endpoint-prototypes/` demonstrate the format handles:
- A 231-line fully-documented endpoint with complex schema (schedule with polymorphic location objects)
- A compact 80-line confirmed endpoint with null Accept header
- A PARTIAL-status endpoint with HTTP 500 on web, 200 on mobile, suspected fix documented, and fallback strategy

**Pros:**
- Zero new dependencies. No npm, no Node, no new Python packages
- Markdown is the most token-efficient format for agents (no structural overhead)
- YAML frontmatter is machine-parseable (PyYAML is already in the dependency tree)
- Free-text notes, caveats, behavioral observations live naturally in markdown
- api-scout can update individual endpoint files without touching others
- Agents load only the files they need (~50-200 lines per endpoint vs. 8,100 lines for the monolith)
- Already prototyped and validated (E-062-R-01 DONE)
- Git-friendly: diffs show exactly which endpoint changed
- Humans can read the files directly without any rendering tool

**Cons:**
- No interactive HTML rendering (not needed for this project, but less visual than Redoc)
- No schema validation tooling (you can write invalid frontmatter and nothing catches it)
- Cross-endpoint search requires grep/glob or the index file, not a UI
- The index file must be maintained manually (or by a script) as endpoints are added
- Not an industry-standard format; new contributors would need to learn the frontmatter schema

**Token efficiency estimate:** An agent loading one fully-documented endpoint: ~500-800 tokens. Loading the index to find endpoints: ~300-500 tokens. vs. current monolith: ~30,000 tokens. That is a 97% reduction per query.

---

### Option D: MCP Server

**What this is:** A custom MCP (Model Context Protocol) server that exposes API documentation through structured tools. An agent could call tools like `lookup_endpoint(path="/teams/{team_id}/schedule")` or `search_endpoints(tag="schedule", status="CONFIRMED")` instead of reading files.

**How it would work:**

Using FastMCP (the dominant Python MCP framework, used by 70% of MCP servers), you would build a small server with tools like:

```python
@mcp.tool
def lookup_endpoint(path: str) -> str:
    """Look up documentation for a specific API endpoint by path."""
    # Read the corresponding markdown file, return its content

@mcp.tool
def search_endpoints(tag: str = None, status: str = None, auth: str = None) -> str:
    """Search for endpoints matching criteria. Returns a summary table."""
    # Parse frontmatter from all files, filter, return matches

@mcp.tool
def get_headers(profile: str = "web") -> str:
    """Get the canonical header set for a profile."""
    # Read headers.md, return profile-specific headers
```

**Key insight: MCP is a delivery mechanism, not a storage format.** The MCP server would read from whatever underlying format stores the documentation. It could read from markdown files, a SQLite database, or even an OpenAPI spec. The format question and the MCP question are orthogonal.

**With Claude Code's Tool Search feature,** MCP tools are loaded on-demand (deferred loading). The MCP server's tool definitions would consume minimal context until actually needed. An agent working on a crawler would search for "API endpoint lookup" and get the tool loaded dynamically.

**Pros:**
- Structured, typed access to documentation (no file path guessing)
- Built-in search without loading all files
- Could return exactly the fields an agent needs (e.g., just headers, just response schema)
- Python-native (FastMCP); fits the ecosystem
- Complements any storage format
- Could enforce consistency (validate frontmatter on write, not just read)

**Cons:**
- Another service to run (though it could be a stdio MCP server, no separate process needed)
- Adds `fastmcp` as a dependency
- Over-engineered for 88 endpoints? Grep + file read may be sufficient
- MCP servers require configuration in `.claude/settings.json`
- Agents already have file access tools (Read, Grep, Glob) that work on markdown files
- Building and maintaining the server is real work on top of the format migration

**Verdict:** Genuinely complementary. Not a replacement for the format choice. The question is whether it adds enough value over file-based access to justify the complexity. See the dedicated MCP assessment section below.

---

### Option E: Stoplight / Mintlify / Hosted Platforms

**What these are:**

**Stoplight Studio:** Visual OpenAPI editor with built-in docs, mocking, and Git integration. Pricing starts at $99/month. Requires an OpenAPI spec as input.

**Mintlify:** AI-native documentation platform with OpenAPI playground, AI assistant, MCP integration, and `/llms.txt` support. Pricing starts at $300/month. Hosted SaaS -- docs live on their infrastructure.

**Assessment for this project:**

These are both designed for companies publishing official API documentation for external developers. They solve problems we don't have:
- We don't need a public-facing developer portal
- We don't need interactive API playgrounds (the API requires captured credentials)
- We don't need team collaboration features or commenting
- We don't need AI writing assistants for docs (api-scout already maintains them)
- Monthly costs ($99-$300+) are unjustified for a high school baseball project

Both require OpenAPI specs as input, so they inherit all of Option A's problems with partial/uncertain documentation. They add a hosting dependency, a paid subscription, and vendor lock-in.

Mintlify's MCP integration and `/llms.txt` support are interesting in principle, but they solve the "make docs accessible to external AI tools" problem, not the "make our internal reverse-engineering notes machine-readable for our own agents" problem.

**Verdict:** Eliminated. Wrong tool for the job. These are for companies with API products, not for internal reverse-engineering documentation.

---

### Option F: Hybrid -- OpenAPI + Markdown Extensions

**What this is:** Maintain an OpenAPI spec for the structured parts (paths, methods, parameters, response schemas) and companion markdown files for the fuzzy parts (caveats, behavioral notes, profile quirks, investigation status).

**How it would work:**
```
docs/api/
  openapi.yaml           # Structured spec: paths, params, schemas
  endpoints/
    schedule.notes.md    # Free-text notes, caveats, profile quirks
    schedule.notes.md
    ...
```

An agent would load the OpenAPI entry for schema/parameter info and the companion markdown for behavioral context.

**Pros:**
- Gets the best of both worlds in theory
- Schema validation on the structured parts
- Free-form notes where they're natural

**Cons:**
- Two files per endpoint -- double the maintenance burden
- Information split across two formats requires knowing which file has what
- api-scout must update two files when documenting an endpoint
- Agents must load two files per endpoint query
- The boundary between "structured" and "fuzzy" is blurry and will shift over time
- Still requires npm for OpenAPI tooling/rendering
- Highest complexity of all options for the least clear benefit

**Verdict:** Over-engineered. The structured markdown with YAML frontmatter already captures both structured metadata and free-text notes in a single file. Splitting into two formats creates coordination overhead without proportional benefit.

---

## Comparison Matrix

| Criterion | A: OpenAPI+Redoc | B: OpenAPI+Swagger | C: Markdown+YAML FM | D: MCP Server | E: Hosted Platforms | F: Hybrid |
|-----------|:-:|:-:|:-:|:-:|:-:|:-:|
| **Agent usability** | Medium | Medium | **High** | **High** | Medium | Medium |
| **Zero info loss** | Medium | Medium | **High** | N/A (delivery) | Medium | High |
| **Header/payload detail** | **High** | **High** | **High** | **High** | **High** | **High** |
| **Web vs. mobile** | Low | Low | **High** | **High** | Low | Medium |
| **Ecosystem fit** | **Low** (npm) | **Low** (npm) | **High** (zero deps) | Medium (fastmcp) | **Low** (SaaS) | **Low** (npm) |
| **Maintainability** | Medium | Medium | **High** | Medium | Medium | Low |
| **Searchability** | **High** (UI) | **High** (UI) | Medium (grep/index) | **High** (tools) | **High** (UI) | Medium |
| **Intuitiveness** | **High** (visual) | Medium | **High** (readable) | Medium (tool API) | **High** (visual) | Low |
| **Token efficiency** | Low (YAML bloat) | Low (YAML bloat) | **High** | **High** | Low | Low |
| **Handles uncertainty** | Low | Low | **High** | **High** | Low | Medium |

**Scoring key:** High = strong fit, Medium = workable with effort, Low = poor fit or significant friction.

---

## OpenAPI Prototype -- Proving the Hard Cases

To be fair to OpenAPI, here is what three representative endpoints would look like. This demonstrates both what works and where it gets awkward.

### Fully Documented Endpoint (GET /teams/{team_id}/schedule)

```yaml
paths:
  /teams/{team_id}/schedule:
    get:
      operationId: getTeamSchedule
      summary: Full event schedule for a team
      description: |
        Returns all event types (games, practices, other) with optional venue
        enrichment. Response is a bare JSON array. No pagination observed.

        **Status:** CONFIRMED LIVE -- 228 total records. Last verified: 2026-03-04.

        ### Known Limitations
        - `sub_type` is always an empty array. Purpose unknown.
        - `series_id` is always null. May be for tournament series.
        - `home_away` can be null even for game events.
        - Coordinates appear in two formats: `{latitude, longitude}` in
          `location.coordinates` vs `{lat, long}` in google_place_details.

        ### Coaching Relevance
        Core schedule data for game preparation.
      x-status: CONFIRMED
      x-discovered: "2026-02-28"
      x-last-confirmed: "2026-03-04"
      x-coaching-tier: 1
      x-profiles:
        web:
          status: confirmed
          notes: "Full schema documented. 228 events returned."
        mobile:
          status: unverified
          notes: "Not captured in iOS proxy session."
      x-gc-user-action: "data_loading:team"
      tags:
        - schedule
        - events
        - team
      parameters:
        - name: team_id
          in: path
          required: true
          schema:
            type: string
            format: uuid
        - name: fetch_place_details
          in: query
          required: false
          schema:
            type: boolean
          description: "Enriches location with google_place_details and place_id"
        - name: gc-token
          in: header
          required: true
          schema:
            type: string
          x-credential: true
        - name: Accept
          in: header
          required: true
          schema:
            type: string
            default: "application/vnd.gc.com.event:list+json; version=0.2.0"
      responses:
        '200':
          description: Bare JSON array of schedule items
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: '#/components/schemas/ScheduleItem'
```

This is ~60 lines for a skeleton that doesn't include the response schema definition, the example responses, or the location object polymorphism documentation. The equivalent markdown prototype is 231 lines but includes everything -- full schema tables, two example responses, behavioral notes, and cross-references. The OpenAPI version would need another ~150 lines in `components/schemas/` to match the markdown's fidelity.

### Partial Endpoint (GET /organizations/{org_id}/opponent-players)

```yaml
  /organizations/{org_id}/opponent-players:
    get:
      operationId: getOrgOpponentPlayers
      summary: Bulk opponent roster at org level
      description: |
        **Status:** PARTIAL -- HTTP 500 with web headers, 200 observed on mobile.

        Returns HTTP 500 with web browser headers. Error: "Cannot read properties
        of undefined (reading 'page_size')". Suspected fix: add
        ?page_size=50 + x-pagination:true (same pattern as /organizations/{org_id}/teams).

        iOS proxy showed 200 OK with pagination cursors. Schema not captured.

        **Fallback:** Use GET /teams/{team_id}/opponents/players per team.
      x-status: PARTIAL
      x-caveats:
        - "HTTP 500 without pagination params on web profile"
        - "Schema not captured from mobile response"
      x-profiles:
        web:
          status: partial
          notes: "HTTP 500 -- missing pagination params"
        mobile:
          status: observed
          notes: "200 OK in proxy, schema not captured"
      # No response schema -- we haven't captured one yet
      responses:
        '200':
          description: "Expected: array of opponent player objects (not yet confirmed)"
        '500':
          description: "Returned when pagination params missing"
```

This works, but notice: the actual useful information is entirely in `description` strings and `x-*` extensions. The OpenAPI structure (paths, get, responses, etc.) adds overhead without adding value. An OpenAPI validator would say this is a valid spec, but the `200` response has no schema and the `500` response is documenting a bug, not an API contract. We are using OpenAPI as a container for markdown notes.

### Observed-Only Endpoint (GET /me/advertising/metadata)

```yaml
  /me/advertising/metadata:
    get:
      operationId: getMeAdvertisingMetadata
      summary: Advertising metadata for the app
      description: |
        **Status:** OBSERVED (proxy log, 1 hit, status 304).
        Not relevant to data ingestion.
      x-status: OBSERVED
      x-discovered: "2026-03-05"
      x-coaching-tier: 4
      responses:
        '304':
          description: "Cached response observed in proxy"
```

This is technically valid OpenAPI but meaningless as a spec. We are documenting that we saw this endpoint exist, nothing more.

**Prototype conclusion:** OpenAPI can hold the information, but for partially-known APIs, it is a structured container full of unstructured content. The structure provides little value because we don't have enough knowledge to leverage it. The vendor extensions (`x-status`, `x-profiles`, `x-caveats`) do the actual work, and those are just custom YAML fields -- the same thing YAML frontmatter provides without the OpenAPI boilerplate.

---

## MCP Assessment -- Complementary or Standalone?

### The Question

Could an MCP server add value on top of the markdown file structure? Is it worth building?

### What It Would Look Like

A small FastMCP server (~100-200 lines of Python) with three tools:

1. **`lookup_endpoint(method, path)`** -- Returns the full endpoint doc by reading the corresponding markdown file. Agent doesn't need to know the filename convention.
2. **`search_endpoints(tag, status, auth, profile)`** -- Parses frontmatter from all endpoint files, filters by criteria, returns a summary table. Agent doesn't need to grep.
3. **`get_reference(topic)`** -- Returns a global reference doc (authentication, headers, pagination, content-type). Agent asks for "pagination" instead of knowing the file path.

### Cost-Benefit Analysis

**Costs:**
- `fastmcp` dependency (active, well-maintained, Python-native)
- ~100-200 lines of server code to build and maintain
- MCP server configuration in `.claude/settings.json` or `.mcp.json`
- Another moving part to debug when things go wrong

**Benefits over raw file access:**
- Agents don't need to know file naming conventions or directory structure
- Search by frontmatter fields without parsing YAML themselves
- Could validate frontmatter on write (not just read)
- Tool Search deferred loading means zero context cost until used

**The key question: do agents struggle with file discovery?**

With the markdown approach, an agent that needs the schedule endpoint documentation would:
1. Read `docs/api/README.md` (the index) to find the filename
2. Read `docs/api/endpoints/get-teams-{team_id}-schedule.md`

That's two file reads, ~800 tokens total. An MCP tool call would be one call, ~500 tokens. The savings are real but modest.

Where MCP would shine: multi-criteria search. "Find all CONFIRMED endpoints that require auth and are tagged 'schedule'" -- this is a grep command on frontmatter, but an MCP tool could return it as a clean table. Whether this pattern occurs often enough to justify the infrastructure is debatable with only 88 endpoints.

### Verdict

**MCP is genuinely complementary, not standalone.** It sits in front of the storage format and provides structured access. But for 88 endpoints, it is premature optimization. The markdown files with an index provide sufficient discoverability. Build the file split first. If agents frequently struggle with endpoint discovery or need complex multi-criteria searches, add an MCP server then. The markdown format is MCP-ready -- the server would just read the files.

**Captured as future idea:** This should be an idea in `/.project/ideas/` for post-E-062 evaluation.

---

## Recommendation

### Primary recommendation: Structured Markdown with YAML Frontmatter (Option C)

**Continue with E-062 as designed.** The research spike is done, the format is validated, the prototypes work. The approach directly addresses every evaluation criterion:

**Why this wins:**

1. **Agent usability (HIGH):** 97% token reduction per query. Agents load one 50-200 line file instead of an 8,100-line monolith. YAML frontmatter provides structured metadata without requiring agents to parse YAML nesting -- they can read the file as markdown and get everything they need.

2. **Zero information loss (HIGH):** Markdown naturally accommodates every kind of content in the current monolith: schema tables, JSON examples, behavioral notes, caveats, coaching relevance assessments, cross-references. The YAML frontmatter captures structured fields the monolith expresses inconsistently (status, profiles, auth, Accept header).

3. **Header/payload/response detail (HIGH):** Full header blocks in the markdown body. Accept header in frontmatter. Response schema as markdown tables. Query params in both frontmatter (for search) and body (for detail). No information loss, no compression.

4. **Web vs. mobile separation (HIGH):** `profiles.web.*` and `profiles.mobile.*` in frontmatter with per-profile status and notes. This was specifically designed and validated by api-scout input during the E-062-R-01 spike.

5. **Ecosystem fit (HIGH):** Zero new dependencies. Markdown and YAML are already native to the project. No npm, no Node, no new services. PyYAML is already a transitive dependency.

6. **Maintainability (HIGH):** api-scout updates one file per endpoint discovery. New endpoints: copy the template, fill in what you know. Sparse files are fine -- a PARTIAL endpoint might be 20 lines.

7. **Searchability (MEDIUM):** Grep on frontmatter fields works. The index file (`docs/api/README.md`) provides a human-scannable table. Not as elegant as a search UI, but sufficient for 88 endpoints. If this becomes painful, MCP server is the upgrade path.

8. **Intuitiveness (HIGH):** Any developer can read the files. Any agent can consume them. The format is self-documenting -- open any endpoint file and its structure is obvious.

**Why OpenAPI loses:**

The core argument for OpenAPI is "it's the industry standard." But the industry standard assumes you control and fully understand the API you're documenting. When 60% of your endpoints have `status: OBSERVED` or `status: PARTIAL`, the OpenAPI structure adds overhead without adding value. You end up with a valid spec that contains no schemas, no confirmed response types, and paragraphs of caveats stuffed into `description` fields. The vendor extensions (`x-status`, `x-profiles`, `x-caveats`) that do the real work are just custom YAML -- the same thing frontmatter provides, without the `paths./.get.responses.200.content.application/json.schema` nesting tax.

If GameChanger ever publishes an official API spec, converting FROM structured markdown TO OpenAPI would be straightforward -- the frontmatter fields map cleanly to OpenAPI fields. The reverse migration (OpenAPI to markdown) would lose the vendor extensions that tools don't understand.

**What about the beautiful Redoc HTML?**

It is genuinely beautiful. But the primary consumers of this documentation are Claude Code agents, not humans browsing a web page. The secondary consumers (Jason, coaching staff) will interact with the data through the dashboard, not through API docs. If a human-browsable view is ever needed, a simple script that assembles the markdown index into a single rendered page would take an afternoon.

### Secondary recommendation: Capture MCP server as a future idea

After E-062 completes, observe whether agents struggle with endpoint discovery in the split format. If they do, build a lightweight FastMCP server that reads the markdown files and provides `lookup_endpoint`, `search_endpoints`, and `get_reference` tools. The markdown format is MCP-ready by design.

### What NOT to do

- Do not add npm/Node.js to the stack for Redoc or Swagger UI
- Do not subscribe to Stoplight or Mintlify
- Do not maintain two parallel formats (OpenAPI + markdown notes)
- Do not build an MCP server before the file split is complete and agents have had time to work with it

---

## Sources

- [OpenAPI Extensions (Swagger Docs)](https://swagger.io/docs/specification/v3_0/openapi-extensions/)
- [OpenAPI Specification v3.1.0](https://spec.openapis.org/oas/v3.1.0)
- [Redoc Vendor Extensions (GitHub)](https://github.com/Redocly/redoc/blob/main/docs/redoc-vendor-extensions.md)
- [Redoc CE Vendor Extensions](https://redocly.com/docs/redoc/redoc-vendor-extensions)
- [OpenAPI Deprecation/Beta Status Discussion (GitHub Issue #432)](https://github.com/OAI/OpenAPI-Specification/issues/432)
- [How to Split OpenAPI Spec into Multiple Files](https://medium.com/@gant0in/how-to-split-your-openapi-specification-file-into-multiple-files-33147cdd64e6)
- [Multi-file OpenAPI Definitions (Redocly)](https://redocly.com/learn/openapi/multi-file-definitions)
- [Markdown in OpenAPI (Redocly Blog)](https://redocly.com/blog/markdown-in-openapi)
- [Build Rich Developer Experiences with Markdown in OpenAPI](https://learn.openapis.org/specification/docs.html)
- [Swagger vs Redoc Comparison (Medium)](https://medium.com/@DaveLumAI/swagger-vs-redoc-the-ultimate-showdown-of-api-documentation-titans-6424e5967538)
- [Top 5 API Docs Tools 2025](https://apisyouwonthate.com/blog/top-5-best-api-docs-tools/)
- [Stoplight Pricing](https://stoplight.io/pricing)
- [Mintlify Review 2026 (Ferndesk)](https://ferndesk.com/blog/mintlify-review)
- [Claude Code MCP Documentation](https://code.claude.com/docs/en/mcp)
- [Tool Search Tool (Anthropic Platform Docs)](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-search-tool)
- [FastMCP GitHub](https://github.com/jlowin/fastmcp)
- [FastMCP Tutorial (Firecrawl)](https://www.firecrawl.dev/blog/fastmcp-tutorial-building-mcp-servers-python)
- [Claude Code MCP Tool Search (ClaudeFast)](https://claudefa.st/blog/tools/mcp-extensions/mcp-tool-search)
- [Mermade OpenAPI Specification Extensions (GitHub)](https://github.com/Mermade/openapi-specification-extensions)
- [Redoc HTML Deployment](https://redocly.com/docs/redoc/deployment/html)
- [Use the Redoc CE HTML Element](https://redocly.com/docs/redoc/deployment/html)
- [Redoc GitHub Repository](https://github.com/Redocly/redoc)
- [Stoplight Studio (GitHub)](https://github.com/stoplightio/studio)
- [OpenAPI Multiple Servers Per Endpoint](https://learn.openapis.org/specification/servers.html)
- [Header Variation per Operation (GitHub Issue #146)](https://github.com/OAI/OpenAPI-Specification/issues/146)
