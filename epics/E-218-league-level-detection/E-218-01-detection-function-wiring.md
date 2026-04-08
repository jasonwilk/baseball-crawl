# E-218-01: League/Level Detection Function and Wiring

## Epic
[E-218: League/Level Detection for Pitch Rules](epic.md)

## Status
`TODO`

## Description
After this story is complete, the starter prediction engine will receive the correct league/level identifier for any team, whether tracked (DB fields) or ad-hoc (GC API metadata). When the detected league has no implemented rule set (USSSA, Perfect Game) or detection fails entirely, the engine will suppress rest-tier availability and display a warning instead of silently applying wrong NSAA rules.

## Context
After E-217-01 delivers the NSAA availability engine (which defaults all teams to NSAA varsity), this story adds the detection layer that sits between the data sources (DB, GC API) and the rule engine. It wires detection into both the reports path (`generate_report()`) and the dashboard/opponent path (`compute_starter_prediction()` call sites), so all consumers benefit.

The detection function uses a cascading priority of signals (per epic Technical Notes: "Detection Signal Priority" and "Team Name Keyword Table"). DB fields are checked first (tracked teams), then GC API `ngb` + `age_group` combination (per "NGB + Age Group Interaction"), then team name keyword parsing, then falls through to `unknown`.

## Acceptance Criteria
- [ ] **AC-1**: Given a tracked team with `program_type='hs'` and `classification='varsity'`, when detection runs, then the result is `nsaa_varsity`.
- [ ] **AC-2**: Given a tracked team with `program_type='hs'` and `classification` of `'jv'`, `'freshman'`, or `'reserve'`, when detection runs, then the result is `nsaa_subvarsity` for each.
- [ ] **AC-3**: Given a tracked team with `program_type='hs'` and `classification=NULL`, when detection runs, then the result is `nsaa_varsity` (default -- bounded risk, coach knows their level).
- [ ] **AC-4**: Given a tracked team with `program_type='legion'`, when detection runs, then the result is `legion`.
- [ ] **AC-5**: Given a tracked team with `program_type='usssa'`, when detection runs, then the result is `usssa`.
- [ ] **AC-6**: Given an ad-hoc report where the GC public API returns `ngb='["american_legion"]'`, when detection runs, then the result is `legion`.
- [ ] **AC-7**: Given an ad-hoc report where the GC public API returns `ngb='["usssa"]'`, when detection runs, then the result is `usssa`.
- [ ] **AC-8**: Given an ad-hoc report where the GC public API returns an NSAA-like `ngb` value (e.g., `'["nsaa"]'` or `'["nfhs"]'`) and team name contains "JV", when detection runs, then the result is `nsaa_subvarsity`. (Validates the ngb → NSAA path with name-keyword level disambiguation.)
- [ ] **AC-9**: Given an ad-hoc report where `ngb` is empty but team name contains "JV", when detection runs, then the result is `nsaa_subvarsity`.
- [ ] **AC-10**: Given an ad-hoc report where `ngb` is empty and `age_group` contains a "U" suffix (e.g., "14U"), when detection runs, then the result is `youth_travel`.
- [ ] **AC-11**: Given an ad-hoc report where `ngb` is empty but team name contains "Legion" or matches "Post \d+", when detection runs, then the result is `legion`.
- [ ] **AC-12**: Given no signals match, when detection runs, then the result is `unknown`.
- [ ] **AC-13**: When the detected league is `usssa`, `perfect_game`, `youth_travel`, `legion`, or `unknown`, the starter prediction output follows the Warning Output Contract (epic Technical Notes): `confidence="suppress"`, `data_note` carries a league-specific warning when the league is known (e.g., "USSSA pitch rules not yet supported") or a detection-failure message when unknown ("League not detected -- pitch count rules cannot be applied"), `rest_table` is populated with raw workload data but no availability/exclusion assessment, and `predicted_starter=None`, `alternative=None`, `top_candidates=[]`, `bullpen_order=[]`. No template changes needed.
- [ ] **AC-14**: When the detected league is `nsaa_varsity`, the starter prediction applies the NSAA rule set from E-217 (`get_nsaa_rules(reference_date)`). When the detected league is `nsaa_subvarsity`, the starter prediction applies a subvarsity rule set created by this story (90-pitch max year-round, same rest tiers as NSAA -- E-217 does not provide a subvarsity variant).
- [ ] **AC-15**: The reports path (`generate_report()`) extracts `ngb`, `age_group`, and `name` from the GC public team API response dict and passes them to detection before calling `compute_starter_prediction()`.
- [ ] **AC-16**: The dashboard path (both opponent detail and opponent print views in `src/api/routes/dashboard.py`) passes `program_type`, `classification`, and `team_name` from the DB to detection before calling `compute_starter_prediction()`. (`team_name` is needed because tracked opponents often lack `program_type`/`classification`, requiring the name-keyword fallback.)
- [ ] **AC-17**: Tests cover all detection priority levels and branches:
  - DB fields: `program_type`+`classification` combinations (AC-1 through AC-5 scenarios)
  - `ngb` single values: `["american_legion"]`, `["usssa"]`, `["nsaa"]`/`["nfhs"]` (with name-keyword level disambiguation)
  - `ngb` multi-value priority: e.g., `["usssa", "perfect_game"]` → first match in priority order
  - `ngb=["perfect_game"]` → `perfect_game`
  - Unrecognized `ngb` value (not in known list) → `unknown`
  - `ngb=[]` + `age_group` with "U" suffix → `youth_travel`
  - `ngb=[]` + `age_group` suggesting HS (e.g., "High School") → fall through to name keywords
  - Name keywords: at least one test per keyword category in the Team Name Keyword Table (epic Technical Notes)
  - No signals → `unknown` fallback

