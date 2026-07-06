# E-253-05: Cross-Perspective Game-Dedup Partial UNIQUE Backstop (010)

## Epic
[E-253: Data-Integrity & Deletion Safety](epic.md)

## Status
`DONE`

## Description
After this story is complete, a DB-level partial UNIQUE index will backstop the cross-perspective game-dedup logic against the SELECT-then-INSERT race window, WITHOUT rejecting legitimate doubleheaders. The backstop applies only to games carrying the stable `game_stream_id`.

## Context
See epic Technical Notes **TN-6**. Cross-perspective game dedup is SELECT-then-INSERT via `_find_duplicate_game` (`game_loader.py:1100`) on a natural key (`game_date` + unordered team pair); under the cross-process boundary (admin-UI + CLI + cron on one SQLite file) there is a narrow duplicate-game window with no DB backstop. This is a LOW-severity finding. The HAZARD (TN-6): a naive `UNIQUE(game_date, team_lo, team_hi)` would reject the legitimate second game of a doubleheader; `game_stream_id` is not always present for tracked/public opponent games, and `event_id` is perspective-specific.

## Acceptance Criteria
- [ ] **AC-1**: Migration 010 adds a **partial UNIQUE INDEX gated on `game_stream_id IS NOT NULL`** (per TN-6) that prevents a second `games` row for the same real game (same stable `game_stream_id`) from being inserted under the cross-process race. The migration is idempotent per `.claude/rules/migrations.md`.
- [ ] **AC-2**: Given a legitimate doubleheader (two distinct games, same date, same team pair), when both are loaded, then BOTH `games` rows persist — the backstop does NOT reject the second game. Proven by a test.
- [ ] **AC-3**: Given a tracked/public-opponent game with `game_stream_id IS NULL`, when loaded, then the partial index does not apply and existing behavior is unchanged (the SELECT-then-INSERT dedup path still governs it).
- [ ] **AC-4**: The existing `_find_duplicate_game` SELECT-then-INSERT collapse continues to work as the primary dedup path; the index is a backstop, not a replacement — no regression in cross-perspective collapse behavior.
- [ ] **AC-5**: The migration number is confirmed by globbing `migrations/` at implementation time (expected `010`, after 009 from E-253-02).

## Technical Approach
See epic Technical Notes **TN-6**. Do NOT ship a bare unordered-pair UNIQUE — it rejects doubleheaders. The partial index gated on `game_stream_id IS NOT NULL` is the required form. The implementing agent owns the exact index definition.

## Dependencies
- **Blocked by**: E-253-03 (migration-runner atomicity — new migration runs under the fixed runner); E-253-02 (migration numbering: 009 before 010)
- **Blocks**: None

## Files to Create or Modify
- `migrations/010_game_dedup_backstop.sql` (new)
- `tests/` — doubleheader-not-rejected test + duplicate-same-game-rejected test + NULL-`game_stream_id` passthrough test

## Agent Hint
data-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Cross-reference: `.claude/rules/data-model.md` (Game-ordering convention — doubleheaders; Prevention over cleanup — `_find_duplicate_game` natural key), CLAUDE.md "Prevention over cleanup".
