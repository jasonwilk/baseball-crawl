# IDEA-058: Proper Python Dependency Management via pyproject.toml

## Status
`CANDIDATE`

## Summary
`pyproject.toml` declares zero runtime dependencies. Runtime deps (matplotlib, httpx, fastapi, etc.) only exist in `requirements.in`/`requirements.txt`. The Dockerfile installs `requirements.txt` directly so production works, but the devcontainer's `pip install -e .` pulls in nothing -- causing `ModuleNotFoundError` for any runtime dependency not separately installed. The devcontainer hacks around this with `pip install -r requirements-dev.txt` in `postCreateCommand` instead of using Python's packaging system properly.

## Why It Matters
- **Broken CLI in dev**: `bb report generate` fails in the devcontainer with `ModuleNotFoundError: No module named 'matplotlib'` because matplotlib is a runtime dep not installed by the editable install. Any runtime dependency added to `requirements.in` but not manually added to `postCreateCommand` will have the same gap.
- **Wrong pattern**: The devcontainer uses `pip install -r requirements-dev.txt` + `pip install -e .` as two separate steps instead of declaring deps in `pyproject.toml` and running `pip install -e ".[dev]"`. This bypasses Python packaging plumbing and creates a divergence between what production installs and what dev installs.
- **Maintenance burden**: Adding a new dependency requires updating `requirements.in` AND potentially `postCreateCommand` if it's needed in dev. Should be one place.

## The Fix
1. Add `[project] dependencies` to `pyproject.toml` mirroring `requirements.in` (use `~=` version constraints)
2. Add `[project.optional-dependencies] dev = [...]` mirroring `requirements-dev.in`
3. Devcontainer `postCreateCommand` replaces `pip install -r requirements-dev.txt` + `pip install -e .` with `pip install -e ".[dev]"`
4. Dockerfile continues using `pip install -r requirements.txt` (pinned hashes for reproducibility)
5. `requirements.in`/`requirements.txt`/`requirements-dev.in`/`requirements-dev.txt` remain for pip-tools workflow and Docker builds

## Rough Timing
Should be done before the next dependency addition. The matplotlib gap is already causing real failures in `bb report generate` from the devcontainer.

## Dependencies & Blockers
- [ ] Check `.claude/rules/dependency-management.md` for pip-tools workflow compatibility
- [ ] Verify `pip-compile` still works with `pyproject.toml` as the source (pip-tools supports this)

## Open Questions
- Should `pyproject.toml` become the single source of truth for deps, with `requirements.in` generated from it? Or keep both in sync manually?
- Does the pip-tools workflow need to change? `pip-compile pyproject.toml -o requirements.txt` is supported.

## Notes
- Discovered during E-187 evaluation: `bb report generate` for Lincoln Southwest Freshman failed to render spray charts because matplotlib wasn't installed in the devcontainer.
- The story file written during E-187 evaluation (`E-187-04.md`, since deleted) has detailed ACs and technical approach that can be reused when this promotes to an epic.
- This is a ~1-2 story epic: one story for pyproject.toml + devcontainer, potentially one for verifying pip-tools compatibility.

---
Created: 2026-03-29
Last reviewed: 2026-03-29
Review by: 2026-06-27
