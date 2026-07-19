# E-267-02: Game Grain at Load — Retire Removed + Redirect Rescheduled Games

## Epic
[E-267: Reconcile-at-Load Against the Fresh Crawl](epic.md)

## Status
`TODO`

## Description
After this story is complete, a re-scout that finds a prior-loaded game ABSENT from the fresh crawl either retires it (corroborated removed/voided) or redirects it (corroborated reschedule to a new date) — as part of the normal load, forward-only. This closes IDEA-140 (rescheduled game double-count) and CC-1 (removed game persists in W-L/season lines/recent form/freshness N).

## Context
`_find_duplicate_game` keys on `game_date` + unordered team pair, so a game moved to a new date does not match and is re-inserted (double-counted). A deleted game's rows persist as stale. Both corrupt the game-level reads (`_query_record`, recent form, runs-avg) and, via `player_game_*`, the query-time season aggregates. Uses the E-267-01 primitive + the canonical `merge_duplicate_game` seam.

## Acceptance Criteria
- [ ] **AC-1**: Given a prior-loaded game corroborated as REMOVED (fully absent from the fresh schedule, health-gate passed per TN-2, not a reschedule), when the re-scout loads, then its FULL child surface is hard-deleted atomically with the `games` row LAST (per Technical Notes TN-10 risk 4 — DRY against `game_merge._PERSPECTIVE_CHILD_TABLES` + `game_perspectives` + play_events-via-plays; no partial retire), and it no longer counts in `_query_record`/recent-form/runs-avg or the query-time season aggregates.
- [ ] **AC-2 (cross-perspective reschedule)**: Given a moved game that is a CROSS-perspective twin at a new date (corroborated per TN-3), when the re-scout loads it, then it is redirected/merged via the canonical `merge_duplicate_game` seam instead of double-inserted.
- [ ] **AC-3 (same-perspective reschedule — prefer id-matching, no delete)**: Given a SAME-perspective reschedule (the same team re-scouting the same opponent whose game moved date), when the re-scout loads it, then the game is matched on its STABLE `event_id` (the public `/games` `id`, which survives a GC reschedule PATCH-in-place per TN-11 Probe 2) and its `game_date` is UPDATED in place — NOT double-inserted and NOT deleted. The old-date-row-as-REMOVED hard-delete (per AC-1) is the FALLBACK, used only when id-matching cannot be relied on. Rationale: `merge_duplicate_game` refuses same-perspective and the current `_find_duplicate_game` date+team-pair key breaks on a date move; id-matching closes that gap with a lower false-delete surface.
- [ ] **AC-4**: Given a game present-but-not-final in the fresh schedule — `game_status` is NOT `"completed"`, i.e. the key is ABSENT (the common not-final shape), `null`, or `"new"` (a created-but-unscored 0-0 stub), per TN-11 Probe 1 — OR a grain-level health-gate failure (per TN-2), when the re-scout loads, then the game is NOT retired (bias-to-refuse) and one WARN is emitted. Membership uses `.get("game_status") == "completed"` (handles the absent key).
- [ ] **AC-5 (full-schedule threading — CRITICAL, api-scout evidence-validated)**: The game-grain set-difference MUST compare prior-loaded games against the FULL fresh schedule array (ALL `game_status` values), NOT the `completed_games` subset that the crawler filters at `src/gamechanger/crawlers/scouting.py:155`. Per TN-11 Probe 1 (633 live records): GC KEEPS not-final and long-past-unplayed games in the array, so if the reconcile diffs against `completed_games`, every legitimately-present not-final/unplayed game misclassifies as REMOVED → mass false-delete. A game is a removal candidate ONLY when it is absent from the FULL schedule array.
- [ ] **AC-6 (absent-from-full-array = genuine removal — Probe 1 resolved)**: Per TN-11 Probe 1, GC provably retains postponed/unplayed games in the schedule array (April/June unplayed games still present months later), so a game FULLY ABSENT from the full array IS a genuine removal/void, not a postponement. A removal candidate is therefore any prior-loaded game absent from the full array once the health-gate (TN-2) passes — no extra per-game suspicion clause is required (the earlier pending-capture guard is discharged). Standard bias-to-refuse still applies on a health-gate failure.
- [ ] **AC-7**: Regression test per TN-7: reproduces the cross-perspective reschedule double-count, the SAME-perspective reschedule double-count (AC-3 — asserts an id-matched in-place date UPDATE, no second row and no delete), and the removed-game persistence (stale W-L) — all failing pre-fix — and asserts correct single-count post-fix with the removed game's FULL child surface gone table-by-table (`game_merge._PERSPECTIVE_CHILD_TABLES` + `game_perspectives` + play_events-via-plays — guards a games-row-LAST partial-retire bug); plus bias-to-refuse cases, each asserting one WARN is emitted: (a) a not-final game (`game_status` absent / `null` / `"new"`) not retired (AC-4), (b) a not-final game that survives BECAUSE the full schedule was threaded (AC-5 — fails if the test harness feeds only `completed_games`), and (c) **[GAP-1 mass-delete safety — highest-value test]** a fresh SCHEDULE fetch that FAILS / returns EMPTY / shrinks below FLOOR_RATIO retires ZERO games — asserts the team's entire prior game set AND all child rows survive and one WARN per refusal (proves the grain wiring feeds the health signal, not just the 01 primitive).

## Technical Approach
Wire the E-267-01 `classify_absences` health-gate into the game-load path, feeding it the FULL fresh schedule array (AC-5) — thread the unfiltered `games_data` past the `scouting.py:155` `completed_games` filter into the reconcile so not-final games are visible as PRESENT, not absent. REMOVED (absent from the full array) → hard-delete the full child surface, games row last (TN-10 risk 4). Reschedule splits two ways (TN-3): cross-perspective → `merge_duplicate_game` (natural key, id-matching can't bridge perspectives); same-perspective → prefer stable-`event_id` match + in-place date UPDATE (no delete, per TN-11 Probe 2), delete-old fallback only if id-matching is unreliable. TRANSIENT (not-final per AC-4, or health-gate fail) → refuse. Do not re-inline FK-child re-pointing — route the merge through the canonical seam.

## Dependencies
- **Blocked by**: E-267-01
- **Blocks**: E-267-03 (shared load-path module)

## Files to Create or Modify
- The game-load path (`src/gamechanger/loaders/game_loader.py` and/or the E-267-01 module)
- `src/gamechanger/crawlers/scouting.py` (thread the FULL schedule array — not just `completed_games:155` — into the game-grain reconcile, per AC-5/TN-11)
- Test file under `tests/`

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
- [ ] E-257 reconciliation-scoreboard ratchet not regressed — verified at CLOSURE by the operator (not self-checked from the worktree — dev DB absent there), per TN-5

## Notes
Folds IDEA-140 (PROMOTED) + CC-1. Master record: `.project/research/2026-07-19-rerun-accumulate-only-audit.md`.
