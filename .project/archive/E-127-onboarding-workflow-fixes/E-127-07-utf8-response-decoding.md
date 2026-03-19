# E-127-07: Install brotlicffi for Mobile Profile Brotli Decompression

## Epic
[E-127: Onboarding Workflow Fixes](epic.md)

## Status
`DONE`

## Description
After this story is complete, the Python runtime will have `brotlicffi` installed so that httpx can decompress brotli-compressed responses from the GameChanger API. The mobile profile's `Accept-Encoding: br;q=1.0, gzip;q=0.9, deflate;q=0.8` header is correct and matches the real iOS app -- the fix is installing the missing decompression library, NOT modifying headers.

## Pre-Implementation Status
**The header revert is already applied in the working tree** (not yet committed). `src/http/headers.py` has been restored to include `br;q=1.0` in the mobile `Accept-Encoding`. No further changes to `headers.py` are needed. The remaining work is adding `brotlicffi` to the dependency chain.

## Context
The mobile profile headers in `src/http/headers.py` request `Accept-Encoding: br;q=1.0, gzip;q=0.9, deflate;q=0.8`, matching the real iOS GameChanger app (confirmed via proxy session data across all captured iOS sessions). When GC sends a brotli-compressed response, httpx cannot decompress it because neither `brotli` nor `brotlicffi` is installed. The raw compressed bytes are then passed to `response.text` / `response.json()`, which fails with `'utf-8' codec can't decode byte` because compressed bytes aren't valid UTF-8.

The fix is to install `brotlicffi` (the CFFI-based brotli binding that httpx auto-detects for brotli decompression). Headers must NOT be modified -- they must match real app behavior per the project's HTTP discipline rule.

## Acceptance Criteria
- [ ] **AC-1**: `brotlicffi~=1.0` is listed in `requirements.in`.
- [ ] **AC-2**: `requirements.txt` is regenerated via `pip-compile` and includes the pinned `brotlicffi` version with hash.
- [ ] **AC-3**: `import brotlicffi` succeeds in the Python runtime (verify via a quick import test or inline check).
- [ ] **AC-4**: The mobile profile headers in `src/http/headers.py` still include `br` in `Accept-Encoding` (verify they were NOT stripped -- this is a regression guard).
- [ ] **AC-5**: A test verifies that `MOBILE_HEADERS["Accept-Encoding"]` contains `br` (the opposite of the old story's test -- this confirms headers match real app behavior).

## Technical Approach
Add `brotlicffi~=1.0` to `requirements.in` and run `pip-compile` to regenerate `requirements.txt`. The `python:3.13-slim` Docker base image works with `brotlicffi` wheels -- no Dockerfile or devcontainer.json changes needed. httpx auto-detects brotlicffi when installed and handles brotli decompression transparently.

Key files: `requirements.in` (add dependency), `requirements.txt` (compiled output).

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `requirements.in` -- add `brotlicffi~=1.0`
- `requirements.txt` -- regenerated via `pip-compile`
- `tests/test_headers.py` -- test that mobile headers DO include `br` in Accept-Encoding

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
