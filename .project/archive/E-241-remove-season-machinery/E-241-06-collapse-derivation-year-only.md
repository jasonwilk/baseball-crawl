# E-241-06: Collapse season derivation to year-only — loaders + scouting crawler (delete the fallback variant + suffix taxonomy)

## Epic
[E-241: Remove the cross-season machinery residue from the core](epic.md)

## Status
`DONE`

## Description
After this story is complete, BOTH compound-slug producers derive a single year-only
`season_id`: the loaders' `derive_season_id_for_team`
(`src/gamechanger/loaders/__init__.py`) and the scouting crawler's `_derive_season_id`
(`src/gamechanger/crawlers/scouting.py`). The cross-season derivation scaffolding is
gone — `derive_season_id_for_team_with_fallback`, the `SeasonDerivation` dataclass,
`_PROGRAM_TYPE_SUFFIX`, and the crawler's `season_suffix` parameter no longer exist.
The `season_id` override escape hatch is also removed: `scout_team`'s `season_id`
parameter is dropped and the two provably-dead E-239-orphan batch methods that forward
it (`scout_all`, `scout_all_in_memory`) are deleted with their tests (TN-12), so no
override path can re-introduce a compound slug.
`derive_season_id_for_team` keeps its `tuple[str, int | None]` signature, so the
loader call sites are untouched. No report's stat values change, and no code path
produces a `YYYY-suffix` slug.

## Context
This is the second SE code story, blocked by E-241-01. E-241-01 already removed the
generator's only direct call to `derive_season_id_for_team_with_fallback`, so this
story can delete that variant against zero direct callers without a red boundary.

There are **two** live compound-slug producers (per Technical Notes TN-4), and this
story collapses both:
1. **Loaders** — `derive_season_id_for_team` and its `_with_fallback`/`SeasonDerivation`/`_PROGRAM_TYPE_SUFFIX` machinery.
2. **Scouting crawler** — `_derive_season_id` (default `season_suffix="spring-hs"`),
   the `ScoutingCrawler.__init__` `season_suffix` parameter, and the crawler's own
   `_ensure_season_row`. It is LIVE in the sole reports path (`generator.py:1625`
   constructs the crawler with no `season_suffix` and calls `scout_team` with no
   `season_id`), so today it writes `2026-spring-hs` to `seasons` and `scouting_runs`
   on every run. Stat values are safe (the loader re-derives year-only), but the
   crawler must be collapsed too or the Success Criterion is false and migration 006's
   no-op default re-fragments every run.

The `season_id` column, the `seasons` table, and `ensure_season_row` all stay (the
load-bearing kernel, TN-1); only the *value* derivation produces changes (year-only
instead of `YYYY-suffix`). Per Technical Notes TN-1, TN-3, TN-4, TN-6.

## Acceptance Criteria
- [ ] **AC-1**: `derive_season_id_for_team(db, team_id)` retains its
  `tuple[str, int | None]` return signature and produces a year-only `season_id`
  (the team's `season_year` as a string, or the current year when `season_year` is
  absent). The three loader call sites are unchanged. Per Technical Notes TN-4.
- [ ] **AC-2**: `_PROGRAM_TYPE_SUFFIX`, the `SeasonDerivation` dataclass, and
  `derive_season_id_for_team_with_fallback` no longer exist in
  `src/gamechanger/loaders/__init__.py`; `ensure_season_row`'s dead compound-slug
  split branch is removed. Per Technical Notes TN-4.
- [ ] **AC-3**: The scouting crawler produces a year-only `season_id` — the
  `ScoutingCrawler.__init__` `season_suffix` parameter is removed, `_derive_season_id`
  is collapsed to year-only, and the crawler's `_ensure_season_row` writes year-only.
  The `seasons` + `scouting_runs` writes from a live report run carry a year-only slug.
  Per Technical Notes TN-4.
- [ ] **AC-4**: The `season_id` override escape hatch is removed so that NO code path
  produces a `YYYY-suffix` slug (Success Criterion, honestly absolute). Specifically:
  the `season_id` override parameter is dropped from `scout_team`, and the two
  provably-dead E-239-orphan batch methods that forward it — `scout_all` (test-only)
  and `scout_all_in_memory` (zero callers anywhere) — are DELETED along with their
  tests (per the SE caller-check + whole-repo grep, 2026-06-20; this is the
  "Option 1" scope decision in Technical Notes TN-12). The two crawler construction
  sites (`generator.py:1625` and the module-level helper) and the sole live caller
  `generator.py:1626 scout_team(self.public_id)` remain correct (none passes an
  override). After this, the absolute Success Criterion holds with no asterisk.
- [ ] **AC-5**: `programs.program_type` (the column) and `.claude/rules/pitch-rules.md`
  are not modified — only the `_PROGRAM_TYPE_SUFFIX` *mapping* and the crawler's
  `season_suffix` are removed. Per Technical Notes TN-6.
