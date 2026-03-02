# E-009-R-07 Section 1: apitap Deep-Dive

**Repository**: https://github.com/n1byn1kt/apitap
**Package**: `@apitap/core` on npm
**Version**: 1.1.0 (as of March 2, 2026)

---

## 1. What It Does

apitap is an MCP server that discovers, captures, and replays the internal HTTP APIs that websites use behind the scenes. It works in three layers:

1. **Capture**: Launches a headless Chromium browser (via Playwright), navigates to a target website, and records all HTTP API traffic the site generates (XHR/fetch calls to its own backend). The captured endpoints are saved as portable "skill files" (JSON).

2. **Replay**: Takes previously captured skill files and replays the API calls using plain `fetch()` -- no browser needed. This means an AI agent can call a website's internal API endpoints directly without scraping HTML.

3. **Read**: For supported sites (Reddit, YouTube, Wikipedia, Hacker News, Twitter/X, and two others), built-in decoders extract structured content from HTML without a browser at all, with claimed 74% average token savings vs. raw HTML.

It also includes a Chrome extension that captures API traffic from an already-authenticated browser session, avoiding the need for Playwright to handle login flows.

**In concrete terms**: You point apitap at a website. It opens the site in a headless browser, watches what API calls the website makes, records them, and then lets you replay those same API calls later without the browser. The primary consumer is an AI agent operating via MCP.

## 2. Category

**apitap is an API traffic capture-and-replay tool, packaged as an MCP server for AI agent use.**

Primary category: **Web API discovery and replay** (intercept internal website APIs, generate reusable call patterns)

Secondary categories:
- MCP server / AI agent tooling
- Web content extraction (via its text-mode decoders)
- Lightweight alternative to browser automation for data access

## 3. Setup and Maintenance Cost

### Installation
```bash
npm install -g @apitap/core
claude mcp add -s user apitap -- apitap-mcp
npx playwright install chromium   # optional, for browser-based capture
```

Three commands. No Docker, no server process, no database. It runs as a CLI tool and/or MCP server process.

### Dependencies
Minimal: only three runtime dependencies:
- `@modelcontextprotocol/sdk` (^1.26.0)
- `playwright` (^1.58.1) -- optional if only using replay/read modes
- `zod` (^4.3.6)

Requires Node.js >= 20.

### Maintenance Considerations
- **Skill files may break**: Captured API patterns can become stale if the target website changes its internal API structure, authentication scheme, or adds anti-bot protections. The tool categorizes endpoints into replayability tiers (Green/Yellow/Orange/Red) to signal fragility.
- **Authentication**: For sites requiring login, the Chrome extension captures from an authenticated session. Auth credentials are stored encrypted (AES-256-GCM) separately from skill files.
- **No server to run**: It is a local CLI/MCP tool, not a persistent service. No ongoing infrastructure cost.

### Effort Assessment
- **Initial setup**: Low (minutes). npm install + MCP registration.
- **Per-site onboarding**: Medium. Each new site requires a capture session, evaluation of replayability tier, and possibly auth setup.
- **Ongoing maintenance**: Medium. Skill files for sites with aggressive API changes or anti-bot measures will require periodic re-capture.

## 4. Current Status

| Signal | Value |
|--------|-------|
| **Stars** | 52 |
| **Forks** | 2 |
| **Open issues** | 0 |
| **Last commit** | March 2, 2026 |
| **Repository created** | February 14, 2026 |
| **Version** | 1.1.0 |
| **Test count** | 925 passing |
| **Commit frequency** | 35 commits in 2 days (March 1-2, 2026) |

### Assessment
- **Very new project** -- less than 3 weeks old at time of research.
- **Actively developed** -- high commit velocity, multiple releases (1.0.20 -> 1.0.22 -> 1.1.0) in days.
- **Low community adoption** -- 52 stars, 2 forks, zero open issues. No discoverable community discussion (Hacker News, Reddit, blogs) as of this research date.
- **Single developer** -- commits show one author plus AI pair programming (Claude Opus 4.6 co-authorship).
- **License caveat**: Business Source License 1.1 (BSL), not true open source. Free for non-competing use cases (personal, internal, educational, research, open source). Converts to Apache 2.0 on February 7, 2029. Cannot be rebranded/resold as a competing service.

### Risk Factors
- Brand new, unproven in production
- Single maintainer, no community contributors
- BSL license restricts commercial competing use
- No external reviews, audits, or community vetting

## 5. How It Works (Technical Mechanism)

### Capture Phase
1. Launches Chromium via Playwright with network interception enabled
2. Navigates to the target URL
3. Intercepts all HTTP requests/responses the page makes (XHR, fetch, WebSocket)
4. Filters out noise (static assets, analytics, ads) using heuristics and framework detection (WordPress, Next.js, Shopify, etc.)
5. Records the API endpoints, request parameters, headers, and response shapes
6. Saves the result as a "skill file" (JSON) with endpoint definitions
7. PII is scrubbed during capture; auth tokens are stored separately with AES-256-GCM encryption

### Replay Phase
1. Reads a previously generated skill file
2. Reconstructs the API calls using plain `fetch()` (no browser)
3. Handles auth injection from encrypted credential store if needed
4. Returns clean JSON responses to the calling agent
5. Supports batch replay for multiple endpoints

### Read Phase (No Browser)
1. For supported sites, fetches the HTML page directly
2. Runs site-specific decoder (one of 7 built-in decoders)
3. Extracts structured content (titles, text, metadata) from HTML
4. Returns structured data at significant token savings vs. raw HTML

### MCP Integration
- Exposes 12 MCP tools that AI agents can call
- `apitap_browse` auto-routes between read, replay, and capture based on what is available
- `apitap_peek` does a zero-cost HTTP HEAD to triage URLs before committing to heavier operations
- Interactive capture tools (`capture_start` / `capture_interact` / `capture_finish`) allow step-by-step browsing with human guidance

### Security Measures
- SSRF protection blocks private IPs, internal hostnames, dangerous URL schemes
- DNS rebinding defense
- Skill file signing with HMAC-SHA256
- Header injection prevention
- Redirect validation

---

## Relevance to baseball-crawl

apitap's capture-and-replay approach is directly relevant to the baseball-crawl project's need to access GameChanger's undocumented API. Potential alignment:

- **API Discovery**: Could automate the discovery of GameChanger API endpoints that the api-scout agent currently maps manually.
- **Replay without browser**: Once endpoints are captured, subsequent data pulls would not require a full browser session.
- **Auth handling**: The Chrome extension approach could handle GameChanger's short-lived session tokens by capturing from an already-authenticated browser.

**Concerns for this use case**:
- Very new and unproven (< 3 weeks old)
- BSL license (acceptable for internal use, but worth noting)
- GameChanger may fall into the Orange/Red replayability tier (session binding, possible anti-bot measures)
- Adds a Node.js/TypeScript dependency to a Python-primary project
- Single maintainer risk for a dependency
