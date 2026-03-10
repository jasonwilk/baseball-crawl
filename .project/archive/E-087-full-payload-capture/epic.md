# E-087: Full Payload Capture in Endpoint Logger

## Status
`COMPLETED`

## Overview
Extend the mitmproxy endpoint logger addon to capture complete request/response payloads (bodies, headers, query parameter values) so that api-scout and other agents can build a full picture of API responses from session data alone -- without needing live API calls. Additionally, evolve the API documentation standards to incorporate request/response payload examples with PII-safe placeholder conventions.

## Background & Context
The current `proxy/addons/endpoint_logger.py` deliberately omits bodies, query parameter values, and headers -- logging only lightweight metadata (method, host, path, query key names, content-types, status code, timestamp, source). This was originally conservative, but the session data files (`proxy/data/sessions/`) are gitignored, local-only, and secured. The operator wants full payload capture so proxy sessions become a complete API reference source.

Separately, the API endpoint documentation in `docs/api/endpoints/` currently has an inconsistent approach to example JSON -- some files include real team names, real city names, and real UUIDs in example responses (e.g., `get-me-teams.md` shows "Lincoln Rebels 14U", "Lincoln", and real UUIDs). The PII pre-commit hook catches credentials but not team names or other identifying data in documentation. The API doc rules (`.claude/rules/api-docs.md`) and ingest-endpoint skill (`.claude/skills/ingest-endpoint/SKILL.md`) need guidance on safe placeholder values for committed example JSON.

**Expert consultation**: SE consulted on storage format (inline vs. sidecar files, size thresholds, auth header stripping) for E-087-01. API scout consulted on PII taxonomy completeness, GC API response patterns, and ingest-endpoint workflow impact for E-087-02. Claude-architect consulted on context-layer file placement, ingest-endpoint skill integration, and .env.example structure for E-087-02. All answers incorporated into Technical Notes below.

## Goals
- Proxy session endpoint logs contain complete request/response data (bodies, headers, query values) for all JSON-bearing GC API traffic
- Binary content types are skipped; oversized bodies are truncated with a clear sentinel
- Auth tokens are captured unfiltered by default (session store is secured); stripping is configurable via `PROXY_STRIP_AUTH_HEADERS`
- API documentation rules and ingest-endpoint skill include PII-safe placeholder guidance so committed example JSON never contains real team names, player names, cities, or unredacted UUIDs
- API documentation rules evolve to expect request body and response payload examples as standard sections

## Non-Goals
- Redesigning the JSONL log format or switching to a database-backed log
- Modifying `proxy-endpoints.sh` or `proxy-report.sh` (they read only existing fields and are unaffected by new fields)
- Retroactively sanitizing existing endpoint doc files (that is a separate sweep)
- Adding query parameter values to the existing `query_keys` field (a new `query_params` field captures the full key-value mapping; `query_keys` is retained for backward compatibility)

