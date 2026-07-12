# E-256-07: Dependency refresh and vulnerable-pin remediation

## Epic
[E-256: Post-Descope Simplification & Foundations](epic.md)

## Status
`DONE`

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
- `pyproject.toml` (PM-approved addition during dispatch: its `starlette>=0.41` / `jinja2>=3.1` floors **still permit the vulnerable versions**. `dependency-management.md` requires the two files stay in sync for runtime deps, and a floor is the durable guard where a lockfile is only a snapshot — any `pip install -e .` without `--no-deps` would resolve straight back into the CVE. Omitting this file was a real defect in the story's Files list, not an SE overreach.)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-256-09**: the recompiled, drift-free lockfiles the CI lockfile-drift check verifies.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing (full suite green on the upgraded stack)
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## PM AC-Verification (2026-07-09)
**ALL FOUR ACs PASS.** Verified against the worktree.

- **AC-1 PASS** (re-verified 2026-07-09 against the tightened ranges). `requirements.in` now carries `starlette>=0.49.1,<2`, `jinja2>=3.1.6,<4`, `python-multipart>=0.0.31,<0.1`; `pyproject.toml:18,19,21` mirrors all three floors. `requirements.txt` resolves `starlette==1.3.1`, `jinja2==3.1.6`, `fastapi==0.139.0` — at or above every CVE-fixed floor. Suite re-run on the actual resolved set per AC-1's re-validation clause.

  **AC-1's own PREMISE was factually wrong, and the AC passed anyway — by design.** AC-1 said *"`requirements.in:9`'s `starlette~=0.41` bound is widened to permit the CVE-fixed floor."* But `~=0.41` expands to `>=0.41,==0.*`, which **already permitted 0.49.1**. The bound never blocked the fix floor; what it could not span was **1.x**, and what actually pinned the lockfile at the vulnerable 0.41.3 was **fastapi 0.115's metadata cap `starlette<0.42`** — a transitive constraint, not the line AC-1 named. The ceiling, not the floor, was always the real subject.

  This is the same false-model family as the `pyproject.toml` mechanism error (see Ruling 1's correction): the epic's spec, SE, and PM all reasoned about *floors* when the operative constraint was a *ceiling* imposed elsewhere. **AC-1 survived its own wrong premise only because it made `pip-audit` (AC-2) the security gate rather than literal-version equality** — the hedge in AC-1's final sentence did exactly the work it was written to do. Record for future spec authors: when an AC's rationale names a specific line as the blocker, the AC should still be satisfiable by an outcome check, because the named line is the part most likely to be wrong.
- **AC-2 PASS** — and this is the real security gate. `pip-audit --no-deps -r requirements.txt` → RC=0. SE ran the audit against `git show HEAD:requirements.txt` as a **control first**, which is what makes the clean result meaningful: a clean report from a tool that finds nothing proves nothing. SE also installed `pip-audit` rather than report an ungated AC.
- **AC-3 PASS.** `.devcontainer/devcontainer.json:17` ends `pip install --no-deps -e .`; both lockfiles regenerated.
- **AC-4 PASS.** `3814 passed, RC=0`, reconciling exactly: `3849 (pre-dispatch) − 19 (story 01) − 16 (story 02) = 3814`.

**Ruling 1 — `pyproject.toml` is IN SCOPE, and its omission was a story defect.** Its `starlette>=0.41` / `jinja2>=3.1` floors permitted the vulnerable versions. The edit is **mandated outright** by `dependency-management.md:21` ("Both files must stay in sync for runtime deps"). The **third** Files-list undercount in three stories; the rule-gap hypothesis (that the "Upgrade a runtime dependency" checklist does not restate the sync requirement) is routed to claude-architect at closure.

**CORRECTION (post-CR, 2026-07-09).** PM's first draft of this ruling repeated SE's stated mechanism — *"any `pip install -e .` without `--no-deps` resolves straight back into the CVE"* — and that mechanism is **FALSE**. The old floors were unbounded above, so a plain `pip install -e .` resolves the newest compatible version, not the vulnerable one. `dependency-management.md:30` says so directly: the `>=` range in `pyproject.toml` "is never used for resolution in production (Dockerfile uses `--no-deps`)". The **real** protection is against **backtracking**: an environment that pins `fastapi==0.115` (whose metadata caps `starlette<0.42`) drags starlette back down to 0.41.x. Conditional, but genuine — plus defense-in-depth for any non-production editable install. The edit was right; PM's and SE's shared reason for it was wrong, and PM verified the wrong reason no harder than SE asserted it. **When this rule gap is routed to CA, the checklist must state the WHY, not just the WHAT** — otherwise the next implementer reconstructs the same false model, exactly as happened here twice in one review round.

**Ruling 2 — the `pytest` / PYSEC-2026-1845 deferral is CORRECT, captured as IDEA-120.** PM independently verified the deferral's entire basis: `Dockerfile:21-22` copies and installs `requirements.txt` **only** — there is no `requirements-dev.txt` in the image, so the advisory is unreachable in production. SE tested the resolver conflict (`pytest-asyncio 0.25.0` declares `pytest<9,>=8.2`) rather than asserting it, and routed instead of reaching. Closing it needs a pytest-asyncio migration + async-suite revalidation — a separate, bounded piece of work.

**Ruling 3 — the runtime gap is REAL, and it is bigger than this story.** Two distinct claims were conflated:
1. *The `/static` exposure claim is NOT unverified.* It was proven by live request at planning time and recorded in this story's Context (`§Context`, SE's framing paragraph): a protected route 302s to login while `/static/*` serves 200 anonymously and the `Range` parser executes 206 unauthenticated. Dispatch-time SE could not re-run it in the worktree; that does not un-verify it.
2. *The genuinely NEW gap is the starlette MAJOR bump (0.41.3 → 1.3.1).* `pytest` exercises the app **in-process via TestClient** and never boots the image, so uvicorn/FastAPI **startup** is unexercised by the closure suite. Three transitive MAJOR bumps and a webauthn crypto-backend swap ride along.

Step 1d (story 11) does not currently close it, for two reasons PM routed there as **story-11 AC-4b**: its preflight says "stack up," not *rebuild* — starting a stale image and passing `curl /health` certifies the OLD image; and §3's trigger paths omit `requirements.txt` / `Dockerfile` / `pyproject.toml` entirely, so **a pure dependency-refresh epic would not trigger Step 1d at all** — an inverted gate, since that is exactly the epic class `pytest` cannot see. Both fixed in story 11's ACs. Since 11 lands before this epic's single atomic closure commit, nothing reaches production unsmoked.

## Notes
The exposure is real and security-relevant (a vulnerable starlette version in production behind a live, unauthenticated `/static` mount), but its current blast radius is limited because `/static` serves no real files yet — so flag the dispatch priority as accurate-and-still-urgent, not as an active large-scale DoS. The urgency is that the first committed static asset makes it exploitable with no code change. Do not let this story sit behind lower-severity cleanup at dispatch time.
