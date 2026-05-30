# E-228-02: Admin Sees All Teams (Restore Operator Dashboard Access After Reset)

## Epic
[E-228: Make `bb db reset` Produce a Useful Dev Environment](epic.md)

## Status
`TODO`

## Description
After this story is complete, any admin user will see every team on the coaching dashboard without needing per-team `user_team_access` grants. This restores the operator's dashboard access immediately after `bb db reset` -- with zero manual SQL -- because the operator is an admin and their real data is entirely tracked teams (which no provisioning path grants today). Non-admin dashboard gating is unchanged -- non-admins remain gated by `user_team_access`, preserving the future multi-coach access model. The one narrow non-admin change: the dev-bypass empty-permitted backfill is removed, so a non-admin dev-bypass user no longer gains member teams on a later backfill request (option A; see Technical Notes TN-4). The change applies in both dev and production.

## Context
The "recreate my user" friction the operator described is not a role-assignment problem (the operator is already admin via `ADMIN_EMAIL == DEV_USER_EMAIL` email match) and not a stale-env problem -- both earlier hypotheses were refuted by live runtime data. The confirmed root cause: the coaching dashboard hard-gates on `user_team_access` with no admin bypass (empty permitted_teams short-circuits to a "no assignments" page; team-scoped requests 403 if the team is not permitted). Every provisioning path (`_assign_member_teams`, the admin assign-teams UI) grants only `membership_type='member'` teams. The operator's real data is 27 tracked teams and 0 member teams, so nothing ever populates `user_team_access`, the dashboard stays permanently dark, and the only workaround today is hand-written SQL. The user decided the fix is **admin-sees-all** in dev and production (per Technical Notes TN-4). This story implements that as a single widening of permitted-teams resolution.

## Acceptance Criteria
- [ ] **AC-1**: Given an admin user (admin via `ADMIN_EMAIL` match) with zero `user_team_access` rows and a database containing 2+ teams (at least one with no access row), when the dashboard loads, then `permitted_teams` resolves to ALL team ids and the dashboard renders real team data (not the no-assignments page), per Technical Notes TN-4.
- [ ] **AC-2**: Given an admin user via `users.role='admin'` (with `ADMIN_EMAIL` unset), when the dashboard loads, then `permitted_teams` resolves to ALL team ids -- exercising both admin branches of the canonical predicate, per Technical Notes TN-4.
- [ ] **AC-3**: Given a non-admin user with explicit grants to team A but not team B (database has both), when permitted-teams resolution runs, then the user's `permitted_teams` is exactly `[A]` -- no leak of ungranted teams, per Technical Notes TN-4.
- [ ] **AC-4**: Given a non-admin user with zero grants, when the dashboard loads, then they still receive the no-assignments page (`permitted_teams == []`), preserving current non-admin behavior.
- [ ] **AC-5**: Given the team-scoped 403 gate, when a NON-admin requests an unpermitted `team_id`, then the 403 still fires; when an ADMIN requests any `team_id`, then no 403 fires, per Technical Notes TN-4.
- [ ] **AC-6**: Given the production safety guard, when `DEV_USER_EMAIL` is set and `APP_ENV=production`, then `SessionMiddleware.__init__` still raises (guard unchanged) and the existing production-guard test(s) remain green with unchanged behavior.
- [ ] **AC-7**: Given the admin predicate, when this story is complete, then `src/api/auth.py` provides both a connection-injected `_user_is_admin(conn, user)` (used by the middleware widening) and a thin own-connection `user_is_admin(user)` wrapper (used by routes), the route-level copies (`dashboard.py::_is_admin_user`, `admin.py::_require_admin` path) delegate to the canonical predicate so no duplicated admin-predicate logic remains, and the middleware widening does not import from any route module, per Technical Notes TN-4.
- [ ] **AC-8**: Given the `_handle_dev_bypass` empty-permitted backfill is removed (option A, per Technical Notes TN-4), when an admin dev user with zero `user_team_access` rows triggers the bypass, then they resolve to all teams via the widened `_get_permitted_teams`; AND when a non-admin dev-bypass user triggers a later request that previously hit the backfill, then they no longer gain member teams (the removed path), while `_create_dev_user`'s initial member-team assignment and the `_assign_member_teams` helper remain unchanged; the admin check inside `_get_permitted_teams` runs before any emptiness-based logic. The post-change non-admin dev-bypass behavior is pinned by a test, not merely deleted.

