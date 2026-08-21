<!-- NO REAL NAMES OR IDENTIFIERS — no person's name, ever; for teams, orgs, ids and UUIDs use the PII-Safe Placeholder Taxonomy in `.claude/rules/api-docs.md`. -->

# The reaper can still delete a finished report's served HTML

**Date**: 2026-08-17, spec written 2026-08-21 · **Status**: `READY`
**Source**: `/code-review` of commit `2217092` (the orphan-cleanup FK rollback chunk), run
after that chunk was approved and committed. Stubbed 2026-08-17; specced 2026-08-21 in its
own chunk per operator ruling.

## Why this is owed

`2217092` fixed the reaper's own UPDATE (`lifecycle.py:303`) to gate on rowcount when the
reaper LOSES the race against a finishing generation — verified directly this session
(`git show 2217092 -- src/reports/generator.py` returns nothing; the commit touched only
`lifecycle.py`), so "closed one of two interleavings" is confirmed, not relayed.

The remaining interleaving: when the reaper WINS the race (claims the row, flips it to
`failed`), the generator's own completion write is unconditional and resurrects the row.

Precise claim about `2217092` (codex flagged the looser wording): `git show --stat 2217092`
touches `.project/specs/` files, `docs/admin/operations.md`, `src/api/routes/reports_admin.py`,
and two test files, in addition to `lifecycle.py` — it is NOT a `lifecycle.py`-only commit.
The load-bearing fact is narrower and still holds: `git show 2217092 -- src/reports/generator.py`
returns no diff, so `generator.py` itself was untouched, which is what makes the interleaving
below still open.

- `generator.py:2703` `file_path.write_text(html, ...)` — file lands on disk first.
- `generator.py:2707` → `_update_report_ready` → `generator.py:272-275`:
  `UPDATE reports SET status='ready', report_path=? WHERE id=?` — **no status guard**.

(The stub's original citations — `:2702`/`:2705` — are off by one from the actuals above;
noting the drift rather than silently correcting it away.)

```
generation writes data/reports/{slug}.html
  → reaper's UPDATE ... WHERE status='generating' claims the row (rowcount 1 → 'failed')
  → generation commits status='ready', report_path set
  → reaper unlinks the file
```

End state: `status='ready'`, `report_path` set, **file gone**, reaper reporting
`reaped=1, files_removed=1, errors=0`. A resurrected row also keeps the reaper's
`Reaped: generation did not complete` `error_message`, because `_update_report_ready` never
clears it.

**Bound, stated honestly.** Needs a generation past the 1-hour staleness threshold that then
finishes, AND the reap must land between the file write and the `ready` commit —
milliseconds. Not reproduced live; the mechanism is read off the two orderings (constructed
below). The regenerate is a bulk CLI workload, which is when long generations are most
likely.

## Second, previously-unnoticed site with the identical shape

A mechanical sweep of every `reports`-row writer (`grep -rn "UPDATE reports SET" src/`, all
6 hits — plain `grep -n ... src/` errors with `src/: Is a directory`; the `-r` is required
and every re-run of this sweep MUST use it) — done specifically because the first fix on
this seam closed one writer's guard without anyone checking whether a sibling writer had
one:

| Site | Guarded? |
|---|---|
| `lifecycle.py:303` (reaper claim) | Yes — `AND status='generating'`, rowcount checked (2217092) |
| `lifecycle.py:496` (`cleanup_expired_reports`, nulls `report_path`) | N/A — operates on already-expired rows only, disjoint from this race |
| `generator.py:273` `_update_report_ready` | **No** — the original finding |
| `generator.py:283` `_update_report_failed` | **No** — and understated in an earlier draft of this spec. Reachable from `_fail_report` (`:2743-2749`), called from the broad `except Exception` at `:2718-2725` that wraps the SAME try block as `_update_report_ready`. If `_update_report_ready` commits `ready` at `:2707` and a LATER statement in the same block (`_update_run_record` `:2710`, `_finalize_run_record` `:2716`) then raises, the except handler calls `_fail_report` unconditionally and flips an already-correctly-`ready`, file-served report back to `failed` — `report_path` is left set (this UPDATE doesn't touch it), so the row ends inconsistent (`status='failed'` pointing at a live, valid file) rather than losing the file. Folded into scope below via the same guard, not left as a residual. |
| `generator.py:2070` (title update) | N/A — unrelated column, no status/report_path interaction |
| `generator.py:2162` **no-games terminal path** | **No** — identical shape: writes `data/reports/{slug}.html` at `:2156-2159`, then unconditional `UPDATE ... status='no_games', report_path=?` at `:2161-2164`. |

Any reviewer of this spec should re-run the same grep and confirm the table still matches —
it is the verification step for "did we get every writer," not a one-time inventory.

## A comment whose premise the fix falsifies

`lifecycle.py:343-347`, directly justifying the reaper's own unlink:

> "Unlink any orphan partial HTML (written before the 'ready' update that would have set
> report_path — so report_path is still NULL and cleanup_expired_reports can never reap
> it)."

