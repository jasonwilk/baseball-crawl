# E-276 — Player-Line Gate: Invariant Sweep and Candidate Evaluation (DE)

**Status**: closed. R1 was ruled **diagnostic only, no gate** — no `extra_guard`, no cap; nothing refuses a player-line retire that today's code permits. This file is the executed record behind that decision, not a case for reopening it.
**Author**: data-engineer (`DE-R1`), pre-dispatch consultation, 2026-07-26.
**Scope**: the player-line grain of `src/db/reconcile_at_load.py` only. The roster grain is `E-276-roster-design-recommendation.md`.
**Companion epic**: `epics/E-276-reconcile-health-gate-prior-capture/`.

---

## 0. What this file is

The R1 brief asked DE and SE to evaluate three candidate mechanisms **by construction** against the player-line one-run window, independently, and to build the counterexample against their own candidate before pinning it. This records DE's executions.

Two of its results are worth more than the verdict and are why the file exists:

- **§2 — the deletion-neutrality sweep.** 2366 executed combinations proving the epic's central neutrality claim on this grain. It exists nowhere else, and it stands regardless of which mechanism was adopted.
- **§3 — replace-vs-accumulate.** The health gate guards only the DELETE half of a REPLACE; the WRITE half is ungated. This reframes what "bias to refuse" buys on this grain, and it is load-bearing for the ruling even though DE's own adoption verdict differed (§7).

**Provenance**: every figure below was produced by a harness under a session scratchpad (now gone) that built synthetic SQLite databases from `migrations/` and drove the **real** `ScoutingLoader.load_team`. `data/app.db` was never touched; no network; no repo writes outside this file. The harness simulated the corrected gate by patching `GameLoader._load_team_stats` to capture the pre-upsert snapshot and substituting a `retire_absent_player_lines` that gates on that snapshot while still classifying the **live** prior set. Where a table is quoted, it is the harness's stdout, unedited except where §6 notes a mislabelled column and where the fixture identities were renamed (below).

**Fixture identities, and a near-miss worth the caution.** The name-matching constructions use deliberately synthetic identities: the fork family is `Alp Zeta` (the stub) against `Alpha Zeta` and `Alpine Zeta`; the unrelated departure is `Delta Omega`; the divergent-name pair is `Kilo{i} Tango{i}` → `Yankee{i} Uniform{i}`. **These are renames.** The first draft of this file used plausible personal names, and the doc-PII byte-gate (`scripts/check_doc_pii.sh`) **blocked the commit** — they collided with literal real identifiers on the uncommitted denylist. The pattern scanner cannot see this class; only the byte-gate could. The lesson generalises past this file: **a fixture that needs to exercise name matching invites "realistic" names, and realistic names are by construction the names real people have** — so a name-matching fixture is the one place where plausibility is the hazard rather than the goal. Pick names that could not belong to anyone, and run the gate before committing.

The rename was verified rather than assumed: re-executed against the real `_fold_name` and `plan_player_dedup`, `alp` is a prefix of both `alpha` and `alpine`, the surnames fold equal, the two terminals are distinct, and the planner returns `refused_forks=[['Alpha','Alpine']]` — the same verdict under the new names. The re-typed pair still exhibits no prefix relation and no shared surname. Every figure below survived the rename unchanged.

---

## 1. Premises established by execution

Three facts the rest depends on. All were briefed as claims and all held.

| Premise | Executed result |
|---|---|
| **A refusal does not stop the upsert.** | 9 stored lines, fresh payload of 3 brand-new ids. Gate refuses. Table afterwards holds **12** rows (9 survive, 3 written). |
| **`W ⊆ fresh` on this grain** (`W` = the rows this run writes). | `W = {b-1 … b-9}`, `fresh = {b-1 … b-9}`. Equal. |
| **Identical churn repeated reaches the floor exactly on run 3.** | Per-run, corrected gate, end-to-end through the loader: |

```
run | rows | A-survivors | gate_prior | gate_comparable | permitted | retired
 1  |   9  |      9      |     0      |        0        |   True    |    0
 2  |  18  |      9      |     9      |        0        |   False   |    0
 3  |   9  |      0      |    18      |        9        |   True    |    9
 4  |   9  |      0      |     9      |        9        |   True    |    0
```

Run 3 is `9 >= 0.5 × 18 = 9.0` — **exactly** at the floor, permitting an uncapped retire of all nine originals. A strict `>` would flip it; the design uses `>=`. Recording the knife-edge because a future reader tuning `FLOOR_RATIO` should know the reproduction sits on the boundary rather than inside a band.

Note what premise 1 does to premise 3: `W ⊆ fresh` guarantees this run's own writes cannot be *classified absent this run*. It says nothing about them inflating **next** run's denominator, which is the whole mechanism above. `W ⊆ fresh` constrains the candidate set, not the gate population.

