# Line of march

The standing answer to "what should we do next?" Read this before proposing scope. Lifecycle
step 9 (HANDOFF) updates it: move what landed out of NOW, promote from NEXT, and add anything the
chunk discovered as a stub or a residual.

Individual chunk specs live beside this file as `<date>-<slug>.md`. Every one of them must read
`COMPLETE`, `READY`, `PARKED`, `STUB`, or `OPEN`, or belong to a chunk in flight. The vocabulary is
exactly those five. `READY` (added 2026-08-09, operator ruling) = spec written, codex-reviewed, and
committed — waiting only for a fresh execution session; the march's NEXT should name every READY
spec. `PARKED` now means ONLY "set aside deliberately, + why" — its former "ruled and queued" second
sense moved to READY. (`RULED` was retired 2026-08-08.) Audits verify READY specs are still wanted.

**`specs/done/`.** At handoff, a spec whose Status you just flipped to `COMPLETE` moves to
`.project/specs/done/` in the SAME commit. Everything still open stays in the live directory —
that is exactly what principle F's audit has to see. Note the rename cost: plain `git log` on the
new path shows only the move commit, so **use `git log --follow -M20% -- <path>`** to get a moved
spec's real history — bare `--follow` ALSO fails silently when the move commit carried heavy
growth (chunk 16's spec grew 429 → 790 lines in its move and dropped below git's 50% similarity
default; measured 2026-08-17). Someday-work does not live here at all; it is one line in `IDEAS.md`.

## NOW

Continue the ruled sequence in STANDING RESIDUALS ("Regeneration hazard — RULED 2026-08-12"):
same-listing detection → generate-concurrency cap → runs-as-scoreboard instrument → full
regenerate. **The generation freeze is LIFTED** — the lossy-merge hazard it protected against is
fixed and proven on live data. The plays half-pair clobber below must land BEFORE the regenerate.

- ~~**Generate-concurrency cap**~~ — **LANDED 2026-08-17**, `acceptance: run`. Spec moved to
  `done/2026-08-10-admin-generate-concurrency.md` — **history needs `git log --follow -M20%`**;
  bare `--follow` returns only the move commit for this one, because the spec grew 429 → 790 lines
  in it (the case the `specs/done/` note above describes). Suite
  4,536 → 4,551 (+15). `POST /admin/reports/generate` now carries TWO admission gates covering
  different blind spots: an in-process `BoundedSemaphore(2)`, and a reap-then-count of
  `reports.status='generating'` that can see OTHER PROCESSES. Thirteen mutants, every one matching
  an expectation stated before it ran.

  **The spec's N=2 ruling did NOT survive execution, and the board should say so.** A mid-chunk
  operator ruling added a CROSS-PATH gate after a 2026-08-16 incident: a UI click raced the serial
  CLI restore run, hard-deleted stat rows on games the CLI was actively writing, forced the CLI to
  skip orphan reclamation, and produced a report served as `ready` carrying **155 uncorrected
  reconciliation discrepancies** (run 160). Codex then established that `reports` has **no source
  column**, so the gate cannot distinguish a CLI run from the page's own in-flight generation.
  **Operator ruled: the admin page is ONE-AT-A-TIME.** N=2 is now reachable only inside the
  click-to-`generating`-row window — which is precisely why the semaphore stays rather than being
  deleted as vestigial. Per-path caps do not compose; that is the durable lesson.

  ⚠ **This does NOT cap the CLI — it makes the admin door DEFER to it.** CLI-vs-CLI remains
  unguarded, so consequence 3 of the regeneration hazard below is UNDISCHARGED and the regenerate
  still owes its own discipline.

  **Three residuals it carries out, all live.** (1) **`WEB_CONCURRENCY` set in the untracked
  environment file silently multiplies the cap and NO TEST CAN SEE IT** — uvicorn reads that
  variable directly and the `app` service loads that file, so one line there yields 4 workers and
  an effective cap of 8 with the suite fully green. Found at `/code-review`; the widened guard
  reaches only the TRACKED routes plus the dev container's own environment. This now ranks
  alongside the replication invariant below, and unlike it requires no infrastructure change at
  all. (2) The cap is in-process, so **replicating the app container multiplies it and nothing
  detects that**; its only enforcement is a deployment invariant in `docs/admin/operations.md`.
  (3) The stale-generation reaper now runs on **every** admin submission, refused ones included —
  operator-ruled acceptable (the 1-hour threshold is ~70x a real generation), but a materially
  slower generation would put it at risk of reaping live runs.

  **It also fixed a product-fatal defect OUTSIDE its own file list, on an operator ruling.** In
  `src/reports/lifecycle.py` the reaper unlinked a report's orphan HTML BEFORE marking the row
  failed, inside one swallowing per-row try/except — so a failed unlink left the row `generating`
  forever. Tolerable before; with the new cross-path gate it wedged the generate page PERMANENTLY,
  and the delete affordance is itself gated on `status != 'generating'`, leaving no UI escape. The
  row is now flipped first. An explicit force-clear command for a stuck row younger than the
  staleness threshold was offered and DECLINED, and an unconditional startup wipe was recommended
  against and ruled out — CLI generations run in a separate process that SURVIVES an app-container
  restart, so such a wipe would kill a live run and unlink its file mid-flight.