- [ ] **AC-6**: Every test that asserts a loader or the crawler PRODUCES a compound
  (`YYYY-suffix`) `season_id` via derivation is brought to the year-only contract
  (distinct from opaque-literal seed fixtures, which stay — TN-4 / TN-5). This set is
  COMPLETE — finalized + verified by SE recon 2026-06-20 (the opaque-literal seeds that
  correctly stay are enumerated in Notes):
  - `tests/test_season_id_derivation.py` — `TestDeriveSeasonIdForTeam` asserts flipped
    to year-only; `TestDeriveSeasonIdFallbackSignal` DELETED (it tests the removed
    `_with_fallback`); `TestEnsureSeasonRow.test_year_suffix_format` /
    `test_spring_hs_format` DELETED or rewritten to year-only.
  - `tests/test_scouting_crawler.py` — `test_derive_season_id_extracts_year`,
    `test_derive_season_id_uses_earliest_year`, and
    `test_derive_season_id_fallback_on_missing_ts` flipped to year-only;
    `test_derive_season_id_uses_season_suffix` DELETED.
  - `tests/test_scouting_loader.py` — `test_usssa_team_gets_correct_db_season_id`
    (asserts DB `season_id == '2025-summer-usssa'`) DELETED or rewritten to year-only.
  - `tests/test_loaders/test_game_loader.py` — `test_usssa_team_produces_correct_season_id`
    (E-197-02 AC-9, asserts `2025-summer-usssa`) DELETED or rewritten to year-only.

  Do NOT "fix" a doomed test by restoring a removed branch, and do NOT migrate
  opaque-literal seed fixtures (they are not derivation-output assertions).
- [ ] **AC-7**: After this story, `grep -rn season_fallback src/` returns no matches
  across the whole `src/` tree — this story removes the last remaining reference (the
  `SeasonDerivation` docstring at `src/gamechanger/loaders/__init__.py:52`) by
  deleting the dataclass. (E-241-01 removed the generator/db/template/admin
  references; this story closes the loaders one — see Technical Notes TN-4.)
- [ ] **AC-8**: `tests/test_report_golden.py` passes with the golden JSON
  un-regenerated, and `tests/test_aggregate_parity.py` passes — the in-suite
  zero-stat-change gate (`bb report verify-aggregates` needs `data/` and cannot run
  in-worktree; `test_aggregate_parity.py` is its in-suite proxy). Per Technical Notes
  TN-3.

## Technical Approach
Rewrite `derive_season_id_for_team` (loaders) and `_derive_season_id` (crawler) to
produce year-only `season_id` values; delete the `_with_fallback` variant, the
`SeasonDerivation` dataclass, `_PROGRAM_TYPE_SUFFIX`, the crawler's `season_suffix`
parameter, and the now-dead compound-slug branches in both `ensure_season_row` and
the crawler's `_ensure_season_row`. See Technical Notes TN-4 for the end state and
the second-producer detail. Do not touch the `programs.program_type` column or
`.claude/rules/pitch-rules.md` (TN-6); do not touch the fixtures (E-241-03 owns them).

## Dependencies
- **Blocked by**: E-241-01
- **Blocks**: E-241-02, E-241-04, E-241-05

## Files to Create or Modify
- `src/gamechanger/loaders/__init__.py`
- `src/gamechanger/crawlers/scouting.py`
- `tests/test_season_id_derivation.py`
- `tests/test_scouting_crawler.py`
- `tests/test_scouting_loader.py`
- `tests/test_loaders/test_game_loader.py`
<!-- Derivation-output test set COMPLETE — verified by SE recon 2026-06-20 (see Notes). -->

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-241-04 / E-241-05**: the settled year-only derivation behavior in
  BOTH the loaders and the crawler (and the deleted `_with_fallback`/`SeasonDerivation`/
  `season_suffix` symbols) that the context-layer and docs updates describe.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
No file overlap with E-241-01, 02, or 03 (this story owns `loaders/__init__.py`,
`crawlers/scouting.py`, `test_season_id_derivation.py`, `test_scouting_crawler.py`,
`test_scouting_loader.py`, `test_loaders/test_game_loader.py`; 01 owns the
generator/db/template/admin tests — note 01 edits `generator.py` but NOT the
`ScoutingCrawler(...)` construction at L1625, which this story leaves correct by
dropping the parameter rather than changing the call; 03 owns the two shared fixtures +
their query/golden/parity tests). Numbered 06 because it was split out of the original
combined story after the initial draft; its dependency edges place it after 01 and
before 02. The crawler was added per iteration-1 review finding A1 (a second live
compound-slug producer the initial draft missed); the two loader derivation-output
test files were added per codex iteration-1 finding C2.

**SE-recon obligation — SATISFIED (SE recon 2026-06-20).** SE grepped `tests/` for
compound-slug assertions tied to derivation OUTPUT and confirmed the AC-6 set is COMPLETE
— exactly the four files above, no others. The opaque-literal seeds that correctly STAY
(verified exclusions, NOT derivation output): `test_schema.py:288/290` (round-trips a
season string, tests the `seasons` table not derivation), `test_admin_reports.py:837` +
`test_report_generator.py:1168` (`season_id_used` opaque input for the fallback-badge
test — both in 01's telemetry-strip scope), `test_aggregate_parity.py:168` (E-241-03
fixture territory), `test_scouting_crawler.py:632/644/675` (`_is_scouted_recently` INPUT,
not derivation output). The TN-4 catch-all remains the backstop.