---

## 2. Deletion-scoping invariant sweep — the executed proof

**Standard**: the epic's, not a weaker one — *"the fix never permits a DELETION that today's code refuses"*. Not "permits whenever today permits", which is false by design at the vacuous-permit boundary.

**Executed**: an exhaustive sweep over `(prior, survivors, writes)` for `prior, survivors, writes ∈ [0, 12]`, `survivors ≤ prior`, evaluating both the corrected gate and corrected + a cap-2 `extra_guard` against today's polluted gate.

```
I1 swept 2366 (prior, survivors, writes) combinations
I1: HOLDS — no candidate permits a deletion today refuses
```

**Zero violations**, and the algebra explains why rather than leaving it to the sample:

Let `P_pre` be the pre-upsert prior, `S = |P_pre ∩ fresh|` the survivors, `W` this run's writes. Today's gate reads the post-upsert population, so its numerator is `S + |W|` and its denominator `P_pre + |W|` — **because `W ⊆ fresh`, every written row lands on both sides**. Then:

```
today refuses  ⇔  S + |W| < 0.5·(|P_pre| + |W|)
               ⇔  S < 0.5·|P_pre| − 0.5·|W|
               ⇒  S < 0.5·|P_pre|
               ⇔  corrected refuses
```

So today-refuses implies corrected-refuses, unconditionally, for any `|W| ≥ 0`. Each written row relaxes today's floor by exactly half a row — which is both the defect and the reason the fix is one-directional. Any `extra_guard` sits on top as a strict narrowing (§4), so the property survives every candidate evaluated.

This is the scale-free form of epic TN-5's two-line proof, executed rather than asserted, and it is what makes "the fix only ever refuses more" a checked statement about this grain.

---

## 3. Replace-vs-accumulate — the finding that reframes the residual

> **On this grain the health gate guards only the DELETE half of a REPLACE. The WRITE half is ungated.**

"Bias to refuse" is safe only when refusing preserves the status quo. Here it does not — §1 premise 1 shows the fresh rows are written whether or not the retire is permitted. So a refusal does not restore what was there; it produces the **union** of stale and fresh.

Executed on the worst input for the intuition — a **corrupt** full-size payload replacing 9 real lines with 9 wrong ones, true team season AB = 27:

```
   corrected gate only    player rows= 9  team AB= 27   corrupt only
   (a) cap=2              player rows=18  team AB= 54   UNION of real+corrupt
   (b) churn guard        player rows= 9  team AB= 27   corrupt only
```

Refusing the delete did not save the real data. The corrupt rows were already committed by the same run; refusing merely added the stale ones back on top, producing a superposition no aggregate query can disentangle. `get_season_batting` sums `player_game_batting` per `player_id`, so every retained stale line is an **extra player row carrying the same game's at-bats**.

The general statement: **the player-line grain is not a "delete vs. keep" decision, it is "replace vs. accumulate."** Any mechanism that refuses the delete without also gating the write buys a duplicate, not a rescue. This is also why the roster grain's accepted residual — *"grid clutter, never a corrupted stat"* — does not transfer: on player-line the retained row **is** the corrupted stat.

Independently confirmed at a second fixture size: SE-R1 measured the same 2× inflation as 36→72 AB from a fixture built without reference to this one.

---

## 4. Same-population and narrowing-only

Both verified; neither was at risk from any candidate, and both are recorded so a future mechanism can be checked against them cheaply.

- **Same-population** (numerator and denominator both from `prior ∩ fresh` over `prior`): holds by construction for every candidate evaluated. All three are `extra_guard` predicates over the **absent** set; none is an argument to `crawl_is_authoritative`. The failure to watch for is an implementer folding a precomputed exemption into `comparable` instead of into the guard — that would silently raise the deletion cap above `0.5 × prior`, which is the population mismatch the game grain's comment already documents having tried and rejected twice.
- **Narrowing-only**: structural, from the ordering in `classify_absences` — the health gate is applied first and the guard consulted only when removal is already permitted. Re-verified directly (a permissive guard cannot resurrect a refused gate; a restrictive one always narrows). Already pinned upstream by `tests/test_reconcile_at_load.py::test_permissive_guard_cannot_widen_a_refused_health_gate`.

---

## 5. Per-candidate executed results

### (a) per-run player-line retirement cap — DE verdict: reject

It does close the briefed attack (cap 2, identical repeated churn: 0 retired on every run, `refused_by=extra_guard` from run 3). Four counterexamples:

```
A2 — cap=2, gentle progressive churn (2 re-issues/run)
  run  retired   A_alive
   2      2         7
   3      2         5
   4      2         3
   5      2         1      -> 8 of 9 originals lost in 4 runs
```

