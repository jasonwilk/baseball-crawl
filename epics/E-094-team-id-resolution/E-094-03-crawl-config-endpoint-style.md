# E-094-03: Add Endpoint Style to Crawl Config

## Epic
[E-094: Fix Team ID Resolution in Import and Crawl Pipeline](epic.md)

## Status
`TODO`

## Description
After this story is complete, `TeamEntry` in `config.py` will carry an `is_owned` flag loaded from the database, allowing the crawl orchestrator and individual crawlers to distinguish owned teams (use authenticated UUID-based endpoints) from non-owned teams (use public slug-based endpoints). The `load_config_from_db()` function will populate this field from the `teams.is_owned` column.

## Context
Currently `TeamEntry` has only `id`, `name`, and `level`. The `load_config_from_db()` function filters to `is_active = 1 AND is_owned = 1`, so only owned teams are loaded. However, after E-094-02 fixes the ID storage, `team_id` will be a UUID for owned teams and a public_id for non-owned teams. The config layer needs to express this distinction so that:
1. Crawlers can choose authenticated endpoints (UUID-based) for owned teams.
2. Future public-endpoint crawlers can use public_id-based endpoints for non-owned teams.
3. The crawl orchestrator can load non-owned teams when ready (by relaxing the `is_owned = 1` filter).

This story only adds the `is_owned` field and populates it from the DB. It does not change crawler behavior or load non-owned teams -- those are future work.

## Acceptance Criteria
- [ ] **AC-1**: `TeamEntry` dataclass has an `is_owned` boolean field (default `True` for backward compatibility with YAML config).
- [ ] **AC-2**: `load_config_from_db()` populates `is_owned` from the `teams.is_owned` column for each team entry.
- [ ] **AC-3**: `load_config()` (YAML path) sets `is_owned=True` on all entries (YAML config is for owned teams only).
- [ ] **AC-4**: The `load_config_from_db()` query still filters to `is_active = 1 AND is_owned = 1` (no change to which teams are loaded -- this story only adds the field).
- [ ] **AC-5**: Existing tests in `tests/test_config.py` pass. New tests verify `is_owned` is populated correctly from both YAML and DB paths.
- [ ] **AC-6**: The `TeamEntry` docstring is updated to document the `is_owned` field and its relationship to endpoint selection.

## Technical Approach
This is a small change to two functions in `src/gamechanger/config.py`. The `TeamEntry` dataclass at line 47 gets a new field. The `load_config_from_db()` function at line 122 adds `is_owned` to its SELECT and passes it to the `TeamEntry` constructor. The `load_config()` function at line 74 already hardcodes all entries as owned teams from YAML.

Key reference file: `/workspaces/baseball-crawl/src/gamechanger/config.py`

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/gamechanger/config.py` -- add `is_owned` to `TeamEntry`, update `load_config_from_db()` and `load_config()`
- `tests/test_config.py` -- add tests for `is_owned` field population

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The `public_id` field is not added to `TeamEntry` in this story. Crawlers currently use `team.id` for API paths. Once owned teams have UUID as `team_id`, the crawlers will get the correct value from `team.id` without additional changes. When public-endpoint crawlers are built later, `public_id` can be added to `TeamEntry` at that time.
