# E-214: Fix Predicted Starter Rest Day Anchoring

## Status
`READY`
<!-- Lifecycle: DRAFT → READY → ACTIVE → COMPLETED (or BLOCKED / ABANDONED) -->

## Overview
Fix the predicted starter engine to compute rest days relative to today (dashboard) or report generation date (reports), not relative to the team's last game date. Add a feature flag to disable the predicted starter in production while the fix is verified in dev.

## Background & Context
The predicted starter engine (`src/reports/starter_prediction.py`) anchors all rest/availability calculations to `latest_game_date` -- the most recent game in the pitching history data. This diverges from the rest TABLE, which uses `get_pitching_workload()` with today's date as the reference. The result is conflicting rest days: a pitcher might show "10d rest" in the Pitching section but "4 days rest" in the Predicted Starter reasoning.

This was flagged during E-212's Codex review as "rest anchoring divergence" but was dismissed as "by design (different perspectives for different purposes)." The user confirmed it is a bug with a live example: Cushing's rest days were inconsistent between the two surfaces.

**Expert consultation**: SE consulted on `reference_date` threading approach. Key recommendations incorporated into Technical Notes.

No expert consultation required for baseball-coach (no coaching domain changes -- same data, corrected anchor) or data-engineer (no schema changes).

## Goals
- Predicted starter reasoning, exclusion logic, and likelihood scoring use the same date anchor as the rest table
- A feature flag allows disabling predicted starter in production independently from dev
- Existing test suite updated to validate the new `reference_date` parameter

## Non-Goals
- Changing the rotation detection algorithm or confidence tiers
- Adding new predicted starter features (matchup analysis, etc.)
- Modifying the rest table implementation (it already uses the correct anchor)
- Building a generalized feature flag framework

## Success Criteria
- The "days rest" value in predicted starter reasoning matches the "days since last appearance" value in the rest table for the same pitcher
- Omitting `FEATURE_PREDICTED_STARTER` or setting it to any value other than `1`/`true`/`yes` disables the predicted starter on both dashboard and reports
- All existing tests pass (updated for new signature) plus new tests covering the `reference_date` behavior

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-214-01 | Thread `reference_date` through the prediction engine | TODO | None | - |
| E-214-02 | Update callers to pass `reference_date` | TODO | E-214-01 | - |
| E-214-03 | Add `FEATURE_PREDICTED_STARTER` feature flag | TODO | None | - |

## Dispatch Team
- software-engineer

## Technical Notes

### TN-1: `reference_date` Type and Threading

Per SE consultation:

- **Type**: `reference_date` is `datetime.date` (not `str`). The internal functions currently receive `latest_game_date` as `str` and immediately parse it with `datetime.date.fromisoformat()` -- passing a proper `datetime.date` eliminates redundant parse calls and defensive try/except blocks.

- **Public signature change**: `compute_starter_prediction()` gains a required `reference_date: datetime.date` parameter. No default value -- callers must be explicit about their anchor date.

- **Internal threading**: `reference_date` replaces `latest_game_date` in the following functions' rest/availability calculations:
  - `_is_excluded_within_1_day(profile, reference_date)` -- parameter changes from `str` to `datetime.date`
  - `_is_excluded_high_pitch_short_rest(profile, reference_date)` -- same
  - `_build_reasoning(profile, role, rotation_pattern, reference_date, ...)` -- same
  - `_compute_rotation_likelihoods(profiles, history, roles, reference_date)` -- `latest_game_date: str` replaced by `reference_date: datetime.date`. The rotation sequence detection block (extracting starter order from history) does not use the date parameter at all. Only the rest scoring block (computing rest-based likelihood weight) uses it.

- **`latest_game_date` retained internally**: `compute_starter_prediction()` still computes `latest_game_date` from history for any internal logic that genuinely needs the data-relative anchor (currently: none after the refactor, but the value is inexpensive to compute and documents intent).

