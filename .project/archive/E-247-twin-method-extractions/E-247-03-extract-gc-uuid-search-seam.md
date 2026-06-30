# E-247-03: Extract public_id→gc_uuid search seam + is_gc_uuid helper

## Epic
[E-247: Twin-Method & Duplicated-Block Extractions](epic.md)

## Status
`DONE`

## Description
After this story is complete, the duplicated "page through search results + filter by exact `public_id`" resolution loop — re-implemented in `generator._resolve_gc_uuid` (`generator.py:690`) and `opponents.resolve_own_team_gc_uuid` (`opponents.py:188`), each with its own `_SEARCH_MAX_PAGES = 5` constant — will exist as one shared helper `resolve_gc_uuid_by_public_id(client, name, public_id)`. Separately, the canonical-UUID regex (3 surviving byte-identical copies after E-246-01 deletes the 4th) will collapse to a single `is_gc_uuid(s)` helper in `url_parser.py`. The GC punctuation/Unicode-apostrophe quirk handling stays centralized in `search.py` and is NOT inlined into the new helper.

## Context
The sweep's H3 finding has two halves. The deletion half (dead resolver + test) is E-246-01. This story is the consolidation half. **api-scout (gc-uuid-bridge owner) consulted and corrected the original framing** — the corrections below are authoritative:

1. **The consolidation target is the paginated public_id-match loop, NOT the quirk handling.** Both `generator._resolve_gc_uuid` (`src/reports/generator.py:690`) and `opponents.resolve_own_team_gc_uuid` (`src/gamechanger/crawlers/opponents.py:188`) ALREADY route through `search_teams_by_name()`; the punctuation/apostrophe normalization lives in `search.py` and MUST stay there (do NOT inline it). What they actually duplicate is the loop: page through `_SEARCH_MAX_PAGES` (each redefines `= 5`: `generator.py:687`, `opponents.py:69`) → filter for an exact-`public_id` match → return `result.id` → with a partial-page / dirty-name page-0 short-circuit.
2. **The twins differ in a way the consolidation MUST preserve.** opponents' version first fetches the public profile name via `resolve_team()` AND validates the matched `id` with the UUID regex before returning; generator's version takes `team_name` as a parameter and skips that re-validation. The shared helper must preserve opponents' name-fetch + UUID-validation-of-the-matched-id (e.g., keep those as a thin caller-side wrapper around the shared loop).
3. **UUID-regex consolidation — 3 survivors, not 4.** Byte-identical `_UUID_RE` lives at `url_parser.py:27` (canonical home; backs the `is_uuid` property at `:46`, consumed by `reports_admin.py:694` + `generator.py:1614`), `opponents.py:59`, and `game_loader.py:67`. The 4th, `gc_uuid_resolver.py:29`, is **EXCLUDED — E-246-01 deletes it and E-246 dispatches first.** Collapse the 3 survivors to one `is_gc_uuid(s)` in `url_parser.py`; the `is_uuid` property delegates. NOTE: `plays_parser.py`'s `_UUID_PATTERN` is a *different* template-extraction regex (`\$\{...\}`) — OUT of scope, do not touch.

