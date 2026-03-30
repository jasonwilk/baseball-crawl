---
paths:
  - "requirements*"
  - "pyproject.toml"
  - ".python-version"
  - "Dockerfile"
  - ".devcontainer/devcontainer.json"
---

# Dependency Management

This project uses **pip-tools** for deterministic dependency management, with runtime dependencies declared in two places to support both editable installs and deterministic lockfiles.

## Why Two Sources for Runtime Dependencies

Runtime dependencies are declared in both `pyproject.toml` and `requirements.in`. Neither can replace the other:

- **`pyproject.toml [project.dependencies]`** enables standard Python editable installs (`pip install -e .`), which the devcontainer uses to register the `bb` CLI entry point. Without this, `pip install -e .` would install the package with zero dependencies.
- **`requirements.in`** feeds pip-tools (`pip-compile`) to produce deterministic pinned lockfiles with hashes. The Dockerfile uses the lockfile for reproducible production builds.

**Both files must stay in sync for runtime deps.** Adding, removing, or changing a runtime dependency requires updating both.

### Version Constraint Convention

The two files use different range operators intentionally:

- `pyproject.toml`: `>=` (e.g., `httpx>=0.28`) -- packaging convention declaring the minimum compatible version. Looser range ensures editable installs don't fail when lockfile versions advance.
- `requirements.in`: `~=` by default (e.g., `httpx~=0.28`) -- operational convention providing tighter compatible-release pins for pip-compile. Some packages use `>=` where compatible-release doesn't fit (e.g., `typer[all]>=0.9` because typer's versioning makes `~=` too restrictive).

pip-compile resolves from `requirements.in` for deterministic builds. The `>=` range in `pyproject.toml` is never used for resolution in production (Dockerfile uses `--no-deps` for the editable install).

## File Layout

| File | Purpose |
|------|---------|
| `pyproject.toml [project.dependencies]` | Runtime deps for editable installs (`pip install -e .`); mirrors `requirements.in` |
| `requirements.in` | Direct runtime dependencies for pip-compile |
| `requirements-dev.in` | Dev-only dependencies (pytest, respx, etc.) + constrains to production pins via `-c requirements.txt` |
| `requirements.txt` | Generated -- all runtime deps fully pinned (used by Dockerfile) |
| `requirements-dev.txt` | Generated -- all dev + runtime deps fully pinned |

Dev dependencies are NOT declared in `pyproject.toml`. They remain in `requirements-dev.in` / `requirements-dev.txt` only. (`pip install -e ".[dev]"` does not respect pip-tools constraint files, so dev dep versions could diverge from lockfile pins.)

## Common Operations

**Add a runtime dependency**:
1. Add to `pyproject.toml [project.dependencies]` with a `>=` range
2. Add to `requirements.in` with a `~=` range (or `>=` where compatible-release doesn't fit)
3. Run `pip-compile`
4. Run tests
5. Commit `pyproject.toml`, `.in`, and `.txt` files

**Upgrade a runtime dependency**:
1. Update the range in both `pyproject.toml` and `requirements.in`
2. Run `pip-compile`, run tests, commit all three files

**Remove a runtime dependency**:
1. Remove from both `pyproject.toml` and `requirements.in`
2. Run `pip-compile`, run tests, commit all three files

**Add a dev dependency**: Add to `requirements-dev.in` only (not `pyproject.toml`), run `pip-compile`, run tests, commit `.in` and `.txt` files.

## Notes

- pip-tools is a dev/build tool. It is NOT listed in any `.in` file -- it is installed via `postCreateCommand` in the devcontainer.
- `requirements-dev.in` uses `-c requirements.txt` (constraint file) to ensure dev dependencies resolve to the same transitive versions as production.

# Python Version Policy

- **Source of truth**: `.python-version` (pyenv). All other locations must match it.
- **Also specified in**: `pyproject.toml` (`requires-python`), `Dockerfile` (`FROM` tag), `.devcontainer/devcontainer.json` (Python feature version).
- **Current version**: 3.13 -- chosen over 3.14 (httpx/jinja2 lack official 3.14 support markers) and over 3.12 (all deps support 3.13, extending the EOL window).

**When to consider upgrading:**
- Annually, when a new stable Python release has been out 6+ months and key dependencies support it.
- Immediately, when a dependency drops support for the current version.

**How to verify before upgrading:**
- Check dep compatibility at pyreadiness.org or via per-package PyPI classifiers.
- Run `pip install -r requirements.txt` on the new version.
- Run `pytest` and confirm no failures.
- Check for deprecation warnings in test output.

**When you update the version**, change it in all four locations atomically and reference the story in the commit.