### TN-2: Caller Contract

- **Dashboard**: `reference_date = datetime.date.today()`
- **Reports**: `reference_date = datetime.date.fromisoformat(generated_at[:10])`
- **Contract**: `reference_date` should be >= the latest game date in the history. The engine does not clamp or validate this. Negative rest days from a past `reference_date` are nonsensical but self-evidently wrong in output -- hiding them with defensive clamping would mask bugs.

### TN-3: Feature Flag

- **Env var**: `FEATURE_PREDICTED_STARTER` -- enabled when value is `1`, `true`, or `yes` (case-insensitive); disabled for all other values including `0`, `false`, empty string, and when the env var is absent. This is positive matching, not Python truthiness (since `"0"` is truthy in Python but should mean disabled).
- **Check location**: At the three call sites, not inside the engine. The engine is pure computation; env var checks would break its testability.
- **Helper function**: A single `is_predicted_starter_enabled()` function in `src/reports/starter_prediction.py` keeps the env var name in one place. Call sites use this function.
- **Call sites**: `src/reports/generator.py` (~line 1178), `src/api/routes/dashboard.py` (~line 1635, ~line 1824).
- **Dev `.env`**: Sets `FEATURE_PREDICTED_STARTER=1`. Prod `.env` omits it (disabled by default).

### TN-4: Report Template Gating

The report template (`scouting_report.html`) renders the predicted starter section header and "No pitching data available" message unconditionally when `starter_prediction is None`. The dashboard templates (`opponent_detail.html`, `opponent_print.html`) already gate the entire section on `{% if starter_prediction %}`, so `None` hides the section there.

To support the feature flag without losing the existing "no data" message behavior, the report template needs a separate `show_predicted_starter` boolean in the template context:
- `show_predicted_starter = False` → entire section absent (flag disabled)
- `show_predicted_starter = True`, `starter_prediction = None` → "No pitching data available" (current behavior preserved)
- `show_predicted_starter = True`, `starter_prediction = <object>` → full prediction display

The generator sets `show_predicted_starter=is_predicted_starter_enabled()` in its data dict. The renderer (`src/reports/renderer.py`, ~line 689) must forward this key to the Jinja2 template context alongside `starter_prediction` and `enriched_prediction`. The template wraps the entire `<div class="predicted-starter-section">` (lines 492-636) in `{% if show_predicted_starter %}`.

Dashboard templates need no template changes -- their existing `{% if starter_prediction %}` gate is sufficient since setting `starter_prediction = None` when the flag is off already hides the section.

## Open Questions
- None (all resolved via SE consultation)

## History
- 2026-04-06: Created. SE consulted on reference_date threading and feature flag approach.
- 2026-04-06: Set to READY after 3 internal review iterations + 3 Codex spec review iterations.

### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 -- CR spec audit | 3 | 3 | 0 |
| Internal iteration 1 -- Holistic team (PM + SE) | 5 | 4 | 1 |
| Internal iteration 2 -- CR spec audit | 1 | 0 | 1 |
| Internal iteration 2 -- Holistic team (PM + SE) | 1 | 1 | 0 |
| Internal iteration 3 -- CR spec audit | 1 | 1 | 0 |
| Internal iteration 3 -- Holistic team (SE + UXD) | 0 | 0 | 0 |
| Codex iteration 1 | 2 | 1 | 1 |
| Codex iteration 2 | 4 | 2 | 2 |
| Codex iteration 3 | 5 | 1 | 4 |
| **Total** | **22** | **13** | **9** |

Key accepted findings: test fixture must prove anchor divergence (Codex-2-2), report template needs `show_predicted_starter` boolean via renderer plumbing (Codex iter 1 + 3), positive string matching for feature flag (CR-4), `_build_reasoning` has two date blocks (SE-3). Key dismissed findings: shared-file dependency (5x, serial dispatch with non-overlapping edits), `.env.example` convention (2x, standard pattern).
