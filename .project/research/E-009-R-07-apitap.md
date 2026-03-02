# E-009-R-07: apitap and Alternatives -- Research Report

**Research spike**: [E-009-R-07](../../epics/E-009-tech-stack-redesign/E-009-R-07.md)
**Date**: 2026-03-02
**Researchers**: apitap-investigator, landscape-researcher (agent team)

---

## Section 1: apitap -- What It Is

### What It Does

apitap is an MCP server that discovers, captures, and replays the internal HTTP APIs that websites use behind the scenes. It operates in three modes:

1. **Capture**: Launches a headless Chromium browser via Playwright, navigates to a target website, and records all HTTP API traffic the site generates (XHR/fetch calls). The captured endpoints are saved as portable "skill files" (JSON) with endpoint definitions, request parameters, headers, and response shapes.

2. **Replay**: Reads previously captured skill files and reconstructs the API calls using plain `fetch()` -- no browser needed. An AI agent can call a website's internal API endpoints directly without browser overhead.

3. **Read**: For 7 supported sites (Reddit, YouTube, Wikipedia, Hacker News, Twitter/X, and two others), built-in decoders extract structured content from HTML without a browser, with claimed 74% average token savings vs. raw HTML.

A Chrome extension captures API traffic from an already-authenticated browser session, avoiding the need for Playwright to handle login flows. The tool exposes 12 MCP tools for AI agent integration, including `apitap_browse` (auto-routes between read, replay, and capture) and interactive capture tools for step-by-step browsing with human guidance.

### Category

**apitap is a Web API traffic capture-and-replay tool, packaged as an MCP server for AI agent use.**

Primary category: API discovery and reverse-engineering via traffic interception. Secondary categories: MCP server / AI agent tooling, web content extraction.

### Setup and Maintenance Cost

**Installation** is lightweight -- three commands:

```bash
npm install -g @apitap/core
claude mcp add -s user apitap -- apitap-mcp
npx playwright install chromium   # optional, for browser-based capture
```

Three runtime dependencies: `@modelcontextprotocol/sdk`, `playwright`, and `zod`. Requires Node.js >= 20.

**Ongoing maintenance** is the concern. Captured skill files become stale when a target website changes its internal API structure, authentication scheme, or anti-bot protections. The tool categorizes endpoints into replayability tiers (Green/Yellow/Orange/Red) to signal fragility, but re-capture is the only remedy for breakage. For sites with aggressive API changes (like GameChanger), this could mean frequent re-capture sessions.

### Current Status

| Signal | Value |
|--------|-------|
| Stars | 52 |
| Forks | 2 |
| Open issues | 0 |
| Last commit | March 2, 2026 |
| Repository created | February 14, 2026 |
| Version | 1.1.0 |
| Tests | 925 passing |
| License | BSL 1.1 (converts to Apache 2.0 on Feb 7, 2029) |

**Assessment**: Very new (< 3 weeks old). Actively developed with high commit velocity (35 commits in 2 days). Single developer plus AI pair programming. Zero community adoption signal -- no Hacker News posts, Reddit threads, blog reviews, or external contributors. BSL license is acceptable for internal use but is not true open source.

**Risk factors**: Brand new and unproven. Single maintainer. No community vetting. BSL license restricts commercial competing use.

### How It Works

**Capture**: Launches Chromium via Playwright with network interception. Navigates to the target URL. Intercepts all HTTP requests/responses (XHR, fetch, WebSocket). Filters noise (static assets, analytics, ads) using heuristics and framework detection. Records endpoint definitions into JSON skill files. PII is scrubbed; auth tokens stored separately with AES-256-GCM encryption.

**Replay**: Reads a skill file. Reconstructs API calls with plain `fetch()`. Handles auth injection from encrypted credential store. Returns JSON to the calling agent. Supports batch replay.

**MCP integration**: 12 exposed tools. Auto-routing (`apitap_browse`) selects the cheapest available mode for a given URL. SSRF protection, DNS rebinding defense, and skill file signing (HMAC-SHA256) are built in.

---

## Section 2: Category Landscape

### Category Definition

