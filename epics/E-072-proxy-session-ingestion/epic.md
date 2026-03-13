# E-072: Proxy Session Ingestion Skill

## Status
`READY`

## Overview
Create a new workflow skill that processes an entire mitmproxy session -- identifying unknown endpoints, comparing against documented endpoints, and orchestrating bulk raw data capture with profile-aware headers. This gives the operator a single trigger phrase ("ingest session") to go from a completed proxy capture to documented endpoints and raw data, replacing a manual multi-step process.

## Background & Context
Today, the operator captures web/mobile traffic through mitmproxy sessions on their Mac host. After a session ends, there is no automated way to:
1. Compare captured endpoints against the 119 documented endpoints in `docs/api/endpoints/`
2. Identify genuinely new/unknown endpoints from the session
3. Bulk-fetch raw responses while tokens are still fresh
4. Handle the web vs. mobile profile distinction for headers

The existing `ingest-endpoint` skill (`.claude/skills/ingest-endpoint/SKILL.md`) handles ONE endpoint at a time from a manually-placed curl command. This epic creates a broader session-level skill that can process all unknowns from a proxy session.

**Expert consultation**: Claude Architect and Software Engineer both reviewed the initial spec post-formation. CA provided 7 items (fast-path batch mode, concrete normalization rules, status code classification, cross-profile enrichment, active session gate, endpoint-log size correction, endpoint_count unreliability). SE assessed all 7 and added 3 (deduplicate normalized paths, 304 cache-busting guidance, bb proxy endpoints limitation). User added 2 (serial capture execution, JWT expiry pre-check). All 12 items incorporated into this revision.

Key existing infrastructure this epic builds on:
- **Proxy session data**: `proxy/data/sessions/*/endpoint-log.jsonl` (JSONL -- see Endpoint-Log Format below for field list), `session.json` (profile, status, reviewed, endpoint_count fields)
- **BB CLI proxy commands**: `bb proxy endpoints`, `bb proxy report`, `bb proxy review` (shell script wrappers)
- **HTTP layer**: `src/http/headers.py` (BROWSER_HEADERS, MOBILE_HEADERS), `src/http/session.py` (create_session with profile param)
- **Existing ingest-endpoint skill**: Two-phase workflow (api-scout executes curl, claude-architect integrates) for single endpoints
- **Endpoint docs**: 119 endpoint files in `docs/api/endpoints/` with YAML frontmatter, validated by `scripts/validate_api_docs.py` (120 total files; `web-routes-not-api.md` is a non-API reference file with `status: NOT_API` and must be excluded from endpoint comparison)

## Goals
- A single trigger phrase ("ingest session") kicks off a comprehensive session ingestion workflow
- Unknown endpoints are identified by comparing session endpoint-log against documented endpoints
- Profile (web/mobile) is auto-detected from session metadata, enabling correct header selection
- The operator gets a prioritized list of unknown endpoints to choose from for raw data capture
- Raw responses are saved to `data/raw/` for later analysis by api-scout
- The skill reuses existing `bb proxy` commands and `ingest-endpoint` skill patterns where possible

## Non-Goals
- No new `bb` CLI commands (the skill orchestrates existing commands)
- No automatic crawling or pagination -- the skill presents unknowns and the operator decides what to fetch
- No changes to the proxy addons or mitmproxy configuration
- No changes to the HTTP layer (`src/http/headers.py`, `src/http/session.py`)
- No application code changes -- this is entirely context-layer work (skill files, possibly rules or agent def updates)

## Success Criteria
- An operator can say "ingest session" (or similar trigger phrase) and the skill workflow activates
- The workflow reads the latest proxy session, identifies endpoints not yet documented, and presents a summary
- The workflow handles profile detection (web vs mobile) from session metadata without operator input
- The workflow guides the operator through selective raw data capture for chosen endpoints
- CLAUDE.md Workflows section references the new skill
- The skill file follows the established format (activation triggers, purpose, phases, security invariants, anti-patterns)

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-072-01 | Create ingest-session skill file | TODO | None | - |
| E-072-02 | Register skill in CLAUDE.md and update context layer | TODO | E-072-01 | - |