```
A3 — cap=2, 3 GENUINE removals recurring (+1 new id on run 4)
  run  retired   refused_by
   2      0      extra_guard
   3      0      extra_guard
   4      0      extra_guard   -> permanently unretirable, and blocking
                                  every later removal on this block
```

```
A4 — protection runs BACKWARDS w.r.t. severity
  catastrophic (9-of-9 churn x3):  originals lost = 0
  gentle       (2-of-9 churn x3):  originals lost = 6
```

- **A2** — the cap bounds a **rate**, not a total. Same shape the epic records for `MAX_ROSTER_DEPARTURES`.
- **A3** — a permanent deadlock. **Root cause, and it is specific**: `MAX_GAME_RETIREMENTS` counts `absent - exempt`, and that `exempt` precompute exists precisely to stop refused-and-kept ids recurring in `absent` forever. The player-line grain has **no analogue of `exempt`**, so a cap on it reproduces the deadlock the game grain's cap was built to avoid. "Sibling of `MAX_GAME_RETIREMENTS`" glosses the load-bearing half. *(SE-R1 reached this same root cause independently.)*
- **A4** — protects inversely to severity.
- **The decisive one** — §3 / §6: on the only shape where the residual bites, the cap converts a numerically correct season line into a permanent 2× inflation.

### (b) churn-signature `extra_guard` — DE verdict: adopt (not taken; see §7)

```
B-CONTROL — corrected gate ONLY, same-human id re-issue, no guard
  runs 2-4: refused_by=gate, rows stay 9, 0 retired, 0 lines ever lost
```

- **Dedup alone already closes the collapsible shape.** The epic's grain-table claim holds for it. Candidate (b) adds nothing there.
- **The epic's own churn fixture does not exercise (b) at all.** `a-N` / `b-N` derive names from ids, so no victim name-matches anything: the guard never fires and run 3 retires all 9. Every planning probe in this epic used that fixture.
- **Where it misses, executed**: re-typed names (`Kilo0 Tango0` → `Yankee0 Uniform0` — no prefix relation, no shared surname) — silent, all 9 retired. Victim stored as the FK-safe `('Unknown','Unknown')` stub — no name to match, all 9 retired. **These are exactly the shapes dedup is blind to, because (b) uses the same signal** (a folded prefix match on a co-rostered pair).
- **Therefore (b)'s entire marginal value over the existing dedup sweep is the population dedup DETECTS but does not merge**: a refused fork, and a collapse that fails silently ([[IDEA-189]]).
- **Its cost, measured** (§6): a permanent phantom identity in the coach-facing season line.

### (c) surfacing a dedup fork refusal — DE verdict: adopt as observability

- **Not retrievable.** No table, column or flag records a fork refusal — it exists only as a WARN line, and `dedup_team_players` swallows collapse failures without touching `result.errors`. A schema scan for any dedup/fork/refusal table returned **NONE**.
- **But re-derivable in-run, at the exact moment the gate decides.** Running `plan_player_dedup` from inside the gate decision returned `refused_forks=[['Alpha','Alpine']]`. It works because `_load_team_stats` backfills the fresh ids into `team_rosters` **before** `_retire_absent_player_lines` runs in the same function, so old and new ids are co-rostered when the gate fires.
- (c) changes no deletion, so it cannot close the residual on its own.

### The intersection property — the durable implementation constraint

(b) and (c) turn out to be the **same query**. DE's adoption candidate sourced the signal from `plan_player_dedup` rather than a hand-rolled prefix match, because E-253-08 deliberately consolidated the name fold so detection and the planner cannot diverge; a third copy inside the reconcile would be a new drift surface. Attacking that candidate produced the constraint worth keeping:

```
P1 fork window:      guard fires (stuck=['a-1']), retire refused, stale line retained
P2 UNINTERSECTED:    Delta Omega (unrelated genuine removal) retired = False [9 lines]
P3 INTERSECTED:      Delta Omega (unrelated genuine removal) retired = True  [8 lines]
P4 divergent names:  guard blind, run 3 retires all 9 -> season line CORRECT (9 rows / 27 AB)
    [p1..p4] LoadResult.errors per run: [0, 0, 0] / [0, 0, 0] / [0, 0, 0] / [0, 0, 0, 0]
```

