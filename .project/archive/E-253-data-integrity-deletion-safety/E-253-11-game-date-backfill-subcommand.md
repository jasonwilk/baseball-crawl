# E-253-11: `game_date` Backfill Subcommand (3-tier re-derivation)

## Epic
[E-253: Data-Integrity & Deletion Safety](epic.md)

## Status
`DONE`

## Description
After this story is complete, an operator-maintenance `bb data` subcommand will re-derive the venue-local `game_date` for existing `games` rows from the recoverable UTC instant, correcting the historical UTC mis-derivation. It follows the 3-tier recoverability model: clean re-derivation where an instant + timezone survive, operating-tz fallback where only the instant survives, and a counted skip where no instant is recoverable. It mirrors the idempotent `bb data backfill-appearance-order` operator-maintenance precedent.

## Context
See epic Technical Notes **TN-5** (backfill design from SE's Q2 resolution). The `games` table stores `game_date` (mis-derived), `start_time` (ISO-8601 UTC, migration 014), and `timezone` (IANA, migration 014). For scouting-loaded games `start_time` equals the original derivation instant, so it is the recoverable absolute instant. E-253-04 fixes the derivation going forward and relocates `derive_local_date`; this story corrects existing rows.

Three tiers (TN-5):
1. `start_time` present + `timezone` present → clean re-derivation via `derive_local_date(start_time, timezone)`.
2. `start_time` present, `timezone` NULL → re-derive using the E-252-05 operating-tz default as fallback.
3. `start_time` NULL → no recoverable instant; leave `game_date` untouched, count and report the skip (do not fabricate).

## Acceptance Criteria
- [ ] **AC-1**: A `bb data` subcommand re-derives `game_date` for every `games` row where `start_time IS NOT NULL`, via `derive_local_date(start_time, <tz>)` where `<tz>` is the game's `timezone` when present else the E-252-05 operating-tz default, and UPDATEs only rows where the re-derived date DIFFERS from the stored value. It is idempotent and re-runnable (a second run is a no-op), mirroring `backfill-appearance-order`. The operating-tz-default fallback (tier 2) bridges the seam's `ZoneInfo` to the tz-name `derive_local_date` expects per epic TN-5 (ZoneInfo → tz-name), never passing the `ZoneInfo` object directly.
- [ ] **AC-2**: Rows with `start_time IS NULL` are left untouched and counted; the command reports the count of un-correctable (skipped) rows in its output. Proven by a test with a NULL-`start_time` fixture.
- [ ] **AC-3**: Tier-1 (timezone present) and tier-2 (timezone NULL → operating-tz fallback) both produce the correct venue-local / operating-local date respectively — proven by tests for each tier.
- [ ] **AC-4**: The backfill does NOT re-run player/game dedup — it only corrects stored `game_date` values. A corrected date that shifts 7-day-window membership is the intended correction, not a regression (documented, per TN-5).
- [ ] **AC-5**: Per the CLI error-exit convention (`.claude/rules/testing.md` error-path testing; the audit's own AC-5 exit convention), the command exits non-zero on failure and surfaces errors to the operator; a dry-run form previews changes without writing.

## Technical Approach
See epic Technical Notes **TN-5**. Reuse the relocated `derive_local_date` (from E-253-04) and the E-252-05 operating-tz seam. The implementing agent owns the subcommand shape (following the `bb data backfill-appearance-order` / `reload-annotated-pitches` precedent) and the dry-run/execute split.

## Dependencies
- **Blocked by**: E-253-04 (needs the corrected derivation + relocated `derive_local_date` helper); transitively **E-252** (the E-252-05 operating-tz seam, via E-253-04) — epics run serially with E-252 first
- **Blocks**: None

## Files to Create or Modify
- `src/cli/data.py` (new `bb data` backfill subcommand)
- Backfill implementation module under `src/` (implementer chooses; reuses `derive_local_date`)
- `tests/` — 3-tier re-derivation tests, NULL-`start_time` skip-count test, idempotency test, CLI exit-code test

## Agent Hint
software-engineer

## Handoff Context
- **Produces for the epic close**: an operator follow-up owed — run this backfill on the live DB post-dispatch (needs live-DB access, unavailable in the epic worktree). Record it in the epic completion summary.
- **Context-layer/docs at closure**: a new `bb data` subcommand is a CLI-surface addition — flag for the closure context-layer assessment (CLAUDE.md Commands section + `bb data` help) and documentation assessment.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Cross-reference: CLAUDE.md Commands (`bb data` maintenance-pass precedent — `backfill-appearance-order`, `reload-annotated-pitches`, `fix-self-games`), `.claude/rules/data-model.md` (Game time data ownership; 7-day rolling window).
