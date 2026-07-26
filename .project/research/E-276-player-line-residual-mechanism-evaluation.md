# E-276 — Player-Line Residual: Candidate Mechanism Evaluation (R1)

**Date**: 2026-07-26. **Author**: software-engineer (SE-R1), consultation mode, pre-dispatch.
**Status**: reference record. **Outcome**: operator ruled **diagnostic only, no gate** — no cap, no
churn-signature gate, no `extra_guard` is adopted on the player-line grain; nothing refuses a retire
that today permits one.

**data-engineer (DE-R1) evaluated the same three candidates independently and differed on one point:
it would have GATED the fork population where this evaluation would only WARN.** Nothing further about
DE's reasoning is represented here — this author has not read DE's report.

## What this file is

R1 asked whether the player-line one-run window could be **closed** rather than characterized, by one
of three candidate mechanisms. It could not. The verdicts are executed, not argued, and the harnesses
that produced them live in an ephemeral session scratchpad. Several measured figures now govern
fixtures an implementer will build (story 01 AC-14), so the evidence is recorded here to outlive the
scratchpad.

**Selector**: measured numbers and the executed lines that produced them. Not a narrative of the
session.

---

## 0. Method

All results are driven through the **real** `ScoutingLoader.load_team` → `GameLoader` path against
synthetic SQLite DBs built from `migrations/` in a temp dir. `data/app.db` untouched; no network.

The corrected gate (story 01) does not exist in `src/` yet, so the harness carries a prototype
(`retire_v2`) and injects it by subclassing `GameLoader` and rebinding
`scouting_loader.GameLoader`. The prototype's shape:

- **capture anchor** — override of `_upsert_game_and_stats`, snapshotting
  `{(table, team_id): {player_id}}` for the game + perspective **before any of that game's stat
  writes**;
- **gate population** = the snapshot; **classification universe** = the live prior read (story 01
  AC-9b);
- vacuous permit on `prior_count == 0` (AC-6);
- candidates composed as `extra_guard`, except (c) which only logs.

### ⚠️ Where the defect actually is — the precise form, because the imprecise one circulates

The defect is **not** "the loader reads its prior set late". It is: **the helper
`_prior_line_player_ids` (in `src/db/reconcile_at_load.py`) reads a population that the loader
(`_upsert_game_and_stats` in `src/gamechanger/loaders/game_loader.py`) has already mutated.** Two
modules, and the read is correct where it sits — it is the *population* that is wrong.

This matters for anyone chasing it by line number. The reconcile *call* is at `game_loader.py:680`
(the two `_load_team_stats` upserts are at 662 and 667); the polluted read is one module down. The
"loader reads at ~:679" form has been circulating in this epic's prose since the original handoff and
is corrected here.

Fixture vocabulary used throughout:

| Term | Meaning |
|---|---|
| **detectable churn** | new `player_id`s, IDENTICAL names — `find_duplicate_players` prefix-matches them, so `dedup_team_players` merges |
| **undetectable churn** | new `player_id`s, names sharing no prefix in either direction (`Mike`→`Michael`, `Bob`→`Robert`, `Peggy`→`Margaret`) — dedup detects nothing |
| **genuine removal** | lines vanish from the boxscore, no new ids at all |
| **regime A / regime B** | the two behaviours in §3; the names are used by story 01 AC-14 |

---

## 1. Baseline mechanics (`drv1_baseline.py`)

Confirms the defect, the fix's effect, and **two ways the epic's own player-line grain-table row is
false**. That row reads: *"the dedup sweep closes the one-run window in both dominant shapes."*

