# E-062: Split API Documentation into Per-Endpoint Files

## Status
`COMPLETED`

## Overview
Replace the monolithic `docs/gamechanger-api.md` (~8,100 lines, 88 endpoints) with a per-endpoint file structure that enables agents to load only the endpoints they need -- reducing context window consumption by 60-95% per query while preserving every detail currently documented.

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
- All 88 endpoints from the current doc exist as individual files in `docs/api/endpoints/` (plus 1 web-routes reference file)
- A `docs/api/README.md` index lists every endpoint with method, path, status, and auth requirement
- Global sections (authentication, headers, pagination, content-type convention) live in `docs/api/` reference files, not duplicated per endpoint
- `docs/gamechanger-api.md` is removed (not left as a stale duplicate)
- Agent definitions and CLAUDE.md references updated from the old path to the new structure
- No information present in the old doc is missing from the new structure
- Existing tests continue to pass (no code changes expected, but verify)

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-062-R-01 | Prototype endpoint file format | DONE | None | - |
| E-062-01 | Migrate global reference sections | DONE | E-062-R-01 | SE |
| E-062-02 | Migrate fully-documented endpoints | DONE | E-062-R-01 | SE |
| E-062-03 | Migrate confirmed endpoints | DONE | E-062-R-01 | SE |
| E-062-06 | Migrate proxy-discovered endpoints | DONE | E-062-R-01 | SE |
| E-062-04 | Build endpoint index and remove monolith | DONE | E-062-01, E-062-02, E-062-03, E-062-06 | SE |
| E-062-05 | Update context layer references | DONE | E-062-04 | CA |
| E-062-07 | Frontmatter validation script + migration content verification | DONE | E-062-04 | SE |
| E-062-08 | API docs Claude rule + ingest-endpoint skill rewrite | DONE | E-062-04 | CA |

## Dispatch Team
- software-engineer
- claude-architect

## Technical Notes

