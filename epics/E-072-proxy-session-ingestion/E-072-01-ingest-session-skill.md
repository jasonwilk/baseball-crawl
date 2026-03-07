# E-072-01: Create ingest-session Skill File

## Epic
[E-072: Proxy Session Ingestion Skill](epic.md)

## Status
`TODO`

## Description
After this story is complete, a new skill file exists at `.claude/skills/ingest-session/SKILL.md` that defines the full workflow for processing a mitmproxy proxy session -- from reading session data, through endpoint comparison, to guiding the operator through selective raw data capture. The skill is self-contained and follows the established skill file format used by `ingest-endpoint`, `implement`, and other existing skills.

## Context
The operator captures GameChanger traffic through mitmproxy sessions. Today, there is no automated way to compare a session's captured endpoints against the 89+ documented endpoints and identify what is new. This skill bridges that gap: it reads proxy session data, normalizes endpoint paths, compares against `docs/api/endpoints/`, and presents unknown endpoints to the operator for selective investigation.

The skill is the primary deliverable of E-072. It builds on extensive existing infrastructure: proxy session files (`proxy/data/sessions/*/`), the `bb proxy` CLI commands, the HTTP layer's dual-profile support, and the `ingest-endpoint` skill for single-endpoint follow-up.

## Acceptance Criteria
- [ ] **AC-1**: Given the file `.claude/skills/ingest-session/SKILL.md` does not exist, when this story is complete, then the file exists with a complete skill definition following the established format (Activation Triggers, Purpose, Prerequisites, Phases, Security Invariants, Anti-Patterns, Edge Cases sections).
- [ ] **AC-2**: Given the skill's Activation Triggers section, when a user says "ingest session", "process proxy session", "what's new in the proxy session", or similar trigger phrases, then the triggers clearly match these inputs.
- [ ] **AC-3**: Given the skill's Phase 1 (Session Discovery), when the executing agent reads the skill, then it knows to: (a) locate the latest proxy session via the `proxy/data/current` symlink or accept a `--session` argument, (b) read `session.json` for profile auto-detection, (c) check session status -- if `status == "active"`, present a warning about partial data risk and let the operator decide whether to proceed (NOT a hard refusal), (d) read `endpoint-log.jsonl` directly (typically a few hundred lines per session) and filter to API-host requests only (host = `api.team-manager.gc.com`), (e) exclude OPTIONS preflight requests but retain ALL status codes (do not filter by status code -- classify instead), (f) do NOT rely on `endpoint_count` from `session.json` (it is a stub that shows 0).
- [ ] **AC-4**: Given the skill's Phase 2 (Endpoint Comparison), when the executing agent reads the skill, then it knows to: (a) list all files in `docs/api/endpoints/` to build a known-endpoints set, (b) normalize captured endpoint paths using concrete rules: UUID segments matching 8-4-4-4-12 hex pattern become parameter placeholders (e.g., `{team_id}`, `{game_stream_id}`); short alphanumeric slugs in `/public/teams/` or `/teams/public/` paths become `{public_id}`; multi-parameter paths normalize ALL parameter positions (e.g., `/teams/{team_id}/opponent/{opponent_id}`), (c) deduplicate normalized paths before comparison (50+ raw paths may collapse to one template), (d) resolve ambiguous normalizations by matching against existing doc filenames, (e) convert normalized paths to the doc file naming convention (`{method}-{path-segments}.md`), (f) classify each endpoint as: unknown (no doc file), enrichable (doc exists but session shows new query params or status codes), cross-profile enrichment (doc exists but captured from different profile -- check `profiles.{profile}.status` in frontmatter), or known (fully documented), (g) classify by status code: 2xx = confirmed/capture-worthy, 304 = cached/known (no response body), 401/403 = exists but needs auth, 404 = dead, 5xx = server error.
- [ ] **AC-5**: Given the skill's Phase 3 (Presentation), when the executing agent reads the skill, then it knows to present: (a) a categorized list of unknown, enrichable, cross-profile enrichment, and known endpoints with hit counts and status codes, (b) the session profile (web/mobile) and its implications for header selection, (c) a clear recommendation for which unknowns are highest priority (based on 2xx responses, unique paths, coaching-relevant path segments), (d) cross-profile enrichment opportunities presented separately.
- [ ] **AC-6**: Given the skill's Phase 4 (Selective Capture), when the executing agent reads the skill, then it knows to: (a) decode the `gc-token` JWT and check the `exp` claim before making ANY API calls -- if expired, stop and tell the operator immediately, (b) for single endpoints, reference the `ingest-endpoint` skill (`.claude/skills/ingest-endpoint/SKILL.md`), (c) for multiple endpoints, offer a "quick-capture" sub-mode that lists curl templates for all chosen 2xx unknowns and the operator pastes them one at a time, (d) process endpoints serially -- if a 401 or auth error comes back, stop immediately and report rather than continuing, (e) for 304 responses, note that a fresh sample requires cache-busting curl headers (omit `If-None-Match`, `If-Modified-Since`), (f) note which header profile to use based on the session's profile.
- [ ] **AC-7**: Given the skill's Phase 5 (Session Marking), when the executing agent reads the skill, then it knows to offer marking the session as reviewed via `bb proxy review mark <session-id>`.
- [ ] **AC-8**: Given the skill's Security Invariants section, when the executing agent reads the skill, then it finds the same credential safety rules as `ingest-endpoint`: never display gc-token/gc-device-id values, raw responses to `data/raw/`, placeholder values in docs.
- [ ] **AC-9**: Given the skill's Anti-Patterns section, when the executing agent reads the skill, then it includes at minimum: (a) do not auto-fetch all unknown endpoints without operator selection, (b) do not modify proxy session files, (c) do not skip the endpoint comparison phase, (d) do not attempt to run proxy lifecycle commands from the devcontainer, (e) do not fetch multiple endpoints in parallel -- always serial with stop-on-auth-failure, (f) do not treat `bb proxy endpoints` output as normalized data -- always read JSONL directly and normalize in-agent, (g) do not rely on `endpoint_count` from `session.json`.