```
B0 -- TODAY'S CODE, identical-name re-issue
  run1: rows=9   run2: rows=9   originals surviving: 0

B1 -- corrected gate, identical-name re-issue, OWN block
  rows per run: [9, 9, 9, 9]   originals surviving: [9, 9, 9, 9]
   run2 gate: prior=9 comparable=0 permit=False absent=9 retired=0
   run3 gate: prior=9 comparable=0 permit=False absent=9 retired=0

B2 -- corrected gate, re-issue with NON-prefix name change
  rows per run: [9, 18, 9, 9]   originals surviving: [9, 9, 0, 0]
   run2 gate: prior=9  comparable=0 permit=False absent=9 retired=0
   run3 gate: prior=18 comparable=9 permit=True  absent=9 retired=9

B3 -- corrected gate, identical-name re-issue, OPPONENT block
  rows per run: [9, 18, 9, 9]   originals surviving: [9, 9, 0, 0]
   run2 ('player_game_batting', 2) gate: prior=9  comparable=0 permit=False absent=9 retired=0
   run3 ('player_game_batting', 2) gate: prior=18 comparable=9 permit=True  absent=9 retired=9
```

### 1a. The opponent block has NO closer, in any shape

`_load_team_core` calls `dedup_team_players(self._db, team_id, db_season_id, …)` with the **scouted**
team id. The opponent block's `player_game_*` rows and its `team_rosters` backfill are written under
`opp_team_id`, so the sweep never sees them. B3 is the *detectable* shape — the one dedup is supposed
to close — and it opens the window anyway.

Structural, not fixture-dependent. Not previously written down anywhere located during this
evaluation.

### 1b. Non-prefix name churn is invisible to dedup

`find_duplicate_players` requires folded last names equal AND one folded first name a non-empty
prefix of the other. `mike`/`michael`, `bob`/`robert`, `peggy`/`margaret` satisfy neither direction.
B2 is that shape on the own block.

### 1c. A refusal DOES write

`rows: 9 → 18` across a refused run. The refusal declines the retire; it does not decline the upsert.
This falsifies AC-14's stated premise *"a refusal writes nothing, so run 2's snapshot should equal
run 1's."* `W ⊆ fresh` does not rescue it: that premise constrains the **candidate** set, not the
**gate population**, and it is the gate population that grows.

---

## 2. Sizing (`drv2_sizing.py`, `drv5_boundary.py`)

### 2a. Where the run-3 window lives — partial churn sweep, 12-line block

`gates` tuples are `(prior, comparable, permit, absent, retired)` per run from run 2.

```
  k= 1: rows=[12, 12, 12, 12, 12] surviving=[12, 11, 11, 11, 11]
         gates=[(12, 11, True, 1, 1), (12, 12, True, 0, 0), ...]
  k= 3: rows=[12, 12, 12, 12, 12] surviving=[12,  9,  9,  9,  9]
         gates=[(12,  9, True, 3, 3), (12, 12, True, 0, 0), ...]
  k= 5: rows=[12, 12, 12, 12, 12] surviving=[12,  7,  7,  7,  7]
         gates=[(12,  7, True, 5, 5), (12, 12, True, 0, 0), ...]
  k= 8: rows=[12, 20, 12, 12, 12] surviving=[12, 12,  4,  4,  4]
         gates=[(12,  4, False, 8, 0), (20, 12, True, 8, 8), ...]
  k=12: rows=[12, 24, 12, 12, 12] surviving=[12, 12,  0,  0,  0]
         gates=[(12,  0, False, 12, 0), (24, 12, True, 12, 12), ...]
```

**k ≤ 5 deletes on run 2** — that is TN-8's already-accepted "partial churn still deletes", not the
R1 window. **k ≥ 8 (above the floor) refuses on run 2 and deletes on run 3.** The R1 window's
distinguishing effect is that it converts a run-2 refusal into a run-3 delete of the same rows.

Consequence that governs the candidates: a cap or a guard binds `absent` on **every** run, so it also
binds the k ≤ 5 region. Neither candidate is scoped to the window.

### 2b. ⚠️ THE `m ≥ P` BOUNDARY — this rule governs a fixture

**The rule is `m ≥ P`, not "m ≥ 12".** In the sweep below `P = 12`, so 12 does double duty as both
the original block size and the boundary value, and an implementer building a regime-B fixture at a
different `P` against a bare "12" would be silently wrong. *(This heading read `THE m ≥ 12 BOUNDARY`
until 2026-07-26 — corrected after PM flagged that the derivative in `epic.md` had become more precise
than this primary. It is `doc-sweep.md`'s first named survival shape: a title encoding a claim the
body has since refined, and it is what a reader greps to.)*

