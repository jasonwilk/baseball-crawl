# E-276 — Roster-Grain Design Record and Derivations

**Date**: 2026-07-25. **Status**: design settled (V1), epic not yet READY.
**Author**: product-manager, assembled from software-engineer and data-engineer executions and code-reviewer analyses relayed during E-276 planning.

---

## ⚠️ WHAT THIS FILE IS, AND WHAT IT IS NOT

**It is NOT the SE/DE joint artifact.** That artifact (`8a2de87b` plus addenda `b68ea4df`, `025497f1`, `e6e75596`, `75050729`, `69b5b96c`, `d165e018`, and later) was assembled in agent context and, at time of writing, **exists on no filesystem** — independently confirmed by two reviewers, one of which searched correctly (ERE, one path per invocation, with a positive control after hitting the documented ugrep silent-empty quirk) before concluding the absence was real.

**This file is the PM's own record**, written to satisfy a pre-READY gate the PM set: *a design settled in an artifact on no filesystem is a citation that resolves to nothing.* It carries the derivations, régime tables and rejected designs so that `epic.md` does not have to, and so the epic's History extraction has a destination.

**Provenance discipline, because this epic's subject makes it non-optional**: every executed result below was **run by SE or DE and relayed to PM**. PM did not execute any of it and has not seen the source scripts. Results are marked `[EXECUTED, <agent>]`. Where PM verified arithmetic first-hand, it says so. **§6's text below is a relay of a relay** and is marked as such.

> **⚠️ PRIMACY — this file is the CHECK, not the source.** `E-276-roster-design-recommendation.md` is **primary**: its §6 was recovered **verbatim from session transcripts**, whereas this file was **reconstructed from relayed executions.** For a finding that turns on a single word, a reconstruction is worthless — and **actively misleading if it happens to render the word correctly**, since it would then corroborate by accident. Where the two disagree, **the authors' file governs and the divergence is the object of interest.**

**UPDATE 2026-07-25 — the authors' artifact HAS landed**: `.project/research/E-276-roster-design-recommendation.md`. **It is the primary source and this file is the independent check**, not the other way round — the authors' §6 was recovered **verbatim from session transcripts** rather than reconstructed, precisely because a single-word audit makes a reconstruction worthless and, if it happened to render the word correctly, actively misleading. **Diff the two rather than deleting either**: two records of one design written from different vantage points, neither derived from the other, and where they disagree the disagreement is the object of interest.

**⚠️ A BOUNDARY ON EVERY "VERIFIED ON DISK" CLAIM ABOUT THAT FILE.** The artifact has been edited repeatedly during review, and the sizes reported by different parties disagree because they observed different moments: 34,208 bytes at one read, **34,865 bytes ~90 seconds later** (with §12's quote moving from line 352 to 354 between a reviewer's read and its own grep), and 39,898 bytes reported later still. The reviewer's byte-clean repair audit therefore covers **one timestamped state**, and material landing after it is outside that finding — which the reviewer disclosed rather than letting the audit read as covering the current file. **A file-state verification is a claim with a timestamp, exactly like a handoff**; "verified on disk before reporting" bounds what was verified, not what is there now.

---

## 1. The design

**Corrected gate (pre-upsert snapshot population) on GAME and PLAYER-LINE. No floor ratio at all on ROSTER. The conjunction is dropped as inert everywhere.**

Roster grain, in full:

```
permit = (fresh payload non-empty) AND (|absent ∩ previously| <= MAX_ROSTER_DEPARTURES)
```

Neither today's legacy floor nor a corrected one. `MAX_ROSTER_DEPARTURES` value untouched at 2; the design changes only what the cap is *fed*, never what it is *set to*.

### The mechanism that explains every rejected alternative

> **A payload-size numerator recovers when rows strand; an overlap numerator does not — and V1 has no numerator to ratchet at all.**

