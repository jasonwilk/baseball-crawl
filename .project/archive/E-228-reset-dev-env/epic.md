# E-228: Make `bb db reset` Produce a Useful Dev Environment

## Status
`COMPLETED`
<!-- Lifecycle: DRAFT → READY → ACTIVE → COMPLETED (or BLOCKED / ABANDONED) -->
<!-- PM sets READY explicitly after: expert consultation done, all stories have testable ACs, quality checklist passed. -->
<!-- Only READY and ACTIVE epics can be dispatched. -->

## Overview
Today `bb db reset` leaves a developer with a database full of fake demo teams and players, and an operator who -- despite being an admin -- sees a permanently dark dashboard because nothing grants dashboard access to their (tracked-only) teams. This epic makes a reset produce a clean, immediately-usable dev environment: an empty schema (no fake data) plus an admin-sees-all dashboard so the operator can log in and work with real data right away -- zero manual SQL or fix-up steps.

## Background & Context
`bb db reset` (`src/db/reset.py::reset_database`) currently performs three steps: delete the SQLite DB, run migrations, then load `data/seeds/seed_dev.sql`. Two problems make the result unusable as a starting point for real work:

**Problem 1 -- Useless sample data.** The seed file is 310 rows of fabricated demo data (LSB Varsity/JV/Freshman/Reserve, invented opponents like Northside Eagles, and made-up players/games/stats). The operator's words: *"I'd end up with a bunch of sample data that doesn't really do me any good."* The operator re-crawls real data with `bb data` after a reset, so the fake rows are pure noise. The user has decided the default reset should produce an **empty** database.

DE confirmed there is no reference data to preserve in the seed: the only legitimate bootstrap row -- `programs` = `'lsb-hs'` -- is inserted by migration 001 (`INSERT OR IGNORE`), not the seed. Season rows are created on demand by loaders. So a migrations-only database is schema-valid and app-functional. DE's recommendation: delete `seed_dev.sql` and the seed-loading step outright (no `--seed` flag, no replacement seed) -- "when in doubt, leave it out."

**Problem 2 -- Admin's dashboard is permanently dark after reset.** The operator's words: *"I would end up having to tell you to recreate my user."* The confirmed root cause (live runtime data refuted two earlier hypotheses -- the `role='user'` lockout and a stale container env): the operator IS an admin (via `ADMIN_EMAIL == DEV_USER_EMAIL` email match), the bypass user row exists, and admin-gated routes work. But the coaching **dashboard** hard-gates on `user_team_access` with no admin bypass -- an empty `permitted_teams` short-circuits to a "no assignments" page, and team-scoped requests 403 if the team is not permitted. Every provisioning path (`_assign_member_teams`, the admin assign-teams UI) grants ONLY `membership_type='member'` teams. The operator's real data is 27 tracked teams and 0 member teams (opponent scouting), so nothing ever populates `user_team_access`, the dashboard stays dark, and the only workaround today is a hand-written SQL insert into `user_team_access`. That manual SQL is the "recreate my user" friction.

**User decision: admin-sees-all, in dev AND production.** An admin's dashboard shows ALL teams without per-team grants; non-admin users remain gated by `user_team_access` (preserving the future multi-coach access model). The refuted reset-time-seeding and `role='admin'`-on-create ideas are dropped -- the operator is already admin, so role assignment is irrelevant. The fix is a single widening of permitted-teams resolution so admins resolve to all team ids (per Technical Notes TN-4).

Problem 1 (empty reset) is independent of Problem 2. The two problems map to two implementation concerns.

## Goals
- After `bb db reset`, the database contains the migrated schema plus the migration's `programs` bootstrap row, and **no** fake teams, games, players, or stats.
- After `bb db reset`, the operator (an admin) sees all teams on the coaching dashboard -- with no `user_team_access` grants and zero manual SQL -- and can start working with real data immediately. Admin-sees-all applies in dev and production.
- Non-admin dashboard gating is unchanged (still `user_team_access`-based), preserving the future multi-coach access model. The one narrow non-admin change is the removal of the dev-bypass empty-permitted backfill (option A; see Technical Notes TN-4).
- A single canonical admin predicate exists; the duplicated route-level copies delegate to it.
- The production safety guard remains intact: `DEV_USER_EMAIL` must never be active when `APP_ENV=production`.
- The dev seed file and its now-dead loading code are removed; the test suite is updated to assert the empty-reset outcome rather than the old seeded outcome.