12-line original (`P = 12`) vs an **m**-line churn block, same ids repeated from run 2 on. Per-run
`(rows, originals_alive, gate)`:

```
  m= 9: [(21, 12, (12, 0, False)), (21, 12, (21,  9, False)), ...]  -> originals SURVIVE (permanent bloat)
  m=10: [(22, 12, (12, 0, False)), (22, 12, (22, 10, False)), ...]  -> originals SURVIVE (permanent bloat)
  m=11: [(23, 12, (12, 0, False)), (23, 12, (23, 11, False)), ...]  -> originals SURVIVE (permanent bloat)
  m=12: [(24, 12, (12, 0, False)), (12,  0, (24, 12, True )), ...]  -> ORIGINALS DELETED
  m=13: [(25, 12, (12, 0, False)), (13,  0, (25, 13, True )), ...]  -> ORIGINALS DELETED
  m=14: [(26, 12, (12, 0, False)), (14,  0, (26, 14, True )), ...]  -> ORIGINALS DELETED
  m=15: [(27, 12, (12, 0, False)), (15,  0, (27, 15, True )), ...]  -> ORIGINALS DELETED
```

**The delete fires iff `m ≥ P` — the repeated churn block is at least as large as the original
generation.** At `m = P` the run-3 read is `12 >= 0.5 * 24`, an exact equality, which is why it is a
knife edge rather than a comfortable threshold.

**Measured vs derived, kept apart**: the transition is *measured* at `P = 12` across m = 9…15 (11
refuses, 12 deletes, no gap), with one confirming equality point *measured* at `P = 9, m = 9` (§1 B2
and B3). `m ≥ P` at other values of `P` is *algebra* consistent with those measurements —
`m >= 0.5 × (P + m)` ⟺ `m >= P` — not measurement.

**⚠️ The quoted output above says "(permanent bloat)" and that label overstates it.** It is the
harness's own printed wording and is left verbatim because this is an output record, not prose. The
accurate description: below the boundary the churn block is *smaller* than the original, so the two
generations sit side by side (21/22/23 rows at m = 9/10/11) — **two co-resident generations, not a
doubling.** The exact doubling occurs only at `m = P`. "Bloat" is the kind of word that survives
because it sounds alarming rather than because it is accurate.

**A regime-B fixture whose churn block is smaller than the original pins the wrong outcome** — it
pins co-residence rather than the delete, and it will read as passing. A real `player_id` re-issue
keeps the roster, so it lands exactly on `m = P`.

Corollary, executed at k = 8 above: the run-3 read there is `12 >= 10`, not an equality — so
tightening the floor to a strict `>` does **not** generalize. Recorded so it is not re-proposed.

### 2c. Per-game, so the loss multiplies by the season

The reconcile runs once per game. Fixture: 24 games, **13-line blocks**, **3** ids churned per game
(undetectable names), corrected gate with **no** candidate mechanism.
`(total_rows, original_rows_alive)` per run, index 0 = after run 1:

```
  [(312, 312), (312, 240), (312, 240), (312, 240), (312, 240)]
```

**72 original batting lines died, and they died on RUN 2.** The arithmetic is `24 games × 3 churned
ids = 72`; **13 is the block size (the gate denominator), not a multiplicand** — total rows are
24 × 13 = 312 throughout, since each churned line is replaced one-for-one. The 72 counts rows in
`player_game_batting` only: the fixture's pitching group is empty, so no pitching lines exist, and
the opponent block is empty, so all 72 are own-block (`team_id = 1`).

**⚠️ Regime label: this is TN-8's partial-churn residual at season scale, NOT the R1 run-3 window.**
3 of 13 is below the floor, so the gate permits on run 2 and the delete lands there. The figure
belongs to the "production scale is the point" argument — the block size gates, the season size
multiplies — and must not be attached to regime B.

