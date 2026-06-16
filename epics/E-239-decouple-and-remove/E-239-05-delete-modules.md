# E-239-05: Delete Opponent-Discovery + Remaining Unreferenced Admin-Support Code

## Epic
[E-239: Decouple Pipeline Imports, Then Remove the Unused Surfaces](epic.md)

## Status
`TODO`

## Description
After this story is complete, the opponent-discovery vertical and the remaining dead admin-support code are gone: `crawlers/opponent_resolver.py`, `loaders/opponent_seeder.py`, `src/db/merge.py`, and the now-dead opponent helpers in `src/api/db.py` are deleted. The Epic-E-reserved `src/gamechanger/resolvers/gc_uuid_resolver.py` and (by default) `team_resolver.py` are explicitly preserved despite having zero importers after D2.

## Context
This is the final code-deletion story — it runs after the opponent-flow callers are gone (admin extraction in 01, `scout`/`resolve-opponents`/`dedup` CLI in 03, `trigger.py` in 04). The single highest-risk mistake is a naive "no importers → delete" sweep removing `gc_uuid_resolver.py`, which Epic E reuses for `progenitor_team_id` bridging and which has zero importers post-D2 — it MUST be preserved (a DIFFERENT file from the deleted `opponent_resolver.py`; easy to conflate). `opponent_resolver.py` carries the banned `resolve_unlinked()` follow→bridge→unfollow path — deleting it makes the in-code path moot; the doc ban survives in `gc-uuid-bridge.md` (L45-55), which is why E-239-06 can delete `quarantine.md`.

## Acceptance Criteria
- [ ] **AC-1**: The opponent-discovery + dead-admin-support deletion set in Technical Notes §D is removed: `src/gamechanger/crawlers/opponent_resolver.py`, `src/gamechanger/loaders/opponent_seeder.py`, `src/db/merge.py`, and the dead `api/db.py` opponent helpers (`finalize_opponent_resolution`, `get_opponent_links`, `get_opponent_link_by_id`, `save_manual_opponent_link`, `disconnect_opponent_link`, `get_unresolved_opponent_count`, `get_opponent_link_counts`, `get_duplicate_opponent_name`, `get_opponent_link_count_for_team`, `is_member_team_public_id`). After deletion, grep confirms zero surviving importer of each.
- [ ] **AC-1b** (reconciled against the repo 2026-06-16 per Codex C2): `get_teams_with_data` and `get_opponents_for_team` (listed in early planning) are CONFIRMED ALREADY ABSENT from `api/db.py` — grep-verify absence; no deletion action. The spray-bip query fns (`get_player_spray_bip_count` / `get_player_spray_bip_counts`) are handled in E-239-02 (dashboard-consumed/dead), NOT here. As the LAST `api/db.py` editor in the chain, this story runs the FINAL zero-importer grep-sweep across `api/db.py`: any query fn left with zero importer after all of D2's removals is deleted, after grep-confirming it is NOT reports/charts-shared.
- [ ] **AC-2 (LOUD — preserve)**: `src/gamechanger/resolvers/gc_uuid_resolver.py` is PRESERVED despite zero importers after D2 (Epic E reuses its `progenitor_team_id` bridging — Technical Notes §E), along with its test `tests/test_gc_uuid_resolver.py`. This is a DIFFERENT file from the deleted `crawlers/opponent_resolver.py`.
- [ ] **AC-3 (preserve / verify)**: `src/gamechanger/team_resolver.py` is preserved by default; it may be deleted ONLY if this story explicitly verifies Epic E does not need it AND it is entangled only with already-deleted code (Technical Notes §E / epic Open Questions). Any deletion is flagged for review; `test_team_resolver.py` follows its module.
- [ ] **AC-4**: The report-delete cascade is preserved and functional — `cascade_delete_team`/`cleanup_orphan_teams`/`_delete_team_scoped_data` (`generator.py`) and the admin `_delete_report`/`_delete_team_cascade` delegation are untouched (Technical Notes §E). No cascade rewrite is performed (the quarantined tables stay inert — Technical Notes §G).
- [ ] **AC-5**: No surviving module imports any deleted module — verified by grep across `src/`, `scripts/`, `tests/`. Epic A goldens + `bb report verify-aggregates` parity unchanged/green (Technical Notes §A).
- [ ] **AC-6**: Tests handled per the discrimination rule (Technical Notes §F / SE §4): `test_opponent_seeder.py`, `test_crawlers/test_opponent_resolver.py` are deleted; `test_dedup_integration.py` is read and either trimmed (if it asserts protected dedup behavior) or deleted (if resolver-only); `test_gc_uuid_resolver.py` is KEPT. **`tests/test_finalize_resolution.py` is DELETED entirely (Codex C4 / SE — it is the sole importer of the deleted `finalize_opponent_resolution`, 738 lines testing only it). The `TestGetOpponentLinkCountForTeam` class is removed from `tests/test_db.py` (≈:1066 — its helper is deleted in AC-1; re-grep live lines per §B).** (The other Story-05-deleted opponent helpers — e.g. `save_manual_opponent_link`, `get_duplicate_opponent_name` — are imported only by `test_admin_opponents.py`, which E-239-01 AC-6 already deletes, so no dangling test ref remains.) Full suite green (0 failed) — the closure-gate-blocking break Codex flagged is closed.

## Technical Approach
Delete the §D opponent-discovery modules + the dead `api/db.py` opponent helpers, then grep `src/`, `scripts/`, `tests/` to prove no surviving importer remains — treating `gc_uuid_resolver.py` (and `team_resolver.py` by default) as off-limits. For `team_resolver.py`, document the Epic-E need check before any deletion. Apply the test-discrimination rule. Do not edit any `.claude/` context-layer file — that is E-239-06. Re-grep live paths per Technical Notes §B.

## Dependencies
- **Blocked by**: E-239-01 (admin importers of `db.merge`/opponent helpers gone), E-239-02 (shared `src/api/db.py` AND `tests/test_db.py` edits — 02 removes the dashboard-side helpers/tests first; Codex C1), E-239-03 (scout/resolve-opponents/dedup CLI gone), E-239-04 (`trigger`/`opponent_seeder` importer gone)
- **Blocks**: E-239-06

## Files to Create or Modify
- DELETE `src/gamechanger/crawlers/opponent_resolver.py`
- DELETE `src/gamechanger/loaders/opponent_seeder.py`
- DELETE `src/db/merge.py`
- MODIFY `src/api/db.py` (delete the dead opponent helpers listed in AC-1)
- PRESERVE (do not touch): `src/gamechanger/resolvers/gc_uuid_resolver.py` + `tests/test_gc_uuid_resolver.py`; `src/gamechanger/team_resolver.py` (see AC-3)
- DELETE `tests/test_finalize_resolution.py` (imports the deleted `finalize_opponent_resolution`)
- MODIFY `tests/test_db.py` (delete/adjust the `get_opponent_link_count_for_team` block ≈:1062 — serialized after E-239-02's test_db.py edits via 05 blockedBy 02)
- DELETE / ADJUST tests per SE §4 (`test_opponent_seeder`, `test_crawlers/test_opponent_resolver`, `test_dedup_integration` — read before deciding)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-239-06**: the final surviving code surface — context-layer docs are rewritten against this state; `opponent_resolver.py` fully deleted confirms the `quarantine.md`-delete path.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests deleted/adjusted and passing; import graph grep-clean
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
The AC-2 preservation of `gc_uuid_resolver.py` is the single most important guard in this story — call it out in review (it is the naive-sweep trap).
