# Reaper-race review findings — six carried defects

**Status:** COMPLETE (this commit) — `acceptance: run`. All six carried defects closed, plus
THREE further sites of the same permanent-orphan leak found during execution: one by the audit
(the claim itself failing, no race involved), and two by `/code-review` on the fixes (the
no-games claim, then the no-games recovery block). The stub named one site; there were four. TWO
residuals routed out and onto the board: a live report can be reported to its caller as failed,
and the leak is narrowed rather than closed — a filesystem error still strands a file.

⚠ This line said "One residual" through the approved commit `af813ef`, while the body below
already carried two. The second was added late and its summary was not re-read against it — the
exact header-contradicts-body defect `.claude/rules/tool-discipline.md` names, caught at the
step-9 sweep rather than before the commit. The board entry it promised was also missing and
landed after.

## Provenance, and the audit obligation this creates

These findings came out of `/code-review` run during the Ordering-2 test chunk (commit
`c4de4f6`). That review's range was `origin/main...HEAD` plus the working tree — and because
the push posture is hold, `origin/main` was 4 commits behind, so the reviewer received 954
lines across 13 files rather than that chunk's 224-line test-only diff. Every finding below
therefore lands on code ALREADY COMMITTED at `846e9eb` (the chunk-18 reaper-race fix), not on
the test chunk that triggered the review.

**F1 and F5 were verified firsthand** by the session that filed this stub — code opened, lines
read. **F2, F3, F4 are the reviewer's claims, relayed UNVERIFIED.** F6 was found by codex and
verified. Per the chunk lifecycle, a spec is a CLAIM: audit every one of these against the repo
before implementing, and treat the unverified three as candidates, not facts. Line numbers are
as of `cde5095` and will drift.

## Goal

Close the two confirmed defects (F1, F5), rule on the three relayed ones (F2, F3, F4), and
retire the stale spec path (F6).

## The findings

### F1 — the reaper's unlink is non-atomic, and a comment calls the race harmless (VERIFIED)

`src/reports/lifecycle.py` ~364-368:

```python
file_path = _REPORTS_DIR / f"{slug}.html"
if file_path.is_file():
    file_path.unlink()
```

Bare `unlink()`, no `missing_ok`, not atomic with the `is_file()` above it. A nearby comment
claims the double-unlink is "expected and harmless (`is_file()` makes the loser a no-op)".
That is false for the interleaving where the generator's self-delete lands between the check
and the unlink: the reaper raises `FileNotFoundError`, hits the broad `except`, increments
`files_failed`, and puts an operator-facing WARNING in front of someone for the exact case the
comment declares benign.

Note the shape — a prose claim in a comment that the code does not support. It is the same
defect class as the test docstring corrected in `c4de4f6`, one file over.

Fix direction: `unlink(missing_ok=True)`, mirroring the generator side, OR drop the no-op
claim. Do not do only the second.

### F5 — a rendered report can be stranded on disk permanently (VERIFIED)

`src/reports/generator.py` ~2780-2803. `claimed = _update_report_ready(...)` at ~2780;
`_update_run_record` + `_finalize_run_record` at ~2783-2789 sit INSIDE the try; the
`if not claimed:` self-delete recovery sits AFTER the `except`.

An exception raised in that 2783-2789 window returns via the `except` WITHOUT ever reaching the
self-delete. `_fail_report` then no-ops (the row is already `failed`, rowcount 0), so
`report_path` stays NULL — and `cleanup_expired_reports` selects `WHERE report_path IS NOT
NULL`, so nothing can ever reach the file again.

This is the permanent-orphan leak chunk 18 exists to close, still open on a narrow window.
The window is narrow because `_update_run_record` swallows `sqlite3.Error`; narrow is not
closed.