### 2d. Recovery and varying churn (`drv4_window.py`)

```
D1 RECOVERY -- run2 is a bad payload, run3 returns to the real ids
   rows= 12 generations=['a']      gate=(0,  0,  True,  0,  0, None)
   rows= 24 generations=['a','b']  gate=(12, 0,  False, 12, 0, 'gate')
   rows= 12 generations=['a']      gate=(24, 12, True,  12, 12, None)
   rows= 12 generations=['a']      gate=(12, 12, True,  0,  0, None)

D2 VARYING churn -- a different id set every run
   rows= 12 ['a']              gate=(0,  0,  True,  0,  0, None)
   rows= 24 ['a','b']          gate=(12, 0,  False, 12, 0, 'gate')
   rows= 36 ['a','b','c']      gate=(24, 0,  False, 24, 0, 'gate')
   rows= 48 ['a','b','c','d']  gate=(36, 0,  False, 36, 0, 'gate')
   rows= 48 ['a','b','c','d']  gate=(48, 12, False, 36, 0, 'gate')
```

**D1: in the recovery case run 3's "uncapped delete" removes the BAD payload's rows and leaves the
real ones intact.** The delete is the correct cleanup there. This is why "the run-3 delete" cannot be
described as harmful without naming the regime.

**D2: with a different id set each run there is no delete at all** — unbounded accumulation. The
delete requires the same set to repeat, which is evidence the new ids are the stable truth.

---

## 3. Candidate verdicts (`drv3_candidates.py`, `drv4_window.py`, `drv6_bloat.py`)

### (a) per-run player-line retirement cap — **REJECTED**

Closes the target; breaks two things that work today.

```
A1 CLOSES IT (12-line block, k=12 undetectable):
  cap=None rows=[12, 24, 12, 12, 12] surviving=[12, 12,  0,  0,  0]
  cap=2    rows=[12, 24, 24, 24, 24] surviving=[12, 12, 12, 12, 12]
           refused_by=['gate','cap','cap','cap']
  cap=3, cap=5: identical to cap=2 (absent=12 exceeds all three)

A2 DEADLOCKS A GENUINE REMOVAL (k lines vanish, no new ids):
  k=3 cap=None rows=[12,  9,  9,  9,  9] surviving=[12,  9,  9,  9,  9]
  k=3 cap=2    rows=[12, 12, 12, 12, 12] surviving=[12, 12, 12, 12, 12]  <-- PERMANENT STALE
  k=5 cap=2    rows=[12, 12, 12, 12, 12] surviving=[12, 12, 12, 12, 12]  <-- PERMANENT STALE

A3 RE-OPENS TN-8's ACCEPTED RESIDUAL IN THE WORSE DIRECTION:
  k=3 cap=None rows=[12, 12, 12, 12, 12] surviving=[12,  9,  9,  9,  9] refused_by=[None ×4]
  k=3 cap=2    rows=[12, 15, 15, 15, 15] surviving=[12, 12, 12, 12, 12] refused_by=['cap' ×4]
  k=5 cap=2    rows=[12, 17, 17, 17, 17] surviving=[12, 12, 12, 12, 12] refused_by=['cap' ×4]
```

**Root cause of the deadlock, and it is structural.** `MAX_GAME_RETIREMENTS` survives its own cap
only because `exempt` removes refused-and-kept ids from the count — see the "CAP POPULATION" comment
in `retire_absent_games`, which records that counting them makes the cap permanently self-trapping.
**There is no player-line analogue of that escape hatch**: the ids a player-line cap refuses recur
identically on every subsequent run, and they are by construction the ids dedup cannot merge, so no
exemption could rescue them. This is the roster grain's backfill-churn deadlock reproduced on a grain
with no exemption to relieve it.

### (b) narrowing-only churn-signature `extra_guard` (NAME) — **REJECTED**

