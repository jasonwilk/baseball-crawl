# E-009-R-05: Research Report -- MCP Ecosystem as Agent Integration Layer

**Spike**: E-009-R-05
**Date**: 2026-03-01
**Researcher**: product-manager (PM executing in-session)
**Output path**: `.project/research/E-009-R-05-mcp-ecosystem.md`

---

## Summary

This report evaluates four MCP servers for potential adoption in the baseball-crawl project.
The null hypothesis -- that bash calls are sufficient and MCP adds complexity without
proportional benefit at this project's scale -- is tested against each server.

**Finding**: Two of the four servers are not recommended. One is a borderline "worth a
follow-up spike" for a future state. One (CodeGraphContext/CodeGraphContext) is noteworthy
enough to flag but premature at current codebase scale.

---

## 1. docker/mcp (Docker Inc. -- Community: ckreiling/mcp-server-docker)

### What It Does

The spike referenced `docker/mcp-servers`, which resolves in practice to two distinct things:

1. **docker/mcp-registry** -- Docker Inc.'s official curated catalog of MCP servers.
   This is a registry of other servers, not an MCP server itself. It provides discovery
   and packaging infrastructure but does not expose any tools directly.

2. **ckreiling/mcp-server-docker** -- The best-maintained community Docker MCP server,
   which exposes actual Docker daemon operations over MCP. Tools cover: `list_containers`,
   `create_container`, `run_container`, `recreate_container`, `start_container`,
   `fetch_container_logs`, `stop_container`, `remove_container`, plus image and network
   management. Docker Compose is supported via a `docker_compose` prompt that lets agents
   orchestrate containers from natural language descriptions.

The server mounts the Docker socket as a volume. It can also connect to a remote Docker
daemon over SSH.

### Current Status

- **ckreiling/mcp-server-docker**: 680 stars, 94 forks, 53 commits, 9 open issues.
  GPL-3.0. Last commit not precisely dated but recent commits visible. Actively maintained.
- **docker/mcp-registry**: 428 stars, 620 forks, 1,399 commits, 127 contributors.
  Officially maintained by Docker Inc. Active.

### Fit Assessment for This Project

The baseball-crawl project interacts with Docker Compose via the Bash tool today:
- `docker compose up -d` to start the stack
- `docker compose logs <service>` to inspect output
- `docker compose down` to stop
- `docker ps` for container state

Agents doing this work: general-dev (E-009-02, E-009-03), data-engineer (E-009-02, E-009-05).
The gap this MCP server would close: agents would call `list_containers` or `fetch_container_logs`
as a typed tool rather than parsing bash output from `docker compose logs`.

At current scale (one `docker-compose.yml`, 3-4 services), this gap is narrow. The agent
already has the Bash tool, the commands are simple, and the output is predictable.

### Simpler Alternative

The Bash tool. `docker compose up`, `docker compose logs`, `docker ps --format json`,
`docker compose ps --format json` are all machine-readable already. A `--format json`
flag gives structured output without an MCP layer.

### Trade-off Summary

| Dimension | Bash tool + docker CLI | ckreiling/mcp-server-docker |
|-----------|------------------------|------------------------------|
| Setup cost | Zero (already available) | Moderate (Docker socket mount, settings.json registration) |
| Output parseability | Good with `--format json` | Excellent (typed tool output) |
| Error handling | Agent parses stderr | Structured error responses |
| Compose support | Full (all compose subcommands) | Limited (compose via prompt, not direct) |
| Security surface | Standard | Elevated (Docker socket = root equivalent) |
| Maintenance dependency | None (Docker Inc.) | Community project (ckreiling) |

### Verdict: Not Recommended

The Bash tool with `docker compose` and `--format json` flags is sufficient at this project's
scale (one stack, 3-4 services). The MCP server adds a dependency (GPL-3.0 community project),
a security surface (Docker socket mount), and configuration overhead. The ergonomic gain over
`docker compose ps --format json` is marginal.

When to revisit: If the project grows to multiple stacks or agents routinely fail to correctly
parse Docker output, the typing benefit of an MCP tool would be more defensible.

---

## 2. ChromeDevTools/chrome-devtools-mcp

### What It Does

An official Chrome DevTools project (owned by the ChromeDevTools GitHub organization,
Apache-2.0) that exposes the Chrome DevTools Protocol (CDP) as 29 MCP tools. Organized
across six categories:

- **Input automation** (9): click, drag, fill, fill_form, handle_dialog, hover, press_key,
  type_text, upload_file