Fix direction (reviewer's, untested): move the `if not claimed` recovery inside the try,
immediately after the claim.

### F2 — lost-race run record has no reason (RELAYED, UNVERIFIED)

`src/reports/generator.py` ~2789 and ~2240: the lost-race `_finalize_run_record(..., "failed")`
passes no `error_stage`/`error_message`, so those columns write NULL. The run record then shows
`overall_status='failed'` beside completed per-stage statuses and populated render counts, with
a blank reason. `/admin/reports` reads the run record for failure detail, so the one case an
operator most needs explained is the one with no explanation stored.

Reviewer's suggested fix: pass `error_stage="render"` (`"no_games"` at the other site) plus the
lost-race message.

### F3 — a counter's label names a cause that did not occur (RELAYED, UNVERIFIED)

`src/reports/lifecycle.py` ~990 and ~1032: a `DELETE FROM teams` matching zero rows increments
`skipped_count`, but the summary renders that counter as `"%d skipped (delete raised)"`. A team
that vanished concurrently — nothing raised — sends the operator hunting for an exception that
never happened.

Reviewer's suggested fix: give the rowcount-0 case its own counter/message, or reword to
"skipped (not deleted)".

### F4 — the savepoint guard does not cover a raising RELEASE (RELAYED, UNVERIFIED)

`src/reports/lifecycle.py` ~986: `RELEASE {savepoint}` is inside the `try`. If it raises
`sqlite3.Error`, the handler still sees `savepoint_created is True` and issues `ROLLBACK TO` /
`RELEASE` against a name that may already be gone; that second failure raises out of
`cleanup_orphan_teams` with the transaction live — the uncontained-batch-rollback failure the
savepoint loop exists to prevent. The `savepoint_created` flag guards the SAVEPOINT-raised case
but not the RELEASE-raised one.

Reviewer's suggested fix: set `savepoint_created = False` immediately before `RELEASE`, or wrap
the recovery statements in their own try.

### F6 — the spec path is stale in `src/` (VERIFIED)

`src/reports/generator.py:338` and `src/reports/lifecycle.py:353` both cite
`.project/specs/2026-08-17-reaper-unlink-race.md`. That path is dead — the spec moved to
`.project/specs/done/2026-08-17-reaper-unlink-race.md`. The two occurrences in
`tests/test_report_generator.py` were fixed in `c4de4f6`; these two were deliberately left
alone, because editing `src/` in a test-only chunk would have invalidated the reviews just
completed on it.

## Files

- `src/reports/lifecycle.py` — F1, F3, F4, F6
- `src/reports/generator.py` — F2, F5, F6
- `tests/` — a regression test per confirmed defect (F1 and F5 at minimum; F2/F3/F4 as ruled)

Both files sit on CLAUDE.md's first named destructive seam (`bb report generate` is not
read-only). Treat every edit here as destructive-adjacent.

## Residuals discovered here (carried OUT of this chunk)

- **A live report can be reported to its caller as failed.** `_fail_report` is guarded on
  `WHERE status = 'generating'`, so a failure AFTER a successful `ready`/`no_games` claim leaves
  the row terminal with its `report_path` set and the page genuinely served, while the caller
  still receives `success=False`. `morning_run` then records `delivery_status='failed'` for a
  report an operator can open and share. The guard itself is correct and deliberate — reverting a
  `ready` row would be worse — so the question is what the RESULT should say, not what the row
  should do. Found by `/code-review` 2026-08-22; pre-existing, and narrowed (not introduced) by
  this chunk. Also on the board.