## Technical Approach
The detection function takes optional keyword arguments for each signal type and returns a league/level identifier string. It lives in `starter_prediction.py` alongside its single consumer. The signal priority cascade and keyword table are defined in the epic Technical Notes. `compute_starter_prediction()` gains a parameter for the detected league/level, which it uses to select the correct rule set via a dispatch function. When no rule set exists for the detected league, the function follows the Warning Output Contract (epic Technical Notes): `confidence="suppress"` with warning in `data_note`, `rest_table` populated with raw workload data but no availability assessment, prediction and bullpen order suppressed.

## Dependencies
- **Blocked by**: E-217-01 (NSAA availability engine must exist first -- will provide `PitchCountRules`, `RestTier`, `get_nsaa_rules()`, and the availability function that this story's detection dispatches to)
- **Blocks**: E-218-02

## Files to Create or Modify
- `src/reports/starter_prediction.py` -- add `detect_league_level()` function, modify `compute_starter_prediction()` to accept and use detected league/level
- `src/reports/generator.py` -- extract `ngb`, `age_group` from public API response dict, pass to detection before prediction call
- `src/api/routes/dashboard.py` -- pass `program_type`/`classification` to detection at both opponent detail and opponent print call sites
- `src/api/db.py` -- query `program_type`, `classification`, and `team_name` for tracked teams (dashboard path needs these fields for detection; `program_type`/`classification` not currently queried)
- `tests/test_league_detection.py` -- detection function unit tests (all priority levels, all keyword categories)
- `tests/test_starter_prediction.py` -- update existing tests for `compute_starter_prediction()` signature change (new league/level parameter)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-218-02**: The `detect_league_level()` function and the dispatch mechanism in `compute_starter_prediction()` that maps league identifiers to rule sets. E-218-02 adds the Legion rule constants and wires them into the dispatch.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The `ngb` field is a JSON-encoded string requiring double-parse: `json.loads(team["ngb"])` yields a list like `["usssa"]` or `["american_legion"]`.
- The NSAA `ngb` value is unknown. The detection function should handle `"nsaa"`, `"nfhs"`, and empty `ngb` (fall through to `age_group`/name parsing for HS teams).
- After E-218-01, `legion` is treated as an unsupported league (warning + suppression) -- same as `usssa`, `perfect_game`, `youth_travel`, and `unknown`. E-218-02 replaces the stub with real Legion rules, at which point `legion` moves to the "rules applied" group alongside `nsaa_varsity` and `nsaa_subvarsity`.
