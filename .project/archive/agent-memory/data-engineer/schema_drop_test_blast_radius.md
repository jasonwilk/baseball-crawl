---
name: schema-drop-test-blast-radius
description: When dropping a column/table (layered migration), the test blast radius is far wider than the INSERT sites — a checklist of what breaks the full-suite green gate.
metadata:
  type: reference
---

# Schema-Drop Test Blast-Radius Checklist

When a migration DROPs a column or table (the layered pattern — 006, 008/E-250),
the code-reference removal is the easy part. The full-suite green gate breaks on
test sites that a grep-for-INSERT misses. This is the concrete form of the
E-241-06 "grep recon is insufficient, only the full suite proves it" lesson and
the "enumerate the concern, not the line" discipline.

For a **dropped COLUMN**, every one of these breaks with `no such column`:
- SELECTs of the column (even when the selected value is never asserted — e.g. a
  `SELECT season_id, season_type, year` where only year/season_id are read).
  A shared query constant (`_QUERY_ALL_ORDERED`) breaks EVERY test that uses it.
- INSERTs naming the column in fixtures (direct `INSERT INTO t (...col...)`).
- Assertions on a tuple shape that includes the column (`assert row == (...)`) —
  the expected tuple must DROP the element, not just the query.
- A whole test class whose *premise* is the column (e.g. `TestEnsureSeasonRow`
  asserting `season_type` is always `'default'`) — semantics change once the
  writer stops populating it; the class docstring + multiple sub-tests all shift.
- Docstrings mentioning the column are PROSE — they do NOT break the gate, but
  update them for accuracy. Classify SQL-read vs docstring before scoping.

For a **dropped TABLE**, these break:
- A dedicated constraint/CRUD test class for the table → DELETE it wholesale
  (not edit) — it tests a table that no longer exists.
- Expected-tables assertion SETS (`_EXPECTED_TABLES`, `expected_tables` in
  test_schema.py / test_migrations.py / test_e100_schema.py). The functional
  break is SET MEMBERSHIP (`missing = expected - actual`), not a count. Any
  "N expected tables" docstring is cosmetic (no `len()==N` assert usually) but
  update it.
- A test that uses the table as its **FK-violation vehicle** (`pytest.raises(
  sqlite3.IntegrityError)` wrapping `INSERT INTO dropped_table` with bad FK ids).
  After the drop that INSERT raises `OperationalError (no such table)`, which the
  `IntegrityError` raises-context does NOT catch → the test ERRORS. Repoint to
  another all-FK-bearing table (e.g. `team_rosters`: INSERT team_id=9999,
  player_id='nope', season_id='nope' → teams-FK IntegrityError under FK enforce).

**AC-wording rule**: scope the removal AC to the CONCERN ("remove ALL <col>
usages across these files"), never to specific line numbers — line-scoped ACs
miss the second/third occurrence in the same file (a file often carries BOTH a
column-tuple edit AND a table-drop deletion — two independent edits, easy to do
one and miss the other). See [[fixture_seed_not_rollup_consistent]] for the
sibling fixture-classification footgun.

DROP feasibility (SQLite): direct `ALTER TABLE ... DROP COLUMN` needs 3.35+
(runtime is 3.45.1) AND no index/view/trigger/generated-column/FK dependency on
the column, and no inbound `REFERENCES <table>` FK for a DROP TABLE. Verify by
grep across `migrations/*.sql` and document it in the migration header (006 did).