## Non-Goals
- Rebuilding or reconfiguring the devcontainer. "Reset dev env" here means `bb db reset` only.
- Adding a `--seed` flag, a replacement seed file, or any demo-data mechanism. If demo data is ever needed again it can be re-added in a future epic.
- Changing migration 001 or the `programs` bootstrap row. The `programs` = `'lsb-hs'` row stays.
- Changing the production authentication flow (magic links, passkeys, session issuance) or the production guard's behavior. Note: the admin-sees-all widening (TN-4) intentionally applies on the production path too -- it changes which teams an already-authenticated admin can see, not how anyone authenticates.
- Backing up the operator's existing local data automatically. Reset is destructive by design (see Technical Notes TN-5); operators back up manually if they care about current local data.

## Success Criteria
- `bb db reset` on a fresh checkout produces a database where every table is empty except `_migrations` and `programs` (which holds exactly the one `lsb-hs` bootstrap row), per the checkable definition in Technical Notes TN-1.
- The reset CLI output accurately reflects an empty schema (no "N rows inserted" implying seeded data).
- `data/seeds/seed_dev.sql` and the dead seed-loading code (`load_seed`, `_SEED_FILE`, `scripts/seed_dev.py`) are removed.
- An admin user (via `ADMIN_EMAIL` match OR `users.role='admin'`) with zero `user_team_access` rows resolves to ALL team ids and the dashboard renders real team data instead of the no-assignments page; a non-admin user resolves to only their granted teams (no leak) or the no-assignments page when ungranted.
- The team-scoped 403 gate still fires for a non-admin requesting an unpermitted team and does not fire for an admin requesting any team.
- A single canonical admin predicate exists in `src/api/auth.py`; `dashboard.py` and `admin.py` route copies delegate to it.
- The production guard test(s) for the dev bypass remain green and unchanged in behavior.
- The full test suite passes with no regressions.

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-228-01 | Make `bb db reset` produce an empty schema (remove dev seed) | DONE | None | software-engineer |
| E-228-02 | Admin sees all teams (restore operator dashboard access after reset) | DONE | None | software-engineer |

## Dispatch Team
- software-engineer

<!-- Both stories are software-engineer-hinted. data-engineer was consulted during planning
     (empty-reset scope, test fallout) but owns no implementation story. -->
<!-- docs-writer is NOT on the dispatch team: doc updates (TN-8) are handled at closure via the
     documentation-assessment gate, not as implementation stories. -->
<!-- claude-architect may be required at closure if the context-layer assessment fires on the
     admin-sees-all access-model decision (TN-4) -- evaluated at closure, not dispatch. -->


## Technical Notes

### TN-1: "Empty" means schema + the `programs` bootstrap row
A reset DB is correct when migrations have been applied and the migration-inserted `programs` = `'lsb-hs'` row is present, and every user data table (teams, games, players, and all stat tables) has zero rows. The `programs` row is real org reference data inserted by migration 001 (`INSERT OR IGNORE`), not by the seed -- it stays. Season rows are not part of a bootstrap; loaders create them on demand. Do not edit migration 001 to remove the `programs` row.

DE confirmed an empty DB is fully functional at app startup: no startup path assumes a team, season, or game exists. The one season read (`src/gamechanger/config.py:195`, `SELECT season_id FROM seasons ORDER BY year DESC LIMIT 1`) returns `None` on an empty DB and is a crawl-time fallback -- loaders create seasons on demand. So "empty + `lsb-hs` programs row" serves correctly.

**Checkable definition of "empty" (for the inverse-assertion test):** the test MUST assert zero rows in every table the migrations create EXCEPT the migration-tracking table (`_migrations`) and `programs` (which holds the `lsb-hs` bootstrap row). To avoid silently missing a table, the assertion should enumerate tables dynamically from `sqlite_master` (all `type='table'` names minus `_migrations` and `programs`) and assert each has zero rows -- not hand-list a subset. The `programs` table MUST be asserted to contain exactly the one `lsb-hs` row.

