# Pytest Verbose Flag Requirement

**Always pass `-v` when running pytest.** This is a hard requirement, not a suggestion.

```bash
# CORRECT
python -m pytest tests/ -v
python -m pytest tests/test_foo.py -v
python -m pytest tests/test_foo.py::TestBar -v --timeout=10

# WRONG -- never run pytest without -v
python -m pytest tests/
python -m pytest tests/test_foo.py -q
```

## Why

RTK (Rust Token Killer) rewrites `python -m pytest` to `rtk pytest` for token savings. Without `-v`, `rtk pytest` hides test failures entirely -- it shows `Pytest: No tests collected` for both passing and failing runs. With `-v`, it correctly shows pass/fail counts and failure details.

This caused 67 test failures to accumulate silently across multiple epics (E-173 and others) because agents and code reviewers saw "all tests pass" when they didn't.

## Applies to

- All `python -m pytest` invocations
- All `pytest` invocations
- Both main checkout and epic worktrees
- Both targeted test runs and full suite runs
