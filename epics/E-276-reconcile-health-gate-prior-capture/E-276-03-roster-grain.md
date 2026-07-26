# E-276-03: Roster Grain — Remove the Floor Ratio (V1)

## Epic
[E-276: Reconcile-at-Load Health Gate — Capture the Prior Set Before the Run's Own Writes](epic.md)

## Status
`TODO`

## Description

After this story is complete the roster grain has **no floor ratio**. Its permit condition is:

```
permit = (fresh roster payload non-empty) AND (|absent ∩ previously_rostered_ids| <= MAX_ROSTER_DEPARTURES)
```

Neither today's legacy floor nor a corrected snapshot-population floor survives here. `MAX_ROSTER_DEPARTURES` becomes the **sole** safety control on this grain, and this story writes that obligation at the constant.

**This story's deliverable INVERTS the epic's headline, and that is deliberate.** The other two grains gain a correctly-populated gate. This one loses its gate. It is the operator's ruling to invert the bias on this grain — delete rather than refuse — so the roster grain ends this epic with **less** gating than it started with. Do not read the epic's title as this story's goal.

## Context

### What this story does NOT do — read this before writing any AC or comment

**The commissioned defect is not FIXED on this grain. It is REMOVED, along with the gate that carried it.** DE's executed demonstration — run 1 roster `{r-a, r-b, r-c}`, run 2 fresh `{r-a, r-x}`, `r-b` and `r-c` hard-deleted through the real `ScoutingLoader`, with the WARN reporting `roster_db_count=4` on a roster that only ever held three rows — behaves **identically under V1**: the cap sees two genuine departures, permits, and both rows still go.

So no AC, comment, docstring or commit message in this story may claim it fixes the post-upsert prior read on the roster grain. What it fixes is the *concealment*: a floor that appeared to protect, could not (the cap fires first), and would have locked the grain if it were repaired.

### Why the floor goes rather than being re-populated

The corrected (snapshot-population) roster gate was built and executed through the real `ScoutingLoader`. It **permanently locks the grain** on a reachable input where today's code converges to a clean roster:

```
DB {a,b,c}; cap=2
Run 1  fresh {a,n1}      legacy 2>=2 PERMIT | cap 2<=2 PERMIT | corrected 1>=1.5 REFUSE
       TODAY retires b,c -> {a,n1}           FLOOR-BEARING FIX refuses -> {a,b,c,n1}
Run 2  fresh {n1,n2,n3}  TODAY retires a -> clean.  FIX refuses again
Run 3+ healthy crawl, both gates PERMIT.
       cap: absent {a,b,c} ∩ previously = 3 > 2  -> CAP REFUSES, FOREVER
```

Three players stranded on the coach-facing grid and every subsequent genuine departure blocked. Fed by **two** mechanisms, not one: the cap counting the stranded rows, **and** the floor's own denominator being inflated by rows its own refusals stranded — so a fix addressing only the cap leaves the second intact.

Every floor-bearing alternative failed the same way, for one reason:

> **A payload-size numerator recovers when rows strand; an overlap numerator does not — and V1 has no numerator to ratchet at all.**

And the floor's entire contribution on this grain is small and is exactly the harmful region. Churn-free, a floor can only add a refusal where it refuses while the cap permits, which forces a stored roster of ≤ 3 rows — which is precisely where the lock is produced. Under an inverted bias that contribution is not dead weight; it is the harm. (That theorem carries an unstated premise, `churn = 0`; with churn the divergence is unbounded in churn rows. Both halves matter for fixture sizing — see AC-1.)

### The bound V1 leaves behind is a RATE, not a total, and protection runs backwards with respect to severity

`MAX_ROSTER_DEPARTURES` guarantees **≤2 pre-existing roster rows deleted as departures per *retire invocation*, per `(team_id, season_id)`** — any crawl, any roster size, any churn. It does **not** bound cumulative loss. Executed, 13-row roster:

```
PROGRESSIVE to empty (11,9,7,5,3,1)   per-run [2,2,2,2,2,2]   total 12 of 13   survivors 1
CATASTROPHIC (drops to 1, repeated)   per-run [0,0,0,0,0,0]   total 0          survivors 13
```

A gently degrading crawl empties a roster two rows at a time with the cap permitting every step; a catastrophically broken crawl loses nothing, because the cap refuses. **"Bounded at ≤2" reads as a bound on damage and is a bound on speed.**

**This is a genuine trade, not a defect, and this half must never be dropped**: the same 2-per-run shape is *exactly correct behaviour* for a real roster losing two players a week. The cap cannot distinguish a genuine progressive departure sequence from a progressively degrading crawl — they are byte-identical at every step, and any gate that could tell them apart would need evidence the crawl does not carry. The residual is **ACCEPTED, not closed**.

The unit is per *retire invocation*, not per run: three `team_rosters` delete paths exist (`retire_departed_roster_players` here, `_delete_or_update_rosters` in `src/db/player_dedup.py` — uncapped and later in the same `_load_team_core` — and `_delete_team_scoped_data` in `src/reports/lifecycle.py`), one `generate_report` reaches all three, and morning-run walks several teams per process.

### Why the scope argument survives V1

The grain is in scope because the operator's brief explicitly asked us to check it. It is inert today only because the cap fires before the floor can do damage — **masking, not protection** — and a guard whose only protection is a second, independently-owned policy constant is not a guard. That criticism lands on **the gate** (decorative), not on the **arrangement** (cap-only too weak): removing the gate cures the concealment, and the cap that remains does visible, rate-limited, stated work. Separately, leaving one of three grains reading post-upsert leaves the next grain a broken template to copy, where "the next grain" is a **costed backlog item** — `.project/ideas/IDEA-154-per-perspective-game-retire.md` — not a hypothetical.

*(An earlier version of this paragraph called the cap "tunable" and argued someone would eventually change it. That prediction was pre-registered as a falsifier and **falsified** — the value is locked since E-267 with no proposal anywhere to move it — so it is deleted rather than softened. Reading the surviving sentence as a sufficiency claim resurrects a retired argument.)*

> ### ⚠️ FIXTURE TRAP — it produces a silently INVALID test that looks correct
>
> **Any test here needing two DISTINCT games for one team MUST vary the DATE.** Two games for one team on the same date **collapse into a single `games` row** via E-261's cross-perspective natural key (`season_id` + `game_date` + unordered team pair). A fixture that does not vary the date yields clean-looking output and a wrong conclusion.
>
> **The tell, from the instance that hit it**: a player held **zero batting rows after a run in which he batted.** Nothing errored; the output read as a normal result.
>
> Recorded here rather than left to be rediscovered because it is this epic's own defect class **arriving in the test scaffolding** — a fixture that is scope-accurate about what it builds and false about what it exercises. It bites hardest on exactly the constructions this story must port, which need a fork's two ids to appear in *different* games.

## Acceptance Criteria

- [ ] **AC-1 (the floor is removed — this story's discriminating case)**: The roster grain permits a retire iff the fresh roster payload is non-empty **and** the genuine-departure cap permits. No floor ratio is consulted on this grain, under any input.

      **Discriminating fixture, churn-free**: a **3-row** stored roster whose fresh crawl carries **1** of them. Pre-fix the floor fires (`1 >= 0.5 * 3` fails) and **nothing is retired**; post-fix the cap sees 2 genuine departures, permits, and **both absent rows are retired**. This test FAILS against pre-fix code and PASSES after.

      **The sizing rule, so a variant is derivable rather than guessed.** Write `a` for stored rows still present in the fresh crawl and `b` for stored rows absent from it. A floor can only refuse where the cap permits when `a < b <= MAX_ROSTER_DEPARTURES (= 2)`, so **churn-free, every discriminating shape has a stored roster of ≤ 3 rows** — exactly `(a,b) ∈ {(0,1), (0,2), (1,2)}`. The fixture above is `(1,2)`. **That bound holds only at `churn = 0`**; with backfill churn present the floor's denominator is the live population while the cap counts only `absent ∩ previously`, the two diverge, and the divergence is **unbounded in churn rows** — which is what AC-2's second fixture exercises at ordinary roster size.

      **Do NOT use the 9-stored / 9-brand-new shape here.** It is the shape the originating handoff's acceptance criteria specify and it discriminates at the **player-line** grain. At this grain `absent ∩ previously` = 9 exceeds the cap, so the cap refuses under both regimes and the test cannot fail. Inheriting it would have shipped a regression test that cannot fail, inside the epic written to fix a defect that survived because nothing could catch it.

- [ ] **AC-2 (the churn-region divergence, at ordinary roster size)**: DE's whole-set construction — **10 rostered, fresh crawl drops 2, 20 backfill-churn rows** — is a test. Pre-fix the floor refuses and **zero** rows are retired. Post-fix the cap permits (`absent ∩ previously` = 2, at the cap) and **22 rows are retired: the 20 churn rows and exactly 2 pre-existing rows**, with the 8 survivors intact.

      Assert the pre-existing count explicitly, not just the total. **This test is what pins the cap — and not a floor — as the thing bounding pre-existing loss**, and it is the executable form of the accepted rate residual. It was built to defeat a deletion-neutrality claim; under V1 it executes, which is the change of régime this story ships.

- [ ] **AC-3 (which mechanism refused — binding, per TN-11)**: A refusal assertion MUST identify which mechanism refused. Two can produce "0 retired" on this grain under V1 — an **empty fresh payload** and the **cap** — and a third state, "no absences, nothing to decide", must not read as either.

      Assert on a **structural record carried by the result dataclass, never on WARN prose** — a test that greps log text passes when someone rewords the message. The record must carry, at minimum, which mechanism refused and that mechanism's own counts. `RosterRetireResult` today carries `retired_player_ids`, `refused`, a prose `refusal_reason`, `roster_db_count`, `fresh_crawl_count` and `absent_count`: enough to know *that* it refused, **not which mechanism did**. **Adding the fields is a production change required under either sanctioned means** — read epic TN-17 before writing this test, because `_reconcile_departed_roster` logs a summary and discards the result, so the record is not reachable by default either. Patch target for this grain is `reconcile_at_load` (function-local import); assert positively that the spy captured a result.

      **`roster_db_count` is the epic's own numeric tell** — the original audit identified the defect from a `roster_db_count=4` on a roster that only ever held three rows. It must remain asserted and must remain the exempt-filtered live prior count, which is the population the candidate set is drawn from.

- [ ] **AC-4 (behaviour-unchanged regression: churn retirement)**: Given a first load (empty `previously_rostered_ids`, 13 rostered plus 3 backfill churn rows), **exactly the 3 churn rows are retired, unrefused**. Given the ordinary steady state (13 roster, 13 fresh, 3 churn), the same. Both are identical to today and must stay identical: the churn retire is what keeps a mid-season cut who appears in a completed boxscore from being re-added forever.

      **Assert on STATE, explicitly NOT on the retire WARN — the WARN produces a false NEGATIVE here, not a failure.** On a first load every churn row takes the **INFO-level** recurring-churn branch; the WARNING-level hard-deleted line is never emitted, so a log-grep assertion reports "nothing retired" on a run that retired all three. Assert `RosterRetireResult.retired_player_ids` (reached per TN-17) and the resulting `team_rosters` contents.

      **⚠️ This grain's own test file carries a WARNING-level log helper that silently defeats the assertion**, so a test built by reusing it satisfies nothing. **Read epic TN-11 ("Expose the gate outcome structurally, not in prose") before reusing any log helper in that file** — it names the helper, the mechanism, and the executed instance where exactly this read `retired=False` on a run that retired all three rows.

- [ ] **AC-5 (candidate population and capture site unchanged)**: The candidate population remains the **live, exempt-filtered** prior read (`_prior_roster_player_ids` minus `exempt_player_ids`), and `previously_rostered_ids` continues to scope the cap exactly as it does today. **The pre-load capture site in `scouting_loader.py` and its ordering do not move.** Nothing in this story re-wires either input; the change is the removal of the floor from the authority decision, and the deletion of the input the floor consumed if it becomes unused.

      **The exemption filter stays on the read that feeds the candidate set.** It is the only filter on any grain's prior read, and dropping or widening it changes which rows are retirable, not just which are counted.

- [ ] **AC-6 (`MAX_ROSTER_DEPARTURES` is unchanged in VALUE and newly load-bearing in ROLE — both sentences ship at the constant)**: The constant's value is untouched at 2. Two independent sentences are written **at the constant**, where a future tuner reads them — not only in this epic:

      > This constant sets the **per-invocation RATE** of pre-existing roster loss, not a total. Cumulative exposure is unbounded in the number of invocations against a progressively degrading crawl. **It is also the SOLE guard on the roster grain — there is no floor ratio beneath it.**

      **Both are required and neither implies the other**: a tuner who reads "this sets a rate" still does not learn there is nothing underneath it. The obvious phrasing is the wrong one — *"raise the cap to 5 and per-invocation loss becomes ≤5"* is technically correct **and reads as a bound**, when it means `5N`, unbounded in N, and morning-run walks several teams per process so N is not one.

- [ ] **AC-7 (PORT THE EROSION CONSTRUCTION — a test, not documentation)**: A **26-row roster against a progressively degrading crawl over 5 invocations** lands in `tests/` as a real test with real assertions: at cap 2, **16 survivors**; at cap 5, **1 survivor**. It is the executable form of *"rate, not bound"* and it is the only thing that would meet a future cap-tuner with a gate.

      **Why the existing tests do not cover it** [verified by fixture enumeration]: three tests do fire if the cap is raised — the pin `assert MAX_ROSTER_DEPARTURES == 2` at `tests/test_reconcile_at_load.py:191`, plus two behavioural ones — but **every one fails for the reason "the cap moved", which is exactly what a tuner intends.** They are items on the tuner's own change list. **No test in the suite encodes the CONSEQUENCE of a cap value at any value**, so a tuner who raises the cap and correctly updates all three gets a green suite and learns nothing about `5N`.

      **The cap must be varied through the injection point, not by monkeypatching the constant** — `roster_departure_guard`'s `max_departures` default binds at *definition* time. Note while writing it that this parameter has **zero callers in `src/` or `tests/`** today; "no caller does X" is an observation about the current tree, not an invariant, and this test is the first caller.

      This construction was **absent from epic TN-16's port list** until late in planning — found after the list was written and never added — which is TN-16's own rule (*a construction that exists only in a transcript is not a regression test*) falling on TN-16.

- [ ] **AC-8 (port the remaining executed constructions)**: Two further constructions land in `tests/` as real tests:

      **(a) The 2-vs-2 characterization test** — 2 stored ids against 2 brand-new fresh ids. Under V1 this **permits and retires both**, identically to today. It was the discriminating fixture for a floor-bearing design and is now a **characterization test of the accepted behaviour**: it pins that this grain does not refuse there, and it fails if someone re-adds a floor.

      **(b) The classification-universe slip** — the executed two-run construction in which `previously_rostered_ids` (or any pre-load-derived set) is passed as the classification universe rather than the live prior read. Run 1 then retires nothing where the correct form retires the 3 churn rows; run 2 those rows are pre-existing, trip the departure cap, and become **permanently** unretirable. **This is more consequential under V1, not less** — the cap is now the only guard, so a slip that feeds it a wrong population has nothing beneath it. Story 01 AC-9b owns the primitive-level contract test; this story owns the executed two-run construction. Write the two-run construction here; do not re-write story 01's contract test under a second name.

      **(c) A multi-run sequence at this grain that ends with survivors.** AC-7's erosion construction at cap 2 satisfies this (16 of 26 survive); no separate test is required if AC-7 asserts the per-invocation sequence and not merely the endpoint. Stated because every probe and sweep during planning was single-run and the failures that reopened this design were multi-run.

      **MANDATORY, and the failure is invisible**: two source probes are already named `test_*.py` and already contain `def test_` functions with **zero assertions**. Copying them yields tests pytest collects and passes unconditionally, forever, proving nothing — and it would not look wrong in a diff. **Treat every printed value as an assertion to write, never as output to preserve.** A ported file containing `def test_` with no `assert` fails this AC.

- [ ] **AC-9 (prose the fix falsifies, corrected in this same change)**: The prose sites assigned to this story in epic TN-9 are corrected here, plus one this story adds:

      **(a)** `retire_departed_roster_players`' docstring and the `_cap_on_genuine_departures` comment, both of which describe the arrangement as a cap layered *under* a floor and the pre-load capture as feeding only the cap.

      **(b)** The `MAX_GAME_RETIREMENTS` comment asserting *"a refused retire self-heals, a wrong delete is irreversible"* **and citing the `MAX_ROSTER_DEPARTURES` cap as its precedent** (`src/db/reconcile_at_load.py`, above the constant). **SCOPE IT TO THE GAME GRAIN — DO NOT DELETE IT**; it is correct where it was written and backwards for roster, and under V1 the roster grain no longer prefers-refuse at all, so the precedent citation is doubly wrong. This is **the sentence that made bias-to-refuse feel *safe* on roster**, which is why the analogy went unchallenged by four reviewers.

      **(c) NEW, and it is not in TN-9's table** [PM-VERIFIED, clean read]: `retire_departed_roster_players`' docstring states this grain's failure mode is *"grid clutter, never a corrupted stat, which is what separates this grain from the game and player-line grains."* **V1 falsifies that in the band régime** — a roster delete there can collapse a refused dedup fork into an executed merge and silently reassign a stat row ([[IDEA-188]]). The sentence must be scoped, not deleted: it is true outside the band, and it is the sentence the operator's prefer-delete ruling rests on, so a reader must not be left believing it holds unconditionally.

      Also sweep the module docstring's roster-grain description: it currently narrates a cap operating beneath a flat floor, in more than one place.

- [ ] **AC-10 (the operator-facing WARN names its refuser)**: When this grain refuses, the WARN MUST name the refusing mechanism and carry **that mechanism's own counts**.

      **This is a preservation requirement, not a new capability** [PM-VERIFIED, clean read of `retire_departed_roster_players`]. The refusal path already emits two distinguishable reasons — a not-authoritative one carrying `fresh_crawl_count` / `fresh_comparable_count` / `roster_db_count` / `floor_ratio`, and a cap one carrying `absent_count` / `MAX_ROSTER_DEPARTURES`. Removing the floor **changes the first branch's meaning**: it stops being "suspected partial crawl" and becomes "the fresh roster crawl was empty", and `fresh_comparable_count` and `floor_ratio` stop being the counts that decided anything. Leaving them in place ships a message whose numbers no longer explain the decision.

      **This is not a duplicate of AC-3, and the two do not conflict.** AC-3 governs what a *test* asserts on and forbids the WARN as an assertion target. This governs the *message itself*, which in production is the operator's only signal. The record is the source and the WARN renders from it, never the reverse — so a test for this AC may assert on the message text, because here the message **is** the deliverable.

      **There is a standing case for why the message matters, already filed.** [[IDEA-186]] describes a permanent roster lock in which the cap refuses forever, and records that its whole difficulty is that **"it looks exactly like the guard working"** — a recurring refusal WARN indistinguishable from ordinary bias-to-refuse. Under V1 the cap is the only refuser left, so this is now the *only* signal that separates them. Making the symptom legible costs one string.

- [ ] **AC-11 (suite green, with exactly one expected assertion change)**: `python -m pytest tests/` reports 0 failed.

      **`tests/test_roster_grain_reconcile.py::test_catastrophic_roster_shrink_refuses_on_the_floor` keeps its OUTCOME and loses its REASON.** Sized 14 prior / 1 fresh, it refuses under V1 too — but by the cap (13 genuine absences), not the floor. Its assertion `"floor_ratio" in warnings[0]` fails, and its name and docstring (*"the flat floor still applies underneath the cap"*) become false. **Specify this as an EXPECTED CHANGE, not a regression**, and rename it so the file does not carry a test whose name asserts a design that no longer exists.

      Beyond that, the two direct helper call sites in this file (per TN-13) take the mechanical keyword-argument churn in this same change.

## Technical Approach

The design and its derivations are in the epic's Technical Notes — TN-9 (prose sites), TN-11 (the wrong-reason trap and the structural record), TN-12 (test design), TN-14 (guardrails), TN-17 (reaching the record) — and in full, with the executed evidence and the losing positions, in:

- `/workspaces/baseball-crawl/.project/research/E-276-roster-design-recommendation.md` — the authors' artifact (SE + DE, adversarially read by CR and CR-2), recovered verbatim from session transcripts. **This is the primary source and it governs on wording.**
- `/workspaces/baseball-crawl/.project/research/E-276-roster-design-record.md` — PM's independent record, reconstructed from relayed executions. Where the two diverge, the first governs and the divergence is the object of interest.

**The code change is smaller than this story is.** The pre-load capture already exists at the correct anchor and is already threaded to the retire; the candidate read already exists and is already exempt-filtered. What changes is the authority decision: the floor comes out, the empty-payload refusal stays, the cap is untouched. Whether that is a parameter on the shared authority check or a roster-local decision is the implementer's call, under the constraint from story 01 that the shared check must not be changed unconditionally for every grain.

**If you find yourself re-proposing a floor here, five inputs are what any replacement must pass, and the fifth is why the other four are not enough**: DE's truncated crawl · CR-2's churn sequence · CR's truncation-plus-churn · SE's 13-row-plus-14-churn · **sustained truncation without recovery**. Both rejected floor-bearing designs passed the first four **precisely because all four recover**. Under the fifth, both V1 and every floor-bearing alternative are permanently wrong in opposite directions, and the ruling chooses which wrongness: a wrong delete converges on the only evidence available, while a strand persists *against* evidence. Re-derivability is the **supporting** argument, not the load-bearing one — it is false in exactly the case the ruling turned on, and it reaches the `team_rosters` **row** but not the delete's downstream effect on the identity graph.

## Dependencies
- **Blocked by**: E-276-01 (the shared authority check's shape, and the gate-outcome record type this grain's result must carry), **E-276-02** (both stories modify `src/db/reconcile_at_load.py`, so an ordering is required — see the epic's Stories section)
- **Blocks**: E-276-05

## Files to Create or Modify
- `src/db/reconcile_at_load.py`
- `tests/test_roster_grain_reconcile.py`
- `src/gamechanger/loaders/scouting_loader.py` — **conditional, and only under TN-17's second sanctioned means** (plumbing the record up through the loader's result object). Not touched under the spy means, and **the pre-load capture site and its ordering do not move under either**. E-276-02 already modifies it and blocks this story, so the ordering is explicit either way.

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-276-05**: the corrected roster-grain claim — that this grain ships with no floor and a cap as its sole guard — so the CLAUDE.md replacement paragraph describes all three grains accurately rather than describing one design across three.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing. **The DISCRIMINATING tests — AC-1's 3-row churn-free fixture and AC-2's whole-set construction — demonstrably FAIL against pre-fix code and PASS after.** Scoped deliberately: AC-4 requires behaviour IDENTICAL to today, so a blanket fail-before/pass-after line would demand that the churn regression fail pre-fix, which would mean it was not a regression test. AC-8(a) is a characterization test that passes under both regimes by design, and AC-8(b) exercises a slip in code that does not exist pre-fix.
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests, beyond the single expected assertion change named in AC-11
- [ ] `data/app.db` untouched; no network; synthetic DBs from `migrations/` only

## Notes

**The fork chain is a known, accepted, and partly WIDENED consequence of this story — declined as an AC deliberately, so a reviewer does not read its absence as an oversight.** A roster delete can destroy the ambiguity that caused `plan_player_dedup` to refuse a fork, and the same run's dedup sweep then executes the merge. Today's code fires this identically in the ≤3-row region; V1 extends its reach into a two-value churn band (`c ∈ {R−1, R}` at every roster size tested), where today is healthy and refuses only the departure. In that band one branch **destroys** a stat row and the other **silently reassigns** one — no row count changes, the report renders, totals reconcile. Ruled not-a-blocker per régime, with the band named as the one place the ruling's premise does not reach and its occupancy unmeasured. Filed as [[IDEA-188]]; the lock régime is [[IDEA-186]]. Do not add scope here; do not claim fix-neutrality either.

**A parameter's role widening is not caught by the rule's own search heuristic.** `.claude/rules/testing.md` gives the searchable tell as negative-property test names (`..._cannot_influence_...`, `..._never_affects_...`, `..._is_a_noop_...`). The roster test whose meaning this story changes is `tests/test_roster_grain_reconcile.py:891::test_previously_rostered_ids_scopes_the_cap_population` — a **positive**-property name, invisible to that heuristic. It pins `previously_rostered_ids` as scoping the **cap**; under V1 the cap is the *only* consumer left and the only guard on the grain, so the test's subject is now load-bearing in a way its docstring does not say. It will keep passing. **Do not treat the rule's heuristic as the search**: re-read every test that mentions the parameter by name, not only those whose names sound negative.

**One executed construction from planning is deliberately NOT ported, and the reason belongs here rather than being left as a silent omission.** `scratchpad/t_divergence_sweep.py` (the three-space sweep whose count moves 20 → 26 → 44 while the shape set stays byte-identical) measured divergence between a floor and a corrected floor on this grain. **Under V1 there is no floor, so it has no subject in the code.** Its finding — that a count is range-dependent while a characterization is not — is a process finding, not a property of the shipped design, and belongs with the epic's process record rather than in `tests/`. **Epic TN-16's port table now records it as NOT PORTED with this reason** (corrected 2026-07-25; it previously listed it as a story-03 port target).
