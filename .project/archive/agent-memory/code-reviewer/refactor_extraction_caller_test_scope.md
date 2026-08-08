# Behavior-Preserving Extraction: the test-scope gap is usually a CALLER's existing characterization suite

When a story extracts/relocates a seam (e.g., moves a `client.post_json` call site from
`generator._resolve_gc_uuid` into a new shared `search.resolve_gc_uuid_by_public_id`), the
story's own AC test list and the implementer's run list tend to enumerate only the NEW test
files and the directly-touched modules. The real scope risk is a **pre-existing characterization
suite that lives in a CALLER's test file**, imports the changed function, and exercises it
through a transport-level mock.

## Concrete instance (E-247-03)
- `generator.py::_resolve_gc_uuid` was rewritten to delegate to the new search seam.
- AC-6 enumerated only test_gamechanger_search / test_url_parser / test_opponents_crawler / test_game_loader.
- But `tests/test_report_generator.py:1847-2060` held ~17 tests that **directly call the real
  `_resolve_gc_uuid`**, mocking only `client.post_json` — so they fully exercise the new chain
  (pagination cap, partial-page short-circuit, content-type/params, E-225 dirty-name short-circuit
  + slash-name normalized fallback). Also test_report_e2e.py, test_e211_report_generator.py,
  test_schedule_crawler.py imported the changed surface. None were in the run list.
- Classified MUST FIX (test scope gap). Resolution was confirmation-only: SE ran them → 130 passed.

## Why this matters doubly
A caller's existing characterization suite is often the **committed pre-change pin** that an
extraction's "byte-identical to pre-story output" HARD GATE actually rests on. The new
story-authored tests usually prove only mode/path-EQUIVALENCE (post-change paths agree with each
other), NOT pre-vs-post. So running the caller's pre-existing suite green both closes the scope
gap AND completes the byte-identical-to-pre-story proof. Flag it as load-bearing, not pro-forma.

## Review move
For any extraction/relocation story, after reading the diff:
`grep -rln "<changed_function>" tests/` and `grep -rln "<modified_module path>" tests/`.
Any test file that imports the changed function/module but is NOT in the implementer's run list =
MUST FIX (confirm-run), even if you trace that it *should* pass — transport-mocked caller tests
survive seam relocation but must be confirmed, not assumed.

## Worktree-origin confirmation (acceptable evidence)
When the implementer closes such a gap, a legitimate proof that the green run hit worktree code
(not stale main via the editable install) is: module `__file__` resolves under
`/tmp/.worktrees/baseball-crawl-E-NNN/src/...`, worktree-only new symbols are importable, and
removed symbols (e.g., a deleted module-level `_UUID_RE`) are absent. A temporary probe test that
asserts this and is then deleted (net-zero diff) is fine.