That is why *every* overlap-based design failed rather than merely a list of which ones did. Any gate whose denominator is a snapshot-derived population **ratchets**: its own refusals preserve rows that re-enter the denominator, while the numerator (overlap with fresh) does not grow. Corroboration-based narrowing changes *which* rows ratchet, not *whether*.

Today's gate escapes for a mechanical reason worth stating precisely: **its numerator and denominator share the fresh payload.** The live population includes this run's fresh writes, which are in `fresh` by construction, so they raise both sides together. Not accidental — it is the only structure tested that cannot ratchet.

### Three non-transfers

1. **Payload-size numerator** — a payload arbitrarily unlike what we stored clears the gate simply by being large enough. Survivable on roster **only because the cap covers it**. **Player-line has no cap.**
2. **Prefer-delete** — defensible here because the `team_rosters` **row** is re-derivable from the roster crawl plus jersey backfill. **False on player-line**, where a deleted stat row is gone. See §5 for the carve-out on what re-derivability does *not* reach.
3. **The fork residue** (§6) is roster-shaped and does not generalise.

**Never describe a roster-specific shape as *the* reconcile gate.**

---

## 2. The inertness theorem

```
gate refuses  <=>  survivors < absent
cap permits   <=>  absent <= MAX_ROSTER_DEPARTURES (= 2)
together      =>   absent in {1,2}, survivors in {0,1}  =>  stored roster <= 3   QED
```

[Derived, SE; exhaustive check over stored 1..25 × all absences × new-ids 0..11 agrees, EXECUTED]

**Generalises past the corrected gate**: *any* floor can only add a refusal where it refuses while the cap permits, which forces stored ≤ 3. So the floor's entire contribution on this grain — legacy's included — is the 1-3 row region, which is exactly where it produces the lock (§4). Under an inverted bias that contribution is not dead weight; it is the harm.

**⚠️ The theorem carries an UNSTATED PREMISE: churn = 0.** With churn present, today's floor denominator is the **live** population (`snapshot + churn`) while the cap counts only `absent ∩ previously` — the two diverge, and the step `survivors < absent ≤ 2 ⟹ stored ≤ 3` fails **because it silently assumed both guards read the same population.** See §6. The theorem is narrowed, not refuted: *no widening in the churn-free case.*

---

## 3. The bound is a RATE, not a total

**General guarantee**: ≤2 pre-existing roster rows deleted **as departures** per *retire invocation*, per `(team_id, season_id)`. Any crawl, any roster size, any churn.

**It does not bound cumulative loss.** [EXECUTED, SE/DE]

```
STATIC crawl (11 of 13, repeated)        per-run [2,0,0,0,0]      cumulative  2   terminates
PROGRESSIVE (11,9,7,5,3)                 per-run [2,2,2,2,2]      cumulative 10   unbounded
PROGRESSIVE to empty (11,9,7,5,3,1)      per-run [2,2,2,2,2,2]    total 12 of 13, 1 survivor
CATASTROPHIC (drops to 1 or 3, repeated) per-run [0,0,0,0,0,0]    total 0, 13 survivors
```

**Static-crawl sharpening**: for a *static* truncated crawl cumulative loss is ≤2 across all runs — deleting the missing rows leaves survivors fully covered, the next run sees zero, and it terminates. **"≤2 across all runs" unqualified is FALSE for the progressive case, and it is the reassuring half — the one that survives summarisation.**

### Protection runs BACKWARDS with respect to severity

A **gently degrading** crawl empties a 13-player roster two rows at a time with the cap permitting every step. A **catastrophically broken** crawl loses nothing, because the cap refuses. *"Bounded at ≤2" reads as a bound on damage and is a bound on speed.*

**It is a genuine TRADE, not a defect, and this half must never be dropped**: the same 2-per-run shape is *exactly correct behaviour* for a real roster losing two players a week. **The cap cannot distinguish a genuine progressive departure sequence from a progressively degrading crawl — they are byte-identical at every step**, and any gate that could separate them would need evidence the crawl does not carry. **The residual is therefore ACCEPTED, not closed.**

