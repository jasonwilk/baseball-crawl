# E-239-03: Trim the `bb data` CLI to the Surviving Commands (Sever Chain 2)

## Epic
[E-239: Decouple Pipeline Imports, Then Remove the Unused Surfaces](epic.md)

## Status
`TODO`

## Description
After this story is complete, `src/cli/data.py` contains only the surviving commands — `reconcile`, `dedup-players`, and `backfill-appearance-order` — plus their shared helpers. The member/opponent-flow commands (`sync`, `crawl`, `load`, `scout`, `resolve-opponents`, `dedup`, `repair-opponents`) and the module-level `from src.pipeline import bootstrap/crawl/load` imports (L22-24) are deleted together, severing coupling chain 2 so the pipeline modules become deletable without breaking the entire `bb` CLI.

## Context
This story severs chain 2 (Technical Notes §F). Because Typer imports command modules wholesale at CLI startup, the module-level pipeline imports in `data.py` would break the whole `bb` CLI (including the KEEP commands) once the pipeline is deleted — so the commands and their module-level imports must be removed together (SE artifact §3). Gate (a) from discovery resolved the surviving `bb data` surface to ONLY `reconcile`, `dedup-players`, `backfill-appearance-order`; the `--crawler`/`--loader` flags belong to the deleted `crawl`/`load` commands, and reports use the crawler/loader classes directly via `generator.py`, not the CLI. **`dedup` ≠ `dedup-players`**: delete `dedup` (tracked-team merge, `src/db/merge`), KEEP `dedup-players` (same-team player merge, `src/db/player_dedup`) — easy to conflate.

## Acceptance Criteria
- [ ] **AC-1**: The member/opponent-flow commands are removed from `src/cli/data.py`: `sync`, `crawl`, `load`, `scout`, `resolve-opponents`, `dedup`, `repair-opponents` — together with the module-level imports `bootstrap as bootstrap_module` / `crawl as crawl_module` / `load as load_module` (L22-24) and the `--crawler`/`--loader` flag plumbing.
- [ ] **AC-2**: The surviving commands remain and work unchanged: `bb data reconcile`, `bb data dedup-players`, `bb data backfill-appearance-order` (they lazy-import their deps; no module-level coupling). The scout/dedup-scoped private helpers (SE §3 list) are deleted with their commands AFTER verifying no KEEP command calls them; `_resolve_db_path` and the `_data_group` callback are preserved.
- [ ] **AC-3**: `src/cli/data.py` no longer imports `src.pipeline` at all; `import src.cli.data` does not import `src.pipeline` (assertable).
- [ ] **AC-4**: `bb --help` and `bb data --help` succeed and list only the surviving commands; a subprocess smoke test (`subprocess.run(["bb", "--help"])`) passes (`.claude/rules/testing.md`).
- [ ] **AC-5**: Tests handled per the discrimination rule (Technical Notes §F / SE §4): `test_cli_data.py` is adjusted (remove the deleted-command cases + pipeline imports; keep reconcile/dedup-players/backfill cases); tests exclusively exercising deleted commands are removed. Full suite green.

## Technical Approach
Delete the seven command functions, the L22-24 module-level imports, and the `--crawler`/`--loader` option plumbing together. Audit the private helpers per SE §3 (they are scout/dedup-scoped) and confirm no surviving command depends on them before deleting; keep `_resolve_db_path` and `_data_group`. Confirm `src.cli.data` has no remaining `src.pipeline` reference. Run the surviving-command tests and the `bb --help` subprocess smoke test. Adjust `test_cli_data.py`.

## Dependencies
- **Blocked by**: E-239-01 (chain 1 severed; ordering)
- **Blocks**: E-239-04, E-239-05, E-239-06

## Files to Create or Modify
- MODIFY `src/cli/data.py` (delete the seven commands + L22-24 imports + flags + scout/dedup helpers; keep `reconcile`/`dedup-players`/`backfill-appearance-order` + `_resolve_db_path`/`_data_group`)
- MODIFY `tests/test_cli_data.py` (remove deleted-command cases; keep surviving cases)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-239-04**: chain 2 severed — the pipeline modules have no CLI importer.
- **Produces for E-239-05**: the `scout`/`resolve-opponents`/`dedup` commands (importers of `opponent_resolver`, `gc_uuid_resolver`, `db.merge`) are gone, so those modules' CLI coupling is removed.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests adjusted and passing (incl. `bb --help` subprocess smoke test)
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
This story touches only `src/cli/data.py` + `tests/test_cli_data.py` — disjoint from E-239-02's files — but is sequenced after E-239-01 like the other caller-removal stories.
