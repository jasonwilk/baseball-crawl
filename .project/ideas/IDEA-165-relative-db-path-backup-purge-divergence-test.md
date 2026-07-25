# IDEA-165: Exercise the relative-`--db-path` divergence in the purge backup test

## Status
`CANDIDATE`

## Summary
`test_backup_runs_before_the_purge_on_the_resolved_path` (`tests/test_cli_db.py`) pins that `bb db purge-scouting` passes the RESOLVED path to `backup_database`, via `assert_called_once_with(db_path=preview.resolved_path)`. It discriminates — the weaker `db_path=db_path` form fails it, mutation-confirmed — but it does so because the raw value in that invocation is `None`. It never exercises the scenario the requirement actually exists for: a RELATIVE `--db-path`, where `backup_database` (which uses its argument as-is) and `purge_scouting_data` (which routes through `resolve_db_path`) genuinely resolve to two different files. Add a variant that passes a relative `--db-path` from a non-repo-root cwd and asserts the backup received the absolute resolved path.

## Why It Matters
The failure mode is a backup of the WRONG database on the most destructive command in the system, discovered only when someone tries to restore. The current test would catch a regression that drops the resolved path entirely; it would NOT obviously catch a subtler one that resolves differently under a relative input. Testing the real scenario rather than a proxy for it is also the epic's own lesson one level up — E-270-03 exists because a test observed absence instead of driving the destructive path.

## Rough Timing
Low urgency; the behavior is correct today and pinned against the obvious regression. Natural trigger: the next time `src/cli/db.py`'s purge command or `resolve_db_path` is touched, or if a second caller of `backup_database` appears with its own path-resolution assumption.

## Dependencies & Blockers
- [ ] None. E-270-02 shipped the behavior and the pinning test; this only strengthens the test.

## Open Questions
- Is a cwd-dependent test worth the fixture complexity (monkeypatching cwd, or a `tmp_path`-relative invocation), or does the existing argument assertion plus the amended AC-5 prose carry enough of the intent?
- Should `purge_scouting_data` simply receive the resolved path too, making the whole divergence unreachable and the test unnecessary? Judged a provable no-op at E-270-02 review (same function, same input, same process) and deliberately not filed — but it is the structural fix if this ever bites.

## Notes
Raised by PM as an explicitly-optional strengthening during E-270-02 AC-5 re-verification (2026-07-24), after the AC was amended UP to mandate the resolved path. Not a condition of that AC, which requires only that a test pin the argument — which it does. Related: E-270 (E-270-02 AC-5, epic TN-5(d)).

---
Created: 2026-07-24
Last reviewed: 2026-07-24
Review by: 2026-10-22 (90 days)