## Technical Approach
The skill file follows the established format from existing skills at `.claude/skills/*/SKILL.md`. Key reference files for the implementer:

- **Existing skill to model format after**: `.claude/skills/ingest-endpoint/SKILL.md` -- same domain (API endpoint ingestion), two-phase workflow pattern
- **Proxy session data format**: `proxy/data/sessions/*/session.json` (JSON with session_id, profile, status, reviewed fields), `proxy/data/sessions/*/endpoint-log.jsonl` (JSONL with timestamp, method, host, path, query_keys, status_code, source fields)
- **Endpoint doc naming convention**: `docs/api/README.md` (index), `.claude/rules/api-docs.md` (file naming spec and frontmatter schema)
- **BB CLI proxy commands**: `src/cli/proxy.py` (endpoints, report, review, refresh-headers subcommands)
- **HTTP profiles**: `src/http/headers.py` (BROWSER_HEADERS for web, MOBILE_HEADERS for mobile)
- **Proxy boundary rule**: `.claude/rules/proxy-boundary.md` (what agents can and cannot do with proxy)

The implementer should read the existing `ingest-endpoint` skill in full to understand the format conventions (section ordering, instruction block formatting, security invariant placement). The new skill is complementary: `ingest-session` processes a whole session and identifies unknowns; `ingest-endpoint` handles individual endpoint deep-dives.

Path normalization is the key technical challenge. The endpoint-log contains concrete paths with real UUIDs and public_ids (e.g., `/teams/abc12345-def6-7890-abcd-ef1234567890/schedule`, `/public/teams/a1GFM9Ku0BbF/games`). These must be mapped to the parameter-templated paths used in doc filenames (e.g., `/teams/{team_id}/schedule`). Concrete normalization rules are defined in the epic Technical Notes: UUID regex (8-4-4-4-12 hex), public_id slug patterns, multi-parameter path handling. After normalization, paths must be deduplicated before comparison -- a session may have 50+ raw paths that collapse to a single template. The skill should document these rules clearly so the executing agent can apply them.

**Important**: The `bb proxy endpoints` command outputs raw, unnormalized paths (literal UUIDs). The skill must explicitly instruct the executing agent to read the `endpoint-log.jsonl` JSONL directly and perform its own normalization -- not use `bb proxy endpoints` output as the normalized set.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-072-02 (context layer registration depends on skill file existing)

## Files to Create or Modify
- `.claude/skills/ingest-session/SKILL.md` (create)

## Agent Hint
claude-architect

## Handoff Context
- **Produces for E-072-02**: The skill file at `.claude/skills/ingest-session/SKILL.md` -- E-072-02 needs the activation trigger phrases from this file to write the CLAUDE.md Workflows entry.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Skill file follows established format conventions
- [ ] No regressions in existing tests (no code changes expected, but verify no accidental edits)

## Notes
- The endpoint-log JSONL is typically a few hundred lines per session (427 lines in the 2026-03-07 session). A full file read is appropriate -- no need for streaming or chunked reads.
- The `proxy/data/current` symlink points to the active session directory. If the session is still active (status = "active" in session.json), the skill should present a warning about partial data and let the operator decide -- NOT hard-refuse (a crashed proxy may leave a permanently "active" session).
- `endpoint_count` in `session.json` is a stub field (shows 0 despite hundreds of log entries). Always read the JSONL directly.
- `bb proxy endpoints` output is unnormalized (raw UUID paths). The executing agent must read the JSONL and normalize itself.
