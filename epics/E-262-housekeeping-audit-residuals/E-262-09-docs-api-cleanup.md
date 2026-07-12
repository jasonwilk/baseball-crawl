# E-262-09: docs/api Cleanup

## Epic
[E-262: Post-Program Housekeeping](epic.md)

## Status
`TODO`

## Description
After this story is complete, three `docs/api/` consistency items are cleared: the `/game-stream-processing/` endpoint-doc path-variable naming is normalized to `event_id`, the opponent-scouting flow doc's stat list is reconciled to the actual schema, and the `age_group` field doc records the free-text range form.

## Context
Three api-scout fold-in items over `docs/api/` (api-scout owns `docs/api/**`):
- **IDEA-107 (path-variable rename):** sibling endpoint files name the `/game-stream-processing/{id}/` path variable inconsistently — `get-game-stream-processing-game_stream_id-boxscore.md` uses `{game_stream_id}` while `get-game-stream-processing-event_id-plays.md` uses `{event_id}` — even though BOTH endpoints take `event_id` (verified: `game_stream.id` returns HTTP 500 on both). E-255-04 fixed the PROSE routing claims but left the coupled filename + frontmatter `path:` placeholder + `see_also` link rename. Do it atomically (file rename + frontmatter + all inbound `see_also` refs across `docs/api/`, including `README.md`) so no half-renamed state is left.
- **IDEA-022 (scouting-flow stat mismatch):** `docs/api/flows/opponent-scouting.md` lists stats not present in the actual database schema (the doc describes what the API returns; the schema stores a subset). DE's ratified recommendation is to FIX THE DOC (correct it to what we actually store, flagging any genuinely missing stats as future analytics work) rather than expand the schema. The flow itself is live (the reports pipeline still uses it), so correct the doc — do not delete it.
- **IDEA-126 companion doc note:** `docs/api/endpoints/get-public-teams-public_id.md` documents `age_group` only via the `14U` example. The free-text `"Between 13 - 18"` range form is a real observed value (api-scout live-confirmed) and should be added to that field's description. (The code half of IDEA-126 is story 03; this is only the doc note — no shared file.)

## Acceptance Criteria
- [ ] **AC-1**: Given the `/game-stream-processing/` boxscore endpoint doc, when the doc tree is checked, then its filename, frontmatter `path:` placeholder, heading, and every inbound reference (see_also entries AND non-see_also prose references, e.g. comparison-table headers) use `event_id` (not `game_stream_id`), with no half-renamed/dangling references anywhere in `docs/api/`. The rename is scoped to the literal boxscore-endpoint tokens ONLY (per Technical Notes rename-scope constraint) — every other `game_stream_id` occurrence (the different `/game-streams/{game_stream_id}/...` endpoints and the public-details endpoint that legitimately accepts either id) is preserved unchanged.
- [ ] **AC-2**: Given `docs/api/flows/opponent-scouting.md`, when its stat list is audited against the live schema, then no API-returned stat is presented as stored/queryable-from-our-DB when it is not; factual API-return enumerations are PRESERVED (endpoint-fidelity: factual API content is keep-always), and any genuinely not-stored stats are flagged as future analytics work rather than deleted. A documented near-no-op result is acceptable — the audit may find little to correct, since intervening edits appear to have already reconciled most of the original 2026-03 mismatch (do NOT presume a large correction).
- [ ] **AC-3**: Given `docs/api/endpoints/get-public-teams-public_id.md`, when the `age_group` field description is read, then it documents the free-text `"Between N - M"` range form alongside the existing `14U` bracket example.

## Technical Approach
Docs-only edits across `docs/api/`. Apply the doc-sweep discipline (`.claude/rules/doc-sweep.md`) for both the link sweep and the stat audit.

**AC-1 rename-scope constraint (api-scout, E-262-09 review).** The rename is atomic (file rename + frontmatter `path:` + heading + all inbound refs in one pass) but MUST be token-scoped — do NOT blanket-replace `game_stream_id`. Rename ONLY the literal boxscore-endpoint tokens: the path token `game_stream_id}/boxscore` and the filename token `game_stream_id-boxscore`. Every other `game_stream_id` occurrence stays: (i) the public-details endpoint's own path/filename `/public/game-stream-processing/{game_stream_id}/details`, which legitimately accepts either id (CLAUDE.md) and is OUT OF SCOPE, and (ii) the distinct `/game-streams/{game_stream_id}/...` endpoints, where `game_stream_id` is the correct param. Concrete inbound blast radius to sweep: `README.md:150`; `flows/opponent-scouting.md:64,225` (+ prose mention :81); and the `see_also` `path:` in `get-teams-team_id-game-summaries.md`, `get-public-game-stream-processing-game_stream_id-details.md`, `get-game-streams-game_stream_id-events.md`, `get-public-teams-public_id-games.md`, `get-teams-team_id-schedule-events-event_id-player-stats.md` (see_also AND a non-see_also comparison-table header at :278), `get-game-streams-game_stream_id-game-stat-edit-collection-collection_id.md`. Verify these line refs against current file state before editing.

**AC-2 fidelity boundary (api-scout, E-262-09 review).** The flow-doc stat lines (`opponent-scouting.md:73-74`) are FACTUAL API-returned content — endpoint-fidelity rule: keep-always, never strip. The audit corrects only where the doc presents an API stat as stored/queryable-from-our-DB when it is not; it does not delete API-return enumerations. api-scout's spot-check found the current lists already map to real `player_game_batting`/`player_game_pitching` columns (migration 001), so expect a near-no-op with a documented result, not a large rewrite. Audit against `.claude/rules/data-model.md` + `migrations/`; DE's ratified direction is fix-the-doc, not expand-the-schema.

AC-3 is a one-field description addition (the `age_group` free-text range form).

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `docs/api/endpoints/get-game-stream-processing-game_stream_id-boxscore.md` (rename → `-event_id-boxscore.md`, + frontmatter/heading)
- `docs/api/endpoints/get-public-teams-public_id.md` (AC-3 `age_group` note)
- `docs/api/flows/opponent-scouting.md` (AC-2 stat audit; + inbound refs at :64,225 and prose :81)
- `docs/api/README.md` (inbound ref at :150)
- Inbound `see_also` / prose refs in: `docs/api/endpoints/get-teams-team_id-game-summaries.md`, `get-public-game-stream-processing-game_stream_id-details.md`, `get-game-streams-game_stream_id-events.md`, `get-public-teams-public_id-games.md`, `get-teams-team_id-schedule-events-event_id-player-stats.md` (incl. non-see_also comparison-table header :278), `get-game-streams-game_stream_id-game-stat-edit-collection-collection_id.md`.

## Agent Hint
api-scout

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Sources: IDEA-107, IDEA-022, IDEA-126 (companion doc note). All docs/api — api-scout's tree. The IDEA-126 code fix is story 03 (SE); no shared file, so the two can proceed independently.

**api-scout holistic review (2026-07-12):** all three defects verified real, target files exist, endorsed. Two refinements incorporated: (Finding 1) AC-2 tightened to the endpoint-fidelity boundary (preserve factual API-return content; only stop presenting unstored stats as queryable) + accept a near-no-op since the doc appears largely reconciled already; (Finding 2) AC-1 rename token-scoped to the boxscore-endpoint literals with the concrete 8-file blast radius and the non-see_also prose ref at `player-stats.md:278` pinned in Technical Approach. AC-3 confirmed clean and mechanical.