## Dispatch Team
- claude-architect

## Technical Notes

### Architectural Decisions

**New skill, not an evolution of ingest-endpoint.** The existing `ingest-endpoint` skill is scoped to a single endpoint from a curl command. The session ingestion skill is a different workflow: it starts from proxy session data (not a curl file), processes multiple endpoints, and involves operator selection before any fetching. The two skills are complementary: `ingest-session` identifies unknowns from a session, and the operator can then use `ingest-endpoint` for individual endpoints that need deep documentation. The new skill may reference `ingest-endpoint` as a follow-up action but does not invoke it directly.

**Profile auto-detection from session metadata.** The `session.json` file has a `profile` field (values: "web", "mobile") -- this is the authoritative source for header selection. The endpoint-log JSONL has a `source` field per entry which may show "web" or "ios" (NOT "mobile") -- this tracks what the mitmproxy addon detected, which may differ from the operator-set profile (e.g., session.json may say "web" while source says "ios"). The skill auto-detects profile from `session.json` only and uses it to determine which header set (BROWSER_HEADERS vs MOBILE_HEADERS) is relevant. The `source` field is informational only and is NOT used for profile determination. No operator input needed for profile determination.

**Selective capture with data-first approach.** Sessions using the richer endpoint-log format (2026-03-12+) already contain `response_body` for many entries. The skill checks for captured response data FIRST -- if a non-empty `response_body` exists for a chosen endpoint, it saves directly to `data/raw/` without any curl recapture (selection rule: among all JSONL entries matching the normalized template, prefer the largest non-empty 2xx `response_body` by byte length; ties broken by earliest timestamp; if no 2xx with non-empty body, skip data-first and fall back to curl). Only endpoints lacking response data fall back to curl templates.

**Curl fallback is profile-dependent.** Web profile access tokens are obtained programmatically by `TokenManager` and never persisted to `.env`. Generating curl templates for web sessions would require the agent to display the live gc-token value, violating the "never display gc-token" security invariant. This is a security policy constraint, not a temporary implementation gap. The mobile profile DOES have `GAMECHANGER_ACCESS_TOKEN_MOBILE` persisted in `.env`, making curl templates viable without exposing credentials.

- **Web profile**: For endpoints without captured response data, the skill routes to `ingest-endpoint` per endpoint (operator captures individual curls from browser). Credential freshness check: `bb creds check --profile web` (if API health shows `[XX]`, run `bb creds refresh --profile web` first). No batch quick-capture mode.
- **Mobile profile**: For single endpoints without data, route to `ingest-endpoint`. For multiple endpoints, offer the "quick-capture" sub-mode with shell-variable-based curl templates using `$GAMECHANGER_ACCESS_TOKEN_MOBILE` and `$GAMECHANGER_DEVICE_ID_MOBILE`. Credential freshness check: JWT decode of `GAMECHANGER_ACCESS_TOKEN_MOBILE` from `.env`.

Endpoints are processed serially (not in parallel) so that if a 401 or other auth failure comes back, the operator can stop immediately.

**Endpoint comparison logic.** The skill compares session endpoints against `docs/api/endpoints/` using the file naming convention: `{method}-{path-segments-with-params-as-words}.md`. Path parameters are normalized using concrete rules: UUID segments matching the 8-4-4-4-12 hex pattern (e.g., `aabb0011-ccdd-4eef-8899-ffeeddccbbaa`) become their placeholder names (`{team_id}`, `{game_stream_id}`, etc.); short alphanumeric slugs in `/public/teams/` or `/teams/public/` paths become `{public_id}`. Multi-parameter paths (e.g., `/teams/{team_id}/opponent/{opponent_id}`) must normalize ALL parameter positions. **Fallback for unknown paths**: if a normalized path with named placeholders does not match any existing doc filename, use `{id}` as the generic placeholder for all UUID-shaped segments and mark the candidate as "placeholder names uncertain -- requires human review" in the presentation. After normalization, paths are deduplicated before comparison -- a session with 50+ raw `/teams/{id}/opponent/{id}` paths should collapse to a single template. Ambiguous normalizations are resolved by matching against existing doc filenames. Non-API hosts (e.g., `web.gc.com`) and OPTIONS preflight requests are filtered out. The comparison yields: (1) known endpoints (already documented), (2) unknown endpoints (no matching doc file), (3) enrichable endpoints (doc exists but session shows query params not present in the doc's `query_params` frontmatter list), (4) cross-profile enrichment candidates (doc exists but was captured from a different profile than the current session -- checked via the doc's `profiles.{profile}.status` field). Note: status-code comparison is NOT used for the enrichable classification because the doc schema has no structured status-code inventory; status codes are used only for priority signaling in Phase 3.

