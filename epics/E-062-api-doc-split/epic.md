# E-062: Split API Documentation into Per-Endpoint Files

## Status
`DRAFT`

## Overview
Replace the monolithic `docs/gamechanger-api.md` (~8,100 lines, ~79 endpoints) with a per-endpoint file structure that enables agents to load only the endpoints they need -- reducing context window consumption by 60-95% per query while preserving every detail currently documented.

## Background & Context
The current API doc is the single source of truth for GameChanger API knowledge. It works well as a reference but poorly for agent consumption: every agent that needs to check one endpoint must load ~30K tokens. The file has grown organically through three discovery phases (manual curl, live probe session, proxy capture) and contains three tiers of documentation quality -- from fully-schematized endpoints down to one-line observations. Endpoint information is sometimes split across sections (e.g., a proxy-discovered endpoint later confirmed in the "Confirmed Endpoints" section, with details in both places).

Three independent research agents evaluated the problem space and converged on the same core insight: **the problem is delivery, not format**. Any format loaded in full is too large. The highest-leverage change is splitting so agents load only what they need. The format of each piece matters less than independent access to pieces.

The top-ranked approach across all three evaluations was **structured markdown with YAML frontmatter** in per-endpoint files. This requires zero new dependencies, preserves free-form notes naturally, makes frontmatter machine-parseable for indexing, and aligns with the project's "simple first" principle.

Expert consultation performed during spec review triage (2026-03-07): api-scout provided frontmatter schema feedback (profile granularity, status categories, tag vocabulary) incorporated into E-062-R-01. claude-architect enumerated full context-layer reference surface area (17+ files) and provided path-mapping rules incorporated into E-062-05.

## Goals
- Every endpoint documented in its own file, loadable independently (~50-200 lines each)
- Zero information loss from the current monolithic doc
- Machine-parseable metadata (auth, profile, status, method, path) in YAML frontmatter
- An index file that lets agents find endpoints without loading all of them
- Clear separation of web vs. mobile header profiles per endpoint
- api-scout can write to individual endpoint files without touching others
- Implementing agents (SE, DE) can load only the endpoints relevant to their story

## Non-Goals
- MCP server or programmatic query layer (build when pain justifies it -- captured as future idea)
- OpenAPI/Swagger conversion (higher maintenance burden, poor fit for reverse-engineered API notes)
- SQLite-backed endpoint store (over-engineered for ~80 endpoints)
- Changing what information is captured about each endpoint (this epic restructures, not redefines)
- Automated HAR-to-endpoint-file pipeline (future work after the format is established)

## Success Criteria
- All 79 endpoints from the current doc exist as individual files in `docs/api/endpoints/`
- A `docs/api/README.md` index lists every endpoint with method, path, status, and auth requirement
- Global sections (authentication, headers, pagination, content-type convention) live in `docs/api/` reference files, not duplicated per endpoint
- `docs/gamechanger-api.md` is removed (not left as a stale duplicate)
- Agent definitions and CLAUDE.md references updated from the old path to the new structure
- No information present in the old doc is missing from the new structure
- Existing tests continue to pass (no code changes expected, but verify)

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-062-R-01 | Prototype endpoint file format | TODO | None | - |
| E-062-01 | Migrate global reference sections | TODO | E-062-R-01 | - |
| E-062-02 | Migrate fully-documented endpoints | TODO | E-062-R-01 | - |
| E-062-03 | Migrate confirmed endpoints | TODO | E-062-R-01 | - |
| E-062-06 | Migrate proxy-discovered endpoints | TODO | E-062-R-01 | - |
| E-062-04 | Build endpoint index and remove monolith | TODO | E-062-01, E-062-02, E-062-03, E-062-06 | - |
| E-062-05 | Update context layer references | TODO | E-062-04 | - |

## Dispatch Team
- software-engineer
- claude-architect

## Technical Notes

### Directory Structure (Target)
```
docs/api/
  README.md                          # Index: table of all endpoints with method, path, status, auth
  authentication.md                  # JWT, device ID, app identity, token refresh
  headers.md                         # Header profiles (web vs mobile), browser headers, signature headers
  pagination.md                      # Pagination protocol (x-pagination, x-next-page, cursors)
  content-type.md                    # Vendor media type convention
  observations.md                    # Key observations, notes for implementers (currently at bottom of monolith)
  endpoints/
    get-me-teams.md                  # One file per endpoint
    get-me-user.md
    get-teams-{team_id}.md
    get-teams-{team_id}-schedule.md
    ...
    post-auth.md
    ...
```