**Anyone revisiting a planner-sourced guard under [[IDEA-185]] must intersect the planner's component members with the ABSENT set.** Unintersected, a fork *anywhere* on the team-season blocks the whole block's retire, including unrelated genuine removals. Two further constraints from the same construction: precompute the set **once per game load** and close over it (`classify_absences` is contractually pure and the game grain's `exempt` is the precedent — the gate is evaluated up to 4× per game, 2 blocks × 2 tables), and pass it as `extra_guard` only.

The `errors: [0,0,0]` line is not decoration. An earlier revision of this construction passed `RefusedFork.members` (a list of `PlayerRef`, not ids) into a set intersection; the `TypeError` was swallowed by `_retire_absent_player_lines`' broad `except`, the reconcile aborted, nothing was retired, and **the harness reported "CLOSES the fork window" for the wrong reason**. Per `.claude/rules/testing.md`, an absence claim needs proof the mechanism completed cleanly — the result object, not a spy. Every figure in this file was re-run after that fix.

---

## 6. Season-aggregate cost, by mechanism

Full 9-of-9 id churn, 4 runs. True team season AB = 27, true player rows = 9.

```
name regime                       mechanism            rows  teamAB  verdict
names MATCH (dedup can collapse)  corrected gate only     9     27   CORRECT
names MATCH                       (a) cap=2               9     27   CORRECT
names MATCH                       (b) churn guard         9     27   CORRECT
names MATCH                       (a)+(b)                 9     27   CORRECT
names DIVERGE (dedup blind)       corrected gate only     9     27   CORRECT
names DIVERGE                     (a) cap=2              18     54   INFLATED x2.0
names DIVERGE                     (b) churn guard         9     27   CORRECT
names DIVERGE                     (a)+(b)                18     54   INFLATED x2.0
```

Read it as: **in the one regime where the residual bites, the retire produces the correct season line and refusing it produces a permanent 2× inflation.** In the regime where dedup can collapse the churn, every mechanism — including none — is correct, because dedup does the work.

**Fork case, separately** (a genuine departure whose name forks against two present players, so dedup refuses and nothing collapses it): the guard refuses on every run and `get_season_batting` returns

```
[('a-1', 'Alp Zeta', 3), ('a-2', 'Alpha Zeta', 3), ('a-3', 'Alpine Zeta', 3)]
```

— 9 player rows and 27 team AB for a game with **8** batters. **Label correction to the harness's own output**: it printed "true team AB = 27", which was run 1's truth; after the departure the true value is **24**, so the observed 27 is inflated by 3 AB — one permanent phantom identity. The verdict the harness printed was right; its baseline label was not. Recorded because a future reader would otherwise read 27-vs-27 as agreement.

---

## 7. Verdict, and the disagreement

**DE's verdict as reached**: reject (a); adopt (b) and (c) merged into one planner-sourced narrowing guard, intersected with the absent set; state as an accepted residual that a divergent-name id re-issue still retires uncapped on the third identical run.

**SE-R1 evaluated the same three candidates independently, from the implementation side. Neither agent read the other before reporting.** The two converged on rejecting (a) — including its root cause — on the 2× inflation, on AC-14's false premise, and on the `W ⊆ fresh` scope point, at separate fixtures.

**They diverged on exactly one thing**: whether to gate the fork population. Both had independently built the same counterexample and obtained the same executed result; they priced it differently. DE read the permanent phantom identity as an acceptable cost for closing the only window dedup cannot. SE read it as disqualifying.

**The operator took SE's reading. The ruling is diagnostic only, no gate** — weighing the prefer-delete precedent and SE's finding that the opponent block has no dedup closer in any shape. Recorded plainly because a design record that shows two independent evaluations diverging, and how it was settled, is more useful than one that reads as though the answer was obvious. Nothing in this file reopens it; §5's per-candidate results are kept as the evidence base for [[IDEA-185]], not as a case.

---

## 8. Findings carried into the epic regardless of the verdict

1. **AC-14 pinned a false property.** It required *"after every invocation, the 9 original lines survive"* and that the gate's prior count *"never grows across runs"*. Executed on its own mandated fixture: survivors go **9 → 9 → 0** and gate prior goes **0 → 9 → 18**. The stated mechanism is the error — *"a refusal writes nothing"* conflates the retire with the upsert. The AC is satisfiable only with a name-matching fixture, at which point it tests the **dedup sweep** rather than the gate.
2. **Replace-vs-accumulate** (§3).
3. **`src/db/reconcile_at_load.py`** — the comment above the ordering invariant in `classify_absences` cites *"Pinned by test_permissive_guard_cannot_widen."* No test of that name exists; it is `test_permissive_guard_cannot_widen_a_refused_health_gate` (`tests/test_reconcile_at_load.py:223`).
4. **`retire_absent_player_lines` passes no `extra_guard` today**, so any future mechanism is the first on this grain — there is no existing composition to preserve.
5. **Cite the one-run window by the epic's grain-table row** (`| player-line | corrected gate |`), never by line number. The line-number citation in circulation resolved correctly at the time and is exactly the anchor form `.claude/rules/tool-output-integrity.md` forbids.