### The cap-tuning erosion result

```
26-row roster, progressively degrading crawl, 5 invocations
  cap=2   per-invocation [2,2,2,2,2]   cumulative 10   survivors 16
  cap=5   per-invocation [5,5,5,5,5]   cumulative 25   survivors  1
```

**Raising the cap to 5 does not mean "5 lost". It means 5 per invocation — `5N`, unbounded in N** — and morning-run walks several teams per process, so N is not one. This is the construction story 03 must port; see §8.

### Unit and surface

Per *retire invocation*, not per run. **Three `team_rosters` delete paths**, and they are **COUPLED, not independent** — the first can *trigger* the second within one run:

| Symbol | Module | Note |
|---|---|---|
| `retire_departed_roster_players` | `src/db/reconcile_at_load.py` | the capped retire |
| `_delete_or_update_rosters` | `src/db/player_dedup.py` | the merge — **uncapped**, later in the same `_load_team_core` |
| `_delete_team_scoped_data` | `src/reports/lifecycle.py` | orphan reclamation |

**Symbol anchors, not line numbers** — an artifact establishing a bound while breaking the stable-anchor rule is the shape this epic exists to catch. **Trap**: a naive lookup from the old `reconcile_at_load.py:1364` lands on `_cap_on_genuine_departures`, a **nested def at indent 4**; the DELETE sits in the enclosing `retire_departed_roster_players`.

**Strong form of the guarantee**: it holds because **the guard and the delete consume the identical set object** — no drift surface between check and action, a stronger artifact than two computations agreeing.

---

## 4. Why the conjunction was dropped — the roster lock

A code-reviewer counterexample, **reproduced through the real `ScoutingLoader`, both regimes side by side** [EXECUTED, DE]:

```
DB {a,b,c}; cap=2
Run 1  fresh {a,n1}      legacy 2>=2 PERMIT | cap 2<=2 PERMIT | corrected 1>=1.5 REFUSE
       TODAY retires b,c -> {a,n1}           CONJUNCTION refuses -> {a,b,c,n1}
Run 2  fresh {n1,n2,n3}  TODAY retires a -> clean.  CONJUNCTION refuses again
Run 3+ healthy crawl, both gates PERMIT.
       cap: absent {a,b,c} ∩ previously = 3 > 2  -> CAP REFUSES, FOREVER
```

Today's code converges to a clean roster; the conjunction **locks the team-season permanently** — three players stranded on the coach-facing grid, every subsequent genuine departure blocked.

**Fed by TWO mechanisms, not one**: the cap counting the stranded rows, **and** the corrected gate's own denominator being inflated by rows its own refusals stranded. A fix addressing only the cap leaves the second intact.

**How it was missed**: ruled out for the adopted design by reasoning about the **candidate** population and never re-checked through the **gate**. The mechanism was already documented; nobody re-ran it against the conjunction.

**It does NOT contradict deletion-neutrality**, which is only ever about never *permitting* a deletion today refuses. This is the opposite direction — a refusal that compounds. Conflating them is how it survived.

---

## 5. The ruling: V1 over V4, and what it actually chooses

The two designs differ **only at `snapshot = 3`** (derived, then independently re-derived and executed: V4 ≡ V1 for every snapshot ≥ 4).

- **Transient truncation** — V4 refuses once and recovers; V1 deletes and the next healthy crawl **restores the roster row**. V4's advantage is avoiding one run of a short grid: **visible discontinuity.** (An earlier phrasing, *"V1 does not lose data there"*, is **FALSE** — see §6.)
- **Sustained truncation, no recovery** — **both designs are permanently wrong, in opposite directions.** V4 strands two rows indefinitely; V1 deletes rows the crawl no longer evidences, and re-derivability is conditional on a healthy crawl this case does not have. **Permanent-while-broken, not self-healing.**

> **The ruling chooses which wrongness. It does not choose between a wrong option and a costless one.**