- ~~**Same-listing detection**~~ — **LANDED 2026-08-15**, acceptance owed at the regenerate. Spec
  moved to `done/2026-08-13-same-listing-dedup-detection.md` (`git log --follow` for history).
  Same-pair window 1.0s → 1,800s; a new opponent-divergence second pass; an identity-bearing
  promotion that hard-deletes the stub-headed `games` row (now named in `CLAUDE.md` as `bb report
  generate`'s THIRD destructive condition — the byte cap was raised 11,264 → 11,392 to fit it).
  Suite 4,513 → 4,529.

  **Two spec claims were REFUTED at execution and the rule narrowed twice — read this before
  citing the spec.** (1) Work item 2 said candidates share "the perspective team"; measured, the
  shared team is a perspective of exactly ONE row and uniformly the stub-headed one, so that
  reading fires only when the stub-headed row loads second and left the promotion UNREACHABLE. The
  STRUCTURAL reading shipped instead. (2) `/code-review` found the mixed-identity trigger does not
  discriminate as argued: in **28 of 28** mixed pairs at every
  delta (26 at 0s, 1 at 1,800s, 1 at 3,600s) the identity-bearing side is the LOADING
  TEAM ITSELF, which carries a `public_id` by construction — so it degenerates to "the other row's
  differing team is a stub", true of a genuinely different real team (pool play; varsity + JV on
  one date). **Operator ruling: the divergence branch now requires IDENTICAL recorded instants**
  (`_DIVERGENCE_MAX_DELTA_SECONDS = 0.0`), the same-pair window stays 1,800s, and step 6's
  `(c) 1,800s` acceptance moved from 0 to 1.

  ⚠️ **Delta-0 is exposure-MINIMIZATION, not elimination, and the residual says so in three
  places.** Two real games CAN share a recorded start instant — `start_time` is recorded, not
  observed, which the spec itself proves. A wrong merge hard-deletes forever; a missed duplicate
  stays visible in a report. Anyone widening that bound owes evidence, not convenience.

  **Acceptance is NOT yet run** — it is the post-regenerate census in the spec's Verification
  step 6, and the amended expectation is `(a) → 0`, `(c) 0s → 1`, `(c) 1,800s → 1`,
  `(c) 3,600s → 1`, `(b)` unchanged at 92 with floor 5,400s.

- ~~**Opponent-roster dedup gap**~~ — **LANDED 2026-08-12** at `9f1f930`, acceptance pass PASSED.
  Spec moved to `done/2026-08-10-opponent-roster-dedup-gap.md` (`git log --follow` for history).
  The sweep now runs for every team a load writes roster rows for, scouted team first, each under
  its own savepoint; two guards ship with it. Suite 4,495 → 4,513.

  **Read the acceptance numbers before reading any roster count.** Three report generations took
  repo-wide roster excess **7,048 → 4,347** across **271 → 224** teams; run 1 alone swept 20 teams
  and merged 1,227 ids. Content destroyed: **zero** — 331 stat rows were deleted but the set of
  distinct content signatures is byte-identical before and after, verified against
  `data/backups/app-2026-08-12T022220.db`. The content-aware refusal **fired in production** on its
  first outing (team 301, a merge that would have deleted a differing `rbi`). ⚠️ A converged roster
  is still NOT "one row per human": jersey-corroborated scorekeeper spelling variants remain
  visible to a coach and are deliberately out of scope.

## NEXT

- **Migration Step 4 — second-pass rule trim.** After ~3 more real chunks, take the ~22 surviving
  path-scoped rules through "would removing this line cause a mistake?", run `/doctor`, and
  regenerate the cheat sheet from what actually got used. (The `PARKED`-splitting question this
  entry used to carry is CLOSED — settled ahead of Step 4 by `4fc1f6d`, which added `READY`. Do not
  re-open it.)
- ~~**Rung-c season-year filter**~~ — **LANDED 2026-08-09.** Spec moved to
  `done/2026-08-05-rung-c-season-year-filter.md`. It carried both queued residuals
  (worktree-guard `CLAUDE_HOME`, extensionless PII scannability) and settled the owed
  `codex-review`-vs-`codex review` comparison; all three are struck from the lists below.
- **Step 9's `--follow` promise — STUB 2026-08-17**, spec `2026-08-17-spec-move-follow-gap.md`.
  **Mostly already fixed; what is left is one operator decision, and the chunk may be foldable into
  another docs chunk rather than run alone.** A `git mv` plus a heavy same-commit rewrite drops a
  spec below git's default 50% rename-similarity threshold, so `git log --follow` returns only the
  move commit — silently, with a plausible one-line answer. Measured: chunk 16's spec grew
  429 → 790 lines and is **1 of 15** in `done/` affected; history is intact at `-M20%`, nothing was
  lost. The `specs/done/` preamble (`657dc22`) and the one genuinely-false per-entry pointer are
  both fixed. **Open: does CLAUDE.md step 9 change?** It still promises `--follow` unconditionally,
  which is what a session reads while CREATING the problem — the board note only helps a reader who
  already suspects one. That edit spends CLAUDE.md bytes, so it is a cap trade for the operator;
  the spec lays out three options and recommends adding a one-command check. ⚠ Bitten ONCE, so
  principle E's bites-twice bar means no rule was written — if it recurs, audit 6 has bite two.