- **Navigation** (6): close_page, list_pages, navigate_page, new_page, select_page, wait_for
- **Emulation** (2): emulate, resize_page
- **Performance** (4): performance_analyze_insight, performance_start_trace,
  performance_stop_trace, take_memory_snapshot
- **Network** (2): get_network_request, list_network_requests
- **Debugging** (6): evaluate_script, get_console_message, lighthouse_audit,
  list_console_messages, take_screenshot, take_snapshot

Requires Node.js 20.19+ and Chrome stable. Uses Puppeteer for browser automation.

### Current Status

27,100 stars, 1,600 forks, 594 commits, 56 open issues. Actively maintained by Google's
ChromeDevTools organization. Apache-2.0 license. Public preview launched in 2025 with
ongoing development.

### Fit Assessment for This Project

E-009-R-03 established that `WebFetch` is sufficient for agent browsability of the coaching
dashboard. The baseball-coach agent needs to verify: does this page render stats correctly?
Is the layout readable? WebFetch fetches HTML and lets an AI model evaluate it -- adequate
for text-and-table dashboards.

CDP-level access would add value if the project needed:
- Screenshot verification (visual regression, layout checking)
- JavaScript-rendered content that WebFetch cannot see
- Network trace analysis of dashboard API calls
- Performance profiling of dashboard load times
- Automated form interaction testing

The current dashboard (FastAPI + Jinja2 server-rendered HTML) has none of these needs.
Server-rendered HTML means no JS rendering gap. The dashboard is data tables and stat cards,
not interactive charting. Performance profiling is irrelevant for 5 users.

### Simpler Alternative

`WebFetch` (already available). For screenshot-level verification if ever needed: a one-line
`playwright` or `selenium` Python script called via Bash would be more Pythonic than
registering a Node.js MCP server.

### Trade-off Summary

| Dimension | WebFetch | chrome-devtools-mcp |
|-----------|----------|---------------------|
| Setup cost | Zero | Moderate (Node.js 20.19+, Chrome stable, settings.json) |
| Works with server-rendered HTML | Yes | Yes |
| Works with JS-rendered content | No | Yes |
| Screenshot capability | No | Yes (take_screenshot) |
| Network trace analysis | No | Yes |
| Runtime dependency | None | Chrome + Node.js process |
| Use case relevance today | Full | Near zero (dashboard is server-rendered) |

### Verdict: Not Recommended (today); Worth a Follow-Up Spike (if JS charting is added)

The dashboard is server-rendered. WebFetch handles it. There is no gap to fill.

If E-004 (Coaching Dashboard) later adds JavaScript-rendered charts (Chart.js, D3, or
similar), the CDP screenshot and evaluate_script tools would become genuinely useful.
At that point, a follow-up spike should evaluate: (a) can `playwright` via Bash + Python
handle the same use case more consistently with the Python-first project? (b) if so,
chrome-devtools-mcp is still not recommended.

---

## 3. CodeGraphContext/CodeGraphContext (now: abhigyanpatwari/GitNexus)

### Clarification

The spike referenced `CodeGraphContext/CodeGraphContext`. Research found that the actively
maintained project in this category is **abhigyanpatwari/GitNexus**, which serves the same
purpose: a semantic knowledge graph of the codebase exposed via MCP tools. GitNexus has
7,400 stars, 829 forks, and a last commit of 2026-03-01 (very recent). It is significantly
more developed and active than the CodeGraphContext project, which appears to be dormant.

This evaluation covers GitNexus as the representative of "codebase semantic graph via MCP."

### What It Does

GitNexus indexes a codebase into a persistent knowledge graph (KuzuDB) and exposes seven
MCP tools:

- `query` -- Hybrid BM25 + semantic search grouped by execution processes
- `context` -- 360-degree symbol view: all incoming/outgoing references for a symbol
- `impact` -- Blast radius analysis: what breaks if this symbol changes
- `detect_changes` -- Maps a git diff to affected execution processes
- `rename` -- Multi-file coordinated renaming validated by the graph
- `cypher` -- Raw Cypher graph queries for custom analysis
- `list_repos` -- Lists indexed repositories

Also installs four Claude Code agent skills (Exploring, Debugging, Impact Analysis,
Refactoring) to `.claude/skills/`. CLI: `npm install -g gitnexus`.

The efficiency claim is significant: 11,475 symbols across 1,553 files with 261,813
dependency edges at ~825 tokens (vs. 2.3M tokens for a full file dump). This is relevant
at large codebase scale.

### Current Status

