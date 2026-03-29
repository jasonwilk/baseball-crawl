# E-184: Fix Opponent Resolver Phantom Errors and Negative Unlinked Count

## Status
`COMPLETED`

## Overview
Two production bugs in the opponent resolver produce incorrect error and unlinked counts on every resolution run. One bug inflates errors by +1 per member team (return type mismatch), the other produces negative unlinked counts (counter subtraction logic). Both were flagged as P1 findings in the E-179 Codex code review, and E-179 updated 13 test assertions to match the buggy behavior rather than fixing the production code. This epic fixes both bugs and reverts the test workarounds in a single atomic story.

## Background & Context
Promoted from [IDEA-056](/.project/ideas/IDEA-056-search-fallback-team-return-bug.md). Discovered during E-179-08 (test assertion alignment for pre-existing failures from E-173 UI changes). E-179 was scoped as test-only (TN-3: production code changes were out of scope), so it correctly updated assertions to match actual behavior -- but the Codex reviewer noted this "removes the regression signal instead of protecting the intended contract."

**Bug 1 -- `_search_fallback_team` return type**: At `opponent_resolver.py:511`, `_search_fallback_team()` returns bare `0` when no unlinked rows exist, but the method signature is `-> tuple[int, int]` and the caller at line 174 unpacks `search_count, search_errors = self._search_fallback_team(team)`. The bare int causes `TypeError: cannot unpack non-iterable int`, caught by the broad `except Exception` handler at line 180, silently adding +1 to `result.errors`. This happens for every member team where all opponents are already resolved.

**Bug 2 -- negative `unlinked` counter**: At `opponent_resolver.py:176`, `result.unlinked -= search_count` subtracts search resolutions from the unlinked counter. But `result.unlinked` only counts opponents inserted as unlinked *in the current run* (from `_process_opponent` at line 276). The search fallback can resolve opponents from *prior* runs already in the DB, so `search_count` can exceed `result.unlinked`, producing negative values like -1. The `ResolveResult.unlinked` docstring contract says "Opponents inserted as unlinked" -- a per-run count that should never be negative.

**SE consultation**: Fix approach verified with software-engineer. Both bug descriptions confirmed accurate, no edge cases or side effects identified.

## Goals
- Eliminate phantom +1 error on every resolution run caused by return type mismatch
- Ensure `ResolveResult.unlinked` accurately reflects per-run unlinked insertion count (never negative)
- Restore test assertions to their correct intended values (undo E-179 workarounds)

## Non-Goals
- Refactoring the broad `except Exception` handlers (separate concern)
- Adding new resolver features or changing resolution logic
- Modifying the search fallback algorithm itself

## Success Criteria
- `_search_fallback_team()` returns `(0, 0)` on all early-exit paths, matching its type annotation
- `ResolveResult.unlinked` is never negative after a resolution run
- All 13 test assertions and 3 comments reverted from E-179 workaround values to correct intended values
- `python -m pytest tests/test_crawlers/test_opponent_resolver.py -v` passes with zero failures

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-184-01 | Fix resolver bugs and revert test workarounds | DONE | None | SE |

## Dispatch Team
- software-engineer

## Technical Notes

### TN-1: Bug 1 fix detail
`src/gamechanger/crawlers/opponent_resolver.py`: In `_search_fallback_team()`, the early return when `not unlinked_rows` returns bare `0` instead of `(0, 0)`. This is the only incorrect early-return path -- the `internal_id is None` guard already returns `(0, 0)` correctly, and the end-of-method return produces the `(search_count, error_count)` tuple.

### TN-2: Bug 2 fix detail
`src/gamechanger/crawlers/opponent_resolver.py`: In `resolve()`, `result.unlinked -= search_count` should be removed. The `search_resolved` field already tracks search resolutions separately. The `unlinked` field should purely reflect how many opponents were inserted as unlinked in this run -- subtracting search resolutions conflates "inserted as unlinked" with "currently unlinked in DB," which is a different concept. Removing the subtraction makes `unlinked` match its docstring contract.

### TN-3: E-179 test assertion inventory
E-179 commit `8391bd5` modified 13 assertions and 3 comments in `tests/test_crawlers/test_opponent_resolver.py`. All must be reverted. Use the assertion patterns below to locate each change (line numbers are approximate and may drift).

**Bug 1 reversions** (12 assertions -- `errors` inflated by +1 from phantom TypeError):