**API reverse-engineering via traffic interception** tools solve the problem of programmatically interacting with web services that lack public, documented APIs. When data is only accessible through a website's UI, these tools capture the HTTP traffic between browser and server, identify the underlying API endpoints, and produce reusable artifacts (OpenAPI specs, client code, or parameterized endpoint files) for automated access. The category spans a spectrum from manual traffic inspection (proxy tools) through automated spec generation to AI-powered client code synthesis.

### Well-Known Alternatives

#### 1. mitmproxy + mitmproxy2swagger

- **Description**: Python-native interactive HTTPS proxy. mitmproxy2swagger converts captured traffic into OpenAPI 3.0 specs.
- **Maintenance**: Actively maintained. mitmproxy2swagger has 9.2k stars (Dec 2024 release). mitmproxy itself is mature and well-funded.
- **Language/ecosystem**: Python. pip-installable. Integrates natively with Python workflows.
- **Differentiator**: Established and battle-tested. General-purpose proxy, not AI-agent-specific. No MCP integration, no AI analysis. User does the browsing and filtering; tool does format conversion.

#### 2. openapi-devtools (Browser Extension)

- **Description**: Chrome/Firefox extension that generates OpenAPI 3.1 specs in real-time by monitoring network requests as you browse.
- **Maintenance**: 4.3k stars. Last release March 2024. Author has indicated a successor project exists. Entering maintenance mode.
- **Language/ecosystem**: TypeScript. Browser-only -- no CLI, no Python integration.
- **Differentiator**: Zero setup. Install extension, browse, get spec. But passive only (no replay, no parameterization) and cannot be scripted.

#### 3. reverse-api-engineer

- **Description**: CLI tool that captures browser traffic (HAR files) and uses Claude AI to generate production-ready Python API clients automatically.
- **Maintenance**: 438 stars. Last commit Dec 2025. Actively developed with multiple modes (manual, engineer, agent, collector).
- **Language/ecosystem**: Python (3.11+). pip/uv installable. Generates Python client code. Requires Claude API key.
- **Differentiator**: Python-native and generates Python code directly. Closest Python-native competitor to apitap. But depends on paid Claude API calls and is young/unproven. No MCP integration.

#### 4. API Parrot

- **Description**: Desktop application with built-in HTTP proxy that records traffic, analyzes endpoint relationships, and exports reusable JavaScript code.
- **Maintenance**: Launched Jan 2025 (featured on Hacker News). Desktop GUI. Early-stage.
- **Language/ecosystem**: JavaScript/TypeScript output only. Desktop GUI -- not scriptable.
- **Differentiator**: Focuses on understanding endpoint relationships and data dependencies. GUI-driven, not automatable. Exports JavaScript only.

#### 5. HTTP Toolkit

- **Description**: Cross-platform HTTP(S) debugging proxy with one-click interception, traffic inspection, and response mocking.
- **Maintenance**: Actively maintained commercial product with open-source components. Mature.
- **Language/ecosystem**: Language-agnostic. Has Python interception support. Desktop GUI + CLI.
- **Differentiator**: Full debugging/mocking suite. Supports Python process interception. Interactive tool, not automated discovery/replay. No spec generation, no AI integration.

#### 6. VCR.py + pytest-recording

- **Description**: Records HTTP interactions during test runs and replays them from "cassette" files on subsequent runs. pytest-recording provides pytest integration.
- **Maintenance**: Mature, stable. VCR.py has 2.7k+ stars, actively maintained.
- **Language/ecosystem**: Pure Python. pip-installable. Deep pytest integration.
- **Differentiator**: Solves a related but different problem -- test-time HTTP mocking via recorded interactions, not API discovery. Closest to apitap's "replay" concept but scoped to testing.

### Landscape Summary

The API reverse-engineering category is **fragmented and rapidly evolving**, driven by AI agent demand for machine-readable web APIs. The established layer (mitmproxy, Charles Proxy, HTTP Toolkit) provides robust traffic capture but requires manual analysis. A newer wave (apitap, reverse-api-engineer, API Parrot) adds AI-powered analysis and automated code generation, but these tools are young (< 2 years), have small communities, and are not battle-tested. No single tool dominates. Most practitioners still use a combination of proxy + manual inspection + custom scripts. Python-native options are strong at the proxy/capture layer (mitmproxy) and test-mocking layer (VCR.py, responses) but weaker at the automated spec-generation layer.