**Skill file location.** `.claude/skills/ingest-session/SKILL.md` -- follows the established pattern.

**Integration with bb CLI.** The skill may reference `bb proxy endpoints` for operator convenience, but the executing agent MUST NOT treat its output as the normalized endpoint set. `bb proxy endpoints` (via `proxy-endpoints.sh`) outputs raw, unnormalized paths with literal UUIDs. The agent must read the `endpoint-log.jsonl` JSONL directly and perform its own normalization and deduplication. No new bb commands needed.

### Workflow Phases (for skill design)

1. **Session Discovery**: Read the latest proxy session (or a specific session if the operator names one). Auto-detect profile from `session.json` (the `profile` field is authoritative; ignore the per-entry `source` field which may show "ios" or "web" independently). Check session status: if `status == "active"`, present a clear warning about partial/in-progress data and let the operator decide whether to proceed or wait (do NOT hard-refuse -- a crashed proxy may leave a permanently "active" session). If the `proxy/data/current` symlink is absent, list available sessions under `proxy/data/sessions/` and let the operator choose rather than failing silently. Filter endpoint-log to API requests only (host = `api.team-manager.gc.com`, method != OPTIONS). Read the JSONL directly (typically a few hundred lines per session). Detect the endpoint-log format version by checking for the presence of `response_body` key in the first entry (see Endpoint-Log Format section). If the endpoint-log is empty or contains zero entries matching the API host after OPTIONS filtering, present "No GameChanger API endpoints found in this session" and offer to skip to Phase 5 (session marking) or end the workflow.
2. **Endpoint Comparison**: Normalize filtered endpoint paths (replace UUIDs/IDs with parameter placeholders per the normalization rules in Architectural Decisions). For truly unknown paths where no doc matches named placeholders, fall back to `{id}` as a generic placeholder and mark as "placeholder names uncertain -- requires human review". Deduplicate normalized paths. Compare deduplicated set against `docs/api/endpoints/` listing (exclude files with `status: NOT_API` in frontmatter, such as `web-routes-not-api.md`). Classify each endpoint into one of these categories: (a) **unknown** -- no matching doc file, (b) **enrichable** -- doc exists but session shows query params not present in the doc's `query_params` frontmatter list (status-code comparison is NOT used -- the doc schema has no structured status-code inventory), (c) **cross-profile enrichment** -- doc exists but was captured from a different profile (check `profiles.{profile}.status` in doc frontmatter), (d) **known** -- fully documented. Additionally classify by status code for priority signaling: 2xx = confirmed/capture-worthy, 304 = cached/known (endpoint exists but no response body), 401/403 = exists but needs auth, 404 = dead endpoint, 5xx = server error. Do NOT filter out non-2xx/3xx -- classify them instead.
3. **Presentation**: Present the operator with the categorized list from Phase 2 using the structured format defined in Phase 3 Format Spec below. Use sequential numbering across all categories so the operator can reference any item by number. Collapse KNOWN endpoints to a count only (full list available on request). Include priority signals (HIGH/MED/LOW) based on status code and coaching relevance. After presenting, ask the operator which endpoints to capture using the decision protocol defined in Phase 3→4 Decision Protocol below.
4. **Selective Capture**: First, check credential freshness (profile-dependent):
   - **Web profile**: Run `bb creds check --profile web`. If API health shows `[XX]`, run `bb creds refresh --profile web` first. No JWT decode needed -- the CLI handles token management.
   - **Mobile profile**: Read `GAMECHANGER_ACCESS_TOKEN_MOBILE` from `.env` and decode the JWT: split on `.`, take the second segment, pad with `=` to valid base64, URL-safe base64 decode, JSON parse, read `exp` (Unix epoch), compare against current time. Use `python3 -c` via Bash tool. If expired, stop and tell the operator immediately.

   **Data-first approach**: For each chosen endpoint, check if the session's endpoint-log contains a non-empty `response_body` for that path (richer format sessions only). Selection rule: among all JSONL entries matching the normalized template, prefer the largest non-empty 2xx `response_body` by byte length; ties broken by earliest timestamp; if no 2xx with non-empty body, skip data-first for this endpoint. If a qualifying entry exists, save the body directly to `data/raw/` with a filename reflecting the normalized endpoint path (e.g., `schedule-sample.json`); overwrite if exists. Apply PII redaction per `/.claude/rules/api-docs.md`. Save ONLY `response_body` -- never save `request_headers` which contain live credentials.

   **Curl fallback** (when no response data available): profile-dependent.
   - **Web profile**: Route to `ingest-endpoint` per endpoint (operator captures individual curls from browser). Quick-capture batch mode is NOT available for web -- web access tokens are never persisted to `.env`, so generating curl templates would require displaying the live token, violating the "never display gc-token" security invariant.
   - **Mobile profile**: For single endpoints, reference `ingest-endpoint`. For multiple endpoints, offer the quick-capture sub-mode with shell-variable-based curl templates (see Quick-Capture Curl Format below).

   **Post-capture action** (applies to both data-first saves and curl responses): After each endpoint's response is saved to `data/raw/`, the agent documents it in `docs/api/endpoints/` following the `ingest-endpoint` skill's documentation procedure (create or update endpoint file, validate frontmatter, update README index if new). Process endpoints serially -- if a 401 or auth error comes back, stop immediately and report. For 304 responses, note that a fresh sample requires cache-busting curl headers (omit `If-None-Match`, `If-Modified-Since`). Note which header profile to use based on the session's profile.
