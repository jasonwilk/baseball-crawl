# E-223: E-220 Adopter Audit -- Fix Pre-Provenance Code Paths

## Status
`COMPLETED`

## Overview
E-220 introduced `perspective_team_id` as an architectural invariant, but nobody walked the graph of existing consumers to adopt it. A systematic audit found four code paths still operating on the pre-provenance model -- producing wrong counts, double-counted summaries, and unnecessary load work. This epic fixes all four findings.

## Background & Context
E-220 established perspective provenance (`.claude/rules/perspective-provenance.md`) and did thorough work on data-critical paths: season aggregation, dashboard queries, player dedup, team merge/reassign, DELETE cascades, game dedup, and plays idempotency are all correct. E-221 closed the three remaining high-priority residuals. This epic addresses the four lower-priority findings from the post-E-220 adopter audit (IDEA-071).

**Expert consultations:**
- **SE + DE on F-1 design question**: Both recommend exact-match counts mirroring the cascade, not a broader "blast radius" number. The confirmation page is an informed-consent gate; overstated/understated counts erode trust. SE notes `WHERE perspective_team_id = ? OR team_id = ?` is simpler than the current game-subquery pattern. DE recommends `UNION` on `rowid` for dedup safety. Both note `plays` uses `batting_team_id` (not `team_id`) as its anchor FK.
- **SE on F-3 backfill lifecycle**: Confirmed one-time migration aid for E-204. New rows get `appearance_order` at INSERT time. No operational value fixing perspective handling; deprecation comment is sufficient.

Promoted from: [IDEA-071](/.project/ideas/IDEA-071-e220-adopter-audit-fix-pre-provenance-code.md)

## Goals
- Admin delete confirmation counts accurately reflect what the cascade will delete
- Reconciliation summary does not double-count discrepancies across perspectives
- Spray loaders skip already-loaded perspectives at the game level (efficiency)
- Backfill script is marked as deprecated one-time migration aid

## Non-Goals
- Modifying the actual cascade delete logic (already correct)
- Fixing the cross-perspective safety gate (already correct, updated in E-221)
- Adding perspective awareness to any data-critical aggregation paths (already correct)
- Rewriting the backfill script for ongoing use

## Success Criteria
- All four findings from IDEA-071 are resolved
- The cleanup-detection mirror invariant (`.claude/rules/data-model.md`) is satisfied: confirmation counts mirror the cascade surface
- No regressions in existing admin, reconciliation, or loader tests

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-223-01 | Fix admin delete confirmation counts to mirror cascade | DONE | None | - |
| E-223-02 | Fix reconciliation summary perspective double-counting | DONE | None | - |
| E-223-03 | Add perspective gate to spray loaders + deprecate backfill | DONE | None | - |

## Dispatch Team
- software-engineer

## Technical Notes

### TN-1: Cascade Two-Pass Structure (Reference)

The canonical cascade in `src/reports/generator.py::_delete_team_anchor_and_orphan_data` uses two passes:

- **Pass 1 (perspective)**: `WHERE perspective_team_id = T` on `play_events` (via plays), `plays`, `player_game_batting`, `player_game_pitching`, `spray_charts`, `reconciliation_discrepancies`, `game_perspectives`.
- **Pass 2 (anchor)**: `WHERE team_id = T` (or `batting_team_id = T` for `plays`) on `play_events` (via plays), `plays`, `player_game_batting`, `player_game_pitching`, `spray_charts`, `reconciliation_discrepancies`.

The confirmation counts must mirror this exact surface. For tables with both FK dimensions, the count is the union of rows matching either condition (deduplicated). For `game_perspectives`, only `perspective_team_id` applies.

### TN-2: FK Column Mapping Per Table

| Table | Pass 1 (perspective) | Pass 2 (anchor) |
|-------|---------------------|-----------------|
| `player_game_batting` | `perspective_team_id` | `team_id` |
| `player_game_pitching` | `perspective_team_id` | `team_id` |
| `spray_charts` | `perspective_team_id` | `team_id` |
| `plays` | `perspective_team_id` | `batting_team_id` |
| `play_events` | via `plays.perspective_team_id` | via `plays.batting_team_id` |
| `reconciliation_discrepancies` | `perspective_team_id` | `team_id` |
| `game_perspectives` | `perspective_team_id` | N/A |

### TN-3: Plays Loader Perspective Gate (Correct Reference)

`src/gamechanger/loaders/plays_loader.py` line ~149 demonstrates the correct whole-game idempotency check:
```sql
SELECT 1 FROM plays WHERE game_id = ? AND perspective_team_id = ? LIMIT 1
```
The spray loaders should follow an equivalent pattern to skip already-loaded game+perspective combinations before attempting per-row inserts.

## Open Questions
None -- all resolved during discovery.

## History
- 2026-04-13: Created (promoted from IDEA-071). SE + DE consulted on F-1 design question and F-3 backfill lifecycle.
- 2026-04-14: Set to READY after 3 internal review iterations + 1 Codex spec review.
- 2026-04-14: Dispatch started.
- 2026-04-14: All 3 stories DONE. COMPLETED. All four IDEA-071 findings resolved: admin delete confirmation counts now mirror the cascade two-pass surface, reconciliation summary deduplicates across perspectives and runs, both spray loaders gate on game+perspective before processing, backfill script marked deprecated.

### Dispatch Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Per-story CR — E-223-01 | 3 | 3 | 0 |
| Per-story CR — E-223-02 | 0 | 0 | 0 |
| Per-story CR — E-223-03 | 0 | 0 | 0 |
| CR integration review | 0 | 0 | 0 |
| Codex code review R1 | 4 | 4 | 0 |
| Codex code review R2 | 2 | 1 | 1 |
| **Total** | **9** | **8** | **1** |

### Documentation Assessment
No documentation impact. No new features, endpoints, schema changes, CLI commands, or deployment changes. All changes are internal query fixes and loader optimizations adopting the existing E-220 perspective provenance invariant.

### Context-Layer Assessment
- **T1 (New convention/pattern)**: No. The perspective gate pattern already exists in TN-3 (plays loader) and `.claude/rules/perspective-provenance.md`. Spray loaders adopted the existing pattern.
- **T2 (Architectural decision)**: No. Fixes existing code to adopt the existing E-220 invariant. No new technology choices or structural decisions.
- **T3 (Footgun/failure mode)**: No. The cross-perspective dedup key behavior and spray gate partial-load limitation are characteristics of the existing perspective provenance model, already documented. No new gotchas discovered.
- **T4 (Agent behavior change)**: No.
- **T5 (Domain knowledge)**: No. All findings are E-220 invariant adoption, not new domain insights.
- **T6 (New CLI/workflow)**: No.

### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 — CR spec audit | 3 | 2 | 1 |
| Internal iteration 1 — Holistic team (SE+DE) | 6 | 1 | 5 |
| Internal iteration 2 — CR spec audit | 1 | 1 | 0 |
| Internal iteration 2 — Holistic team (SE+DE) | 2 | 2 | 0 |
| Internal iteration 3 — CR spec audit | 1 | 1 | 0 |
| Internal iteration 3 — Holistic team (SE+DE) | 0 | 0 | 0 |
| Codex iteration 1 | 3 | 2 | 1 |
| **Total** | **16** | **9** | **7** |