```
B1 does NOT fire on the shape that reaches run 3 (k=12 undetectable):
  sig=name  rows=[12, 24, 12, 12, 12] surviving=[12, 12, 0, 0, 0]
            guard events fired: 0

B2 does NOT fire on the detectable re-issue either (the gate refuses first):
  sig=name  rows=[12, 12, 12, 12, 12] surviving=[12, 12, 12, 12, 12]  events=0
            gates=[(12, 0, False, 12, 0, 'gate'), ... ×4]
```

**The disqualifying property is structural, not a tuning problem.** The signature the brief specifies
is a name match, and dedup's detection rule **is** a name match (`find_duplicate_players`). The guard
is therefore redundant wherever dedup succeeds and blind wherever dedup fails — it fires on exactly
the set dedup would have merged anyway. B2's 0 events are for a second reason worth keeping separate:
`extra_guard` is consulted only after the health gate permits, so on the detectable shape the gate
refuses at run 2 and dedup closes it before run 3 exists.

**Implementation trap, found by execution.** A first cut defined "incoming" as `fresh − snapshot`
(brand-new ids this run). That guard **never fires on run 3**, because run 2's refusal already
upserted the churned ids into the snapshot, so `fresh − snapshot` is empty exactly when the delete
happens. Any such signature must compare against the whole fresh set.

### (b′) jersey-number signature — **REJECTED** (a genuinely different signal; still fails)

`team_rosters.jersey_number` is never read by dedup, and a re-issued id keeps its predecessor's
number, so this fires where the name signature cannot.

```
B3 CLOSES IT (k=12 undetectable):
  sig=jersey rows=[12, 24, 24, 24, 24] surviving=[12, 12, 12, 12, 12]  events=3
             refused_by=['gate','churn_signature','churn_signature','churn_signature']

B4b COUNTEREXAMPLE -- a departed player's NUMBER reassigned to an unrelated new player:
  churn_guard=False rows=[12, 12, 12, 12, 12] surviving=[12, 11, 11, 11, 11] refused_by=[None ×4]
  churn_guard=True  rows=[12, 13, 13, 13, 13] surviving=[12, 12, 12, 12, 12] refused_by=['churn_signature' ×4]
```

Permanent stale with no self-heal — dedup cannot merge them, the names differ.

**Name-signature counterexample, same shape** (`drv4` D3): a genuine departure whose name
prefix-matches an unmergeable **fork** (3 members, ≥2 distinct terminals):

```
  churn_guard=False rows=[12, 11, 11, 11] 'Ja Smith' row alive=[True, False, False, False]
  churn_guard=True  rows=[12, 12, 12, 12] 'Ja Smith' row alive=[True, True,  True,  True ]
                                          refused_by=['churn_signature' ×3]
```

Guard and dedup both refuse, forever. **This is the one case where SE and DE priced the same executed
result differently** — see the header.

### (c) loud surfacing of a refused fork over would-be victims — **ADOPTED as a diagnostic only**

```
C1 rows=[12, 13, 13, 13, 13] surviving=[12, 11, 11, 11, 11]
   gates=[(12, 11, True, 1, 1, None, True), (13, 13, True, 0, 0, None, False), ...]
   surfacing events: ["FORK-SURFACE game=game-0001 player_game_batting/1: about to retire
                       1 row(s) whose player_id is a member of a REFUSED dedup fork: ['a-1']"]

C2 COST (24 games, run-3 delete pass):
  fork_surface=False: 0.01s      fork_surface=True: 0.04s
```

Fires correctly, costs ~0.03 s per season-run, **and the row still dies** — it is a diagnostic, not a
closer.

**Its coverage is narrower than it looks.** In the dominant residual shape (undetectable name churn)
dedup detects **no pairs at all**, so there is no fork to surface and (c)-as-specified is silent on
precisely the run that deletes 12 rows. Its reach is bounded to fork members, which is a couple of
rows. It also needs `season_id` plumbed into `GameLoader`, which does not carry it today.

