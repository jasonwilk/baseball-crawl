# E-256-05: Fix the rest-day reference date at all three UTC sites

## Epic
[E-256: Post-Descope Simplification & Foundations](epic.md)

## Status
`TODO`

## Description
After this story is complete, report generation derives its venue-local reference date ONCE through the operating-timezone seam and passes it to all three consumers, so evening report generations no longer compute pitcher rest days and the 7-day rolling pitch-count window against tomorrow's UTC date.

## Context
This is the third, orphaned site of the systemic UTC-date finding whose other two sites E-252 (morning-run target date) and E-253 (stored `game_date`) already fixed. The rest-day reference date fell between those two epics and was never corrected. **Three UTC call sites, not one** — `generator.py:2378` (the 7-day rolling `pitches_7d` window), `:2411`, and `:2431` — and the partial fix is the *likely* failure: fix two, miss `:2378`, and the printed reference date is correct and the headline invariant passes green while the workload window stays silently broken. The canonical seam is `derive_local_date()` in `src/util/timezone.py` (the same converter E-253-04 relocated for cross-layer reuse).

## Acceptance Criteria
- [ ] **AC-1**: Given report generation, when this story is complete, then the venue-local reference date is derived ONCE via `derive_local_date()` (`src/util/timezone.py`), bound to a single variable, and passed to all three consumers at `generator.py:2378`/`:2411`/`:2431`. No consumer site re-derives the date.
- [ ] **AC-2**: Given the generator module, when this story is complete, then a grep for `generated_at[:10]` (the UTC-slice pattern) returns **zero** surviving occurrences in `generator.py` — the caller-audit check that catches the partial fix.
- [ ] **AC-3**: Given an evening report generation (a `generated_at` UTC timestamp that has rolled past local midnight), when the report is produced, then the reference date, the pitcher rest-day math, and the 7-day `pitches_7d` window all use the venue-local date, verified by a test that pins a late-UTC `generated_at` and asserts the local date is used at all three consumers.
- [ ] **AC-4**: Given `bb report generate`, when a report is generated successfully, then the command prints the reference date it used — otherwise Step 1d's headline invariant (`reference_date` == today in operating tz) is unassertable.

## Technical Approach
Depends on story 04 (same file; the settled `generator.py` structure and the public `utcnow_iso`). Derive once, pass down; do not re-derive at any consumer. The caller-audit AC (grep for `generated_at[:10]`) is the mechanical guard against the partial fix — a reviewer confirms zero surviving occurrences. AC-4's printed reference date is consumed by the Step 1d smoke (story 11); coordinate the exact output shape with that story so the invariant is assertable.

**Type note (SE):** `derive_local_date()` returns a `"YYYY-MM-DD"` **string**, not a `date`. The three consumers differ: `:2378`'s `get_pitching_workload` takes the string directly (the 7-day window is SQL `date(ref, '-6 days')`), while `:2411`/`:2431` compute date arithmetic and so wrap the string in `date.fromisoformat(...)`. Bind the single derived string once; each consumer adapts it as needed — do NOT derive twice to get one string and one `date`.

## Dependencies
- **Blocked by**: E-256-04 (same file; settled structure + `utcnow_iso`)
- **Blocks**: E-256-11 (Step 1d asserts on the printed reference date)

## Files to Create or Modify
- `src/reports/generator.py`
- `tests/test_report_generator.py` (or the appropriate report test file) — the late-UTC fixture test
- Possibly `src/cli/report.py` (the `bb report generate` reference-date print, AC-4)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-256-11**: the `bb report generate` printed reference date that Step 1d's headline invariant asserts (`reference_date` == today in operating tz).

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing (late-UTC fixture + grep-audit)
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
The 7-day window uses `date(ref, '-6 days')` inclusive semantics (`.claude/rules/data-model.md`); the fix corrects the `ref` value, not the window arithmetic.
