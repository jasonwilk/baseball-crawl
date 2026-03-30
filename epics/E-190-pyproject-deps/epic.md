# E-190: Declare Dependencies in pyproject.toml

## Status
`READY`

## Overview
Add `[project.dependencies]` to `pyproject.toml` so the editable install (`pip install -e .`) pulls in runtime dependencies. This fixes `ModuleNotFoundError` failures in the devcontainer (e.g., `bb report generate` failing on matplotlib) and aligns the project with standard Python packaging.

## Background & Context
`pyproject.toml` currently declares zero runtime dependencies. All deps live only in `requirements.in` / `requirements-dev.in`, which feed pip-tools to generate pinned lockfiles. The Dockerfile installs `requirements.txt` directly so production works. But the devcontainer's `pip install -e .` pulls in nothing -- the editable install sees no declared deps.

The devcontainer `postCreateCommand` already runs `pip install -r requirements-dev.txt` then `pip install -e .`. The first step installs all deps from the lockfile; the second registers the package (for the `bb` CLI entry point). Because the editable install declares no deps, it relies entirely on the requirements step having run first. In practice this works -- but it means `pip install -e .` alone in a fresh venv would fail, and the packaging metadata is incorrect.

Discovered during E-187 evaluation: `bb report generate` failed with `ModuleNotFoundError: No module named 'matplotlib'`.

**Expert consultations:**
- **SE**: Recommends adding `[project.dependencies]` with `>=` ranges (packaging convention). Recommends AGAINST adding `[project.optional-dependencies] dev` because `pip install -e ".[dev]"` bypasses pip-tools constraint files and could cause dev dep version divergence. Keep dev deps in `requirements-dev.in` only.
- **CA**: Recommends a separate CA-routed story for `dependency-management.md` rule update, blocked by the SE story. No other context-layer files need updating.

## Goals
- `pyproject.toml` declares all runtime dependencies so `pip install -e .` pulls them in
- `requirements.in` / `requirements.txt` continue to work unchanged for pip-tools and Docker builds
- The dependency-management rule documents the dual-source workflow so future dep additions update both files

## Non-Goals
- Adding `[project.optional-dependencies] dev` to pyproject.toml (dev deps stay in `requirements-dev.in` only -- SE advises against it due to constraint bypass)
- Dropping `requirements.in` files (they remain as the pip-compile input)
- Switching pip-compile to use `pyproject.toml` as input
- Changing the Dockerfile install strategy
- Changing the devcontainer `postCreateCommand` (the existing two-step sequence works correctly once pyproject.toml declares deps)
- Upgrading or changing any dependency versions

## Success Criteria
- `pip install -e .` in a fresh venv installs all 14 runtime deps
- `docker compose up -d --build app` builds and passes health check (Dockerfile unchanged)
- `dependency-management.md` documents the dual-source pattern for future dep additions

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-190-01 | Add runtime dependencies to pyproject.toml | TODO | None | - |
| E-190-02 | Update dependency-management rule for dual-source workflow | TODO | E-190-01 | - |

## Dispatch Team
- software-engineer
- claude-architect

## Technical Notes

### Dual-Source Pattern

After this epic, runtime dependencies are declared in two places:

| Source | Purpose | Consumed by |
|--------|---------|-------------|
| `pyproject.toml [project.dependencies]` | Package metadata for editable installs | `pip install -e .` (devcontainer). Dockerfile uses `--no-deps` so deps are NOT resolved from here. |
| `requirements.in` | pip-compile input for deterministic lockfile | `pip-compile requirements.in -o requirements.txt` |
| `requirements.txt` | Pinned runtime lockfile (hashes) | Dockerfile `pip install -r requirements.txt` (all deps resolved here) |

Dev dependencies remain in `requirements-dev.in` / `requirements-dev.txt` only. They are NOT declared in pyproject.toml.

**Both `pyproject.toml` and `requirements.in` must stay in sync for runtime deps.** Adding, removing, or changing a runtime dependency requires updating both files.

Why two sources: `pyproject.toml` enables proper editable installs (standard Python packaging -- needed for the `bb` CLI entry point). `requirements.in` feeds pip-tools for deterministic pinned lockfiles with hashes (needed for the Dockerfile). Neither can replace the other.

### Version Constraint Convention

- `pyproject.toml`: uses `>=` ranges (packaging convention -- declares minimum compatible version)
- `requirements.in`: uses `~=` ranges (operational convention -- tighter compatible-release pins for pip-compile)

This difference is intentional. pip-compile resolves from `requirements.in` for deterministic builds. The looser `>=` range in `pyproject.toml` ensures editable installs don't fail when lockfile versions advance.

### Why NOT `[project.optional-dependencies] dev`

`pip install -e ".[dev]"` does NOT respect pip-tools constraint files (`-c requirements.txt`). It uses pip's normal resolver, so dev dep versions could diverge from what pip-compile pinned. The existing devcontainer flow -- `pip install -r requirements-dev.txt` (deterministic pins) then `pip install -e .` (package registration + runtime deps) -- is correct and should not change.

### Dockerfile Behavior (Unchanged)

The Dockerfile continues: `pip install -r requirements.txt` (pinned deps with hashes) then `pip install --no-deps -e .` (package registration only). The `--no-deps` flag prevents pip from re-resolving deps already installed from the lockfile. No Dockerfile changes needed.

## Open Questions
None.

## History
- 2026-03-29: Created from IDEA-058
- 2026-03-30: Set to READY after internal review + Codex review.

### Review Scorecard (Planning)
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 -- CR spec audit | 6 | 6 | 0 |
| Internal iteration 1 -- Holistic team (PM) | 3 | 3 | 0 |
| Codex review round 1 | 4 | 3 | 1 |
| **Total** | **13** | **12** | **1** |
