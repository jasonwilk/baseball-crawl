# E-266-03: Devcontainer headless-Chromium infra + `devcontainer.md` boundary doc

## Epic
[E-266: Pitcher Outings Breakdown — Expand-in-Place & Print](epic.md)

## Status
`DONE`

## Description
After this story is complete, the devcontainer installs headless Chromium on build (via `playwright install --with-deps chromium` in the postCreate flow), and `.claude/rules/devcontainer.md` documents the browser-test infrastructure and its dev/main-checkout-only, not-a-CI-gate boundary. This provides the browser binary the headless-Chromium test (E-266-04) runs against.

## Context
The browser-render test (epic TN-6) needs a chromium binary, which is not a pip artifact. claude-architect ruled: install chromium-only (~150MB, one-time; worktrees share the container FS) in the devcontainer `postCreateCommand`, dev/main-checkout only, NOT a CI gate — mirroring Step 1d's live-only boundary (epic TN-7). This is a context-layer/infra story owned by claude-architect. The `.claude/rules/devcontainer.md` file already exists and is extended here.

## Acceptance Criteria
- [ ] **AC-1**: The devcontainer post-create flow runs `playwright install --with-deps chromium` (chromium only) after `pip install -r requirements-dev.txt`, so a freshly built container has the browser binary available. Under the fail-closed test design (epic TN-6, reconciling CA-F1 + SE-F1) the flow does NOT set a run-enabling env marker — a postCreate export would not reach the non-interactive closure pytest anyway, and the test hard-fails if chromium is absent. (The exact placement — `postCreateCommand` in `.devcontainer/devcontainer.json` vs. `.devcontainer/post-create-env.sh` — is claude-architect's call to match the existing post-create structure.)
- [ ] **AC-2**: `.claude/rules/devcontainer.md` documents the browser-test infra: chromium-only install, the dev/main-checkout-only boundary, that it is NOT a CI gate (mirrors Step 1d's live-only boundary), that it is authoritative in the full-suite-green closure gate, AND the fail-closed test convention with its opt-out escape-hatch env var — the exact literal `SKIP_BROWSER_TESTS` (per epic TN-6, the same token E-266-04's test reads — cross-story pin) — for chromium-less contributor environments (epic TN-6/TN-7).
- [ ] **AC-3**: The doc records the two install footguns per epic TN-7 — Footgun 1 (the one-time live-container operator step `pip install -r requirements-dev.txt && playwright install --with-deps chromium`, since `postCreateCommand` only fires on a future build) and Footgun 2 (this class of change trips Step 1d at closure, whose reinstall gets the package but not the browser binary).

## Technical Approach
Add the chromium install to the existing post-create flow (matching whether the project uses inline `postCreateCommand` or the `post-create-env.sh` script), sequenced after the dev-lockfile install. Extend `.claude/rules/devcontainer.md` with the boundary + footgun documentation per epic TN-7. Do not add a CI workflow — the test is a closure-gate/live-container test, not CI (epic Non-Goals).

## Dependencies
- **Blocked by**: E-266-02 (postCreate `pip install -r requirements-dev.txt` needs the `playwright` package in the lockfile first)
- **Blocks**: E-266-04 (test needs the chromium binary)

## Files to Create or Modify
- `.devcontainer/devcontainer.json` and/or `.devcontainer/post-create-env.sh` (modify — add chromium install to the post-create flow)
- `.claude/rules/devcontainer.md` (modify — document the browser-test infra + boundary + footguns)

## Agent Hint
claude-architect

## Handoff Context
- **Produces for E-266-04**: the chromium binary (in a freshly built container) the browser test runs against; the operator-step documentation the E-266-04 operator-step AC references.

## Definition of Done
- [ ] The post-create flow runs `playwright install --with-deps chromium` AFTER the dev-lockfile install (AC-1); it sets NO run-enabling env marker
- [ ] `.claude/rules/devcontainer.md` documents the dev/main-checkout-only boundary, the NOT-a-CI-gate note, the fail-closed convention + the exact `SKIP_BROWSER_TESTS` opt-out token (AC-2), and BOTH install footguns including the AUTHORITATIVE one-time live-container operator step (AC-3, single source of truth for E-266-04's pointer)
- [ ] No CI workflow added (epic Non-Goals)
- [ ] Code follows project style (see CLAUDE.md); no regressions in existing tests

## Notes
Context-layer story — routes to claude-architect per the context-layer routing precedence (`.devcontainer/` infra + `.claude/rules/`). The live-running container is NOT updated by this story's postCreate change; that is the operator step captured on E-266-04 (epic TN-7 Footgun 1).
