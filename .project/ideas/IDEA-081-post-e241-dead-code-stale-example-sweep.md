# IDEA-081: Post-E-241 dead-code + stale-example sweep

## Status
`CANDIDATE`

## Summary
A small, focused cleanup sweep of dead code and stale compound-slug example text
that E-241 (the cross-season machinery removal) left behind or surfaced but
deliberately did NOT action, to keep that work tightly scoped to the derivation
collapse. Three buckets: (a) the `scout_all`-orphaned freshness-gating cluster in
`src/gamechanger/crawlers/scouting.py`, (b) the dead `format_season_display` helper
in `src/api/helpers.py`, and (c) stale compound-slug example comments in source.

## Why It Matters
E-241 removed the cross-season machinery at the root, but doing so orphaned a
cohesive subsystem and left a handful of stale `2026-spring-hs`-style example
strings in comments. None of these affect behavior (the suite is green), but they
are honesty gaps: dead code that no production path calls, and example text that
contradicts the year-only reality the codebase now enforces. Removing them as one
coherent unit (rather than half-cleaning during E-241) keeps the cleanup honest and
avoids leaving a half-dead subsystem with false test coverage. This directly serves
the operator's standing "remove the de-scoped bones at the root" preference for the
adjacent opponent-discovery residue, just properly scoped as its own pass.

## Rough Timing
Someday / low urgency — next time a dead-code or scouting-crawler cleanup pass is
warranted. No functional pressure; the suite is green and behavior is correct. Good
candidate to fold into any future scouting-crawler or test-fixture touch.

## Dependencies & Blockers
- [x] E-241 (cross-season machinery removal) complete — it produced/surfaced all
      three buckets. No other blockers.

## Open Questions
- For bucket (a): delete the whole freshness-gating cluster as one unit, or keep
  `_is_scouted_recently` if a future morning-run freshness gate would re-use it?
  (As of E-241 it is production-dead — its only callers were the deleted
  `scout_all`/`scout_all_in_memory` batch methods.)

## Notes
Surfaced and deliberately deferred during E-241 dispatch (06 per-story CR SHOULD-FIX +
Phase-4a CR informational items). The three buckets:

**(a) `scout_all`-orphaned freshness-gating cluster** (`src/gamechanger/crawlers/scouting.py`)
— one cohesive subsystem, all orphaned when E-241-06 deleted `scout_all` +
`scout_all_in_memory` (the TN-12 Option-1 deletions):
- `_resolve_team_id` (~scouting.py:338) — fully orphaned, ZERO callers in `src/` and
  `tests/` (distinct from `_resolve_team_ids` in game_loader.py and
  `_resolve_team_id_by_public_id` in scouting_spray_loader.py, which keep their own callers/tests).
- `_is_scouted_recently` (~scouting.py:378) — PRODUCTION-dead (only the deleted batch
  methods called it), but still exercised by 4 direct freshness-gate tests
  (`tests/test_scouting_crawler.py:525-579`) = false coverage (tests validating a
  method no production path calls).
- The 4 freshness-gate tests + their `_insert_scouting_run` / `_insert_season` seed
  helpers go with `_is_scouted_recently`.

**(b) Dead `format_season_display`** (`src/api/helpers.py`) — pre-existing dead
function (zero callers; only its own doctests reference it). The E-241 year-only
collapse makes its suffix-stripping logic moot, though it degrades gracefully.

**(c) Stale compound-slug example COMMENTS:**
- `src/gamechanger/parsers/plays_parser.py:22` — stale `2026-spring-hs`-style example
  comment, unrelated to derivation; actionable in the sweep.
- `migrations/001_initial_schema.sql:81` (`-- e.g., '2026-spring-hs'`) — a FROZEN
  migration. **DO NOT EDIT.** Captured here only so a future reader who greps for the
  stale example is not surprised; the migration is immutable history.

Related: E-241 (parent, the removal that surfaced these); the deferred-whole decision
is recorded in the archived E-241 epic History + Dispatch & Review Scorecard.

---
Created: 2026-06-21
Last reviewed: 2026-06-21
Review by: 2026-09-19 (90 days from created)
