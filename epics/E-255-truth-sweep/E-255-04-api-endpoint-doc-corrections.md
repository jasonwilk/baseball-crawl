# E-255-04: `docs/api/` endpoint-doc accuracy corrections

## Epic
[E-255: Truth Sweep — Context Layer, API Docs, Runbooks](epic.md)

## Status
`TODO`

## Description
After this story is complete, the GameChanger endpoint docs under `docs/api/` are factually accurate: the boxscore IP self-contradiction is resolved, the public-games perspective-specific-id caveat is added, the README endpoint count + duplicate row are fixed, the post-search quirk gets a pointer, and the `game_stream.id` corrections + `team_season` shape fix are applied from the E-255-R-01 verified facts. PII is not reintroduced (byte-gate re-run).

## Context
api-scout owns `docs/api/**`. The CE-4 PII scrub of these files is DONE (E-254-07, archived) — this story is pure doc-accuracy on already-scrubbed files and MUST NOT reintroduce PII (re-run the byte-gate). The two live-verification items (game_stream.id, team_season shape) were settled in E-255-R-01 (main checkout, since a worktree cannot make authenticated GC calls — TN-6); this story applies them. Per API-doc fidelity (`.claude/agent-memory/product-manager/feedback_api_doc_endpoint_fidelity.md`): correct what the API factually OFFERS; do not degrade endpoint facts.

## Acceptance Criteria
- [ ] **AC-1** (A — pure): Given the boxscore doc's IP self-contradiction (L141 & L176 correctly say IP is float decimal innings; L170 wrongly says "IP is integer outs"), when resolved, then the doc states a single correct IP representation (float decimal innings; the loader converts to `ip_outs`), and L170 is fixed/removed.
- [ ] **AC-2** (B + E — pure): Given `get-public-teams-public_id-games.md` lacks the perspective-specific-id caveat (same real game → different `id` per team's schedule, per CLAUDE.md L21), when added, then the caveat is documented; and the "/games completed-only" claim is confirmed already-fixed (2026-06-12, predates audit) with the authenticated game-summaries completed-only claim left TRUE — recorded as a confirmation, no stray sites.
- [ ] **AC-3** (C — pure): Given `README.md` lists `/me/subscription-information` TWICE (L62 & L231) and the Completeness Check line ("121 files = 120 endpoint files + web-routes") is wrong two ways (the real count is 120 files, and the split is 119 endpoints + 1 `web-routes-not-api.md` NOT_API reference), when corrected, then the duplicate row is removed AND the Completeness Check line is REWRITTEN to read **"120 files (119 endpoints + 1 web-routes reference)"** — not a flat "120 endpoints" (that would introduce a fresh inaccuracy). **This exact phrasing is the canonical value CA's `api-docs.md` (E-255-02) must match** (also 4 flow docs: opponent-resolution, opponent-scouting, plays-ingestion, spray-chart-rendering).
- [ ] **AC-3b** (own-memory carve-out): Given api-scout's own `MEMORY.md` carries the same wrong endpoint count, when corrected, then it reads the same "120 files (119 endpoints + 1 web-routes reference)" phrasing (own-memory edit under the carve-out; part of this story since api-scout owns it).
- [ ] **AC-4** (D — pure): Given `post-search.md` omits the punctuation/curly-apostrophe zero-hit quirk, when a Known-Limitations POINTER to `gc-uuid-bridge.md` is added (a pointer, not a restatement — the exact-failure claim is not fully reproducible), then the doc references the quirk without duplicating its detail.
- [ ] **AC-5** (F — apply from R-01): Given the game-summaries doc's `game_stream.id` at 5 sites (L37/39/52/114/142-143) + the opponent-scouting Authenticated Fallback, when corrected to the E-255-R-01 verified ACTUAL behavior (the `/game-stream-processing/{id}/…` form takes the SAME id for boxscore AND plays — contradicting L52's "different UUIDs" — and TWO plays URL forms exist), then all 5 sites and the fallback name the correct id/URL for each endpoint.
- [ ] **AC-5b** (F cross-file sweep — was under-scoped): Given the `game_stream.id`/`event_id` routing claim spans ~12 `docs/api` files (not just the 5 game-summaries sites) and the dedicated plays doc `get-game-stream-processing-event_id-plays.md` ALREADY contradicts game-summaries L52 today, when a grep-driven sweep of ALL `docs/api` `game_stream.id`/`event_id` routing claims is reconciled against R-01's verified fact, then no `docs/api` file contradicts another on which id each endpoint takes (a grep for the routing claim across `docs/api` shows one consistent story). If E-073 is archived (see E-255-06), this cross-file sweep MUST land here — it does not fall between epics.
- [ ] **AC-6** (G — apply from R-01; CORRECTED target file): Given the `team_season` shape lives in **`get-public-teams-public_id.md`** (the `GET /public/teams/{public_id}` doc — NOT the UUID→public_id bridge doc `get-*public-team-profile*.md`, which has no `team_season`), when corrected to the E-255-R-01 verified shape (cached sample: `season` a bare string, `year` flat at `team_season.year`), then that doc matches ground truth and the verified shape is the one CA applies to testing.md + data-model.md (E-255-01/02). Also check `get-athlete-profile` + season-stats docs for the same stale `team_season.season.year` nesting and correct any found.
- [ ] **AC-7**: Given the corrections touch files CE-4 already scrubbed, when the story completes, then `scripts/check_doc_pii.sh docs/api` passes (no PII reintroduced).