**Adopted form** (generalized, per the operator's ruling): a churn-signature **diagnostic on a
permitted retire**, never a gate. When a retire is permitted and any victim name-matches or
jersey-matches a *surviving* fresh id, emit one WARN naming the count, the ids, and
`bb data dedup-players` as the instrument. Deletion behaviour is unchanged, so story 01 AC-8's
deletion-neutrality is untouched by construction, and it fires on the shape (c)-as-specified misses.

---

## 4. ⚠️ Why refusing is NOT the safe direction on this grain (`drv6_bloat.py`)

Every mechanism that closes the window closes it by refusing **forever**. Reading the shipped
query-time aggregate `src.api.db.get_season_batting` after four runs of a 12-line, 36-AB game:

| regime | leaderboard rows | team AB total |
|---|---|---|
| none (corrected gate alone) | **12** | **36** |
| cap=2 | 24 | 72 |
| jersey signature | 24 | 72 |

**A permanent refusal produces a permanent split identity: the whole roster appears twice and every
team total is exactly 2×.** This is the harm the epic's own fork-residue table names, arrived at
deliberately instead of accidentally.

Bias-to-refuse assumes the refused rows are live data worth keeping. In the churn regime they are
duplicates of rows that are also present. That is the load-bearing asymmetry between this grain and
the roster grain, and it is why the prefer-delete precedent transfers here.

---

## 5. Two implementation hazards for story 01

### 5a. The vacuous permit is FAIL-OPEN on a mis-keyed snapshot

The harness initially hooked the wrong method name (`_load_game`, which does not exist; the method is
`_upsert_game_and_stats`), so the snapshot was silently empty. AC-6's vacuous-permit rule then
permitted every gate:

```
   run2 gate: prior=0 comparable=0 permit=True absent=9 retired=9
   originals surviving: [9, 0, 0, 0]
```

**A wiring mistake reproduced the pre-fix blast radius exactly, with no error.** AC-7's
required-keyword parameter stops an *omitted* argument but not a *wrongly-keyed dict*. The keyed
record's `gate_prior_count` is the only observable that catches it — a further argument for AC-2
asserting it per keyed entry rather than as a scalar.

### 5b. A guard that RAISES is identical to one that REFUSED **under the row count** — `LoadResult.errors` discriminates, at one of five sites

*(Heading scoped 2026-07-26. It read `observationally identical` unqualified, which is stronger than
the body: identical under the SURVIVING-ROW COUNT, not under every observable. Left unqualified it
licenses "no test can tell them apart", when `LoadResult.errors` can — everywhere the swallow site
increments it, which is the player-line reconcile and nowhere else.)*

When the harness's `_churn_signature` raised (`sqlite3.OperationalError: no such column: id` — the
`players` PK is `player_id`), `GameLoader._retire_absent_player_lines`'s broad `except` swallowed it,
returned `errors += 1`, and the run produced **every positive signal of a working guard**: nothing
retired, rows preserved, WARN-level logs clean. It read as the guard working.

This is `.claude/rules/testing.md`'s "an absence claim needs proof the mechanism COMPLETED CLEANLY",
arriving on the guard rather than on the test. Anything that adds DB access inside `extra_guard` on
this grain must set the record's `gate_evaluated` false on exception, or a refusal and a crash are
indistinguishable. Story 01 AC-1's `LoadResult.errors == 0` assertion is doing real work here.

**⚠️ INDEPENDENTLY REPRODUCED — this is a property of the module, not a caution.** Per the team lead,
DE-R1 hit the same trap in a different construction during the same evaluation, without either agent
knowing the other had: a `TypeError` from passing `RefusedFork.members` into a set intersection was
swallowed, the reconcile aborted, and its harness printed *"CLOSES the fork window"* — the right
answer for the wrong reason. **It was caught by `LoadResult.errors`, not by the row count.**

Two agents, both deliberately probing this seam, both produced a **false PASS that the surviving-row
count could not distinguish from success**. The binding consequence reaches the tests as well as the
implementation: **any assertion that establishes a refusal by counting surviving rows is satisfiable
by a crash.** Pair it with the result object.

*(Recorded as relayed by the team lead. This author has not read DE-R1's report and does not
represent its reasoning beyond the fact of the second instance.)*

