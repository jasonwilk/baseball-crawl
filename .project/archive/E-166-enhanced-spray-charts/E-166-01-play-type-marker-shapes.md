# E-166-01: Play Type Marker Shapes and Legend

## Epic
[E-166: Enhanced Spray Charts](epic.md)

## Status
`DONE`

## Description
After this story is complete, the spray chart renderer will differentiate BIP events by play type using four distinct marker shapes (circle, triangle, diamond, square) while preserving the existing hit/out color coding. The DB queries will include `play_type` in the result set, and the legend will use a two-row layout showing both outcome colors and play type shapes.

## Context
The `play_type` column exists in the `spray_charts` table and is populated by the spray chart loader, but `src/api/db.py` queries only SELECT `x, y, play_result`. The renderer (`src/charts/spray.py`) currently draws all events as `plt.Circle()` patches. This story adds play type awareness end-to-end: DB query → renderer → legend.

## Acceptance Criteria
- [ ] **AC-1**: Given a spray chart with events of different play types, when the chart is rendered, then each play type uses the marker shape defined in Technical Notes TN-1 (ground_ball/hard_ground_ball/bunt → circle, line_drive/hard_line_drive → triangle, fly_ball → diamond, popup/pop_fly/pop_up → square).
- [ ] **AC-2**: Given events with `play_type=NULL`, `other`, or an unrecognized value, when the chart is rendered, then those events use the circle (fallback) marker shape.
- [ ] **AC-3**: The hit/out color scheme is unchanged per Technical Notes TN-2 — marker color encodes outcome, marker shape encodes contact type.
- [ ] **AC-4**: The chart legend uses a two-row layout per Technical Notes TN-3: Row 1 shows outcome colors (green Hit, red Out); Row 2 shows play type shapes in neutral gray.
- [ ] **AC-5**: `get_player_spray_events()` and `get_team_spray_events()` in `src/api/db.py` include `play_type` in the SELECT clause per Technical Notes TN-5.
- [ ] **AC-6**: The existing rendering behaviors are preserved: coordinate transforms, HR zone bubbles, hit/out classification, z-order (outs rendered before hits).
- [ ] **AC-7**: Existing tests in `tests/test_charts/test_spray.py` continue to pass, and new tests verify play type marker differentiation, NULL fallback behavior, and two-row legend structure.

## Technical Approach
The renderer needs to migrate from individual `plt.Circle()` patches to `ax.scatter()` calls grouped by play type and outcome, per Technical Notes TN-4. The DB queries need a one-column addition per TN-5. The legend rendering logic needs to produce two rows per TN-3. The marker shape mapping is defined in TN-1.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/api/db.py` — add `play_type` to SELECT in `get_player_spray_events()` and `get_team_spray_events()`
- `src/charts/spray.py` — migrate to scatter markers, add play type shape mapping, update legend
- `tests/test_charts/test_spray.py` — new tests for play type markers, NULL fallback, two-row legend

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The `play_type` values in the DB come from GameChanger's `playType` attribute (open enum, stored raw by the loader). Known values per API docs: `ground_ball`, `hard_ground_ball`, `line_drive`, `hard_line_drive`, `fly_ball`, `popup`, `pop_fly`, `pop_up`, `bunt`, `other`. The API uses three spellings for popup-type plays across different endpoints — all must map to square. See TN-1 for the full mapping.
- Marker size must be distinguishable at mobile display widths (~375px rendered PNG width).
- Per Test Scope Discovery (`testing.md`), `tests/test_dashboard.py` must be run alongside `tests/test_charts/test_spray.py` — it exercises the spray chart routes via TestClient and will surface any NULL handling regressions. The dashboard test fixture inserts spray events without `play_type`, so `play_type=None` will flow through the renderer — AC-2's NULL fallback must handle this correctly.
