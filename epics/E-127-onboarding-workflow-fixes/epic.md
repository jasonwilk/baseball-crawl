# E-127: Onboarding Workflow Fixes

## Status
`READY`
<!-- Lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED) -->

## Overview
Fix the workflow gaps that make post-reset developer onboarding and first crawl painful: credential import only accepts curl commands (not raw tokens), `bb creds extract-key` picks the wrong key from bundles with multiple matches, the admin UI is undiscoverable from the dashboard, the dev user bypass creates a user with no team assignments, the crawler processes placeholder teams from seed data, the mobile profile requests brotli compression that the runtime can't decompress, the dashboard defaults to a hardcoded season that doesn't match teams with data in other seasons, and navigation between dashboard tabs drops season context. Together these force the operator to manually parse JWTs, regex-edit `.env`, write SQL INSERTs, guess URLs, construct query parameters by hand, and debug encoding errors just to get a working local environment after `bb db reset`.

## Background & Context
During a real-world reseed-and-crawl session (2026-03-18), four friction points emerged:

1. **Credential import**: The operator had raw token JSON (from a proxy capture or browser devtools) but `bb creds import` only accepts curl commands. They had to manually decode the JWT, determine token type (access vs refresh), and hand-edit `.env`. Additionally, `bb creds extract-key` extracted the mobile client ID instead of the web one because GC's JS bundle now contains two `EDEN_AUTH_CLIENT_KEY` entries and the regex returns the first match (mobile).

2. **Admin UI discoverability**: The admin UI at `/admin/teams` has a fully implemented two-phase add-team flow -- but there is no link to `/admin` anywhere in the main navigation or dashboard. The operator went to manual SQL because they couldn't find the admin UI. The bottom coaching nav (Batting/Pitching/Games/Opponents) also renders on admin pages, creating confusing context.

3. **User-team assignment**: The `DEV_USER_EMAIL` bypass in `src/api/auth.py` auto-creates a user row on first request but inserts zero rows into `user_team_access`. The app shows "You have no team assignments" and the operator must manually INSERT to get access.