---

## 6. Closure by exhaustion — the reasoning, so it is checkable

The operator's position is that the residual is **surfaced, not closed**. That claim rests on the
following, and each leg is executed above rather than argued:

1. **The window is a ratio artifact.** It exists because a refusal still upserts, so the gate's
   denominator grows by the churn (§1c) and the floor is met on the next repeat (§2b).
2. **A cap cannot close it without deadlocking.** The game grain's cap is safe only because of
   `exempt`; that escape hatch has no player-line analogue, and the refused ids recur forever (§3a).
3. **A name signature adds nothing dedup does not already do**, because it *is* dedup's rule (§3b).
4. **A jersey signature is a real new signal but buys closure with a permanent duplicate identity**
   (§3b′, §4).
5. **Every closing mechanism refuses forever, and forever-refusing doubles the coach-facing season
   aggregate** (§4). The cure is worse than the disease on this grain specifically.
6. **The delete is CORRECT in the recovery regime** (§2d D1), so a mechanism that suppresses it
   unconditionally suppresses correct behaviour too.
7. **Two families were executed and discarded without a counterexample, on their own evidence**: a
   strict `>` floor (does not generalize — §2b corollary) and rolling back a refused run's own
   upserts (freezes the game's lines at the pre-churn state permanently and never accepts a genuine
   re-issue).

**What would close it** is already named by the epic. TN-8: *"Closing it needs a different instrument
— a same-game name-prefix dedup-candidate check, not a ratio and not a cap → IDEA-185, not this
epic."* The correct outcome in the churn regime is **merge-not-delete** — retire the old id *into*
the surviving fresh one — which is IDEA-185's instrument. R1's three candidates are drawn from the
two instrument families TN-8 had already ruled insufficient; this evaluation supplies the executed
evidence for that ruling rather than restating it.

**Stated residual after adoption.** A GameChanger `player_id` re-issue whose names dedup cannot
prefix-match, or which lands on the opponent block, still hard-deletes the prior generation of lines
on the third re-scout, uncapped — **provided the repeated churn block is at least as large as the
prior generation (§2b)**. Below that size, or with a different id set each run, it instead accumulates
duplicate lines indefinitely (§2d D2). Both halves are visible in the WARN and in the gate-outcome
record; neither is prevented.

---

## 6b. The accumulate-then-delete predicate — EXECUTED 8/8 AT THE RECORD LEVEL, test-side only (`drv7_predicate.py`)

*(Heading scoped 2026-07-26. It read `EXECUTED, 8/8` — a bare pass rate whose two limits, "record
level, not against the real `ScoutingLoader`" and "test-side, not production", lived only in the body
below. "8/8" is what a reader greps to and quotes; the qualifiers are what stop it being over-read.)*

An earlier draft offered `gate_prior_count ≈ 2 × gate_comparable_count` as the run-3 signature.
**Withdrawn** — the ratio is 2.00 only when the churn block equals the original (`m = P`) and falls to
1.80 by m = 15, so it is an artifact of the equality case and is not a testable predicate.

The predicate that replaces it, built and run rather than reasoned to:

```
fires(prev, cur) == cur.gate_permitted is True
                   AND cur.gate_prior_count > prev.gate_prior_count
                   AND prev.gate_prior_count > 0
```

`prev` is the record for the SAME key from the PREVIOUS invocation; the key is
`(game_id, table, team_id)` — **`game_id` is required in the key**, or a season's games overwrite
each other. No tolerance, no arithmetic.

| # | scenario | required | fired on |
|---|---|---|---|
| S1 | regime A — identical-name re-issue, own block | silent | none ✔ |
| S2 | regime B — undetectable names, m = P = 12 | fire inv 3 | 3 ✔ |
| S3 | sub-boundary — m = 9 < P = 12 | silent | none ✔ |
| S4 | first-ever load then a clean reload | silent | none ✔ |
| S5 | clean no-churn re-scout × 4 | silent | none ✔ |
| S6 | regime B at P = 9 | fire inv 3 | 3 ✔ |
| S7 | opponent block, identical names | fire inv 3 | 3 ✔ |
| S8 | a new game joins the season on invocation 2 | silent | none ✔ |