### TN-2: Delete the seed, do not replace it
Per DE, there is nothing in `data/seeds/seed_dev.sql` worth preserving. The seed file, the `load_seed()` function and `_SEED_FILE` constant in `src/db/reset.py`, and the now-dead `scripts/seed_dev.py` are all removed. No `--seed` flag and no replacement seed are added. `scripts/reset_dev_db.py` is a thin wrapper that remains valid (it calls `reset_database`); leave it functioning.

### TN-3: Reset return shape and CLI output
`reset_database()` currently returns `(tables_created, rows_inserted)` and the CLI prints "N tables created. N rows inserted." With the seed gone there are no seeded rows. **Decided shape: keep the `(int, int)` tuple returning `(table_count, 0)`.** It preserves the 2-tuple, so the unpacking `tables, rows = reset_database(...)` in `src/cli/db.py` keeps working and most mocks need no shape change. Collapsing to a single int is explicitly OUT OF SCOPE -- it would break that unpacking and every mock in both test files. NOTE: this does NOT mean `tests/test_db_reset_guards.py` is untouched -- it patches the now-deleted `load_seed` and asserts a seeded `rows` value, so it still needs edits (see Technical Notes TN-7). The 2-tuple decision only avoids unpacking/arity churn, not the symbol-deletion fallout. The CLI output MUST NOT imply seeded data was loaded -- it should communicate an empty schema (e.g., "Database reset to empty schema. N tables created."). Keep the production guard sequencing in the CLI (`check_production_guard` before the confirmation prompt) unchanged.

### TN-4: Admin-sees-all -- widen permitted-teams resolution
**Confirmed root cause:** the coaching dashboard hard-gates on `user_team_access` with no admin bypass (empty `permitted_teams` short-circuits to the no-assignments page; team-scoped requests 403 if the team is not in `permitted_teams`). All provisioning grants only `member` teams, so an admin whose data is tracked-only never gets dashboard access. The earlier `role='user'` lockout and stale-env hypotheses are both refuted by live data -- do NOT implement reset-time user seeding or `role='admin'`-on-create.

**Fix location (single chokepoint):** widen `_get_permitted_teams` in `src/api/auth.py` (currently lines ~162-178). It is the one function called from both `_resolve_session_from_cookie` (production path: cookie / magic-link / passkey) and `_handle_dev_bypass` (dev path), and its result populates `request.state.permitted_teams`, which every dashboard route reads. One change therefore covers dev AND production and flows through every dashboard gate with no per-route widening. Shape: if the user is an admin, return all team ids (`SELECT id FROM teams`); otherwise unchanged (`SELECT team_id FROM user_team_access WHERE user_id = ?`).

**Admin predicate -- two entry points (resolves the connection mismatch):** the admin predicate (`ADMIN_EMAIL == email` OR `users.role == 'admin'`) is currently duplicated in `dashboard.py::_is_admin_user(user)` (~1172-1205) and `admin.py::_require_admin` (via `_get_user_role_by_id`). The middleware widening runs inside `_get_permitted_teams`, which already has an open connection, so it needs a connection-injected predicate. But the route-level callers (`dashboard.py::_is_admin_user` call sites at ~452 and ~1586 via `run_in_threadpool`; `admin.py::_require_admin`) hold NO open connection. A single connection-injected signature cannot serve both without forcing the routes to open a connection. Therefore provide BOTH entry points in `src/api/auth.py`:
- `_user_is_admin(conn, user)` -- connection-injected; the canonical core logic, used by the middleware widening (reuses the open connection, no extra connection).
- `user_is_admin(user)` -- a thin public wrapper that opens its own connection and delegates to `_user_is_admin`; used by the route modules.

The middleware widening MUST call `_user_is_admin` (the injected form) and MUST NOT import from a route module. Import-cycle check is clean: `auth.py` imports only `src.api.db`; route modules may import `auth` without a cycle.