- **Orphan-cleanup FK rollback — READY 2026-08-17** (`bb95034`), spec
  `2026-08-16-orphan-cleanup-fk-rollback.md`. `cleanup_orphan_teams` uses a games-only
  deletability test while reclamation also checks six game-child tables, so one undeletable team
  FK-crashes the delete and — because nothing commits incrementally — rolls back the WHOLE
  batch's cleanup. **Recommended to land before the counted rebuild.**

  **The permanence mechanism was found at spec time and is the reason this is not cosmetic**: the
  rollback also restores the orphan-vs-orphan `games` rows cleanup had just deleted, and
  `_TEAM_BASE_PRED` requires a team to have NO games row — so every rolled-back team is thereafter
  invisible to the only pass that could sweep it. Corroborated by `Orphan reclamation: deleted 0
  team(s)` on **70 of 70** runs. Operator ruled the fix shape (align the predicate AND add a
  per-team savepoint) and **fix-forward-only** — no repair of existing residue.

  ⚠ **Two numbers the STUB carried are FALSE; the spec marks them and they must not be requoted.**
  The restore run FINISHED (`[71/71] OK`, `generated: 71  skipped: 0  failed: 0`) — the stub's
  "70 of 71" was measured mid-run — and the "rebuild would leak ~30 team rows" projection is
  unsupported: 34 is the sum of discarded batch sizes, not a count of leaked rows. Also, 2 of the
  15 "excluded from reclamation" ids predate the first crash and are the by-design
  divergence-collapse stubs, not damage.

  **It now carries a SECOND work item, operator-ruled 2026-08-17.** Three `/code-review` findings
  on the ALREADY-COMMITTED generate-concurrency chunk, verified against the files: the reaper's
  reorder (flip row, then unlink) left behind a docstring at `lifecycle.py:184-186` stating the
  opposite order — which invites re-wedging the generate page — plus `reaped`/`errors` no longer
  being disjoint, and a false operator-facing ERROR claiming the page is wedged when only an
  unlink failed. Codex found a FOURTH site in `docs/admin/operations.md`. Bundled so one set of
  review gates covers both; they share a file, not a cause.

  Two sibling stubs from the same sweep, untouched: `2026-08-16-plays-parser-unknown-templates.md`
  (6 dropped play templates, 46 firings — north-star fidelity, appeal OUTS among them) and
  `2026-08-16-restore-run-observations.md` (six needs-a-look items, adjudicate at the next audit
  or the rebuild spec).
- **API-doc corrections & probes — one bundled chunk, PARKED behind the march** (audit-5
  routing, 2026-08-16). One api-scout pass, one PII-gated docs commit, after the regenerate:
  the three `event_id` doctrine sites (see STANDING RESIDUALS), the name-year probe
  (`2026-08-05-post-search-name-year-doc-defect.md`), the residual one-sided-game probe,
  `2026-08-04-public-organizations-surface.md`, and the harvest-web-bundle adopt-or-discard
  decision (`2026-08-04-harvest-web-bundle-before-probing.md`, which that chunk reads before
  its first probe).
- **Opponent org-reachability measurement — RULED: measure only** (operator, 2026-08-08). Bulk
  org discovery is DECLINED (vision non-goal). The funded question: what fraction of our real
  unresolved opponents (no `progenitor_team_id`) are reachable via a discoverable organization's
  roster surface? Read-only, needs a team→org lookup answer first; design nothing unless the
  number is material. Spec `2026-08-04-org-team-discovery-and-roster-ingest.md`.