### Endpoint File Naming Convention
`{method}-{path-segments-joined-by-dashes}.md` with path parameters kept as `{param}`. Examples:
- `get-me-teams.md`
- `get-teams-{team_id}-schedule.md`
- `get-game-stream-processing-{game_stream_id}-boxscore.md`
- `post-auth.md`
- `get-public-teams-{public_id}.md`

### YAML Frontmatter Schema (Prototype -- spike will validate)
```yaml
---
method: GET
path: /teams/{team_id}/schedule
status: CONFIRMED        # CONFIRMED | OBSERVED | UNTESTED | DEPRECATED
auth: required           # required | none
profiles:
  web: true
  mobile: true
accept: "application/vnd.gc.com.event:list+json; version=0.2.0"
query_params: [include]
pagination: true
discovered: 2026-02-28
last_confirmed: 2026-03-07
tags: [schedule, events, team]
---
```

### Documentation Tiers (from current doc)
The current doc has three implicit tiers of documentation quality:
1. **Fully documented** (~24 endpoints): Complete headers, response schema, query params, behavioral notes, confirmation dates
2. **Partially documented** (~40 endpoints): Method, path, status, some schema or behavioral notes, often from proxy capture + live confirmation
3. **Minimal** (~15 endpoints): Method, path, observed status code, maybe a one-line note

All three tiers must be migrated. The file format accommodates all tiers -- minimal endpoints simply have sparse frontmatter and a short body.

### Web vs. Mobile Profile Handling
The current doc already partially tracks web/mobile differences (header profiles table, per-endpoint header blocks). The new format should support per-endpoint profile annotations:
- Which profiles have been tested against this endpoint
- Any profile-specific header differences observed
- Profile-specific behavioral notes (e.g., "returns 500 with web headers, succeeds with mobile")

This is captured in the frontmatter `profiles` field and in the endpoint body under a "Profile Notes" section.

### Cross-References
The current doc has internal cross-references (e.g., "See schema in Proxy-Discovered section above"). These must be converted to file-relative links between endpoint files or to the global reference files. The spike should identify all cross-reference patterns.

### Information That Lives Outside Endpoint Files
These sections from the current doc become standalone reference files, not duplicated per endpoint:
- Base URL
- Authentication (JWT structure, device ID, app identity)
- Request Headers (common headers, browser headers, signature headers, header profiles table)
- Content-Type Convention (vendor media types)
- Pagination (protocol, cursor behavior)
- Endpoint Priority Matrix
- Key Observations
- Notes for Implementers

### Migration Ordering
Stories E-062-01, E-062-02, E-062-03, and E-062-06 can execute in parallel because they create different files (reference files vs. endpoint files, with the spike inventory assigning each endpoint to exactly one story). E-062-04 depends on all four to build the index and remove the monolith. E-062-05 updates context-layer references after the structure is finalized.

### Parallel Safety Note
E-062-02, E-062-03, and E-062-06 all write to `docs/api/endpoints/` but create disjoint file sets. The spike inventory (E-062-R-01) assigns each endpoint to exactly one story. No two stories create the same file.

### api-scout Frontmatter Schema Inputs (from spec review consultation)
The spike (E-062-R-01) must validate these edge cases identified by api-scout:
1. **Profile granularity**: `profiles.web: true/false` is too coarse. Some endpoints behave differently per profile (different response fields, different status codes). The schema needs to support profile-specific behavioral notes beyond presence/absence.
2. **Status categories**: The proposed `CONFIRMED | OBSERVED | UNTESTED | DEPRECATED` set is missing a category for endpoints that work only with specific parameters (e.g., HTTP 500 without `?page_size=50`, succeeds with it). Consider adding `PARTIAL` or a `caveats` field.
3. **Tag vocabulary**: No controlled tag vocabulary is defined. Without one, tags become unsearchable. The spike should define an initial tag set or decide tags are free-form with conventions.

## Open Questions
- Exact YAML frontmatter fields -- the spike will validate the prototype schema against real endpoint data
- Whether `observations.md` should be a single file or split by topic -- spike will recommend
- File naming edge cases for endpoints with complex paths (e.g., `/teams/public/{public_id}/players` vs `/public/teams/{public_id}`) -- spike will establish convention

## History
- 2026-03-07: Created. Research findings from three deep-research agents inform the approach. Structured markdown with YAML frontmatter selected as the leading candidate based on convergent research recommendations.
- 2026-03-07: Codex spec review triage. Expert consultation with api-scout (routing, sizing, schema) and claude-architect (context-layer surface area, AC specificity). Key changes: split E-062-03 into E-062-03 (confirmed) + E-062-06 (proxy-discovered); added api-scout frontmatter schema inputs to Technical Notes; expanded E-062-05 ACs with enumerated file list and mapping rules; added ACs to E-062-R-01; updated line count to ~8,100; customized DoD for docs-only stories.
