# E-218-02: Legion Pitch Count Rule Set

## Epic
[E-218: League/Level Detection for Pitch Rules](epic.md)

## Status
`TODO`

## Description
After this story is complete, when the detection function identifies a team as American Legion, the starter prediction engine will apply Legion-specific pitch count rules (105-pitch max, Legion rest tiers) instead of showing a "rules not available" warning. This is the first non-NSAA rule set, validating the detection-to-dispatch pipeline end-to-end.

## Context
E-218-01 adds `detect_league_level()` and the dispatch mechanism in `compute_starter_prediction()`. When `legion` is detected, E-218-01 stubs it as unsupported (warning + suppression). This story replaces the stub with real Legion rules using the same `PitchCountRules` / `RestTier` data model that E-217 creates for NSAA.

Legion uses pitch-count-based rest tiers (same structural model as NSAA) but with different thresholds and a lower daily max. The consecutive-days rule is identical to NSAA (max 2 appearances in 3-day period). The Legion same-day limit (>45 pitches in game 1 -> cannot pitch game 2) is out of scope per the epic Non-Goals.

## Acceptance Criteria
- [ ] **AC-1**: Legion rest tiers are defined as rule constants per the epic Technical Notes "Legion Rest Requirements" table (0-30/0d, 31-45/1d, 46-60/2d, 61-80/3d, 81+/4d, max 105).
- [ ] **AC-2**: When `detect_league_level()` returns `legion`, `compute_starter_prediction()` applies Legion rest tiers (not NSAA) to determine pitcher availability.
- [ ] **AC-3**: Given a Legion pitcher who threw 48 pitches 1 day ago, the pitcher IS excluded (Legion 46-60 tier = 2 days rest). Under NSAA, 48 pitches falls in the 31-50 tier (1 day rest) so the same pitcher would be available -- confirming Legion's tighter mid-range tiers produce different outcomes.
- [ ] **AC-4**: Given a Legion team where a pitcher threw 82 pitches 3 days ago, the pitcher IS excluded (Legion 81+ tier = 4 days rest required, only 3 elapsed). Under NSAA pre-April rules, this same pitcher would be available (71-90 tier = 3 days, 3 elapsed).
- [ ] **AC-5**: The Legion daily max is 105. The `PitchCountRules` constant reflects this.
- [ ] **AC-6**: Given a Legion pitcher with appearances on each of the prior 2 consecutive days, when availability is computed for today, then the pitcher IS excluded (max 2 appearances in 3-day period). This confirms the consecutive-days check (shared with NSAA) works correctly under Legion rules.
- [ ] **AC-7**: When `legion` is detected, the "rules not available" warning from E-218-01 is no longer shown. Instead, normal availability assessment is displayed with Legion rules applied.
- [ ] **AC-8**: Tests cover Legion-specific rest tier boundaries (edge cases at 30/31, 45/46, 60/61, 80/81 pitches) and the 105-pitch max.

## Technical Approach
Add Legion rule constants (frozen dataclasses) alongside the NSAA constants that E-217 creates. Wire them into the rule dispatch function so that when `detect_league_level()` returns `legion`, the Legion `PitchCountRules` are used. Legion has no season-phase split (unlike NSAA's pre/post April 1 boundary), so a single constant suffices. The consecutive-days check is league-agnostic and requires no changes.

## Dependencies
- **Blocked by**: E-218-01 (detection function and dispatch mechanism must exist)
- **Blocks**: None

## Files to Create or Modify
- `src/reports/starter_prediction.py` -- add Legion `PitchCountRules` constant, wire into rule dispatch
- `tests/test_starter_prediction.py` -- Legion-specific availability tests (rest tier boundaries, max pitches, AC-4 differential scenario)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- Legion has no season-phase split (no pre/post April 1 boundary). The 105-pitch max and rest tiers apply year-round.
- The AC-4 scenario (82 pitches, 3 days ago) is the key differential test: Legion requires 4 days rest for 81+ pitches, while NSAA requires only 3 days for 71-90 pitches. Same pitcher, different outcome depending on detected league.
- The Legion same-day limit (>45 pitches in game 1 -> cannot pitch game 2 same day) is explicitly out of scope for this story and this epic.
- Legion Seniors and Juniors divisions use identical pitch count rules (confirmed by domain expert). The single `legion` identifier covers both.
- NSAA sub-varsity levels (JV, Freshman, Reserve) share identical rest tiers with varsity. The only difference is the daily max (90 year-round vs 110 post-April 1). The subvarsity rule set is created by E-218-01, not by E-218-02.
- Tests for this story go in `tests/test_starter_prediction.py` (extending the existing test file, not creating a new one). E-218-01's detection tests live separately in `tests/test_league_detection.py`.
