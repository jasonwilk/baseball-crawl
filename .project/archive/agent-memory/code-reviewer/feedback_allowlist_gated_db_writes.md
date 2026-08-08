---
name: allowlist-gated-db-writes
description: When a DB write helper filters columns through an allowlist/frozenset, every new column needs a real-schema round-trip test or the write silently drops
metadata:
  type: feedback
---

When a run-record / telemetry write helper filters its kwargs through an allowlist
(e.g. `_update_run_record` in `src/reports/generator.py`: `fields = {k: v ... if k in _RUN_RECORD_COLUMNS}`),
a new column is silently DROPPED if the author forgets to add it to the allowlist —
no error, the value just never persists (reads back NULL).

**Why:** During E-236, every story that added a count column (plays_errors,
boxscores_fetched, spray_games_with_data, load_errors) had to add it to
`_RUN_RECORD_COLUMNS` AND prove the write lands. The proof pattern that works:
a real-schema round-trip test (`load_real_schema` → INSERT row → call the writer →
SELECT the column back → assert the exact value). A test asserting `run["col"] == N`
through the real schema fails loudly if the allowlist add was forgotten (reads NULL).

**How to apply:** For any story that writes a NEW column through an allowlist-gated
helper, REQUIRE (a) the column added to the allowlist frozenset, and (b) a
round-trip assertion against the real schema (not a mock). A unit test that mocks
the writer or only checks the in-memory value does NOT catch the dropped write —
insist on the real-schema round-trip. This is a MUST FIX gap if the write is
claimed but only mock-tested. Related: [[E-147 allowlist write-lands]] is the same
class as the migration-column-before-code deploy-time check.
