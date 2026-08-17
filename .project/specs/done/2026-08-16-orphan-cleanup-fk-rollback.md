<!-- NO REAL NAMES OR IDENTIFIERS — no person's name, ever; teams by id/role only. -->

# Orphan cleanup FK failure rolls back the whole phase; and the reaper's prose outlived its reorder

**Date**: 2026-08-16 (rewritten 2026-08-17) · **Status**: `COMPLETE (this commit)` ·
`acceptance: owed at the counted rebuild` — the observable proof is that the FK traceback and the
`Orphan cleanup failed` warning are ABSENT from that run's log (Verification step 9).
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
- **2026-08-17 (execute session)** — Audited the spec against the repo before writing code; every
  load-bearing claim held. Verification step 1 re-derived exactly: FK `5`; `Orphan cleanup failed`
  at lines 10167/18831/20296/22287/28406 reading `5, 12, 8, 4, 5`; `70` × `Orphan reclamation:
  deleted 0 team`; `1` deferred; positive control `0` in `CLAUDE.md`. Also confirmed by reading:
  neither `_delete_game_scoped_data_for_perspectives` (`:467`) nor `_delete_team_scoped_data`
  (`:693`) commits; `reports.team_id` is `NOT NULL REFERENCES teams(id)` with no `ON DELETE`
  (`migrations/001_initial_schema.sql:611`); the reaper's four production callers
  (`main.py:80`, `reports_admin.py:148`, `lifecycle.py:401`, `:1485`); and per Verification step 6,
  a READ of every `.errors` hit in `src/api/` + `lifecycle.py` — `reports_admin.py:149/167` is the
  only READER of a reaper result's `.errors` in `src/` (the two `lifecycle.py` hits are WRITERS,
  one of them `CleanupResult`'s, a different dataclass). `tests/test_orphan_reclamation.py:1121`
  asserts `.errors == 0` on a clean DB and survives the new counting unchanged.
- **RED, then GREEN.** RED (RC captured unpiped): `RC=1`, 9 failed / 2 passed, with all four
  spec-named tests failing by name. GREEN: `RC=0`, 11 passed. The 2 that passed at RED
  (`test_a_failed_unlink_still_reaps_the_row`, `test_a_failed_row_flip_counts_as_an_error`) are
  regression pins on behavior the 2026-08-16 reorder already produced, not defect tests.
- **Full suite**: baseline `4551 passed` (measured on a stashed tree, `RC=0`), after
  `4561 passed`, `RC=0`. +10 tests, 0 deleted — ratchet satisfied.
- **One deviation from the spec, deliberate**: `TestAdminGateWedgeLog` landed in
  `tests/test_admin_reports.py`, not `tests/test_report_generator.py`. It tests
  `reports_admin._a_generation_is_in_flight`, whose other gate tests already live there, and
  `test_<module>.py` is the naming convention. Verification step 2's command was run across BOTH
  files. Everything else landed as specified.
- **Fix shape as landed.** Item 1: deletability now `game_ref_ids | stat_ref_ids`, the second
  composed from `_TEAM_STAT_EXISTS` (no hand-list), computed AFTER Phase 1; a per-team `SAVEPOINT`
  around each `DELETE FROM teams` catching `sqlite3.IntegrityError`; a WARNING naming the team id
  and — only where the probe can answer — the referencing table; the savepoint WARNING names the
  team and the sqlite text and promises NO table. All three prose sites corrected (docstring,
  inline comment, summary log line, which now reads `retained (still FK-referenced)` +
  `skipped (delete raised)`). Item 2: `ReaperResult.files_failed` added, the unlink given its own
  `try`, the docstring's order claim corrected, the admin ERROR reworded and left gated on
  `errors` (which now means row-clearing only), and `docs/admin/operations.md`'s "check is not
  passive" paragraph corrected to match `reports_admin.py:119-125`.
- **Documentation assessment**: trigger 5 fired; `docs/admin/operations.md` updated (the paragraph
  above) and its file-level `Last updated` line bumped to 2026-08-17 with this spec as Source.
