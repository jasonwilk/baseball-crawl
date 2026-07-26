# E-276 — Roster Grain Design Recommendation (joint: SE, DE; adversarially read by CR, CR-2)

**Status**: settled. Team-lead has ruled on every open disposition, and every review item is closed — CR-2's two pre-registered checks PASS against the primary source, the §6 repair is verified byte-clean, and §3's reason has been replaced. Two obligations carry forward *out of* this file: the erosion construction (§3c) must be **ported into `tests/`** (PM2 holds it as an AC), and the load-target classification for the memory-write lesson is routed to claude-architect.
**Subject**: the reconcile-at-load health gate's roster grain — which gate design ships, and what it costs.
**Companion epic**: `epics/E-276-reconcile-health-gate-prior-capture/` (self-contained; it does not cite this file).

---

## 0. What this file is, and why it exists

This is the design *reasoning* behind E-276's roster-grain decision. The epic carries the conclusions; this carries the arguments, the losing positions stated strongly enough to attack, the executed evidence, and the retraction chain.

It exists because it previously did not. The artifact was assembled and revised across eleven addenda entirely inside agent-to-agent messages, and CR-2 — assigned to adversarially read §6 — searched `epics/`, `.project/`, `src/`, `docs/`, `.claude/` and every session scratchpad, hit the documented ugrep silent-empty quirk, re-ran with `-E` one path per invocation plus a positive control, and correctly reported that the document did not exist. It then declined to assert a review it could not perform.

That is this epic's own thesis turned on its central deliverable: **a construction that exists only in a transcript is not a regression test**, and a design settled in an artifact on no filesystem is a citation that resolves to nothing. PM2 has made the existence of this file a pre-READY gate.

**How to read it**: §§1–8 are the artifact in its current state, with all eleven addenda **applied inline** rather than appended. **§9** carries the remaining required items. **§10** records the ruling. **§11** is the change log and retraction chain — the part worth more than the conclusions. **§12** preserves the original §6 verbatim, because a repair to a quoted passage has to be auditable. Status and carry-forward obligations are in the header above; there is no separate open-items section.

**Provenance, and how to weigh a divergence.** **This file is the PRIMARY source.** Its text was recovered *verbatim* from the original `SendMessage` payloads in the session transcripts (`~/.claude/projects/-workspaces-baseball-crawl/<session>/subagents/agent-aSE-*.jsonl`), not reconstructed from memory. PM2's parallel record (`.project/research/E-276-roster-design-record.md`) is the **independent check**, reconstructed from relayed executions. **If the two diverge, this file governs on wording and PM2's governs on nothing by default** — the check confirms, it does not overrule.

That ordering is not a courtesy, it is a consequence of method, and it was load-bearing twice: CR-2's findings turned on a **single word** (`bound` vs `rate`), where a reconstruction would have been worthless — and *actively misleading if it happened to render the word correctly, because it would have looked like evidence*. It was load-bearing again on the "What does not dissolve" paragraph, where only the primary source could settle whether SE had rewritten it or the relay had been loose.

**Corroboration, with its limit stated precisely** — the two halves do NOT have the same evidential backing:

- **The reconciliation quote: two channels.** CR-2 diffed its own copy of PM2's relay against this recovery — **identical**. A later two-record comparison found PM2's copy character-for-character identical to this one, differing only in blockquote nesting depth. So the relay channel did not corrupt the text the entire single-word audit turned on.
- **The "What does not dissolve" paragraph: ONE channel.** **PM2's record contains no copy of it.** The finding that *"PM2's relay was accurate and SE rewrote the paragraph"* rests on CR-2's copy alone. Do not read the two-channel result above as covering it.

---

## 1. Position: V1 — RULED, not merely conceded

`permit = (fresh payload non-empty) AND (|absent ∩ previously| <= MAX_ROSTER_DEPARTURES)`. **No floor ratio on the roster grain.**

Team-lead's ruling, in its corrected form (the original reasoning was withdrawn by its author as too clean — see the retraction table in §11):