- ~~**Sweep `docs/` for the retired workflow**~~ — **LANDED 2026-08-09.** Spec moved to
  `done/2026-08-09-docs-retired-workflow-sweep.md`. `docs/admin/agent-guide.md` deleted (124
  lines); 26 files touched; no executable line of `scripts/codex-review.sh` changed (proven by a
  before/after diff of its `--help` output, not by a `#`-prefix check).

  **The undercount ran to five passes, not three.** The spec inherited a 12-site inventory built
  across a term-grep pass, the codex-spec-review, and a post-`902fb1e` file-then-read pass. The
  execution session's re-run of Verification 10 found **six more**, taking it 5 → 8 → 12 → 18:
  `ephemeral/README.md` (the per-epic convention `safe-data-handling.md` points AT as "the full
  convention"), `.claude/rules/devcontainer.md:85,106` ("closure-gate tests"),
  `.claude/rules/dependency-management.md:46` ("a story's Files to Modify list"),
  `docs/admin/operations.md:309` ("until a follow-up story removes it"), and
  `.claude/rules/python-style.md:20`. **Four of the six sat in files already on the edit list** —
  the same blind spot that produced passes 1 and 2, reproduced by an inventory that had already
  been corrected twice for exactly it. Re-running the sweep is what caught them; trusting the
  inbound inventory would not have.
- ~~**PII scanner hardening**~~ — **LANDED 2026-08-10** at `26bf605`. Spec moved to
  `done/2026-08-10-pii-scanner-hardening.md` (`git log --follow` for history). Both
  `get_staged_files()` enumeration bypasses closed (`ACM`→`ACMR` and `-z`); its frozen-diff
  review experiment ran and fed Audit 4's ruling.
- ~~**Plays final-score recovery (seed §2)**~~ — **LANDED 2026-08-11.** Spec moved to
  `done/2026-08-10-plays-final-score-recovery.md`. Parser returns `ParsedGamePlays` (plays + derived
  final), loader persists it to `game_perspectives` (migration `013`), full suite green at **4,495**.
  The corpus was quiet and every pinned number held. **Two stubs it routed are in NEXT below**; read
  the backfill one before reading any 91 as a failure.

  **The review round mattered more than the build.** `/code-review` and codex were run
  independently and overlapped on exactly ONE of four findings — each caught something the other
  missed, which is the strongest single-diff evidence yet for the "keep both" verdict already in
  these residuals. The one only `/code-review` found was the serious one: `merge_duplicate_game`
  COPIES `game_perspectives` rows through a hand-written column list, so it silently DROPPED both
  new columns on every twin merge — reproduced `(8,7) → (None,None)` while the plays re-pointed
  intact, and it never self-heals. That is the Cleanup-Detection Mirror Invariant on a COPY path,
  and it was reachable by exactly the ordering the backfill stub plans. Now guarded by a
  `PRAGMA table_info`-derived drift test that fails on the NEXT forgotten column.
- **Plays final-score BACKFILL** — **STUB 2026-08-11**, spec
  `2026-08-11-plays-final-score-backfill.md`. The fix landed but **no stored data moved**: the
  detection query still reads **91** and all 2,464 `game_perspectives` rows are NULL, because
  whole-game plays idempotency skips any game that already has plays. Backup → reset → re-scout, in
  its own session, naming `bb report generate` as destructive first. **Success is 91 → the
  abandoned-charting residual (≥1), NOT → 0** — 87 of 88 recover, and one game's run is genuinely
  absent from the payload.
- **Runs as a reconciliation-scoreboard stat** — **STUB 2026-08-11**, spec
  `2026-08-11-runs-as-scoreboard-stat.md`. The scoreboard measures no runs stat, so **the north-star
  instrument was blind to the 102-run defect the recovery chunk just fixed**. Add it UNGATED first
  (gating raises `BaselineError`/exit 4 against a baseline lacking the key), and treat the 9
  two-scorebook units and the non-monotone units as legitimate disagreement. ⚠ Read the gate residual
  below before gating anything.
- ~~**Opponent-roster dedup gap**~~ — **LANDED 2026-08-12**; see NOW for the acceptance numbers.
  Spec moved to `done/2026-08-10-opponent-roster-dedup-gap.md`. The "zero refused forks is what
  the hazard looks like" lesson this entry carried is preserved in the spec and the jot list.
- **Plays final-score half-pair clobber** — **STUB 2026-08-12**, spec
  `2026-08-12-plays-final-score-half-pair-clobber.md`. `_persist_final_score`'s UPSERT guard is
  `OR` while both columns are assigned from `excluded`, so a half-derived pair `(5, NULL)` landing
  on a stored `(NULL, 7)` **NULLs a real score** — contradicting the docstring three lines above,
  which promises an all-or-nothing write. Found by codex review of a different chunk's diff.
  **Why you should care**: it is LATENT today (all 2,464 rows are NULL) and **the full regenerate
  is what fires it**, so it must land BEFORE that regenerate, not after. Not the one-character fix
  it looks like — `OR`→`AND` also discards a half we legitimately derived, so measure whether real
  payloads produce half-pairs before choosing.
- ~~**Same-listing dedup detection**~~ — **LANDED 2026-08-15; see NOW, not here.** Spec moved to
  `done/2026-08-13-same-listing-dedup-detection.md`. The source stub
  `2026-08-10-same-listing-dedup-window.md` stays `STUB` for the residual observations it also
  carries (the orphan one-sided game, the one-sided perspective predicate mismatch); its DETECTION
  half is superseded and its REPAIR half died with the 2026-08-12 regeneration ruling. Its text was
  re-pointed at execution.
- **Morning-of-game scheduled reports** — the forward product feature (`docs/ROADMAP.md`).

## PARKED DECISIONS

None open. The sitting of 2026-08-08 ruled all three (details in the named specs):

1. **Bulk org discovery: DECLINED** — vision non-goal; the narrow roster-recovery measurement is
   funded instead (see NEXT).
2. **Season-year filter: BUILD**, semantics settled — never cross-YEAR, same-year cross-season
   fine, absent year refuses (see NEXT).
3. **Prefix corpus: rule RELAXED, scrub CANCELLED** — real team/org/game ID prefixes are
   acceptable in `-REDACTED` placeholders; PERSON-scoped identifiers (player/user ids) remain
   synthetic-only, verified whenever those docs are next touched. The `api-docs.md` rule edit
   rides the PII-docs chunk.

## STANDING RESIDUALS

Carried deliberately. Not prose, not tickets — things that will bite if forgotten.

- **Regeneration hazard — RULED 2026-08-12.** Operator ruling (verbatim intent): existing
  scouting data is NOT precious — "I don't care if we lose everything that is there and I have
  to regenerate absolutely everything. Whatever gets us to 'correct ingestion' the fastest and
  most accurately." Two consequences (the first is the ruling, the second is trainer synthesis
  from it — re-adjudicate at spec time, not silently):
  1. Still generate no reports until `2026-08-10-opponent-roster-dedup-gap.md` lands — not to
     protect rows, but because pre-fix generation writes the same wrong merges (61 Unknown-name
     collapses, 33 lossy named merges loaded) into any fresh output. Correct ingestion first.
  2. REPAIR halves of open stubs are de-scoped; DETECTION/fix halves stay. One full regenerate
     after the correctness chunks land replaces the fleet roster repair pass, the seven
     twin-group merges, and the standalone plays backfill — the backfill's success criterion
     (91 → abandoned-charting residual ≥1, not 0) transfers to that regenerate's acceptance.
     Sequencing that follows: dedup fix → same-listing detection → generate-concurrency cap →
     runs-as-scoreboard instrument (so the regenerate is verifiable) → full regenerate.
  3. ⚠ **THE REGENERATE OWES ITS OWN CONCURRENCY DISCIPLINE, IN ITS OWN SPEC** (operator ruling
     2026-08-16, made while specing the cap). The generate-concurrency cap binds the **admin web
     page only** — the CLI and cron paths are uncapped BY DESIGN, and a bulk regenerate is
     precisely a CLI workload. So the cap landing does NOT make the regenerate safe: that spec
     must say serial, or name its own bound, or it re-runs the load that produced the 243-failure
     storm through the one door nothing guards.

     **UPDATED 2026-08-17, when the cap landed — this is still owed, but the shape changed.** The
     cap's amendment added a cross-path gate, so the admin page now REFUSES while any generation is
     in flight, CLI runs included. That closes admin-vs-CLI, which is the pair that actually bit
     (the 2026-08-16 incident). What remains open is **CLI-vs-CLI**: two `bb report` processes, or
     a regenerate overlapping the `morning-run` cron, are still completely unguarded — nothing in
     the CLI path consults the gate. A regenerate spec that reasons "the cap landed, so this is
     handled" would be reading the wrong half. Serial, or its own bound, still required.

