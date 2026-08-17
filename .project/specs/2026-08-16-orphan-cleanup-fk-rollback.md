<!-- NO REAL NAMES OR IDENTIFIERS — no person's name, ever; teams by id/role only. -->

# Orphan cleanup FK failure rolls back the whole phase; and the reaper's prose outlived its reorder

**Date**: 2026-08-16 (rewritten 2026-08-17) · **Status**: `READY`
**Source**: `.project/specs/README.md` NEXT. Item 1 from the trainer's sweep of the 71-team restore
run; item 2 folded in by operator ruling 2026-08-17 from a `/code-review` of `origin/main...HEAD`.

## Goal

After this chunk, one undeletable orphan team can no longer discard an entire batch's cleanup, and
the two seams that answer "is this team safe to delete?" give the same answer. Separately, the
stuck-`generating` reaper stops describing an ordering it no longer uses, stops counting one row as
both reaped and errored, and stops telling the operator the generate page is wedged when it is not.

Both items live in `src/reports/lifecycle.py` and both are "a delete path whose prose contradicts
its code". They are bundled by operator ruling so one set of review gates covers both, not because
they share a cause.

## Files

- `src/reports/lifecycle.py` — `cleanup_orphan_teams` (item 1); the reaper docstring, the
  `ReaperResult` contract, and the per-row error scoping (item 2)
- `src/api/routes/reports_admin.py` — the false wedge ERROR at `_a_generation_is_in_flight` (item 2)
- `docs/admin/operations.md` — one operator-facing sentence carrying a rationale the code already
  refutes (item 2, site 4)
- `tests/test_report_generator.py` — new tests for both items, plus one stale test updated
- `.project/specs/README.md` — board update at handoff (step 9)

## Item 1 — the FK rollback

### The defect, two layers

1. **Predicate mismatch.** `cleanup_orphan_teams` computes deletability ONLY from
   `games.home_team_id`/`away_team_id` (`lifecycle.py:820-827`). Orphan reclamation answers the same
   question over `games` PLUS six game-child tables (`_TEAM_STAT_EXISTS`, `lifecycle.py:1134`). A
   team with zero games but a surviving `player_game_batting` row passes cleanup's filter, then
   `DELETE FROM teams` raises `sqlite3.IntegrityError: FOREIGN KEY constraint failed`.

   Root cause of the divergence: `cascade_delete_team` runs `_delete_team_anchor_and_orphan_data`
   first, clearing the team's stat rows before deleting the team row. `cleanup_orphan_teams` never
   runs that pass — its Phase 2 (`_delete_team_scoped_data`) covers team-scoped tables only.

2. **Blast radius: the rollback eats the good work too.** Neither
   `_delete_game_scoped_data_for_perspectives` (`:467-551`) nor `_delete_team_scoped_data`
   (`:693-731`) commits internally — verified by reading both — and the exception fires before the
   `conn.commit()` at `:837`. So phases 1 and 2 roll back for ALL teams in the batch. The caller
   (`generator.py:2441-2450`) swallows it as `Orphan cleanup failed for N team(s); report continues.`

**The rollback is what makes the leak permanent.** It restores Phase 1 — the orphan-vs-orphan
`games` rows cleanup had just deleted. `_TEAM_BASE_PRED` (`:995-996`) requires a team to have NO
games row, so every rolled-back team is thereafter invisible to the only pass that could sweep it.
Nothing self-heals. The log corroborates: reclamation ran 70 times and deleted 0 teams every time.

### Measured

From `ephemeral/2026-08-16-report-restore/regenerate-20260816-204714.log`, re-derived 2026-08-17
(the run has since finished; do not inherit these, the commands are in Verification):

| signal | count |
|---|---|
| `FOREIGN KEY constraint failed` | 5 |
| `Orphan cleanup failed for N team(s)` | 5, 12, 8, 4, 5 — batch sizes summing to 34 |
| `excluded from reclamation` | 389 firings, 15 distinct team ids, all naming `player_game_batting` |
| `Orphan reclamation: deleted 0 team(s)` | 70 runs, plus 1 that logged `deferred` |

⚠ **Two claims in this spec's own earlier text were FALSE and are corrected here.** (1) It said
"30,082-line log, 70 of 71 complete". The log is now 30,689 lines and the run FINISHED:
`[71/71] OK`, `generated: 71  skipped: 0  failed: 0  of 71`. The earlier note was written mid-run.
(2) It projected "the rebuild would leak ~30 team rows". **That is unsupported and must not be
repeated**: 34 is the sum of discarded batch sizes, not a count of leaked rows, and the 15 distinct
ids count teams holding stat rows, not teams leaked. The leaked-row count is UNMEASURED.

