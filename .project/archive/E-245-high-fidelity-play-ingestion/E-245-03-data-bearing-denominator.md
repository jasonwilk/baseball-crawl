# E-245-03: Data-bearing pitch-detail denominator + honest pitch-charted coverage badge

## Epic
[E-245: High-Fidelity Play Ingestion](epic.md)

## Status
`DONE`

## Description
After this story is complete, the report's pitch-detail rate stats (FPS%, P-PA, P-BF) will be
computed over charted plate appearances only, so un-charted PAs no longer dilute the rate; QAB% will
keep its all-PA denominator (every PA is a QAB opportunity — its NUMERATOR is not fully
outcome-derived, but that is recovered upstream by E-245-02, not by gating the denominator; see epic
TN-5); and the report will present honest pitch-charted coverage — a "Pitch-charted: N of M games"
badge, an inline charted-game count beside each pitch-detail stat, and, for teams with zero
pitch-charted games, one of TWO notes per TN-5: a full "no pitch-by-pitch data" note when there are
no plays at all, or a narrowed "pitch-charting not available" note (with QAB% still shown) when plays
exist but none are charted — never suppression. The result is a report whose pitch-detail numbers a
coach can trust and weight correctly.

## Context
`src/reports/generator.py` computes FPS% / P-PA / P-BF as `SUM(...) / COUNT(*)` over ALL plays
(`_query_plays_pitching_stats`, `_query_plays_batting_stats`, `_query_plays_team_stats`). When a
game's PAs are not pitch-charted, those PAs sit in the denominator with zero `pitch_count` and drag
the rate toward zero — the same family of distortion the parser bug (E-245-02) caused, but at query
time. The coverage badge and per-stat copy are built in `src/reports/renderer.py` and rendered in
`src/api/templates/reports/scouting_report.html`. The denominator policy and exact coach-facing copy
are resolved in epic TN-5; the never-suppress principle is `.claude/rules/display-philosophy.md`.
This story is independent of E-245-02 (different files) but is most visibly correct after that
story's reload populates `pitch_count`.

## Acceptance Criteria
- [ ] **AC-1**: Given the pitching and team pitch-detail queries, when FPS% and P-BF are computed,
      then the denominator counts only PAs with `pitch_count > 0` (charted PAs), per epic TN-5.
- [ ] **AC-2**: Given the batting and team pitch-detail queries, when P-PA is computed, then the
      denominator counts only PAs with `pitch_count > 0`, per epic TN-5.
- [ ] **AC-3**: Given QAB%, when it is computed, then it KEEPS its all-PA denominator (NOT gated on
      `pitch_count > 0`) and is surfaced with its own games-with-plays count, distinct from the
      pitch-charted coverage, per epic TN-5 (QAB Denominator Policy + Two distinct coverage counts).
- [ ] **AC-4**: Given the team-level coverage, when the badge renders, then it reads
      `"Pitch-charted: N of M games"` where N = pitch-charted games (games with ≥1 charted PA,
      perspective-scoped) and M = games to date, per epic TN-5.
- [ ] **AC-5**: Given a pitch-detail stat with at least one charted game, when it renders, then the
      charted-game count rides the same line (e.g. `"FPS% 64% (4 charted games)"`), and the sparse
      case (1–3 games) uses the same format with the count as the warning, per epic TN-5.
- [ ] **AC-6**: Given a team with zero pitch-charted games AND zero games-with-plays (no plays at
      all), when the report renders, then the pitch-detail section is still shown with the full note
      `"No pitch-by-pitch data available for this team"` — never suppressed (epic TN-5 case (a)).
- [ ] **AC-7**: Given a team with zero pitch-charted games BUT some games-with-plays (plays exist,
      none pitch-charted), when the report renders, then QAB% still renders with its games-with-plays
      count, and FPS%/P-PA/P-BF show the NARROWED note `"Pitch-charting not available — FPS% and P/PA
      cannot be computed"` (NOT the "no data" note — the team has plays data) — never suppressed
      (epic TN-5 case (b)).

## Technical Approach
Restrict the FPS%/P-PA/P-BF aggregate denominators in the three `_query_plays_*` functions to
charted PAs, leave the QAB% denominator at all-PA, and derive the two coverage counts
(pitch-charted games; games-with-plays). Carry both counts and the per-stat charted counts into the
renderer context and render the badge, inline counts, and zero-charted note per the resolved copy in
epic TN-5. Preserve the existing perspective scoping (`perspective_team_id = team_id`) and game-id
scoping in the queries. Verify with fixtures that mix charted and un-charted PAs across games,
including a zero-charted team.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/reports/generator.py` (`_query_plays_pitching_stats`, `_query_plays_batting_stats`, `_query_plays_team_stats`; the pitch-charted vs. games-with-plays counts)
- `src/reports/renderer.py` (badge text, inline per-stat charted count, zero-charted note context)
- `src/api/templates/reports/scouting_report.html` (render the badge, inline counts, and zero-charted note)
- `tests/test_report_generator.py` and/or `tests/test_report_plays.py` (mixed charted/un-charted PA fixtures; both coverage counts; QAB all-PA; zero-charted note)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
- [ ] Test scope discovery run for every modified module (per `.claude/rules/testing.md`)

## Notes
Coach-facing copy and the QAB policy are the resolved baseball-coach decisions in epic TN-5 — do not
re-derive them. See `.claude/rules/testing.md` for the disk-backed `db` fixture deadlock gotcha in
`tests/test_report_generator.py` before writing report-generator tests.
