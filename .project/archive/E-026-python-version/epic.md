# E-026: Python Version Governance -- Migrate to 3.13

## Status
`COMPLETED`
<!-- Lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED) -->

## Overview
Establish a single source of truth for the project's Python version, migrate from 3.12 to 3.13, and document a version maintenance policy. The current use of 3.12 was a model training artifact, not a deliberate decision -- there is no `.python-version` file, no `pyproject.toml`, and no documented rationale. This epic fixes that.

## Background & Context

### What exists today
Python 3.12 appears in two places:
- `Dockerfile`: `FROM python:3.12-slim`
- `.devcontainer/devcontainer.json`: `ghcr.io/devcontainers/features/python:1` with `"version": "3.12"`

There is no `.python-version` file, no `pyproject.toml` with `requires-python`, no documented version policy, and no single source of truth. The version was inherited from model training data, not chosen deliberately.

### Why 3.13
Research (completed prior to this epic) evaluated 3.12, 3.13, and 3.14:
- **3.14** (current stable, EOL Oct 2031): httpx and jinja2 lack official 3.14 support markers. Too risky.
- **3.13** (bugfix phase, EOL Oct 2030): All project dependencies officially support it. Mature and well-tested.
- **3.12** (bugfix phase, EOL Oct 2029): Works fine but is unnecessarily behind when 3.13 is fully compatible.

3.13 is the right target: mature, fully supported by all deps, and a meaningful step forward from 3.12 without the compatibility risk of 3.14.

### CLAUDE.md version references
CLAUDE.md currently says "Python 3.12" in the Tech Stack section. This reference must be updated to reflect the new version and point to `.python-version` as the source of truth, rather than hardcoding a version number that drifts.

### Expert consultation
No expert consultation required. This is straightforward development environment governance -- choosing a Python version, creating standard config files, and updating existing references. No domain, API, architecture, or schema expertise is needed.

### Relationship to E-025
E-025 (Devcontainer Update) is currently ACTIVE and sets `"version": "3.12"` in devcontainer.json. E-026 will update that same file to `"3.13"`. There is no dependency -- E-026 simply overwrites the version field regardless of E-025's state.

## Goals
- A single source of truth (`.python-version`) governs the Python version across all project files
- All version references (Dockerfile, devcontainer.json, CLAUDE.md) are consistent at 3.13
- A `pyproject.toml` declares `requires-python` so tooling can enforce the minimum version
- A documented version maintenance policy explains when to upgrade and how to verify compatibility
- All existing dependencies install and tests pass on Python 3.13

## Non-Goals
- Migrating from `requirements.txt` to `pyproject.toml` for dependency management (only `requires-python` is added)
- Adding CI/CD version matrix testing
- Supporting multiple Python versions simultaneously
- Upgrading any Python dependencies (only verifying they work on 3.13)
- Automating version bumps across files (manual process with clear docs is fine for this project's scale)

## Success Criteria
- `.python-version` exists and contains `3.13`
- `pyproject.toml` exists with `requires-python = ">=3.13"`
- `Dockerfile` uses `python:3.13-slim`
- `.devcontainer/devcontainer.json` specifies `"version": "3.13"` for the Python feature
- CLAUDE.md Tech Stack section references `.python-version` instead of hardcoding a version number
- CLAUDE.md contains a Python Version Policy section documenting where the version is specified, when to upgrade, and how to verify
- All dependencies from `requirements.txt` install without errors on Python 3.13
- All existing tests pass on Python 3.13

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-026-01 | Migrate to Python 3.13 and establish version source of truth | DONE | None | general-dev |
| E-026-02 | Document Python version maintenance policy in CLAUDE.md | DONE | None | general-dev |

## Technical Notes

### Source of truth: `.python-version`
The `.python-version` file is the canonical source for the project's Python version. It contains a single line: `3.13`. This is the file that humans and tooling (pyenv, asdf, IDE integrations) check first.

### `pyproject.toml` -- minimal scope
The `pyproject.toml` is created ONLY for `requires-python`. This epic does NOT migrate dependency management from `requirements.txt` to `pyproject.toml`. The file should contain:
```toml
[project]
name = "baseball-crawl"
requires-python = ">=3.13"
```
That is it. No `[build-system]`, no `[tool.*]` sections, no dependencies. Keep it minimal -- complexity as needed.

### Files to update for version change
1. `.python-version` (CREATE) -- `3.13`
2. `pyproject.toml` (CREATE) -- `requires-python = ">=3.13"`
3. `Dockerfile` (MODIFY) -- `FROM python:3.12-slim` -> `FROM python:3.13-slim`
4. `.devcontainer/devcontainer.json` (MODIFY) -- `"version": "3.12"` -> `"version": "3.13"`
5. `CLAUDE.md` (MODIFY) -- Tech Stack section: replace hardcoded "Python 3.12" reference with a reference to `.python-version` as the source of truth

### CLAUDE.md version policy section
Story E-026-02 adds a new "Python Version Policy" section to CLAUDE.md (after Tech Stack) documenting:
- Where the version is specified (`.python-version` is source of truth; also in `pyproject.toml`, Dockerfile, devcontainer.json)
- When to upgrade (annually, or when a dependency drops support for the current version)
- How to verify (install deps, run tests, check dep compatibility on pyreadiness.org)
- The current rationale (why 3.13 was chosen over alternatives)

### Verification approach
The implementer of E-026-01 should:
1. Make all file changes
2. Run `pip install -r requirements.txt` to confirm all deps install on 3.13
3. Run `pytest` to confirm all tests pass
4. Check for any deprecation warnings in test output

### Parallel execution
E-026-01 and E-026-02 have NO file conflicts and can run in parallel:
- E-026-01 touches: `.python-version`, `pyproject.toml`, `Dockerfile`, `.devcontainer/devcontainer.json`, CLAUDE.md (Tech Stack line only)
- E-026-02 touches: CLAUDE.md (new Python Version Policy section only)

The CLAUDE.md edits are in different sections (Tech Stack line vs. new Version Policy section), so parallel execution is safe.

## Open Questions
None. The research is complete and the scope is clear.

## History
- 2026-03-03: Created as READY. Python version research completed prior to epic creation. No expert consultation required -- development environment governance.
- 2026-03-03: Epic set to ACTIVE. Both stories (E-026-01, E-026-02) dispatched IN_PROGRESS in parallel via Agent Teams.
- 2026-03-03: Both stories DONE. All acceptance criteria verified. Epic COMPLETED. Changes: .python-version created (3.13), pyproject.toml created (requires-python >=3.13), Dockerfile updated to python:3.13-slim, devcontainer.json updated to version 3.13, CLAUDE.md Tech Stack updated to reference .python-version, Python Version Policy section added to CLAUDE.md. All deps install and tests pass on 3.13.