- **The leak is narrowed, not eliminated: a filesystem error still strands a file.** When
  `unlink` raises `OSError` (read-only mount, EPERM, EBUSY) in either `_reaper_lost_the_race` or
  `_discard_unreachable_render`, the file remains at `reports/{slug}.html` with the row at
  `('failed', report_path NULL)` — beyond `cleanup_expired_reports` and beyond the reaper, with
  no counter and no retry. That is the same permanent-strand condition this chunk exists to
  remove, narrowed to the case where the OS refuses the delete. Deliberate (the alternative
  destroys the operator-facing reason, and no code can delete what the OS won't), pinned by two
  tests, and named here by `/code-review` 2026-08-22 rather than left implicit. A future closer
  would need a swept stray-file surface — a reconciliation between `data/reports/` and the
  `reports` table — not another try/except.

## Out of scope

- Any change to the reaper's claim/rowcount arbitration itself — that is `846e9eb`'s and it
  reviewed clean.
- The Ordering-1/Ordering-2 test coverage — landed in `c4de4f6`.
- The push posture and the runs-instrument chunk — both queued behind this one by the same
  ruling.

## Verification

- RED-first per defect: show each new regression test failing before the fix, and classify each
  at step 7 (behavior-failure / symbol-absence / never-shown-failing).
- F5 specifically needs a test that raises inside the claim→check window and asserts the file is
  gone. An absence assertion here needs proof the mechanism completed cleanly — the Ordering-2
  chunk had 3 of 10 tests pass against deliberately broken code on exactly this shape, because a
  swallowed exception satisfied every absence they asserted.
- Full suite green from baseline 4590 (`c4de4f6`). Never trust a piped pytest RC: redirect to a
  file, capture `$?` separately, read the file for the RC and the pass/fail line.
- `/code-review` and codex both required — this chunk touches `src/`.
- ⚠ Scope the review to THIS chunk's base, not `origin/main...HEAD`, unless the push has landed
  by then. That mis-scoping is what produced this stub.

## Progress log

- 2026-08-22 — Stub filed from the Ordering-2 chunk's review round. F1, F5, F6 verified
  firsthand; F2, F3, F4 relayed unverified. Operator ruled fix-first, ahead of runs-instrument
  and the push. Nothing implemented.
- 2026-08-22 — EXECUTE. Audited all six against the repo BEFORE implementing: **all six
  confirmed**, including the three relayed unverified ones. Line numbers had not drifted.

  **One spec claim corrected.** F2 says the lost race is the case with "no explanation stored".
  The reaper DOES store one, on the `reports` row (`lifecycle.py`'s
  `UPDATE reports SET status = 'failed', error_message = ?`), and `admin/reports.html:85`
  displays it. F2 is a second, missing explanation on the RUN record (whose stage-error block
  at `admin/reports.html:121-123` renders only when `run_error_message` is non-NULL), not the
  absence of any. Fixed as such.

  **One finding the spec does not carry: a SECOND permanent-orphan window, needing no race.**
  Any exception between the render's `write_text` and a committed 'ready' claim — a failing
  `get_connection()` or a failing claim UPDATE, i.e. a locked/unavailable DB — reaches the
  `except`, where `_fail_report` moves the row to 'failed' with `report_path` still NULL. That
  is beyond `cleanup_expired_reports` (`report_path IS NOT NULL`) and beyond the reaper
  (`status = 'generating'`), so the rendered file is stranded exactly as in F5 — but with no
  reaper involved, so F5's fix direction does not reach it. Operator ruled 2026-08-22 to close
  both windows in this chunk. Closed by `_discard_unreachable_render`, which RE-READS the row
  and deletes only when nothing points at the file.

  **Landed.** F1: the `is_file()` pre-check is gone (no ordering of two statements makes them
  atomic); `FileNotFoundError` is the benign case and moves NEITHER counter; the false comment is
  replaced. `missing_ok=True` was deliberately NOT used — it would count a never-removed file in
  `files_removed`, which is F3's defect one branch over. F2: both claim sites finalize with
  `error_stage` + `_LOST_RACE_RUN_ERROR` (`"render"` / `"no_games"`). F3: rowcount-0 gets its own
  `vanished_count` and its own "already gone (delete matched no row)" wording. F4: the recovery
  pair runs under its own `try`, containing-and-warning instead of escaping with the transaction
  live. F5: the recovery moved INSIDE the try, directly under the claim, with the render counts
  written above it. F6: both `src/` citations now point at `done/`.

  **Verification.** Baseline `4590 passed, RC=0` at `c4de4f6`; FINAL `4618 passed, RC=0` — +28,
  matching the 28 tests added, RC captured unpiped from a redirected file both times. (Two
  intermediate figures appear in the log entries above and are superseded: 4605/+15, 4606/+16,
  4608/+18, 4612/+22, 4617/+27 — each superseded by the next review round's additions.)

  RED classification of the 28, which splits 20/8 and does NOT read "all 28 shown failing":
  **20 shown RED, all behavior-failures** — F1 2, F2 2, F3 2, F4 6, leak sites 6, message-honesty 2; none was a
  symbol-absence, and the F4 REDs reproduced the escape as a traceback out of `lifecycle.py`.
  **6 never-shown-failing, and that is their purpose** — they are positive controls asserting
  behavior that is already correct and must SURVIVE the fix, so a RED for them would mean the
  control itself was broken: a real unlink failure must still warn (F1), a genuinely raised delete
  must still say "delete raised" (F3), each leak window's row must really be in the state that
  makes its file unreachable (2, else the absence assertions prove nothing), a 'ready' report must
  never be discarded, and a CLAIMED no-games page must survive an unrelated later failure (the two
  guard rails on the discard, which is the one new destructive act in this chunk).

  All 9 lifecycle tests were re-RED'd against stashed original source under the mutation protocol
  — cache cleared in both directions, restore verified by diff. The three leak-window REDs were
  each produced by removing the specific fix under test, one at a time, restore verified by diff.
- 2026-08-22 — Codex review (`uncommitted` mode = this chunk's range, since the base is HEAD).
  Three findings, all read in full; two folded, one is timing.

  **P2 — the F2 render-site assertion was too weak.** It checked
  `(error_stage, error_message) != (None, None)`, which a regression to the WRONG stage would
  pass while showing an operator the wrong half of the pipeline. Now pinned to
  `error_stage == "render"`, matching the no-games test's shape.

  **P2 — the F4 test proved the weaker half.** One seeded team proves "the exception no longer
  escapes" but not the batch guarantee the code's own comment claims ("kept the rest of the
  batch"); a transaction left poisoned by the failed recovery would pass it. Added a sibling-team
  test asserting the later team is deleted AND committed (read on a fresh connection).

  ⚠ **The first attempt at that fix silently disarmed the two tests it sat beside, and only a
  re-RED caught it.** Making the double fail the FIRST `RELEASE` only means the handler's own
  `RELEASE` succeeds, so nothing escapes and all three tests passed against STASHED ORIGINAL
  SOURCE — a fix for a review finding that turned two live regression tests into vacuous ones.
  Resolved with two doubles: the always-on one keeps the escape tests live, and a second scoped by
  savepoint NAME fails one team's `RELEASE` throughout (so its escape is still reachable) while
  leaving the sibling's untouched. All three verified RED against original source afterwards.
  This is the narrowing-fix-invalidates-its-neighbours shape, one level down: the invalidated
  thing was not an acceptance count but the discriminating power of adjacent tests.

  **P5 — spec `Status` still `STUB` and `README.md` still lists this as next.** Not foldable
  before step 7 by construction (step 7 flips Status so it rides the commit); done there, not
  disputed.
- 2026-08-22 — `/code-review` (operator-typed). Five findings, all read in full and all verified
  firsthand before triage; four folded, one routed out. Both this reviewer and codex reviewed the
  SAME diff and overlapped on nothing — and the highest-severity finding of the chunk came from
  this pass, on the fix itself.

  **A THIRD site of the same leak, which the render fix structurally could not reach.** The
  no-games branch writes `data/reports/{slug}.html` too, and its failures land in
  `_run_pipeline`'s handler — a DIFFERENT handler, which calls `_fail_report` and cannot see
  `file_path`. So a raising claim there stranded the page exactly as the render branch did.
  Closed by attaching the discard where that file is created and re-raising for the pipeline
  handler to do the row work. Verified RED by removing the discard: exactly one test failed, the
  control passed. **Neither codex nor my own audit found this; the second reviewer found it on
  the fix.** Two windows were named at the start of the chunk and there were three.

  **My change silently made four NEIGHBOURING tests vacuous, for the second time this chunk.**
  Moving the recovery inside the try turned a would-ESCAPE `FileNotFoundError` into a
  caught-and-degraded one, so `TestReadyClaimWhenTheReaperAlsoUnlinkedTheFileFirst` — a
  PRE-EXISTING class, untouched by my diff — stopped discriminating. Re-measured under the
  bare-`unlink()` mutation: **1 of its 5 tests failed where its docstring claimed all would**,
  while its no-games sibling (which already carried a completed-cleanly precondition) failed 5 of
  5. Fixed by giving it the same precondition — guarding on `"Post-pipeline error:"`, NOT the
  sibling's `"Pipeline error:"`, since a copied literal would never fire. Its docstring's two
  false claims are corrected in place with the correction recorded.

  Note the pattern, which bit twice in one chunk from opposite directions: a fix invalidated a
  test I WROTE (the one-shot double), and a fix invalidated tests I DID NOT TOUCH and whose file
  my diff barely entered. The second is the harder one — nothing in the diff pointed at it, and
  the suite was green throughout both.

  **Also folded:** a vanished `reports` row now DISCARDS the file rather than keeping it (a row
  deleted mid-generation is the strongest evidence of unreachability — the admin delete unlinks
  by `report_path`, NULL in exactly that window, so nothing else ever would); and the
  `reap_stale_generating_reports` docstring's surviving `.is_file()` claim, one function
  docstring above the fix that removed it, is retired.

  **Routed OUT, not fixed — see Residuals below.** The finding about `_fail_report` no-opping
  after a successful claim is pre-existing and deliberate (pinned by
  `test_a_failed_claim_does_not_revert_an_already_ready_row`), and this chunk NARROWED rather than
  widened it by moving the render-count write above the claim.
- 2026-08-22 — SECOND review round, on the fixes themselves (the first codex pass predated the
  `/code-review` fixes, so it had never seen the no-games discard — a destructive-seam change
  reviewed by nobody until this round). Codex 2 findings, `/code-review` 3. Four were new; one had
  already been closed by a codex fix applied before that reviewer read the tree.

  **P1 (codex, with a reproducer) — the savepoint fix misclassified a real outcome.** A `RELEASE`
  that raises AFTER SQLite executed it leaves the savepoint GONE and the DELETE STANDING; the
  `ROLLBACK TO` then fails against a name that no longer exists. The handler counted every
  `RELEASE` failure as "kept", so a team that WAS deleted was reported skipped and `deleted_count`
  under-reported. Codex reproduced it: `cleanup_orphan_teams` returned 1 while both teams were
  gone. **This is F3's own defect class — a counter naming an outcome that did not happen —
  reintroduced by F4's fix, from the opposite direction.** Fixed by RE-READING the row instead of
  inferring the outcome from which exception fired; the unknown-on-read case counts the
  conservative side and says so. (`/code-review`'s finding 3 is this same defect via a failing
  `ROLLBACK TO`; already closed by this fix when that review landed.)

  **`/code-review` finding 1 — a FOURTH site of the chunk's own leak.** The first no-games fix
  wrapped the claim and the orphan sweep but left the `if not claimed:` recovery block BELOW the
  guard, so a raise there still escaped to `_run_pipeline`'s handler and stranded the page at
  `('failed', NULL)`. Reproduced by the reviewer, then by a RED test here. Fixed by pulling the
  block inside the guard.

  **`/code-review` finding 2 — my restructuring buried the explanation it added.** Moving the
  recovery inside the try made `_reaper_lost_the_race`'s own `unlink` catchable, so an `OSError`
  fell to the handler, which rewrote the run record with `Post-pipeline error: ...` ON TOP of
  `_LOST_RACE_RUN_ERROR`. The operator got a filesystem error where the whole point was to say
  "the reaper claimed this row first". Fixed by containing the unlink inside
  `_reaper_lost_the_race` — a stray file is the lesser harm and is already the reaper's tolerated
  failure mode. The success log line was split from the failure one in the same edit, because
  "deleted its own file" would otherwise be printed when nothing was deleted.

  **Codex P2** — the vanished-row discard branch, which came from review feedback, was itself
  untested. Pinned.

  Suite 4590 → 4612 (+22). **Every review pass in this chunk found something, and the last two
  found defects INTRODUCED BY FIXES to the previous pass.** Three of the four new findings above
  are regressions from my own review fixes, not from the original six. That is the chunk's real
  lesson: on a destructive seam, a fix is a change that owes a review, and "the reviewer already
  passed this file" is about a file that no longer exists.
- 2026-08-22 — THIRD review round (operator-ruled after being shown that pattern), plus
  `/security-review`. Four more findings, all again downstream of the previous round's fixes.
  **Severity is decaying — round 3's were data-loss, round 4's are all honesty-of-claim** — but
  the rate is not: no pass has yet come back clean.

  **Declined, with the trade pinned by tests rather than argued in prose:** codex read the
  contained `OSError` in `_reaper_lost_the_race` as reintroducing the orphan leak and asked for it
  to propagate so `_discard_unreachable_render` gets a turn. That helper's only destructive act is
  the SAME `unlink` that just failed — it re-reads the row and unlinks — so on a read-only mount
  it fails identically and the file remains under either design. **File state is unchanged by the
  choice; what propagating changes is the run record**, which the handler rewrites with
  `Post-pipeline error: ...`, destroying the lost-race reason the previous round restored. Two
  tests now pin all three facts (file remains, row terminal, stray-file warning emitted) so the
  next reader knows what reversing it costs.

  **Folded — three sites of ONE defect, and I had just written two of them.**
  `exists()`-then-`unlink(missing_ok=True)` is the identical non-atomic check-then-act this chunk
  removed from the reaper in F1, and I reintroduced it while fixing the "deleted its own file"
  message. The reaper unlinks this exact path by slug concurrently, so the check can pass and its
  unlink land first, leaving us claiming a deletion we did not perform. All three sites now let
  `unlink()` itself decide (`FileNotFoundError` → its own branch), and `_reaper_lost_the_race`
  reports three distinct outcomes: deleted / already gone / could not delete. Two PRE-EXISTING
  tests were asserting the false message in the already-gone case and were corrected — they were
  locking the defect in.

  **Folded — absent is not deleted-by-us.** A team that vanished concurrently AND whose `RELEASE`
  then failed after executing was counted as deleted: the re-read finds no row, but the row's
  absence is somebody else's doing. Only the DELETE's own `rowcount`, captured before the
  `RELEASE`, separates them. This is the third distinct way this one counter has been wrong in
  this chunk.

  ⚠ **My first double for that test passed against deliberately broken code.** It modelled the
  concurrent vanish with a second connection, which cannot delete while phases 1–2 hold SQLite's
  write lock — so it blocked for the busy timeout, raised `database is locked` INSIDE our DELETE,
  and produced a "skipped" outcome that satisfied the assertion for entirely the wrong reason.
  The only tell was a ~5s runtime. Replaced with a double that reproduces the observed STATE (row
  absent, rowcount 0) directly, and re-verified GREEN-with-fix / RED-without. **Third vacuous-test
  incident of this chunk**, and the second where the suite was green throughout.

  `/security-review`: no HIGH or MEDIUM findings. The new deletion capability was checked for path
  traversal (slug is `secrets.token_urlsafe(12)`, never user input, no separators), for deleting a
  served report (guarded by the row re-read; DB error or unknown state declines to delete), and
  for injection (all new queries parameterized; the one interpolated identifier passes through
  `int()`).

  Suite 4590 → 4617 (+27).
- 2026-08-22 — FOURTH review round. **Codex: ONE finding, Priority 6 — the first pass with no
  correctness defect.** `/code-review`: three, all real, all the same honesty class.

  Folded: (1) the `delete_rowcount is None` state — the DELETE itself raising — fell to the
  deleted branch, so a row absent for reasons unknown was counted as our deletion; the gate is now
  `== 1` (the only evidence our delete removed it) rather than `!= 0`. **Third distinct way this
  one counter has been wrong, and the fourth time this chunk has miscounted a destructive act.**
  (2) `_discard_unreachable_render` caught only `sqlite3.Error` while its docstring promised
  best-effort; `get_connection()` can fail otherwise, and since BOTH callers invoke it from inside
  an exception handler, an escape would have replaced the original failure — on the no-games path,
  destroying the real exception before its `raise`. Widened to `except Exception`. (3) The
  run-record reason claimed "this run's own output was discarded", written BEFORE a self-delete
  that has an outcome leaving the file in place; it now says "is not served", which is true in all
  three. Codex's P6 was the same overclaim in `_reaper_lost_the_race`'s docstring ("the file is
  gone"), which now documents all three outcomes and warns callers not to rely on absence.

  ⚠ **FOURTH vacuous test of this chunk, same session, caught the same way.** The double for (1)
  modelled the DELETE raising but not the recovery — so `ROLLBACK TO` succeeded, the row came
  BACK, and the run ended in the `skipped` branch without ever reaching the gate under test. It
  passed against the deliberately broken gate. Fixed by failing `ROLLBACK TO` too, then
  re-verified GREEN-with-fix / RED-without. Every one of the four was caught by re-running against
  broken code and by nothing else; the suite was green through all four.

  Suite 4590 → 4618 (+28).
- 2026-08-22 — Review round: codex run on `uncommitted` (this chunk's base is HEAD, so that mode
  IS the chunk range, avoiding the `origin/main...HEAD` mis-scoping that produced this stub).
  `/code-review` is operator-typed and was requested at the gate.
