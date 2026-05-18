# IDEA-078: Extract Per-Team Scouting Query Helpers from `positioning_bundle.py` + `generator.py` into `src/api/db.py`

## Status
`CANDIDATE`

## Summary
Extract the small per-team scouting query helpers currently duplicated in `src/reports/positioning_bundle.py` (and partially mirrored in `src/reports/generator.py`) into `src/api/db.py` per the CLAUDE.md "Shared query functions" rule. Both `generator.py` and `positioning_bundle.py` then import from `src/api/db.py`, breaking the circular-import constraint that forced the duplication in the first place.

## Why It Matters
CLAUDE.md "Shared query functions" rule: *"When both dashboard and reports need the same data, the query logic lives in a shared function in `src/api/db.py`."* During E-229-08 codex remediation (F2), SE added 7 small per-stat query helpers to `positioning_bundle.py`: `_query_team_record`, `_query_runs_per_game`, `_query_team_bip_count`, `_query_next_game_date`, `_query_team_name`, `_query_team_low_confidence`. The same SQL exists in `src/reports/generator.py` for the standalone scouting report's `data["team"]["record"]` block. SE chose to duplicate the SQL because `generator.py` already imports `generate_positioning_bundle` from `positioning_bundle.py` at module top, so the reverse import would create a cycle.

The duplication is small now but tends to drift over time: the dashboard and reports surfaces will compute the same stat slightly differently, and divergence between them is exactly what the shared-query rule exists to prevent. Routing both consumers through `src/api/db.py` is the canonical pattern (already established for `get_pitching_workload()` and `finalize_opponent_resolution()`).

## Acceptance Criteria Sketch
- Shared helpers live in `src/api/db.py` as the single source of truth.
- `generator.py` and `positioning_bundle.py` both import from `src/api/db.py` (no circular import).
- All E-229 + standalone scouting report tests pass unchanged.

## Rough Timing
Touch-three-subsystems refactor; not urgent. Trigger to promote:
- A second consumer (e.g., dashboard, standalone report viewer) starts needing one of the helpers and re-implements it.
- A coaching-visible stat divergence is observed between the bundle's opponent-context-card and the dashboard's same stat.

## Dependencies & Blockers
- [ ] E-229 closure merges to `epic/E-228-defensive-positioning-cards` (so the helpers in `positioning_bundle.py` exist as the extraction source)
- [ ] No active in-flight epic mutating the same helpers (avoid merge-churn)

## Open Questions
- Which helpers move? Just the 7 added in E-229-08 F2, or sweep similar private helpers from `generator.py` at the same time?
- Should the extracted helpers be named with a `scouting_` prefix in `src/api/db.py`, or grouped under a `scouting/` submodule?
- Is there a test-coverage gap to close as part of the extraction (the helpers are currently exercised only via bundle assembly tests)?

## Notes
Source: code-reviewer non-blocking finding during E-229 codex pre-closure remediation review (2026-05-18). Affected files at time of capture: `src/reports/positioning_bundle.py` (7 helpers added in E-229-08 R3), `src/reports/generator.py` (similar helpers pre-exist), `src/api/db.py` (extraction target). Related canonical pattern precedents: `get_pitching_workload()` in `src/api/db.py` (E-196), `finalize_opponent_resolution()` in `src/api/db.py`.

---
Created: 2026-05-18
Last reviewed: 2026-05-18
Review by: 2026-08-16