- **2026-08-17 (`/simplify`)** — Four cleanup agents (reuse / simplification / efficiency /
  altitude). Applied: `_FailingUpdateConnection` became a `sqlite3.Connection` SUBCLASS via
  `connect(factory=...)` instead of a hand-surfaced proxy (a proxy is a whitelist —
  `_require_clean_connection` already reads `in_transaction` on the borrowed path); the new reaper
  test class now reuses module-level `_insert_report_row` and `_write_report_file` instead of a
  third report-INSERT literal and a hand-rolled mkdir; `skipped_ids` (a list only ever `len()`-ed)
  became two counters incremented WHERE THE OUTCOME HAPPENS, so the success count is observed
  rather than derived by subtraction from a pre-loop set. Suite unchanged at `4561 passed`, `RC=0`.
- **Skipped, with reasons.** (1) *Drop two new tests as subsumed by the amended stale test* — they
  are named in this committed spec, and `.claude/rules/testing.md` requires a spec to name any test
  deletion; the duplicated arrange block was reduced instead. (2) *Compose the FULL
  `_team_orphan_pred` rather than just `_TEAM_STAT_EXISTS`* — the altitude agent correctly noted
  `_TEAM_BASE_PRED` (`:1101-1107`, read directly) carries a `reports` root, i.e. exactly the FK
  test (e) drives its raise from. **Verified the consequence and it argues FOR the spec's shape**:
  enumerating every FK on `teams(id)` from the migrations, the tables Phase 2 does not clear are
  `games`, the six stat children, and `reports` — so adopting the full predicate would cover ALL of
  them and leave the savepoint with no reachable failure to test, which is precisely the
  unfalsifiability the spec's "(e) is the one that matters for review" note exists to prevent. It
  would also newly retain any `member` team in the batch (`_TEAM_BASE_PRED` opens with
  `membership_type = 'tracked'`) — a behavior change beyond this chunk. Kept as specced; recorded
  here so `/code-review` can rule independently.
- **Residual (perf, NOT acted on).** The new stat-reference SELECT is per-candidate correlated
  EXISTS, and four of its six subqueries have no usable index (`spray_charts.team_id`,
  `plays.batting_team_id`, `reconciliation_discrepancies.team_id`, and the `perspective_team_id`
  columns on those three). Agent-measured against the live dev DB: ~50 ms warm per stat-free team,
  so ~2.5 s on a 50-team batch, against a generation that already spends tens of seconds on
  network. Both closers (a hand-written six-table set query, or an index migration paying write
  amplification on ~770k load-path rows) are worse trades today. Route to `IDEAS.md` at handoff.