5. **Session Marking**: After the operator is done (including when they chose "skip" in the decision protocol), offer to mark the session as reviewed via `bb proxy review mark <session-id>`.

### Endpoint-Log Format

Two format versions exist. Detect by checking for `response_body` key in the first JSONL entry.

**Legacy format** (2026-03-07 and earlier):
```
timestamp, method, host, path, query_keys, request_content_type, response_content_type, status_code, source
```

**Richer format** (2026-03-12 and later):
```
timestamp, method, host, path, query_keys, request_content_type, response_content_type,
status_code, source, query_params (dict), request_headers (full dict), response_headers (full dict),
request_body (string), response_body (string)
```

The richer format enables direct data extraction: `response_body` contains the full response for ~45% of entries (the rest are empty for OPTIONS, 304s, auth errors, etc.). **Security**: `request_headers` contains live gc-token values -- never save or display this field.

### Phase 3 Format Spec

```
SESSION SUMMARY
Profile: web | mobile
Session: <session_id> (<date>)
Endpoints in log: <raw count> → <normalized count> after deduplication

UNKNOWN (N) — not yet documented
1. GET /teams/{team_id}/schedule              [HIGH: 200, coaching path]
2. POST /teams/{team_id}/lineup-suggestions   [HIGH: 200, coaching path]
3. GET /me/notifications                      [LOW: 200, non-coaching]
4. GET /teams/{team_id}/practice-plans        [MED: 404]

ENRICHABLE (N) — documented but new data found
5. GET /public/teams/{public_id}/games        [MED: new query param: include_playoffs]

CROSS-PROFILE (N) — doc exists but from different profile
6. GET /me/teams                              [MED: doc is mobile-only; this session is web]

KNOWN (N) — fully documented, nothing new
(collapsed — full list available on request)
```

Priority signal rules (mutually exclusive — apply first matching rule):
1. **HIGH**: status 2xx AND path contains a coaching keyword
2. **MED**: status 2xx but no coaching keyword, OR any non-2xx unknown endpoint, OR any enrichable/cross-profile endpoint
3. **LOW**: status 304, OR status 4xx/5xx on an unknown endpoint