It goes to V1 because the operator ruled prefer-delete on this grain, and because **a wrong delete at least converges on the only evidence available, while a strand persists *against* evidence.**

**The losing argument, stated strongly enough to attack**: V4 restores the protection V1 loses in exactly the region V1 loses it and nowhere else, because a payload-size numerator recovers when rows strand while an overlap numerator does not. That is true, and it is a better argument than the one originally made for V4.

**Struck, and it was the team lead's own**: *"V1's cost under persistent truncation: none — it converges to the truth."* Too clean; it holds only if the truncation reflects reality.

**⚠️ Re-derivability is the SUPPORTING argument, not the load-bearing one.** The design was ruled on **sustained truncation without recovery** — precisely the case where re-derivability is **false**, since the mechanism that would restore the row is the thing that is broken. **Which-wrongness carries it.** And the row/delete carve-out: the **row** is re-derivable; **the delete's downstream effect on the identity graph is not** (§6).

**Provenance of the deciding comparison**: the cosmetic-vs-permanent comparison only became available **because two agents had each executed a different half of the region.** *The comparison was cheap; producing the halves was not.*

---

## 6. The fork chain — pre-existing AND widened

> **A delete in the roster grain silently converts a REFUSED dedup fork into an EXECUTED merge.**

Fork members are **not exempt** from the retire. Deleting one maximal member **destroys the ambiguity that caused the refusal**; the same run's dedup sweep then sees an unambiguous pair and merges. [EXECUTED, SE; confirmed pre-existing by DE]

```
1  intact fork, dedup runs      batting=[janet:3, john:4, jstub:2]   roster=[janet, john, jstub]
2  retire deletes Janet         batting unchanged                    roster=[john, jstub]
3  SAME RUN, dedup sweep        batting=[janet:3, john:4]            roster=[john]
4  next healthy crawl restores  batting=[janet:3, john:4]            roster=[janet, john]
```

Step 4 restores the roster row and **does not restore the merged-away stat row or un-merge the identity.**

### The widening, and the three régimes

```
R = 13-row roster containing the fork trio; crawl drops one player; c = backfill churn rows
c    healthy_refused  churn_left_after_healthy  departure_refused  janet_alive
11      False                 0                     False            False
12      False                 0                     True             True     <- BAND
13      False                 0                     True             True     <- BAND
14      True                 14                     True             True     <- LOCK
```

Today **locks** at `c > R` but refuses **departures** from `c > R − 2`, because a healthy run compares `R` against `0.5(R + c)` while a departure run compares `R − 1`. **The band is exactly `{R−1, R}` at every roster size tested (9, 11, 13, 15) — two wide, scaling with `R`.**

| régime | today | V1 | trade |
|---|---|---|---|
| `c ≤ R − 2` | permits | permits | no widening |
| **band `{R−1, R}`** | healthy; churn clears; **stats untouched**; one player on the grid | player retired correctly; **fork breaks** | **grid clutter vs a corrupted stat** |
| `c > R` | **permanently locked** | **converges** | the ruled trade |

### Both fork branches, and one is INVISIBLE

`merge_player_pair` is delete-or-update:

| Case | Effect | Team sums |
|---|---|---|
| Fork **REFUSED** | split per-player line; one human's season understated | correct |
| Fork **BROKEN**, ids share a game | colliding rows **DELETED** | **WRONG, low** — detectable, row count changes |
| Fork **BROKEN**, distinct games | `lost:[('s1','game-0002')] gained:[('f1','game-0002')]` | correct — **no row count changes, nothing looks wrong** |

> **A report reader sees a plausible stat line.**

A loss announces itself; a **silent reassignment does not**, and this project's premise is that a coach reads the report as fact.

**Why the band matters to the ruling**: `retire_departed_roster_players`' docstring says this grain's failure mode is *"grid clutter, **never a corrupted stat**, which is what separates this grain from the game and player-line grains."* **In the band a roster delete produces exactly that.** The prefer-delete ruling rests on roster failures being recoverable grid-level issues — so *"the same trade already ruled on"* **claims a coverage the ruling does not have.**

