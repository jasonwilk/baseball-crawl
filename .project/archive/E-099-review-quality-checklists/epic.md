# E-099: Targeted Review Quality Checklists

## Status
`COMPLETED`

## Overview
Add concrete bug-pattern checklists to the code-reviewer and software-engineer agent definitions, and an error-path testing requirement to `testing.md`, so the specific failure classes that escaped E-097 review are caught systematically in future dispatches. E-098 fixes the bugs themselves; this epic prevents the class from recurring.

## Background & Context
The E-097 Opponent Scouting Pipeline shipped with four bugs that both the software-engineer (implementer) and code-reviewer (quality gate) missed. A post-dev Codex code review caught all four:

1. **P1-1**: `_compute_batting_aggregates` and `_compute_pitching_aggregates` in `scouting_loader.py` accept `season_id` as a parameter but the SQL queries filter only on `team_id`. Multi-season scouting inflates stats because per-game rows from all seasons are aggregated into one season row.
2. **P1-2**: The CLI in `data.py` ignores `loader.load_team()` return values and always prints "Load complete." The crawler in `scouting.py` marks `scouting_runs.status = completed` before loading happens. Together: silent load failures with no operator visibility and corrupted freshness state.
3. **P2-1**: No multi-season test exists, so the missing `season_id` filter produces correct results with single-season fixtures.
4. **P2-2**: No CLI error-path test exists, so the ignored return values are never exercised.

**Root cause (per all four expert analyses)**: Both agents verified *presence* (function exists, test exists, AC checked) but not *correctness* (does the query filter on all dimensions? is the return value consumed? does the test exercise boundary conditions?). The current rubric guidance is abstract ("find logic errors," "test edge cases") -- it relies on general reasoning rather than enumerating concrete checks for known bug patterns.

**The fix**: Add specific, actionable checklist items to the SE and CR agent definitions targeting the three bug classes (query scope, return value consumption, status lifecycle), and add an explicit error-path testing requirement to `testing.md`. These are small additions to existing files -- no new infrastructure.

Consultation: All four relevant experts (SE, CR, DE, CA) provided root-cause analyses and specific recommendations. Their inputs are synthesized here.

## Goals
- SE self-review catches unused SQL parameters and ignored return values before reporting completion
- CR review catches query scope bugs, ignored return values, and missing error-path tests during structured review
- Testing rules explicitly require error-path coverage for orchestration code (CLI, pipelines)

