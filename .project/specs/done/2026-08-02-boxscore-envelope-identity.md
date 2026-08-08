# Boxscore envelope identity — stop discarding the opponent

**Date:** 2026-08-02 · **Source:** `.project/research/ingestion-fidelity-seed.md` §1
**Status:** COMPLETE — code committed (`10c32f3`), dev-DB backfill done 2026-08-03

## Goal

`GameLoader._detect_team_keys` classifies boxscore envelopes by **key shape** — "our team
is the slug, the opponent is the UUID". That inference holds only when the opponent has
no public GameChanger presence. When they do, GC keys their envelope with a `public_id`
slug too, so `uuid_keys == []` → `opp_key = None` → the opponent's entire batting and
pitching envelope is never read.

Make the classification **identity-based**, and make an unclassifiable 2-key payload an
*error* instead of a silent absence. Then backfill the dev DB by regeneration.

It is silent at every layer today: the only record is a `logger.debug`, the caller's
error path requires *both* keys `None`, the read site is a bare `if opp_data:`, and
nothing increments `LoadResult.errors` — so the E-236 stage classifier reports
`completed`.

Fixing this also heals the `Unknown Unknown` opponent players on the affected games
(~11/game as measured 2026-07-26), because `ensure_player_row` prefers the longer name
and the boxscore `players` array is the only path that names opponents today. Free side
effect, not separate work.

**Population, stamped — these move, so re-measure rather than reusing them.**
The seed measured 29 one-sided games of 228 completed (12.7%) across 5 scouted teams
@ 2026-07-26. Re-measured @ 2026-08-02: **73 one-sided of 928 completed, across 16
scouted teams.** The seed's figures are evidence of a past state, not today's targets.

## Files

- `src/gamechanger/loaders/game_loader.py` — rewrite `_detect_team_keys` (`def` at
  `:1121`; defect at `:1139-1140`) as an identity ladder; surface the unclassifiable
  2-key case as an error; correct two false prose sites (the comment ending "the opponent
  then simply has no per-player stat rows (truthful)" at `:653`, and `_resolve_team_ids`
  docstring item 2 at `:781-783`). Both claim the absent opponent block is "truthful";
  both are false in the all-slug case, where the block was present and discarded.
- `tests/test_loaders/test_game_loader.py` — the new cases below.
- Nothing else. **`is_gc_uuid` (`src/gamechanger/url_parser.py`) is correct and must not
  change** — it is a canonical seam with three collapsed call sites and load-bearing
  anchoring. The predicate is right; the inference built on top of it is wrong.

## Design

Ladder, in order, inside `_detect_team_keys`:

1. **`public_id` exact match** (case-sensitive, as GC emits it) → that key is `own_key`.
2. **`gc_uuid` match** (case-insensitive) → that key is `own_key`. This generalizes the
   existing all-UUID branch, which today hides behind `own_key is None` (`:1144`) and so
   never fires in the all-slug case.
3. **In a 2-key payload, once one key is identified the other IS the opponent** —
   regardless of either key's shape. Never leave `opp_key` `None` in a 2-key payload.
4. **Shape inference survives only as a last-resort fallback**, when neither identifier
   is available, and logs a **WARNING** (not `debug`) when it fires.
5. **A 2-key payload that yields no `opp_key` is an error condition** — increment
   `LoadResult.errors` so the stage classifier surfaces it. A discarded envelope must
   never again be indistinguishable from an opponent who never used GC scorekeeping.

`LoadResult.errors` over a dedicated counter is deliberate: the classifier is
error-driven by design, and after this fix the unclassifiable case is genuinely rare
(neither identifier resolves *and* shape cannot split), so it will not mark healthy runs
degraded.

