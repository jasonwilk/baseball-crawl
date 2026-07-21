# E-270-06: Correct the CLAUDE.md purge paragraph (partition-drift claim + E-270-02 behavior reconciliation)

## Epic
[E-270: Harden Reconcile-at-Load and Purge](../E-270-reconcile-purge-hardening/epic.md)

## Status
`TODO`

## Description
After this story is complete, the CLAUDE.md `bb db purge-scouting` paragraph will be truthful on TWO counts: (1) it will accurately describe the KEEP→PURGE FK protection — the current clause says a future KEEP→PURGE FK "silently breaks this command" and that "the partition drift test catches a new unclassified TABLE but not a new KEEP→PURGE FK," both halves of which understate the protection (a dedicated test AND a runtime FK assertion cover the FK case, and it aborts LOUDLY, not silently); and (2) it will describe the purge command's ACTUAL post-E-270-02 behavior (split `--force`/`--yes`, resolved-path + row-count display, typed confirmation on production, fail-closed auto-backup) instead of the pre-E-270 behavior it currently documents.

## Context
Two corrections to the CLAUDE.md purge paragraph. (1) Audit item 5(d): the CLAUDE.md line understates the purge command's protection. data-engineer verified the correction is accurate: `tests/test_purge_scouting.py:392-424` `test_keep_set_has_no_foreign_key_into_a_purged_table` derives FK edges at runtime from `PRAGMA foreign_key_list` over every KEEP table and asserts none point into `PURGE_TABLES` (with an anti-vacuity guard at :417), and `_assert_foreign_keys_on` (`src/db/purge_scouting.py:192-211`) would abort a real purge on such an FK via `IntegrityError`. The spec-review (CR M-1) further found the correction must span the WHOLE clause (the "silently breaks" first half is the same understatement), not just the drift-test half. (2) CR S-4: E-270-02 changes the command's behavior (flag split, typed confirm, auto-backup), so the paragraph's behavior description would ship stale and must be reconciled. This story touches CLAUDE.md — a context-layer path — so it routes to claude-architect. See epic Technical Notes TN-9.

## Acceptance Criteria
- [ ] **AC-1**: The correction spans the WHOLE clause per TN-9(1), not just the drift-test half. The corrected sentence states that a KEEP→PURGE FK aborts LOUDLY — caught at plan time by the dedicated `test_keep_set_has_no_foreign_key_into_a_purged_table` (with its anti-vacuity guard) AND at run time because FK enforcement is proven LIVE by `_assert_foreign_keys_on`, under which the purge's ordered DELETE aborts with `IntegrityError` — and MUST NOT retain the "silently breaks this command" wording. The sentence MUST NOT attribute an `IntegrityError` raise to `_assert_foreign_keys_on` itself (that function raises `RuntimeError`, and only when FK enforcement is OFF) — the `IntegrityError` comes from the ordered DELETE under proven-live enforcement (claude-architect precision fix, TN-9). It may still note the true nuance that the partition-DRIFT test itself only catches a new unclassified TABLE (the FK case has its own dedicated test).
- [ ] **AC-2**: Every factual claim the corrected sentence makes is verifiable against the two cited sources: (a) it names the plan-time test `test_keep_set_has_no_foreign_key_into_a_purged_table` and its stated behavior matches `tests/test_purge_scouting.py:392-424` (runtime FK-edge derivation via `PRAGMA foreign_key_list` over the KEEP set, asserting none cross into `PURGE_TABLES`, with the anti-vacuity guard); (b) its description of the runtime protection matches `src/db/purge_scouting.py:192-211` — FK enforcement is proven live before the deletes, so a KEEP→PURGE FK makes the purge's ordered DELETE abort with `IntegrityError` rather than silently orphan rows; and (c) it contains no claim the two sources contradict — in particular it does NOT attribute an `IntegrityError` raise to `_assert_foreign_keys_on` itself (that function raises `RuntimeError` when FK enforcement is OFF).
- [ ] **AC-3**: The rest of the purge paragraph NOT touched by AC-1/AC-4 (partition, single-transaction, HTML unlink, identity preservation) remains intact and consistent with the corrected sentences. "Intact" scopes to that untouched content ONLY — it MUST NOT re-preserve the "silently breaks" understatement AC-1 removes, and MUST NOT re-preserve the pre-E-270 behavior description AC-4 updates (CR M-1: the old AC-3 "remains intact" wording contradicted AC-1 by preserving the same clause AC-1 corrects).
- [ ] **AC-4**: The purge paragraph's BEHAVIOR description is reconciled to E-270-02's shipped surface per TN-9(2): the split `--force` (production-refusal override) / `--yes` (prompt skip) flags, the resolved-path + per-table row-count display before the prompt, the typed confirmation on production, and the fail-closed pre-purge auto-backup. The paragraph must not continue to describe the single overloaded `--force` or omit the typed-confirm / auto-backup behavior. Verify the described behavior against the MERGED code (`src/cli/db.py`, `src/db/purge_scouting.py`) as authoritative — NOT E-270-02's story prose, which can drift from what actually shipped (claude-architect refinement; this story is blocked by E-270-02).

## Technical Approach
Two corrections to the CLAUDE.md purge paragraph, per TN-9. For (1): read the two cited sources to confirm the claim (the test derives FK edges from `PRAGMA foreign_key_list` and asserts KEEP tables have no FK into `PURGE_TABLES`; `_assert_foreign_keys_on` refuses to purge unless FK enforcement is live), then rewrite the whole understating clause so it no longer says "silently breaks." For (2): read what E-270-02 actually shipped (its story + the merged `src/cli/db.py` / `src/db/purge_scouting.py`) and reconcile the paragraph's behavior description — flags, confirmation, backup — to match. Keep both corrections minimal and consistent with the paragraph's existing "standing obligation" framing about future KEEP→PURGE FKs.

## Dependencies
- **Blocked by**: E-270-02 (AC-4 reconciles the paragraph to the purge behavior E-270-02 ships; the doc must describe what actually shipped)
- **Blocks**: None

## Files to Create or Modify
- `CLAUDE.md` (modify — one sentence in the `bb db purge-scouting` paragraph)

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Context-layer story: `CLAUDE.md` is a context-layer path, so this routes to **claude-architect** at dispatch per the Routing Precedence rule (`.claude/rules/agent-routing.md`), regardless of the primarily-documentation nature of the change. It is the ONLY context-layer touch in this epic; all other stories are SE-domain. These are factual/behavior doc corrections, NOT a process/rule/skill change (those are Epic B). Blocked by E-270-02 so AC-4 describes the shipped purge behavior — handling the behavior reconciliation in-epic (rather than deferring the stale paragraph to the closure context-layer assessment) keeps CLAUDE.md truthful at epic close (CR S-4).