**Predicate consolidation (included in scope):** make `dashboard.py::_is_admin_user` and `admin.py::_require_admin`'s admin check delegate to the canonical `auth.py` predicate (routes call the own-connection `user_is_admin` wrapper) so exactly one copy of this security-relevant check exists. This is a deliberate decision to avoid shipping a third copy of an auth predicate (drift risk); the dedup is small. SE-3 cleanup: when `dashboard.py::_is_admin_user` becomes a delegation, remove any now-unused `sqlite3`/`closing` imports it no longer needs (cosmetic, part of the same change).

**Remove ONLY the `_handle_dev_bypass` empty-permitted backfill (option A, SE-confirmed against the existing tests).** Under admin-sees-all, the backfill block in `_handle_dev_bypass` (auth.py ~248-253) -- which calls `_assign_member_teams` when `permitted_teams` is empty, with a comment naming the "bb db reset but .env preserved" scenario -- is obsolete: an admin's `permitted_teams` is never empty under the widening, and a non-admin dev-bypass user should not gain member teams via a later backfill request. **Remove this backfill block only.**

`_create_dev_user`'s call to `_assign_member_teams` (auth.py ~154) and the `_assign_member_teams` helper itself (auth.py ~120) **stay**. The helper retains a caller (`_create_dev_user`), so it is NOT dead code -- do not remove it.

**Why option A over removing both call sites (option B):** ground truth is that `tests/test_auth.py` has a `TestDevUserAutoAssignment` class (~line 582, from E-127-03) with 5 tests asserting non-admin dev-bypass member-team auto-assignment (using non-`ADMIN_EMAIL` emails). Removing both call sites (B) breaks 4 of those 5 tests and makes the epic's "non-admin behavior unchanged" claim false for non-admin dev-bypass users -- for a purely hypothetical non-admin-dev-bypass case. Option A breaks only the one test tied to the backfill being removed (`test_existing_dev_user_with_no_assignments_gets_backfilled`), keeps the other 4 green, and keeps "non-admin unchanged" honest. The operator outcome is identical either way (the operator is an admin, governed by admin-sees-all regardless), so A is the simpler-thing-that-works choice with the smaller blast radius.

**Tests:** assert that (a) an admin dev user with zero `user_team_access` rows resolves to all teams via the widened `_get_permitted_teams`; and (b) a non-admin dev-bypass user no longer gains member teams via a later empty-permitted backfill request (the removed path), while `_create_dev_user`'s initial assignment and all real-session grant paths are unchanged.

**Ordering constraint:** the admin check inside `_get_permitted_teams` must run before any emptiness-based logic, so an admin never falls into an empty-permitted branch.

**Non-admin behavior -- precise scope.** Non-admin DASHBOARD GATING is unchanged: non-admins still resolve to their `user_team_access` grants (or the no-assignments page when ungranted), preserving the future multi-coach access model. The ONE intentional non-admin change is narrow: the dev-bypass empty-permitted backfill is removed, so a non-admin dev-bypass user no longer gains member teams on a later backfill request. All other non-admin paths -- real-session grants and `_create_dev_user`'s initial member-team assignment -- are unchanged.

**Production guard untouched:** `SessionMiddleware.__init__` still raises if `DEV_USER_EMAIL` is set while `APP_ENV=production` (auth.py ~281-286). No migration is needed (no schema change). SE estimates ~15 lines in `auth.py` plus the route dedup.