## Technical Approach
Verify pure corrections (A–E) against proxy captures (`proxy/data/`) / cached samples per `feedback_consult_proxy_data`. Apply F & G from `.project/research/E-255-verified-facts.md` (E-255-R-01). Establish/confirm the count as "120 files (119 endpoints + 1 web-routes reference)" so E-255-02 can cite the exact phrasing. Re-run the doc-PII byte-gate before done.

## Dependencies
- **Blocked by**: E-255-R-01 (verified game_stream.id per-endpoint params + team_season shape)
- **Blocks**: E-255-02 (canonical count phrasing "120 files (119 endpoints + 1 web-routes reference)" + verified team_season shape for testing.md)

## Files to Create or Modify
**Conflict-isolation basis:** E-255-04 is the SOLE story in this epic that touches `docs/api/**` — it owns the entire tree. No other story can conflict regardless of which `docs/api` files the AC-5b sweep resolves, so the exact file set does not need to be frozen at planning time; the named files below are the confirmed targets, and AC-5b's grep-driven sweep defines its own additional set at execution (this is the story's litmus: a discovery sweep whose OUTPUT is the file list).
- `docs/api/README.md` (AC-3: count + duplicate row)
- `docs/api/endpoints/get-teams-team_id-game-summaries.md` (AC-5: `game_stream.id` sites)
- `docs/api/endpoints/get-game-stream-processing-game_stream_id-boxscore.md` (AC-1: IP contradiction; AC-5: boxscore id)
- `docs/api/endpoints/get-game-stream-processing-event_id-plays.md` (AC-5/AC-5b: plays id — already contradicts game-summaries L52 today)
- `docs/api/endpoints/get-public-teams-public_id-games.md` (AC-2: perspective-id caveat)
- `docs/api/endpoints/post-search.md` (AC-4: quirk pointer)
- `docs/api/endpoints/get-public-teams-public_id.md` (AC-6: the `team_season` shape lives HERE — corrected from the wrong `get-*public-team-profile*.md` bridge doc)
- `docs/api/flows/opponent-scouting.md` (AC-5: Authenticated Fallback)
- **AC-5b discovery sweep** — the `game_stream.id`/`event_id` routing-claim subset of `docs/api` (a PM grep found 41 files mention the tokens; api-scout's semantic pass narrows to the ~12 that make a boxscore/plays ROUTING claim — that narrowed set IS AC-5b's output and is edited to one consistent story). Candidate additions surfaced by the grep include `get-teams-team_id-schedule.md`, `get-events-event_id.md`, `get-events-event_id-best-game-stream-id.md`, `get-game-streams-game_stream_id-events.md`, and the flows `plays-ingestion.md` — api-scout confirms the routing-claim subset at execution.
- **AC-6 secondary check** — `get-athlete-profile`/`get-teams-team_id-season-stats.md` (+ any other doc) for the same stale `team_season.season.year` nesting; correct any found.
- `.claude/agent-memory/api-scout/MEMORY.md` (AC-3b: same count fix, own-memory carve-out)

## Agent Hint
api-scout

## Handoff Context
- **Produces for E-255-02**: canonical count phrasing "120 files (119 endpoints + 1 web-routes reference)" for `.claude/rules/api-docs.md`; the verified `team_season` shape for testing.md.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] F & G applied from the R-01 artifact (not re-verified in the worktree)
- [ ] `scripts/check_doc_pii.sh docs/api` passes
- [ ] Canonical count phrasing "120 files (119 endpoints + 1 web-routes reference)" communicated to CA (E-255-02); api-scout MEMORY.md count fixed (AC-3b)

## Notes
Confirm exact endpoint filenames by listing `docs/api/endpoints/`. E-073 (API Documentation Validation Sweep, READY) covers a systematic validation of the same layer — the PM triage in E-255-06 addresses the overlap; do not duplicate a full E-073-style sweep here.