- **2026-08-17 (codex review + `/code-review`)** — Codex run on `uncommitted`
  (its `RESULT_FILE` under `/tmp`, 5 lines, read to completion — the epoch-stamped filename is
  deliberately not reproduced here; a 10-digit run trips the scanner's `us_phone` pattern, the
  documented noise class in `pii_patterns.py`): **1 P1, 1 P2**.
  `/code-review` returned 4 findings independently. The two reviewers OVERLAPPED on one defect
  (codex P1 = `/code-review` #4), which codex rated far higher because it reproduced the data loss.

  **FIXED — the reaper discarded its own arbiter's rowcount (codex P1 / CR #4).** The UPDATE is
  guarded by `AND status = 'generating'`, but `reaped += 1` and the HTML unlink both fired
  regardless of whether it matched. **Reproduced independently before fixing** (not taken from the
  reviewer): a generation that ran past the threshold and then committed `ready` ended as
  `status='ready'`, `report_path='reports/race.html'`, **its served HTML DELETED**, with the reaper
  returning `ReaperResult(reaped=1, files_removed=1, errors=0, files_failed=0)` — a clean success.
  The share link then 404s on a report the admin list calls ready. Now gated on
  `cursor.rowcount == 1`; a lost race logs at INFO and is counted nowhere (nothing failed, and the
  gate's `status='generating'` COUNT will not see the row either). This is the
  DELETE-is-the-arbiter rule in `.claude/rules/data-model.md`, which the reaper had the guarded
  write for but never applied. ⚠ **PRE-EXISTING on already-committed code** — approval died with
  that commit; folded in under "no pre-existing excuse" because it sits inside the lines this
  chunk edits, and flagged to the operator as a scope expansion.
  **FIXED — CR #2, the savepoint caught only `IntegrityError`.** Any other DB error escaped with
  the SAVEPOINT open → caller swallows → connection closed mid-transaction → the whole-batch
  rollback this chunk exists to prevent. Broadened to `sqlite3.Error`. ⚠ **I did NOT accept the
  finding's stated scenario.** It argued `database is locked` on the Phase-3 DELETE; **measured
  otherwise** — a DELETE matching ZERO rows still takes SQLite's write lock, so Phases 1-2 already
  hold it by then. Cross-process contention surfaces at Phase 1's first DELETE, before any
  savepoint exists, where nothing in this function can contain it. **That exposure is real and
  stays OPEN** (residual below). The catch is justified as never-strand-a-savepoint, not by the
  lock story.
  **FIXED — codex P2, the concurrency test gap.** New `TestReaperWhenALateGenerationFinishesFirst`
  (3 tests). **Mutation-proven, expected catchers named BEFORE the run**: predicted 2 of 3 fail
  (`..._html_survives`, `..._not_counted_as_reaped`) with `..._left_ready` passing either way since
  the guarded UPDATE matches nothing regardless. Ran with `__pycache__` cleared and the mutation
  asserted applied: **exactly 2 failed, 1 passed**, then restored and residue-checked.
  **ROUTED TO OPERATOR, not fixed — CR #1 (MEDIUM)** `MAX_CONCURRENT_ADMIN_GENERATIONS = 2` lets
  two generations through the click-to-row window the semaphore exists to cover; the reviewer
  argues the operator's own one-at-a-time ruling implies `1`. Untouched by this chunk, pinned by
  `TestTheCapValue` to a 2026-08-16 operator ruling — a value ruling to re-make, not a bug to fix
  here. **ROUTED — CR #3 (LOW)** Starlette skips a background task if the response send fails
  (client disconnect), leaking a semaphore slot permanently; two occurrences wedge the page. Also
  already-committed code, outside this chunk.
- **Full suite after review fixes**: `4564 passed`, `RC=0` (baseline `4551`, +13, 0 deleted).
- **Residual (OPEN, route at handoff)**: cross-process lock contention at Phase 1's first DELETE
  still rolls the whole batch back and re-arms the permanence mechanism. No savepoint can contain
  it — containment would have to move above Phase 1 or into the caller.
- **2026-08-17 (`/security-review`)** — **No findings at any severity.** Four candidate surfaces
  traced to primary sources and ruled out: (1) the new f-string SQL in `cleanup_orphan_teams` — all
  three interpolated positions are module constants or an `int()`-coerced rowid, with every team id
  parameterized; (2) path traversal via the reaper's `_REPORTS_DIR / f"{slug}.html"` unlink — `slug`
  has exactly ONE writer, `secrets.token_urlsafe(12)` (`generator.py:1906`), which emits only
  `[A-Za-z0-9_-]`, and the new rowcount gate strictly NARROWS what gets unlinked; (3) the
  authorization and CSRF boundary on `POST /admin/reports/generate` — `_require_admin` remains the
  first statement, both admission gates run after it, and `CSRFMiddleware` fires before the
  endpoint; (4) the new log lines and refusal banners — banners are constants rendered under Jinja
  autoescape, and the logs carry only integer ids and sqlite error text (no person names).
  ⚠ **Scope note worth keeping**: the diff the harness handed the reviewer was STALE — it predated
  the savepoint/predicate rework, the `files_failed` split, the rowcount gate, and the reworded
  admin ERROR. The reviewer detected this, re-derived the live diff, and reviewed BOTH. Verifying
  the reviewer's range (CLAUDE.md step 5) caught a real gap here; do not assume the supplied diff
  is current.
- **Non-security observation from that pass, NOT acted on**: `conn.execute(f"SAVEPOINT {savepoint}")`
  sits OUTSIDE the per-team `try`, so a raise there would escape as the whole-batch rollback. It is
  unreachable — ids are positive AUTOINCREMENT rowids through `int()` — and moving it inside would
  make the `except` issue `ROLLBACK TO` against a savepoint that may not exist, trading an
  unreachable failure for a reachable one. Left as is, deliberately.
- **Owed next**: operator approval (step 7). All four reviews are complete.
- **Status note**: `READY` is written pre-commit by design — CLAUDE.md step 7 flips Status before
  staging so it rides this commit. Codex flags this every time; it is unfoldable by construction.