> **V4 was ruled against, not withdrawn by its author.**
>
> The two designs differ only at `snapshot = 3` (SE's derivation; independently re-derived and executed by CR, which found V4 ≡ V1 for every snapshot ≥ 4). That region splits into transient and sustained truncation:
>
> - **Transient**: V4 refuses once and recovers; V1 deletes and the next healthy crawl **restores the roster row**. V4's advantage is that it avoids one run of a short grid — **visible discontinuity, not data loss.** Framing it as "protection" is what gave it weight, and the main session did so when relaying it.
> - **Sustained, no recovery**: **both designs are permanently wrong, in opposite directions.** V4 strands two rows indefinitely; V1 deletes rows the crawl no longer evidences, and re-derivability is conditional on a healthy crawl that this case does not have — so V1's loss here is **permanent-while-broken, not self-healing.**
>
> **The ruling chooses which wrongness, not between a wrong option and a costless one.** It goes to V1 because the operator ruled prefer-deleting on this grain, and because a wrong delete at least converges on the only evidence available, while a strand persists against evidence.
>
> **The losing argument, stated for attack**: V4 restores the protection V1 loses in exactly the region V1 loses it and nowhere else, because a payload-size numerator recovers when rows strand while an overlap numerator does not. That is true, and it is a better argument than the one made for V4 when it was proposed.

**Wording constraint (CR's MUST, confirmed by execution and still binding).** The transient case must say **"restores the roster row"** — never *"does not lose data"* or *"both end correct."* Those are **false for a fork member**, within the transient run, with no sustained truncation required: the retire deletes one fork member, the fork collapses to an unambiguous pair, and the same run's dedup sweep executes a merge the planner had refused. A later healthy crawl restores the roster row and does **not** un-merge the identity or restore the stub's stat row. Executed in §7.

**Provenance of the deciding comparison** (team-lead): the cosmetic-vs-permanent comparison only became available *because SE and DE had each executed a different half of the region*. The comparison was cheap; producing the halves was not.

**Strike wherever it appears**: *"V1's cost under persistent truncation: none — it converges to the truth."*

**V4's docstring match is not evidence for it** — CR, verbatim: *"Matching stale prose is not evidence of correctness — it is the epic's thesis run backwards."*

---

## 2. The mechanism behind V1

**A payload-size numerator recovers when rows strand; an overlap numerator does not — and V1 has no numerator to ratchet at all.** That is the cleanest statement of the ratchet SE and DE mis-attributed in opposite directions, and it explains why *every* overlap-based design failed rather than merely cataloguing that they did.

**Non-transfer**: a payload-size numerator means a payload arbitrarily unlike what we stored clears the gate simply by being large enough. Survivable on roster only because the cap covers it. **The player-line grain has no cap.** Never describe a roster-specific shape as *the* reconcile gate.

---

## 3. The bound — a RATE, not a total

- **General guarantee**: **≤2 pre-existing roster rows deleted as departures per retire invocation, per `(team_id, season_id)`.** Any crawl, any roster size, any churn.
- **It does NOT bound cumulative loss across runs.** Against a progressively shrinking crawl the grain sheds up to two rows per invocation indefinitely.
- **Static-crawl sharpening (CR)**: for a *static* truncated crawl, cumulative loss is **≤2 across all runs** — deleting the missing rows leaves survivors fully covered, so the next run sees zero and it terminates.

Executed, 13-row roster:

```
STATIC crawl (11 of 13, repeated)      per-run [2,0,0,0,0]   cumulative 2    terminates
PROGRESSIVE crawl (11,9,7,5,3)         per-run [2,2,2,2,2]   cumulative 10   unbounded
```

**Do not merge these.** "≤2 across all runs" unqualified is false for the progressive case, and it is the reassuring half — the one that survives summarisation.

### 3a. Protection inverts with severity

```
PROGRESSIVE to empty (11,9,7,5,3,1)   per-run [2,2,2,2,2,2]   total 12 of 13   survivors 1
CATASTROPHIC (drops to 1, repeated)   per-run [0,0,0,0,0,0]   total 0          survivors 13
CATASTROPHIC (drops to 3, repeated)   per-run [0,0,0,0,0,0]   total 0          survivors 13
```

**A gently degrading crawl can empty a 13-player roster two rows at a time with the cap permitting every step. A catastrophically broken crawl loses nothing, because the cap refuses.** *"Bounded at ≤2" reads as a bound on damage and is a bound on speed.*

**This is a genuine trade rather than a defect** (CR): the same 2-per-run shape is *exactly correct behaviour* for a real roster losing two players a week. The cap cannot distinguish a genuine progressive departure sequence from a progressively degrading crawl — they are byte-identical at every step, and any gate that could tell them apart would need evidence the crawl does not carry. **So the residual is accepted rather than closed.**

### 3b. Unit, composition, and the three delete paths

**Unit** (CR): per *retire invocation*, not per run. Three `DELETE FROM team_rosters` paths exist, and one `generate_report` reaches all three; morning-run walks several teams per process.

- **`retire_departed_roster_players`** (`src/db/reconcile_at_load.py`) — the capped retire
- **`_delete_or_update_rosters`** (`src/db/player_dedup.py`) — the merge; uncapped, and later in the same `_load_team_core`
- **`_delete_team_scoped_data`** (`src/reports/lifecycle.py`) — orphan reclamation

> **Anchor trap, worth carrying**: a naive symbol lookup on the old line citation lands on `_cap_on_genuine_departures`, which is a **nested** def at indent 4 — the DELETE sits in the enclosing `retire_departed_roster_players`. Anyone re-deriving these anchors from line numbers will hit that.

**These three are COUPLED, not independent** (CR): the retire can *trigger* the merge inside the same run. That coupling is the mechanism of the fork chain in §7, and listing them as three separate surfaces is what let the chain go unnoticed.

**Composition** (CR): the unbounded part is rows **self-created, or written by a concurrent writer during this load.**

**Strong form** (CR): the bound holds because the guard and the delete consume the **identical set object** — no drift surface between check and action, a stronger artifact than two computations agreeing.

### 3c. Required wording at the constant

The forward-obligation note at `MAX_ROSTER_DEPARTURES` must state a **rate**. Executed:

```
starting from a 26-row roster, progressively degrading crawl, 5 invocations
  cap=2   per-invocation [2,2,2,2,2]   cumulative 10   survivors 16
  cap=5   per-invocation [5,5,5,5,5]   cumulative 25   survivors 1
```

Adopted verbatim (DE):

> This constant sets the **per-invocation rate** of pre-existing roster loss, not a total. Cumulative exposure is unbounded in the number of invocations against a progressively degrading crawl.

---

## 4. CR's counterexample, resolved by composition

Two independent constructions agree (SE arithmetic tier, DE loader tier). CR's own `absent ∩ previously = 1` forces `previously = 2` — Reading A. Reading B (churn already stored) shows no divergence, and a re-deriver lands on B first.

The 13 rows are **12 self-undo + 1 pre-existing** — **provided the pre-existing row is ordinary. If it is a fork member it is not self-undoing in any sense** (see §7).

The *"12 self-undo"* figure survived CR's attack: churn rows are re-created by the jersey backfill from boxscores, which does not depend on the roster crawl, so they return even under sustained truncation.

**Composition statement, with CR's limit applied**: the pre-existing loss is **permanent-while-broken, not self-healing.** Re-derivability is conditional on a subsequent healthy crawl, and sustained truncation has none — the mechanism that would restore the row is the thing that is broken. Today's alternative is also permanent, in the other direction. Both are wrong rosters; the operator's ruling picks which wrongness.

**Why re-derivability holds, and its limit** (CR's caveat 4, with the §1 carve-out applied):

> `team_rosters` **rows** are fully re-derivable from the roster crawl plus the jersey backfill. **That** is why prefer-delete is defensible on this grain and would not be on player-line, where a deleted stat row is gone and there is no cap either. **But the row is what is re-derivable — the delete's downstream effect on the identity graph is not** (see §7): restoring the roster row does not un-merge an identity or restore a merged-away stat row.

That carve-out exists because the unqualified sentence **committed the exact defect §1 identifies, one section apart**: scope-accurate about rows, doing duty about deletes.

---

## 5. Required inputs — five

DE's truncated crawl · CR-2's churn sequence · CR's truncation-plus-churn · SE's 13-row-plus-14-churn · **sustained truncation without recovery.**

**Why the fifth exists**: it discriminates V1 from every floor-bearing design, and **both rejected designs passed the first four precisely because all four recover.** Without that sentence a future reader adds a sixth input without understanding why four were not enough.

---

## 6. The caveat-(2) reconciliation — is a cap-only guard acceptable?

**The objection**: E-276 story 03 justifies its own scope with *"a guard whose only protection is a second, independently-owned policy constant is not a guard"* — and V1 ships a roster grain whose only protection is exactly that.

**CR's reconciliation** (quoted; the bracketed repair is editorial and is explained below, with the original preserved in §12):

> A cap is not sufficient *as a substitute for a correct gate*, but it is an adequate **[per-invocation rate-limit on]** pre-existing loss when the failure it **[rate-limits]** is re-derivable. The E-267 objection was to a gate that appeared to protect and did not, with a second guard hiding the fact — a concealed defect, not an insufficient one. Removing the gate cures the concealment; the cap that remains is doing visible, **[rate-limited]**, stated work.

**Editorial repair, applied (CR-2's conditional MUST, confirmed).** The shipped text said *"an adequate **bound** on pre-existing loss when the failure it **bounds** is re-derivable"* and *"visible, **bounded**, stated work"* — using "bound" three times, **two sections after §3c warns that this is the last place "bounded" could be read as a bound on damage rather than on speed.** §3 establishes the quantity is a per-invocation rate, unbounded in N. The repair is confined to that word-class; no other wording changed.

**Required qualifications (CR-2's second conditional, also confirmed).** The shipped §6 said *"when the failure it bounds is re-derivable"* **unqualified**, while the qualification lived only in §4 — over-claiming precisely where the ruling turned, and repeating §4's own scope defect one section later. Both must be stated here, not by reference:

1. **Re-derivability is conditional and partial.** It holds for the ordinary roster row under a subsequent healthy crawl. It does **not** hold under sustained truncation (no healthy crawl to do the restoring), and it does **not** reach the delete's downstream effect on the identity graph (§7).
2. **The deciding case is which-wrongness, not re-derivability.** The ruling turned on §1's comparison — both designs permanently wrong in opposite directions under sustained truncation, and the operator's prefer-delete ruling selecting which. A reconciliation resting on re-derivability alone rests on the leg that is false in exactly the case that decided it.

**What does not dissolve — the residue is accepted, not discharged.** DE's own auditing rule, from `.claude/agent-memory/data-engineer/health_gate_prior_set_must_be_temporal.md`, is *"evaluate each guard against inputs where the OTHER guards permit."* Applied to V1: the only guards for pre-existing rows are `fetch_ok` and the cap, so evaluate the cap where `fetch_ok` permits — the progressively-degrading crawl, 13 rows to 1 (§3a). **DE's own rule, applied to the shipped design, regenerates the rate residual.** That does not falsify the reconciliation; the epic accepts that residual. But the reconciliation cannot claim the objection is fully discharged.

> **Discharged as to concealment. Accepted as to the residue.** Both halves ship.

**Corroboration that the reconciliation is not a rewrite** (CR-2): the "concealment, not insufficiency" reading was attacked as reverse-engineered and found **independently corroborated in DE's memory file above**, which states the rationale as concealment — authored before and outside the reconciliation.

**Three further grounds** (SE, added when CR recused itself from reviewing its own text; adversarially read and not broken by CR-2):

- **Grammar.** *"A guard whose only protection is a second, independently-owned policy constant is not a guard."* The subject is *a guard*, and *whose only protection* attributes the protection **to that guard**. Literally: a thing calling itself a guard while supplying no protection of its own is not a guard. The criticism lands on **the gate** (decorative), not the **arrangement** (cap-only too weak).
- **The paragraph's clinching argument** is the *template* argument — one of three grains left reading post-upsert is a broken template for `IDEA-154`. Concealment-family; nothing in it says the cap is too weak.
- **Decisive: the sufficiency reading was present in STORY 03 and was struck there.** Story 03's parenthetical records that an earlier version *of that paragraph* called the cap *"tunable"* and argued someone would eventually change it — precisely the sufficiency reading — pre-registered as a falsifier, falsified, and *deleted rather than softened*. Reading story 03's survivor that way resurrects an argument story 03 retired.

  > **Scoped deliberately, after a discrepancy.** *"Deleted rather than softened"* is **story 03's own phrase about its own paragraph**, and an earlier version of this bullet quoted it unscoped — which reads as a claim about the corpus. It is not one. **The word survives verbatim in `.claude/agent-memory/data-engineer/health_gate_prior_set_must_be_temporal.md`**: *"a guard whose only protection is a second, **tunable** guard is not a guard."* That is the **ancestor of the disputed sentence**, and DE's memory legitimately keeps its own wording — nobody edits it over this.
  >
  > **The discrepancy does not weaken the Decisive ground; it sharpens it.** Story 03 now reads *"a second, **independently-owned policy constant**"* where the ancestor read *"a second, **tunable** guard."* The two artifacts differ **in exactly the direction under dispute**, which is affirmative evidence the rewording was deliberate rather than incidental — the sufficiency-flavoured adjective was replaced, not dropped by accident.
  >
  > **One honest cost, recorded because it cuts against the reading I hold.** The corroboration cited above — DE's memory stating the rationale as *concealment* — sits in the file whose own closing adjective leans *sufficiency*. The file's substance is concealment-framed (*"masked its broken ratio gate rather than protecting it"*, *"a cap is not evidence the gate under it works"*); only that final word leans the other way. So the corroboration is **weaker than an unqualified citation of it implies**, and should be cited with this caveat attached.

**A standing forward obligation, written AT the constant** where a future tuner will read it — not only in the epic. The originally-shipped form of this paragraph read *"'No cap moves in this epic' becomes a standing forward obligation"*; it was rewritten by SE and the original is preserved in §12.

Under V1 the floor is gone on this grain, so **the cap is the sole roster guard across the entire churn range**: *"the cap is locked"* is no longer a supporting observation but a load-bearing design premise. **This remains a documentation ask rather than a blocker — but not for the reason SE originally gave.**

**The reason that does NOT carry it (SE's, retracted).** SE graded it non-blocking on the pin test `test_roster_departures_at_cap_are_removed` plus the absence of any `max_departures` override, arguing the cap "cannot move silently." CR-2 attacked this and it fails on both legs:

- **The pin does not prevent, it only makes deliberate.** Three tests fire at cap 5, but **every one fails for the reason "the cap moved" — the tuner's own intent.** No test at any cap encodes the *consequence*. A tuner raises the cap, sees three expected failures, updates them, and ships `5N` with a green suite.
- **The zero-override fact is a coincidence, and the parameter is dead.** All three `max_departures` hits are inside `roster_departure_guard` itself. Worse, story 03's own footgun note — the default binds at *definition* time, so monkeypatching the constant does nothing — makes this override **the only supported way to vary the cap in a test.** So "nobody overrides it" is a property that the first cap-sensitivity test deletes.

**The reason that does carry it (CR-2's).** **The residual was priced and taken.** The operator ruled V1 knowing the trade, and §3a records the rate residual as *accepted, not closed*, because the cap cannot distinguish genuine two-a-week departures from slow degradation — byte-identical at every step, and no gate could separate them on the evidence a crawl carries. That is an accepted-residual argument, and it is sound.

**The interaction, and why it is worse than a tension** (CR-2). SE predicted that the pin mitigation and the §3a residue "point in opposite directions." They do not — **they share no axis**:

- the pin guards the cap's **value against change**;
- the residual is a failure **at the current value, requiring no change at all** — 13 rows to 1 at cap 2.

They cannot contradict each other because they never touch. **That is precisely why the pin read as a mitigation**: it is true, verifiable, and about the same constant — just about a different property of it. **Orthogonality is worse than tension, because tension is visible.** *"The cap is pinned by a test"* reads as *"the cap is under control"* — true on the axis where nothing fails, and silent on the axis where something does. The finding is not a contradiction to resolve; it is that **the mitigation could never have fired on the residue.**

**Record this as a FALSE MITIGATION, not as "resolved — orthogonal"** (team-lead's ruling; originally recorded here as binding on TN-10, **now carried at TN-19** — TN-10 is occupied by the corrected-invariant wording that stories 01 and 05 bind verbatim, and the epic records the renumbering explicitly). The *tension* is closed; the *finding* is not. A reader taking §3's pin and §3a's residue together receives reassurance the design does not provide, and "resolved, orthogonal" is exactly the phrasing that would let that reassurance ship. **The comfort §3 offers reads as covering §3a and structurally cannot.**

**Test obligation (not documentation)**: the erosion construction — 26-row roster, cap 5, five invocations, 1 survivor (§3c) — **must be ported into `tests/`**. It is absent from TN-16's port list only because it was found after that list was written, and TN-16's own rule applies to it verbatim.

**CR's unifying observation**: the cap permits iff `|S − F| ≤ 2`, forcing `|F| ≥ |S| − 2`; fed into any floor `|F| ≥ 0.5·|S|` this gives `|S| ≥ 4 ⟹ the floor cannot narrow`. The exception is churn: with a live-population denominator the floor can refuse at any roster size once churn is heavy. **The divergence is unbounded in churn rows and ≤2 in pre-existing rows** — the design question in one line.

---

## 7. The fork chain — pre-existing AND widened

### 7a. The chain

> **A delete in the roster grain silently converts a REFUSED fork into an EXECUTED merge — and V1 makes that bypass reachable at ordinary roster sizes.**

`plan_player_dedup` refuses a component whose stub prefix-matches ≥2 distinct fuller names ("refuse, don't guess"), because prefix matching cannot tell one human from two. Retiring one maximal member **destroys the ambiguity that caused the refusal**, so the planner then sees an unambiguous pair and merges — same run, no signal.

**Fork-refusal reason** (DE, verbatim): a fork is two candidate humans behind one stub; merging re-points `player_game_*` rows from one human onto another — **stat misattribution no crawl recovers, because the source rows are gone. A duplicate roster row is a display artifact; a wrong merge is corrupted history.**

Executed:

```
STEP 1  intact fork, dedup runs        batting=[janet:3, john:4, jstub:2]  roster=[janet, john, jstub]
STEP 2  retire deletes Janet           batting unchanged                   roster=[john, jstub]
STEP 3  SAME RUN, dedup sweep          batting=[janet:3, john:4]           roster=[john]
STEP 4  next healthy crawl restores    batting=[janet:3, john:4]           roster=[janet, john]
```

Step 4 restores the roster row and does **not** un-merge the identity or restore the stub's stat row. This is the execution behind §1's wording constraint.

### 7b. Disposition — both halves are fact

- **Pre-existing in the ≤3-row region.** DE ran the same experiment under today's code and it fires identically.
- **Widened by V1 into the churn region.** CR found the case; SE verified it.

```
roster |S|=13 including the fork trio; crawl drops Janet only (1 genuine absence)
   churn   today permits   V1 permits    fork unlocked ONLY under V1
       0            True         True
      11            True         True
      12           False         True    YES
      14           False         True    YES
      20           False         True    YES
threshold: today refuses when 2*|fresh| < |S| + c   =>   c > 11
```

**Ruled: not a blocker, per régime** (team-lead, §10). Ship both halves as fact, neither by elimination. Filed as an idea alongside the IDEA-186 lock, because **the churn-inflated denominator is the only place today's floor is stricter than V1** — so it is simultaneously the only place removal can widen anything and a place today is already broken. Filing them apart would hide that they are one mechanism.

### 7c. Three régimes — the trade is NOT uniform

The widening region splits, and only the lock régime is covered by the operator's prefer-delete ruling. Executed across roster sizes; **the band is exactly `{R−1, R}` at every size tested**:

```
 R    c   healthy-run   departure-run   regime
  9    7   permit        permit          today permits both
  9    8   permit        REFUSE          BAND
  9    9   permit        REFUSE          BAND
  9   10   REFUSE        REFUSE          LOCK (IDEA-186)
 11   10   permit        REFUSE          BAND
 11   11   permit        REFUSE          BAND
 11   12   REFUSE        REFUSE          LOCK
 13   12   permit        REFUSE          BAND
 13   13   permit        REFUSE          BAND
 13   14   REFUSE        REFUSE          LOCK
 15   14   permit        REFUSE          BAND
 15   15   permit        REFUSE          BAND
 15   16   REFUSE        REFUSE          LOCK
```

Two thresholds, not one: a healthy run compares `R` against `0.5(R+c)`, a departure run compares `R−1`. So `c > R` locks; `c > R−2` refuses departures only.

**LOCK régime (`c > R`) — the ruled trade.** Today refuses everything, including churn retirement, so phantom backfill rows accumulate and stay. Executed, 13-row roster, 14 churn, same crawl four times:

```
=== today ===                                            === V1 ===
run2  refused_by=FLOOR  n_after=27  departed=True         run2  n_after=12  departed=False
run3  refused_by=FLOOR  n_after=27  departed=True         run3  n_after=12  departed=False
run4  refused_by=FLOOR  n_after=27  departed=True         run4  n_after=12  departed=False
run5  refused_by=FLOOR  n_after=27  departed=True         run5  n_after=12  departed=False
-> 27 stored against a 12-player truth, permanently      -> converges on run 2 and holds
```

Today = fork intact + roster permanently stranded at **2.25× truth**. V1 = fork broken + roster converges. Both wrong; same trade as sustained truncation, already ruled in the prefer-deleting direction.

**BAND régime (`R−2 < c ≤ R`) — NOT the ruled trade.** Today is *healthy*: it clears all churn on a healthy run and refuses only the departure. Executed at `R=13, c=12`, fork trio `J Smith` / `John Smith` / `Jack Smith`, departure drops Jack:

```
collision branch (stub and canonical batted in the SAME game)
  today : refused_by=FLOOR   fork refused, all 3 unmerged   STAT ROWS LOST: none
  V1    : retire permitted   merge s1 -> f1                 STAT ROWS LOST: [('s1','game-0001')]

distinct-games branch (the more dangerous one)
  today : lost: []                    every row intact and correctly attributed
  V1    : lost: [('s1','game-0002')]  gained: [('f1','game-0002')]
          john rows after: [('f1','game-0001'), ('f1','game-0002')]
```

In the band the trade is **grid clutter versus a corrupted stat**. The distinct-games branch is the worse one, and the reason is not severity but **detectability**: **no row count changes and nothing looks wrong** — John's season line silently absorbs a game that may have been Jack's, on exactly the guess the fork refusal exists to prevent (`collapsed component into f1`, chosen with no evidence).

**State this to the operator as INVISIBLE, not as "a corrupted stat"** (team-lead's ruling). A loss is detectable — a missing player, a total that dropped, a line that vanished. A silent reassignment is not: **no row count changes, the report renders, the totals still reconcile, and team-level sums are unaffected** — so on the signals we actually have, nothing looks wrong, and the only way to know is to already know. **This project's premise is that a coach reads the report as fact**, so an error that clears the checks we run is categorically worse than a larger error that announces itself. The collision branch destroys a row and can in principle be noticed; this one is not visible to any check enumerated here.

> **Bounded deliberately, and the earlier form is worth recording as a defect.** This previously read *"every downstream check passes"* and *"survives every available check"* — **unbounded universals over a set nobody has closed.** CR-2 attacked the claim and could not break it: its sharpest candidate falsifier was `bb report reconcile-scoreboard`, and a silent reassignment moves plays-derived and boxscore-derived attribution *together*, so no delta surfaces and the scoreboard does not fire. **That supports the claim and does not close the set** — a failed counterexample attempt is not an enumeration. The claim is therefore scoped to the signals actually listed.
>
> Note where the defect sat: **the closing generalization of a safety note about invisibility.** That is the exact position `.claude/rules/tool-output-integrity.md` names as where this concentrates — the sentence that sounds most authoritative and gets checked least — and the alarming direction is self-protecting, so "worse than you think" reads as appropriate caution rather than as an unverified universal. It is also the same species as §11's other entries: **a claim quantified over a region I did not sample**, here the set of downstream checks rather than a churn range.

**Why this matters beyond the numbers**: the roster grain's separation from the other two rests on one sentence in its own docstring — *"the failure mode is grid clutter, **never a corrupted stat**."* **In the band, V1 crosses that line**, and the prefer-delete ruling does not reach it, because that ruling premises roster failures being recoverable grid-level issues. Band occupancy is unmeasured.

### 7d. The residue, by branch — three cases, not one

`merge_player_pair` is delete-or-update: colliding rows are **deleted**, non-colliding are **re-pointed**.

- **Fork REFUSED** — split per-player line; **team sums correct**; one human's season understated.
- **Fork BROKEN, colliding game** — stat rows destroyed; **team sums wrong, low**.
- **Fork BROKEN, distinct games** — canonical line inflated; team sums correct; the other human's season vanishes.

*"Team sums correct either way"* is true **only** of the refused-fork residue.

---

## 8. Multi-run results

**Game grain: CLEAN.** Byte-identical across both shapes — newly-completed games raise numerator and denominator together, so the strand cannot outgrow the recurring set. A checked clearance with its mechanism.

**Player-line: DIVERGES; not reopened.** One-time churn self-corrects; the dedup sweep closes the window in both dominant shapes (identical names; initials-vs-full). Recurring churn accumulates — idea plus grain note. The fork stays open, bounded, self-limiting.

---

## 9. Other required items

- **Committed test**: `test_roster_grain_reconcile.py` — the 13-genuine-absence case keeps its outcome under V1 (the cap refuses) but its `"floor_ratio"` reason assertion fails. **Specify the edit as an expected change, not a regression.**
- **`W ⊆ fresh` is a NAMED PREMISE** for neutrality on game and player-line, not a structural guarantee. Stated as what it is: could not be falsified (one `INSERT INTO games` path; 179 runtime invocations across the full suite), which is not proof.
- **The `MAX_GAME_RETIREMENTS` comment** claiming the `MAX_ROSTER_DEPARTURES` precedent (*"a refused retire … self-heals … a wrong delete is irreversible"*) is the **fourth pre-existing false claim**: true for game, backwards for roster, both directions executed and independently confirmed. **It is the sentence that made bias-to-refuse feel safe on roster**, which is why the analogy went unchallenged by all four reviewers. **Story 05: scope it to the game grain, do not delete it.**
  - CR's separate roster-docstring citation was retracted — a fusion of its own inference with a genuine quotation. **That retraction withdraws CR's fabricated clause, not this correction.** A future reader who finds the retraction in the record must not conclude the fix was withdrawn with it. The roster docstring is clean; the `MAX_GAME_RETIREMENTS` comment is not.
- **Precondition (e) is MOOT under V1** — keep as CONDITIONAL in the TN-15 shape. Verified independently three ways: `exempt_player_ids` is **roster-only**, and the roster prior read is the **only** filtered read; the two grains with a snapshot gate have no filter. The cap is invariant **structurally**: `absent` derives from an already-exempt-filtered `prior_ids`, so `absent ∩ exempt = ∅` by construction. Two triggers wake it: (i) the roster grain regains a snapshot-population gate, (ii) any grain adds a filter to its prior read.
  - **Polarity taxonomy, so the inversion cannot re-enter**: fail-closed (stricter, spurious refusals) = an **availability** concern; fail-open (permits where it should refuse) = the **safety** concern.
  - The direction of the (e) divergence is **data-dependent** — the unfiltered snapshot is looser iff `2k > E`, and the canonical load-bearing component sits exactly on that boundary. **The fix is congruence, not a direction**: filter both or filter neither, and say which.
- **Fixture trap for the implementer**: two games for one team **on the same date** collapse into one `games` row via E-261's cross-perspective natural key (`season_id` + date + unordered team pair). A test needing two distinct games for one team **must vary the date**. This silently invalidated a fixture during §7c's branch-2 work and produced clean-looking output with a wrong conclusion; the tell was a player holding zero batting rows after a run in which he batted.

---

## 10. Ruling record

**Team-lead, on the fork chain's disposition (§7b):**

> **Characterisation**: pre-existing in the ≤3-row region **and** widened into the churn region. Both halves as fact, neither by elimination.
>
> **Disposition**: **not a blocker**, on the executed trade — today's alternative is not fork-preservation, it is permanent non-convergence at 2.25× the true roster.
>
> **Qualification**: ruled not-a-blocker **per régime**, with the band stated as the one place the ruling's premise does not reach, and its occupancy unmeasured. Do not let the lock-régime sentence be generalised across the widening region.

---

## 11. Change log and retraction chain

The reasoning here is worth more than the conclusions, and most of it is a record of claims that were wrong in a specific, repeating way.

**Applied from eleven addenda**: caveat (4) and the line-148 retraction framing (a1); symbol anchors replacing line citations, with the nested-def trap (a2); rate-not-total and protection-inversion (a3); team-lead's replacement §1 and the withdrawal of SE's "fail-open" claim (a4); rate wording at the constant (a5); CR's §1 MUST confirmed by execution and the three-case residue (a6); the chain shown pre-existing (a7); (e) mootness, polarity taxonomy, §1 MUST still open (a8); retraction of the no-widening claim and the §4 carve-out (a9); DE's three artifact changes and the strand execution (a10); CR's band and the per-régime correction (a11).

**Retractions, each by a non-author of the retracted claim:**

| Claim | By | Falsified by | What was actually wrong |
|---|---|---|---|
| *"V1's cost under persistent truncation: none"* | team-lead | its own author | Too clean — holds only if the truncation reflects reality |
| *"(e) is fail-open in the deletion-permitting direction"* | SE | CR | Right arithmetic, wrong model — `E = k` is the **inert** case; boundary is exactly `2k > E` |
| *"V1 does not widen the fork chain — structurally unreachable"* | SE | CR | Exhaustive sweep that **fixed churn at zero** |
| *"the same trade already ruled on"* (whole widening region) | SE | CR | Measured `c=14, R=13` — the first row of the **lock** régime — and generalised across a region containing the band |
| *"team sums correct either way"* | SE/DE | CR | True only of the **refused**-fork residue |
| *"an adequate **bound** on pre-existing loss"* | CR | CR-2 | The quantity is a per-invocation **rate**, unbounded in N (§6, §12) |
| *"the cap is pinned, so it cannot move silently"* (as the reason §3 is non-blocking) | SE | CR-2 | **Verdict survived, reason did not.** The pin makes a change deliberate, not prevented — every test that fires at cap 5 fails for the tuner's own intent, and none encodes the consequence. The zero-override fact was coincidence on a **dead** parameter that the first cap-sensitivity test would delete |

**The species — and CR-2's split of it.** Every one was a correct computation attached to the wrong region: not one arithmetic error among them, across a full day on a gate whose entire defect was a population claim. **The epic's subject reproduced itself in the process of being investigated, in every participant.** But the family has **two** members, and conflating them hides why the second survives more reviewers:

- **Correct-verdict-on-an-unsupporting-premise** — the conclusion is right, the stated reason does not establish it. Detection question: *does this evidence actually support this claim?* (Rows 1–5 above, plus team-lead's `epic.md` retraction below.)
- **Correct-fact-on-the-wrong-axis** — the fact is true and verifiable, and it is about a *different property* of the same object than the one at risk. Detection question: *what axis does this fact live on, and is it the axis where the failure is?* (Row 7 — the pin test.)

The second is the harder one, and the pin test shows why: **it survived four reviewers.** A reader checking *"is the pin real?"* gets **yes** and stops — the premise-checking question passes cleanly, because the premise is sound. Only the axis question fails, and nobody asks it, because the fact is about the right constant.

**Three rules that came out of it, in the order they were earned:**

1. **A correct narrowing that licenses stopping is more dangerous than an under-covered input set** (DE). *"An under-covered input set announces itself as incomplete — you can always ask 'did I try enough?' A correct narrowing answers that question falsely, because it tells you the space is small and you have already characterised it."* A theorem that identifies a region is not a result about what happens inside it.

2. **Confirming a negative claim must vary what the original fixed** (DE's boundary on SE's rule). Confirming a **positive** claim (*"input I produces outcome O"*) is a replication by design and sharing the parameterisation is the point. Confirming a **negative or universal** claim (*"no input exists such that X"*) with a shared fixed axis is fatal — the claim ranges over exactly the space the shared constant excludes. *Two agents, same missing axis, one "confirmed" — and the confirmation made the claim more credible than the original.*

3. **A claim quantified over a region requires sampling the region, not a point inside it** (SE's band error, which fits neither category above — *"today refuses at c=14"* is positive and true; what failed was the silent quantifier). The checkable form: **what region did I sample, and what region am I claiming?**

**Two observations worth keeping unsoftened:**

- **The qualifier is invisible from inside the case that produced it** (DE). Three findings needed a qualifier corrected in the direction of sounding safer — *"self-healing"*, *"≤2 as a total"*, *"bounded" vs "rate"*. Each was caught by a different agent, each about someone else's phrasing, **none by its author**. Each was written by whoever had just done the work that made the claim true in the case they tested, and the softer word was the one that made the result feel finished.

- **A correct computation whose case never arose** (CR). *"Four of us argued the direction of an asymmetry across three rounds, and nobody asked whether it fires at all. One grep settled it, and the grep was available throughout."* The corrective differs from the others: this one needs a **reachability check before the analysis**, not a scope check after.

- **A verdict's REASON rots independently of the verdict — and a retraction is where it hides** (team-lead, found by SE checking a retraction rather than accepting it). Team-lead asserted the `bound` defect also existed in `epic.md` and directed a repair; it then **retracted** that on a grep returning *"two hits repository-wide, none in the epic."* The retraction's verdict was **right** — there is no assertive copy, so nothing to repair — but its evidence was **wrong**: `epic.md` does contain the phrase, and the literal grep missed it because the quoted text carries **markdown emphasis inside the phrase** (`an adequate **bound** on pre-existing loss`), which breaks the literal match. An emphasis-normalized sweep finds **7 occurrences, not 2**; all seven are quotations-as-defect or preservation copies, and **zero are assertive**, which is the check that actually supports the conclusion.

  Two things to carry. **The sweep hazard**: markdown emphasis interpolated into a phrase silently defeats a literal grep, and `doc-sweep.md`'s synonym expansion does not cover it — these are not synonyms but the same words with markup inside them. **Strip `**`/`__` before any literal-phrase sweep of this repo's prose.** And **the structural point**: this is the third instance today of a correct conclusion resting on a false premise, and it occurred *inside a retraction* — the position where relief at having caught an error is what stops the reason being read. Any check asking *"was the call right?"* passes; only re-running the evidence catches it.

  Team-lead's own framing of the root cause, which is the transferable half: *"I have no channel to read files in this role, so asserting their contents is not a care failure but a structural one — route or attribute, every time."*

**Process failures of the coordination protocol itself**, recorded because they were not free: CR was asked for an adversarial read of a document it had not been sent, and refused on exactly the right grounds — in an epic whose subject is unverified claims. The same failure recurred with §4 (a section summary sent in place of verbatim text) and again, terminally, with this whole artifact, which existed on no filesystem until now. Against that: three message crossings producing duplicate drafts, and a routing failure in which **agent TYPES were used where NAMES were required** (`product-manager`, `code-reviewer`, `data-engineer` do not route; `PM2`, `CR`, `CR-2`, `DE` do), which cost a full relay cycle and produced a false "all teammates unreachable" conclusion.

---

## 12. Appendix — §6 as originally shipped (verbatim, unrepaired)

Preserved because §6 repairs a **quoted** passage, and a repair to a quotation must be auditable against its original. This is the text CR-2 was assigned to review and could not obtain.

**Scope correction (CR-2's finding).** This appendix originally carried only the reconciliation quote while its heading claimed to preserve §6 — so the *second* paragraph, which SE also changed, was unauditable. CR-2 flagged that it could not tell whether SE had rewritten it, whether PM2's relay was loose, or whether the original differed, **and that the unanswerability was itself the defect.** Settled from the transcript: **PM2's relay was accurate and SE rewrote the paragraph.** The full original section now follows, verbatim, so every change is checkable.

---

**§6 as shipped, in full:**

> ## 6. CR's caveat-(2) reconciliation — verbatim
>
> > A cap is not sufficient *as a substitute for a correct gate*, but it is an adequate bound on pre-existing loss when the failure it bounds is re-derivable. The E-267 objection was to a gate that appeared to protect and did not, with a second guard hiding the fact — a concealed defect, not an insufficient one. Removing the gate cures the concealment; the cap that remains is doing visible, bounded, stated work.
>
> **What does not dissolve**: `MAX_ROSTER_DEPARTURES` becomes the only thing between a truncated crawl and pre-existing rows. "No cap moves in this epic" becomes a **standing forward obligation**, written **at the constant** where a future tuner will read it — not only in the epic.
>
> **CR's unifying observation**: the cap permits iff `|S − F| ≤ 2`, forcing `|F| ≥ |S| − 2`; fed into any floor `|F| ≥ 0.5·|S|` this gives `|S| ≥ 4 ⟹ the floor cannot narrow`. The exception is churn: with a live-population denominator the floor can refuse at any roster size once churn is heavy. **The divergence is unbounded in churn rows and ≤2 in pre-existing rows** — the design question in one line.

---

**What changed, paragraph by paragraph:**

1. **The quote** — three uses of the "bound" word-class; no qualification of *re-derivable*; no mention of which-wrongness. Both of CR-2's conditional findings are confirmed against this text. Repaired in §6 to the rate word-class only; CR-2 verified the remainder byte-identical after stripping the substitutions, so no collateral edit was made.

   > **Timestamp bound on that verification** — a "verified on disk" claim without one decays silently. CR-2 diffed the **2026-07-25 21:24:28 UTC** state (391-byte remainders, identical), after first re-checking its own earlier 21:20:14 extracts to close the window in which this file was still being written. **Edits after 21:24:28 are additive prose in §0, §6, §7c and §11 and did not touch the §6 quote or this appendix's original** — that is an author's claim about their own edits and is the weaker link in the chain; re-verify rather than inherit it. **Byte sizes recorded anywhere in this epic are stale** and should not be used as identity checks: the file has grown repeatedly since.
2. **"What does not dissolve"** — rewritten by SE. *"No cap moves in this epic"* was replaced with the load-bearing-premise framing, and new material was added (sole-guard-across-the-churn-range, plus the pin-test mechanical basis that CR-2 has since overturned). **This is the change §12 previously failed to expose.**
3. **CR's unifying observation** — carried into §6 unchanged.
