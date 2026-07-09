# E-256-06: Add .dockerignore; delete the orphaned data/seeds surface

## Epic
[E-256: Post-Descope Simplification & Foundations](epic.md)

## Status
`TODO`

## Description
After this story is complete, the repo has a `.dockerignore` that keeps `.env`, the live DB, and `.git` out of the Docker build context, and the orphaned `data/seeds/` deploy surface — which makes a fresh clone's documented deploy dead on arrival — is fully removed rather than resurrected.

## Context
Two independent fixes are bundled here because both concern the Docker build context and a fresh clone. No `.dockerignore` today means `.env`, the live DB, and `.git` all ship to the daemon as build context — one careless `COPY . .` from baking secrets into layers. Separately, `data/seeds/` is not in git despite `.gitignore` claiming it is, and `Dockerfile:41`'s `COPY data/seeds/` breaks any fresh clone. Git forensics settle the direction (Technical Notes §9): `seed_dev.sql` was **never tracked**, so committing it would resurrect ~21 KB of demo data E-228 deliberately removed and contradict the `bb db reset` empty-DB invariant. Fix = delete the orphaned surface, not commit the file.

## Acceptance Criteria
- [ ] **AC-1**: Given the repo root, when this story is complete, then a `.dockerignore` exists that excludes at least `.env*`, `data/` (the live DB + backups), `.git/`, `__pycache__/`, and `*.pyc` from the build context, and a `docker build` succeeds without them present in context.
- [ ] **AC-2**: Given the Dockerfile, when this story is complete, then the `COPY data/seeds/` at `Dockerfile:41` is deleted; the `chown` at `Dockerfile:38` keeps its non-`/seeds` components (the `/seeds` component is dropped); and the runtime bind-mount comment noting the shadow is preserved or corrected.
- [ ] **AC-3**: Given `.gitignore`, when this story is complete, then the dead `!data/seeds/` negations (lines ~40-41) are deleted.
- [ ] **AC-4**: Given a fresh `git clone`, when `docker compose build` is run, then it succeeds with no missing-`data/seeds/` failure.

## Technical Approach
Delete, do not commit — see Technical Notes §9 for the forensics. This is a **single-owner SE story** (repo-root build/ignore files only). Per CA's Q1 routing rule, the `docs/admin/architecture.md:67` seeds-line correction (a `docs/admin/` edit, docs-writer's domain) is **factored OUT of this story into story 10** (the docs-writer docs/admin story) — it is NOT an AC here. The stale on-disk `seed_dev.sql` (untracked) can be left alone or noted; it is invisible to git and harmless once the COPY is gone.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-256-09 (CI runs `docker build`, which needs `.dockerignore` and a clean fresh-clone build)

## Files to Create or Modify
- `.dockerignore` (create)
- `Dockerfile` (lines ~38, ~41)
- `.gitignore` (lines ~40-41)
- (NOT `docs/admin/architecture.md` — the seeds-line correction is story 10's, per Q1 routing.)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-256-09**: a clean fresh-clone `docker build` that the CI workflow's `docker build` stage depends on.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing (a build-context or fresh-clone assertion where feasible)
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Committing the seed file would contradict the documented `bb db reset` empty-DB invariant (`.claude/rules/data-model.md`). Deletion is the settled direction.