---

## Section 3: Fit Assessment for baseball-crawl

### Project Context

The baseball-crawl project interacts with GameChanger's undocumented API. The API discovery process is managed by the api-scout agent, which maintains `docs/gamechanger-api.md` as the single source of truth. The project has ~20 known endpoints. All HTTP client code lives in `src/gamechanger/` and `src/http/`. The stack is Python end-to-end (FastAPI, SQLite, pytest). Tests mock at the HTTP layer per CLAUDE.md rules.

### apitap

- **Is there a real problem this solves?** Partially. GameChanger API discovery is a real ongoing task. apitap could automate the capture of endpoint patterns from the GameChanger UI. However, the api-scout agent already handles this manually with browser DevTools, and the endpoint count (~20) does not justify automated discovery tooling.
- **Simpler alternative**: Browser DevTools Network tab + manual documentation in `docs/gamechanger-api.md`. For systematic capture: mitmproxy (pip install, Python-native).
- **What does apitap add?** MCP integration so AI agents could discover and replay APIs directly. Automated filtering and skill file generation. But it adds a Node.js/TypeScript dependency, a brand-new unproven tool, and ongoing skill file maintenance.
- **Verdict: Not recommended.** The project has ~20 endpoints, a working manual discovery process, and a Python stack. apitap introduces Node.js/TypeScript, a BSL-licensed dependency from a 3-week-old single-maintainer project, and ongoing skill file maintenance -- all for a problem the project is already solving adequately. The risk/complexity cost far exceeds the marginal benefit at this scale.

### mitmproxy + mitmproxy2swagger

- **Is there a real problem this solves?** Marginally. Could systematize the api-scout's endpoint discovery by capturing traffic through a proxy and auto-generating an OpenAPI spec. Relevant if the project needs to re-discover endpoints after GameChanger changes its API.
- **Simpler alternative**: Browser DevTools + manual documentation (current approach).
- **What does this add?** Python-native, mature, battle-tested. Could generate an OpenAPI spec automatically from browsing sessions. But the project's hand-maintained `docs/gamechanger-api.md` serves the same purpose and contains context (notes, quirks, credential patterns) that an auto-generated spec would not.
- **Verdict: Not recommended.** Useful tool, wrong scale. With ~20 endpoints and a hand-maintained API doc that includes contextual notes, auto-generating an OpenAPI spec adds process overhead without clear benefit. If the endpoint count grows significantly (50+) or the API changes frequently enough to make manual tracking painful, revisit this.

### openapi-devtools

- **Is there a real problem this solves?** Same marginal use case as mitmproxy2swagger -- real-time spec generation while browsing GameChanger.
- **Simpler alternative**: Browser DevTools Network tab.
- **What does this add?** Even simpler than mitmproxy -- zero-setup browser extension. But output is an OpenAPI spec with no Python integration, and the project is entering maintenance mode.
- **Verdict: Not recommended.** Entering maintenance mode. Output (OpenAPI spec) does not integrate with the project's Python workflow. The hand-maintained API doc is more useful.

### reverse-api-engineer

- **Is there a real problem this solves?** Yes, in theory. Generating Python API client code from captured traffic aligns with the project's needs better than TypeScript skill files. Could accelerate the api-scout's work by auto-generating initial Python client functions.
- **Simpler alternative**: Writing Python client functions manually based on the hand-maintained API doc (current approach).
- **What does this add?** Python-native. Generates actual Python client code from HAR captures. Uses Claude AI for analysis. But requires paid Claude API calls, is a young project (438 stars), and the project's endpoint count (~20) means the manual approach is tractable.
- **Verdict: Worth a follow-up spike** -- but only if the api-scout reports that manual client code generation is becoming a bottleneck. The follow-up spike would need to: (a) test reverse-api-engineer against a GameChanger browsing session, (b) evaluate the quality of generated Python code vs. hand-written, (c) assess the Claude API cost per capture session. Not urgent at current scale.