7,400 stars, 829 forks, 265 commits, 24 open issues. Last commit 2026-03-01. npm package
`gitnexus` at version 1.3.6. Actively maintained. Supports TypeScript, JavaScript, Python,
Java, Kotlin, C, C++, C#, Go, Rust, PHP, Swift.

### Fit Assessment for This Project

The baseball-crawl codebase is currently under 20 Python files. The efficiency argument
for a code graph does not apply at this scale. An agent can read all relevant files in
a single context. Symbol cross-referencing is done by Grep + Read without exhausting the
context window.

The tools that would be most useful for this project's current state:
- `impact` -- useful when modifying `src/gamechanger/client.py` (does this break the
  data loaders?). At 20 files, Grep achieves the same result.
- `detect_changes` -- maps diffs to affected code. Useful post-refactor. Currently
  redundant with a git diff + Grep pass.

The break-even point where a code graph starts paying for itself is approximately
100-200 Python files with significant inter-module dependencies. The project will reach
this when E-004 (Coaching Dashboard) adds a substantial FastAPI routing layer and
multiple loader modules.

### Simpler Alternative

Grep + Read + Glob (all already available). At under 20 files, an agent reading all
source files fits in a single context pass. No indexing infrastructure needed.

### Trade-off Summary

| Dimension | Grep + Read + Glob | GitNexus MCP |
|-----------|--------------------|--------------|
| Setup cost | Zero | Moderate (npm global install, gitnexus analyze, settings.json) |
| Works offline | Yes | Yes (local index) |
| Codebase scale fit | Excellent (< 50 files) | Marginal now; excellent at > 100 files |
| Token efficiency | Good (selective reads) | Excellent at scale |
| Impact analysis accuracy | Manual (Grep) | Systematic (graph traversal) |
| Maintenance dependency | None | npm package (gitnexus) |
| Pre-existing skills | None (use project skills) | Installs its own .claude/skills/ |

Note on skills conflict: GitNexus installs skills to `.claude/skills/`. The project already
has custom skills at `.claude/skills/`. A GitNexus installation would need to be verified
not to overwrite or shadow existing skills.

### Verdict: Worth a Follow-Up Spike (when codebase reaches ~100 Python files)

Not recommended now. The codebase is too small for the efficiency gain to be meaningful.

Promotion trigger: when the `src/` directory exceeds ~100 Python files (likely after E-004
and E-002 are complete), run a follow-up spike. The spike should ask: (1) does `gitnexus`
work cleanly with a Python-only codebase at that scale? (2) does the skills installation
conflict with existing `.claude/skills/` content? (3) is the token efficiency gain
measurable in real agent sessions?

---

## 4. GlitterKill/sdl-mcp (Symbol Delta Ledger)

### What It Does

SDL-MCP (Symbol Delta Ledger MCP Server) indexes a repository into a SQLite-backed symbol
ledger and exposes 13+ tools for structured code context access. The core concept is a
four-rung context escalation ladder:

1. Symbol Cards (~50 tokens): name, signature, summary, dependencies
2. Skeleton IR (~200 tokens): signatures plus control flow structure
3. Hot-Path Excerpt (~500 tokens): lines matching specific identifiers
4. Full Code Window (~2,000 tokens): complete source with justification requirement

Tools: `search`, `getCard`, `build` (graph slices), `needWindow`, `getSkeleton`,
`getHotPath`, `policy` (governance), PR risk analysis, agent orchestration.

### Current Status

68 stars, 0 forks, 144 commits, last commit 2026-03-01 (v0.7.1). Active individual project
by developer GlitterKill. No community adoption (0 forks is a strong signal). Established
documentation but nascent adoption.

### Fit Assessment for This Project

SDL-MCP solves the same problem as GitNexus (token-efficient codebase access) via a
different mechanism (explicit context escalation vs. semantic graph search). The same
scale argument applies: at under 20 Python files, there is no token efficiency problem
to solve. Every file fits in context.

The PR risk analysis and policy governance features are interesting for future state
(when the project has a GitHub remote and CI/CD), but those are premature for the current
state of the project.

SDL-MCP's 0 forks and 68 stars vs. GitNexus's 7,400 stars and 829 forks indicates that
if the project were to invest in a code graph MCP, GitNexus is the more battle-tested
choice.

### Simpler Alternative

Same as CodeGraphContext: Grep + Read + Glob. See above.

### Trade-off Summary

| Dimension | Grep + Read + Glob | SDL-MCP |
|-----------|--------------------|---------|
| Setup cost | Zero | Moderate (npm/pip install, indexing, settings.json) |
| Community adoption | N/A | Very low (0 forks, 68 stars) |
| Token efficiency | Good now | Excellent at scale |
| Governance/policy tools | No | Yes (audit, policy) |
| PR risk analysis | No | Yes (future use) |
| Maintenance risk | None | High (solo project, early stage) |

