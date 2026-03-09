# E-084-01: Guard against None values in resolve_proxy_from_dict

## Epic
[E-084: Fix resolve_proxy_from_dict None Value Crash](epic.md)

## Status
`DONE`

## Description
After this story is complete, `resolve_proxy_from_dict()` will handle `None` values in the env dict without crashing. When `dotenv_values()` encounters a bare key with no `=` sign (e.g., a line containing just `PROXY_ENABLED`), it maps that key to `None`. The current code calls `.strip()` on the result of `dict.get()`, which crashes with `AttributeError` when the value is `None`.

## Context
`dict.get("KEY", "")` returns the fallback `""` only when the key is absent from the dict. When the key is present but mapped to `None`, `.get()` returns `None` and `.strip()` raises `AttributeError`. Two callsites in `resolve_proxy_from_dict()` are affected: the `PROXY_ENABLED` lookup and the `PROXY_URL_{profile}` lookup.

`get_proxy_config()` is not affected because `os.environ` never stores `None` values.

## Acceptance Criteria
- [ ] **AC-1**: Given an env dict where `PROXY_ENABLED` maps to `None`, when `resolve_proxy_from_dict(env_dict, "web")` is called, then it returns `None` without raising an exception
- [ ] **AC-2**: Given an env dict where `PROXY_ENABLED` is `"true"` and `PROXY_URL_WEB` maps to `None`, when `resolve_proxy_from_dict(env_dict, "web")` is called, then it returns `None` and logs a warning about the missing URL
- [ ] **AC-3**: Given an env dict where both `PROXY_ENABLED` and `PROXY_URL_WEB` map to `None`, when `resolve_proxy_from_dict(env_dict, "web")` is called, then it returns `None` without raising
- [ ] **AC-4**: New tests covering `None` values are added to `TestResolveProxyFromDict` in `tests/test_http_session.py`
- [ ] **AC-5**: All existing proxy tests continue to pass

## Technical Approach
The two `.get()` calls in `resolve_proxy_from_dict()` need to handle `None` values from `dotenv_values()`. The `(value or "")` idiom converts both `None` and absent keys to an empty string before calling `.strip()`.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/http/session.py` -- fix two callsites in `resolve_proxy_from_dict()`
- `tests/test_http_session.py` -- add `None`-value tests to `TestResolveProxyFromDict`

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
