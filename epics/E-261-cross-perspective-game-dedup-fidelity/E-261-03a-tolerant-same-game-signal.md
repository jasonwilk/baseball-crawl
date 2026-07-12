# E-261-03a: Tolerant cross-perspective same-game signal + uniform candidate-loop guard

## Epic
[E-261: Cross-Perspective Game-Dedup Fidelity](./epic.md)

## Status
`TODO`

## Description
After this story, `_find_duplicate_game()` recognizes two perspectives of the same real game even when their scorekeepers disagree on the score (Defect B), using the **schedule-count** discriminator rather than score-tolerance. The signal is applied UNIFORMLY across the whole candidate loop (not only the cross-perspective sub-branch), so a healed DB does not re-accumulate duplicates on regeneration. Score ownership on a cross-perspective redirect is made deterministic (canonical scores win). This story is the same-game DECISION half of the fix; the in-pipeline twin merge that acts on it is E-261-03b.

## Context
Defect B (epic Background): the cross-perspective branch's exact `(home_score, away_score)` match misses one-run disagreements (observed 12-4 vs 12-5, confirmed same game by identical 18-batter lineup). The resolved signal policy, plumbing constraints, and the SE-5b test reconciliation are in epic TN-4; score ownership is in epic TN-1. The offline form of the predicate this story factors is reused by E-261-04.

## Acceptance Criteria
- [ ] **AC-1**: Given the TN-2 Defect B seeded state (cross-perspective candidate row scoring the game 12-4), when the own perspective loads the same game scoring it 12-5 AND the incoming run's summaries show exactly ONE game vs this pair on this date, then `_find_duplicate_game` returns the canonical id (redirect fires per the TN-4 schedule-count signal) and the load records the redirect in `redirect_map` (E-244 contract preserved for plays/spray stages).
- [ ] **AC-2**: Given a genuine doubleheader — two same-date same-pair games present in the incoming perspective's own summaries (incoming_count == 2) — when they load, then TWO `games` rows result (existing doubleheader tests still pass, plus a new cross-perspective doubleheader test where the DB already holds both opponent-perspective rows). The signal never collapses a doubleheader.
- [ ] **AC-3**: Uniform candidate-loop guard (finding B): given a canonical row that already carries BOTH perspectives in `game_perspectives` (the post-merge state, seeded directly), when a same-perspective reload of the source event runs, then the schedule-count guard catches it and NO new duplicate `games` row is inserted. The guard is applied perspective-agnostically across the whole `_find_duplicate_game` candidate loop, not only the cross-perspective sub-branch.
- [ ] **AC-4**: When the tolerant signal fires on disagreeing scores, a WARNING log records both scorelines and both game ids (operator-visible data-quality trace). Score ownership follows epic TN-1: the cross-perspective redirect does NOT overwrite the canonical row's existing scores (first-loaded perspective wins), while a SAME-perspective reload still updates scores (correction path preserved) — verified by a test in each direction.
- [ ] **AC-5**: SE-5b reconciliation: the existing test `test_cross_perspective_no_dedup_when_scores_disagree` (`tests/test_loaders/test_game_dedup.py:598`) remains valid and passes — because the tolerant signal is schedule-count and DEFAULTS OFF with no count context, an 11-1 vs 10-1 pair with no schedule-count supplied still does NOT dedup. This story explicitly owns preserving that outcome and documents (test comment) why it coexists with AC-1.
- [ ] **AC-6**: Fail-safe on missing context (finding E): when the opponent identity / schedule-count cannot be resolved for the incoming game (e.g. None opponent name), the tolerant signal DECLINES — the loader falls back to exact-score match and never merges on missing context.
- [ ] **AC-7**: The reusable OFFLINE same-game predicate is factored into `src/db/game_merge.py` with a stable, documented, importable signature — verifiable WITHIN this story (a unit test constructs it directly and asserts its decisions). Its inputs are **disjoint cross-perspective (PRIMARY) + bounded score-tolerance corroboration + near/matching play-count corroboration**, and it EXCLUDES the live-only schedule-count gate. The actual import/reuse by the offline repair pass is verified in E-261-04, NOT here (epic finding-J resolution; Codex P2-3 scoping). The play-count corroboration is a REQUIRED input, not optional — the predicate must not merge on disjoint-perspective + score-tolerance alone (Codex P1-2: the merge deletes a `games` row, so the safeguard is pinned into the predicate, not left advisory).

## Technical Approach
Per epic TN-4 (RESOLVED). Compute a per-(game_date, unordered team-pair) count in `ScoutingLoader` — which holds the full `games_index` (`scouting_loader.py`) — and pass it to `GameLoader` (at construction or per-call). `GameLoader.load_payload` receives ONE summary at a time and does NOT see all summaries (api-scout / Codex P2-4), so the count MUST be precomputed upstream, not derived inside `GameLoader`. Treat a 1-incoming-vs-1-candidate cross-perspective pair as the same game regardless of score mismatch; keep exact-score match as the fast path. Honor the TN-4 plumbing constraints: resolve the count (naturally keyed by date + opponent name, where `games_index` lives) into the (date, team-id-pair) space the dedup decision uses; derive the count's `game_date` with the SAME logic `_load_boxscore_data` uses (a shared `derive_local_date` seam) so a key-miss cannot silently disable the signal; and DECLINE on unresolved opponent identity. Score-tolerance is corroboration only, never a standalone trigger. Score ownership on the cross-perspective redirect path is gated per TN-1 (do NOT apply a blanket score COALESCE in `_upsert_game`). Factor the offline predicate into `src/db/game_merge.py` per finding J. Extend the TN-2 fixtures. The in-pipeline twin-merge invocation at the redirect site is E-261-03b's job — this story stops short of merging an already-persisted twin.

## Dependencies
- **Blocked by**: E-261-01 (same file `game_loader.py` — serial), E-261-02 (offline predicate lands in `game_merge.py`)
- **Blocks**: E-261-03b (same file `game_loader.py` — serial; consumes the same-game decision + redirect site), E-261-04 (offline predicate reuse)

## Files to Create or Modify
- `src/gamechanger/loaders/game_loader.py` (modify — `_find_duplicate_game` cross-perspective + uniform guard, score ownership on redirect)
- `src/db/game_merge.py` (modify — add the reusable offline same-game predicate)
- `src/gamechanger/loaders/scouting_loader.py` (modify — only if summary-count plumbing requires it)
- `tests/test_loaders/test_game_dedup.py` (modify — tolerant-signal, uniform-guard, doubleheader-guard, score-ownership, SE-5b reconciliation tests)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-261-03b**: the tolerant same-game decision at the redirect site (canonical id resolution) plus the score-ownership scoping, which 03b extends by merging an already-persisted source-event twin before the upsert.
- **Produces for E-261-04**: the OFFLINE same-game predicate in `src/db/game_merge.py` (schedule-count-free form) with its documented signature.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
The signal-gating question is RESOLVED (epic Resolved Decisions): schedule-count PRIMARY, score-tolerance corroboration-only, defaults OFF without count context. Preserve the E-244 `redirect_map` contract exactly: fetch stays keyed by SOURCE event id; only DB-facing keys become canonical.