**Test matrix (all 8 required; reflected in E-228-02's ACs AC-1 through AC-8):**
1. Admin via `ADMIN_EMAIL` match, 0 `user_team_access` → `permitted_teams` = ALL team ids; dashboard renders real data (not no-assignments). Fixture: 2+ teams, ≥1 with no access row.
2. Admin via `role='admin'` (`ADMIN_EMAIL` unset) → same all-teams result (covers both admin branches).
3. Non-admin with explicit grants → sees ONLY granted teams (no leak). Fixture: granted team A, ungranted team B → `permitted_teams` = `[A]`.
4. Non-admin with 0 grants → still gets the no-assignments page (`permitted_teams == []`).
5. Team-scoped 403 still fires for a NON-admin requesting an unpermitted `team_id`; does NOT fire for an admin requesting any team.
6. Production guard unchanged: `DEV_USER_EMAIL` + `APP_ENV=production` still raises at middleware init.
7. Multi-value fixture obligation: tests 1 and 3 MUST use 2+ teams so "all teams" vs "granted subset" are distinguishable (a single-team fixture would hide the bug).
8. Backfill removal (option A): an admin dev user with zero `user_team_access` rows resolves to all teams via the widened `_get_permitted_teams`; AND a non-admin dev-bypass user no longer gains member teams via a later empty-permitted backfill request (the removed block), while `_create_dev_user`'s initial assignment is unchanged. Pin the post-change non-admin dev-bypass behavior so it is asserted, not merely deleted.

**Test module:** the existing auth/dev-bypass test module is the expected baseline home for these tests; the implementing agent confirms the exact module(s) by grepping callers of `_get_permitted_teams` and `_handle_dev_bypass`.

### TN-5: Reset is destructive (operator-facing note)
`bb db reset` deletes the real local `data/app.db` (the operator's working DB may hold real crawled data). This is expected behavior for a reset command and is not changing. Operators who care about current local data should back up first (`bb db backup`). This is a documentation/communication concern, not a code change.

### TN-6: Runtime root-cause diagnosis (resolved)
The runtime failure mode is confirmed by live diagnostics run before planning, so no in-dispatch diagnostic is required. Confirmed environment facts: the live container HAS the bypass env (`DEV_USER_EMAIL == ADMIN_EMAIL`, `APP_ENV=development`), the operator user row exists and is admin via email match, and the operator's data is entirely tracked teams (27 tracked, 0 member). The failure is the dashboard's member-only `user_team_access` gate (TN-4), not a role default or a stale environment. No standalone verification story is needed; E-228-02's AC matrix (TN-4) verifies the fix directly.

### TN-7: Test fallout (the main work surface for E-228-01)
Deleting `load_seed`, `_SEED_FILE`, and the seed-error handling breaks more than the row-existence tests -- some references are imports and `patch()` targets that fail at collection/patch time, not just assertions. PM verified each line below by direct inspection. The implementing agent must address ALL of these:

- `tests/test_seed.py` (~438 lines):
  - **Module-level import (line ~25):** `from src.db.reset import (..., load_seed, ...)`. After deletion this fails at COLLECTION time, taking down the whole module. Remove `load_seed` from the import.
  - **`_SEED_FILE` constant (line ~38):** the test defines/imports its own `_SEED_FILE` reference. Remove it.
  - **`class TestSeedFile` (lines ~426-438, 3 tests):** asserts the seed file exists / is non-empty / contains INSERTs. DELETE the entire class (the seed file is gone).
  - DELETE the row-existence tests that assert seed rows exist. KEEP the migrations-applied, core-tables-exist, WAL-mode, migrations-table, `get_db_path`, production-guard, AND `test_overwrites_existing_database` (reset idempotency -- not a seed-row test) tests. ADD the inverse assertion per Technical Notes TN-1 (every table empty except `_migrations` and `programs`; `programs` holds exactly the one `lsb-hs` row).
- `tests/test_cli_db.py`:
  - `test_reset_prints_summary_on_success`: hard assertions `assert "5" in output` / `assert "42" in output` (~lines 90-91) and a `(3, 10)` mock (~line 96). Update the mocked return tuples to `(table_count, 0)` AND drop the row-count output assertions ("42"/"10") -- not just reword the success string.
  - **`test_reset_file_not_found_exits_1` (line ~151):** mocks `reset_database` raising `FileNotFoundError` ("missing seed file") and asserts exit 1. MF-2/TN-9 removes that handler and `reset_database` no longer raises `FileNotFoundError` for a missing seed -- DELETE or repurpose this test so it no longer asserts seed-file-not-found behavior.
- `tests/test_db_reset_guards.py`:
  - **`test_ac7_skip_guard_true_bypasses_internal_guard` (~line 223):** patches `src.db.reset.load_seed` and asserts `rows == 10`. The earlier "zero changes" claim (from DE-2) was WRONG -- it only checked tuple READS and missed this PATCH target. `patch()` of a deleted symbol fails. Remove the `load_seed` patch line and change `assert rows == 10` → `assert rows == 0`; keep the guard-bypass core assertion. The other ~6 `(5, 42)` mocks patch `src.cli.db.reset_database` (not `load_seed`) and need no change.

### TN-8: Documentation impact (flag for closure doc-assessment gate)
Docs that go stale under this epic -- flag for the closure documentation-assessment gate (docs-writer updates them at closure; implementing agents should NOT edit docs):

**Stale from seed deletion (E-228-01):**
- `docs/admin/getting-started.md` (~lines 91-111): a "Seed the Development Database" section that instructs running `scripts/seed_dev.py` and `scripts/reset_dev_db.py` and says the dashboard will show "sample data."
- `docs/agent-browsability-workflow.md` (~lines 46-49 and 154-158): references `scripts/seed_dev.py` as a setup/troubleshooting step.

**Stale from admin-sees-all (E-228-02):**
- `docs/admin/post-reset-guide.md`: the member-team auto-assignment model described throughout "Step 4: Verify Dev User Access" and its troubleshooting block (~lines 117-126, the `--source db` note ~line 139, and the "Dev user still not seeing teams" block ~lines 161-163) becomes stale/wrong under admin-sees-all. The operator no longer needs member-team assignment to see the dashboard -- as an admin they see all teams. docs-writer revises this guide to reflect admin-sees-all (and the empty-reset starting state).

DE's grep confirmed there are NO `seed_dev`/`load_seed` **symbol** references in CI config or code beyond the 3 test files and 2 scripts already enumerated in TN-2/TN-7. The doc references above are prose mentions of those workflows, not symbol references -- consistent with DE's finding, and the only remaining cleanup surface.

### TN-9: Dead seed-error handling and stale docstring (E-228-01)
Removing the seed step leaves stale code artifacts in three files that the story must clean up:
- `src/cli/db.py` (~lines 88-90): the `except FileNotFoundError` block that prints "Seed file error: ..." becomes dead -- `reset_database()` no longer reads a seed file and no longer raises `FileNotFoundError` for a missing seed. Remove this handler. (If the implementing agent finds the surrounding `try` no longer needs to catch anything, simplify accordingly.)
- `src/db/reset.py` (`reset_database()` docstring, ~lines 161/178/182): the docstring still says the function does "delete, migrate, seed", documents the old `(tables_created, rows_inserted)` return semantics, and lists `Raises: FileNotFoundError: If the seed file is missing.` All three are stale. Update the summary to "delete, migrate" (no seed), reconcile the return documentation with the `(table_count, 0)` shape per TN-3, and drop the `FileNotFoundError` `Raises` entry.
- `scripts/reset_dev_db.py` (the thin wrapper kept in service per TN-2): same stale messaging as `cli/db.py` -- module docstring "load seed data" (line ~2) and the argparse description (line ~56), the `except FileNotFoundError → "Seed file error"` handler (lines ~86-88), and the "N rows inserted" print (line ~93). Clean all of these parallel to the `cli/db.py` cleanup: drop seed references from the docstring/description, remove the dead `FileNotFoundError` handler, and reword the final print to reflect an empty schema.

## Open Questions
- None. DE scoped the empty-reset definition and test fallout (E-228-01). SE's live runtime diagnostics confirmed the Problem 2 root cause (member-only dashboard gate), designed the admin-sees-all fix and its 8-test matrix (TN-4), and -- after the Codex review surfaced the existing `TestDevUserAutoAssignment` tests -- confirmed option A (remove ONLY the dev-bypass empty-permitted backfill). The user decided admin-sees-all for dev and production.

## History
- 2026-05-30: Created.
- 2026-05-30: Problem 2 root cause confirmed by live runtime data -- the dashboard's member-only `user_team_access` gate, not a role default or stale env (two earlier hypotheses refuted). User decided admin-sees-all (dev + production). E-228-02 rewritten from "operator auto-admin" to "admin sees all teams" (single widening of `_get_permitted_teams` + canonical admin predicate consolidation). TN-4/TN-6/TN-8 and Goals/Success Criteria updated accordingly. Story file renamed to `E-228-02-admin-sees-all.md`.
- 2026-05-30: MF-1 finalized as option B (SE-confirmed): remove the member-only auto-grant from BOTH dev-bypass paths (`_handle_dev_bypass` backfill AND `_create_dev_user`'s `_assign_member_teams` call) and delete the now-uncalled `_assign_member_teams` helper as dead code. TN-4, AC-8, matrix test 8, E-228-02 Files/Notes, and Open Questions updated.
- 2026-05-30: Internal review iteration 1 incorporated. ACCEPTED: MF-1 (remove dead dev-bypass member-team backfill + test; ordering constraint) → TN-4 + AC-8; MF-2 (dead seed-error handler + stale `reset_database` docstring) → new TN-9 + E-228-01 AC-5; MF-3/SE-2 (two-entry-point admin predicate for no-connection route callers) → TN-4 + AC-7; SF-1 (widen-before-empty ordering) folded into AC-8; SF-2 (enumerate empty tables) → TN-1; SF-3 (explicit no-change outcome for guards test) → TN-3/TN-7; SF-5 (name auth test module) → TN-4/E-228-02; DE-1 (specific test_cli_db.py lines + drop row-count asserts) → TN-7; DE-2 (zero changes to test_db_reset_guards; keep idempotency test) → TN-3/TN-7; SE-3 (clean unused dashboard imports) → TN-4/E-228-02. DISMISSED: SF-4 (CR self-confirmed clean), SE-1 (duplicate story file -- already removed pre-review). One item flagged to SE for confirmation (backfill remove-vs-scope; see Open Questions).
- 2026-05-30: Codex spec review iteration 1 incorporated; all 4 findings ACCEPTED. **REVERSAL B→A:** Codex P2 surfaced that `tests/test_auth.py::TestDevUserAutoAssignment` (E-127-03, 5 tests) asserts non-admin dev-bypass member-team auto-assignment; DE+SE verified option B breaks 4 of them and falsifies "non-admin unchanged." Switched to **option A** (remove ONLY the `_handle_dev_bypass` backfill; `_create_dev_user` + `_assign_member_teams` stay, not dead code). Operator outcome identical; smaller blast radius; keeps "non-admin unchanged" honest. Reverted the option-B incorporations in TN-4/AC-8/matrix-test-8/Goals/Description/Notes/Open Questions. Codex P1 (test fallout): rewrote TN-7 with DE's corrected ground truth -- collection-time import removal (`load_seed`/`_SEED_FILE` in test_seed.py ~25/38), delete `TestSeedFile` (~426-438), delete `test_reset_file_not_found_exits_1` (test_cli_db.py ~151), fix `test_ac7_skip_guard_true_bypasses_internal_guard` patch+assert (test_db_reset_guards.py ~223); corrected the stale "zero changes" claim in TN-3; broadened E-228-01 AC-5/AC-6/Files. Codex P2 (reset_dev_db.py): stale messaging cleanup added to TN-9 + E-228-01 AC-5/Files. Codex P2 (file enumeration): E-228-02 Files now names SE's verified test list (test_auth.py, test_dashboard_auth.py, test_admin_routes.py as EDIT; 4 dashboard/db tests as RUN-for-regression) with a behavioral grep backstop replacing the symbol grep.
- 2026-05-30: Set to READY. Codex iteration 2 declined by the user (iteration 1 was clean after incorporation). Review scorecard:

### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 -- CR spec audit | 8 | 7 | 1 |
| Internal iteration 1 -- Holistic team (DE+SE) | 5 | 4 | 1 |
| Codex iteration 1 | 4 | 4 | 0 |
| **Total** | **17** | **15** | **2** |

CR (8): accepted MF-1, MF-2, MF-3, SF-1, SF-2, SF-3, SF-5; dismissed SF-4 (self-confirmed clean). Holistic (5): accepted DE-1, DE-2, SE-2, SE-3; dismissed SE-1 (duplicate story file -- already removed pre-review). Codex (4): accepted all (1 P1 + 3 P2), including the consequential B→A reversal. Note: SE-2 is the same finding as CR's MF-3 (no-connection route callers); counted once under each pass per the scorecard structure, incorporated once.

- 2026-05-30: COMPLETED. Both stories DONE; full dispatch review chain clean. **Accomplished:** (1) E-228-01 -- `bb db reset` now produces an EMPTY schema (migrated tables + the migration-001 `programs`=`lsb-hs` bootstrap row, nothing else). Removed `data/seeds/seed_dev.sql`, `load_seed()`/`_SEED_FILE` in `src/db/reset.py`, and `scripts/seed_dev.py`; cleaned dead seed-error handling and stale "rows inserted" messaging across `src/cli/db.py`, `src/db/reset.py`, and `scripts/reset_dev_db.py`; updated the three test files (TN-7) including the collection-time import fallout and `patch()` targets, and added the TN-1 dynamic-enumeration empty-schema inverse assertion. (2) E-228-02 -- admin-sees-all dashboard: an admin (via `ADMIN_EMAIL` match OR `users.role='admin'`) now resolves to ALL team ids with zero `user_team_access` grants and zero manual SQL, restoring the operator's dashboard immediately after reset. **Root cause (confirmed by live runtime data, two earlier hypotheses refuted):** the coaching dashboard hard-gated on `user_team_access` with no admin bypass, while every provisioning path granted only `member` teams -- the operator's 27 tracked / 0 member teams left the dashboard permanently dark. **Fix:** single widening of `_get_permitted_teams` at the shared chokepoint (covers dev + production), plus a two-entry-point canonical admin predicate (`_user_is_admin(conn,user)` injected + `user_is_admin(user)` own-connection wrapper) that `dashboard.py` and `admin.py` now delegate to (one copy of the security check). **Option A** backfill removal: removed ONLY the `_handle_dev_bypass` empty-permitted backfill; `_create_dev_user`'s `_assign_member_teams` call and the helper itself stay (not dead code), keeping "non-admin unchanged" honest. Non-admin dashboard gating and the `DEV_USER_EMAIL`/`APP_ENV=production` guard are unchanged.

### Review Scorecard (dispatch phase)
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Per-story CR -- E-228-01 | 2 | 2 | 0 |
| Per-story CR -- E-228-02 | 2 | 0 | 2 |
| CR integration review | 0 | 0 | 0 |
| Codex code review | 2 | 2 | 0 |
| **Total** | **6** | **4** | **2** |

E-228-01 CR (2): 0 MUST FIX, 2 SHOULD FIX = stale-doc fallout, accepted -> handled by the closure documentation-assessment gate. E-228-02 CR (2): 0 MUST FIX, 2 SHOULD FIX = pre-existing test-infra defects (coverage-indicator + `_make_client` fixture bug), dismissed as out-of-scope/pre-existing (independently confirmed pre-existing by CR). CR integration review: clean, no findings. Codex (2): 2 missing-test findings, both accepted and remediated by SE. (This dispatch-phase scorecard is separate from the planning-phase spec-review scorecard above.)

### Closure Assessments
- **Documentation assessment: FIRES.** Per TN-8, docs-writer dispatched to update `docs/admin/getting-started.md` (the "Seed the Development Database" section, now obsolete), `docs/agent-browsability-workflow.md` (`scripts/seed_dev.py` setup/troubleshooting references), and `docs/admin/post-reset-guide.md` (the member-team auto-assignment model in "Step 4: Verify Dev User Access" and its troubleshooting, now superseded by admin-sees-all + empty-reset starting state) before archival.
- **Context-layer assessment (6 triggers, explicit verdicts):**
  - #1 New convention/pattern: **YES** -- admin-sees-all access model + canonical admin-predicate delegation (route copies delegate to one `auth.py` predicate).
  - #2 Architectural decision with ongoing implications: **YES** -- admins bypass `user_team_access` (in dev AND production); non-admins remain gated, preserving the future multi-coach model.
  - #3 Footgun / boundary: **YES** -- the member-only-grant dark-dashboard trap for tracked-only admins; the empty-reset starting state (reset no longer seeds demo data).
  - #4 Agent behavior / routing: **NO.**
  - #5 Domain knowledge for future epics: **NO.**
  - #6 New CLI / workflow / operational procedure: **YES** -- `bb db reset` now yields an empty DB; post-reset operator onboarding changed (admin sees all teams immediately, no member-team assignment step).
  - Verdict: context-layer gate **FIRES** -> claude-architect dispatched to codify before archival.
