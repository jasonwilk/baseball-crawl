# E-250-03: Fixture compound-slug (Class-1) normalization + plays_parser docstring

## Epic
[E-250: Root-Level Cross-Season / Multi-Season De-Scope](../E-250-cross-season-descope/epic.md)

## Status
`TODO`

## Description
After this story is complete, no test fixture or source docstring seeds or describes a cross-season `season_id` shape: Class-1 compound-slug DB `season_id` literals are normalized to year-only, and the one `plays_parser` docstring that hardcodes a compound slug is corrected. Filesystem disk-slug literals (Class-3) and opaque isolation tokens (Class-2) are deliberately left intact. The single-season isolation/exclusion fixtures keep two distinct years (2025 and 2026) to keep proving exclusion. (The `season_type`-INSERT fixtures were already removed in E-250-02, atomically with the column drop — they are NOT this story's concern.)

## Context
Compound-slug fixtures (`2025-spring-hs`, etc.) are the last place a cross-season `season_id` shape is seeded. Left in place, a compound `season_id` feeding a year-only-deriving loader fails as a SILENT `FOREIGN KEY constraint failed` (E-241-06 lesson) — grep reconnaissance cannot catch it, only the full suite can. This story normalizes the Class-1 DB `season_id` literals (~5 files) while carefully preserving the Class-3 filesystem-slug contract, the Class-2 opaque isolation tokens, and the two-distinct-year exclusion fixtures.

## Acceptance Criteria
- [ ] **AC-1**: Every Class-1 literal (a DB `season_id` compound slug used as the partition key/FK) across the affected test files (~5) is normalized to year-only. Each literal is CLASSIFIED into one of the three classes per Technical Notes TN-6 before being changed.
- [ ] **AC-2**: Class-2 literals (opaque isolation tokens like `'s1'`, `'old-season'` used only to prove scoping/exclusion) and Class-3 literals (FILESYSTEM slug paths, e.g. `data/raw/2025-spring-hs/...`, the `src/gamechanger/loaders/plays_loader.py:32` disk-slug docstring) are LEFT UNCHANGED — neither is cross-season logic — per Technical Notes TN-6 and the Filesystem-vs-DB-Season_id-Decoupling rule in `.claude/rules/architecture-subsystems.md`.
- [ ] **AC-3**: The single-season isolation/exclusion fixtures retain TWO DISTINCT YEARS (2025 AND 2026) — only the suffix is dropped on Class-1 literals, never the second year (Technical Notes TN-6).
- [ ] **AC-4**: The one source docstring hardcoding a Class-1 compound `season_id` is corrected: `src/gamechanger/parsers/plays_parser.py:22` (`season_id="2026-spring-hs"` → `"2026"`). The `src/gamechanger/loaders/plays_loader.py:32` docstring is a Class-3 filesystem path and is NOT touched (CR F2).
- [ ] **AC-5**: The full test suite passes (`python -m pytest tests/` green) — the mandatory full-suite gate per Technical Notes TN-8. A green suite is the only proof that no seeded compound `season_id` produces a silent FK failure.

## Technical Approach
Enumerate every compound-slug and opaque-token `season_id` literal across the test tree first, then classify each before editing: Class-1 DB `season_id` slug → normalize to year-only; Class-2 opaque isolation token (`'s1'`/`'old-season'`) → keep; Class-3 filesystem slug → keep (TN-6). The classification is the load-bearing step — a blind find/replace would corrupt the filesystem-slug contract, the opaque isolation tokens, or the two-year exclusion fixtures. `season_type` is NOT in scope here (handled in E-250-02). Run the full suite as the gate, not grep.

## Dependencies
- **Blocked by**: E-250-02 (the `season_type` fixtures are removed there; any file that also carries a Class-1 compound slug is edited there first — same-file ordering)
- **Blocks**: None

## Files to Create or Modify
- ~5 test files under `tests/` carrying Class-1 compound-slug `season_id` literals (classify + normalize; exact set enumerated during implementation)
- `src/gamechanger/parsers/plays_parser.py` — docstring correction (:22, Class-1 compound slug → year-only)

## Agent Hint
data-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
The full-suite gate is non-negotiable here (E-241-06): a compound `season_id` fixture surfaces only as a silent FK failure under the year-only loader. Scope was narrowed after CR spec review: `season_type`-INSERT fixture removal moved to E-250-02 (atomic with the `NOT NULL` column drop, CR F1), and the `plays_loader.py:32` "docstring fix" was dropped as a contradiction (it is a Class-3 filesystem path to LEAVE, CR F2). `ensure_season_row`'s dead-compound-parse removal is also NOT in this story — it lives in E-250-02 (TN-4).
