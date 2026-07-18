# E-266-02: Add `playwright` to dev dependencies (lockfile)

## Epic
[E-266: Pitcher Outings Breakdown — Expand-in-Place & Print](epic.md)

## Status
`TODO`

## Description
After this story is complete, the Python `playwright` package is a declared dev dependency and present in the compiled dev lockfile, so the devcontainer's chromium install step (E-266-03) and the headless-Chromium test (E-266-04) have the `playwright` CLI and library available. This is the pip-tools dependency slice that unblocks the testing infrastructure.

## Context
The browser-render test (epic TN-6) uses Python Playwright. The `playwright` CLI that runs `playwright install --with-deps chromium` ships FROM this pip package, and the devcontainer `postCreateCommand` runs `pip install -r requirements-dev.txt` before its chromium install step — so the package must be in the lockfile first (epic TN-7). This story is dev-tooling only; it adds no runtime dependency and touches no application code.

## Acceptance Criteria
- [ ] **AC-1**: `playwright` is added to `requirements-dev.in` (dev dependency, not a runtime `requirements.in` entry).
- [ ] **AC-2**: `requirements-dev.txt` is recompiled from `requirements-dev.in` via the project's pip-tools flow (per `.claude/rules/dependency-management.md`), pinning `playwright` and its transitive deps; no churn beyond `playwright`'s transitive requirements (a legitimate shared-pin bump forced by `playwright`'s transitive deps — e.g. `greenlet`/`pyee`/`typing-extensions` — is acceptable and expected; unrelated churn is not, per software-engineer F5).
- [ ] **AC-3**: The compiled lockfile is internally consistent (the recompile is the standard `pip-compile` output, not a hand-edit).

## Technical Approach
Follow the pip-tools workflow in `.claude/rules/dependency-management.md`: add `playwright` to `requirements-dev.in`, recompile `requirements-dev.txt`. No application code changes. The chromium browser BINARY is not a pip artifact and is installed separately (E-266-03 devcontainer step + the live-container operator step in epic TN-7) — this story only lands the Python package.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-266-03 (devcontainer postCreate needs the package in the lockfile), E-266-04 (test imports playwright)

## Files to Create or Modify
- `requirements-dev.in` (modify — add `playwright`)
- `requirements-dev.txt` (modify — recompile)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-266-03**: the `playwright` package in `requirements-dev.txt` that the devcontainer `postCreateCommand`'s `pip install -r requirements-dev.txt` step consumes before running `playwright install`.
- **Produces for E-266-04**: the importable `playwright` library the browser test depends on.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
This story trips the Step 1d build-input trigger at epic closure (epic TN-7, Footgun 2) — expected and correct. The Step-1d/closure dependency reinstall gets this package but NOT the chromium binary (that is the separate operator step, epic TN-7 Footgun 1).
