# E-256-02: Delete the dead backfill-appearance-order command

## Epic
[E-256: Post-Descope Simplification & Foundations](epic.md)

## Status
`DONE`

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

## PM AC-Verification (2026-07-09)
**ALL THREE ACs PASS.** Verified against the worktree.

- **AC-1 PASS.** All three deletion targets absent (`src/gamechanger/loaders/backfill.py`, `scripts/backfill_appearance_order.py`, `tests/test_backfill_appearance_order.py`) — confirmed by an independent Glob, agreeing with SE's `ModuleNotFoundError`. SE additionally **pinned** the deletion in the removed-commands guard tuple, so a re-add fails a test instead of passing silently. That was not required by any AC and is the right instinct.
- **AC-2 PASS.** Suite 3830 → 3814 (−16), exactly the deleted test file's count; no orphaned imports.
- **AC-3 PASS.** PM ran an independent repo-wide grep (`backfill.appearance.order|backfill_appearance_order|loaders\.backfill|backfill CLI`). **Zero live `src/` references survive.** Remaining hits are exactly: the routed non-SE surfaces (docs/admin, CLAUDE.md, data-model.md, agent-memory, ROADMAP), this epic's own planning files, E-259's forward-looking conditionals, IDEA-115, and `.project/archive/**` + `.project/research/E-239-deletion-inventory.md` — **frozen historical records, correctly left untouched.** The two deliberate `tests/test_cli_data.py` mentions are the re-point docstring and the guard-tuple pin, both intended.

**Ruling — `src/reconciliation/engine.py` IS in scope.** AC-3's satisfaction condition is *grep-and-reconcile, not matching a frozen list*, and §15 states outright that a reference the grep finds but the seed omits is still in scope. The two comments at `:462,984` claimed pitcher order comes "from cached boxscore JSON"; PM verified `_extract_pitcher_order` reads the **`appearance_order` DB column** (`engine.py:1024-1027`, `SELECT player_id, appearance_order … ORDER BY appearance_order`), so the comments were a false provenance claim that E-204 orphaned. Left standing, they would have asserted a live cached-boxscore-JSON reader in the same commit that deleted the last one. SE traced before touching and changed no behavior (55 reconciliation tests green). This is the concept-sweep half of the doc-sweep discipline working as designed — **no token grep finds these**, and they are `src/`, which this story owns.

**Not an AC matter — `pitcher_order_json` (`:512`, `:1058`, and their bodies).** PM's view for CR: the parameter name asserts JSON provenance for data that is now DB-derived at **every** call site (`:225→:232`, `:463→:480`), so it is the same false-provenance class as the comments SE did fix, not merely "a name." It is a 3-site rename in one private module with zero behavior change. AC-3 does not compel it (the name contains no reference to the deleted command), so this story does not fail on it — but if CR asks for it, PM supports it, and if CR does not, it should be captured rather than forgotten.

## PM AC-Verification Round 2 (2026-07-09)
**AC-3 re-verified: PASS.** (AC-1 and AC-2 undisturbed — no deletions or test-count changes this round.)

- **Precedent chain corrected and PM-verified in-tree.** `backfill_game_dates.py:23-26` now mirrors `bb data reload-annotated-pitches` **(E-245)**, stating both epic IDs inline so the arrow's direction is checkable in-file; `plays_reload.py:270` is genericized to "the project's idempotent operator-maintenance convention" with no epic reference (correct — nothing surviving predates E-245). Chronology now runs **E-204 → E-245 → E-253**, forward. PM also checked the restored claim at `backfill_game_dates.py:48` ("commits its own UPDATEs, mirroring `reload_all_games`") against `plays_reload.py:273`, which does commit per game — the claim was verified, not transplanted.
- **Sixth token-invisible surface annotated, not struck.** `tests/test_gs_mixed_appearance_order.py:17-24` carries a HISTORICAL NOTE naming the original `backfill-appearance-order → canonical_recompute → verify-aggregates` chain, recording its deletion, and stating the two facts that make a mixed scope unreachable from ingestion (zero NULL rows live; the loader populates on every load) plus why the tests still stand. Correct disposition: the tests pin a live CASE-expression semantic, and the history stays true.
- **`pitcher_order_json` rename complete.** Zero occurrences survive in `src/`.

**Boundary CONFIRMED (PM read each, independently of SE and CR).** The `pre-backfill` / `fully-backfilled` mentions at `season_aggregates.py:275`, `test_scouting_loader.py:1463,1478`, and `test_gs_mixed_appearance_order.py:135,149` are **data-state descriptors** — each names the condition "every `appearance_order` is NULL," not a remedy pointing at a deleted command. `season_aggregates.py:275` reads "NULL when every game row's appearance_order is NULL, i.e. pre-backfill," which stays true regardless of what populated the column. Correctly left alone; rewriting them would be churn.

**Near-miss worth carrying to closure:** `_check_pitcher_signals` emits `signal_name="pitcher_order"` (`engine.py:650`) — a **string literal naming a persisted reconciliation signal**, one token away from the identifier being renamed. A `replace_all` on `pitcher_order` would have silently rewritten persisted signal data with a green suite. SE diffed against `git show HEAD:` to confirm the literal is byte-identical. PM re-confirmed: `:650` is the sole occurrence of the literal in `src/`. **The generalizable rule — a rename whose identifier also appears as a persisted string literal (signal name, column name, JSON key, status enum) must be done site-by-site, never `replace_all`** — is a code-reviewer/software-engineer memory candidate, flagged for the closure trigger-8 assessment.

## Notes
Per CA's Q1 routing rule, this story is single-owner (software-engineer, `src/` + tests only). The CLAUDE.md `backfill-appearance-order` prose removal was factored out to story 15 (claude-architect), which already owns CLAUDE.md and is blockedBy this story — so the deleted command is not left described in CLAUDE.md.