**This also closes the latent ordering hole (seed §1.6).** `own_key = slug_keys[0]`
selects by JSON insertion order, not identity, so an all-slug payload serialized
opponent-first loads the opponent's stats **as ours** — silent misattribution, strictly
worse than absence. Not currently occurring (in all 29 games affected @ 2026-07-26 the
loaded side's pitching R equalled the opposing final score, 29/29), but that is an
empirical regularity, not a contract. Identity-based classification makes insertion
order irrelevant.

## Out of scope

- Seed §2 (game-ending run dropped on a skip path), §3 (`team_players` fetched and
  thrown away), §4 (score-only game labeling). Separate chunks. §4 must sequence *after*
  this one — until then its zero-stat-rows signature overlaps this defect's symptom.
- Any change to `is_gc_uuid` or its regex.
- Historical repair beyond what regeneration does as a side effect. Operator ruling
  (2026-07-27): *"We can reset all prod data. We don't have to repair anything
  historically. We only need to ensure we are accurate moving forward."*
- Prod. The standing prod sequence is rebuild → reset → re-scout, which repopulates from
  the API on a fixed classifier and moots any prod backfill.
- Discriminating a *discarded* envelope from a *genuinely absent* one on the residual
  population — that needs live API probes. Worth doing on a handful later; not here.

## Hard constraint — user accounts, and the ONE way access can still be lost

**No `bb db purge-scouting`, no `bb db reset`, no `bb report cleanup`.** Users are not
easy to recreate right now, and neither is their team access.

- **`users` rows are never touched.** Neither the code change (confined to
  `game_loader.py` and its tests) nor `bb report generate` deletes from `users`.
- `purge-scouting` preserves the 7 identity/auth tables, so logins survive — but it
  **wipes `user_team_access`** (`src/db/purge_scouting.py`), and every grant would have
  to be re-issued by an admin. Not part of this chunk under any circumstance.
- ⚠️ **`bb report generate` CAN delete `user_team_access` rows.** The path is
  `_cleanup_orphans` (`src/reports/generator.py:2425`) → `cleanup_orphan_teams`
  (`src/reports/lifecycle.py:765`) → `_delete_team_scoped_data` (`:668`), which executes
  `DELETE FROM user_team_access WHERE team_id IN (...)` at **`lifecycle.py:687`**.
  The `user_team_access` reachability root documented in
  `.claude/rules/canonical-seams.md` protects `reclaim_orphan_reference_data` — a
  **different** sweep. It does not protect this one.
- **Blast radius is narrow but real.** `_compute_orphans` (`generator.py:2414`) sets
  `orphan_ids = created_team_ids - {report team}` — only teams *this run INSERTed*. The
  loss case is a grant attached to a freshly-created opponent stub before cleanup runs.
  Measured `user_team_access`: **0 rows @ 2026-08-02** (1 user), so the live risk is
  currently empty — but step 2 of the backfill re-checks rather than trusting that.
- The backup in step 1 is the recovery path if any of the above turns out to be wrong.

## Verification

**New tests** in `tests/test_loaders/test_game_loader.py`:

- All-slug 2-key payload → own/opp split correctly by `public_id`; the opponent envelope
  is read (not `None`).
- The same payload with the **opponent key first** in insertion order → still correct.
  Pins the ordering hole; must fail against today's code.
- 2-key payload where neither key matches `public_id` or `gc_uuid` → shape fallback
  fires, WARNING logged.
- 2-key payload with no identifiable own key *and* no shape split → `LoadResult.errors`
  incremented (the absence is no longer silent).

**Must stay green, unchanged:**

- `test_detect_team_keys_classification_byte_identical` (`:906`) — the E-247 hard gate.
  All 3 parametrize cases pass on the identity ladder **without re-baselining**: cases
  1–2 match rung 1 (the fixture's `_OWN_TEAM_SLUG` `public_id`), case 3 matches rung 2 (its
  expected own key `team-uuid-jv-001` *is* the fixture's `gc_uuid`, via `_make_loader`).
  This is the conscious resolution of the seed's §1.9 fixture warning. **If any expected
  value in this test needs editing, stop — the ladder is wrong, not the gate.**
- `test_detect_team_keys_uuid_only_gc_uuid_none` (`:839`).
- `tests/test_player_line_reconcile.py::test_absent_opponent_block_leaves_an_observable_uncovered_residual`.

No existing test pins the buggy behavior, so the fix is free to change it.

**Command:** `python -m pytest tests/ > /tmp/out.txt 2>&1; echo "RC=$?" >> /tmp/out.txt`,
then read the file. **Never pipe pytest** — a piped exit code is the pipe's, not
pytest's. Full suite green before commit.

### Backfill (dev DB) — only after the suite is green

1. `python3 scripts/backup_db.py` — snapshot before any mutating pass. Non-negotiable;
   regeneration hard-deletes.
2. `SELECT COUNT(*) FROM user_team_access` — record it. If **0**, the access risk above
   is empty. If non-zero, dump the table first so any grant lost to orphan cleanup can
   be re-issued from the dump.
3. Run the detection query and record the number **with its date** (`73 @ 2026-08-02`).
   Never carry a bare figure forward — it moves on every re-scout.
4. Derive the affected scouted teams by joining the affected `game_id`s through
   `game_perspectives` to `teams.public_id` (**16 @ 2026-08-02**). Re-derive; do not
   assume the count.
5. Regenerate one report per affected `public_id`, **one at a time**, re-reading the
   count between runs so a regression is attributable to a single team.
6. Read the count again. **Expect a large decrease, NOT zero.**

⚠️ **Zero is the wrong target, and the seed is wrong to name it.** The `(h>0) <> (a>0)`
query matches *any* one-sided game, and a genuinely one-sided game is the **modal
opponent-scouting case** — an opponent who never used GC scorekeeping has no envelope to
discard. `tests/test_player_line_reconcile.py::test_absent_opponent_block_leaves_an_observable_uncovered_residual`
pins exactly that shape and requires the residual stay observable. The query is a
**population heuristic, not a defect-specific proof**. The verdict is the *decrease*,
plus no game getting worse.

Detection query (seed §1.4), before and after:

```sql
WITH sides AS (
  SELECT g.game_id,
    (SELECT COUNT(*) FROM player_game_batting b WHERE b.game_id=g.game_id AND b.team_id=g.home_team_id)
   +(SELECT COUNT(*) FROM player_game_pitching p WHERE p.game_id=g.game_id AND p.team_id=g.home_team_id) h,
    (SELECT COUNT(*) FROM player_game_batting b WHERE b.game_id=g.game_id AND b.team_id=g.away_team_id)
   +(SELECT COUNT(*) FROM player_game_pitching p WHERE p.game_id=g.game_id AND p.team_id=g.away_team_id) a
  FROM games g WHERE g.status='completed')
SELECT COUNT(*) FROM sides WHERE (h>0) <> (a>0);
```

⚠️ **`bb report generate` is DESTRUCTIVE** — reconcile-at-load can hard-delete `games`
and their entire child surface; orphan reclamation can hard-delete unreachable
`teams`/`players`/`team_rosters`. Regeneration is never read-only or purely additive.
(Restoring opponent rows only *adds*, so E-276's health gate — which protects retires —
will not trip.)

**Instrument caveat (seed §8):** `bb report reconcile-scoreboard` is the standing
plays-vs-boxscore diagnostic, but ~180 lines of retired ratchet machinery still live in
`src/reports/recon_scoreboard.py` (`load_baseline`, `evaluate_gate`, `write_baseline`,
`GateResult`, from `:492`). This chunk does **not** depend on that instrument — the
detection-query decrease is the verdict. If a reading from it is used anyway, first
confirm which code path the CLI actually runs, and do **not** `--update-baseline`.

## Execution order

1. Rewrite `_detect_team_keys` as the identity ladder; correct the two prose sites.
2. Add the four new tests; confirm the opponent-first ordering test fails pre-fix.
3. Full suite green (unpiped RC), then commit — `[pii-hook] PII scan passed.` must
   appear in the output. Operator approves the commit.
4. Backfill steps 1–6 above.
5. Update the progress log with before/after figures, each stamped with its date.

## Progress log

- **2026-08-02** — Spec written. Codex spec review run: 3 findings, all independently
  verified and folded in — (a) the false "nothing touches user access" claim corrected
  against `lifecycle.py:687`, (b) the seed's 29/228/5-team figures re-measured to
  73/928/16, (c) "expect 0" retired as an unsound target. Implementation not started.
- **2026-08-02** — Execution steps 1–3 (code). `_detect_team_keys` rewritten as the
  identity ladder; the unclassifiable 2-envelope case now counts into
  `LoadResult.errors` via `discarded_opponent_error` in `_load_boxscore_data`; both
  false "truthful" prose sites corrected. Four new tests added; all four confirmed
  **failing against pre-fix source** (backed up and restored via scratchpad, restore
  verified byte-identical) — the opponent-first case failed on
  `own_key == 'z81QpLmv7BXK'`, i.e. the ordering hole is real, not just latent.
  The three must-stay-green tests were re-run **by exact node id** (a renamed test
  cannot fail a suite): all PASSED, and the `tests/` diff is **purely additive** —
  no expected value in the E-247 byte-identical gate was edited, which is this
  spec's own signal that the ladder is right. Full suite: **4403 passed, RC=0
  @ 2026-08-02** (unpiped).
- **2026-08-02** — `/code-review`: **6 findings, all 6 accepted and fixed.** Each was
  re-verified against the repo before acting; findings 1, 2 and 6 were confirmed by
  re-running the new tests against the pre-remediation source (backed up and restored
  via scratchpad, restore verified byte-identical).
  - **1 (HIGH)** — the guard detected classification failure and then loaded anyway,
    attributing an envelope by insertion order. Confirmed: the opponent's line landed
    under **our** `team_id`. **Fixed by refusing the payload** (`return
    LoadResult(errors=1)`) instead of counting-and-continuing.
  - **2 (HIGH)** — the guard was one-sided: an unnamed OWN key left `errors == 0`, so
    `classify_stage_status` reported `completed` while our envelope was filed under the
    opponent's id — the more damaging direction and exactly the silence this chunk
    exists to end. Confirmed (`assert 0 == 1`). **Guard is now symmetric** and reads
    `len(raw) >= 2 and (own_key is None or opp_key is None)`.
    ⚰ **RETIRED 2026-08-03** — this entry also claimed the `>= 2` form *"covers a
    3-key payload the `== 2` literal missed."* **Overstated.** It covers a 3-key
    payload ONLY in the sub-case where a key is unresolvable. Executed: a 3-key
    payload resolving at rung 1 returns `(<own slug>, 'aaaaaaaa-…')` — both keys
    non-`None`, so the guard does not fire and the THIRD envelope is dropped in
    silence. Bounded: the endpoint doc specifies exactly 2 keys, and the pre-change
    code dropped extras the same way, so this is not a regression — but the coverage
    claim was wrong and is withdrawn.
  - **3 (MEDIUM)** — the E-247 hard gate went **vacuous**: the ladder resolves all
    three of its cases at rung 1/2, so `is_gc_uuid` is never called. Mutation-proven
    here with a positive control: predicate stubbed always-False → old gate passes
    3/3, new `test_shape_fallback_classification_is_driven_by_the_uuid_predicate`
    fails. This corrects a claim in the entry above: "the gate stays green without
    re-baselining" was true and *was* the right signal that the ladder is right, but
    it is NOT evidence the gate still protects anything. The anchoring/IGNORECASE
    cases are re-pinned on the rung-4 fallback, the one path that still uses the
    predicate.
  - **4 (MEDIUM)** — the **module docstring** still asserted the shape rule, 1150
    lines above its own refutation. A third prose site; this spec's Files list named
    only two. Corrected.
  - **5 (LOW)** — `docs/api/endpoints/get-game-stream-processing-event_id-boxscore.md`
    still *prescribed* shape detection in both the `caveats:` block and the Response
    section. **Scope deviation, flagged:** this spec says "Files: … Nothing else."
    Fixed anyway — the doc of record was instructing the next consumer to rebuild the
    defect. The factual observation about key forms is preserved; only the detection
    recipe changed, per the API-doc-fidelity rule. `scripts/check_doc_pii.sh docs/api`
    → PASS (REAL mode, 36 patterns, 0 matches).
  - **6 (LOW)** — the rung-4 WARNING fired on an empty `{}` payload, raising a second
    alarm for one benign 200. Guarded on non-empty keys; the fallback's early `return`
    (which also skipped the debug trace) is gone, so there is one exit again.
- ⚠️ **Deviation from this spec's rung 5, deliberate.** Rung 5 as written says
  *increment `LoadResult.errors`*, which reads as count-and-continue; findings 1–2
  showed that continuing means guessing. The chunk now **refuses** the payload. It
  still satisfies rung 5's stated purpose (the discard is no longer indistinguishable
  from an unscored opponent) and follows this spec's own ruling that misattribution is
  *"strictly worse than absence"*. **This does NOT shrink the backfill population**:
  the ~73 affected games match our `public_id` at rung 1, so they classify and load
  normally — refusal fires only when NEITHER identifier matches any key, which is rare.
- Full suite after remediation: **4408 passed, RC=0 @ 2026-08-02** (unpiped).
- **2026-08-03** — Codex review (second opinion). **One P1, accepted**: three sites in
  `docs/api/endpoints/get-game-stream-processing-event_id-plays.md` and three AC-6
  labels in the test file still documented the retired shape contract. All six read
  literally and confirmed before acting (grep finds candidates; only a Read rules).
  **Codex's citation list was not the whole worklist.** Sweeping the retired claim
  properly surfaced **10 more carriers Codex did not cite**, in `docs/api/flows/`,
  `.claude/rules/architecture-subsystems.md`, and four agent-memory files — including
  **three separate sites in one file I had already edited twice**, the partial-ruling
  shape. The last of those was found only by the **verify-by-ABSENCE** pass (grep the
  FALSE forms, require zero), not by confirming the corrections had landed.
  Verdicts on every surfaced line, including no-change:
  - **FIXED (16 sites, 10 files)** — every PRESCRIPTIVE carrier, i.e. any line telling
    a reader how to decide which key is which.
  - **NO CHANGE — different asymmetry**: the player-stats / spray endpoint team-scope
    asymmetry, the doubleheader "asymmetric hazard", baseball-coach's "asymmetric
    detectability". Same token, unrelated claim.
  - **NO CHANGE — evidence, not criterion**: `boxscore-empty-shape.md` (two dated live
    captures), `tests/fixtures/e2e_degraded/README.md` (what the fixture contains),
    `ingest-workflow-log.md` (a historical record of past integrations). These report
    what was OBSERVED; correcting them would destroy records.
  - **NO CHANGE — correct tombstone**: `game_loader.py:16` quotes the retired rule with
    the retirement marker FIRST, so the grep hit is the retirement, not residue.
  - **NO CHANGE — still true**: `perspective-provenance.md:44` (the keys genuinely ARE
    perspective-specific).
  **The plays path had no CODE defect** — `plays_parser.parse_game` never reads
  `team_players` (only its docstring names it), and the documented consumer builds a
  flat lookup across both keys. The P1 was a prospective documentation hazard, not a
  live bug; stated here so nobody re-derives a data-loss claim from it.
- ⚠️ **Second scope deviation, flagged.** This spec says "Files: … Nothing else"; the
  sweep touched 10 files across `docs/api/`, `.claude/rules/`, and `.claude/agent-memory/`.
  Only the retired claim was rewritten — no verdict, rating, or unrelated prose moved.
- Gates after the sweep: full suite **4408 passed, RC=0 @ 2026-08-03** (unpiped);
  `check_doc_pii.sh docs/api` PASS (REAL, 36 patterns, 0 matches); API-doc validator
  51 passed.
- **2026-08-03** — Adversarial scour workflow (4 lenses → skeptic per finding).
  **15 raised, 3 survived refutation, 5 refuted, 7 left unverified by a deliberate
  2-per-lens cap** (the cap is logged, not silent). Of the 7 capped, 3 were checked by
  hand here and fixed; the rest are recorded below rather than dropped.
  - **⚠️ CORRECTION to the entry above.** That entry claims *"FIXED (16 sites, 10 files)
    — every PRESCRIPTIVE carrier."* **That is false.** `docs/api/flows/opponent-scouting.md`
    still carried a runnable `Detection algorithm:` python block splitting own-vs-opponent
    by UUID regex — four lines under the heading the same sweep renamed to "Boxscore keys
    (identity, not shape)", contradicting two lines the same sweep authored above it.
    Executed verbatim it raises `StopIteration` on an all-slug payload (no `next` default)
    and silently inverts own/opponent when the scouted team is UUID-keyed. **Why the
    absence-grep missed it: the block is CODE and carries none of the prose tokens** —
    the doc-sweep rule's executable-consumer clause, *"a prose sweep structurally cannot
    see code that still PARSES."* Replaced with an identity-based recipe that names
    `_detect_team_keys` as canonical. **Fourth site in a file already edited three times.**
  - **The refusal's withheld vouch was unpinned.** No test in the repo referenced
    `processed_event_ids` (0 matches). Moving *only* the new guard below the vouch leaves
    the game refused but self-vouching, flipping `boxscores_complete` True and letting
    `retire_absent_games` HARD-DELETE the canonical row and its whole child surface — the
    agent executed that delete. The sibling `(None, None)` return had a guardian test; the
    new guard had none. Both refusal tests now assert the event id is absent from
    `processed_event_ids`. Mutation-proven, per-test: guard-below-vouch → both refusal
    tests FAIL (control 92 passed).
  - **Rung 2's case-fold was unpinned.** Swapping it to rung 1's exact compare left the
    full suite green while a casing-differing UUID key drops to rung 4 and SWAPS own for
    opponent at `errors == 0`. Added
    `test_rung_two_matches_gc_uuid_across_a_casing_difference`; mutant → that one test
    FAILS, alone. Also **retracted an unevidenced claim I authored**: the comment said
    *"GC emits both casings"* — 0 of 28 stored gc_uuids and 0 of 447 captured UUIDs are
    non-lowercase. The fold is kept as DEFENCE and now says so.
  - **Three capped findings verified by hand and fixed** (stale mechanism prose the earlier
    sweep never reached, because it covered `docs/`, `.claude/` and one test file only):
    the E-247 gate's own comment still claimed to pin the uuid/slug split it no longer
    exercises; `test_player_line_reconcile.py` explained a branch split as slug-vs-UUID;
    and **my own `architecture-subsystems.md` edit gave a FALSE MECHANISM for a true
    conclusion** — it credited the flat lookup dict, when in fact `plays_parser.parse_game`
    never reads `team_players` at all. Class A: false premise under a correct conclusion,
    authored in the very sweep meant to remove such claims.
  - **Refuted, and worth recording so they are not re-raised**: the `len(raw) >= 2` bound
    does NOT open a 1-key hole (pre-change code behaved identically — the bound CLOSED a
    subset, it did not open one); the rung-3 docstring clause is scoped by its own
    antecedent and item 4 documents the exception; and "one refused boxscore disables the
    team-season retire" is the documented, pre-existing, deliberate `boxscores_complete`
    posture, not new in kind.
  - **Still unverified (cap), recorded not dropped**: one MEDIUM — the `len(raw) >= 2`
    boundary has no test for the single-unmatched-envelope case (related to a refuted
    finding, so likely pre-existing behavior rather than a regression) — plus LOW-rated
    stale-comment claims in `test_game_grain_reconcile.py`.
- Gates after this pass: full suite **4409 passed, RC=0 @ 2026-08-03**; doc-PII PASS
  (REAL, 36 patterns); API-doc validator 51 passed.
- **2026-08-03** — Second `/code-review`. It scoped WIDER than this chunk
  (`origin/main...HEAD`, which includes the already-committed worktree-guard rewrite and
  PII SKIP_PATHS narrowing). Three of its five findings are about those commits, not this
  chunk; they are reported to the operator and NOT actioned here. Two are this chunk's:
  - **Overstated `>= 2` coverage claim — CORRECTED** (see the retired clause above).
    Executed and confirmed: a 3-key payload resolving at rung 1 leaves both keys non-`None`,
    so the guard cannot fire and the third envelope is dropped silently. A comment at rung 3
    now records the behaviour. Not a regression (pre-change code dropped extras too).
  - **Rung-4 shape fallback still guesses on a slug+UUID split — ACCEPTED AS RESIDUAL,
    not fixed.** When neither identifier matches and the shapes DO split, both keys come
    back non-`None`, the guard does not fire, and the load completes at `errors == 0` on a
    shape guess; if our envelope were the UUID key and the opponent held the slug, both
    would be filed under the wrong team. Reasons for leaving it: (a) this spec explicitly
    preserves rung 4 as the last-resort fallback, so refusing there is a design change, not
    a fix; (b) the same claim's stronger form was REFUTED by an independent skeptic on
    reachability, and this reviewer reached the same mitigation independently — all
    perspective teams carry both `public_id` and `gc_uuid`, so rung 1/2 resolves in
    practice; (c) the pre-change code guessed by shape ALWAYS, so this is a narrowing, not
    a new hole. **Recorded as a known defensive gap for the operator to rule on, not
    silently closed.**
- Gates: full suite **4409 passed, RC=0 @ 2026-08-03**.

- **2026-08-03** — **Backfill steps 1–6 COMPLETE.** All figures stamped; none reused.
  1. Backup `data/backups/app-2026-08-03T023142.db`, byte-size verified against source.
  2. `user_team_access` = **0 @ 2026-08-03**, re-checked rather than trusting the stamped
     value. Pre-existing (measured 0 on 2026-08-02, before this session), so the
     grant-loss path was empty and no dump was needed.
  3. BEFORE: **73 one-sided of 928 completed @ 2026-08-03**.
  4. Affected scouted teams re-derived: **16 @ 2026-08-03** (matches the spec's figure);
     **0** affected games had a NULL-`public_id` perspective team, so all were reachable.
  5. 16 regenerations, ONE AT A TIME, count re-read between each. A rail was added beyond
     the spec: abort if the count ever INCREASED. It never fired — **all 16 deltas ≤ 0**
     (largest single −11; one team 0), rc=0 on all 16.
  6. AFTER: **1 one-sided of 974 completed @ 2026-08-03.**
  **The decrease is RECOVERY, not deletion** — checked explicitly, because a deleted game
  leaves this query exactly the way a repaired one does. The denominator GREW: completed
  games 928 → 974, `player_game_batting` 19,277 → **21,254 (+1,977)**,
  `player_game_pitching` 4,378 → 4,826, `plays` 57,388 → 60,531, `teams` 475 → 487.
  `users` 1 and `user_team_access` 0 both unchanged.
- ⚠️ **This REFUTES the population claim this spec inherited from the seed.** The spec
  argues zero is the wrong target because *"a genuinely one-sided game is the modal
  opponent-scouting case."* The TARGET reasoning was right — we did not reach zero and
  must not chase it — but **the population estimate behind it is wrong for this DB**: of
  73 one-sided games, ~72 were DISCARDS, not genuine absences. The single residual is not
  the predicted shape either: its empty side carries BOTH a `public_id` and a `gc_uuid`,
  so it is not an opponent who never used GameChanger. Most likely a scored-but-empty
  boxscore (envelope present, nothing charted) — legitimate and unrecoverable.
  **Do not re-derive a "most one-sided games are genuine absences" claim from this spec.**
- Confirming which it is needs a live API probe, which this spec puts out of scope
  ("worth doing on a handful later"). One game is that handful — the natural follow-up.
- **Status: this chunk is COMPLETE.** Code committed (`10c32f3`); dev-DB backfill done.
  Prod is out of scope by the spec (standing sequence is rebuild → reset → re-scout).