### HTTP Toolkit

- **Verdict: Not recommended.** Interactive debugging tool, not automated discovery. Useful for ad-hoc HTTP debugging but the project already has browser DevTools and curl for this. Overkill for the use case.

### API Parrot

- **Verdict: Not recommended.** Desktop GUI, exports JavaScript only. Does not fit a Python CLI/agent workflow.

### VCR.py + pytest-recording

- **Is there a real problem this solves?** Yes. The project's testing rules require mocking HTTP at the transport layer. VCR.py records real HTTP interactions and replays them in tests from cassette files. This is directly relevant to testing GameChanger API client code.
- **Simpler alternative**: `unittest.mock` or `responses` library (patch/mock HTTP calls manually).
- **What does this add?** Record-once, replay-forever testing. No need to hand-craft mock responses. Cassette files serve as living documentation of real API responses. pytest-recording provides clean pytest integration. Mature, stable, pure Python.
- **Verdict: Worth a follow-up spike.** VCR.py solves a real, current problem (testing HTTP client code against realistic responses). The follow-up spike would: (a) test VCR.py against a GameChanger API session to see if cassette recording works with the project's auth/session patterns, (b) evaluate integration with the project's existing pytest setup, (c) determine if cassette files can be safely committed (PII scrubbing needed). This is independent of the apitap category and closer to a testing infrastructure improvement.

---

## Section 4: Synthesis

### Is There a Gap?

**No meaningful gap exists at the project's current scale.** The API discovery and reverse-engineering category addresses a real class of problem, but baseball-crawl's instance of that problem is small enough (~20 endpoints, one undocumented API, a working manual discovery process) that existing tools handle it adequately. The project does not need automated API discovery, AI-powered endpoint analysis, or MCP-integrated capture-and-replay.

The newer AI-powered tools in this category (apitap, reverse-api-engineer) are solving for a scale and complexity that baseball-crawl has not reached. When you have hundreds of endpoints across multiple undocumented APIs, automated discovery and code generation become compelling. At 20 endpoints with one API, the manual approach (browser DevTools + hand-maintained docs + hand-written Python clients) is not just sufficient -- it produces better artifacts because the human context (credential quirks, rate limiting notes, endpoint behavior documentation) is captured alongside the technical spec.

### Best Fit (if any)

No tool in the primary category (API discovery/reverse-engineering) is recommended for adoption.

Two tools are worth monitoring:

1. **reverse-api-engineer**: If the api-scout reports that manual client code generation is becoming a bottleneck, this Python-native tool warrants a focused spike. Not recommended now; the trigger is scale or friction, not capability.

2. **VCR.py + pytest-recording**: This is outside the primary category (it is a testing tool, not a discovery tool) but was surfaced during landscape research and addresses a real current need. It deserves a follow-up spike as a testing infrastructure improvement, independent of the apitap investigation.

### Under What Circumstances to Revisit

Revisit the API discovery/reverse-engineering category if:
- The project needs to interact with a second undocumented API (not just GameChanger)
- The GameChanger API undergoes a major restructuring requiring wholesale re-discovery
- The endpoint count grows past ~50 and manual documentation becomes unsustainable
- apitap or reverse-api-engineer reach maturity (1.0+ stable release, >500 stars, multiple contributors, community adoption signals)

### Anything Unexpected Discovered

**VCR.py** was the most practically relevant find. It was not the target of the investigation, but it addresses the project's testing needs (record real HTTP interactions, replay in tests, avoid hand-crafting mock responses) more directly than any tool in the primary category. It is mature, Python-native, well-maintained, and has deep pytest integration. If this spike leads to any follow-on work, it should be a VCR.py evaluation spike, not an apitap adoption.

**The AI-agent-as-API-consumer pattern** (apitap, reverse-api-engineer) is an emerging category worth watching. The tools are too young for production use today, but the underlying idea -- AI agents that can discover and call undocumented web APIs autonomously -- has obvious long-term relevance for projects like baseball-crawl. This is a "check back in 6-12 months" category, not a "never" category.
