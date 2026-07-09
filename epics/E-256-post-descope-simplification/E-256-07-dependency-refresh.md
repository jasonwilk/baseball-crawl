# E-256-07: Dependency refresh and vulnerable-pin remediation

## Epic
[E-256: Post-Descope Simplification & Foundations](epic.md)

## Status
`TODO`

## Description
After this story is complete, the known-vulnerable jinja2 and starlette pins are upgraded, the lockfiles are recompiled, `requirements-dev.txt` is brought current, and the devcontainer no longer backfills unpinned dependencies. This removes a starlette version carrying an unauthenticated Range-parser DoS (GHSA-7f5h-v6xp-fcq8 / CVE-2025-54121).

## Context
This is a real, security-relevant fix that must not be buried as a routine dependency bump — but its framing must be accurate, not inflated. SE's exact recommended framing, proven by loading the real `src.api.main:app` (DEV_USER_EMAIL/ADMIN_EMAIL unset) and issuing unauthenticated requests through the full stack:

> The app runs a starlette version with an unauthenticated Range-parser DoS (GHSA-7f5h-v6xp-fcq8) plus CVE-2025-54121. The `/static` mount that exposes it is live and unauthenticated (confirmed by live request — a protected route 302s to login, `/static/*` serves 200 anonymously, and the `Range` parser executes 206 on an unauthenticated request). It currently hosts no real files (`src/api/static/` is empty except a tracked `.gitkeep`, and no template references `/static/`), so exploitation *today* is limited — but the mount exists precisely so CSS/JS can be added, and the first committed static asset makes it a fat target with no code change. The vulnerable version ships regardless; the fix (starlette ≥0.49.1, proven green) should not wait.

So the accurate reading is: the mount is live and unauthenticated (confirmed), the vulnerable version is in production, but there is **no sizeable current blast radius** because `/static` serves nothing today. `src/api/auth.py:45` lists `/static/` in `_EXCLUDED_PREFIXES` (that is what makes the mount pre-auth); there is no rate limiting in `src/api/` and Cloudflare is a plain tunnel, so the first real asset added is exposed with no further code change. jinja2 3.1.5 carries CVE-2025-27516 in the same refresh. The coordinated fastapi/starlette bump lands well past the `≥0.49.1` fix floor (Technical Notes §11).

The user was offered a ship-now-as-hotfix option and **chose to keep this in E-256** (2026-07-09). That choice keeps E-256's dispatch priority security-relevant — accurate-and-still-urgent, not inflated.

SE validated the upgraded stack: full suite **`3849 passed, RC=0`** in an isolated venv. See Technical Notes §11 for the target versions and the ~11-package scope.

## Acceptance Criteria
- [ ] **AC-1**: Given `requirements.in`, when this story is complete, then `requirements.in:9`'s `starlette~=0.41` bound is widened to permit the CVE-fixed floor, and `pip-compile` resolves `requirements.txt` to versions **at or above the CVE-fixed floors** (`starlette ≥0.49.1`, `jinja2 ≥3.1.6`), with `fastapi` bumped to whatever the coordinated resolve requires (FastAPI 0.139 dropped its starlette upper bound, so `fastapi~=0.115` already permits it). **The exact triple `fastapi==0.139.0` / `starlette==1.3.1` / `jinja2==3.1.6` is the as-of-planning target SE validated (`3849 passed`), not a hard pin** — `pip-compile` picks latest-compatible at run time, so a newer patch is acceptable (and preferable). **If the resolver selects a version above the validated target at dispatch time, the implementer re-runs the full suite to re-establish green on the actual resolved set.** AC-2 (pip-audit clean) is the real security gate, not literal-version equality.
- [ ] **AC-2**: Given `pip-audit` (or an equivalent vulnerability check) run against the recompiled `requirements.txt`, when this story is complete, then it reports **zero** known vulnerabilities for jinja2 and starlette.
- [ ] **AC-3**: Given the recompile, when this story is complete, then `requirements-dev.txt` is regenerated so it is no longer 3 runtime deps stale, and the devcontainer editable install adds `--no-deps` so it no longer backfills unpinned dependencies (matplotlib now pins 3.11.0, resolving the existing 3.10.8-vs-3.11.0 drift the suite already ran under).
- [ ] **AC-4**: Given the full suite on the upgraded stack, when this story is complete, then it is green in the main checkout (SE's isolated-venv run was `3849 passed`).

## Technical Approach
Coordinated fastapi/starlette bump per Technical Notes §11. State the ~11-package scope in the change so a reviewer does not read it as scope creep — `pip-compile --upgrade` moves fastapi, starlette, jinja2, matplotlib, numpy, uvicorn, typer, webauthn, python-multipart and their transitive deps, not only the two CVE packages. Follow `.claude/rules/dependency-management.md` for the `*.in` → `*.txt` workflow. A new `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated` appears on the bumped stack — captured as IDEA-110, not fixed here.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-256-09 (CI's lockfile-drift check needs the recompiled lockfiles)

## Files to Create or Modify
- `requirements.in`
- `requirements.txt`
- `requirements-dev.in` / `requirements-dev.txt`
- `.devcontainer/devcontainer.json` (or wherever the editable install runs — add `--no-deps`)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-256-09**: the recompiled, drift-free lockfiles the CI lockfile-drift check verifies.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing (full suite green on the upgraded stack)
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
The exposure is real and security-relevant (a vulnerable starlette version in production behind a live, unauthenticated `/static` mount), but its current blast radius is limited because `/static` serves no real files yet — so flag the dispatch priority as accurate-and-still-urgent, not as an active large-scale DoS. The urgency is that the first committed static asset makes it exploitable with no code change. Do not let this story sit behind lower-severity cleanup at dispatch time.
