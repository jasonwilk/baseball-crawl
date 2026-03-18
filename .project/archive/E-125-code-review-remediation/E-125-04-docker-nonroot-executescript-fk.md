# E-125-04: Docker Non-Root User + executescript FK Enforcement

## Epic
[E-125: Full-Project Code Review Remediation](epic.md)

## Status
`DONE`

## Description
After this story is complete, the Docker production container will run the application as a non-root user, and all `executescript()` calls will properly enforce foreign key constraints. These are infrastructure hardening fixes that prevent privilege escalation and data integrity violations.

## Context
**Docker root** (Review 04 #3): The Dockerfile has no `USER` directive. The container runs uvicorn as root. If an attacker exploits a vulnerability in FastAPI, they gain root access inside the container.

**executescript FK** (Review 04 #6): SQLite's `executescript()` issues an implicit COMMIT and resets connection state. `PRAGMA foreign_keys=ON` set before the call has no effect inside `executescript()`. This means migrations and seed data loading run without FK enforcement -- FK-violating data could be silently inserted.

## Acceptance Criteria
- [ ] **AC-1**: The Dockerfile creates a non-root user and switches to it via `USER` directive before the CMD/ENTRYPOINT
- [ ] **AC-2**: The application starts successfully as the non-root user (health check passes)
- [ ] **AC-3**: The non-root user can read/write the mounted data directory (`./data/app.db`)
- [ ] **AC-4**: All `executescript()` calls in `migrations/apply_migrations.py`, `src/db/reset.py`, and `scripts/seed_dev.py` enforce foreign keys (either by prepending `PRAGMA foreign_keys=ON;` to the SQL string or by switching to `execute()`)
- [ ] **AC-5**: A test verifies that FK enforcement is active during migration execution (e.g., attempt to insert a row with a bad FK reference during a migration and confirm it fails)
- [ ] **AC-6**: All existing tests pass
- [ ] **AC-7**: `docker compose up -d --build app` succeeds and health check passes

## Technical Approach
**Docker non-root**: Per Technical Notes TN-4, add a `RUN useradd` + `USER` directive. The data directory mount permissions need consideration -- the non-root user must own or have write access to `./data/`. The `docker-compose.yml` may need a `user:` directive or the Dockerfile can `chown` the app directory.

**executescript FK**: Per Technical Notes TN-4, the simplest fix is to prepend `PRAGMA foreign_keys=ON;\n` to the SQL string before passing it to `executescript()`. This is a one-line change per call site.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `Dockerfile` (add non-root user)
- `docker-compose.yml` (potentially, for data directory permissions)
- `migrations/apply_migrations.py` (FK enforcement in executescript)
- `src/db/reset.py` (FK enforcement in executescript)
- `scripts/seed_dev.py` (FK enforcement in executescript)
- `tests/test_migrations.py` (FK enforcement test)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The non-root user change affects production deployment. The `docs/production-deployment.md` runbook may need a note about data directory ownership if the existing `./data/` directory was created by root.
- The FK enforcement issue hasn't caused visible problems because seed data and migrations are correct, but it's a latent risk that must be fixed.
