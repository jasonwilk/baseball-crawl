# E-057: pip-tools Dependency Management

## Status
`READY`
<!-- Lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED) -->

## Overview
Adopt pip-tools to gain deterministic, fully-pinned dependency installs with transitive dependency tracking. The project currently pins direct dependencies but has no visibility into or control over transitive versions, making builds non-reproducible across environments and upgrades risky.

## Background & Context
The project has 14 direct dependencies in `requirements.txt` with exact pins (e.g., `httpx==0.28.1`) but zero transitive pinning. This means `pip install -r requirements.txt` can resolve different transitive versions on different machines or at different times, leading to subtle bugs. pip-tools solves this with a two-file workflow: `requirements.in` (what you want) and `requirements.txt` (what you get, fully resolved).

**Expert consultation (SE -- tool selection)**: SE consultation attempted but unavailable via Task tool. PM assessed directly based on project knowledge and dependency management domain expertise. pip-tools was evaluated against Poetry, PDM, and uv. pip-tools is the right fit: it adds transitive pinning without changing the install workflow (Dockerfile still does `pip install -r requirements.txt`). Poetry/PDM are overkill for a non-publishing Docker-deployed project. uv is promising but still maturing; migration from pip-tools to uv is trivial later if desired (same file format).

**Expert consultation (claude-architect -- CLAUDE.md changes)**: E-057-02 modifies CLAUDE.md, a context-layer file. The proposed additions are: (1) a "Dependency Management" subsection documenting the two-file workflow, and (2) pip-compile commands in the Commands section. Both follow existing CLAUDE.md patterns -- Commands already lists similar tool invocations, and Tech Stack already has comparable subsections. These are factual documentation additions, not architectural or agent-system changes. claude-architect is the correct implementer per routing precedence (context-layer file), and the additions are appropriate for CLAUDE.md scope.

## Goals
- All Python dependencies (direct and transitive) are pinned to exact versions in `requirements.txt`
- Direct dependencies are declared with compatibility ranges in `.in` files, making upgrades intentional and safe
- Production Docker image installs only runtime dependencies (no test tooling)
- Developer workflow for adding/upgrading deps is documented and repeatable

## Non-Goals
- Migrating to Poetry, PDM, or uv as the dependency manager
- Changing the Dockerfile install command (`pip install -r requirements.txt` stays as-is)
- Upgrading any dependency versions (this epic establishes the workflow; upgrades are separate work)
- Adding pip-tools to the Docker production image (it is a dev/build tool only)

## Success Criteria
- `requirements.in` and `requirements-dev.in` exist with compatibility-ranged direct deps
- `requirements.txt` and `requirements-dev.txt` are pip-compile output with full transitive pins
- `pip install -r requirements.txt` in a clean venv produces an identical environment to the current one (no version changes)
- `pip install -r requirements-dev.txt` in a clean venv includes all dev+runtime deps
- All 930+ existing tests pass without modification
- Dockerfile builds successfully using the new `requirements.txt`
- CLAUDE.md Commands section documents the pip-compile workflow

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-057-01 | Create .in files and compile pinned outputs | TODO | None | - |
| E-057-02 | Update project docs and developer workflow | TODO | E-057-01 | - |

## Dispatch Team
- software-engineer
- claude-architect

## Technical Notes

### File Layout
```
requirements.in          # Direct runtime deps with ~= ranges
requirements-dev.in      # Dev-only deps (pytest, respx, etc.) + includes requirements.in
requirements.txt         # pip-compile output from requirements.in (GENERATED -- do not edit)
requirements-dev.txt     # pip-compile output from requirements-dev.in (GENERATED -- do not edit)
```

### Compatibility Range Strategy
- Default: `~=` (compatible release). E.g., `httpx~=0.28` allows `0.28.*` but not `0.29`.
- Exception: `starlette` should be pinned with `~=` matching the range FastAPI expects. Add a comment in `requirements.in` explaining the FastAPI coupling. pip-compile will resolve the intersection.
- Exception: `uvicorn[standard]~=0.34` -- extras are handled correctly by pip-tools.

### Starlette Handling
Currently `starlette==0.41.3` is explicitly pinned in requirements.txt with comment "pinned here for run_in_threadpool access." In the pip-tools world, starlette is a transitive of FastAPI. Two options:
1. **List it in requirements.in** with a comment -- makes the intentional pin visible.
2. **Let it resolve transitively** -- simpler, but less visible.

Recommendation: Option 1. List `starlette~=0.41` in `requirements.in` with a comment. pip-compile will resolve the intersection of FastAPI's requirement and our explicit pin. If they conflict, pip-compile will error clearly, which is what we want.

### Dev vs. Runtime Split
**Runtime** (`requirements.in`): httpx, fastapi, uvicorn[standard], starlette, jinja2, aiofiles, python-multipart, webauthn, python-dotenv, pyyaml
**Dev-only** (`requirements-dev.in`): pytest, pytest-asyncio, pytest-timeout, respx, plus `-r requirements.in` to inherit runtime deps

### Dockerfile Impact
None. The Dockerfile line `RUN pip install --no-cache-dir -r requirements.txt` does not change. The generated `requirements.txt` is a superset of the current one (same direct pins + transitive pins added). The production image continues to exclude dev deps.

### Devcontainer Impact
pip-tools needs to be available for developers to run `pip-compile`. Add it to `postCreateCommand` or document `pip install pip-tools` as a one-time setup step. It should NOT be listed in any `.in` file -- it is a build tool.

Recommendation: Add `pip install pip-tools` to the devcontainer `postCreateCommand` chain, after the main `pip install -r requirements.txt` (or `requirements-dev.txt`).

### Migration Safety
The first `pip-compile` must produce a `requirements.txt` whose direct pins match the current file exactly. Transitive pins will be added. The acceptance criteria verify this by running the full test suite against the compiled output. No version changes should occur in this epic -- only transitive visibility is added.

### pip-compile Invocation
```bash
pip-compile requirements.in --output-file=requirements.txt --strip-extras --generate-hashes
pip-compile requirements-dev.in --output-file=requirements-dev.txt --strip-extras --generate-hashes
```
The `--generate-hashes` flag adds integrity verification. If it causes issues with any package (some packages lack hashes on PyPI), drop it and note the reason. The `--strip-extras` flag keeps the output clean.

## Open Questions
- Whether `--generate-hashes` works cleanly for all 14 direct deps and their transitives. If any package lacks hashes, the story should document which ones and proceed without hashes rather than blocking.

## History
- 2026-03-06: Created. pip-tools selected over Poetry/PDM/uv based on project scale, simplicity principle, and zero Dockerfile install-command impact.
- 2026-03-06: Spec review triage. Fixed 6 findings: (P1) added claude-architect consultation rationale for CLAUDE.md changes; (P2) tightened AC-3 baseline to `git show HEAD:requirements.txt`; (P2) removed implementer epic-file edits from AC-8 -- hash fallback reporting goes to PM via completion message; (P2) fixed DoD wording in both stories to remove internal contradiction; (P3) made AC-1 comment format concrete with examples; (P3) made AC-3/AC-4 in E-057-02 specify required content points instead of vague line counts. Epic re-verified as READY.
