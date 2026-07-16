# E-265-01: Per-pitcher per-appearance derivation layer

## Epic
[E-265: Pitcher Outings Breakdown](epic.md)

## Status
`TODO`

## Description
After this story is complete, a new derivation module produces, for the scouted opponent, one typed structure per pitcher: a season summary line (IP, G, GS, ERA on E-264's basis, WHIP, FPS%, plus the rate set K/BF | BB/INN | K/BB | H/BF with small-sample flags) and a chronological list of per-appearance outings (Date, Opponent, IP, BF, H, HR-allowed, BB, K, R, FPS%, per-outing ERA, and a computed green "strong-outing" flag). This is the data the renderer (E-265-02) consumes; it writes nothing to the DB.

## Context
The report already stores per-game boxscores (`player_game_pitching`) and plays (`plays`/`play_events`); opponent season-stats is 403, so all outing stats derive from those. The boxscore base is `get_pitching_history` (`src/api/db.py`), which already returns per-appearance rows with the perspective filter baked in. The plays-derived values (HR-allowed, FPS%) and all aggregation/derivation logic live in a new `src/reports/pitcher_outings.py` module (the `starter_prediction.py` / `recon_scoreboard.py` read-and-derive precedent). See epic TN-2 (per-outing columns), TN-3 (season rate set + caveats), TN-4 (green thresholds), TN-5 (ERA basis), TN-6 (perspective/role filter, plays-off-outings, NULL handling, placement).

## Acceptance Criteria
- [ ] **AC-1**: Given a scouted team + season, the derivation returns one entry per pitcher, each with a chronological list of per-appearance outings carrying the epic TN-2 fields (Date, Opponent faced, IP, BF, H, HR-allowed, BB, K, R, FPS%, per-outing ERA). Boxscore fields (IP/BF/H/BB/K/R) come from `player_game_pitching`; HR-allowed (`plays.outcome = 'Home Run'`) and FPS% are derived from plays per epic TN-6, and the plays aggregation is driven OFF the completed-game boxscore outings (not independently enumerated from `plays` — epic TN-6, finding F12).
- [ ] **AC-2**: Per-outing ERA is computed as `ER × (innings_per_game × 3) / ip_outs` on the scouted team's E-264 `teams.innings_per_game` basis (fallback 7). Because E-264 ships NO reusable accessor and does NOT thread the basis onto `get_pitching_history`, E-265 obtains the basis via a seam it owns (a scalar read of `teams.innings_per_game` for the scouted team, or extending `get_pitching_history`) and re-applies the fallback `basis = innings_per_game if innings_per_game is not None else 7` (explicit `is not None`, NOT `if not`). It does NOT use the hardcoded 9-inning `× 27`, does NOT re-fetch from the API, and does NOT touch E-264's two season-ERA sites (epic TN-5, finding F1). When `ip_outs = 0` the per-outing ERA is `None`, never a divide-by-zero.
- [ ] **AC-3**: Each pitcher's season summary line carries the FULL context set per epic TN-3 — IP, G, GS, ERA (on the E-264 basis), WHIP, FPS% — PLUS the rate set K/BF, BB/INN, K/BB, H/BF (NOT K/9 or K/G). Each of the four rate stats is flagged for the small-sample caveat when the pitcher's season `ip_outs < 45` (< 15 IP), and K/BB additionally carries its underlying BB count when season `bb < 5`. When season BB = 0, K/BB returns a value that DISTINGUISHES the zero-walk case (a command strength) from the genuine no-data case, so the renderer can present it as a strength rather than a blank (epic TN-3/TN-6, finding F11). No stat is suppressed regardless of sample.
- [ ] **AC-4**: Every rollup applies the perspective/role filter of epic TN-6: pitching rows scoped `team_id = perspective_team_id = scouted`; plays scoped `perspective_team_id = scouted AND batting_team_id != scouted AND pitcher_id = pitcher`. A game loaded from two perspectives yields exactly one set of outings for a pitcher (no double-count) — asserted by a two-perspective test.
- [ ] **AC-5**: The green "strong-outing" boolean is set on an outing iff it meets ANY ONE of the four epic TN-4 criteria — where the Aggression criterion (2) gates on the charted-PA count (`pitch_count > 0`, the FPS% denominator), NOT raw BF (finding F8). The TN-4 sample floor (`BF < 10 AND IP < 2`) is a defensive backstop that every criterion's own gate already exceeds, so a green-qualifying row has necessarily cleared it (finding F2) — a sub-floor outing meets no criterion and is unflagged; do NOT construct an (impossible) "meets a criterion but below floor" test case. (Rendered in E-265-02; computed and unit-tested here.)
- [ ] **AC-6**: Rate stats (FPS%, K/BF, BB/INN, K/BB, H/BF, per-outing ERA) yield `None` when their denominator is absent/zero — never 0 and never a crash (epic TN-6); the K/BB zero-BB case returns a value distinguishable from the no-data `None` (per AC-3). Excluded stats (velocity/pitch-mix, W/L/SV, S%, extended Group-C, Group-E) are absent (epic Non-Goals).

## Technical Approach
Reuse `get_pitching_history` for the per-appearance boxscore base (it already carries the pitching perspective filter) and drive the plays aggregation off those completed-game outings (epic TN-6, F12). Add the opponent-faced value (extend the shared SELECT with a regression check on existing consumers, OR resolve it in the new module — implementer's choice). Read the ERA basis via a seam E-265 owns (scalar `teams.innings_per_game` read for the scouted team, or extend `get_pitching_history`) and re-apply the explicit `is not None` fallback (F1) — E-264 exposes no accessor. Build the plays-derivation (HR-allowed via `plays.outcome = 'Home Run'` — mirror the `recon_scoreboard`/`plays_parser` convention with a module-local `_HR_OUTCOMES`; FPS% reusing the charted-PA `pitch_count > 0` denominator CONVENTION, not the `_query_plays_pitching_stats` function itself, which lacks the `batting_team_id != scouted` role clause — F7), the per-outing ERA, the season rate aggregation (incl. H/BF), the small-sample flags, and the green-outing flag in a new `src/reports/pitcher_outings.py` returning typed dataclasses. Also add the module-level `is_pitcher_outings_enabled()` flag reader here (owned by this story; E-265-02 only wires it). See epic TN-6 for placement and the exact role filter. Do NOT touch E-264's ERA sites.

## Dependencies
- **Blocked by**: E-264 (epic — provides the `teams.innings_per_game` column; there is NO reusable accessor, so E-265 reads the column directly per epic TN-5. Must complete before this starts.)
- **Blocks**: E-265-02

## Files to Create or Modify
- `src/reports/pitcher_outings.py` (new — derivation module: plays-derivation, aggregation incl. H/BF, per-outing ERA, green-flag, `is_pitcher_outings_enabled()`, typed dataclasses)
- `src/api/db.py` (only if extending `get_pitching_history` to carry the opponent faced and/or `innings_per_game`; otherwise the opponent + basis are read via scalar `teams`/`games` queries in the new module — implementer's choice)
- `tests/` (new derivation tests: per-outing fields incl. HR = 'Home Run'; ERA basis incl. a non-7 basis + explicit `is not None` fallback on a NULL/absent basis + `ip_outs=0`; rate set incl. H/BF + small-sample flags + the BB=0 distinguishable case; perspective/role two-perspective no-double-count; green-flag criteria incl. the charted-PA gate on criterion 2; None-not-0 denominators)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-265-02**: the typed per-pitcher outings structure (season summary line + per-appearance outing list with the green-outing flag and the distinguishable zero-BB K/BB marker) and the `is_pitcher_outings_enabled()` flag reader that E-265-02 wires into the generator/template.
- **Produces for E-265-03**: the concrete field set available per outing and per season line (incl. H/BF and the zero-BB marker), so the layout spec maps columns to real data.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing (including the two-perspective no-double-count test, the criterion-2 charted-PA gate test, and the BB=0 distinguishable-marker test)
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests (esp. any `get_pitching_history` consumers if its SELECT was extended)

## Notes
data-engineer confirmed feasibility with no migration and no new index. HR-allowed and FPS% are plays-derived (no per-game boxscore column). The ~90–95% pitcher-attribution caveat (epic TN-6) is a directional-read caveat surfaced to coaches in E-265-04, not a correctness bug here.