## Non-Goals
- Changing the dispatch pattern, review loop mechanics, or worktree isolation
- Adding a mandatory Codex post-review layer
- Fixing the E-097 bugs themselves (that is E-098's scope)
- Broad refactoring of agent definitions beyond the targeted checklist additions
- Adding schema comments to migration files (future work if needed)

## Success Criteria
- The code-reviewer agent definition contains a concrete bug-pattern checklist covering: SQL query scope, return value consumption, and status lifecycle correctness
- The software-engineer agent definition contains a pre-submission self-review checklist covering the same three bug classes
- `testing.md` contains an explicit error-path testing requirement for orchestration code
- All additions are concrete and actionable (specific checks an agent can execute mechanically), not abstract guidance

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-099-01 | Add bug-pattern checklists to CR and SE agent definitions | DONE | None | claude-architect |
| E-099-02 | Add error-path testing requirement to testing.md | DONE | None | claude-architect |

## Dispatch Team
- claude-architect

## Technical Notes

### Three Bug Classes to Target

All checklist items address exactly three bug classes identified in E-097. Do not expand scope beyond these.

**Class 1: Query scope incompleteness**
- Pattern: Function receives a scope parameter (e.g., `season_id`) but the SQL query does not filter on it. The parameter is silently unused.
- Detection (SE): Before finalizing any SQL query function, verify every scope parameter in the signature appears in the WHERE/JOIN/GROUP BY.
- Detection (CR): For every SQL SELECT in changed code, cross-reference function parameters against WHERE clause bindings. Missing parameters are MUST FIX.
- Aggravating factor (from DE): When the destination table has a dimension column (e.g., `season_id` on `player_season_batting`) but the source table does not (e.g., `player_game_batting`), a JOIN through an anchor table (e.g., `games`) is required. Missing JOINs are a specific sub-pattern.
- Aggravating factor (from DE): When a wrong-scope query feeds an upsert (ON CONFLICT DO UPDATE), the error compounds on every re-run -- each execution overwrites with an ever-growing cross-scope total.

**Class 2: Ignored return values / silent failures**
- Pattern: A function returns a result/status/error object, but the caller discards it. The caller prints "success" or exits 0 regardless of outcome.
- Detection (SE): Before finalizing any function that calls another, verify the return value is captured and used. Silently ignoring a `LoadResult`, `CrawlResult`, or similar status type is a bug.
- Detection (CR): For every call to a fallible operation (loader, crawler, DB write, HTTP call), verify the return value is consumed and failure states affect control flow.

**Class 3: Premature status marking / status lifecycle errors**
- Pattern: Code writes a terminal status (`completed`, `success`) to a tracking table before downstream operations that could fail. If those operations fail, the status is stale and gates future behavior incorrectly.
- Detection (SE): Before reporting completion, verify that status transitions in tracking tables happen AFTER the full pipeline succeeds, not just after one phase.
- Detection (CR): When code writes a terminal status to a tracking/state table, trace what downstream behavior that status gates. Verify the status is written only AFTER the gated work succeeds.

### Test Coverage Patterns

Two test patterns that would have caught the bugs:

**Multi-scope test**: For any aggregate query filtering by N dimensions, the test must include data spanning 2+ values in at least the primary dimension (e.g., two seasons). Single-value fixtures make wrong-scope queries produce correct results.

**Error-path test**: For any CLI command or pipeline that delegates to a fallible operation, at least one test must exercise the failure path (mock the dependency to fail) and verify exit code + output.

These belong in the SE pre-submission checklist (as obligations) and the CR rubric (as verification items).

### Placement Within Existing Files

**`code-reviewer.md`**: Add a "Bug Pattern Checklist" subsection within the Review Rubric section, positioned after Priority 2 (Bugs and Regressions). Items in this checklist are classified as MUST FIX when violated -- they are concrete instances of Priority 2 and Priority 3 patterns. Also add multi-scope test and error-path test items to the Priority 3 section.

**`software-engineer.md`**: Add a "Pre-Submission Checklist" section after the existing work authorization or code standards guidance. This is a self-review the SE executes before reporting story completion.

**`testing.md`**: Add an "Error-Path Testing" section after the existing "Test Scope Discovery" section.

### What NOT to Change

- Do not modify the dispatch pattern, review loop, or worktree isolation rules.
- Do not add the Codex rubric content to the CR agent -- they are different tools with different strengths.
- Do not create new rule files or new agents -- additions go into existing files per the core principle (simple first).
- Do not add abstract guidance ("be more careful," "think harder") -- every addition must be a concrete, mechanically executable check.

## Open Questions
None.

## History
- 2026-03-12: Created. Synthesized from root-cause analyses by SE, CR, DE, and CA on the E-097 post-dev review findings. All four experts consulted; recommendations converged on targeted checklist additions to existing agent definitions. No expert consultation required beyond the team inputs already received.
- 2026-03-12: COMPLETED. Both stories implemented by claude-architect. Bug Pattern Checklist added to code-reviewer.md (SQL query scope, return value consumption, status lifecycle). Pre-Submission Checklist added to software-engineer.md (same three bug classes + two test obligations). Error-Path Testing section added to testing.md. All context-layer-only -- no code-reviewer needed. Documentation assessment: No documentation impact. Context-layer assessment: (1) New convention -- yes (the deliverables ARE the context-layer additions; no further codification needed), (2) Architectural decision -- no, (3) Footgun discovered -- no (already codified by the stories), (4) Agent behavior change -- yes (CR and SE definitions modified; this IS the deliverable), (5) Domain knowledge -- no, (6) New CLI/workflow -- no.
