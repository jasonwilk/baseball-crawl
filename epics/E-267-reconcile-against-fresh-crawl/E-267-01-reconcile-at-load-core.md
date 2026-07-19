# E-267-01: Reconcile-at-Load Core — Set-Difference + Removed-vs-Transient Corroboration (bias-to-refuse)

## Epic
[E-267: Reconcile-at-Load Against the Fresh Crawl](epic.md)

## Status
`TODO`

## Description
After this story is complete, the load pipeline has a shared reconcile-at-load primitive that, given a prior-loaded set and the fresh crawl for a team+season, computes the set-difference (what is loaded but absent from the fresh crawl) and classifies each absence as genuinely-removed (retire) or transient/postponed/not-yet-final (refuse, keep live data). This is the foundation the three grains (game, player-line, roster) build on. This story delivers the primitive and its corroboration decision WITHOUT applying any grain-specific retire yet.

## Context
The pipeline is accumulate-only; the fix is prevention-at-load going forward (per Technical Notes TN-1 — reconcile-at-load, not a `bb data` pass). The load-bearing risk is deleting live data on a transient absence, so the corroboration decision (bias-to-refuse, mirroring `is_offline_same_game`) is the core deliverable. Grains 02/03/04 consume this primitive.

## Acceptance Criteria
- [ ] **AC-1**: Given `prior_ids`, `fresh_ids`, and a `crawl_authoritative` health signal for a grain, when `classify_absences(prior_ids, fresh_ids, *, crawl_authoritative)` runs, then it returns per id a classification of PRESENT / REMOVED / TRANSIENT_ABSENT per Technical Notes TN-2. NO stored snapshot table — the DB is the prior set and the fresh crawl is the authority.
- [ ] **AC-2**: Given the fresh crawl for a grain that (a) failed to fetch, (b) returned an empty payload, OR (c) shrank below the floor (`fresh_count < prior_count * FLOOR_RATIO`, FLOOR_RATIO = 0.5), when `classify_absences` runs, then it CLASSIFIES ALL absences in that grain as TRANSIENT_ABSENT (never REMOVED) — bias-to-refuse — per TN-2. The classifier only returns the classification; the WARN-per-refusal is emitted by the grain retire helpers (02/03/04), NOT here (per AC-4). FLOOR_RATIO is the UNIVERSAL minimum; the classifier accepts a stricter per-grain guard (the roster grain supplies one per TN-12 — the flat floor is too loose for a 12-15 roster), so a grain may refuse on a smaller shrink than the universal floor.
- [ ] **AC-3**: The module DEFINES the retire convention as HARD-DELETE (per TN-4 — no soft-retire marker, no new column/migration) and the classification permits retire ONLY for the REMOVED value. This story performs NO grain DELETE and emits NO WARN (neither per-retire nor per-refusal) — both the DELETE and the WARN-per-refusal are delivered by the grain stories 02/03/04, which consume this primitive; story 01 is closable on the pure classifier + its unit tests alone.
- [ ] **AC-4**: `classify_absences` itself is a PURE function over id sets (no DB handle, no I/O) — it takes `prior_ids`/`fresh_ids`/`crawl_authoritative` and returns the classification. The connection-in / no-commit / caller-owns-the-transaction contract belongs to the grain RETIRE helpers (defined/consumed by 02/03/04, mirroring the `merge_duplicate_game`/`is_offline_same_game` seam conventions), NOT to the classifier. The module documents this split so the two contracts don't conflict.
- [ ] **AC-5**: The primitive's contract documents the grain-specific delete-scoping key (per DE risk 1, TN-10): the PLAYER-LINE grain scopes by `perspective_team_id` (`player_game_*` carry it; collision hazard real), the ROSTER grain scopes by the natural key `(team_id, season_id)` (`team_rosters` has NO `perspective_team_id`). Exercised by grain stories 03/04.
- [ ] **AC-6**: Regression test per TN-7: unit tests proving (a) PRESENT vs REMOVED vs TRANSIENT_ABSENT classification on seeded inputs (a present id classifies PRESENT, a genuinely-absent id under a healthy crawl classifies REMOVED); (b) each of the three bias-to-refuse triggers (fetch-fail, empty payload, sub-floor shrink) classifies ALL absences TRANSIENT_ABSENT — MUST fail if the primitive would retire any of them.

## Technical Approach
Build `classify_absences` (health-gate corroboration, no history diff) as a PURE function over id sets in the db/loader layer, mirroring `is_offline_same_game`'s bias-to-refuse shape. The retire form is hard-delete (TN-4). Do not wire any grain-specific retire here — grains 02/03/04 consume the classification and own their DELETEs (each connection-in/no-commit, perspective-scoped and health-gated). Per-grain corroboration guards (game not-final/scoreless = transient; scored-but-empty boxscore never retires; roster empty-guard) are applied in the grain stories using this primitive's health inputs.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-267-02, E-267-03, E-267-04

## Files to Create or Modify
- A new shared reconcile-at-load module under `src/db/` or `src/gamechanger/loaders/` (implementer's decision)
- Corresponding test file under `tests/`

## Agent Hint
data-engineer

## Handoff Context
- **Produces for E-267-02/03/04**: the `classify_absences` primitive (PRESENT/REMOVED/TRANSIENT_ABSENT, health-gated, no snapshot table) each grain calls; retire form = hard-delete (TN-4), perspective-scoped per TN-10 risk 1.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing (incl. the bias-to-refuse test)
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
- [ ] E-257 reconciliation-scoreboard ratchet not regressed — verified at CLOSURE by the operator (not self-checked from the worktree — dev DB absent there), per TN-5

## Notes
Master record: `.project/research/2026-07-19-rerun-accumulate-only-audit.md`. This is prevention-at-load, forward-only — no retroactive repair.