This assumes the file being unlinked is always a *partial* file from a truly-crashed
generation. Under the race this chunk fixes, the file can be the **complete, finished**
report — written by a live generation that simply hasn't (and, after this fix, never will)
committed `ready`. The comment's premise is false in exactly the case this spec exists to
handle; it must be corrected in the same commit, or the fix ships under prose asserting its
own defect cannot occur.

## Two smaller findings, same file, riding the same pass

- **The SAVEPOINT statement sits OUTSIDE its `try`** (`lifecycle.py:971-972`, inside
  `cleanup_orphan_teams`'s Phase 3 delete loop). If it raises, the exception escapes
  `cleanup_orphan_teams`, `generator.py::_cleanup_orphans` swallows it, and the connection
  closes with the transaction live — the whole-batch rollback the loop exists to prevent.
  Fix: move `SAVEPOINT {savepoint}` to be the *first* statement inside the `try`. This is
  NOT free — the `except` at `:993` runs `ROLLBACK TO`/`RELEASE`, which themselves need the
  savepoint to have been created successfully; if the SAVEPOINT statement itself is what
  raised, those cleanup statements would raise a second time on a savepoint that never
  existed. Track whether the SAVEPOINT succeeded (a simple flag) and skip
  `ROLLBACK TO`/`RELEASE` when it didn't, re-raising or logging instead so the loop still
  advances past this team rather than aborting the batch.
- **`deleted_count += 1` without checking the DELETE's rowcount** (`lifecycle.py:973-975`),
  while the comment above it (`:964-966`) claims the count is taken "where the outcome
  actually HAPPENS." Fix: check `cursor.rowcount == 1` before incrementing `deleted_count`;
  a 0-row DELETE routes through the existing `skipped_count` path instead. Confirmed mostly
  unreachable under the pass's `BEGIN IMMEDIATE`, but it contradicts the rowcount-arbiter
  pattern this same commit (2217092) established for the reaper — fixing it removes that
  contradiction, not a live bug this session has evidence of firing.

## Fix shape

One small shared helper, used by both unguarded sites (avoids the two-copies drift this
repo's `canonical-seams` rule warns about):

```python
def _claim_report_completion(
    conn: sqlite3.Connection,
    report_id: int,
    *,
    status: str,
    report_path: str | None = None,
    error_message: str | None = None,
) -> bool:
    """Atomically transition a 'generating' report to a terminal status.

    ``report_path`` and ``error_message`` are OPTIONAL and independently
    preserve the existing per-column write behavior of the two functions this
    helper replaces: passing ``None`` for either leaves that column UNCHANGED
    (via ``COALESCE(?, column)``), it does NOT null it out.  This matters
    concretely: ``_fail_report`` fires from crawl/load-stage failures
    (``generator.py:1970``, ``:2033``) where no HTML has been rendered and no
    ``report_path`` value exists in scope -- the caller passes
    ``report_path=None`` there, exactly mirroring today's
    ``_update_report_failed``, which never touches that column either.

    Returns False (no-op) if the row already left 'generating' -- e.g. the
    reaper claimed it first.  Callers MUST treat False as "the reaper won":
    a ready/no_games caller deletes the file it just wrote and logs a
    WARNING, never assuming the reaper's own unlink already covered it (it
    may run before the file exists -- see the ordering-1 counterexample
    below).  A failed-path caller (`_fail_report`) treats False as "leave the
    row alone" -- it is either already `failed` (harmless no-op) or already
    `ready` (must not be reverted).
    """
    cursor = conn.execute(
        "UPDATE reports SET status = ?, "
        "report_path = COALESCE(?, report_path), "
        "error_message = COALESCE(?, error_message) "
        "WHERE id = ? AND status = 'generating'",
        (status, report_path, error_message, report_id),
    )
    conn.commit()
    return cursor.rowcount == 1
```

Both `_update_report_ready` (`generator.py:269-276`) and the no-games branch
(`generator.py:2160-2165`) route through it. On `False`: delete the just-written file
(best-effort, matching the reaper's own `is_file()` guard style), log a WARNING naming the
report id and slug, and do NOT proceed to write `report_path` or claim success.

**Also fold in `_update_report_failed` (`generator.py:279-286`, reached via `_fail_report`
at `:2743-2749`, which every crawl/load/render failure path calls — `generator.py:1970`,
`:2033`, `:2724`, among others)**, guarded the same way but in the opposite direction — it
must NOT flip an already-`ready` row back to `failed` when a later, non-essential step in
the same try block raises after `_update_report_ready` already committed. Same shared
helper, called with `status="failed"`, `report_path=None` (crawl/load failures never reach
render, so no path value exists in scope — `report_path`'s `COALESCE`-preserving default
above is what makes this call legal) and `error_message=msg`. A `False` return means the row
already left `generating` (either the reaper claimed it, in which case it is already
`failed` and this is a harmless no-op, or the render path already committed `ready`, in
which case the row must be left alone). This closes the case codex's review surfaced — the
earlier "only `error_message` could be clobbered" framing undersold the actual risk (see the
writer table above). A second review pass (operator-run `/code-review` on this spec) then
caught that the helper's ORIGINAL signature made `report_path` a required argument, which
these crawl/load-stage `_fail_report` call sites cannot satisfy — fixed by making both
`report_path` and `error_message` independently optional via `COALESCE`, per the helper's
docstring above.

### Counterexamples, both orderings, constructed against the FIXED code

Two-connection construction (reaper connection R, generation connection G), mirroring the
existing `_RacingReadyConnection` pattern in `tests/test_report_generator.py`
(`class TestReaperWhenALateGenerationFinishesFirst`). Both become real pytest tests, not
prose assertions.

**Ordering 1 — reaper's unlink runs before the file exists.** R: SELECT sees `generating` →
UPDATE claims (rowcount 1, row now `failed`) → R's per-row unlink runs immediately,
`file_path.is_file()` is **False** (G hasn't written yet) → R skips, `files_removed`
unaffected by this row. G: writes the file → calls `_claim_report_completion` → rowcount 0
(row already `failed`) → **without this fix's self-delete, the file becomes a permanent
orphan** (`report_path` stays NULL forever, so `cleanup_expired_reports`'s
`WHERE report_path IS NOT NULL` selection can never reach it). This ordering is the argument
for the self-delete-on-no-op behavior — it is load-bearing, not belt-and-suspenders: the
reaper's own unlink cannot cover a file that does not exist yet at the moment it runs.

**Ordering 2 — write before unlink (the original stub's shape).** G: writes the file → R:
claims the row (rowcount 1) → R's unlink finds the file, removes it, `files_removed += 1` →
G: `_claim_report_completion` returns rowcount 0 → G's self-delete finds nothing
(`is_file()` False), no-ops cleanly, still logs the WARNING. End state identical to
Ordering 1: row `failed`, no file on disk, one WARNING logged, `files_removed` credited to
whichever side actually removed it (never double-counted, since only one side ever finds
the file present).

Both orderings converge on the same safe, auditable end state under the fix; neither did
before it.

## Scope decision

`_finalize_run_record(report_id, "completed")` (`generator.py:2716`) runs unconditionally
right after `_update_report_ready` today, so on the no-op branch the run record would say
"completed" while `reports.status` says `failed` — a new, narrower inconsistency the guard
itself introduces if left unaddressed. **In scope**: make the finalize status-aware —
`"completed"` when `_claim_report_completion` returns `True`, `"failed"` (or an equivalent
existing status constant from `run_status.py`) when it returns `False`. Same shape applies
to the no-games branch's `_finalize_run_record(self.report_id, "completed")` call
(`generator.py:2174`).

## Files

This chunk touches `bb report generate`'s pipeline (`generator.py`) and its orphan-cleanup
pass (`cleanup_orphan_teams` in `lifecycle.py`) — both live on CLAUDE.md's first named
destructive seam ("`bb report generate` is NOT read-only ... orphan reclamation").

- `src/reports/generator.py` — add `_claim_report_completion`; wire `_update_report_ready`,
  the no-games branch (`:2160-2165`), and `_update_report_failed`/`_fail_report`
  (`:279-286`, `:2743-2749`) through it; self-delete + WARNING log on a `ready`/`no_games`
  no-op; status-aware `_finalize_run_record` calls at both completion sites.
- `src/reports/lifecycle.py` — correct the orphan-partial-HTML comment at `:343-347`;
  move `SAVEPOINT` inside its `try` (`:970-975`) with the never-created-savepoint guard;
  rowcount-checked `deleted_count` (`:973-975`).
- `tests/test_report_generator.py` — new test class(es) for all three completion sites
  (both orderings, two-connection construction per `_RacingReadyConnection`) plus the
  self-delete/WARNING no-op behavior; sibling coverage for the savepoint-inside-try and
  `deleted_count` rowcount fixes in `TestCleanupOrphanTeams` / `TestCleanupOrphanTeamsFkSafety`
  (`tests/test_report_generator.py:3220` / `:3449` — confirmed as the current coverage;
  `tests/test_orphan_reclamation.py` and `tests/test_report_negative_paths.py` also import
  `cleanup_orphan_teams` and must be checked per Test Scope Discovery in
  `.claude/rules/testing.md` before this chunk is called done).

## Out of scope

- Any live reproduction of the race under real timing (the bound above is stated honestly
  as read-off-the-orderings, not observed).

## Verification

Run before AND after (diagnostic, per CLAUDE.md's north-star instrument, not a gate):
`bb report reconcile-scoreboard`.

- `python -m pytest tests/test_report_generator.py -k "Reap or Ready or NoGames or Race or Completion" > /tmp/race.txt 2>&1; echo RC=$?` — read the file for RC and the pass/fail line, never trust a piped exit code. (`pytest --collect-only` with this `-k` currently selects 15 tests, all reaper/ready/no-games; this command covers the generator-side fix only.)
- `python -m pytest tests/test_report_generator.py::TestCleanupOrphanTeams tests/test_report_generator.py::TestCleanupOrphanTeamsFkSafety > /tmp/orphan.txt 2>&1; echo RC=$?` — the targeted check for the savepoint-inside-try and `deleted_count` fixes; the `-k` command above does not reach these tests.
- Full suite (this chunk touches `src/`, full suite required per testing.md's ratchet rule):
  `python -m pytest > /tmp/full.txt 2>&1; echo RC=$?`.
- Mutation check on the new guard, per the full mutation protocol in `.claude/rules/testing.md`
  (all legs required, not just the mutate-and-observe step): run a no-mutation control first;
  clear `__pycache__` before the mutation; state which tests are expected to fail BEFORE
  mutating (`AND status = 'generating'` removed from `_claim_report_completion`); apply the
  mutation and confirm the mutated string is actually present in the loaded module; run and
  confirm the expected tests fail; clear `__pycache__` again before restoring; restore and
  confirm green.
- Re-run `grep -rn "UPDATE reports SET" src/` at review time and confirm the writer table in
  this spec still matches every hit.

## Review gates (this chunk)

Touches `src/`, the serving path, and `bb report generate`'s destructive orphan-cleanup pass
(named per CLAUDE.md's two-destructive-seams paragraph). `/code-review` (fork) is
REQUIRED; `codex-spec-review.sh` is REQUIRED before this spec is presented for commit
approval; `/security-review` is assumed yes (delete path over served artifacts). Both
`/code-review` and `/security-review` are operator-typed — a session cannot invoke either;
stop and ask at that step.

## Progress log

- **2026-08-17** — Stubbed from a post-commit `/code-review`. All three original findings
  verified against the files. Operator ruled: its own chunk, next, before the runs
  instrument. No code.
- **2026-08-21** — Specced in a fresh session. Re-audited all three stub findings directly
  against current code (confirmed, noting a one-line citation drift vs. the stub). Verified
  `2217092`'s "closed one of two interleavings" claim by reading the commit itself, not
  relaying it. Ran the full-writer sweep (`grep -n "UPDATE reports SET" src/`) and found a
  second unguarded site (`generator.py:2162`, no-games terminal path) the stub had not
  named. Found and corrected-in-scope a comment (`lifecycle.py:343-347`) whose premise the
  fix falsifies. Constructed both race orderings against the proposed fix, including the
  ordering that establishes the self-delete-on-no-op behavior is load-bearing rather than
  redundant with the reaper's own unlink. Operator chose (AskUserQuestion, this session):
  on a guard no-op, the generator deletes its own file and logs a warning, rather than
  trusting the reaper's unlink alone. Ran `./scripts/codex-spec-review.sh` (RESULT_FILE
  `/tmp/codex-spec-review.1fdiFL`): 1 P1 + 3 P2 + 1 P3, all folded in — the sweep command
  needed `-r` (`grep: src/: Is a directory` without it); the `2217092`-touched-only-lifecycle
  claim was loosened to what's actually load-bearing (untouched `generator.py`);
  `_update_report_failed` was understated as low-risk and is now folded into the fix
  (guards against the exception handler flipping an already-`ready` row back to `failed`);
  verification gained a targeted `cleanup_orphan_teams` test command and the full mutation
  protocol's missing legs; the destructive seam (`bb report generate`) is now named in Files
  and Review gates. Presented for commit approval; the operator ran `/code-review` on the
  spec itself, which found the shared helper's ORIGINAL signature made `report_path` a
  required argument that `_fail_report`'s crawl/load-stage call sites (`generator.py:1970`,
  `:2033`) cannot supply (no HTML rendered yet in those paths). Fixed: `report_path` and
  `error_message` are now independently optional on `_claim_report_completion`, each
  preserved via `COALESCE(?, column)` when omitted — matching today's per-function
  column-touch behavior exactly (`_update_report_ready` never touches `error_message`;
  `_update_report_failed` never touches `report_path`). No code — this commit is spec-only.
  Status: `READY`; re-presenting for commit approval.
