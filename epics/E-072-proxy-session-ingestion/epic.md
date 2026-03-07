# E-072: Proxy Session Ingestion Skill

## Status
`READY`

## Overview
Create a new workflow skill that processes an entire mitmproxy session -- identifying unknown endpoints, comparing against documented endpoints, and orchestrating bulk raw data capture with profile-aware headers. This gives the operator a single trigger phrase ("ingest session") to go from a completed proxy capture to documented endpoints and raw data, replacing a manual multi-step process.

## Background & Context
Today, the operator captures web/mobile traffic through mitmproxy sessions on their Mac host. After a session ends, there is no automated way to:
1. Compare captured endpoints against the 89+ documented endpoints in `docs/api/endpoints/`
2. Identify genuinely new/unknown endpoints from the session
3. Bulk-fetch raw responses while tokens are still fresh
4. Handle the web vs. mobile profile distinction for headers

The existing `ingest-endpoint` skill (`.claude/skills/ingest-endpoint/SKILL.md`) handles ONE endpoint at a time from a manually-placed curl command. This epic creates a broader session-level skill that can process all unknowns from a proxy session.

**Expert consultation**: Claude Architect and Software Engineer both reviewed the initial spec post-formation. CA provided 7 items (fast-path batch mode, concrete normalization rules, status code classification, cross-profile enrichment, active session gate, endpoint-log size correction, endpoint_count unreliability). SE assessed all 7 and added 3 (deduplicate normalized paths, 304 cache-busting guidance, bb proxy endpoints limitation). User added 2 (serial capture execution, JWT expiry pre-check). All 12 items incorporated into this revision.

Key existing infrastructure this epic builds on:
- **Proxy session data**: `proxy/data/sessions/*/endpoint-log.jsonl` (JSONL with method, path, status_code, source, query_keys), `session.json` (profile, status, reviewed fields)
- **BB CLI proxy commands**: `bb proxy endpoints`, `bb proxy report`, `bb proxy review` (shell script wrappers)
- **HTTP layer**: `src/http/headers.py` (BROWSER_HEADERS, MOBILE_HEADERS), `src/http/session.py` (create_session with profile param)
- **Existing ingest-endpoint skill**: Two-phase workflow (api-scout executes curl, claude-architect integrates) for single endpoints
- **Endpoint docs**: 89+ files in `docs/api/endpoints/` with YAML frontmatter, validated by `scripts/validate_api_docs.py`

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

**Profile auto-detection from session metadata.** The `session.json` file has a `profile` field (values: "web", "mobile"). The endpoint-log JSONL has a `source` field per entry (same values). The skill auto-detects profile from `session.json` and uses it to determine which header set (BROWSER_HEADERS vs MOBILE_HEADERS) is relevant. No operator input needed for profile determination.

**Selective capture with fast-path batch mode.** Token freshness is a concern (gc-signature in POST requests expires within minutes; gc-token lasts 14 days). The skill presents the list of unknown endpoints and lets the operator choose which to fetch. For single endpoints, the operator uses the standard `ingest-endpoint` follow-up. For multiple endpoints, the skill offers a "quick-capture" sub-mode: it lists curl templates for all chosen 2xx unknown endpoints at once, and the operator pastes them one at a time in series. This reduces per-endpoint ceremony while keeping the operator in the loop. Endpoints are processed serially (not in parallel) so that if a 401 or other auth failure comes back, the operator can stop immediately rather than wasting time on remaining endpoints.