⚠ **Not all 15 excluded ids belong to this defect.** Ids 1104 and 1181 fire before the first FK
failure — that is the by-design divergence-collapse stub exclusion `.claude/rules/data-model.md`
describes as expected and benign. Do not count them as damage.

### The work

1. Widen `undeletable_ids` to the same test reclamation uses, composed from the existing
   `_TEAM_STAT_EXISTS` constant. **Do not hand-write a second table list** — that is the drift this
   fix exists to close, and a hand-list is how `merge_duplicate_game` silently dropped two columns.
2. Delete the deletable teams **per team under a SAVEPOINT**, catching `sqlite3.IntegrityError`,
   rolling back to that savepoint, and logging a WARNING. One failure skips one team; the rest of
   the batch survives to the commit. Follow the precedent at
   `src/gamechanger/loaders/scouting_loader.py:389-420`, do not reinvent it.
3. **Keep the warning's claim narrow.** It names the team id and the sqlite error text. It names a
   referencing TABLE only when it can: `_first_stat_reference_table` probes just the six
   `_STAT_REFERENCE_PROBES` tables and returns `"unknown"` otherwise (`:1156`, `:1248`) — and after
   step 1 those six can no longer be the cause, so it will return `"unknown"` for precisely the
   cases the savepoint catches. Either broaden the probe or promise less; do not promise a table
   name the code cannot produce.
