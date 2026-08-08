# Code Reviewer Agent Memory

## Closure-Smoke (Step 1d) Adjudication
- [A red mobile creds profile is not a preflight fail](closure_smoke_preflight_creds_profile.md) — `bb creds check` always prints mobile dead (no programmatic refresh); the reports path uses WEB only, so check `--profile web` before calling ENV-FAIL. Also records what retired with the 2026-07-26 ratchet demotion: Step 1d now asserts only `self_games == 0` and ignores the exit code, so stale-baseline drift can no longer reach you as a FAIL.

## Measured Tool Behavior
- [A new gate inherits its host hook's enumeration](new_gate_inherits_hook_enumeration.md) — MEASURED: `--diff-filter=ACM` excludes renames, so a `git mv` archive move is 0 entries; E-279-04's AC told the implementer to verify the delete+add shape, the one that WORKS. Check the host's filter and early exits.
- [Tool gotchas](tool_gotchas.md) — tools that silently return the wrong answer: `checkout-index` and skip-worktree, ruff's `include` walk-filter, unsplit `$files` exiting 0, `git show HEAD:` mid-epic, `fnmatch` and `**`, `core.quotePath`, `git diff` blind to untracked.
- [Worktree pytest loads the WORKTREE's src/](worktree_pytest_loads_the_worktree_src.md) — MEASURED: `PathFinder` precedes the appended `_EditableFinder`, and pytest puts the repo root on `sys.path[0]` because `tests/__init__.py` exists. The Test Execution Constraint in my own agent definition is FALSE. Two conditions carry it; verify before relying.

## Calibration (findings of mine that were falsified)
- [Three errors in one thread, each while fixing the last](past_tense_prediction_in_a_batch.md) — E-280: `git add -A >/dev/null 2>&1 || true; echo "(no add run -- read-only)"` — it ran (plain P1 violation); I diagnosed it as a GAP in P2 (a gap-shaped story is more available to a defect's author, and feels like rigour); then mischaracterized the Prohibitions section though I'd quoted it verbatim myself. **Reading for property X ≠ checking property Y.** Delete the command, don't annotate it.
- [Regenerate the population, don't diff the pair you hold](regenerate_the_population_not_the_pair.md) — E-279: twice in one session I found ONE discrepancy and stopped (a 3rd residual count 11 lines away; a hit in my OWN grep output I never ruled on). Finding *a* discrepancy feels like finishing the check. Prefer remedies immune to an incomplete list.
- [Never claim a ratio-gate population change is side-effect-free](ratio_gate_population_claims.md) — E-267-02: my "no false refusals" hand-derivation held at N=30 and broke at N=3. Enumerate fail-open AND fail-closed, evaluate at the smallest realistic N, say "verify empirically".
- [Re-verify "the defect still persists" after a redesign narrows the code](stale_defect_characterization.md) — E-267-03: I carried a round-1 harm description into round 2 where the new `team_id` predicate had made it false. Quote the WHERE clause, walk the binding positionally.
- [Never rule on gate coverage from a config constant or a rule file](gate_behavior_needs_the_executable.md) — E-275: I ruled the PII gate did NOT cover `epics/` from `SKIP_PATHS` + a stale rule file; `.githooks/pre-commit` runs a SECOND gate that does. A constant scopes one mechanism; a hook composes several. My proposed fix was the more alarming sentence.
- [A call site proves CONSTRUCTED, never CONSUMED](finding_severity_needs_the_callee.md) — E-278: I rated a two-part record string "coach-facing" from the call site; the callee documents the param as *"accepted for call-site compatibility, intentionally unused"*. One Read of the consuming function refutes a severity. Retract in the same channel and prominence as the claim.
- ["Same branch" is not a reason to withdraw a test-coverage finding](finding_withdrawal_shared_branch_reasoning.md) — E-272-02: I withdrew a sibling case on shared-return reasoning; the four names route through four distinct patterns, so enumeration discriminates. Concede when the implementer's version is better.

## Closure-Pass Practice
- [Verdicts that say nothing vanish](verdicts_that_say_nothing_vanish.md) — a "no change needed" ruling and a clean APPROVED cause no artifact effect, so neither leaves a trace. Write a verdict per surfaced site; issue every verdict as `APPROVED @ <tree-sha>`. E-280: a delivered 06 verdict sat in the scorecard as UNRECORDED, settled only by mtime-vs-send-time. **Also: a DELTA needs two anchors — `<delta> @ <base> → <tree>`. You hold your base implicitly, so it is the half that goes unwritten.**
- [Run the shipped gate against its OWN epic](run_the_shipped_gate_against_its_own_epic.md) — E-279 shipped an archive-ref gate whose trigger E-279's own closure satisfies; one execution returned exit-1 BLOCKED, at the last point where the remedy was a reword not `--no-verify`. Prove the exclusion with a known-present control (E-243: 6 hits = ran, archive-tree dropped = filter works).
- [Re-diffstat at Step 1b/1d and compare to what you reviewed](closure_diff_growth_after_integration_review.md) — E-272: the closure diff grew 15→37 files AFTER my Step 1c APPROVED, `src/` included. Remediation + PM bookkeeping land after the last review BY DESIGN. Never let an approval stretch; state src/-reviewed vs context-layer-unreviewed precisely. Also check `git status` for `??`/`MM` — "everything is staged" was wrong twice.

## Spec-Audit Frame Patterns
- [Check REACHABILITY before adjudicating DIRECTION](check_reachability_before_adjudicating_direction.md) — a dispute hands you a framed question, so the cheapest decisive check is the one nobody runs (E-276: 4 agents, 3 rounds on the direction of an asymmetry that fires nowhere; one grep settled it). Also: give reasons not verdicts, record which axes a run held CONSTANT, and prefer a column that SHOWS a property over an inference that implies it.
- [Enumerate BACKWARDS from the cited artifact](enumerate_backwards_from_the_cited_artifact.md) — a broken edge is invisible walking forward from the consumer; grep the consumers for the TN/idea's OWN id, and regenerate every exhaustive-class claim from the directory (E-276: TN-19 cited by nobody, IDEA-189 linked by nobody, "three ideas"/"two files" were five and five).
- [Sweep the RESIDUE of each correction, not whether it landed](spec_audit_sweep_correction_residue.md) — E-278: all 5 surviving MUST FIX were stale copies of claims corrected elsewhere in the SAME file (a retired rule sitting in Success Criteria). Also: a planning audit runs against a MOVING target — `stat` the files before finalizing, and publish a label map when re-auditing.
- [Auditing a MOVING target: snapshot, pin by hash, verdict by identity](auditing_a_moving_target.md) — MEASURED (E-280): a "frozen" tree moved across ~8 batches and my own `cp` raced the writer mid-file. Verify the snapshot's mtime across the copy, publish a hash manifest, and when a re-check tree is byte-identical to what you verdicted, carry the verdicts over — re-grepping identical bytes is theater.
- [A churn inventory drawn over CONSUMER test files omits the primitive's own](inventory_frame_omits_the_primitives_own_tests.md) — recompute from the changed SYMBOL; if the headline test count equals the named files EXACTLY, that equality is the frame and what it excludes holds the unsatisfiable AC (E-276: 34+20+18=72, primitive's 19 tests invisible, one asserts the exact input the fix inverts). Item 5 carries my OWN falsified rule: shape-count vs combination-count is a unit error, and I verified the counterexample in the same session I generalised past it.

## Invariant Audit Patterns
- [Sibling writers can defeat a provenance guard](invariant_audit_sibling_writer.md) — when an epic guards ONE writer, sweep sibling DELETE+rederive paths that delete the protected row first (E-237 merge_player_pair).
- [Spec audit: distrust "sole/canonical producer" claims](spec_audit_sibling_producer.md) — grep src/ for literal output forms + sibling `_derive_*`/`_ensure_*` helpers before trusting an epic's enumerated producer set (E-241: crawler `_derive_season_id` falsified "no code path produces YYYY-suffix" + broke migration durability).

## Removal-Epic Review Patterns
- [Asset deletion: sweep ALL test reference mechanisms](route_deletion_test_sweep.md) — deleting a route/module/template breaks tests that import it, `client.get()` it (assert 200), OR read it by literal path in a parametrize list (FileNotFoundError); import sweeps miss forms 2+3. Never `| head` a completeness grep (E-239: Codex caught form 2 in 4b, Phase 5 gate caught form 3).
- [Spec audit: a column-DROP story asserting full-suite-green can't defer fixture cleanup](spec_audit_column_drop_fixture_atomicity.md) — a dropped column breaks all its INSERT fixtures atomically; if cleanup is assigned downstream while the drop story asserts pytest-green, that's a MUST-FIX scope/dependency finding. Grep `tests/` (incl. fixtures/*.sql) for the dropped element and count files (E-250: season_type in 29 files + 2 SQL fixtures).

## Refactor/Extraction Review Patterns
- [A moved function resolves its NEW module's globals — every such name is a detached test seam](moved_function_resolves_new_module_globals.md) — implementers catch the constants and miss `get_connection`; trace INDIRECT call paths, and note a swallowing `try/except` at the call site makes "suite green" independent of "seam attached" (E-256-04: 43 tests would have hit the live 17MB dev DB).
- [Extraction scope gap = a CALLER's existing characterization suite](refactor_extraction_caller_test_scope.md) — when a story relocates a seam, the unrun test is usually a caller's pre-existing transport-mocked suite that directly exercises the changed function; grep tests/ for the changed function + module, flag any importer not in the run list as MUST FIX (it's often the committed pre-vs-post pin the HARD gate rests on). E-247-03: test_report_generator.py's ~17 _resolve_gc_uuid tests.
- [Removing an early-return before a recompute/dedup tail: prove no-op on a POPULATED DB](recompute_tail_noop_populated_db.md) — a fresh-DB no-op test is necessary but NOT sufficient; a rebuild-from-source tail (historically `canonical_recompute`, retired in E-259; the surviving dedup half can still merge) re-derives from ALL existing per-game rows, so on a populated/out-of-sync DB the unconditional tail mutates data. Demand a populated-DB characterization test; under a stat HARD gate, restore the early-return. (E-247-01 F1, caught by Codex Phase 4b after I missed it; general lesson re-validated in E-259-01/02.)

## Reset/Abort & Guard-Fix Review Patterns
- [Whole-file revert destroys same-file ancillary edits; prove which vector a guard-fix moves](reconcile_whole_file_revert_vs_ancillary.md) — (1) a reset/abort `git checkout -- <file>` nukes a same-file ancillary hunk staged by another step (E-251-01 abort vs Step 7a MEMORY.md — I passed it in Phase 4a, Codex caught it); (2) to rule on a guard-fix, run pre-vs-post + the single-slash/negative control to separate the guard's pre-existing scope from what the fix changed, and read the AC's binding clause not its parenthetical example.

## Mandatory Review Checks -- MOVED, NOT RETIRED

All five (SQL dimension audit, fallible call chain, status write lifecycle, multi-dimension test coverage, error-path CLI tests) live in `.claude/agents/code-reviewer.md`'s Bug Pattern Checklist, in fuller form and with their defect citations attached. Deleted from memory 2026-07-26 (layer pass D6) as duplication of a file you always load. **They are still mandatory** -- if you cannot find one there, it was lost in a later edit, not retired.

## Recurring Patterns Found in Reviews

### Allowlist-gated DB writes need real-schema round-trip proof
See [allowlist-gated DB writes](feedback_allowlist_gated_db_writes.md) — when a write helper filters
columns through an allowlist (e.g. `_update_run_record` + `_RUN_RECORD_COLUMNS`), a new column is
silently dropped if not added to the allowlist. Require the allowlist add AND a real-schema round-trip
test (not a mock). E-236 used this pattern correctly across 4 count columns.

### Test/Implementation Alignment on Behavior Changes
When an implementer changes behavior for correctness (e.g., making PII-safe fallbacks instead of email exposure),
existing tests written against the old behavior will break. Always run the full related test suite, not just
new test files. Pre-existing tests that document old behavior need to be updated when behavior intentionally changes.

### Duplicate Helper Functions
When a story says "consider moving to a shared location (implementer discretion)" for a utility function,
and the implementer instead creates a near-identical copy in a different module, flag as SHOULD FIX.

### PII in Tests
Test files may contain fake PII (email addresses) as test data. The `# synthetic-test-data` comment at the
top of test files marks them as containing synthetic data. Real PII must never appear.

### Files in the assignment but not in the diff
A file listed in the review assignment but absent from your review diff was not changed by this story --
it existed before. The scope guardrail applies: only flag code WRITTEN OR MODIFIED in the current story.
**Mechanism updated 2026-08-02 (E-280): the diff is `git diff <prev-tree-sha> <this-tree-sha>`, not
`git diff HEAD` and not the unstaged diff.** The rule was always sound; only the command was stale.

## Project-Specific Conventions
- `from __future__ import annotations` required at top of every module
- `Optional[str]` from typing is acceptable in Typer CLI commands (existing pattern)
- Bare `except Exception:` needs `# noqa: BLE001`
- Test files use `# synthetic-test-data` comment for files with fake credentials/emails
- `dotenv_values()` from python-dotenv is the standard way to load .env in tests (monkeypatched)

## Security Review Mandate (added after E-123 full-project code review)

The Priority 4 security review checklist was expanded significantly after a full-project code review
found critical issues (CSRF, SQLi, SSRF, XSS, plaintext tokens, root Docker) that should have been
caught during story-level reviews. The checklist is now in the agent definition under Priority 4 with
subsections 4a-4h. Key reminders:

- Cloudflare/WAF/network controls are NOT compensating controls for app-layer defects. Never downgrade.
- `|safe` in Jinja2 templates is a red flag -- must be justified for every use.
- POST forms without CSRF tokens are automatic MUST FIX.
- SQL via f-string/format/concat is automatic MUST FIX regardless of input source.
- URL following (pagination, redirects) must validate host before sending auth headers.
- All stored tokens/secrets must be hashed -- inconsistency between token types is a defect.
- Header parsing (Retry-After, etc.) must handle malformed values without crashing.
- Docker containers must not run as root.

## Important File Locations
- Python style rules: `.claude/rules/python-style.md`
- Testing rules: `.claude/rules/testing.md`
- Story files: `/epics/E-NNN-slug/` or `/.project/archive/E-NNN-slug/` after archival