**Not a blocker**: pre-existing (today fires it identically), the band is two values of `c`, and **its occupancy is unmeasured.** Filed as IDEA-188; one régime with IDEA-186.

---

## 7. Five required inputs

DE's truncated crawl · CR-2's churn sequence · CR's truncation-plus-churn · SE's 13-row-plus-14-churn · **sustained truncation without recovery.**

**The fifth exists because both rejected floor-bearing designs passed the first four — precisely because all four recover.** Without that sentence a future reader adds a sixth without understanding why four were not enough.

---

## 8. Obligations carried into the epic

1. **Constant wording** — two independent sentences at `MAX_ROSTER_DEPARTURES`: it sets a **per-invocation RATE**, not a total, cumulative exposure unbounded in N; **and** it is the **SOLE guard** on the roster grain, no floor beneath it. A tuner reading "rate" still does not learn the second.
2. **Port the erosion construction** (§3) into `tests/` — an AC, not documentation. Three tests do fire at cap 5, but **every one fails because "the cap moved", which is the tuner's own intent**; no test at any cap encodes the *consequence*.
3. **Dead override**: `roster_departure_guard`'s `max_departures` has **zero callers**. "No caller does X today" is an observation about the current tree, not an invariant — and the definition-time default binding makes the injection point the only supported way to vary the cap in a test, so the first cap-sensitivity test deletes the property.
4. **Multi-run checks** — game grain CLEAN with mechanism (newly-completed games raise numerator and denominator together, so the strand cannot outgrow the recurring set); player-line diverges, not reopened.
5. **Fixture trap** — two games for one team on the same date **collapse into one `games` row** via E-261's natural key. Any test needing two distinct games must vary the **DATE**. The tell is a player holding zero batting rows after a run in which he batted.
6. **`W ⊆ fresh` is a NAMED PREMISE** for neutrality on game and player-line, not a structural guarantee: could not be falsified (one `INSERT INTO games` path; 179 runtime invocations), which is not proof.

---

## 9. §6 of the SE/DE artifact — RELAYED TEXT, ruling outstanding

**Marked as a relay of a relay. Neither PM nor the reviewing agent has seen the source.**

> A cap is not sufficient *as a substitute for a correct gate*, but it is an adequate bound on pre-existing loss when the failure it bounds is re-derivable. The E-267 objection was to a gate that appeared to protect and did not, with a second guard hiding the fact — a concealed defect, not an insufficient one. Removing the gate cures the concealment; the cap that remains is doing visible, bounded, stated work.

### RULING (2026-07-25) — Check A **PARTIAL**, Check B **FAIL**. Both close with one sentence and one word.

Ruled against **this relayed copy**, not a primary source, and marked as such by the reviewer. The quotation above is **preserved unrepaired on purpose**, so the repair can be audited against the text that was assigned.

**Check B — FAIL on all three occurrences**, none qualified. **Occurrence 1 is a TRUTH-level failure, not a clarity one**: unqualified, *"an adequate bound on pre-existing loss"* is **false** — the cap bounds the **rate**, cumulative loss is unbounded, 13 rows to 1 at the shipped value. The reviewer tried to save occurrence 3 with its own pre-registered exclusion (*"bound used where surrounding sentences already establish per-invocation framing"*) and **could not**: the paragraph contains no "per invocation", no "per run", no "rate", and no cumulative clause.

