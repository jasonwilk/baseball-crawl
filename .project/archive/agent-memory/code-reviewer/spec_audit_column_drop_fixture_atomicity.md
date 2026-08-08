# Spec Audit: a column-DROP story that asserts full-suite-green cannot defer fixture cleanup

When a planning story drops a DB column/table AND asserts a full-suite-green gate,
grep the test tree for EVERY fixture that references the dropped element before trusting
the story's scope split. A dropped column breaks all its INSERT fixtures **atomically** —
the instant the migration runs, every `INSERT INTO <table>(..., <dropped_col>, ...)` raises
`OperationalError: no column named <dropped_col>`. So the fixture cleanup CANNOT be deferred
to a downstream story: at the drop-story's "done" the suite is objectively red, making its
green-gate AC unachievable, and the two stories overlap-own the same fixture files.

## How to catch it during a spec audit
1. Identify the dropped schema element(s) from the migration story's ACs.
2. `grep -rln "<element>" tests/` (include `tests/fixtures/*.sql`). Count the files.
3. Check which story owns removing those references. If it's NOT the drop story, but the
   drop story asserts pytest-green, that is a MUST-FIX scope/dependency finding.
4. Distinguish separable work: value-shape normalization (e.g. compound `season_id` slug →
   year-only) is INDEPENDENT of a *different* column's drop and can live in a separate
   story. Only the references to the DROPPED element are atomically coupled.

## The fix to recommend
Fold all `INSERT`-fixture removal for the dropped element into the drop story (atomic with
the migration), or merge the two stories. Whichever story removes the references is the one
whose full-suite-green AC is asserted. Also check same-file dependency ordering: if an
earlier story edits a test file that the fixture-cleanup story must also edit, the cleanup
story needs an explicit `blocked-by` on the earlier one (project rule: same-file stories
MUST declare ordering).

Instance: E-250 (2026-07-03) planning audit — E-250-02 dropped `seasons.season_type` with a
full-suite AC while 29 test files + 2 SQL fixtures still INSERTed it; cleanup was assigned to
downstream E-250-03. Related: [[route_deletion_test_sweep]] (deletion breaks tests via
import/client-get/literal-path — same "sweep ALL reference mechanisms" discipline, applied to
schema drops instead of route/module deletion).
