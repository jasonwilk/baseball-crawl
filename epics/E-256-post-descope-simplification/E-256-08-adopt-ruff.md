# E-256-08: Adopt ruff (F-class)

## Epic
[E-256: Post-Descope Simplification & Foundations](epic.md)

## Status
`TODO`

## Description
After this story is complete, ruff is configured for the F-class (pyflakes) lint rules scoped to `src/` and `scripts/`, the 17 real F-class violations in `src/` are fixed, and the 6 false positives are resolved cleanly (via a `TYPE_CHECKING` block) rather than suppressed.

## Context
No lint tooling exists today. Technical Notes §12 has the counts: 17 F-class in `src/` (8 F401 unused-import, 5 F541 f-string-without-placeholders, 4 F841 unused-variable), 22 including `scripts/`. Repo-wide 96, of which 6 are false positives — F821 undefined-name in `tests/test_cli_creds.py`, all string return annotations paired with function-local imports, never evaluated at runtime; the clean fix is a `TYPE_CHECKING` block. **mypy is explicitly out of scope.** Two of the F841s are at `backfill.py:184-185`, which story 02 deletes — so they must already be gone when this story runs (hence the dependency).

## Acceptance Criteria
- [ ] **AC-1**: Given `pyproject.toml`, when this story is complete, then `[tool.ruff.lint]` selects `["F"]` only, scoped to `src/` and `scripts/`, with no mypy configuration added.
- [ ] **AC-2**: Given `ruff check src/ scripts/`, when this story is complete, then it reports **zero** violations.
- [ ] **AC-3**: Given the 6 F821 false positives in `tests/test_cli_creds.py`, when this story is complete, then they are resolved via a `TYPE_CHECKING` block (not a `# noqa`), so the string return annotations resolve without a runtime import.
- [ ] **AC-4**: Given `src/api/routes/auth.py:648` (`existing_creds` assigned never used — the one substantive F841 outside deleted code), when this story is complete, then it is resolved by dropping the unused binding while preserving any side effect of the right-hand call (verify the call is pure before deleting it outright).
- [ ] **AC-5**: Given the full suite, when this story is complete, then it is green.

## Technical Approach
Fix violations rather than blanket-ignore. For AC-4, check whether the `existing_creds` assignment's RHS has a side effect before removing — if it does, keep the call and drop the binding; if pure, remove the statement. The two `backfill.py` F841s are not this story's concern (story 02 deleted the file). Adopt ruff as a dev dependency via the `*.in` workflow if it is not already present.

## Dependencies
- **Blocked by**: E-256-01, E-256-02, E-256-03, E-256-04, E-256-05, E-256-07 — ruff must lint the **final** `src/`/`scripts/` tree, so it runs after every story that mutates those trees (01 deletes the disk flow, 02 deletes backfill, 03 the dead-code sweep, 04 restructures generator.py + creates `lifecycle.py`, 05 the rest-day edit, 07 the dep bump that also touches `requirements-dev`). Otherwise a later story adds an unused import after the baseline is set and CI (story 09) catches it instead.
- **Blocks**: E-256-09 (CI may run ruff as part of the static gate — coordinate with story 09)

## Files to Create or Modify
- `pyproject.toml` (`[tool.ruff.lint]`)
- The ~17 `src/` files carrying F-class violations (unused imports, empty f-strings, unused vars)
- `tests/test_cli_creds.py` (`TYPE_CHECKING` block)
- `src/api/routes/auth.py` (line ~648)
- `requirements-dev.in`/`.txt` if ruff is added as a dev dep

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-256-09**: a clean `ruff check` the CI static gate can optionally run.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
mypy is deliberately deferred (epic Non-Goals). ruff F-class only for this pass.
