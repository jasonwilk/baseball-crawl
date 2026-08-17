<!-- NO REAL NAMES OR IDENTIFIERS — no person's name, ever; for teams, orgs, ids and UUIDs use the PII-Safe Placeholder Taxonomy in `.claude/rules/api-docs.md`. -->

# The reaper can still delete a finished report's served HTML

**Date**: 2026-08-17 · **Status**: `STUB` — routed to its own chunk by operator ruling
2026-08-17, to run BEFORE the runs-as-scoreboard instrument.
**Source**: `/code-review` of commit `2217092` (the orphan-cleanup FK rollback chunk),
run after that chunk was approved and committed. Findings verified against the files by
the spec session before routing — this stub is not a relay.

## Why this is owed

`2217092` fixed the reaper's unlink race by making the guarded UPDATE's rowcount the
arbiter. **It closed one of the two interleavings.** The other still ends in the same
place: a report the admin list calls `ready` whose share link 404s, silently.

`generate_report` writes the HTML and only THEN commits `ready`
(`src/reports/generator.py:2702`, then `:2705` → `_update_report_ready`), and that UPDATE
carries no status guard (`:272-275`). So:

```
generation writes data/reports/{slug}.html
  → reaper's UPDATE ... WHERE status='generating' claims the row (rowcount 1 → 'failed')
  → generation commits status='ready', report_path set
  → reaper unlinks the file
```

End state: `status='ready'`, `report_path` set, **file gone**, reaper reporting
`reaped=1, files_removed=1, errors=0`. The chunk's own reproduction of the ORIGINAL defect
describes this exact end state (`src/reports/lifecycle.py:320-325`). A resurrected row
also keeps the reaper's `Reaped: generation did not complete` `error_message`, because
`_update_report_ready` never clears it.

**Bound, stated honestly.** Much narrower than the defect already fixed: it needs a
generation past the 1-hour staleness threshold that then finishes, AND the reap must land
between the file write and the `ready` commit — milliseconds. Not reproduced live; the
mechanism is read off the two orderings. But the regenerate is a bulk CLI workload, which
is when long generations are most likely.

## Two smaller findings from the same review, same file

- **The SAVEPOINT statement sits OUTSIDE its `try`** (`src/reports/lifecycle.py:971-972`).
  If it raises, the exception escapes `cleanup_orphan_teams`, `generator.py::_cleanup_orphans`
  swallows it, and the connection closes with the transaction live — the whole-batch
  rollback the loop exists to prevent, re-arming the permanence mechanism. ⚠ Moving it
  inside the `try` is NOT free: the `except` runs `ROLLBACK TO`/`RELEASE`, which themselves
  fail if the savepoint was never created. This sharpens STANDING RESIDUAL 1, which
  currently names only Phase 1's first DELETE.
- **`deleted_count += 1` without checking the DELETE's rowcount** (`:973-975`), while the
  comment above it claims the count is taken "where the outcome actually HAPPENS". Mostly
  unreachable under the pass's `BEGIN IMMEDIATE`, but it contradicts the rowcount-arbiter
  pattern the SAME commit adopted for the reaper.

## Shape of the fix — not yet decided, decide at spec time

The unlink is the privileged action and it is currently unguarded by anything read at
unlink time. Candidates, none ruled: re-read `status`/`report_path` immediately before
`unlink()` and skip when the row moved; give `_update_report_ready` its own
`AND status = 'generating'` guard so a reaped row cannot silently resurrect (which changes
what happens to a legitimately-late generation — decide what SHOULD happen to it); or
order the generator's file write after the `ready` commit. Each has a different failure
mode for the late-finishing generation, which is the case that matters.

⚠ This touches the serving path and a destructive pass. It owes `/code-review` AND
`/security-review`, and both are operator-typed.

## Progress log

- **2026-08-17** — Stubbed from a post-commit `/code-review`. All three findings verified
  against the files (the two orderings read directly; `_update_report_ready`'s missing
  guard confirmed). Operator ruled: its own chunk, next, before the runs instrument. No code.