**The `prev.gate_prior_count > 0` clause is load-bearing, established by running without it**: S4, S5
and S8 all false-fire when it is dropped — S8 twice, including on the newly-added game at invocation
3, which is an ordinary in-season shape. The cause is the vacuous permit: a first-ever load records
`prior=0, permitted=True`, so the next clean load reads as growth-with-permit.

**Two honest scope notes.**

1. **In regime A the silence comes from the `gate_permitted` conjunct, not the growth conjunct.**
   Dedup merges the fresh generation away each run, so the snapshot is always the old ids, `comparable`
   is 0, and the gate refuses on every invocation (`prev_prior=12 prior=12 comp=0 permit=False`). The
   predicate does not distinguish merged from unmerged and does not need to — it keys on
   permit ∧ growth.
2. **⚠️ This is a TEST-side assertion across invocations, NOT a production diagnostic.** It needs the
   previous invocation's record for the same key, and nothing in production retains one — the record
   is built per call and returned in the result dataclass. Persisting it would be a snapshot table by
   another name, which TN-2 rejected. The production-side surfacing recommended in §3(c) is a
   different artifact: a single-run WARN on a permitted retire whose victims name- or jersey-match a
   surviving fresh id. **Do not wire this predicate into production.**

## 7. Follow-ups — both ROUTED (operator ruling, 2026-07-26)

Neither is dropped, and neither needed an idea file from this author. Recorded here so a later reader
does not re-raise them as loose ends.

- **The opponent-block dedup gap** (§1a) — `dedup_team_players` is scoped to the scouted team, so the
  opponent block has no closer in *any* shape, including the detectable one. Distinct from IDEA-185.
  **To be filed as an idea AT CLOSURE**, deliberately not before: this epic's commission is to keep
  scope tight, and a pre-filed idea sitting outside the epic is a weaker commitment than a deferral
  written into an AC. It lands twice — as that idea, and as a named **accepted documented residual**
  in story 01 AC-14's regime B.
- **The fail-open vacuous permit on a mis-keyed snapshot** (§5a) — **NOT an idea.** Folded into story
  01 as an **AC-2 assertion on `gate_prior_count` per keyed entry**, on the reasoning that it sits
  inside the gate fix's own blast radius rather than beside it. §5a is the reason that AC exists.

## 8. Provenance of the harnesses

Built and run in an ephemeral session scratchpad
(`…/2728098f-4677-4ff3-a474-cda6aed92b4c/scratchpad/r1/`): `h.py` (prototype + candidates),
`drv1_baseline.py`, `drv2_sizing.py`, `drv3_candidates.py`, `drv4_window.py`, `drv5_boundary.py`,
`drv6_bloat.py`, consolidated output `EVIDENCE.txt`. **Assume those paths are gone**; the output
lines quoted above are the record, and §0 carries enough of the method to rebuild them.

Prior art this evaluation started from: `x_attack.py` (attacks X1–X6) at
`…/4aca143d-2d11-40ae-ae02-d8924803b063/scratchpad/e276-review/`. Its X3 established the run-3
arithmetic **at the primitive level only** (hand-fed `crawl_is_authoritative` and
`classify_absences`); §1 B2/B3 above is the same result driven end-to-end through the loader.

### Citation finding worth one line

The commissioning prompt gave `x_attack.py` under the `2728098f-…` scratchpad; it is under
`4aca143d-…`. The mechanism is worth recording because it fails silently: story 01's two *legitimate*
reference paths (`divergence_plugin.py`, `divergence_game.py`) **are** under `2728098f-…`, and the
third path was pattern-matched onto the same directory without being checked. **A path that is right
for its neighbours is not thereby right, and a session-scoped scratchpad is exactly where that
assumption breaks** — the directory exists, so the error surfaces as a missing file rather than a
missing directory, which reads as a vanished artifact rather than a wrong path.