- Devcontainer pip will break the way CI did when its image floats to pip 26.2.
- **The reconciliation gate CANNOT work on a growing corpus, and this is a design fault, not drift**
  (found 2026-08-10). `evaluate_gate` ratchets on ABSOLUTE deltas, so data growth alone fails it:
  across one ingest, pitching-BF accuracy moved 98.8% → 98.5% while its abs-Δ went 132 → 464. Nothing
  got worse; the corpus tripled. **Why you should care**: `CLAUDE.md` calls `reconcile-scoreboard`
  "a diagnostic, not a gate", but the CLI still calls `evaluate_gate`, exits non-zero, and its
  docstring calls itself "the north-star ratchet" — so every session that runs it sees a red FAILED
  it must be told to ignore. Reviving it needs RATE-based thresholds; retiring it means deleting the
  gate half. Operator ruling owed. ⚠️ **The nearest prior record, `IDEA-195`, is ARCHIVED
  (`.project/archive/ideas/`, not live `IDEAS.md`) and its PREMISE IS NOW REFUTED**: it calls the
  machinery "vestigial" and the scoreboard "a pure diagnostic with no verdict to trip". Measured
  2026-08-10 — the CLI calls `evaluate_gate`, prints `Reconciliation gate FAILED`, and exits **RC=1**.
  It is live, not vestigial. Read that idea before acting anyway: it carries a real footgun about two
  ratchets sharing this vocabulary, and says to scope any deletion by FILE, never by grepping
  "baseline"/"ratchet"/`--update-baseline`.
- **Row counts cannot detect an UPDATE — do not use them as a "DB is settled" check** (found
  2026-08-10, cost two rounds of wrong numbers in one spec). `games` and `plays` counts held
  identical at 2,303 / 143,613 across an entire session while `games.home_score` changed underneath,
  moving a measured population from 92 units to 91 and invalidating a 90-game validation run.
  **Why you should care**: every before/after measurement in this repo rests on a stability
  assumption, and the obvious check is the one that fails silently. Gate on CONTENT (score sums, the
  detection count itself), and only on the tables the chunk actually depends on.
- **The plays endpoint doc is silent on the terminal play's score fields** (found 2026-08-10).
  `docs/api/endpoints/` records the `${uuid} at bat` trailing play as "1 per game, always last,
  empty final_details" — but not that it carries `0`/`0` with `did_score_change: false` normally,
  and the REAL final with `did_score_change: true` when the last PA was unresolved mid-scoring.
  **Why you should care**: that silence is the entire defect the §2 chunk fixes, and the doc as
  written invites the exact rule that would zero every score in the DB. One paragraph.
  **Still open after §2 landed (2026-08-11)** — the CODE now encodes the distinction
  (`PlaysParser._derive_final_score`'s docstring carries the three rejected rules and their
  evidence, and `.claude/rules/data-model.md` carries the column contract), but the ENDPOINT doc
  was not touched and still describes the trailing play without its score semantics.
- **FOUR test files hand-build a schema, so an ADDITIVE migration can red the suite from files no
  test-scope grep names** (found 2026-08-11, cost 9 failures across two rounds on migration `013`).
  `tests/test_report_plays.py`, `tests/test_loaders/test_game_dedup.py` and
  `tests/test_loaders/test_game_loader.py` each hand-LIST a migration subset (each entry added,
  with a comment, by the chunk that needed it), and
  `tests/test_migrations.py::TestE220UpgradeGuard` builds a synthetic pre-E-220 DB carrying just
  enough tables for every PENDING migration to apply before the guard fires. Adding two columns to
  `game_perspectives` broke three of them; the fourth (`test_game_loader.py`) was aligned
  preemptively because it writes `game_perspectives` too. **Why you should care**: the spec's
  test-scope grep selector named NONE of them, and the `test_game_dedup.py` breakage appeared only
  AFTER a review fix touched the merge seam -- so ONE full-suite run is not enough either; a chunk
  touching `migrations/` owes one per round. Everything else routes through
  `conftest.load_real_schema`, which GLOBS every numbered migration and needed no edit.
  **Open question, deliberately not answered blind**: should the three subsets just use the glob?
  `test_game_dedup.py` stops at 001+008 ON PURPOSE and layers `010` only where a test needs it, so
  a blind glob would silently change what those tests exercise.
- **`teams.classification` is unset on ALL 1,029 teams; `innings_per_game` is fetched for 66**
  (found 2026-08-10). **Why you should care**: any future segmentation by level (youth vs HS vs
  Legion) has no direct column to use — the §2 chunk's 2.5× youth skew rests on regulation-innings
  as a proxy over a 66-team basis. A real level analysis needs one of these backfilled first.
- ✅ **CLOSED 2026-08-10** — CI's whole-tree PII scan was RED on `main`, found by the scanner-hardening
  chunk's `/code-review` and NOT introduced by it. The 2026-08-09 dotfile widening made `.env.example`
  scannable and it carried three `email` matches, so CI's own command exited **123**, failing `ci.yml:95`
  under `pipefail`. **The operator ruling changed** — the earlier "LEAVE, no suppressor" was made against
  only half the consequence (it named the pre-commit hook, not CI). Fixed by remedy #1, changing the data:
  the FROM address moved to an RFC 2606 domain, and the two proxy-URL format comments to angle-bracket
  placeholders. Same command now exits **0**. Positive control: re-adding the old address returns RC=1, so
  the instrument still fires. **The lesson worth keeping**: a consequence stated for one gate is not the
  whole consequence — this ruling named the hook and missed CI, and nothing re-checked it for eight days.