4. **Three prose sites go false with step 1, not one.** The summary log line
   `"%d retained (shared games)"` (`:842`), the docstring at `:795` ("Orphan teams that still have
   game FK references after Phase 1 are retained"), and the inline comment at `:819` ("which orphans
   still have remaining game FK references") each state that retention is only ever for a remaining
   game reference. Prose is a claim.

**Fix forward only** (operator ruling 2026-08-17). No repair pass for teams already stranded:
existing scouting data is not precious (standing ruling) and the counted rebuild is next.

## Item 2 — the reaper's stale prose and its error contract

Three findings on ALREADY-COMMITTED code (the generate-concurrency chunk). Approval died with that
commit, so they arrive here as new work. Each was verified against the file, not taken from the
reviewer. One root cause: that chunk reordered the reaper to flip the `reports` row BEFORE unlinking
the orphan HTML — correct, and what stopped a failed unlink wedging the generate page — but two
places describing what an "error" MEANS did not move with it.

1. **`lifecycle.py:184-186` — the docstring states the opposite of the code.** It still says the
   reaper unlinks "before flipping the row", while the comment at `:263` declares the reverse order
   LOAD-BEARING and explains that restoring the old order re-wedges `POST /admin/reports/generate`
   with no UI escape. **Highest rank**: it needs no trigger and it authorizes the next reader to
   reintroduce a product-fatal bug.
2. **`lifecycle.py:284` — `reaped` and `errors` are no longer disjoint.** `result.reaped += 1` sits
   above the unlink while the `except` at `:296` wraps the whole per-row body, so a failed unlink
   counts the row in BOTH — contradicting `ReaperResult`'s docstring at `:158-160`.
3. **`reports_admin.py:149-158` — a false operator-facing ERROR.** It asserts "a row it failed to
   clear will keep refusing submissions until it is resolved." After the reorder those errors come
   mostly from unlink failures on rows already flipped to `failed`, which the `status='generating'`
   count two lines below no longer sees — so they refuse nothing. The comment at `:150-151` carries
   the same stale premise.

### The work

1. Give the unlink its own `try` and its own counter (`files_failed`, additive on `ReaperResult`),
   leaving `errors` to mean what its docstring says. This is what lets finding 3 distinguish "could
   not clear the row" (a real wedge) from "could not delete the file" (a stray file).
2. Gate the admin ERROR on the row-clearing failure only, and reword it and its comment.
3. Correct the reaper docstring at `:184-186` to match the code, and say why the order is what it is.
4. **A FOURTH stale site sits outside `src/`.** `docs/admin/operations.md` (the "The check is not
   passive" paragraph, ~line 582) tells the operator the reap-first order "is what stops a crashed
   generation from blocking this page for an hour" — the exact rationale `reports_admin.py:119-125`
   says is "wrong in both directions and is corrected here". The reaper only selects rows ALREADY
   past the threshold, so reaping first shortens nothing. Correct the doc sentence to match the
   route comment.
5. **Establish the consumer set by reading, not by assuming.** The reaper has FOUR production
   callers — `src/api/main.py:80` (reads `.reaped`), `src/api/routes/reports_admin.py:148` (reads
   `.errors`), and `src/reports/lifecycle.py:401` and `:1485` (discard the result). In `src/`,
   `reports_admin.py` is the only `.errors` READER. **But tests are consumers too**:
   `tests/test_orphan_reclamation.py:1121` asserts `.errors == 0`. Check it survives the new
   counting rather than assuming it does.

⚠ **A stale test rides this.** `tests/test_report_generator.py::test_the_row_is_freed_even_when_the_orphan_unlink_fails`
(~line 5290) asserts `result.errors == 1` for the failed-unlink case. Under the new counting that
becomes `files_failed == 1, errors == 0`. Updating it is MUST-FIX in the same change, and it should
pin `reaped` too — the overlap is currently unasserted in either direction.

## Tests

`tests/test_report_generator.py`, beside the existing `cleanup_orphan_teams` coverage
(~3282-3738), real schema via `conftest.load_real_schema`, BDD shape per `.claude/rules/testing.md`.

**Item 1** — class `TestCleanupOrphanTeamsFkSafety`:
- (a) `test_the_deletable_sibling_is_still_deleted` — a gameless team holding one
  `player_game_batting` row, batched with a genuinely deletable team; no exception escapes.
- (b) `test_the_stat_referenced_team_is_retained`
- (c) `test_the_retention_is_named_in_a_warning`
- (d) `test_the_batch_work_is_committed_not_rolled_back` — on a FRESH connection the deletable
  team's row is absent and its team-scoped rows are gone.
- (e) `test_an_uncovered_foreign_key_skips_only_that_team` — savepoint containment proven
  INDEPENDENTLY of the predicate: force the FK failure from a table step 1 does NOT cover —
  `reports.team_id` (`migrations/001_initial_schema.sql:611`, `NOT NULL REFERENCES teams(id)`, no
  `ON DELETE`).

**(e) is the one that matters for review**: without it the savepoint half is unfalsifiable, because
predicate alignment alone makes every covered case pass.

**Item 2** — classes `TestReaperUnlinkFailureAccounting` and `TestAdminGateWedgeLog`:
- `test_a_failed_unlink_still_reaps_the_row` — `reaped=1`, and the row reads `failed` on a fresh
  connection.
- `test_a_failed_unlink_counts_as_files_failed_not_errors` — `files_failed=1, errors=0`.
- `test_a_failed_row_flip_counts_as_an_error` — `errors=1`.
- `test_no_wedge_error_is_logged_when_only_the_unlink_failed`, and its inverse
  `test_the_wedge_error_is_logged_when_the_row_could_not_be_cleared` — the second is the positive
  control: without it, a gate that never logs at all would pass the first.

Plus the stale-test update named above.

## Out of scope

- `cascade_delete_team` — its anchor pass already clears the stat rows, and its deliberately-spared
  F-H1 rows are covered by its survivor check. Not exposed to this crash.
- `reclaim_orphan_reference_data` — it is the seam being agreed WITH, not changed.
- Repair of the teams already stranded (see the fix-forward ruling above).
- The reaper's 30s `busy_timeout` latency on a serving path, and an unhandled exception escaping
  `generate_report` leaving a row `generating` for the full hour. Both are recorded, acknowledged
  trades in `docs/admin/operations.md`, not findings.
- The two sibling stubs from the same log sweep: `2026-08-16-plays-parser-unknown-templates.md` and
  `2026-08-16-restore-run-observations.md`.

## Verification

Never trust a piped pytest exit code — redirect and capture `$?` separately.

1. **Re-derive the log counts** (do not inherit the table above):
   `grep -c "FOREIGN KEY constraint failed" ephemeral/2026-08-16-report-restore/regenerate-20260816-204714.log`
   → expect `5`; `grep -n "Orphan cleanup failed" <log>` → expect 5 lines reading 5, 12, 8, 4, 5;
   `grep -o "Orphan reclamation: deleted [0-9]* team" <log> | sort | uniq -c` → expect `70` at
   `deleted 0 team`; and `grep -c "Orphan reclamation deferred" <log>` → expect `1`, the run that
   makes 70 + 1 = 71. **Positive control**: `grep -c "FOREIGN KEY constraint failed" CLAUDE.md`
   → `0`, proving the pattern can miss.
2. **RED, before the fix**:
   `python -m pytest tests/test_report_generator.py -k "TestCleanupOrphanTeamsFkSafety or TestReaperUnlinkFailureAccounting or TestAdminGateWedgeLog" > /tmp/red.txt 2>&1; echo "RC=$?" >> /tmp/red.txt`
   → read the file; expect `RC=1` with at least `test_the_deletable_sibling_is_still_deleted`,
   `test_the_batch_work_is_committed_not_rolled_back`,
   `test_an_uncovered_foreign_key_skips_only_that_team` and
   `test_a_failed_unlink_counts_as_files_failed_not_errors` failing BY NAME. A test that passes here
   is not testing the defect.
3. **GREEN, after the fix**: same command → `RC=0`.
4. **Full suite**: `python -m pytest > /tmp/suite.txt 2>&1; echo "RC=$?" >> /tmp/suite.txt` → read
   the file for the RC and the `N passed` line. Expect `RC=0` and a passed count ≥ the pre-chunk
   baseline. Record BOTH numbers in the progress log. Run it once per review round — a chunk
   touching this file has broken hand-built-schema tests before.
5. **Test-scope discovery**: `grep -rl "reports.lifecycle" tests/` → run every file it names, not
   just the one in Files.
6. **Consumer check** (item 2, work step 5). Two greps, because one does not prove it:
   `grep -rn "reap_stale_generating_reports" src/ tests/` → expect the four production callers
   named in work step 5 plus the test sites; then
   `grep -rn "\.errors" src/api/ src/reports/lifecycle.py` and READ each hit — expect
   `reports_admin.py` as the only reader of a REAPER result's `.errors` in `src/`. Do not read a
   count as proof: `.errors` is a field name shared with several unrelated result dataclasses
   (`LoadResult`, `CleanupResult`), so the grep over-matches by design and only a read of each line
   rules it in or out.
7. **PII scan**: `python3 src/safety/pii_scanner.py --staged` → `0 violations`, and reconcile the
   scanned-count against the staged-count. `SKIP_PATHS` blinds it to whole trees; give each skipped
   staged file a manual pass. Note the rename gap if a spec moves to `done/` in this commit.
8. **Reviews** — all OPERATOR-TYPED; a session cannot invoke them, so stop and ask. `/simplify`
   optional and BEFORE `/code-review`; then `/code-review`; then **`/security-review`, REQUIRED**
   (CLAUDE.md step 5 names deletes and this is a hard-delete seam). Codex review REQUIRED — the
   chunk touches `src/`. Name the review range and verify the reviewer received it.
9. **Acceptance is owed at the rebuild, not here.** The observable proof is that the FK traceback and
   the `Orphan cleanup failed` warning are ABSENT from the counted rebuild's log. Record as
   `acceptance: owed at <rebuild chunk>` at handoff.

⚠ `bb report generate` is destructive on three conditions (CLAUDE.md). This chunk changes one of its
cleanup paths; no step here runs it against live data.

## Progress log

- **2026-08-16** — Stubbed from the trainer's log sweep during the 71-team restore run. No code touched.
- **2026-08-17** — Full-run counts added (later corrected; see below). Recommendation upgraded to
  land before the counted rebuild.
- **2026-08-17 (spec session)** — Rewritten STUB → full spec. Every claim re-derived against the
  repo rather than inherited: both delete helpers read and confirmed not to commit; the
  cleanup-vs-reclamation predicate divergence confirmed by reading both; the permanence mechanism
  (rollback restores Phase 1 → `_TEAM_BASE_PRED`'s no-games clause hides the team forever) found in
  this session and corroborated by `deleted 0 team(s)` on 70 of 70 runs. **Two of this spec's own
  earlier numbers were falsified** — the run finished 71/71, and the "~30 leaked rows" projection is
  unsupported. Operator ruled the fix shape (align AND savepoint) and fix-forward-only.
- **2026-08-17 (spec session, item 2)** — Codex spec review run on the plan outline
  (`RESULT_FILE=/tmp/codex-spec-review.E81Jkc`, 1 P1 / 5 P2 / 2 P3, all folded; codex independently
  reproduced the `IntegrityError`). Its P1 — `/security-review` is mandatory on a delete path, not
  optional — is now Verification step 8. A `/code-review` then surfaced three findings on the
  already-committed generate-concurrency chunk; all three verified against the files here, and the
  operator ruled them folded into this chunk as item 2 rather than run separately.
- **2026-08-17 (spec session, round 2)** — Codex spec review run on THIS FILE
  (`RESULT_FILE=/tmp/codex-spec-review.ysa9c2`): **0 P1, 2 P2, 2 P3**, all four verified against the
  repo and folded. It confirmed the `lifecycle.py` / `reports_admin.py` line citations and the log
  math independently. The two that changed scope: a FOURTH stale-prose site in
  `docs/admin/operations.md` carrying a rationale `reports_admin.py:119-125` already calls wrong,
  now in Files and work step 4; and the sole-consumer claim was **too strong** — the reaper has four
  production callers and a test at `tests/test_orphan_reclamation.py:1121` also reads `.errors`, so
  the claim is narrowed to "the only `.errors` reader in `src/`" and its grep is split in two. The
  other two made Verification executable: concrete test names in step 2, and the `+1 deferred`
  re-derivation in step 1. Per the rubric's re-review protocol, no round 3 is owed — nothing found
  here was a P1/P2 artifact of an earlier fold-in.
- **Status note**: `READY` is written pre-commit by design — CLAUDE.md step 7 flips Status before
  staging so it rides this commit. Codex flags this every time; it is unfoldable by construction.