### Verdict: Not Recommended

SDL-MCP is an interesting project with a thoughtful design, but it is a solo early-stage
tool with no community adoption (0 forks). The token efficiency gain is irrelevant at
current codebase scale. The policy and PR risk features are premature (no GitHub remote,
no CI/CD). If GitNexus is ever evaluated at 100+ file scale, SDL-MCP is not worth a
parallel evaluation given the adoption gap.

---

## Synthesis

### Which MCP Servers Are Worth Adopting?

None of the four evaluated servers are recommended for adoption today.

- **docker/mcp**: Bash + `docker compose` is sufficient. GPL dependency + Docker socket
  exposure is not worth a marginal ergonomic gain.
- **chrome-devtools-mcp**: WebFetch is sufficient for server-rendered dashboard review.
  Revisit if JS-rendered charting is added to E-004.
- **GitNexus (CodeGraphContext representative)**: Excellent tool for the right scale.
  The project is not there yet. Worth a follow-up spike at ~100 Python files.
- **SDL-MCP**: Solo project with 0 forks. Not recommended at any stage vs. GitNexus.

### General Pattern: What Types of MCP Servers Tend to Be Worth It vs. Not?

**Tend to be worth it** (for a project like this):
- Servers that expose data structures not available via bash (e.g., typed GitHub API
  responses when a GitHub remote exists -- see E-009-R-06)
- Servers with high community adoption (thousands of stars, hundreds of forks) where
  the maintenance risk is low
- Servers that eliminate an entire category of fragile bash-output parsing

**Tend not to be worth it** (for a small, Python-first project):
- Servers that duplicate capabilities already available via Bash + standard CLI flags
  with `--format json` or `--json`
- Servers that solve a scale problem the project does not have yet
- Solo projects with <100 stars and 0 forks
- Servers that require a separate runtime (Node.js) in a Python-only project
- Servers that install their own `.claude/skills/` potentially conflicting with existing
  project skills

### What Would Need to Change Before MCP Investment Pays Off?

1. **Scale**: When `src/` exceeds ~100 Python files, GitNexus becomes worth evaluating.
2. **GitHub remote**: When the project has a GitHub remote, github/github-mcp-server
   (GitHub's official MCP server, 27,400 stars, 3,700 forks) becomes the strongest
   candidate for adoption. It is not evaluated in this spike because R-06 covers the
   git/GitHub integration question directly.
3. **JS-rendered dashboard**: If E-004 adds Chart.js or similar, chrome-devtools-mcp
   warrants a re-evaluation.

### MCP Servers Discovered During Research That Were Not in the Original List

**github/github-mcp-server** (GitHub's official MCP Server):
- 27,400 stars, 3,700 forks, 755 commits. Actively maintained by GitHub.
- Exposes: repo browsing, issues, PRs, Actions, code search, project boards
- Requires: GitHub remote + Personal Access Token or OAuth
- This is a much stronger candidate than GitNexus for "structured GitHub data access."
  It is directly relevant to E-009-R-06's question. Not evaluated here because R-06
  covers it, but PM should review R-06's findings against this server.

---

## Recommendation to PM

No immediate action required. The null hypothesis holds: bash calls are sufficient at
this project's scale for all four evaluated servers.

**Capture as an idea** (not an epic yet):
- If E-004 adds JS-rendered content: revisit chrome-devtools-mcp
- When codebase reaches ~100 Python files: run GitNexus follow-up spike
- When GitHub remote is established: see E-009-R-06 for the stronger recommendation
  around github/github-mcp-server

---

**Sources:**
- [docker/mcp-registry](https://github.com/docker/mcp-registry)
- [ckreiling/mcp-server-docker](https://github.com/ckreiling/mcp-server-docker)
- [ChromeDevTools/chrome-devtools-mcp](https://github.com/ChromeDevTools/chrome-devtools-mcp)
- [abhigyanpatwari/GitNexus](https://github.com/abhigyanpatwari/GitNexus)
- [GlitterKill/sdl-mcp](https://github.com/GlitterKill/sdl-mcp)
- [6 Must-Have MCP Servers (Docker Blog)](https://www.docker.com/blog/top-mcp-servers-2025/)
- [Chrome DevTools for AI Agents](https://developer.chrome.com/blog/chrome-devtools-mcp)
- [gitnexus on npm](https://libraries.io/npm/gitnexus)