- **`tests/fixtures/*.sql` are outside the scan surface and the residual below does not name them.** The
  `SCANNABLE_EXTENSIONS` gap recorded for `migrations/*.sql` also leaves `tests/fixtures/seed.sql`,
  `parity_consistent.sql`, and `recon_scoreboard_seed.sql` unscanned. **Why you should care**: seed fixtures
  are the higher-risk half — the plausible landing spot for a real player name or email, the same class that
  once put a real minor's name in a planning file.
- ~~**The `codex-spec-review` rubric is stale on spec Status.**~~ **CLOSED — fixed 2026-08-12**
  (`a7ef590` folded the fix: line 48 now lists all five statuses and calls a sixth a finding).
  Struck at audit 5 after the bullet was found still claiming to be open.
- **`.project/ideas/` is inert in `SKIP_PATHS`** (found 2026-08-10). No such directory exists — ideas live at
  `.project/specs/IDEAS.md`, history at `.project/archive/ideas/`. **Operator ruled 2026-08-10: LEAVE.**
  Unlike `epics/`, which can never return, this tree plausibly could, and the re-measured TN-2 noise
  rationale still covers it. Recorded so the next sweep does not re-discover it as a defect.
- ✅ **CLOSED 2026-08-10** — three PII-scanner residuals below (`--staged` rename blindness, the `-z`
  C-quoting bypass, the inert `epics/` entries) all landed in the scanner-hardening chunk. Spec moved to
  `.project/specs/done/`. **Four NEW residuals that chunk's five-arm review surfaced are recorded above** —
  read those, not these.
- **`pii_scanner.get_staged_files()` fails OPEN when git itself fails** (found 2026-08-10, `/code-review` +
  bare-headless). `except (CalledProcessError, FileNotFoundError): return []`, and `main()` then hits
  `if not file_paths: return 0` — printing NOTHING and exiting 0. Reproduced from a non-repo cwd: `rc=0`,
  silent. `.claude/hooks/pii-check.sh` reads exit 0 as "no PII found, allow the commit". **Why you should
  care**: this is the same fail-open class the unreadable-blob handler 100 lines below explicitly refuses —
  that path prints `REFUSING to certify clean` and exits non-zero; this one certifies clean silently. Not
  fixed in the hardening chunk because raising changes the contract for every caller and needs its own RED
  test and `/security-review`.
- **The git pre-commit hook scans the WORKING TREE, not the staged blob** (found 2026-08-10 by three of five
  review arms independently). `.githooks/pre-commit:107` pipes paths to `pii_scanner --stdin`, which routes
  `scan_files` → `scan_file` → `Path.read_text()`. Reproduced side by side: stage a token, blank the
  working-tree copy, commit → `Scanned 1 file(s), 0 violations`, rc=0, token in `HEAD`; the same path under
  `--staged` → `[PII BLOCKED]`, rc=1. **Why you should care**: `.claude/rules/pii-safety.md` advertises
  staged-blob reading as a scanner capability, and it is real — but ONLY in `--staged`, which is the agent
  PreToolUse hook. A human `git commit` does not get it. The byte-gate half of the hook judges the index
  correctly; it is only the pattern-scanner half that reads the working tree. This is a LARGER divergence
  than the flag drift the hardening chunk just closed.
- **A typechange (`T`) reaches zero PII gates, and empties the hook's staged set so the byte-gate is skipped
  too** (found 2026-08-10, `/security-review`, reproduced). Replacing a tracked symlink with a regular file
  scores `T`, which `--diff-filter=ACMR` drops on BOTH enumerations. Executed: a `T`-only staged set returns
  zero bytes → scanner rc=0 with no output, and in the hook `STAGED_ARR` is empty so it `exit 0`s at line
  100-102 **above** the byte-gate. **Why you should care**: the repo currently tracks no symlinks, so this
  needs a two-step sequence — that is what makes it a residual and not a live hole. Fix is `ACMRT` in both
  enumerations in ONE commit, or invert to `--diff-filter=d` so a future status letter defaults to *scanned*.
- **DISPUTED, owed an operator ruling: does removing `epics/` from `GATE_TREES` reduce coverage?** Codex
  (2026-08-10, P1) reproduced that with `epics/` gone from the gate, staging `epics/E-999-demo/epic.md` with a
  denylisted identifier now commits clean, and cites `AGENTS.md:8` still naming `epics/` as a work location.
  The counter-argument, which the spec and the prior operator ruling rest on: the tree is retired and deleted,
  nothing is under it, and keeping dead entries forever is the drift `CLAUDE.md` warns against. **Both are
  true** — the entry was doing LATENT work, and the session did not silently overrule the ruling. **Why you
  should care**: the real question is whether the byte-gate should gate ALL staged paths rather than a tree
  allowlist, which would moot the argument permanently. Decide the general form, not the `epics/` instance.
