# E-174: Fix Key Extractor to Search Asset Chunks

## Status
`READY`
<!-- Lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED) -->

## Overview
Fix `bb creds extract-key` to search code-split asset chunks when the `EDEN_AUTH_CLIENT_KEY` is no longer inlined in the index bundle. As of ~2026-03-25, GameChanger moved the env config object into a code-split asset chunk (`/assets/*.js`), causing the extractor to fail. The existing regex is correct -- it just needs to search additional JS files.

## Background & Context
`src/gamechanger/key_extractor.py` extracts the `EDEN_AUTH_CLIENT_KEY` composite value from the GC web JavaScript bundle. It fetches the homepage HTML, finds the `<script src="...static/js/index.*.js...">` tag, downloads that bundle, and regex-extracts the key.

Around 2026-03-25, GC restructured their JS build. The index bundle now contains a variable reference (`$4.EDEN_AUTH_CLIENT_KEY`) instead of the inline string value. The actual composite value (`uuid:key`) is in one of ~19 code-split asset chunks loaded via `<link rel="modulepreload" href="/assets/*.js">` tags. The chunk name includes a content hash that rotates with each GC deploy (likely Vite/Rollup convention), and the key could move to a different chunk in future deploys.

The fix is to add a fallback: when the index bundle doesn't contain the inline key, search the asset chunks sequentially until the key is found.

No expert consultation required for baseball-coach or data-engineer -- this is pure credential infrastructure with no coaching data, schema, or API behavior impact. SE consulted for technical validation of the implementation approach. api-scout confirmed the key is a JS build-time constant that only appears in JS bundles (not HTML, API responses, or service workers).

## Goals
- `bb creds extract-key` succeeds against the current live GC site
- Backward compatible: if GC moves the key back to the index bundle, the extractor still works (index bundle tried first)
- `ExtractedKey.bundle_url` reflects the actual file the key was found in

## Non-Goals
- Parallel chunk fetching (sequential with early exit is sufficient for ~19 chunks)
- Caching chunk contents across invocations
- Detecting or handling the variable-reference form (`$4.EDEN_AUTH_CLIENT_KEY`) in the index bundle
- Changes to the `bb creds setup web` flow (it calls `extract_client_key()` which this epic fixes)
- Searching source maps, service workers, or other non-bundle JS files

## Success Criteria
- `bb creds extract-key` returns a valid key from the live GC site
- All existing tests continue to pass
- New tests cover: key in index bundle (existing), key in asset chunk (fallback), key missing everywhere (error), multi-chunk early exit

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-174-01 | Add asset chunk fallback to key extractor | TODO | None | - |

## Dispatch Team
- software-engineer

## Technical Notes

### Current Architecture
- `_find_bundle_url(html)` -- finds the index bundle URL via `_BUNDLE_SRC_PATTERN` (matches `static/js/index.*.js`)
- `_fetch_bundle(client, url)` -- downloads any JS URL, returns text (reusable for asset chunks without modification)
- `_find_composites(js)` -- regex-extracts all `EDEN_AUTH_CLIENT_KEY:"..."` values; raises `KeyExtractionError` if none found
- `_parse_composite(composite, url)` -- splits `uuid:key` composite, attaches bundle_url for traceability
- `extract_client_key(known_client_id)` -- orchestrates the full flow; handles multi-key disambiguation

### Fallback Strategy
1. Fetch the GC homepage HTML (unchanged).
2. Try the index bundle first (current behavior). If `_find_composites()` succeeds, return as today.
3. If the index bundle has no inline key (`_find_composites()` raises `KeyExtractionError`), fall back to asset chunks.
4. Discover asset chunk URLs from the HTML via a new helper.
5. Fetch each chunk sequentially, run `_find_composites()` on each. Stop at first success.
6. If no chunk contains the key, raise `KeyExtractionError` with an updated message indicating the number of chunks searched.

### Index Bundle Graceful Degradation
If the index bundle `<script>` tag is not found in the HTML at all (page structure changed completely), the extractor should still attempt asset chunk discovery before raising. This handles the case where GC removes the index bundle pattern entirely in a future deploy.

### Asset Chunk Discovery
The HTML contains `<link rel="modulepreload" href="/assets/*.js">` tags and potentially `<script src="/assets/*.js">` tags. A new helper should extract JS URLs from both patterns under the `/assets/` path. The chunk naming convention is `{name}-{hash}.js` (Vite/Rollup). The hash portion rotates per deploy; the name portion is semi-stable but should not be relied upon for filtering.

### Error Handling in Fallback Loop
- `_find_composites()` raises `KeyExtractionError` when no key is found in a chunk -- catch this per-chunk and continue to the next.
- `_fetch_bundle()` raises `KeyExtractionError` on network errors -- log and skip the chunk rather than aborting. A single unreachable chunk should not prevent finding the key in another.
- Log each chunk URL as it is fetched (DEBUG level) and log which chunk the key was found in (INFO level).

### HTTP Client Scope
The `httpx.Client` context manager in `extract_client_key()` currently closes before composites are parsed. For the fallback path, the client must remain open for asset chunk fetches. The `with httpx.Client(...)` block needs to encompass the entire search sequence (index bundle + fallback chunks).

### Documentation Assessment Note: docs/api/auth.md Update
`docs/api/auth.md` references `static/js/index.{hash}.js` as the key location (lines 278-279 and manual extraction steps 5-7). After this epic, the key may appear in `/assets/*.js` chunks instead. Flag for documentation assessment at epic closure -- the manual DevTools instructions still work (global search finds the key regardless of file) but should note the key may appear in either location. `docs/api/auth.md` is owned by api-scout per `/.claude/rules/documentation.md`.

## Open Questions
- None

## History
- 2026-03-28: Created (DRAFT)
- 2026-03-28: Set to READY after review

### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 -- CR spec audit | 3 | 3 | 0 |
| Internal iteration 1 -- Holistic team | 3 | 3 | 0 |
| Codex iteration 1 | 2 | 2 | 0 |
| **Total** | **8** | **8** | **0** |

Key changes from review: AC-5/AC-8 conflict resolved (AC-8 revised to acknowledge test updates), AC-7 (httpx scope) and AC-9 (test discovery) moved from ACs to Technical Approach and Definition of Done respectively, AC-4 strengthened with early-exit verification, documentation assessment note corrected from context-layer routing, module docstring update added to Technical Approach.