## Technical Approach
Implement the admin-sees-all widening per Technical Notes TN-4: add the two-entry-point admin predicate to `src/api/auth.py` (`_user_is_admin(conn, user)` injected + `user_is_admin(user)` own-connection wrapper), widen `_get_permitted_teams` so admins resolve to all team ids while non-admins keep the existing `user_team_access` query, remove ONLY the `_handle_dev_bypass` empty-permitted backfill block (option A -- `_create_dev_user`'s `_assign_member_teams` call and the helper itself STAY; the helper is not dead code), and consolidate the duplicated admin predicate so the route-level copies delegate to the canonical one (cleaning up any now-unused imports). The widening sits at the single chokepoint reached by both the production path (`_resolve_session_from_cookie`) and the dev path (`_handle_dev_bypass`), so all dashboard routes inherit the behavior via `request.state.permitted_teams` with no per-route changes. Do NOT add reset-time user seeding or `role='admin'`-on-create (refuted directions). Do NOT alter the production guard. Cover the 8-test matrix in Technical Notes TN-4, including the multi-team fixture obligation and the option-A backfill-removal assertion. Beyond the enumerated files, discover any additional affected tests with a BEHAVIORAL grep (not a symbol grep, since test helpers are private and tests exercise behavior via `TestClient`): `grep -rlE "permitted_teams|DEV_USER_EMAIL|ADMIN_EMAIL|no_assignments" tests/ --include=*.py`.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/api/auth.py` -- add `_user_is_admin(conn, user)` + `user_is_admin(user)` wrapper; widen `_get_permitted_teams` (admins → all team ids); remove ONLY the `_handle_dev_bypass` empty-permitted backfill block (option A; `_create_dev_user` and `_assign_member_teams` stay)
- `src/api/routes/dashboard.py` -- `_is_admin_user` delegates to the canonical `auth.py` predicate; remove any now-unused `sqlite3`/`closing` imports
- `src/api/routes/admin.py` -- `_require_admin`'s admin check delegates to the canonical `auth.py` predicate

Tests (EDIT -- per SE's verified list):
- `tests/test_auth.py` -- `TestDevUserAutoAssignment` (~line 582, 5 tests): under option A, only `test_existing_dev_user_with_no_assignments_gets_backfilled` breaks (the removed backfill) -- update/supersede it to pin the new behavior; the other 4 and the production-guard tests stay green. Add the AC-8 admin-sees-all assertions.
- `tests/test_dashboard_auth.py` (~line 177): `DEV_USER_EMAIL=coach-multi@` multi-team fixture + the `no_teams_client` fixture that relies on backfill not triggering -- review; likely add an admin-sees-all case.
- `tests/test_admin_routes.py` (~line 243): `TestDevModeEmptyState` -- confirm it still passes (`dev@` is non-admin/0-grants → empty state holds).

Tests (RUN for regression -- name explicitly, may need no edits): `tests/test_dashboard.py`, `tests/test_dashboard_schedule.py`, `tests/test_dashboard_prediction.py`, `tests/test_db.py`.

The behavioral grep in Technical Approach is the backstop for any test not enumerated here.

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
This story is independent of E-228-01 -- it touches `src/api/auth.py` and the two route modules plus auth tests, which do not overlap with E-228-01's files. The two can execute in either order. SE estimated ~15 lines in `auth.py` plus the route dedup, with the 8-test matrix in TN-4. The predicate consolidation (AC-7) is included deliberately to avoid shipping a third copy of a security-relevant admin check -- the drift risk outweighs the small dedup cost. The dev-bypass change (AC-8) is option A, confirmed by DE+SE against the existing tests: remove ONLY the `_handle_dev_bypass` empty-permitted backfill; keep `_create_dev_user`'s assignment and the `_assign_member_teams` helper (not dead code). Option B (removing both call sites) was rejected because it breaks 4 of the 5 `TestDevUserAutoAssignment` tests and falsifies "non-admin unchanged" for a hypothetical non-admin-dev-bypass case, with identical operator outcome. See Technical Notes TN-4.