| Current (buggy) | Revert to | Pattern to find |
|-----------------|-----------|-----------------|
| `assert result.errors == 1` | `assert result.errors == 0` | In test that asserts `result.resolved == 1` and `result.unlinked == 0` (single progenitor resolution, ~line 220) |
| `assert result.errors == 2` | `assert result.errors == 1` | In test with `"Access denied"` caplog check (~line 434) |
| `assert result.errors == 2` | `assert result.errors == 1` | In test with `"API error"` caplog check (~line 473) |
| `assert result.errors == 2` | `assert result.errors == 1` | In test asserting `result.resolved == 0` after API error (~line 496) |
| `assert result.errors == 1` | `assert result.errors == 0` | In test asserting `result.resolved == 0`, `result.unlinked == 0` for hidden opponents (~line 562) |
| `assert result.errors == 1` | `assert result.errors == 0` | In test with `result.skipped_hidden == 1` (~line 590) |
| `assert result.errors == 1` | `assert result.errors == 0` | In test with `"UNIQUE collision"` caplog check (~line 1347) |
| `assert result.errors == 1` | `assert result.errors == 0` | In test with `"missing public_id"` caplog check, first occurrence (~line 1388) |
| `assert result.errors == 1` | `assert result.errors == 0` | In test with `"missing public_id"` caplog check, `public_id is None` assertion (~line 1428) |
| `assert result.errors == 1` | `assert result.errors == 0` | In test checking `gc_uuid` and `public_id` row after resolution (~line 1470) |
| `assert result.errors == 1` | `assert result.errors == 0` | In test with E-167 `ensure_team_row` comment (~line 1514) |
| `assert result.errors == 1` | `assert result.errors == 0` | In test asserting exact team count after resolution (~line 1563) |

**Bug 2 reversion** (1 assertion -- `unlinked` went negative):

| Current (buggy) | Revert to | Pattern to find |
|-----------------|-----------|-----------------|
| `assert result.unlinked == -1` | `assert result.unlinked == 0` | In search fallback test (~line 1724) |

**Comment reversions** (3 comments -- E-179 altered explanatory comments):

| Current text | Revert to | Pattern to find |
|-------------|-----------|-----------------|
| `# Resolution still succeeds (not an error from the resolver itself)` | `# Resolution still succeeds (not an error)` | ~line 1345 |
| `# Resolution still counted as successful (not an error from the resolver itself)` | `# Resolution still counted as successful (not an error)` | ~line 1386 |
| `# unlinked starts at 0 (no opponents from API), search resolves 1 → -1` | `# Finding 1 fix: unlinked should be decremented when search resolves` | ~line 1723 |

## Open Questions
- None -- both bugs are well-understood with clear fixes.

## History
- 2026-03-29: Created. Promoted from IDEA-056.
- 2026-03-29: Internal review round 1. Merged 2 stories into 1 (DoD contradiction). Fixed TN-3: corrected line numbers, switched to pattern-based guidance, added missing 3rd comment reversion, included original comment text. Rewrote ACs as outcome-based.
- 2026-03-29: Codex spec review round 1. 2 findings, both dismissed (already fixed by internal review). Set to READY.
- 2026-03-29: Set to ACTIVE, dispatch begun.
- 2026-03-29: COMPLETED. Single story delivered. Per-story CR: APPROVED (1 SHOULD FIX accepted -- misleading comment fixed). All ACs verified.

### Documentation Assessment
No documentation impact -- bug fix only, no new features or changed interfaces.

### Context-Layer Assessment
1. **New convention or pattern**: No -- bug fix, no new conventions.
2. **Changed architectural decision**: No -- no architecture changes.
3. **New agent capability or workflow**: No -- no agent changes.
4. **Lessons learned worth codifying**: No -- straightforward bug fix.
5. **New integration or external dependency**: No -- no new integrations.
6. **Changed data model or API contract**: No -- `ResolveResult` fields unchanged, only corrected values.

No context-layer impact.

### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 -- CR spec audit | 3 | 3 | 0 |
| Internal iteration 1 -- SE holistic | 2 | 2 | 0 |
| Internal iteration 1 -- PM self-review | 3 | 3 | 0 |
| Codex iteration 1 | 2 | 0 | 2 |
| Per-story CR -- E-184-01 | 1 | 1 | 0 |
| **Total** | **11** | **9** | **2** |
