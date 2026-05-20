# E-230-01: `src/charts/positioning.py` Chart Module + Unit Tests

## Epic
[E-230: Positioning Section Refactor (Scouting Reports)](./epic.md)

## Status
`DONE`

## Description

After this story is complete, the system will have a render-layer module `src/charts/positioning.py` that produces matplotlib PNG bytes for two purposes: a full-field team-level positioning chart (6 stars + outliers + density background) and a per-position cropped chart (single star + outliers + density, viewport-clipped to the position's zone). The module mirrors `src/charts/spray.py`'s PNG-bytes contract exactly — no in-image headers, caller-passed `figsize`, headless Agg rendering. The module is wired into the scouting report in story E-230-02; this story delivers only the module and its unit tests.

## Context

The scouting report currently embeds the same SVG renderer used by the standalone quarter-letter print bundle, which produces two bugs (duplicate-header from in-SVG text headers; pill collision from quarter-letter print geometry). E-230 fixes both bugs by giving the embedded surface its own render-layer module that returns pure-pixel PNGs sized for the report layout.

This story builds the module in isolation: no caller wiring, no template changes, no engine changes. The module is a pure consumer of existing data — the four query helpers in `src/reports/positioning_card.py` already cover all reads.

Per epic Technical Notes section TN-1 (mandatory branch implementation), dispatch creates the worktree from `epic/E-228-defensive-positioning-cards`, not from main. The base branch for all dispatch `git diff` references is `epic/E-228-defensive-positioning-cards`.

## Acceptance Criteria

- [ ] **AC-1**: A new module exists at `src/charts/positioning.py` containing two public functions per Technical Notes section TN-3: `render_team_position_chart` and `render_position_chart`. Both return `bytes`. Both accept `title: str | None = None` defaulting to no in-image title. Both accept `figsize` with defaults `(6, 4)` for the team chart and `(2.5, 2)` for the per-position chart.
- [ ] **AC-2**: The module declares `matplotlib.use("Agg")` at module scope before any pyplot import, matching the precedent in `src/charts/spray.py`.
- [ ] **AC-3**: A module-level constant `POSITION_VIEWPORTS: dict[str, tuple[float, float, float, float]]` is defined per Technical Notes section TN-5, with one entry for each of `LF`, `CF`, `RF`, `3B`, `SS`, `2B`. Each viewport is a ±60-px box around the corresponding `BASE_POSITIONS[position]` anchor in engine 320×480 SVG space.
- [ ] **AC-4**: Given a database connection with team-aggregate, batter-positioning, and spray-chart data for an opponent, when `render_team_position_chart(conn, public_id, season_id, perspective_team_id=N)` is called, then the returned bytes start with the PNG signature `b'\x89PNG\r\n\x1a\n'` and have length ≥ 1024.
- [ ] **AC-5**: Given the same database state, when `render_position_chart(conn, public_id, season_id, position, perspective_team_id=N)` is called for each of the six positions (`LF`, `CF`, `RF`, `3B`, `SS`, `2B`), then each returned bytes value starts with the PNG signature and has length ≥ 1024.
- [ ] **AC-6**: Given a position name not in `POSITION_VIEWPORTS` (e.g., `"P"` or `"C"`), when `render_position_chart` is called, then it raises a `ValueError` naming the unsupported position and listing the six supported positions.
- [ ] **AC-7**: Unit tests parametrize across all six positions and assert for each viewport `(xmin, xmax, ymin_bottom, ymax_top)`: `xmin < xmax`, `ymin_bottom > ymax_top` (y-axis inversion preserved per Technical Notes section TN-5), and the corresponding `BASE_POSITIONS[position]` `(x, y)` falls inside the viewport rectangle.
- [ ] **AC-8**: Unit tests for the density helper assert it produces non-empty matplotlib output when given a non-empty point list and produces a valid (zero-element) plot when given an empty list — no exception raised either way.
- [ ] **AC-9**: All new tests pass when run via `python -m pytest tests/ -v` (per `.claude/rules/pytest-verbose.md` — `-v` mandatory, no `-x`/`--exitfirst`).

## Technical Approach

Mirror `src/charts/spray.py` line-for-line wherever the patterns transfer:
- Headless Agg backend at module scope.
- PNG-bytes return via `fig.savefig(buf, format="png", dpi=150, bbox_inches="tight"); plt.close(fig)`.
- **Import field-drawing primitives from `src/charts/spray.py` — do NOT duplicate.** This includes `_FIELD_PATH_D`, `_raw_to_svg`, `_HOME_PTS`/`_1B_PTS`/`_2B_PTS`/`_3B_PTS`, `_FIELD_LINE`/`_BASE_FILL` color constants, and `_draw_field(ax)`. Duplication invites drift — if spray's field path or polygon constants ever update, the positioning chart's field will silently diverge. Cross-module private-name imports between sibling modules are in-pattern here: `src/reports/positioning.py:32` already imports `_raw_to_svg` from `src.charts.spray`, establishing precedent. Document the import surface in a one-line module comment at the top of `src/charts/positioning.py`.
- Axis convention `ax.set_xlim(xmin, xmax)` and `ax.set_ylim(ymin_bottom, ymax_top)` with `ymin_bottom > ymax_top` for inversion.

The four data reads come from existing helpers in `src/reports/positioning_card.py`:
- `_query_team_aggregate(conn, team_id, season_id, position) -> dict | None` — single star + bip_count + low-confidence flag. **This helper does NOT take `perspective_team_id` as a parameter** — it uses an internal prefer-then-fallback chooser and RETURNS the chosen `perspective_team_id` in its result dict. Callers extract `perspective_team_id` from the returned dict and thread it through the other three helpers; the value MUST match what `_choose_perspective_team_id` returns at the caller (they will, by construction — both apply the same standalone-perspective-preferred rule — but the spec asserts the equivalence).
- `_query_populated_zones(conn, team_id, season_id, position, perspective_team_id) -> set[str]` — outlier zones present for the position
- `_query_density_points(conn, team_id, season_id, perspective_team_id) -> list[tuple[float, float]]` — `(x, y)` pool for the density background, same pool for all 7 charts
- `_query_outlier_batters(conn, team_id, season_id, perspective_team_id, position) -> list[dict]` — outlier batter rows for pill placement

Internal helpers worth extracting for unit testability (no DB required):
- `_position_viewport(position) -> tuple[float, float, float, float]` — lookup with `ValueError` per AC-6.
- `_draw_field(ax)` — imported from `src.charts.spray` (do not duplicate; see Technical Approach bullet on field-drawing imports).
- `_draw_stars(ax, stars)` — draw 1 or 6 stars in engine space.
- `_draw_outlier_pills(ax, outliers)` — project deviations to `(x, y)` per `src/reports/positioning_card.py` patterns, scatter pills with zone-letter labels.
- `_draw_density(ax, points)` — `ax.scatter(xs, ys, s=4, c="#000", alpha=0.12)` per Technical Notes section TN-9.

`perspective_team_id` is a required keyword argument on both public functions — callers (story E-230-02) thread the same id into all 7 chart calls per Technical Notes section TN-4. The module itself never resolves perspective; that's the caller's responsibility.

Test approach: parametrize fixture-based unit tests over the six positions. Mock or monkeypatch the four `_query_*` helpers to return canned shapes; this avoids requiring a populated test DB for the chart-rendering path. Use small synthetic inputs (~10 density points, 1-3 outliers per position) to keep test runtime trivial. PNG signature + length assertions per AC-4/5 are the slot-fill content assertions per `.claude/rules/testing.md`.

## Dependencies

- **Blocked by**: None
- **Blocks**: E-230-02

## Files to Create or Modify

- `src/charts/positioning.py` — new module
- `tests/charts/test_positioning.py` — new test file

## Agent Hint

software-engineer

## Handoff Context

- **Produces for E-230-02**: A `src/charts/positioning.py` module exposing `render_team_position_chart` and `render_position_chart` per Technical Notes section TN-3. Story E-230-02 imports and wires these into `_build_scouting_report_positioning_payload`, derives `perspective_team_id` once via `_choose_perspective_team_id`, and threads it through all 7 chart calls (1 team-level + 6 per-position) per Technical Notes section TN-4. The two public functions are the integration contract.

## Definition of Done

- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes

- Worktree base reminder per epic Technical Notes section TN-1: this story executes in `/tmp/.worktrees/baseball-crawl-E-230` which branches from `epic/E-228-defensive-positioning-cards`, NOT main. All `git diff` references during dispatch compare against the E-228 branch.
- The bundle path (`src/reports/positioning_card.py` + `src/reports/positioning_bundle.py`) is NOT modified in this story. The new module is a sibling at `src/charts/positioning.py`; existing positioning_card/positioning_bundle are untouched.