4. **Crawl failures** (discovered during crawl testing after addressing points 1-3): The crawler's `--source db` path processes all active member teams including those with placeholder gc_uuids from seed data (e.g., `lsb-varsity-uuid-2026`), which hit the GC API and return 500. Real teams with valid gc_uuids get HTTP 200 for roster/schedule but crash with `'utf-8' codec can't decode byte` because the mobile profile headers request brotli compression (`br;q=1.0`) while neither `brotli` nor `brotlicffi` is installed. Additionally, all 17 boxscore fetches fail with HTTP 500 "Cannot find event" because the game stats crawler uses `game_stream.id` as the boxscore endpoint path parameter when the endpoint actually expects `event_id`.

**Expert consultation findings** (2026-03-18):
- **SE**: Confirmed `bb creds refresh` access token non-persistence is by design (access tokens are short-lived, ~60min, intentionally memory-only; TokenManager always fetches fresh via refresh token at startup). Identified `extract-key` bug: `.search()` returns first of multiple `EDEN_AUTH_CLIENT_KEY` matches in the bundle.
- **DE**: Confirmed no schema changes needed. Flagged that user creation + team assignment must be in the same transaction (atomic), and `INSERT OR IGNORE` should be used for idempotency. Noted known constraint: teams added after dev user creation won't auto-grant (acceptable).
- **UXD**: Identified the core discoverability blocker: no `/admin` link exists in the main nav or dashboard. Also flagged: empty-state "Contact your administrator" message should link admins to `/admin/users`, coaching bottom nav renders on admin pages (confusing), and "Add Team" button placement.
- **coach**: Season selector must use human-readable labels (not raw IDs), include a stale-data indicator when viewing prior-season data, and show game counts for thin seasons. Season selector must work for both own-team and opponent views without hard-coding batting-first assumptions.
- **api-scout**: Confirmed POST /auth response JSON shape for token import. Noted undocumented `user_id` top-level field that parser must tolerate. Corroborated SE's multi-match finding for `EDEN_AUTH_CLIENT_KEY`. Confirmed admin UI add-team flow already handles team lookup correctly (`/me/teams` returns both UUID and `public_id` for member teams; `public_id` alone suffices for tracked opponents).

## Goals
- Operator can import credentials from raw token JSON, bare JWT strings, or curl commands via a single `bb creds import` command
- `bb creds extract-key` correctly selects the web client key when multiple keys exist in the JS bundle
- Admin UI is discoverable from the main dashboard navigation
- After `bb db reset` + app start, the dev user is automatically assigned to all member teams
- Crawler skips placeholder teams from seed data instead of sending invalid UUIDs to the API
- Mobile profile brotli responses decompress correctly (brotlicffi installed; headers match real iOS app)
- Boxscore crawler uses the correct ID (`event_id`) for the boxscore endpoint
- Game loader matches boxscore files to summaries regardless of naming key
- Scouting crawler uses the correct Accept header for the public games endpoint
- Scouting load step processes completed crawl runs (not just running ones)
- Dashboard auto-detects the most recent season with data for the selected team
- Season context persists across Batting/Pitching/Games/Opponents navigation
- Operator knows the post-reset workflow (documented in admin guide)

## Non-Goals
- Mobile credential import (mobile profile has separate complexities; out of scope)
- Changing seed data to include real GC identifiers (seed data is for testing, not production seeding)
- Full admin UI/UX redesign (only the critical discoverability fixes)
- Persisting access tokens to `.env` in `bb creds refresh` (by design: access tokens are short-lived and TokenManager handles refresh at startup)

## Success Criteria
- `bb creds import` accepts a bare JWT string or a JSON object containing tokens, auto-detects the format, and writes the correct env vars to `.env`
- `bb creds extract-key` logs all matches and selects the web client key when GC bundles contain multiple `EDEN_AUTH_CLIENT_KEY` entries
- A link to `/admin` is visible in the main navigation bar
- A fresh `bb db reset` + app start + first page load creates a dev user who can see all member teams without manual SQL
- `bb data crawl --source db` skips teams with NULL or placeholder gc_uuids with warning logs
- `brotlicffi` is installed and mobile profile crawling succeeds with brotli-compressed responses
- Boxscore fetches succeed using `event_id` (no more "Cannot find event" errors)
- Game loader indexes summaries by both `event_id` and `game_stream_id` for robust boxscore file matching
- Scouting crawler fetches opponent schedules without HTTP 415 errors (correct Accept header)
- `bb data scout` load step finds and processes completed crawl runs without manual intervention
- Dashboard shows data for any team regardless of season, auto-detecting the correct season when none is specified
- Season labels are human-readable (e.g., "Spring 2025"), not raw backend IDs
- When viewing a prior season, a visible indicator warns that current-season data hasn't been loaded yet
- All dashboard nav links carry `season_id`, so switching tabs does not lose season context
- `docs/admin/post-reset-guide.md` documents the end-to-end workflow

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-127-01 | `bb creds import` multi-format input | TODO | None | - |
| E-127-02 | `bb creds extract-key` multi-match disambiguation | TODO | None | - |
| E-127-03 | Dev user auto-assignment to member teams | TODO | None | - |
| E-127-04 | Admin nav discoverability | TODO | None | - |
| E-127-05 | Post-reset onboarding guide | TODO | None | - |
| E-127-06 | Crawler skips placeholder teams | TODO | None | - |
| E-127-07 | Install brotlicffi for mobile brotli decompression | TODO | None | - |
| E-127-08 | Boxscore crawler uses wrong ID + loader dual-key index | TODO | None | - |
| E-127-09 | Scouting crawler public games Accept header | TODO | None | - |
| E-127-10 | Scouting loader skips completed crawl runs (both paths) | TODO | None | - |
| E-127-11 | Season selector UX design | TODO | None | - |
| E-127-12 | Season selector implementation | TODO | E-127-11, E-127-04 | - |

## Dispatch Team
- software-engineer
- docs-writer
- ux-designer
- api-scout

### Dispatch Sequencing
- E-127-04 must be **merged before** E-127-12 begins implementation. Both stories modify `base.html` and dashboard templates. The dependency is declared (E-127-12 depends on E-127-04) but dispatch must enforce sequential execution: dispatch E-127-04 first, merge it, then dispatch E-127-12.
- E-127-05 (docs) should be **dispatched last** or reviewed after E-127-01/02/03/04 merge, since the guide references their behavior.
- E-127-01 and E-127-02 both modify `src/cli/creds.py` but in different regions (~500 lines apart: `import_creds` at L74 vs `extract_key` at L616). Safe to dispatch in parallel -- worktree merges handle non-overlapping edits.
- E-127-09 is routed to **api-scout** (not SE) because AC-2 modifies `docs/api/endpoints/` files. api-scout owns `docs/api/`.
- All other stories (01-03, 06-11) can run in parallel.

## Technical Notes

### TN-1: Token Format Detection for `bb creds import`

The import command should auto-detect input format without requiring new flags. Detection heuristic (applied to the stripped input string):

1. **Curl command**: Starts with `curl ` (case-insensitive). Route to existing `parse_curl()` pipeline.
2. **JSON object**: Starts with `{`. Parse as JSON. Expected shapes:
   - GC auth response: `{"type": "token", "access": {"data": "jwt...", "expires": N}, "refresh": {"data": "jwt...", "expires": N}}` -- always contains `type: "token"` at top level; may also contain an undocumented top-level `user_id` field; the parser must tolerate extra top-level fields
   - Simple token map: `{"access_token": "jwt...", "refresh_token": "jwt..."}`
   - Single token: `{"token": "jwt..."}`
3. **Bare JWT**: Contains two `.` separators and no whitespace before the first `.` (three dot-separated base64url segments). Decode the payload to determine token type (`type: "user"` = access token, no `type` field = refresh token) using the existing JWT inspection logic in `credential_parser.py`.
4. **File fallback**: If none of the above match and `--file` was specified, try reading the file and re-detecting.

For JSON and bare JWT inputs, the profile routing logic from the existing curl parser applies: web profile stores refresh tokens as `GAMECHANGER_REFRESH_TOKEN_WEB`; access tokens are only stored for mobile profile as `GAMECHANGER_ACCESS_TOKEN_MOBILE`.

### TN-2: Extract-Key Multi-Match Bug

`key_extractor.py` uses `_EDEN_KEY_PATTERN.search()` which returns the first match. GC's JS bundle now contains multiple `EDEN_AUTH_CLIENT_KEY` entries (web and mobile). The fix should:
1. Use `findall()` instead of `search()` to capture all matches
2. Log all discovered composite values (redacted -- show only the UUID portion, not the key)
3. Select the correct key by matching the UUID against the known web client ID (`GAMECHANGER_CLIENT_ID_WEB` from `.env`). If `GAMECHANGER_CLIENT_ID_WEB` is not set and multiple keys are found, present all candidates with their UUIDs and exit without writing -- no silent heuristic (see AC-3 in E-127-02)

### TN-3: Dev User Auto-Assignment

In `src/api/auth.py`, `_create_dev_user()` currently creates a user row and returns. After user creation, it should also:
1. Query `SELECT id FROM teams WHERE membership_type = 'member'`
2. `INSERT OR IGNORE INTO user_team_access(user_id, team_id)` for each member team
3. The INSERT must be in the same transaction as user creation (atomic)

Additionally, handle the case where a dev user already exists but has zero team assignments (from a prior reset). If `_get_permitted_teams()` returns an empty list and the user was loaded (not just created), auto-assign and re-query. This handles the "reset DB but keep .env" scenario where the user row survives but assignments don't.

**Known constraint**: Teams added to the database after the dev user is created will not be auto-granted. This is acceptable -- the backfill path (empty permitted_teams triggers re-assignment) covers the most common case. A full solution would require checking on every request, which is unnecessary overhead for a dev-only feature.

### TN-4: Admin Nav Discoverability

The main navigation bar (`base.html`) has no link to `/admin`. The bottom fixed nav renders coaching pages (Batting/Pitching/Games/Opponents) on all pages including admin.

Fixes:
1. Add an "Admin" link to the top navigation bar in `base.html`, visible to all users (admin access is gated by Cloudflare Access in production; in dev, all routes are accessible)
2. Admin templates should suppress or replace the bottom coaching nav with admin-specific navigation (the admin sub-nav with Users/Teams/Opponents already exists in admin templates)
3. The dashboard empty-state "You have no team assignments. Contact your administrator." message should include a link to `/admin/teams` when the user is in dev mode (detectable via `DEV_USER_EMAIL` being set)

### TN-6: Crawler Placeholder Team Guard

`load_config_from_db()` in `src/gamechanger/config.py` queries all active member teams with no filter on `gc_uuid` validity. The seed data contains teams with placeholder gc_uuids (e.g., `lsb-varsity-uuid-2026`) that aren't real UUIDs. The `gc_uuid or str(row["id"])` fallback in the list comprehension compounds the problem -- NULL gc_uuids fall back to the integer PK string.

The fix should:
1. Filter out teams where `gc_uuid IS NULL` (these have no API identity)
2. Validate that non-NULL gc_uuid values match UUID v4 format before including them
3. Log a warning for each skipped team (team name + reason)

The SQL filter (`WHERE gc_uuid IS NOT NULL`) is preferred over post-query Python filtering because it reduces the result set at the source. The UUID format validation catches seed placeholders that aren't NULL but aren't real UUIDs.

### TN-7: Brotli Decompression Failure

The mobile profile headers in `src/http/headers.py` request `Accept-Encoding: br;q=1.0, gzip;q=0.9, deflate;q=0.8` (brotli preferred). This matches the real iOS GameChanger app (confirmed via proxy session data across all captured iOS sessions). Neither `brotli` nor `brotlicffi` is installed. When GC sends a brotli-compressed response, httpx cannot decompress it. The raw compressed bytes are then passed to `response.text` / `response.json()`, which fails with `'utf-8' codec can't decode byte` because compressed bytes aren't valid UTF-8.

Fix: Install `brotlicffi~=1.0` in `requirements.in` and regenerate `requirements.txt` via `pip-compile`. httpx auto-detects brotlicffi when installed and handles brotli decompression transparently. The `python:3.13-slim` Docker base image works with brotlicffi wheels -- no Dockerfile or devcontainer.json changes needed. Headers MUST NOT be modified -- they must match real app behavior per the HTTP discipline rule.

### TN-8: Boxscore Endpoint ID Mapping

The boxscore endpoint `GET /game-stream-processing/{id}/boxscore` expects `event_id` from game-summaries records. The game stats crawler (`src/gamechanger/crawlers/game_stats.py`) incorrectly extracts `game_stream.id` instead. The module docstring's "CRITICAL ID MAPPING" section (lines 15-21) explicitly -- and incorrectly -- documents this wrong mapping.

From the game-summaries response:
- `event_id` -- the correct path parameter for the boxscore endpoint
- `game_stream.id` -- a different identifier (NOT the boxscore path parameter)
- `game_stream.game_id` -- equals `event_id` (confirmed in the existing comment, line 20)

**Two boxscore ID contexts**:
- **Authenticated flow** (`game_stats.py`): Uses `event_id` from game-summaries. The crawler was using `game_stream.id` -- this is the bug.
- **Public/scouting flow** (`scouting.py`): Uses `game.get("id")` from the public `/games` endpoint. This `id` field is the public-endpoint equivalent of `event_id` and is correct. No fix needed.

**Loader dual-key index**: Once the crawler uses `event_id` for boxscore file naming, the game loader (`src/gamechanger/loaders/game_loader.py`) must index game summaries by both `event_id` and `game_stream_id` so that file-to-summary matching works. The `_build_summaries_index()` method stores each `GameSummaryEntry` under both keys.

### TN-9: Scouting Public Games Accept Header

The scouting crawler's `_PUBLIC_GAMES_ACCEPT` constant was set to `application/vnd.gc.com.event:list+json; version=0.1.0`, which the public games endpoint rejects with HTTP 415 Unsupported Media Type. The correct vendor media type is `application/vnd.gc.com.public_team_schedule_event:list+json; version=0.0.0`. Both the type name and version differ from the original value.

### TN-10: Scouting Loader Status Query Bug

`_find_scouting_run()` in `src/cli/data.py` (line 304-309) queries `scouting_runs WHERE status = 'running'`. The crawl step (`ScoutingCrawler.scout_team()`) marks runs as `completed` before the load step executes, so the query always returns zero rows and the load step silently skips every team. Fix: broaden the query to `status IN ('running', 'completed')`.

**Second instance**: `_load_all_scouted()` at line ~382 has the same `status = 'running'` filter on a different query (the multi-team `bb data scout` path). Both functions must be fixed.

**Timestamp format note**: The repo consistently uses ISO `T`-separator format (`strftime('%Y-%m-%dT%H:%M:%fZ', 'now')` in SQL, `.strftime("%Y-%m-%dT%H:%M:%S.000Z")` in Python). Both sides match. Maintain this format -- do not switch to space-separator format.

### TN-11: Season Selector

The dashboard's season fallback is hardcoded to `f"{current_year}-spring-hs"` (lines 100-102, 234-235, 343-344, 520-521 in `src/api/routes/dashboard.py`). This fails for teams with data in other seasons. Two problems:

1. **No auto-detection**: No query exists to find which seasons have data for a given team. The fallback should query the database (e.g., `SELECT DISTINCT season_id FROM player_season_batting WHERE team_id = ? UNION SELECT DISTINCT season_id FROM player_season_pitching WHERE team_id = ?`) and pick the most recent.

2. **Season context lost on navigation**: The bottom nav in `base.html` links to `/dashboard/games`, `/dashboard/pitching`, etc. without `season_id`. Templates never reference `season_id` in link generation. All dashboard links must carry the current `season_id`.

E-127-12 depends on both E-127-11 (UX design) and E-127-04 (admin nav -- both touch `base.html` and dashboard templates).

### TN-5: Post-Reset Workflow

The documented workflow after `bb db reset`:

1. `bb db reset` -- wipes and reseeds the database with placeholder data
2. `docker compose up -d --build app` -- starts the app
3. Navigate to `http://localhost:8000/admin/teams` (now discoverable via the Admin link in the nav)
4. Use "Add Team" to paste a GameChanger team URL (e.g., `https://web.gc.com/teams/XXXXXX/schedule`)
5. The two-phase flow resolves the team name, gc_uuid, and public_id automatically
6. Set membership type (member for your teams, tracked for opponents)
7. On first dashboard visit, the dev user is auto-assigned to all member teams (per TN-3)
8. Run `bb data crawl` (or equivalent) to pull real data

## Open Questions
- None remaining.

## History
- 2026-03-18: Created from post-reset onboarding pain point analysis
- 2026-03-18: Revised after SE, DE, and UXD consultation findings. Dropped access token persistence story (by design per SE). Added extract-key multi-match story (SE finding). Added admin nav discoverability story (UXD finding). Incorporated DE transaction/idempotency guidance into TN-3.
- 2026-03-18: Incorporated api-scout findings. Added undocumented `user_id` field tolerance to TN-1 JSON parsing. Api-scout corroborated extract-key multi-match and confirmed admin UI team lookup is correct.
- 2026-03-18: Added E-127-06 (crawler placeholder team guard) and E-127-07 (brotli decompression fix) from crawl testing findings. Added TN-6 and TN-7.
- 2026-03-18: Corrected E-127-07 root cause -- not non-UTF-8 characters in player names but missing brotli decompressor for mobile Accept-Encoding header. Rescoped from client.py encoding fix to headers.py one-line fix.
- 2026-03-18: Added E-127-08 (boxscore wrong ID). game_stats crawler uses `game_stream.id` but endpoint expects `event_id`. All 17 boxscore fetches failed. Added TN-8.
- 2026-03-18: Post-crawl/scout testing refinement. Added E-127-09 (scouting Accept header -- HTTP 415 on public games endpoint). Expanded E-127-08 to include game loader dual-key index (boxscore files named by `event_id` must match summaries indexed by `game_stream_id`). Clarified TN-8: scouting crawler's boxscore ID usage is correct (public `id` = authenticated `event_id`); only authenticated flow was broken. Added TN-9.
- 2026-03-18: Added E-127-10 (scouting loader skips completed runs). `_find_scouting_run()` queries `status = 'running'` but crawl step already set `completed` before load runs. Blocks entire scouting load path. Added TN-10.
- 2026-03-18: Added E-127-11 (season selector UX design) and E-127-12 (season selector implementation). Dashboard defaults to hardcoded `{year}-spring-hs`, failing for teams with data in other seasons. Nav links drop season context. E-127-12 depends on E-127-11 and E-127-04. Added ux-designer to Dispatch Team. Added TN-11.
- 2026-03-18: Full-team refinement session (SE, DE, UXD, coach, CA, api-scout). 17 findings incorporated. Followed by Codex spec review (10 findings triaged: 4 refined, 2 fixed, 2 dismissed, 1 removed, 1 added dispatch note). Key Codex-driven changes: E-127-01 AC-1b added for convenience JSON formats; E-127-02 AC-3 tightened (no silent heuristic); E-127-11 AC-5 pinned artifact path; E-127-12 season label format aligned to "Spring 2025" (season-first); E-127-10 timestamp note corrected (repo uses ISO T-format, not space-separator); coach added to consultation audit trail; E-127-05 dispatch-last note added; E-127-01/02 creds.py dispatch awareness note added. Original 17 findings: E-127-10 expanded to cover second `_load_all_scouted()` bug instance + timestamp format warning; E-127-07/08/09 annotated with pre-implementation status; E-127-09 AC-2 expanded to fix stale `id` field description in public games endpoint doc; E-127-04 ACs tightened (is_admin_page default, specific styling); E-127-11 ACs added for human-readable labels, stale-data indicator, game count, own-team/opponent view compatibility; E-127-12 ACs refined (season selector on 4 main tabs only, back link persistence, expanded test coverage, data freshness indicator); E-127-05 AC-3 expanded to include extract-key; TN-1 updated with `type: "token"` field; TN-10 expanded; dispatch sequencing note added. No new stories, no migrations, no context-layer changes needed.
- 2026-03-18: Proxy data refinement round. E-127-07 fully rescoped: proxy sessions confirm iOS sends brotli Accept-Encoding across all captures. Fix changed from "remove br from headers" to "install brotlicffi~=1.0". Headers must match real app behavior (see feedback memories). E-127-02 updated with client ID rotation finding (iOS client ID rotates with app updates, e.g., 0f18f027→23e37466 between Odyssey 2026.8.0→2026.9.0). TN-7 rewritten. Goals, Success Criteria, and story title updated to match new approach. Bonus findings (web Accept-Encoding gap, iOS user-agent version drift) captured as vision signals.
- 2026-03-18: Second fresh-eyes refinement (SE, DE, UXD, coach, CA, api-scout). 13 findings, 11 applied: (1) E-127-09 Agent Hint changed from SE to api-scout -- SE anti-patterns prohibit editing `docs/api/`; api-scout added to Dispatch Team; (2) E-127-10 AC-1 corrected to `IN ('running', 'completed')` matching TN-10; (3) TN-2 heuristic fallback removed to align with E-127-02 AC-3; (4) E-127-11 AC-7 expanded with stale-data indicator copy spec per coach; (5) E-127-11 AC-8 expanded with opponent "scouted" qualifier per coach; (6) E-127-12 AC-2 adds single-season suppression; (7) E-127-12 season_display suffix list expanded (`-reserve`, `-legion`, graceful unknown); (8) E-127-01 AC-6 adds `user_id` tolerance test + `--profile mobile` JSON; (9) E-127-04 AC-4 clarifies right-side placement; (10) E-127-04 test spec adds dev-mode empty-state test; (11) E-127-08 AC-3 expanded to cover all stale references + Pre-Impl Status flags game_loader module docstring; (12) E-127-09 AC-2 expanded to name all 3 locations in public games doc. Deferred: CLAUDE.md `game_stream_id` description update -- handle at epic closure context-layer assessment.