**Check A — PARTIAL, exactly as pre-registered.** A1 is satisfied **on the letter** — sentence 1 is conditional (*"adequate … **when** … re-derivable"*), so it does not *claim* to cover sustained truncation or the fork member. Two weaknesses reported as substance rather than used to escalate the tier: **the antecedent is never discharged** (§6 never says when re-derivability holds or fails, and the surrounding epic language invites a reader to assume it generally does), and **the conditional does not survive its own paragraph** (sentence 1 conditional, sentence 3 unconditional, so the reader's last impression drops the qualifier). **A2 FAILS outright**: §6 does not mention sustained truncation, does not mention which-wrongness, and names nothing as carrying the case the ruling turned on — *the design was ruled on the input where §6's premise is false, and §6 is silent about that input.* **That gap stands regardless of wording**; repairing only "bounded" would leave it.

**Sentence 2 — the concealment claim — NEEDS NO CHANGE** and was not re-opened; it was ruled HOLDS on independent corroboration in DE's own memory file.

**The repair, as ruled:**

> A cap is not sufficient *as a substitute for a correct gate*, but it is an adequate **per-invocation rate-limit** on pre-existing loss **for ordinary rows under an eventually-healthy crawl** — **cumulative exposure is unbounded in the number of invocations.** Under **sustained truncation without recovery**, and for a **fork member** whose identity-graph effect no later crawl undoes, re-derivability does not hold, and what carries the design there is the operator's ruling on **which wrongness**: a wrong delete converges on the only evidence available, while a strand persists *against* evidence.

Sentence 3: *"visible, **rate-limited**, stated work."*

**This ruling falsified one of the epic's own sentences** — the claim that the wording at the constant is *"the last place in the whole design where 'bounded' could be read as a bound on damage rather than on speed."* §6 was another such place, three times over, and it sits **upstream** of the corrected wording in the cap-tuner's highest-traffic paragraph. **A scope claim carried past its case, inside the sentence asserting the defect has nowhere left to appear** — found only because a reviewer checked the assurance instead of trusting it. The epic's sentence is now scoped and no longer claims to be last.

**Practice worth preserving**: the reviewer **pre-registered PASS/PARTIAL/FAIL criteria and an explicit anti-retro-tightening clause before seeing the text**, then held Check A at PARTIAL despite holding evidence that would have supported FAIL. A reviewer refusing to move its own goalposts after seeing evidence favouring a harsher verdict. The practice was invented the same afternoon by another agent for its own claims and **propagated agent-to-agent without being directed** — applied here to a review rather than to a claim, which removes the reviewer's ability to fit criteria to findings.

**Independent corroboration for §6's central move** (that the E-267 objection was to *concealment*, not to a cap being singular) exists outside the reconciliation, in `.claude/agent-memory/data-engineer/health_gate_prior_set_must_be_temporal.md`: *"A cap is not evidence the gate under it works… a guard whose only protection is a second, tunable guard is not a guard."* Authored before and outside the reconciliation, which makes the reading a reading rather than a rewrite.

**Residue that reading does not dispose of**: the same memory carries the actionable form — *"evaluate each guard against inputs where the OTHER guards permit."* Applied to V1: the only guards for pre-existing rows are `fetch_ok` and the cap, so evaluate the cap where `fetch_ok` permits → the degrading crawl → 13 rows to 1. **The objection is discharged as to concealment and ACCEPTED as to the residue. §6 must say both.**

---

## 10. Superseded — must not be revived

- **The conjunction** (`legacy AND corrected`) — inert everywhere; locks the roster grain (§4).
- **`prior_at_start ∩ prior_now`** in any form — its motivation was refuted (the twin merge is keyed on the source event id captured before the canonical-id rebind, so the merged-away id is always in `fresh`).
- **"gate strictly narrower"**, **"the fix never newly deletes a row that existed before the run"**, **"neutrality is relocated to the cap"**.
- **V4** and the corroboration variant — both ratchet (§1).
- **"V1's cost under persistent truncation: none"**, **"V1 does not lose data there"**, **"team sums correct either way"**, **"pre-existing and fix-neutral"**, **"V1 does not widen the fork chain"**, **"clutter identical to today"**.
- **"Matching stale prose is not evidence of correctness — it is the epic's thesis run backwards."** V4's docstring match was never an argument for it.