**Endpoint comparison logic.** The skill compares session endpoints against `docs/api/endpoints/` using the file naming convention: `{method}-{path-segments-with-params-as-words}.md`. Path parameters are normalized using concrete rules: UUID segments matching the 8-4-4-4-12 hex pattern (e.g., `aabb0011-ccdd-4eef-8899-ffeeddccbbaa`) become their placeholder names (`{team_id}`, `{game_stream_id}`, etc.); short alphanumeric slugs in `/public/teams/` or `/teams/public/` paths become `{public_id}`. Multi-parameter paths (e.g., `/teams/{team_id}/opponent/{opponent_id}`) must normalize ALL parameter positions. After normalization, paths are deduplicated before comparison -- a session with 50+ raw `/teams/{id}/opponent/{id}` paths should collapse to a single template. Ambiguous normalizations are resolved by matching against existing doc filenames. Non-API hosts (e.g., `web.gc.com`) and OPTIONS preflight requests are filtered out. The comparison yields: (1) known endpoints (already documented), (2) unknown endpoints (no matching doc file), (3) endpoints with new status codes or query params not in existing docs, (4) cross-profile enrichment candidates (doc exists but was captured from a different profile than the current session -- checked via the doc's `profiles.{profile}.status` field).

**Skill file location.** `.claude/skills/ingest-session/SKILL.md` -- follows the established pattern.

**Integration with bb CLI.** The skill may reference `bb proxy endpoints` for operator convenience, but the executing agent MUST NOT treat its output as the normalized endpoint set. `bb proxy endpoints` (via `proxy-endpoints.sh`) outputs raw, unnormalized paths with literal UUIDs. The agent must read the `endpoint-log.jsonl` JSONL directly and perform its own normalization and deduplication. No new bb commands needed.

### Workflow Phases (for skill design)

1. **Session Discovery**: Read the latest (or specified) proxy session. Auto-detect profile from `session.json`. Check session status: if `status == "active"`, present a clear warning about partial/in-progress data and let the operator decide whether to proceed or wait (do NOT hard-refuse -- a crashed proxy may leave a permanently "active" session). Filter endpoint-log to API requests only (host = `api.team-manager.gc.com`, method != OPTIONS). Read the JSONL directly (typically a few hundred lines per session -- 427 lines in the 2026-03-07 session; a full file read is appropriate). Do NOT rely on `endpoint_count` from `session.json` (it shows 0 despite hundreds of log entries -- it is a stub field).
2. **Endpoint Comparison**: Normalize filtered endpoint paths (replace UUIDs/IDs with parameter placeholders per the normalization rules in Architectural Decisions). Deduplicate normalized paths. Compare deduplicated set against `docs/api/endpoints/` listing. Classify each endpoint into one of these categories: (a) **unknown** -- no matching doc file, (b) **enrichable** -- doc exists but session shows new query params or status codes, (c) **cross-profile enrichment** -- doc exists but was captured from a different profile (check `profiles.{profile}.status` in doc frontmatter), (d) **known** -- fully documented. Additionally classify by status code: 2xx = confirmed/capture-worthy, 304 = cached/known (endpoint exists but no response body), 401/403 = exists but needs auth, 404 = dead endpoint, 5xx = server error. Do NOT filter out non-2xx/3xx -- classify them instead.
3. **Presentation**: Present the operator with the categorized list from Phase 2. For each category, include hit counts and status codes from the session. Note the session profile (web/mobile) and its implications for header selection. Recommend which unknowns are highest priority (2xx responses, unique paths, coaching-relevant path segments). Present cross-profile enrichment opportunities separately.
4. **Selective Capture**: Before making any API calls, decode the `gc-token` JWT and check the `exp` claim. If the token is expired, stop and tell the operator immediately -- do not proceed with capture. For single endpoints, reference the `ingest-endpoint` skill for the standard workflow. For multiple endpoints, offer a "quick-capture" sub-mode: list curl templates for all chosen 2xx unknown endpoints, and the operator pastes them one at a time in series. Process endpoints serially -- if a 401 or auth error comes back, stop immediately and report rather than continuing with remaining endpoints. For 304 responses, note that the endpoint exists but a fresh sample requires cache-busting curl headers (omit `If-None-Match`, `If-Modified-Since`). Note which header profile to use based on the session's profile.
5. **Session Marking**: After the operator is done, offer to mark the session as reviewed via `bb proxy review mark`.

### Security Invariants
- Same as `ingest-endpoint`: never display gc-token or gc-device-id values
- Raw responses go to `data/raw/` (gitignored)
- Credential values in endpoint docs use placeholders

### Files Involved Across All Stories
- `.claude/skills/ingest-session/SKILL.md` (new)
- `CLAUDE.md` (Workflows section update)

## Open Questions
None -- all architectural questions resolved in Technical Notes. Expert consultation (CA + SE) completed post-formation, pre-dispatch.

## History
- 2026-03-07: Created. CA consultation attempted but PM lacks Task tool; architectural decisions derived from codebase analysis of existing skill patterns and proxy infrastructure.
- 2026-03-07: Refined with 12 items from post-formation expert review (CA: 7 items, SE: 3 items, user: 2 items). Key changes: (1) fast-path batch mode for multi-endpoint capture with serial execution, (2) concrete path normalization rules (UUID regex, public_id slugs, multi-param paths), (3) status code classification instead of filtering, (4) cross-profile enrichment category, (5) active session warning instead of hard refusal, (6) corrected endpoint-log size (hundreds of lines, not 25K), (7) endpoint_count field unreliable -- always read JSONL directly, (8) normalize-then-deduplicate before comparison, (9) 304 cache-busting guidance, (10) bb proxy endpoints output is unnormalized -- agent must read JSONL directly, (11) serial capture with stop-on-auth-failure, (12) JWT expiry pre-check before any API calls.
