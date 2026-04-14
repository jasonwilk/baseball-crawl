---
paths:
  - "**"
---

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

# WRONG -- never use -x/--exitfirst (see below)
python -m pytest tests/ -v -x
python -m pytest tests/ -v --exitfirst
```

## Why

RTK (Rust Token Killer) rewrites `python -m pytest` to `rtk pytest` for token savings. Without `-v`, `rtk pytest` hides test failures entirely -- it shows `Pytest: No tests collected` for both passing and failing runs. With `-v`, it correctly shows pass/fail counts and failure details.

This caused 67 test failures to accumulate silently across multiple epics (E-173 and others) because agents and code reviewers saw "all tests pass" when they didn't.

## Never Use `-x`/`--exitfirst`

**Do not pass `-x` or `--exitfirst` to pytest.** RTK compression hides suite truncation — the summary may show "N passed" without indicating hundreds of untested files were skipped. Remove `-x` for all suite runs. This applies to combined short flags too (`-xvs`, `-vx`, etc.).

## Interpreting RTK Output

RTK compresses pytest output. Before reporting results, sanity-check the summary line:
- Does the test count match expectations for the file or suite being tested?
- If the count seems suspiciously low (e.g., 3 passed for a full suite run), investigate before reporting success — RTK may have compressed away failure details or the run was truncated.

## RTK Bypass

When full output fidelity is required (parsing failure details, debugging output format issues), bypass RTK compression:

```bash
rtk proxy python -m pytest tests/ -v --timeout=30
```

`rtk proxy` passes the command through without filtering, giving raw pytest output.

## Applies to

- All `python -m pytest` invocations
- All `pytest` invocations
- Both main checkout and epic worktrees
- Both targeted test runs and full suite runs