- **The inert `epics/` entries in the two security controls ride the scanner-hardening chunk.**
  `src/safety/pii_patterns.py` (`SKIP_PATHS`) and `.githooks/pre-commit:125` (`GATE_TREES`) both
  still name `epics/`. Neither can match — nothing can be staged under a tree that does not
  exist — so the 2026-08-09 docs sweep deliberately left them. **Why you should care**: they must
  move WITH `.claude/rules/pii-safety.md:50,52,54`, which restates `SKIP_PATHS` accurately as the
  code stands today. Editing either side alone breaks a doc/code agreement that is currently
  correct. Route them through the chunk that owns the `pii_scanner --staged` rename blindness
  below, which already owes a `/security-review`.

  **ROUTED 2026-08-10** — spec `2026-08-10-pii-scanner-hardening.md`, Status `READY`. ⚠ **The coupling claim
  above was AUDITED and is over-broad — do not execute it as written.** Only `:54` restates `SKIP_PATHS` and
  must move. `:52` is a section heading (cosmetic). **`:50` is REFUTED and must be LEFT ALONE**: its `epics/`
  mentions are historical provenance plus an illustration mirrored verbatim at `scripts/check_doc_pii.sh:57`,
  so editing it would CREATE the divergence this residual exists to prevent. The spec carries the evidence.
- **The runtime smoke check is not a named step in the `CLAUDE.md` lifecycle.** The 2026-08-09
  sweep retitled it to "Runtime Smoke Check" (`docs/admin/production-deployment.md`) and restated
  its trigger as operator-run before a commit touching a runtime or build-input surface — but
  nothing in the lifecycle tells the operator to run it. **Why you should care**: it used to fire
  automatically at epic closure, and that trigger is now deleted, so a real gate silently became
  opt-in. Wiring it into `CLAUDE.md` is a byte-cap trade (headroom is single-digit bytes as of
  audit 5 — see the cap bullet below for the current numbers), which principle I sends to the
  operator, not to a session.
- ✅ **CLOSED 2026-08-09** — `worktree-guard.sh` `CLAUDE_HOME` slash normalization. It was ~3 lines,
  not the 2 estimated; the empty case needed handling and had to DIVERGE from `REPO` (empty `REPO`
  denies, empty `CLAUDE_HOME` falls back to the literal default).
- ✅ **CLOSED 2026-08-09** — `codex-review` skill vs. first-party `codex review`. **Verdict: KEEP
  BOTH, they are not substitutes.** On one diff, four tools produced eleven findings with
  essentially ZERO overlap, and the two Codex paths failed in *characteristic* directions: the
  rubric-injected skill found the project-shaped defect (a fail-closed guard going silent), the
  uninstructed first-party path found the two a rubric would not prompt for (durable-state
  poisoning, and the already-cached-rows migration question). Dropping either would have lost real
  P1/P2/P3 findings. ⚠ Bound: ONE diff — this refutes "they are redundant", it is not a measured
  overlap rate. Feeds Migration Step 4.
- Residual one-sided game (both identifiers on the empty side) — needs a live probe.
- ✅ **SUPERSEDED 2026-08-10** — `.env.example` was SCANNED and carried three `email` matches (2026-08-09):
  our own `noreply@` service address plus two proxy-URL FORMAT comments, read and confirmed to hold no
  credential and no person's address. **The 2026-08-09 ruling was "LEAVE, no suppressor", and it named the
  consequence as only "staging `.env.example` will trip the hook."** That was half of it — CI's whole-tree
  scan was also failing, which nobody checked for eight days. **Ruling reversed 2026-08-10: reworded, still
  no suppressor**, by remedy #1 exactly as this bullet prescribed. The file now scans clean. What survives
  from the original: the three matches never were PII, and a `pii-ok` inside a credential template is still
  the wrong instrument.
- **The extensionless scan allowlist is a NAMED LIST** (`SCANNABLE_BASENAMES`, 2026-08-09). A NEW
  extensionless file stays unscanned until someone adds its basename. A shebang test cannot replace
  it: the scannability gate runs BEFORE the content read on both paths, and `Dockerfile` has no
  shebang anyway.
- **Still outside the PII scan surface entirely** (surfaced by the 2026-08-09 security review, not
  fixed): non-dotfile templates whose final suffix is unlisted
  (`docker-compose.override.yml.example`), and file types absent from `SCANNABLE_EXTENSIONS`
  (`migrations/*.sql`, `requirements.in`, `*.conf`). Widening the surface to those is a policy call,
  not a bug fix.
- **`/security-review` can be handed the WRONG DIFF on uncommitted work** (2026-08-09). Its
  `DIFF CONTENT` came from the COMMITTED range while `GIT STATUS` showed the working tree; since
  markdown findings are an excluded category, it would have returned a VACUOUS CLEAN over two
  modified security controls. Check the scope before trusting the verdict.
- **Pre-existing `opponent_links` rows with `resolution_method='search'` never see the season-year
  filter** — the terminality gate short-circuits them, so a pre-patch cross-year auto-match survives.
  **Operator ruled 2026-08-09: LEAVE.** Correctable via `bb report map-opponent`, and they die at the
  next data reset regardless. No invalidation, no migration.
- **Three doc sites overstate what `event_id` can do — carried here because no other live list
  has it** (probed live 2026-08-13 with positive controls; method and results pinned in
  `done/2026-08-13-same-listing-dedup-detection.md`, fact F2). `CLAUDE.md`,
  `.claude/rules/perspective-provenance.md`, and
  `docs/api/endpoints/get-teams-team_id-game-summaries.md` all describe the authenticated
  `game-summaries` `event_id` as the stable cross-perspective key. Probed on unmanaged teams:
  two teams that played each other carry fully DISJOINT event_id sets, and a double-listed game
  holds two distinct event_ids in ONE team's own list. Correcting the three sites is its own
  small chunk and owes an `api-scout` pass, because it edits an API doc.