## Acceptance Criteria
- [ ] **AC-1**: Given the page-through-+-filter-by-public_id loop is re-implemented in two modules, when the story completes, then one shared helper `resolve_gc_uuid_by_public_id(client, name, public_id)` (alongside `search_teams_by_name` in `src/gamechanger/search.py`) owns that loop and the single `_SEARCH_MAX_PAGES` constant, and both `generator._resolve_gc_uuid` and `opponents.resolve_own_team_gc_uuid` delegate to it. The helper continues to route searches through `search_teams_by_name` (NOT `POST /search` directly), so the punctuation/apostrophe quirk handling stays centralized in `search.py` and is NOT inlined. The partial-page / dirty-name page-0 short-circuit behavior is preserved exactly.
- [ ] **AC-2**: Given the twins differ, when the story completes, then the difference is preserved: the opponent path still fetches the public profile name via `resolve_team()` and validates the matched `id` with the UUID regex before returning, while the generator path still accepts `team_name` as a parameter and resolves without that extra fetch. (Preserving these as thin caller-side wrappers around the shared helper is acceptable.)
- [ ] **AC-3**: Given the canonical-UUID regex has 3 surviving byte-identical copies, when the story completes, then one `is_gc_uuid(s)` helper in `src/gamechanger/url_parser.py` replaces them at `url_parser.py:27`, `opponents.py:59`, and `game_loader.py:67`, and the `is_uuid` property (`url_parser.py:46`) delegates to it. The consolidated helper preserves the EXACT pattern, `re.IGNORECASE`, and `^...$` full-match anchoring. A grep confirms no surviving inline canonical-UUID regex literal (excluding `plays_parser.py`'s distinct `_UUID_PATTERN`, which is out of scope), and that `gc_uuid_resolver.py` is gone (deleted by E-246-01), not edited.
- [ ] **AC-4**: Given `game_loader.py:818-819` classifies boxscore keys as own-vs-opponent via `_UUID_RE.match` (HARD GATE — stats-collection integrity, per epic Technical Notes; a botched anchor flips key classification → wrong team's boxscore → a stats-collection regression), when the regex is swapped for `is_gc_uuid`, then the `uuid_keys`/`slug_keys` split at `game_loader.py:818-819` is re-verified byte-identical to pre-story classification by a `pytest` test over representative key sets.
- [ ] **AC-5**: Given the consolidation (HARD GATE — stats integrity; gc_uuid resolution selects WHICH team's data is fetched), when resolution runs for both the report-generator path and the opponent path against existing fixtures via a `pytest` test, then the resolved gc_uuids are byte-identical to the pre-story output. Proven by test on existing fixtures, not inspection.
- [ ] **AC-6**: Given the consolidation, when the search/resolution test modules (`tests/test_gamechanger_search.py`, `tests/test_url_parser.py`, `tests/test_opponents_crawler.py`, `tests/test_loaders/test_game_loader.py`) run, then they pass. (The full-suite-green check across `tests/` is the epic-level closure gate — Technical Notes "Closure Gate (blocking)" — not a per-story AC, because the whole-suite run is only authoritative in the merged main checkout, not the worktree.)

## Technical Approach
Verified locations (re-confirm before acting): resolve loops — `src/reports/generator.py:690` (`_SEARCH_MAX_PAGES` at `:687`, loop at `:708`) and `src/gamechanger/crawlers/opponents.py:188` (`_SEARCH_MAX_PAGES` at `:69`, loop at `:241`). UUID regex survivors — `src/gamechanger/url_parser.py:27` (+ `is_uuid` property at `:46`), `src/gamechanger/crawlers/opponents.py:59`, `src/gamechanger/loaders/game_loader.py:67` (key-split at `:818-819`); `is_uuid` consumers at `src/api/routes/reports_admin.py:694` + `src/reports/generator.py:1614`. `src/gamechanger/resolvers/gc_uuid_resolver.py:29` is EXCLUDED (deleted by E-246-01). `src/gamechanger/parsers/plays_parser.py`'s `_UUID_PATTERN` is a different template regex — EXCLUDED. The shared `resolve_gc_uuid_by_public_id` helper lives next to `search_teams_by_name` in `search.py` and MUST route through it (NOT `POST /search`); the quirk normalization stays in `search.py`. Resolved gc_uuids and the `game_loader` key classification must be byte-identical.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-247-05 (both touch `src/reports/generator.py`)

## Files to Create or Modify
- `src/gamechanger/search.py` (new `resolve_gc_uuid_by_public_id` helper + the single `_SEARCH_MAX_PAGES`)
- `src/gamechanger/url_parser.py` (new `is_gc_uuid(s)` helper; `is_uuid` property delegates)
- `src/reports/generator.py` (delegate `_resolve_gc_uuid` to the helper; `:1614` is_uuid consumer — verify unchanged)
- `src/gamechanger/crawlers/opponents.py` (delegate `resolve_own_team_gc_uuid`; swap `_UUID_RE` → `is_gc_uuid`)
- `src/gamechanger/loaders/game_loader.py` (swap `_UUID_RE` → `is_gc_uuid`; `:818-819` key-split must stay byte-identical)
- `src/api/routes/reports_admin.py` (`:694` is_uuid consumer — verify unchanged; modify only if the property's call surface changes)
- `tests/test_gamechanger_search.py`, `tests/test_url_parser.py`, `tests/test_opponents_crawler.py`, `tests/test_loaders/test_game_loader.py` (extend — resolution + regex-classification equivalence per AC-3/AC-4/AC-5; all exist today)
- **EXCLUDED:** `src/gamechanger/resolvers/gc_uuid_resolver.py` (deleted by E-246-01), `src/gamechanger/parsers/plays_parser.py` (distinct `_UUID_PATTERN`, out of scope)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-247-05**: This story finalizes the shape of `generator._resolve_gc_uuid` and touches `generator.py`. E-247-05 also edits `generator.py` and must run after this story.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Resolved gc_uuids verified byte-identical (both paths, existing fixtures)
- [ ] `game_loader.py:818-819` key-split verified byte-identical
- [ ] No remaining inline canonical-UUID regex literal (grep-confirmed; `plays_parser._UUID_PATTERN` excluded)
- [ ] No regressions in existing tests
- [ ] Code follows project style (see CLAUDE.md)

## Expert Consultation (api-scout — gc-uuid-bridge owner)
api-scout consulted and set the following binding constraints (record verbatim):
1. Centralized punctuation/apostrophe quirk handling stays in `search.py` — do NOT inline it into the new helper.
2. The opponent path's UUID-validation of the matched `id` (and its `resolve_team()` name-fetch) is preserved.
3. The dirty-name page-0 short-circuit is preserved.
4. `game_loader`'s anchored-regex own-vs-opponent key classification is preserved unchanged.
The byte-identical-resolution-on-existing-fixtures assertion is AC-5; the key-classification assertion is AC-4.

## Notes
This is the consolidation half of H3; the deletion half is E-246-01. **E-246 must dispatch before E-247** so `gc_uuid_resolver.py` is already deleted when this story runs — its `_UUID_RE` site is therefore excluded, leaving exactly 3 regex survivors to consolidate. The remaining shared file with downstream stories is `generator.py` (and defensively `reports_admin.py`); the existing E-247-03 → E-247-05 → E-247-07 chain serializes them.
