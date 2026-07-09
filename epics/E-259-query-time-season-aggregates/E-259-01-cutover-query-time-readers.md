# E-259-01: Cut season readers over to query-time derivation

## Epic
[E-259: Query-Time Season Aggregates](epic.md)

## Status
`TODO`

## Description
After this story is complete, the season batting and pitching lines are derived at query time from the per-game tables. The SQL body inside `get_season_batting`/`get_season_pitching` (already relocated to `src/api/db.py` by E-256) is rewritten in place to SUM from `player_game_batting`/`player_game_pitching` — perspective-filtered — and the ORDER BY is reproduced over the new per-game-SUM projection. The report renders identically: `tests/test_report_golden.py` is zero-diff.

## Context
This is the cutover — the highest-risk single change in the epic, and it carries the epic's most important AC. E-256 already relocated the fetch to `src/api/db.py` precisely so **this change is a legible old-SQL-vs-new-SQL diff inside one function** (Technical Notes §1). The stored rows carried perspective scoping **implicitly** (`canonical_recompute` applied `perspective_team_id = ?` at write time, `season_aggregates.py:230-235`); the current reader filters on neither perspective nor `stat_completeness`. A rewrite that omits the perspective filter **silently doubles** a player's season line when a game was loaded from two perspectives — nothing crashes. See Technical Notes §2 (the perspective hazard), §4 (populated-fixture requirement), §8 (ORDER BY reproduction).

## Acceptance Criteria
- [ ] **AC-1**: Given `get_season_batting`/`get_season_pitching` in `src/api/db.py`, when this story is complete, then their SQL bodies are rewritten **in place** to derive the season line by SUMming from `player_game_batting`/`player_game_pitching`, joined for GS via `appearance_order = 1` (NULL-safe CASE) and for jersey via the `team_rosters` LEFT JOIN — with the function signatures, names, and returned raw-column dict keys unchanged (so the `_query_*` wrappers and the golden test are untouched).
- [ ] **AC-2**: Given the rewritten SQL, when this story is complete, then it filters `perspective_team_id = <team_id>` per Technical Notes §2, and a test seeding **two perspectives for one game** asserts the resulting season line is NOT doubled. **This is the single most important AC in the epic.**
- [ ] **AC-3**: Given the ORDER BY clauses, when this story is complete, then they reproduce the prior ordering semantics over the new per-game-SUM projection (batting: PA-proxy `(ab+bb+hbp+shf) DESC, last_name ASC`; pitching: `ip_outs DESC, last_name ASC`), now as expressions over the SUM projection rather than stored columns (Technical Notes §8), and `tests/test_report_golden.py` is **zero-diff** (no import edits, no expectation edits).
- [ ] **AC-4**: Given a populated fixture whose per-game rows produce a known season line, when `get_season_*` runs, then its output equals the output the prior `canonical_recompute` path produced for the same data (the equality pin), per the populated-fixture requirement in Technical Notes §4 — the test seeds a POPULATED, deliberately stale-disagreeing state, not an empty DB.
- [ ] **AC-5**: Given the SUM projection, when this story is complete, then it reuses `batting_recompute_select()`/`pitching_recompute_select()` from `src/db/season_aggregates.py` so exactly one SUM projection exists in the tree (do not hand-write a second column list — the E-246 false-parity footgun).
- [ ] **AC-6**: Given the full suite, when this story is complete, then it is green.

## Technical Approach
Rewrite the SQL body only — no relocation (E-256 did that), no signature change, no wrapper change. DE owns the SQL. Do NOT touch the golden test or the `_query_*` wrappers. Provenance handling: post-cutover only `boxscore_only` semantics exist; DE decides whether a `stat_completeness` filter is even meaningful once no member rows can be written (story 03's migration enforces their absence). The perspective filter and the SUM-expression ORDER BY are the two semantic changes; everything else is byte-stable.

**Composition note (DE):** the shared `batting_recompute_select()`/`pitching_recompute_select()` projection carries **neither** the `JOIN players` (name) **nor** the `LEFT JOIN team_rosters` (jersey) the reader needs. So AC-5's "reuse the projection" is satisfied by **wrapping the shared projection as a subquery and joining `players`/`team_rosters` on the OUTSIDE** — NOT by inlining those joins into the shared helper (which would corrupt the write-path projection the helper also serves). Likewise, reuse the `BATTING_RECOMPUTE_KEYS`/`PITCHING_RECOMPUTE_KEYS` tuples for row unpacking so they do not orphan when `canonical_recompute` (story 02) and `aggregate_parity.py` (story 04) — their only other consumers — are deleted.

## Dependencies
- **Blocked by**: **E-256-04 (CROSS-EPIC, HARD)** — this story rewrites the SQL body inside `get_season_batting`/`get_season_pitching`, which do not exist until E-256-04 relocates them to `src/api/db.py`. E-259 must not dispatch until E-256 is COMPLETED + merged (epic Prerequisite 0). Also gated on the operator Prerequisites in epic.md.
- **Blocks**: E-259-02 (write paths can only retire once the reader derives from per-game tables)

## Files to Create or Modify
- `src/api/db.py` (rewrite the SQL body inside `get_season_batting`/`get_season_pitching`)
- `tests/test_report_generator.py` / the appropriate report test file (perspective-doubling test + populated equality pin)
- **NOT** `tests/test_report_golden.py` (zero-diff); **NOT** `src/reports/generator.py` (the wrappers are unchanged)

## Agent Hint
data-engineer

## Handoff Context
- **Produces for E-259-02**: the confirmed fact that the reader derives from `player_game_*`, unblocking the write-path retirement.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing (perspective-doubling test + populated equality pin; golden zero-diff)
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Reuse the single SUM projection (`*_recompute_select()`); do not hand-write a second column list — the false-parity footgun (`.claude/rules/data-model.md`, E-246) is exactly this hazard.