Coaching keywords: lineup, schedule, stats, pitching, batting, spray, opponent, scout, season, roster, players, boxscore.

Priority signals appear on all UNKNOWN, ENRICHABLE, and CROSS-PROFILE items. KNOWN endpoints are collapsed to a count and have no signals. Numbering is sequential across all categories.

### Phase 3→4 Decision Protocol

After presenting the categorized list, ask:

> "Which endpoints would you like to capture? Options:
> - Numbers or ranges: `1`, `1 3 5`, `1-4`, `all`
> - Category shorthand: `all unknowns`, `all high`, `all 2xx unknowns`
> - `skip` or `none` — go directly to session marking without capture"

Interpretation: single number → one endpoint (reference `ingest-endpoint` for follow-up); multiple numbers/range/`all` → quick-capture sub-mode; `skip`/`none` → proceed to Phase 5 immediately. If the operator's response is ambiguous (e.g., partial path name), confirm the match before proceeding.

### Quick-Capture Curl Format (Mobile Profile Only)

Quick-capture batch mode is available ONLY for mobile profile sessions. Web profile sessions lack a persisted access token in `.env` -- generating curl templates would require displaying the live token, violating security invariants. For web sessions, the skill routes to `ingest-endpoint` per endpoint instead.

Templates use shell variable references for credentials -- never literal token values:

```bash
curl 'https://api.team-manager.gc.com/teams/aabb0011-ccdd-4eef-8899-ffeeddccbbaa/schedule' \
  -H "gc-token: $GAMECHANGER_ACCESS_TOKEN_MOBILE" \
  -H "gc-device-id: $GAMECHANGER_DEVICE_ID_MOBILE" \
  -H "User-Agent: Mozilla/5.0 ..."
```

Path parameters (team IDs, game IDs) use literal values from the session data -- these are not credentials. Only auth headers use shell variable references.

Before listing templates, instruct the operator to export credentials:
```bash
export GAMECHANGER_ACCESS_TOKEN_MOBILE=$(grep GAMECHANGER_ACCESS_TOKEN_MOBILE .env | cut -d= -f2)
export GAMECHANGER_DEVICE_ID_MOBILE=$(grep GAMECHANGER_DEVICE_ID_MOBILE .env | cut -d= -f2)
```
For the full post-capture procedure per endpoint, see Phase 4 in Workflow Phases.

### Security Invariants
- Same as `ingest-endpoint`: never display gc-token or gc-device-id values
- Raw responses go to `data/raw/` (gitignored)
- Credential values in endpoint docs use placeholders
- When saving from richer-format endpoint-log, save ONLY `response_body` -- never save or display `request_headers` (contains live gc-token values)
- Quick-capture curl templates (mobile only) use shell variable references (`$GAMECHANGER_ACCESS_TOKEN_MOBILE`, `$GAMECHANGER_DEVICE_ID_MOBILE`) -- never embed literal credential values

### Files Involved Across All Stories
- `.claude/skills/ingest-session/SKILL.md` (new)
- `CLAUDE.md` (Workflows section update)

## Open Questions
None -- all architectural questions resolved in Technical Notes. Expert consultation (CA + SE + CR + UXD) completed across two refinement passes, pre-dispatch. api-scout consultation intentionally skipped: auth behavior and endpoint patterns are well-documented in CLAUDE.md and `docs/api/`; no novel API questions in this epic.

