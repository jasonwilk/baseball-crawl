# E-264-03: Visible ERA-basis disclosure on the report

## Epic
[E-264: League-Aware ERA Basis Fix](epic.md)

## Status
`DONE`

## Description
After this story is complete, every ERA on the report will disclose the game-length basis it was computed on. The Pitching table's ERA column header carries the basis (e.g. `ERA (7-inn)`), an assumed/fallback basis is marked with an asterisk and a one-time footnote, and the standalone key-player card ERA carries the inline basis label. A coach comparing ERAs across teams or reports always knows which game length produced each number, and an assumed basis is never presented silently.

## Context
baseball-coach ruled that the basis must be shown on ERA in BOTH the known and assumed cases (not only the fallback), because a coach can compare ERAs computed on different game lengths and needs the signal — a coaching-integrity requirement, consistent with `.claude/rules/display-philosophy.md` ("never suppress, always contextualize"). The exact copy, placement, and wording rules are fixed in epic Technical Notes TN-7. The report's Pitching table is a single-team table with one ERA header (`scouting_report.html:673`), so the preferred header-level form applies; the key-player card (`scouting_report.html:648`) is a standalone ERA that uses the inline form. The "assumed" signal is the raw NULL `innings_per_game` on the pitcher rows (E-264-01 / TN-3): `assumed = innings_per_game is None`.

## Acceptance Criteria
- [ ] **AC-1**: The renderer passes the team's basis value and its assumed flag (`assumed = innings_per_game is None`, per Technical Notes TN-3/TN-7) into the report template context so the template can render the basis label.
- [ ] **AC-2**: The Pitching table ERA column header renders the header-level copy from Technical Notes TN-7 verbatim — `ERA (7-inn)` for a known basis (with the actual value substituted, e.g. `ERA (6-inn)`), and `ERA (7-inn)*` for an assumed basis. Given a report for a team with a fetched basis of 6, when rendered, then the header reads `ERA (6-inn)` with no asterisk; given a team with a NULL basis, then the header reads `ERA (7-inn)*`.
- [ ] **AC-3**: When (and only when) the basis is assumed, the exact footnote from Technical Notes TN-7 is printed once under the table: `* Game length not available from GameChanger for this team -- ERA assumed on a 7-inning basis.` Given a known-basis report, when rendered, then no such footnote appears.
- [ ] **AC-4**: The standalone key-player card ERA (`scouting_report.html:648`) renders the inline-form basis label from Technical Notes TN-7 — `4.50 (7-inn)` known, `4.50 (7-inn)*` assumed (value substituted).
- [ ] **AC-5**: No raw field name (`innings_per_game`) is user-facing anywhere; the compact forms use `-inn` and the footnote spells "inning" (per TN-7). Renderer/rendering tests (`tests/test_report_renderer.py`, `tests/test_report_rendering.py`) cover the known header, the assumed header + footnote, and the inline card label; `python -m pytest tests/` is green.

## Technical Approach
Read the basis + assumed flag from the reader-carried `innings_per_game` on a pitcher row (E-264-01; a team-level constant, identical across the team's pitcher rows). Do NOT use a team-info query — no story widens `_query_team_info` (`generator.py:368`) to carry it, and this story is renderer + template only. Both ERA surfaces are truthiness-guarded (`{% if has_pitching %}` on the Pitching table, `{% if key_players.top_pitcher %}` on the card), so a pitcher row always exists whenever a basis label renders. Render the header-level label on the Pitching table's ERA `<th>` and the conditional footnote under the table; render the inline label on the key-player card ERA. The specific fixture teams carrying basis 6, a known basis, and NULL/assumed are those E-264-02 seeds and documents in `seed.sql` (per its Handoff Context) — assert against that documented mapping so the AC-2/AC-3 expectations are unambiguous. Use the strings in TN-7 verbatim — do not paraphrase. If the compact header form does not fit the existing `<th>` markup, flag baseball-coach for shorter copy rather than dropping the label (TN-7); do not invent alternative wording. Follow `.claude/rules/jinja-safety.md` (no `| safe` on any dynamic value).

## Dependencies
- **Blocked by**: E-264-02 (labels the corrected ERA; shares `src/reports/renderer.py` and needs the fixture's NULL-basis and 6-inn teams to assert against)
- **Blocks**: None

## Files to Create or Modify
- `src/reports/renderer.py` (modify — pass basis + assumed flag to template context)
- `src/api/templates/reports/scouting_report.html` (modify — ERA header label + footnote + key-player card inline label)
- `tests/test_report_renderer.py`, `tests/test_report_rendering.py` (modify/add coverage per AC-5)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Copy is fixed by baseball-coach (epic TN-7). Placement is header-level for the Pitching table and inline for the key-player card because the table is single-team; both string sets are coach-provided.