### Directory Structure (Target)
```
docs/api/
  README.md                          # Index: table of all endpoints with method, path, status, auth
  auth.md                            # JWT, device ID, app identity, token refresh
  headers.md                         # Header profiles (web vs mobile), browser headers, signature headers
  pagination.md                      # Pagination protocol (x-pagination, x-next-page, cursors)
  content-type.md                    # Vendor media type convention
  base-url.md                        # Base URL and subdomain conventions
  error-handling.md                  # Common HTTP error codes in GC API context
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
- Authentication -> `auth.md`
- Request Headers -> `headers.md`
- Content-Type Convention -> `content-type.md`
- Pagination -> `pagination.md`
- Base URL -> `base-url.md`
- Common error codes -> `error-handling.md`
- Endpoint Priority Matrix, Key Observations, Notes for Implementers -> folded into `README.md` or relevant endpoint files per format spec

### Migration Ordering
Stories E-062-01, E-062-02, E-062-03, and E-062-06 can execute in parallel because they create different files (reference files vs. endpoint files, with the spike inventory assigning each endpoint to exactly one story). E-062-04 depends on all four to build the index and remove the monolith. E-062-05, E-062-07, and E-062-08 all depend on E-062-04 and can run in parallel with each other. E-062-07 and E-062-08 can also run in parallel with E-062-05.

### Parallel Safety Note
E-062-02, E-062-03, and E-062-06 all write to `docs/api/endpoints/` but create disjoint file sets. The spike inventory (E-062-R-01) assigns each endpoint to exactly one story. No two stories create the same file.

### api-scout Frontmatter Schema Inputs (from spec review consultation)
The spike (E-062-R-01) must validate these edge cases identified by api-scout:
1. **Profile granularity**: `profiles.web: true/false` is too coarse. Some endpoints behave differently per profile (different response fields, different status codes). The schema needs to support profile-specific behavioral notes beyond presence/absence.
2. **Status categories**: The proposed `CONFIRMED | OBSERVED | UNTESTED | DEPRECATED` set is missing a category for endpoints that work only with specific parameters (e.g., HTTP 500 without `?page_size=50`, succeeds with it). Consider adding `PARTIAL` or a `caveats` field.
3. **Tag vocabulary**: No controlled tag vocabulary is defined. Without one, tags become unsearchable. The spike should define an initial tag set or decide tags are free-form with conventions.

### UX Recommendations (from E-062-07/08 consultation)
The following UXD recommendations affect existing migration stories and E-062-04's index building:
1. **Index grouping**: The `docs/api/README.md` index should group endpoints by domain (Authentication, My Account, Team Core, Schedule & Events, Games & Streams, Lineups, Players & Opponents, Public Endpoints, Organization, Sync & Subscription, Reference). Alphabetical within each group. This applies to E-062-04.
2. **One-line descriptions**: The index should include a 6-10 word description per endpoint. Method + path alone is ambiguous. For PARTIAL/OBSERVED endpoints, surface key caveat in the description. This applies to E-062-04.
3. **Investigation Status block**: PARTIAL and OBSERVED endpoint files should include an Investigation Status block near the top (below summary, before Path Parameters) that surfaces what's known, what's unknown, and next steps. This applies to E-062-03 and E-062-06.
4. **Flat directory confirmed**: 88 files in `docs/api/endpoints/` without subdirectories. Agent paths are predictable, domain navigation handled by grouped index.

### E-062-05 / E-062-08 Overlap Resolution
E-062-05 AC-7 (ingest-endpoint skill workflow update) and AC-8 (documentation.md ownership update) are absorbed by E-062-08. E-062-08 performs a full skill rewrite that supersedes E-062-05's path-swap approach for the ingest-endpoint skill. E-062-05 retains its remaining 7 ACs (AC-1 through AC-6, AC-9). Both stories depend on E-062-04 and can run in parallel.

## Open Questions
- ~~Exact YAML frontmatter fields -- the spike will validate the prototype schema against real endpoint data~~ (Resolved by E-062-R-01)
- ~~Whether `observations.md` should be a single file or split by topic -- spike will recommend~~ (Resolved: `error-handling.md` covers common errors; observations folded into endpoint files)
- ~~File naming edge cases for endpoints with complex paths~~ (Resolved by E-062-R-01 Section 2)

## History
- 2026-03-07: Created. Research findings from three deep-research agents inform the approach. Structured markdown with YAML frontmatter selected as the leading candidate based on convergent research recommendations.
- 2026-03-07: Codex spec review triage. Expert consultation with api-scout (routing, sizing, schema) and claude-architect (context-layer surface area, AC specificity). Key changes: split E-062-03 into E-062-03 (confirmed) + E-062-06 (proxy-discovered); added api-scout frontmatter schema inputs to Technical Notes; expanded E-062-05 ACs with enumerated file list and mapping rules; added ACs to E-062-R-01; updated line count to ~8,100; customized DoD for docs-only stories.
- 2026-03-07: Added E-062-07 (validation script) and E-062-08 (rule + skill rewrite). Expert consultation with SE (script architecture, YAML parsing, migration verification, error reporting), CA (rule scope, loading discipline, skill rewrite, overlap resolution), and UXD (error output formatting, index scannability, directory structure). Key changes: absorbed E-062-05 AC-7/AC-8 into E-062-08; added UX recommendations to Technical Notes for existing stories; resolved all open questions.
- 2026-03-07: Second codex spec review triage (17 findings). REFINED 7 findings: (1) E-062-07 AC-8 -- added inventory status normalization rule for parenthetical annotations; (2) E-062-04 AC-6 -- standardized verification artifact to story notes, added explicit count (88+1); (3) E-062-05 AC-6 -- removed ingest-endpoint/SKILL.md (owned by E-062-08); (4) epic Technical Notes directory structure, E-062-01 file list, E-062-04 AC-3 -- aligned reference file names with format spec (authentication.md->auth.md, observations.md removed, added base-url.md + error-handling.md); (5) epic overview + success criteria -- updated 79->88 endpoint count; (6) E-062-03 AC-5 -- corrected blanket CONFIRMED to match inventory (some endpoints are OBSERVED); (7) E-062-08 AC-13 -- changed from "remove ACs" to "verify ACs already removed." DISMISSED 10 findings: F1 (zero info loss is clear for doc migration), F4/F5 (absorption already applied, no hidden dep), F6/F7 (DoD grep exclusions already handle overlap), F9/F10/F11 (mechanical migration work fits single sessions), F12 (SE hint correct -- migration, not API exploration).
- 2026-03-07: **COMPLETED.** All 8 stories (1 research spike + 7 implementation) verified DONE. Monolithic `docs/gamechanger-api.md` (~8,100 lines) replaced by `docs/api/` directory: 89 endpoint files (88 endpoints + 1 web-routes reference), 6 global reference files, 1 README index. Three-way count match confirmed (89/89/89). Validation script (`scripts/validate_api_docs.py`, 36 tests) catches 28 frontmatter errors in migrated files and corrects them. Context layer fully updated: 17+ files re-pointed from monolith to new structure. New `.claude/rules/api-docs.md` enforces loading discipline. Ingest-endpoint skill rewritten with embedded format spec. Documentation ownership table updated. No documentation impact beyond the epic's own scope (the epic IS the documentation change). No follow-up work identified.