## History
- 2026-03-07: Created. CA consultation attempted but PM lacks Task tool; architectural decisions derived from codebase analysis of existing skill patterns and proxy infrastructure.
- 2026-03-07: Refined with 12 items from post-formation expert review (CA: 7 items, SE: 3 items, user: 2 items). Key changes: (1) fast-path batch mode for multi-endpoint capture with serial execution, (2) concrete path normalization rules (UUID regex, public_id slugs, multi-param paths), (3) status code classification instead of filtering, (4) cross-profile enrichment category, (5) active session warning instead of hard refusal, (6) corrected endpoint-log size (hundreds of lines, not 25K), (7) endpoint_count field unreliable -- always read JSONL directly, (8) normalize-then-deduplicate before comparison, (9) 304 cache-busting guidance, (10) bb proxy endpoints output is unnormalized -- agent must read JSONL directly, (11) serial capture with stop-on-auth-failure, (12) JWT expiry pre-check before any API calls.
- 2026-03-13: Refinement pass with evaluation team (SE, CR, UXD). 14 findings incorporated (2 MUST FIX, 5 SHOULD FIX, 7 MINOR). Key changes: (1) data-first capture approach -- richer endpoint-log format (2026-03-12+) includes response_body, enabling direct data extraction without curl recapture; (2) endpoint_count is accurate (not a stub) -- removed all "unreliable" warnings; (3) structured Phase 3 presentation format with numbered items, priority signals, collapsed KNOWN category; (4) explicit Phase 3→4 decision protocol with number/range/category/skip inputs; (5) quick-capture curl templates use shell variable references instead of literal credentials; (6) fallback normalization with generic {id} placeholder for truly unknown paths; (7) explicit JWT decode steps (base64 middle segment, parse JSON, check exp); (8) source field clarification (values: "web"/"ios", NOT "mobile"; informational only, not used for profile detection); (9) endpoint count updated 89+ → 122; (10) empty session handling; (11) missing-symlink edge case; (12) AC wording tightened per CR review.
- 2026-03-13: Second refinement pass (Codex spec review). 6 findings (1 P1, 4 P2, 1 advisory). Key changes: (1) P1 -- web profile has no persisted access token; quick-capture batch mode restricted to mobile profile only; web sessions route to ingest-endpoint per endpoint; credential freshness check split by profile (bb creds check for web, JWT decode for mobile); (2) P2 -- data-first selection rule made deterministic: largest non-empty 2xx response_body by byte length, ties by earliest timestamp, else fall back to curl; (3) P2 -- enrichable category simplified to query-params-only (doc schema has no structured status-code inventory -- status codes used only for priority signaling); (4) P2 -- E-072-02 AC-3 sweep now enumerates specific files to inspect: CLAUDE.md, .claude/rules/dispatch-pattern.md, .claude/agents/*.md; (5) P2 -- endpoint comparison must exclude files with status: NOT_API in frontmatter (web-routes-not-api.md); count corrected to 119 actual endpoint docs (120 total files); (6) advisory -- api-scout consultation intentionally skipped, documented in Open Questions with rationale.
- 2026-03-13: Third refinement pass (Codex round 2). 4 P2 fixes: (1) AC-2 trigger list made closed/fixed -- removed "or similar" and "close variants" fallbacks; (2) env var naming standardized to actual `.env` names (`$GAMECHANGER_ACCESS_TOKEN_MOBILE`, `$GAMECHANGER_DEVICE_ID_MOBILE`) everywhere -- removed generic `$GC_TOKEN`/`$GC_DEVICE_ID` aliases; (3) endpoint count corrected 121→119 (120 total files minus web-routes-not-api.md); (4) Phase 5 `bb proxy review mark` → `bb proxy review mark <session-id>`.
- 2026-03-13: Fourth refinement pass (CR round 2 + Codex round 3). 18 combined findings triaged: 10 accepted, 5 dismissed, 3 already fixed. Key changes: (1) post-capture action added to Phase 4 -- after saving to data/raw/, document in docs/api/endpoints/ per ingest-endpoint procedure; (2) priority rubric made mutually exclusive with ordered first-match rules, signals scoped to UNKNOWN/ENRICHABLE/CROSS-PROFILE only, coaching keywords enumerated; (3) curl template example uses literal UUID (not shell variable for path params); (4) `--session argument` → natural language throughout; (5) web restriction reframed as security policy (not file-state assertion); (6) `all 2xx unknowns` added to decision protocol options; (7) DoD updated for context-only stories; (8) E-072-02 AC-3 reviewer guidance added. Dismissed: CR-4 (process-level structural fix out of scope), CR-5 (--session already fixed in round 3 epic.md), CR-6 false positive (grep confirmed already fixed), Cdx-P2-1 (endpoint_count discussed in Notes, not ACs), Cdx-P2-3 (skill implementer decides section structure).