## Success Criteria
- A proxy session capturing GC web traffic produces JSONL entries with inline request/response bodies, headers (unfiltered by default), and full query parameters
- Bodies exceeding 2MB are truncated with a `"<truncated: N bytes>"` sentinel
- Binary content types (image/*, video/*, application/octet-stream) produce no body in the log entry
- All existing tests still pass; new tests cover the expanded entry format
- `.claude/rules/api-docs.md` and `.claude/skills/ingest-endpoint/SKILL.md` include PII-safe placeholder taxonomy and request/response example guidance

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-087-01 | Capture full payloads in endpoint logger | DONE | None | SE |
| E-087-02 | API doc standards for payload examples and PII-safe placeholders | DONE | None | CA |

## Dispatch Team
- software-engineer
- claude-architect

## Technical Notes

### SE Consultation Results (2026-03-09)

**Storage format**: Inline. Bodies go directly into the JSONL entry as string fields. Sidecar files add coordination complexity for no real gain. `jq` handles fat lines fine. Binary-skip eliminates worst cases. One line = one complete request/response pair (atomic).

**Size threshold**: 2MB cap via `MAX_BODY_BYTES` module-level constant, overridable via environment variable. Truncated bodies get a sentinel string `"<truncated: {N} bytes>"` (where N is the original byte count) so analysts know data was cut, not absent. Never silently drop.

**Auth header stripping**: Configurable via `.env`. Three env vars control behavior:
- `PROXY_CAPTURE_BODIES` -- `true` (default) enables full payload capture (bodies, headers, query values). `false` reverts to metadata-only mode (backward compatible with current behavior).
- `PROXY_STRIP_AUTH_HEADERS` -- `true` enables denylist-based stripping of sensitive headers. `false` (default) captures all headers unfiltered. The session store is gitignored and secured, so the default is no filtering.
- `MAX_BODY_BYTES` -- body size cap (default 2MB). Bodies exceeding this are truncated with a sentinel.

Sensitive header denylist (when stripping is enabled): `gc-token`, `gc-device-id`, `authorization`, `gc-signature`, `cookie`, `set-cookie`. Normalize to lowercase before matching.

**Test updates needed** (per SE):
- `_make_flow` helper needs extending with `request_body`/`response_body` (and `request_headers`/`response_headers`) params
- `test_entry_contains_exactly_expected_keys` needs updating for the expanded key set
- `test_no_body_data_in_entry` and `test_query_keys_sorted_and_no_values` need replacement with tests that verify the new fields ARE present

### PII Safety Taxonomy for API Doc Examples

Committed API doc files (`docs/api/endpoints/*.md`) must use clearly fake/redacted data in example JSON. Taxonomy of safe placeholder values:
- **Team names**: `"Example Team 14U"`, `"Anytown Eagles 12U"`
- **Organization/league names**: `"Example Organization"`, `"Example League"`
- **Cities/States**: `"Anytown"`, `"XX"` (or generic like `"Springfield"`, `"IL"`)
- **Venue/field names**: `"Anytown Field"`, `"Example Park"`
- **Person names (players, coaches, staff, parents)**: `"Jane Doe"`, `"Player One"`
- **Phone numbers**: `"+1 (555) 555-0100"` or `"+15550001234"`
- **UUIDs**: Redact to `"72bb77d8-REDACTED"` or `"00000000-0000-0000-0000-000000000001"`. This rule applies to ALL UUID fields regardless of field name (`id`, `stream_id`, `event_id`, `game_stream_id`, `player_uuid`, `team_id`, `opponent_id`, etc.) and when UUIDs appear as dict keys (e.g., player-stats keyed by player UUID).
- **Dates**: Keep realistic but not identifying (any recent date is fine)
- **Emails**: use `example.com` domain placeholders
- **public_id slugs**: `"xXxXxXxXxXxX"` or similar clearly fake values
- **url_encoded_name**: `"2024-spring-example-team-14u"` (these encode real team identity)
- **Avatar/media URLs**: `"https://media-service.gc.com/example-avatar-url"` (signed URLs may embed identifiers)
- **Scores/stats**: Keep realistic numeric values (these are not PII)
- **Jersey numbers**: NOT PII (visible on any game broadcast) -- keep as-is
- **Boolean flags, enum values**: NOT PII -- keep as-is

**Semi-identifying combinations**: Avoid preserving exact win-loss records (e.g., `"61-29-2"`) that could identify a specific team. Use generic records (e.g., `{"wins": 12, "losses": 8, "ties": 0}`). Avoid combining a specific `season_year + age_group + competition_level` that matches a real team's history -- replace with a generic recent year.

**Redaction scope**: PII redaction applies to BOTH request body AND response body examples in endpoint documentation.

The PII pre-commit hook catches credentials but not team names or cities. The documentation rules and ingest-endpoint skill are the enforcement point for this guidance.

### SE Implementation Guidance (2026-03-09 refinement review)

**mitmproxy API behavior**:
- mitmproxy transparently decompresses gzip/deflate bodies before the `response` hook fires. `flow.response.content` is always decoded bytes. No special decompression handling needed.
- Chunked transfer encoding is reassembled automatically. `flow.response.content` is the complete body.
- Streaming responses may have `content = b""` -- this returns an empty string body, which is acceptable.

**Empty body handling (AC-3)**: `flow.request.content` is `b""` for GET requests (no body). Decoding gives `""` (empty string), not `None`. The implementation must explicitly check `not flow.request.content` and emit `null` in the JSONL entry, not an empty string.

**Safe decode strategy**: All `.decode()` calls on `flow.request.content` and `flow.response.content` must use `errors="replace"` to handle non-UTF-8 bytes gracefully (e.g., partially gzipped bodies, binary content that slipped past the content-type filter).

**`MAX_BODY_BYTES` env var validation**: Guard `int(os.environ.get(...))` with a try/except. On invalid values, fall back to the 2MB default and log a warning.

**Binary content-type matching (AC-8)**: Use prefix matching (`startswith`) for `image/` and `video/` since content types include subtypes (e.g., `image/png`, `video/mp4`). Match `application/octet-stream` exactly.

**Header multidict serialization**: `dict(flow.request.headers)` produces a plain dict with lowercase keys. Duplicate header names (e.g., multiple `set-cookie`) keep only the last value. This is acceptable for diagnostic logs.

**AC-11 key-set test**: Must have two variants -- one asserting the expanded key set in capture mode (`PROXY_CAPTURE_BODIES=true`), one asserting the original key set in metadata-only mode (`PROXY_CAPTURE_BODIES=false`).

**Test replacements needed**:
- `test_no_body_data_in_entry` → replace with `test_body_null_for_get_request` + `test_body_captured_for_post_request`
- `test_query_keys_sorted_and_no_values` → the `"true" not in json.dumps(entry)` assertion will fail once `query_params` contains the value `"true"`. Replace with `test_query_params_contains_full_key_value_mapping` and keep `test_query_keys_sorted_alphabetically`.
- Add a test for truncation sentinel format: verify `response_body == "<truncated: N bytes>"` when body exceeds threshold.

**Response body storage format**: Response bodies are stored as raw strings, not re-parsed to JSON objects, to avoid double-parse complexity. Downstream consumers use `jq -r '.response_body | fromjson'` when structured access is needed.

**Session file size impact**: Full payload capture produces significantly larger session files (~50-100MB for a typical crawl session vs. kilobytes for metadata-only). Session files are gitignored and local-only.

### Backward Compatibility

The `query_keys` field is retained in the JSONL entry for backward compatibility with any tooling that reads it. A new `query_params` field (dict) captures the full key-value mapping. Both fields coexist.

### Context-Layer Placement Guidance (2026-03-09 refinement review)

**api-docs.md**: New "Example JSON Safety" section goes after the existing YAML Frontmatter Schema section (currently the last section). Add a cross-reference sentence in the existing Accuracy Standard section pointing to the new section.

**ingest-endpoint skill**: PII redaction step goes in Phase 1 between step 3 (verify credential safety) and step 4 (document the endpoint). "Example Request Body" template section goes between Headers and Response in the Markdown Body Template. Add "Omit if method is GET or no request body" annotation, consistent with the existing pattern for optional sections.

**Ingest workflow clarification**: For POST/PATCH endpoints, the saved raw response in `data/raw/` is the RESPONSE body only. The request body is documented in the endpoint file, not saved as a separate raw artifact.

**Dual-path workflow note**: The ingest-endpoint skill has two entry paths: (1) live curl execution (time-sensitive -- gc-signature expires within minutes, execute promptly) and (2) session replay (body already captured from proxy session data in `proxy/data/sessions/`, no curl execution needed). PII redaction applies equally to both paths -- the source of the example JSON does not affect the redaction obligation. This is an implementation note for the CA implementer when inserting the redaction step.

### Env Var Threading

The proxy's `docker-compose.yml` uses `env_file: ../.env` (with `required: false`). All vars from the project root `.env` are available inside the mitmproxy container automatically. The new `PROXY_CAPTURE_BODIES`, `PROXY_STRIP_AUTH_HEADERS`, and `MAX_BODY_BYTES` vars require no additional `docker-compose.yml` changes. Code-level defaults handle the case where vars are absent.

## Open Questions
None.

## History
- 2026-03-09: Created. SE consulted on storage format (inline, 2MB cap, denylist). User provided additional requirements for API doc evolution and PII safety.
- 2026-03-09: User override -- no header filtering by default (session store is secured). Auth header stripping made configurable via `PROXY_STRIP_AUTH_HEADERS` env var (default: off). Full payload capture toggleable via `PROXY_CAPTURE_BODIES` (default: on).
- 2026-03-09: Full refinement review with PM, SE, API scout, and claude-architect. SE confirmed all 13 ACs implementable, added implementation guidance (empty body handling, safe decode, env var validation, mitmproxy API notes, test replacement details). API scout expanded PII taxonomy (org/league names, venue names, avatar URLs, url_encoded_name, UUID-as-key, jersey numbers, semi-identifying combos). Architect confirmed clean context-layer integration and provided precise placement guidance. PM confirmed READY status. Added new env vars to `.env.example` and `.env` (Proxy Capture section).
- 2026-03-10: Refinement team review. PM identified missing .env.example AC -- added AC-14 to E-087-01. Added SE Implementation Guidance notes on raw string storage format and session file size impact. Added `.env.example` to E-087-01 Files to Create or Modify.
- 2026-03-10: All stories DONE. E-087-01 approved by code-reviewer (round 2 after extracting `_build_capture_fields` helper to satisfy 50-line limit). SHOULD FIX: `_build_entry` at exactly 50 lines (1 over strict limit) -- not blocking. E-087-02 verified directly (context-layer-only). Documentation assessment: trigger 5 fires (new env vars for proxy behavior) -- docs-writer to update `docs/admin/mitmproxy-guide.md`. Context-layer assessment: trigger 1 yes (already satisfied by E-087-02 in-scope); triggers 2-6 no. Epic marked COMPLETED.