- **CLAUDE.md byte cap: 12,032 as of audit-5 batch 2 (2026-08-16; number delegated to the
  trainer by the operator — "I trust you to raise the cap"), raised from 11,520 to fit the
  codex-required, review-scope, and handoff-rewording rulings; now ENFORCED MECHANICALLY by
  `.githooks/pre-commit` (`CLAUDE_CAP`), where the number lives and where a future raise is
  recorded.** Earlier steps: 11,264 → 11,392 (operator-ruled 2026-08-15), 11,392 → 11,520
  (operator-ruled 2026-08-16, approval-dies-with-its-commit). ⚠ **CORRECTION OF RECORD (audit 5)**: an
  earlier version of this bullet accused the 2026-08-15 session of raising the 11,264 → 11,392
  cap without bringing the operator the trade. **That was FALSE** — the session asked via a
  three-option question at 13:59 and the operator selected "Raise cap to 11,392" at 14:00:39,
  2026-08-15; the finding was an artifact of a transcript scan that cannot see question-box
  answers (the auditor trap now recorded in `tool-discipline.md`). The 2026-08-16 "blessing"
  re-affirmed a cap already legitimately ruled. Real residual: **no hook or script enforces the
  cap** — it is checked by sessions reading this bullet. Per principle I the cap remains a
  TRIPWIRE, not a wall: when it binds against **load-bearing** content, STOP and bring the
  operator the specific trade — never compress meaning to fit, never raise the cap unilaterally.
  The original 8KB cap was raised by operator decision during the Step 1 review, after it proved
  to be trading against the file's own acceptance criterion: meeting 8192 had squeezed out the
  per-rule pointer enumeration, the `bb` command groups, the session-token sensitivity rule and
  more, and the compression itself introduced prose defects. Keep measuring it — the point of the
  cap was to stop the drift back toward a 20KB always-on file, and that point still stands.
- **`.claude/` is ungated for PII by BOTH instruments.** `SKIP_PATHS` blinds the pattern scanner
  to it even when files are passed as explicit arguments — verified 2026-08-06 by copying a
  known-bad file under `.claude/`, where it returned RC=0 and printed nothing, versus RC=1
  outside. And `scripts/check_doc_pii.sh .claude` exits 1 today on pre-existing content in
  `agent-memory/`, four agent definitions, and `data-model` / `gc-uuid-bridge` / `pitch-rules`.
  That state predates this chunk and is consistent with the "identifiers are fine where they
  anchor evidence" scoping, but it means a `.claude/` write gets no automatic PII coverage: scan
  it by hand, and note that a silent RC=0 there is vacuous, not clean.

- **`pii_scanner.py --staged` is BLIND TO RENAMES** (found 2026-08-08, Step 3). `src/safety/
  pii_scanner.py:320` enumerates with `--diff-filter=ACM`; the pre-commit hook enumerates `ACMR`.
  Measured on the Step 3 commit: ACM 17 paths vs ACMR 284 — **267 renames invisible**, including a
  move-AND-edit git scored `R099`. The HOOK is unaffected, so committed content is still gated; the
  gap is in the by-hand command CLAUDE.md step 6 tells every session to run. Same defect class
  `.claude/rules/pii-safety.md` already records as a live bypass for the frozen-archive gate. A
  one-line fix that touches a security control — give it its own spec and a `/security-review`.

  **ROUTED 2026-08-10** — spec `2026-08-10-pii-scanner-hardening.md`, Status `READY`. Two corrections to the
  above. The citation **`:320` has drifted to `:353`** (the file grew when the extensionless fix landed
  2026-08-09). And it is **not** a one-line fix: the same function has a SECOND documented bypass — no `-z`,
  so a C-quoted path names no readable file — which the operator ruled rides along, so the chunk is two fixes,
  two RED tests, and the `epics/` removals above. It also reaches further than "the by-hand command":
  `.claude/hooks/pii-check.sh:35` runs `--staged` as a PreToolUse gate on **every agent commit**.
- **A `git mv` into `specs/done/` strands pointers.** Step 3 moved seven specs and stranded six
  references across four live specs; two were repointed (path-shaped / "See" navigation), four
  provenance records were left as written per the criterion-vs-evidence rule. Any future `done/`
  move owes the same sweep — the retired archive-refs gate used to catch exactly this class.

### Accepted residuals from Step 2

- ✅ **CLOSED 2026-08-09** — the PII scanner's blindness to EXTENSIONLESS files (`Dockerfile`,
  `.githooks/pre-commit`), fixed with a named-basename allowlist. The fix found a SECOND hole the
  residual had not named: `Path.suffix` lies about dotfiles carrying a further suffix, so the
  TRACKED `.env.example` and `proxy/.env.example` were unscanned too — the likeliest files in the
  repo to receive a real token by copy-paste. Both classes are now scanned, proven a strict
  widening (0 narrowings over 36,932 synthetic paths and 2,485 tracked files, against a control
  that produced 1,680).
- **`.project/archive/`, `.project/research`, `.project/decisions`, `reviews/` keep role names and
  pre-freeze `epics/` paths.** Historical records, not pointers — they stay as written. The frozen
  `epics/` and `ideas/` trees moved under `.project/archive/` on 2026-08-08 and are history:
  salvage on demand, never bulk-migrate.
- ✅ **CLOSED 2026-08-09** — the `codex-review`-vs-`codex review` comparison, owed since Step 2 and
  carried (not dropped) at Step 3. Verdict and its bound are in STANDING RESIDUALS above.

Closed by Step 3 (2026-08-08): the `codex-spec-review` triad now takes a spec FILE path and emits a
`RESULT_FILE` receipt; the four epic/story/spike/idea templates are gone, replaced by one
`spec-template.md`; the archive-refs gate is retired (script, test, hook stanza, ops-doc section) —
it had become permanently unsatisfiable, since it swept the working tree including gitignored
`.codex-home/` Codex transcripts that regenerate on every `codex exec` run.
