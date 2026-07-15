# E-264-02: ERA basis correction — fetch, apply at the ERA sites, regenerate guards

## Epic
[E-264: League-Aware ERA Basis Fix](epic.md)

## Status
`TODO`

## Description
After this story is complete, the report pipeline will fetch each team's `innings_per_game` from GameChanger, store it, and compute ERA on that game-length basis (fallback 7) so our ERA reconciles with the GC app. The two ERA computation sites use the fetched basis; K/9 and WHIP are untouched. The golden and value-regression guards are regenerated to reflect the corrected numbers.

## Context
This is the correctness core of the epic: it makes our ERA match what a coach sees in the GameChanger app. The empirical basis, source endpoint, opponent-capability, and fallback are in epic Technical Notes TN-1; the storage/reader plumbing this story writes into and reads from is delivered by E-264-01 (TN-2/TN-3/TN-4). The fetch has an ordering constraint in the report pipeline (TN-6) — the value is only available after gc_uuid resolution, so it threads in via the post-resolution write path, not the initial ensure call. The scope is ERA-only (TN-9): K/9 stays on its 9-inning basis, WHIP stays per-inning.

## Acceptance Criteria
- [ ] **AC-1**: During report generation, when the team's `gc_uuid` is resolved, the pipeline fetches `settings.scorekeeping.bats.innings_per_game` from the authenticated `GET /teams/{gc_uuid}` (per Technical Notes TN-1) and writes it to `teams.innings_per_game` via `ensure_team_row` / the post-resolution backfill path (per Technical Notes TN-6). Given a report generated for a team whose basis GC exposes, when generation completes, then that team's `teams.innings_per_game` holds the fetched integer.
- [ ] **AC-2**: When the basis cannot be read (no resolvable `gc_uuid`, field absent, or fetch failure — including a RAISED 403 (`ForbiddenError`/`CredentialExpiredError`), which `GET /teams/{gc_uuid}` is known to return for some non-owned teams and which MUST be caught so it never crashes generation; the fetch is guarded independently of the spray-chart try/except, so per Technical Notes TN-6 it runs whether or not spray succeeds), generation continues (non-fatal, mirroring the spray-chart resilience posture) and `teams.innings_per_game` is left UNCHANGED (never fabricated) — NULL only if the team was never successfully fetched, otherwise the prior fetched value is KEPT (never clobbered to NULL, per Technical Notes TN-4). ERA is computed on the stored value when present, else the fallback 7. Given a never-fetched team, when a fetch fails, then the column stays NULL and ERA uses 7; given a team with a prior stored basis, when a re-fetch fails, then the stored value is retained and ERA uses it (not 7).
- [ ] **AC-3**: The two ERA sites in Technical Notes TN-5 compute `ER × (innings_per_game × 3) / ip_outs` with the compute-site fallback `basis = innings_per_game if innings_per_game is not None else 7` (explicit `is not None` — a bare `if not None` never falls back and crashes on the assumed path): `_compute_pitching_rates` (`src/reports/generator.py:453`, the displayed ERA string) and `_era_raw` (`src/reports/renderer.py:264`, the heat-map ranking input, changed in lockstep). Given a pitcher with known ER/ip_outs and a team basis of 7, when ERA is computed, then it equals `ER × 21 / ip_outs`; given a team basis of 6, then it equals `ER × 18 / ip_outs`; given a NULL basis, then it equals `ER × 21 / ip_outs` (fallback 7).
- [ ] **AC-4**: The K/9 sites (`generator.py:454`, `renderer.py:265`, `src/api/db.py:369`) and WHIP are UNCHANGED — no `27` at a K/9 site is altered, and WHIP still uses its per-inning basis (per Non-Goals / TN-5). Given the same fixture, when the report is generated, then K/9 and WHIP values are identical to before this epic.
- [ ] **AC-5**: The golden and value-regression guards are regenerated and green per Technical Notes TN-8: the golden is regenerated via `scripts/regen_report_golden.py` (the regenerated `tests/fixtures/golden/report_stats.json` appears in the diff), the fixture seeds BOTH provenance cases (a stored integer including a 6, AND a NULL team), and `tests/test_report_golden.py`, `tests/test_report_e2e.py`, `tests/test_db.py` (and any other ERA fixture assertions) pass. `python -m pytest tests/` is green.
- [ ] **AC-6**: The fixture (`tests/fixtures/seed.sql`) contains an EXPLICIT, documented team→basis mapping — a named team with stored basis 6, a named team with a stored known basis, and a named team with NULL — recorded in the fixture (a `seed.sql` comment or a shared fixture constant) so E-264-03 can assert its `ERA (6-inn)` / known / `ERA (7-inn)*` cases against identifiable teams without guesswork. Given the seeded fixture, when E-264-03 reads it, then each of the three provenance cases resolves to a specific named team/`public_id`.

## Technical Approach
Reuse the existing `gc_uuid` resolution seam the generator already uses for spray charts (`_resolve_gc_uuid` / `self.resolved_gc_uuid`, `src/reports/generator.py`); there is an in-repo precedent for the authenticated team-detail call with the correct version pin (`TEAM_DETAIL_ACCEPT` in `src/gamechanger/opponent_ladder.py:69`). Extract the integer from `settings.scorekeeping.bats.innings_per_game`, tolerate absence/failure (AC-2). Write it through `ensure_team_row(innings_per_game=...)` / `_backfill_innings_per_game` from E-264-01, respecting the ordering constraint in TN-6. Apply the basis at the two ERA sites in TN-5 with the compute-site fallback; leave the K/9 sites on `27`. Preserve the existing same-connection/commit ordering at this seam so the `innings_per_game` write is visible to the later `get_season_pitching` read within the same generation (the `season_year` write at the same seam already establishes this ordering) — do not introduce a fresh uncommitted connection for the fetch write. Then regenerate the golden and update the affected suites (TN-8). The `key_players.top_pitcher.era` card value derives from the same computed ERA, so it corrects automatically here (its basis label is E-264-03's concern).

## Dependencies
- **Blocked by**: E-264-01 (needs the column, the `ensure_team_row` param, and the reader-carried value)
- **Blocks**: E-264-03 (adds the basis-disclosure label on top of the corrected ERA; shares `src/reports/renderer.py`)

## Files to Create or Modify
- `src/reports/generator.py` (modify — fetch `innings_per_game` at the gc_uuid seam + thread to `ensure_team_row`; ERA site at `:453`)
- `src/reports/renderer.py` (modify — `_era_raw` site at `:264`)
- `tests/fixtures/seed.sql` (modify — seed both provenance cases per TN-8)
- `tests/fixtures/golden/report_stats.json` (regenerate via `scripts/regen_report_golden.py`)
- `tests/test_report_golden.py`, `tests/test_report_e2e.py`, `tests/test_db.py` (modify — updated ERA expectations). NOTE: `tests/test_db.py` is also touched by E-264-01 (reader coverage); the serial dependency (02 blocked-by 01) makes this safe — 02 builds on 01's `test_db.py` additions, does not replace them.

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-264-03**: the corrected ERA and a fixture with a DOCUMENTED team→basis mapping — a team with a stored 6-inn basis, a team with a known basis, and a NULL-basis (assumed) team — recorded in a `seed.sql` comment so E-264-03's label assertions reference specific teams unambiguously. Pinned as a hard requirement in AC-6.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
The golden test never self-writes; regeneration is the explicit `scripts/regen_report_golden.py` path and is code-reviewed (epic TN-8).
