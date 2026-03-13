# E-102-01: TeamRef Resolution Layer and CrawlConfig Changes

## Epic
[E-102: Pipeline INTEGER PK Migration](epic.md)

## Status
`TODO`

## Description
After this story is complete, a `TeamRef` dataclass will exist that separates internal DB identity (`id: int`) from external GC identifiers (`gc_uuid`, `public_id`). `CrawlConfig.TeamEntry` will gain an `internal_id: int` field populated from `teams.id`. `load_config_from_db()` will populate `internal_id` from the INTEGER PK. Crawlers and loaders will receive `TeamRef`-aware team entries, enabling subsequent stories to migrate SQL from TEXT to INTEGER FK references.

## Context
The E-100 schema rewrite changes `teams` from `team_id TEXT PK` to `id INTEGER PRIMARY KEY AUTOINCREMENT`. Pipeline code currently passes TEXT `team_id` values that serve as both DB keys and API identifiers. This story introduces the foundational resolution layer that subsequent stories (E-102-02, E-102-03) build on.

## Acceptance Criteria
- [ ] **AC-1**: `TeamRef` dataclass exists (location at agent's discretion, likely `src/gamechanger/config.py` or a new `src/gamechanger/types.py`) with fields: `id: int`, `gc_uuid: str`, `public_id: str | None`.
- [ ] **AC-2**: `CrawlConfig.TeamEntry` has an `internal_id: int | None` field (default `None` for backward compatibility with YAML path).
- [ ] **AC-3**: `load_config_from_db()` populates `TeamEntry.internal_id` from the `teams.id` column (the INTEGER PK).
- [ ] **AC-4**: `load_config()` (YAML path) still works — `internal_id` is `None` when loaded from YAML (requires a DB lookup step that may be added here or deferred to the caller).
- [ ] **AC-5**: A helper function exists to resolve a `TeamEntry` to a `TeamRef` by looking up the team in the DB by `gc_uuid` or `public_id` and returning the INTEGER `id`. This is the bridge for code that has a GC identifier and needs the internal ID.
- [ ] **AC-6**: All existing tests pass. New tests cover: TeamRef creation, TeamEntry.internal_id population from DB, resolution helper lookup.

## Technical Approach
Refer to the epic Technical Notes "TeamRef Pattern" and "CrawlConfig Changes" sections. The resolution helper needs a DB connection — consider whether it belongs in `config.py` or a separate module.

## Dependencies
- **Blocked by**: E-100 (INTEGER PK schema must exist)
- **Blocks**: E-102-02, E-102-03

## Files to Create or Modify
- `src/gamechanger/config.py` (modify — TeamEntry, load_config_from_db)
- `src/gamechanger/types.py` (CREATE — or wherever TeamRef lives)
- Test files for TeamRef and resolution (CREATE)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-102-02**: `TeamRef` dataclass and resolution helper. Crawlers/loaders can resolve TEXT GC identifiers to INTEGER DB IDs.
- **Produces for E-102-03**: `TeamRef` available for admin routes to look up teams by INTEGER ID.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
