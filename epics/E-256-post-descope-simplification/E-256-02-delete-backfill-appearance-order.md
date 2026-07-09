# E-256-02: Delete the dead backfill-appearance-order command

## Epic
[E-256: Post-Descope Simplification & Foundations](epic.md)

## Status
`TODO`

## Description
After this story is complete, `bb data backfill-appearance-order` and its supporting module, script, tests, and CLAUDE.md prose are gone. The command is dead three ways over: zero NULL `appearance_order` rows exist in the live DB (DE confirmed via `SELECT COUNT(*) FROM player_game_pitching WHERE appearance_order IS NULL` = 0), no writer can produce a new NULL row (`game_loader.py:1065` + the UPSERT at `:1533`), and its path builder resolves `data/raw/<season_id>/` = `data/raw/2026/`, which does not exist because the on-disk trees use the retired suffixed-season taxonomy (`data/raw/2026-spring-hs/`).

## Context
DE ran the live-DB count that discharges the E-253 owed operator follow-up (which chained `backfill-appearance-order → canonical_recompute → verify-aggregates`): the count is 0, so no backfill is owed. The command reads a disk cache nothing writes and is a silent no-op on any fresh machine. Its path resolving to the non-existent `data/raw/2026/` is one more leaf of the retired suffixed-season taxonomy — deleting it removes one leaf; the root (the on-disk suffixed trees) is a standing user ask tracked separately and is **out of scope** (Non-Goals). See CLAUDE.md `bb data` prose and its footgun note.

## Acceptance Criteria
- [ ] **AC-1**: Given the CLI, when this story is complete, then `bb data backfill-appearance-order` no longer exists (the command, its `src` module, and `scripts/` wrapper if any are removed) and `bb data --help` does not list it.
- [ ] **AC-2**: Given the tests, when the command is removed, then its dedicated tests are deleted and the full suite is green (no orphaned import of the deleted module).
- [ ] **AC-3**: Given the deleted command, when this story is complete, then this story runs an **authoritative repo-wide grep** for the command identifier (`backfill.appearance.order` across `src/`, `scripts/`, `tests/`, `docs/`, `.claude/`, `CLAUDE.md`, and `docs/ROADMAP.md`) and (a) reconciles every LIVE reference it OWNS — the `src/` and `tests/` surfaces: the `src/cli/__init__.py` command-list docstring, the `bb data backfill-appearance-order` precedent docstrings in `src/db/backfill_game_dates.py` and `src/gamechanger/loaders/plays_reload.py` (re-point each to a surviving precedent), and `tests/test_cli_data.py`'s command-list references; and (b) records the full grep surface list in its completion report and hands the non-SE surfaces to their routed owners (epic Technical Notes §15: `docs/admin/`→story 10, context-layer rules/CLAUDE.md→story 15, agent-memory→owning agent, `docs/ROADMAP.md`→PM). The satisfaction condition is **grep-and-reconcile, not matching a frozen list** — the §15 surfaces are a seed, not a ceiling (a hand-listed eviction set has proven incomplete repeatedly this planning cycle; IDEA-115).

## Technical Approach
Delete the command function, its module, and its tests. This is a **pure `src/`-and-tests SE story** — it does NOT edit CLAUDE.md, docs, or context-layer files. Per CA's routing rule (Q1), the CLAUDE.md `backfill-appearance-order` prose removal is **owned entirely by story 15** (CA's context-layer eviction pass, which already owns CLAUDE.md and is blockedBy this story), NOT a cross-domain AC here. The two ruff F841 violations at `backfill.py:184-185` (Technical Notes §12) disappear with the file, so they are not the ruff story's concern.

This story additionally owns the **authoritative repo-wide grep** (AC-3) that seeds the epic's whole backfill eviction: it reconciles its own `src/`/`tests/` surfaces and routes the rest by ownership (epic Technical Notes §15). This grep-and-reconcile framing replaces the old two-surface hand-list, which Codex round 2 proved incomplete (2 → 5 → 11 surfaces); the durable fix is grep-not-list (IDEA-115).

## Dependencies
- **Blocked by**: None
- **Blocks**: E-256-08 (ruff — the F841s at backfill.py:184-185 vanish with this deletion), E-256-10 (`operations.md` backfill eviction, AC-6), E-256-15 (eviction sweep)

## Files to Create or Modify
- The `backfill-appearance-order` command module (locate under `src/cli/data.py` + its implementation module, e.g. `src/.../backfill.py`)
- `scripts/` wrapper if one exists
- The command's test file(s)
- `src/cli/__init__.py` (command-list docstring, AC-3)
- `src/db/backfill_game_dates.py`, `src/gamechanger/loaders/plays_reload.py` (precedent docstrings citing the deleted command, AC-3 — re-point to a surviving precedent)
- `tests/test_cli_data.py` (command-list references, AC-3)
- (NOT `CLAUDE.md`, `docs/`, or `.claude/` prose — those surfaces route to stories 15/10 and PM per §15, per Q1 routing.)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-256-08**: confirmation that `backfill.py:184-185` (two F841s) are deleted, so ruff need not address them.
- **Produces for E-256-15**: the deleted command name for story 15's eviction sweep across `data-model.md` AND `CLAUDE.md` (story 15 owns both prose edits).
- **Produces for E-256-10**: the deleted command name + the authoritative grep surface list, for story 10's `operations.md` backfill eviction (AC-6).
- **Produces for PM (closure)**: the `docs/ROADMAP.md` backfill surfaces (:219, :376) plus the agent-memory topic-file hits (code-reviewer, data-engineer), routed per §15 — PM reconciles `docs/ROADMAP.md` and its own memory at closure and flags the code-reviewer / data-engineer memory hits (owning agents not on E-256's team) for a follow-up sweep.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests updated (dead tests removed) and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Per CA's Q1 routing rule, this story is single-owner (software-engineer, `src/` + tests only). The CLAUDE.md `backfill-appearance-order` prose removal was factored out to story 15 (claude-architect), which already owns CLAUDE.md and is blockedBy this story — so the deleted command is not left described in CLAUDE.md.
