# E-276: Reconcile-at-Load Health Gate — Capture the Prior Set Before the Run's Own Writes

## HOW TO READ THIS FILE — it is long, and most readers need a small part of it

**This file is ~2,073 lines. Nobody needs all of it, and reading it front-to-back is the wrong approach.** Its length is the residue of a design that was reopened three times plus a deliberate decision to inline everything load-bearing rather than cite an artifact that lives on no filesystem. Both were right; the combination is not free, and this section is the mitigation.

| If you are… | Read | Skip |
|---|---|---|
| **the operator, deciding dispatch** | `WHAT CHANGED FROM THE COMMISSION` (next section). That is written for you and is self-contained. | everything else |
| **an implementer** | your story file first; then only the Technical Notes it cites by number; then the banner at the top of Technical Notes | Background, History, the Codification Recommendation |
| **a reviewer** | the banner, Goals, Non-Goals, Success Criteria, the story you are reviewing, and the TNs it cites | History, unless you are checking a claim's provenance |
| **claude-architect at closure** | `Codification Recommendation`, then History | the Technical Notes |
| **anyone asking "was this reviewed, and by whom?"** | `READY SCORECARD` | everything else |
| **someone asking "why is it like this?"** | History | the rest |

**The one thing every reader must not skip**: the banner at the top of Technical Notes. It says which parts of this file are current design and which are kept as history, and reading a superseded section as spec is the single most expensive mistake available here.

**Known and deliberate**: the History carries nine-plus process mechanisms with their instances and derivations. **An implementer never needs them.** They are the epic's most transferable output and they are the first thing to extract to a research artifact — see the size note in Technical Notes.

## Status
`COMPLETED` — 2026-07-26. **All five stories DONE; every closure gate cleared.** Both grains that keep a gate now compute the floor over a pre-upsert snapshot; the roster grain's floor is removed on the operator's ruling, leaving `MAX_ROSTER_DEPARTURES` as its sole guard.

**⚠️ Authored in the WORKTREE at the implement skill's Step 8 sub-step 3, BEFORE the full-suite green gate — deliberately, and it is safe.** COMPLETED is *set on disk* now so it rides the closure patch, but it is **never COMMITTED on a red suite**: a red gate aborts the commit and reverse-applies the patch, taking this flip with it. **If you are reading this in an unmerged worktree, it is an authored intention, not a finalized status** (`.claude/rules/workflow-discipline.md`, Full-Suite-Green Closure Gate).

**Closure record**: five per-story reviews (one clean first pass), Codex — 1 finding, valid, remediated, the Step 1a invariant audit, the Step 1c integration review re-issued after CR withdrew its own premature approval, an **operator-signed ratchet exception** (baseline deliberately NOT re-snapshotted — the inherited overrun stays visible as debt), and claude-architect's codification. **~12 spec corrections landed during dispatch, every one to a claim this epic had already reviewed and passed.**

*(Prior: `ACTIVE` — dispatched 2026-07-26 on the operator's authorization, with review.)*

**Prior state, kept because the paragraphs below are written against it**: `READY`, re-affirmed 2026-07-25 on the operator's authorization after the pre-dispatch amendment and **six review passes**. The READY freshness gate measured from that date; it no longer applies, since `ACTIVE` epics are exempt (`.claude/rules/workflow-discipline.md`).

**The artifact was edited again on 2026-07-26, AFTER that re-affirmation** — the operator's red-team repairs **R2–R5**, and then, in a later round, the **R1 disposition** (History, top two entries). **No design change in either; READY was not disturbed and was not re-asserted by those edits.** Stated here because the Size section directly below assumed this file had frozen at READY and was wrong about it, and a reader who takes the date above as an as-of-last-edit marker would inherit the same mistake.

**R1 has LANDED** — it arrived as the story 01 AC-14 rewrite plus a new AC-15, both now on disk in `E-276-01-gate-primitive-and-player-line-grain.md`. *(This paragraph previously read "R1 is still outstanding"; that was true when written during the R2–R5 round and was falsified by the later R1 round without anything editing it — the 9th mechanism, in the Status block this time.)*

Gate design RESOLVED per grain; consistency, banner and claim sweeps all clean.

**The prior "amended-and-not-re-affirmed" hold is DISCHARGED.** It was in force from the pre-dispatch amendment until this line, and its purpose is served: the two acceptance criteria added to the implementer surface after the original READY (**01 AC-14**, **02 AC-11**) have since been through **four further review passes** — two Codex spec audits, an edge-walk, and an independent parallel enumeration with its re-verify. **Nothing about the design changed at any point**; every amendment added tests, disclosures, citations, or corrections to tracking artifacts.

**READY and DISPATCH were separate gates, and BOTH have now been passed** — READY on 2026-07-25, dispatch as a distinct operator decision on 2026-07-26. The separation is recorded because it was load-bearing while it lasted, not because anything is still pending.

**Read the banner at the top of Technical Notes before implementing anything about the gate shape.** It says which parts of this file are current design and which are kept as history, and reading a superseded section as spec is the single most expensive mistake available here.

**One thing an operator should carry into the dispatch decision**: this epic **removes** the roster grain's gate rather than fixing it, on the operator's own ruling to invert the bias on that grain — so that grain ships with **less** gating than it started with, and `MAX_ROSTER_DEPARTURES` becomes its sole guard. That is deliberate, and the `WHAT CHANGED FROM THE COMMISSION` section immediately below is written for exactly this decision.

## Overview

The reconcile-at-load health gate is supposed to refuse a retire when the fresh crawl no longer vouches for most of what we already had. It cannot ask that question, because it reads its "prior" id-set from the database **after** the same run's fresh rows are already written. All three grains are affected. The executed consequence is live data loss on a routine `bb report generate`: a full GameChanger `player_id` churn hard-deletes every prior batting line for the game, uncapped.

This epic restores the gate's intended population **on game and player-line**, by capturing the prior set before those grains' own writes — and **removes the roster grain's floor gate outright**, on the operator's ruling to invert the bias there. It also corrects the prose the fix falsifies, including a stated invariant that is **true of the broken code**, which is why four review layers passed over this.

**⚠️ The asymmetry is the design, not an omission, and it must not be smoothed into one sentence.** Two grains gain a correctly-populated gate; the third loses its gate and ships with **less** gating than it started with. See `WHAT CHANGED FROM THE COMMISSION` below — it is written for the operator approving dispatch.

## ⚠️ WHAT CHANGED FROM THE COMMISSION — read this before approving dispatch

**The design that will ship is not the design that was commissioned.** The defect is the same; the remedy is not, at one of three grains. Stated here rather than only in the History, because an operator approving dispatch should not have to reconstruct it from a chronology.

| | Commissioned | Shipping |
|---|---|---|
| **Diagnosis** | the health gate reads its prior set after the run's own writes | **unchanged** |
| **Grains affected** | two (the brief) | **three** — the roster grain was broken the same way, and checking it was an explicit operator instruction |
| **game** | capture the prior set pre-upsert; gate it | **as commissioned** |
| **player-line** | capture the prior set pre-upsert; gate it | **as commissioned** |
| **roster** | same fix as the other two | **THE GATE IS REMOVED ENTIRELY.** No floor ratio — neither today's nor a corrected one. Protection is `MAX_ROSTER_DEPARTURES` alone. |

**Five things the operator should weigh:**

*(**The heading read "Three" over FOUR items** before this round — the fourth was added with the IDEA-188 widening and the count was not re-read. Corrected to five with the addition of item 5 below. Same shape as the 9th mechanism in the process-findings index: **a count invalidated by an edit that never touched the sentence containing it**, here in the section written specifically for the operator's dispatch decision.)*

1. **The roster grain ends this epic with LESS gating than it started with**, and that is deliberate — the operator's own ruling to invert the bias on that grain (delete rather than refuse). The corrected gate was demonstrated, by execution through the real loader, to **permanently lock** the grain on a reachable input where today's code converges to a clean roster. Every floor-bearing alternative failed the same way.
2. **`MAX_ROSTER_DEPARTURES` becomes the sole safety control on that grain.** It is no longer a policy tweak; changing it is a safety change, and the obligation is written at the constant rather than only here. **The number does not mean what it looks like**: it sets a **per-invocation rate**, not a total — raising it from 2 to 5 does not mean "5 rows lost", it means 5 *per invocation*, and a morning-run walks several teams per process. Executed on a 26-row roster against a degrading crawl over 5 invocations: cap 2 leaves 16 survivors, cap 5 leaves **1**.
3. **The bound it provides is a RATE, not a total**, and it protects *inversely* to severity — a catastrophically broken crawl loses nothing, a gently degrading one can empty a roster two rows per run. That residual is **accepted, not closed**, because the degrading case is byte-identical to a real roster losing two players a week.
4. **The shipped design WIDENS one pre-existing data-corrupting chain — and here is what today's code does in the same region, because a widening stated without its alternative is not a trade, it is a defect.** A roster delete can collapse a refused player-dedup fork into an executed merge ([[IDEA-188]], pre-existing — today fires it too). V1 extends its reach from ≤3-row rosters to any roster carrying backfill churn above roughly its own size. **What today does there is not "the safe thing":**

   | backfill churn `c` (roster size `R`) | today's code | shipped design |
   |---|---|---|
   | `c ≤ R − 2` | permits | permits — **no widening** |
   | **band: `c ∈ {R−1, R}`** | healthy; stats untouched; **one player left on the grid** | player correctly removed; **a stat row destroyed OR silently reassigned — see below** |
   | `c > R` | **permanently locked** — roster never updates again, all future departures blocked | **converges to a correct roster** |

   **In the `c > R` régime today is the worse option and the shipped design fixes it** — that is the same lock/converge trade as sustained truncation, which you have already ruled in the prefer-delete direction, and it is the bulk of the widened region.

   **The band is the one place that reasoning does not reach, and it is the part to weigh.** The ruling rests on roster failures being recoverable grid-level problems — which is also what the grain's own code asserts: *"grid clutter, **never a corrupted stat**."* In the band the cost is a **different kind**, not a larger amount.

   **⚠️ AND ONE OF THE TWO BAND FAILURES IS INVISIBLE. This is the part that should decide how you weigh it.** Executed, both branches:

   - **Collision branch** (the two ids batted in the same game): the merge **loses a stat row**. Detectable — the row count changes.
   - **Distinct-games branch**: `lost: [('s1','game-0002')]`, `gained: [('f1','game-0002')]`. **No row count changes. Nothing looks wrong.** One player's season line silently absorbs a game that may have belonged to another — decided by a guess the fork refusal exists specifically to prevent, made with no evidence.

   > **A report reader sees a plausible stat line.**

   A loss announces itself; a silent reassignment does not — and this project's premise is that a coach reads the report as fact. **That is why this is in your summary rather than in a Technical Note.** It does not change the disposition: the band requires a conjunction of narrow conditions (churn in the band, a live fork, a departure in the same run), **it is exactly `{R−1, R}` at every roster size tested — two wide, scaling with the roster, not an artifact of one size** — and its **occupancy is unmeasured**. It is filed as [[IDEA-188]] rather than treated as a blocker. But you are approving on the strength of what the failure *looks like*, and "invisible" is the part that decides how that weighs.

5. **⛔ THE EPIC'S HEADLINE FIX IS TRUE FOR ONE RUN ONLY, AND THIS IS THE ITEM MOST LIKELY TO BE READ AS SOLVED.** *(Added at the R1 disposition, 2026-07-26. Placed in your summary rather than a Technical Note because the Overview's promise — "a full `player_id` churn hard-deletes every prior batting line; the fix refuses instead" — is accurate about **run 1** and stops being accurate at **run 3**.)*

   **The mechanism, and it is the corrected gate working as designed rather than a new defect: a refusal still WRITES.** The fresh rows land; only the retire is refused. So each refused run adds its generation to the stored population while the gate's prior set grows to match. By the third re-scout the gate permits at the floor and **hard-deletes the prior generation, uncapped** — this grain has no `MAX_*` beneath it. **`W ⊆ fresh` does not rescue this**: it constrains the *candidate* set, not the *gate population*, and it is the population that grows. Both agents reached that independently; it is the crux of the finding.

   **The only closer is the end-of-run `dedup_team_players` sweep, and it has three holes:**
   - it is scoped to the **scouted team**, so the **opponent block has no closer in any shape**;
   - it matches on **name prefix**, so `Mike`→`Michael` is invisible to it;
   - its **fork-refusal** class recurs and is silent through `LoadResult.errors` ([[IDEA-189]]).

   **Three mechanisms were evaluated BY CONSTRUCTION — an `extra_guard`, a cap, and a churn-signature gate — and NONE was adopted.** Not for cost: **every mechanism that closes the window closes it by refusing forever, and a permanent refusal on this grain DOUBLES the coach-facing season aggregate** — measured against the shipped `get_season_batting` at 27→54 AB and 36→72 AB *[executed independently by SE-R1 and DE-R1; reached twice from different fixtures]*. **A coach reading a doubled season line is a worse outcome than the deletion**, and this project's premise is that the report is read as fact.

   **So the disposition is: residual ACCEPTED and SURFACED, not closed.** What ships instead is a **diagnostic** (story 01 AC-15) that names the condition and points at `bb data dedup-players`, plus regression tests pinning both regimes so a later change cannot worsen it silently. **Nothing refuses a retire that today permits one** — deletion behaviour is unchanged by construction, which is why AC-8's deletion-neutrality is untouched. The real closer is **merge-not-delete**, already routed out as [[IDEA-185]].

   **What this means for your decision**: the epic still removes the defect it was commissioned for — the gate now asks the right question, on the right population, at every grain. It does **not** make a sustained id-churn scenario safe, and **no version of it that we could construct does so without corrupting the report**. If you want that window closed, it is [[IDEA-185]]'s scope and a different epic.

**Scope that did NOT change**: no cap values move, no schema change, no migration, no crawl, no network, `data/app.db` untouched. **R1 added no gate, no cap, and no `extra_guard`** — one diagnostic WARN, one record field, and tests.

**FIVE residuals were routed out rather than absorbed** — *(corrected 2026-07-25; this read "two … and a third" and under-enumerated by two, in the section an operator reads to see what was deferred)*:

| Idea | Routed out on | What it holds |
|---|---|---|
| [[IDEA-185]] | substance | partial id churn still retires, after the gate is honest |
| [[IDEA-186]] | substance | the permanent roster-retire lock after a truncated crawl |
| [[IDEA-187]] | **ownership** — DE's own memory file, and DE is not on the Dispatch Team | now deflated twice; residual is one cross-reference |
| [[IDEA-188]] | substance | a roster delete converting a REFUSED dedup fork into an EXECUTED merge — **pre-existing and WIDENED by V1** |
| **[[IDEA-189]]** | substance | **a failing dedup collapse is invisible through `LoadResult.errors`** |

**⚠️ [[IDEA-189]] was linked from NOWHERE in this epic until 2026-07-25, and it is the one that qualifies a live premise.** TN-5's three-bucket lock disposition rests in part on a merge failure being **recurring and visible**; IDEA-189 establishes it is recurring but **not visible through the channel this codebase treats as authoritative** (`dedup_team_players` swallows without incrementing `result.errors`). **The bucket-(c) ruling STANDS — IDEA-189 says so itself, "sharpens rather than changes"** — but its supporting assumption is narrower than stated, and a reader had no route to that. **This is a pointer, not a re-opening**; nothing about the disposition moves.

## Background & Context

### The defect

`src/db/reconcile_at_load.py` computes its health gate as `comparable = prior_ids & fresh`, requiring `|comparable| >= FLOOR_RATIO * |prior_ids|`. The intent is "does the fresh payload still vouch for at least half of what we loaded previously?"

But `prior_ids` is read at retire time, downstream of the upsert, so it is `old ∪ new_this_run`. Every row the run just wrote lands in **both** sides of the ratio. SE's general form of the executed gate:

```
|old ∩ fresh| + |new| >= 0.5 * (|old| + |new|)
```

— every row written this run relaxes the floor by half a row. In the zero-overlap churn case this reduces to `|fresh| >= |stale|`: with `S` stale and `N` brand-new, `N >= 0.5(S+N)` → `N >= S`. That is a comparison between the fresh payload and the stale remainder, not a health signal. A payload arbitrarily unlike what we stored clears it simply by being large enough.

Stating the general form (not just the `|fresh| >= |stale|` reduction) is what makes the game-grain case legible: **newly-completed games are not a special case, they are the general mechanism.**

### What was executed, by whom

The finding is not inherited from the handoff. It was derived independently by PM from the code, then confirmed by execution twice:

- **Player-line grain (SE, and the 2026-07-25 audit):** 9 stored lines against 9 brand-new payload ids → **all 9 hard-deleted, 0 refusals**. Same inputs with a pre-upsert prior → refused, 9 of 9 survive. Boundary sweep: stale 9 / fresh 8 refuses; 9/9 deletes 9; 9/10 deletes 9.
- **Roster grain (DE):** run 1 roster `{r-a, r-b, r-c}`, run 2 `{r-a, r-x}` → **`r-b` and `r-c` hard-deleted** through the real `ScoutingLoader` ordering. The WARN reports `roster_db_count=4` on a roster that only ever held three rows; the fourth is `r-x`, written by that run's own upsert. That count is the tell.
- **Game grain:** stale absences alone refuse; add newly-completed games in the same run and the same absences retire, bounded at 2 only by `MAX_GAME_RETIREMENTS`.

### The framing that narrows this epic

**The candidate/absent set is already correct.** `live_prior - fresh` equals `old - fresh`, because every row written this run is by construction in `fresh`. Only the gate's numerator and denominator are wrong.

This is a **gate-population fix, not a delete-targeting fix.** Recorded here so nobody widens it.

### Why the existing 72 reconcile tests miss it

Every existing shrink test uses a fresh set that is a strict **subset** of prior (`test_shrink_at_the_floor_still_retires`, `test_catastrophic_shrink_of_the_player_set_retires_nothing`, and the game-grain equivalents). When `fresh ⊆ prior`, post-upsert prior equals pre-upsert prior and the pollution is invisible. **The churn shape — fresh ids that are NOT in prior — is untested at every grain.**

SE quantified this rather than asserting it: two read-only pytest plugins recomputed the gate both ways at every reconcile call across the three reconcile test files plus `tests/test_report_generator.py` — **295 player-line calls and 153 game-grain calls, 0 divergences, 240 passed.** No existing assertion flips under the fix.

### The defect class has TWO instances of the epic's own mechanism, and a third that belongs to a class the codebase already names

The original framing here counted three instances and called that a pattern. **Instance 2 has been reclassified out**, because a rule already covers it and inventing a second name for a class we have written down is how the context layer grows without gaining anything. What is left is two instances plus one prior case — weaker than "three, therefore a pattern", and stated at that strength deliberately.

**The two instances of this epic's own mechanism:**

1. **The invariant.** "Numerator and denominator drawn from the same population" was **true-as-written and false-in-effect** — both sides were drawn from the polluted set. Four review layers read it and moved on.
2. **The inherited acceptance criterion.** The originating handoff specified a 9-stored / 9-brand-new regression fixture. That shape discriminates at the player-line grain and **does not** at the roster grain, where the departure cap refuses regardless. Adopting it there would have shipped **a regression test that cannot fail**, inside the epic written to fix a defect that survived because nothing could catch it.

The mechanism, stated **with the scope it survived testing at**: **a claim that is locally true propagates unverified, because its truth-condition lives in a different artefact than the claim.** The invariant is true of its own code; the fixture is true at the grain it was written for. Each is falsified only by looking somewhere else.

**The reclassified one — `crawl_is_authoritative`'s docstring — is a STALE CONTRACT, and `.claude/rules/python-style.md` already carries that class.** The docstring documents its fresh count as "size of the fresh payload" while all three callers have passed the *overlap* since E-267. **Pre-existing, not caused by this epic** — found while fixing it. [PM-VERIFIED] The rule's missing-safety-signal entry already names both the shape and the sweep it requires: *"when a contract changes, sweep the IDENTIFIER across the module graph, not the phrasing of the claim."* A parameter whose documented contract diverged from what every caller feeds it is precisely that, and the prescribed action — sweep `fresh_count` across its callers — is what found it.

**Why the distinction is worth making rather than letting three instances stand.** Story 05 hands this epic's generalization to claude-architect for codification. Handing over a three-instance pattern that silently includes a case an existing rule already covers invites a *second* rule for the same class — the context layer paying twice and a future reader having to work out which one applies. The honest handover is: two instances of a mechanism we do not yet have a rule for, and one case that should be routed to the rule we do.

**It also cost this epic an argument.** Instance 2 was the one that forced "artefact" to mean the *claim unit* rather than the file (Attack 2 below), because the docstring and its three callers sit a few functions apart. That weakening still stands — the fixture instance reaches the same conclusion on its own — but it was established on the case now leaving, and a reader should know that.

#### The bound, established by attacking the claim rather than re-reading it

This generalization was flagged by PM as its own most suspect contribution and then tested two ways. **It did not survive unbounded**, and the bound is stated here rather than left for a reviewer to impose:

**Attack 1 — find a session failure that does NOT fit.** Two classes do not:

- **Plainly-false claims nobody checked at all.** The relay layer's stale-symbol claim was not locally true; it was simply wrong, and a single grep settled it. That is a *simpler* failure — no verification attempted — not verification that would have required travel. Folding it in would flatter the mechanism.
- **A claim whose stated SUPPORT is wrong while the claim is right.** The misattributed convergence evidence (History) inverts the shape: the claim was true and its citation false, so checking the citation would have discarded a sound conclusion. The mechanism describes claims that survive checking; this one would have *failed* checking and been right anyway.
- **Claims that were true when written and went stale.** SE's "the only surviving hole" was accurate until DE's contest arrived; DE's own simulation-tier flag was accurate until DE re-ran it through the loader. Those failed along a **time** axis, not a **location** axis. The mechanism does not explain them, and a separate finding in this History names that fifth host (the summary of a claim) precisely because it is a different shape.

**Attack 2 — check the converse: was any instance falsifiable from inside its own artefact?** One was: `crawl_is_authoritative`'s docstring and all three of its callers sit in the **same file**, a few functions apart. So "artefact" cannot mean *file*. It means the **claim unit** — the docstring, the invariant sentence, the acceptance criterion — and the falsifier can sit close by and still be outside it. That is a real weakening of the sharper reading, and it is why the sentence says *artefact* rather than *module*. **The weakening survives its source's reclassification** — the acceptance-criterion instance forces the same reading, since a fixture and the grain that falsifies it are equally "close by" in an epic directory.

**What survives**: the mechanism covers claims that are locally true and falsifiable only outside their own claim unit. It does **not** cover unchecked-but-plainly-false claims, and it does **not** cover claims that decayed with time. Two of this session's failures fit it, one belongs to the stale-contract class already ruled on, and several fit neither.

That bounded form is still the useful one, because it is actionable in a way "verify your claims" is not — **it says where to look: at the boundary of whatever artefact you are reading.**

### Why the roster grain is in scope

The operator's brief did not merely omit it — it explicitly asked us to check it ("verify the roster grain's `previously_rostered_ids` is captured pre-upsert by its caller — the audit did not clear that ordering"). We checked. It is broken the same way. Fixing what we were sent to look at is completion of the assigned task, not an addition to it; "gate fix" means the gate, not two of its three grains.

The pre-load capture in `scouting_loader.py` **is** taken at the right moment, but it feeds only the `MAX_ROSTER_DEPARTURES` cap scoping. The gate separately reads the roster prior at retire time. The gate is therefore inert today **only because the cap fires first — masking, not protection.** Two reasons that is not good enough: the gate is dead code whose only cover is a **separate, independently-owned policy constant**, and leaving one of three grains reading post-upsert re-arms the defect class behind a number for the next grain to copy — a next grain that is a **costed backlog item** (`.project/ideas/IDEA-154-per-perspective-game-retire.md`), not a hypothetical.

*(An earlier version of this sentence said the cap is a constant "someone will eventually tune". That prediction was pre-registered as a falsifier by DE and **falsified** — the value has been locked since E-267 with no proposal anywhere to move it. It is deleted rather than softened; see "The scope ruling never rested on frequency" below.)*

**Reachability, stated in the corrected form — and scoped to ONE DIRECTION, which the earlier wording was not.** For the divergence this epic exists to close — the **over-deletion** direction, where the corrected gate refuses and today's code deletes — divergence between the polluted and honest gates requires **both**: more than half the pre-load roster absent, **AND at least one id in the fresh crawl that was not previously rostered.**

**The defect is a MISSING PARAMETERIZATION, not loose wording — and naming the population is the entire fix** [code-reviewer, mechanism established from the two executed artifacts]. The sentence says *"divergence between the polluted and honest **gates**"* — that is **gate-VALUE divergence, population (ii)** — while its two conditions characterize the **observable-outcome** population (iii). Those are different questions, and the conditions are correct for the second and false for the first.

**The counterexample, and it required nothing new**: pre-load roster `P` = 10, fresh ⊆ `P` with 8 survivors, live prior inflated to 30 by this run's backfill churn. Legacy computes `8 >= 15` → **refuse**; corrected computes `8 >= 5` → **permit**. **Both stated conditions are false** — fewer than half the pre-load roster is absent, and no fresh id is newly rostered — **and the gate values diverge anyway.** Under (iii) this is not a divergence at all (both sides False); under (ii) it is. That is the whole of the defect.

**Why NEITHER sweep could catch it, which is what makes this a parameterization gap rather than an oversight.** SE's enumeration **pre-filters on `prior_pre < 2 * absent` — DE's boundary itself** — so it explores within the claim and can never test its necessity. DE's `t_roster_boundary.py` runs with **no churn**, where `live == snapshot`, the legacy gate tracks the corrected one exactly, and there is **zero divergence in that space by construction**. The counterexample is excluded from SE's space twice over: churn fixed at zero, and `10 < 4` fails the pre-filter. **Two executed artifacts sitting in one directory — one deriving the boundary in a world without churn, the other being the churn world where it fails.**

And the condition-2 omission has the same cause: the boundary was derived in a no-churn world, where the only way to separate `live` from `snapshot` **is** a new fresh-crawl id. **Backfill churn also separates them and is not a fresh-crawl id** — so condition 2 names one mechanism because its parameterization contained only one.

**The three shapes are NECESSARY, not SUFFICIENT.** They are the `(a, b)` projection of `corrected refuses ∧ cap permits`. Whether **legacy** permits turns on a third axis neither the boundary nor DE's sweep varies — what separates `live` from `snapshot`. An observable case additionally needs `live != snapshot` in the permitting direction. **That is why 2-vs-2 works** (shape `(2,2)` *plus* two brand-new fresh ids entering `live`) **and why 5-vs-5 fails** — 5-vs-5 is outside the three shapes entirely, so no amount of new-id machinery rescues it. The rule and the fixtures explain each other. A necessary-but-not-sufficient condition stated as sufficient is the defect this paragraph exists to correct; it must not re-enter one level up.

Story 03 leans on this sentence directly — as the justification whose **first half alone** must not be used to derive a fixture.

**A second correction fell out of scoping this one**, and it is the more consequential of the two: story 03's fixture warning described this boundary as *"a no-churn shape where `live == snapshot`"*. That was true of the boundary's **original one-condition form** and is false of the corrected two-condition form, which requires churn explicitly. Left alone it would have told an implementer that the boundary and a discriminating fixture are incompatible, when in the corrected form the boundary's second condition is exactly what makes a fixture discriminate. **A correction upstream left a warning downstream describing the pre-correction object** — the fifth host (a summary carrying a truth-value past its qualification) landing on this epic's own second-order text.

The second condition matters and was originally missing — the first half alone is **necessary but not sufficient**. Two agents reached that same missing condition independently: DE by executing its own weakest claim during self-audit, and SE from the opposite direction as a fixture-design trap (*with no churn, `live == snapshot`, so the legacy gate tracks the corrected gate exactly*). Those are the same condition stated from the gate side and the fixture side.

**The first half is separately CONFIRMED at execution tier** — SE's sweep verified that it predicts corrected-gate refusal, with zero mismatches. That strengthens the necessary half and says nothing about sufficiency, because the sweep varies neither the legacy gate nor the cap. Both halves of that sentence are load-bearing: a summary of the same result reached this epic framed as a blanket confirmation and would have reverted this paragraph to its over-claimed form (History).

**A count was the wrong instrument. This is the derived-complete characterization instead** [SE and DE, jointly settled] — and it counts the **observable-outcome** divergence specifically, which is the scoping the earlier wording lacked:

> Divergence in **observable outcome** — a floor-bearing design refuses where today's code deletes, i.e. **the legacy gate permits AND the cap permits AND the corrected gate refuses** — is confined, on the roster grain, to a **pre-load roster of 1, 2 or 3 rows**, each case additionally requiring **at least one newly-rostered id in the fresh crawl**. There are exactly **three** such shapes, and the bound is **range-independent**: the departure cap forces at most two absent snapshot rows, and the corrected gate refuses only when fewer snapshot rows survive in the fresh crawl than are absent from it — together capping the pre-load roster at three.

**This count's space is `MAX_ROSTER_DEPARTURES = 2`, and that must be stated with it.** The general bound is `S ≤ 2·cap − 1`; "three shapes" is the `cap = 2` instance, not a property of the design. Range-independent is not the same as parameter-free — the count is free of the *sweep* bounds, which is what makes it better than 222, and it remains a function of one policy constant. **Naming that space is the epic's own standing rule applied to its own best number**, and it is the one the earlier drafts came closest to shipping unqualified. (It does **not** license the retired *"someone will tune the cap"* prediction — that was pre-registered as a falsifier and falsified; see below. Stating a count's space and predicting the space will change are different claims.)

**Naming WHICH divergence is counted is not pedantry.** A resolved count does not scope the sentence: "three shapes" and "222" and "20" were each reported as *the* divergence count while measuring different things, and the sentence above says which one it counts. Three successive attempts to reconcile those figures failed (below), and the discipline of naming the measured divergence is what survives from the last of them.

Per-shape evidence tier, since presenting three shapes at one tier would overstate two of them:

| Shape `(survivors, pre-existing absences)` | Tier |
|---|---|
| `(1,2)` | **EXECUTED** — DE's loader run |
| `(0,2)` | **EXECUTED** — SE's 2-stored / 2-brand-new fixture |
| `(0,1)` | **DERIVED** from the constraint argument; never built as a fixture |

**THE RECONCILIATION — PARTIALLY RESOLVED. What each sweep measured is settled for one of them and OPEN for the other. Recorded in full because the failure pattern is worth more than the answer.**

> **⚠️ Read the three claims below as separate. Collapsing them is how this gap has now produced four successive explanations.**
>
> 1. **SE's sweep measures population (iii)** — SETTLED, source-verified, and it depends on no arithmetic. See the ruling under the convergence heading.
> 2. **DE's four figures are a function of its sweep bounds** — the *artifact-of-bounds* account, DE's own position, supported by the formula fit below.
> 3. **What DE's 222 measured** — **OPEN.** Claim 2 does not answer it. "The counts vary with the bounds" and "the sweep additionally required the legacy gate and the cap to permit" are different assertions, and only the first has evidence.

**Supporting claim 2: the formula fit.** DE's four figures fit one enumeration `c(n) = (3n−2)(n−1)/2`, with `n` the number of values in the swept range — **a four-point exact fit, not an assertion.** [DERIVED, **CR-2**; arithmetic re-checked independently by PM]

| Range | `n` | `(3n−2)(n−1)/2` | DE reported |
|---|---|---|---|
| `0..3` | 4 | 15 | **15** |
| `0..4` | 5 | 26 | **26** |
| `0..8` | 9 | 100 | **100** |
| `0..12` | 13 | 222 | **222** |

Four for four on a fixed quadratic. SE's ≈20 is the same three shapes enumerated over a different swept parameter (`new_ids` 0..7, as 7 + 6 + 7). **The multiplicity varies with the bounds; the shapes never do.**

**⛔ ONE ARGUMENT inside the third account is REFUTED — and note carefully that this refutes an ARGUMENT, not the account.** The third account framed the figures as three populations answering three questions (corrected-gate refusal; gate-VALUE difference; observable-outcome difference) and attached a decisive check: *"had DE's population carried the cap it could not have reached 222, since `a < b` with `b ≤ 2` forces `p ≤ 3` regardless of sweep range."*

**That decisive check is a UNIT ERROR.** `a < b ≤ 2 ⟹ p ≤ 3` bounds the **pre-load roster size**. It does not bound the number of swept parameter *combinations* realising those shapes, because the remaining swept parameters — new-id count, churn count, live size — still range freely. **222 counts combinations; 3 counts shapes.** Different units, so "a cap-constrained count would be range-independent" does not follow — and SE's own sweep is the counterexample that was in everyone's hands the whole time: it **carries the cap** and still scales 20 → 26 → 44 across three spaces with a byte-identical shape set. [Conceded and corrected by its author; PM's arithmetic confirmed independently.]

**⚠️ AND HERE IS THE TRAP THIS EPIC WOULD OTHERWISE HAVE WALKED INTO A FOURTH TIME.** Refuting that check removes an argument *against* the artifact-of-bounds account. **It supplies no argument FOR the original cap-based account.** Treating it as one would be the fourth successive explanation of a single disagreement, each adopted because it corrected its predecessor — the exact pattern recorded below. **PM did exactly this**, reverting to "the first account survives" on the strength of a refuted counter-argument plus a misattributed source, and it was caught by the party whose work was misattributed.

**The FRAMING of the third account SURVIVES and is load-bearing**: name WHICH divergence a count measures — observable-outcome, gate-value, or gate-refusal. **One of its row assignments is now source-verified and one is open**: SE's sweep is **(iii)**, not the (i) that account assigned it — corrected under the convergence ruling, and in the *opposite* direction from the two refuted reconciliations. What DE's 222 measured remains **open**.

**NO COUNT SHIPS**, which all three accounts agree on and which is the operative rule. The figures appear here only to identify what each measured; none is a fact about the code without its bounds *and* its question, and none belongs in a story, an acceptance criterion, or a summary.

#### The pattern: FOUR accounts of one 20-vs-222 gap, each arriving as the correction of the last

1. **Cap-based #1** — the gap is the departure cap: shapes above two absences are gate-divergent but deletion-unobservable.
2. **Cap-based #2** — inverts #1, asserting *"DE's sweep already applied the cap"* and relocating the difference to a churn axis plus a bound.
3. **Populations** — rejects both as cap-based, on a decisive check that confuses combinations with shapes. **Its framing survives; its decisive check does not; one of its row assignments is now source-verified and one is open.**
4. **The revert** — PM, on finding the formula fit, concluded "the first account survives on arithmetic" and reverted #3 wholesale. **Wrong twice over**: the fit supports the *artifact-of-bounds* account (the counts vary with the bounds), which is a different claim from the *cap-based* one; and PM attributed the fit to the wrong reviewer, having read it in a handoff whose header names the outgoing PM as its author and whose section heading names **CR-2**.

**Each was accepted because it corrected a known-wrong predecessor.** That is the finding — and #4 is the sharpest instance because **PM had already written that sentence into this History about someone else's error, then committed it, then was corrected by the very party whose work it had misattributed.** A rule that fires on a stranger's error and not on your own next one is not yet a rule you hold. **A reconciliation is a claim, and arriving as the correction of a wrong claim is not evidence for it** — the relief of having caught an error is what stops the replacement being checked, exactly as `.claude/rules/tool-output-integrity.md` records for retractions. Three iterations is enough to call it a property of the material rather than a run of bad luck: **this gap is unusually good at generating confident wrong explanations**, because both numbers are real, both authors are competent, and any story connecting them sounds like insight.

**The cheapest check beat all three explanations and nobody ran it for three rounds**: fit the reported figures to a curve. Four numbers, one formula, one minute. **Reconciling two measurements by reasoning about their METHODS is far more error-prone than testing whether one arithmetic relation reproduces the reported values** — and the numbers were sitting in the document the whole time.

**Status**: PM has verified the arithmetic first-hand and can show its working, but has **not** read DE's sweep source, so `n` = range-size is inferred from the fit rather than read from the code. That is a real limit and is why this is recorded as *survives on arithmetic* rather than *settled*.

**Recorded symmetrically, against both numbers, at both authors' insistence** — DE offered to take the whole correction and SE declined to let it. SE flagged DE's 222 as needing reconciliation while reporting its own 20 as a fact about the code. **Same error, different bounds**: a quantity over a self-chosen space, reported as though the space were given.

**Recorded symmetrically, against both numbers, at both authors' insistence** — DE offered to take the whole correction and SE declined to let it. SE flagged DE's 222 as needing reconciliation while reporting its own 20 as a fact about the code. **Same error — a quantity over a self-chosen space, reported as though the space were given — though over different bounds AND, as it turned out, different questions.**

**The symmetry is the finding, not the courtesy.** One author committing this is a slip; **two committing it independently, within the same hour, while actively hunting for exactly this class of error**, is a property of the work rather than of either agent. That is what makes the seventh host worth a standing rule instead of a note.

**⚠️ The paragraph that stood here was cap-based reconciliation #2** — *"the difference was the churn axis and the bound, not the departure cap; DE's sweep already applied the cap"* — struck 2026-07-25; see the numbered pattern above. Its own closing line was *"the wrong explanation is the kind that survives as a plausible-sounding reconciliation nobody re-checks."* It survived two more hands, and its replacement was wrong too.

**RULED: this result STANDS — verified, then restated in four ways** [code-reviewer, after re-executing `scratchpad/t_divergence_sweep.py` AND re-deriving its figures by hand].

**The strongest sentence available is not either number.** Across three sweep spaces the count moves **20 → 26 → 44 while the shape set is byte-identical** at `[(0,1), (0,2), (1,2)]`. That contrast *is* the range-dependent-count / range-independent-characterization finding, demonstrated in one line of the sweep's own output rather than argued. The numbers are supporting detail; lead with the contrast and they cannot mislead.

The tuple counts re-derive by hand from the three shapes, using the closed-form legacy condition `survivors + new_ids >= 0.5·(prior_pre + new_ids)`:

| shape `(survivors, absent)` | `prior_pre` | legacy permits when | `new_ids` 0-7 | 0-9 | 0-15 |
|---|---|---|---|---|---|
| `(0,1)` | 1 | `new_ids >= 1` | 7 | 9 | 15 |
| `(0,2)` | 2 | `new_ids >= 2` | 6 | 8 | 14 |
| `(1,2)` | 3 | `new_ids >= 1` | 7 | 9 | 15 |
| | | **total** | **20** | **26** | **44** |

**Three restatements the earlier wording got wrong:**

1. **SE's sweep measures population (iii), NOT (i).** It applies the cap as a **predicate inside the divergence test** rather than as a range bound, so shapes with `absent > 2` have both sides False and can never count as divergent — which is how it collapses to three shapes without bounding anything. The measured population is the full three-condition one: **corrected refuses AND legacy permits AND cap permits.**
2. **20 / 26 / 44 are counts of parameter TUPLES, not shapes.** The sweep reports `matching` = 434 / 546 / 882 over the same spaces, so the tuple-vs-shape distinction is visible in its own output.
3. **NOT "two independent routes".** The sweep pre-filters on `prior_pre < 2 * absent` — **that is DE's boundary**, so it explores *within* the derivation rather than arriving at it independently. Accurate wording: **an analytic derivation confirmed by execution over an added axis** (`new_ids`, which the analytic route does not have). Weaker than convergence, and it is what the evidence supports. What execution *does* independently establish is the cap-collapse and the shape set's range-independence.

**Recorded distinctly from the F1 convergence, and the contrast improved on inspection**: F1 was **a sound conclusion behind misattributed evidence**; this is **a sound conclusion with real, correctly-attributed evidence and a mis-described population.** Three distinct failure modes on one axis — whose the evidence is, and what it was measured over — is a sharper record than "one converged and one did not."

**How it was settled is the transferable part.** The reviewer did not rule by re-running SE's script: it re-derived 20 / 26 / 44 **by hand** from the three shapes, and cross-checked the shape set against its own earlier enumeration off a different artifact, where `(prior_pre, absent) = (1,1), (2,2), (3,2)` is the identical set under a different key. Its reason: **"re-running a script only confirms the script."** That is the exact companion to the printed-conclusion host in the History — an artifact's authority extends neither to the prose written beside it nor to a second run of it.

**Stated without apology, because the derived claim is the stronger one**: three shapes complete beats 222 enumerated, even though it is a smaller number. It removes the one sentence a reviewer could attack as inflated and replaces it with one that survives attack.

**The scope ruling never rested on frequency.** It rests on reachability — established by the executed two-row deletion — plus two reasons referencing no count at all: the gate is **dead code masked by a constant that is currently LOCKED**, and a grain left reading post-upsert is the template the next grain copies.

**Both legs were pre-registered as falsifiers by DE and independently adjudicated. One fell; the surviving text reflects that** [code-reviewer, 2026-07-25]:

- **"someone will eventually tune the cap" — FALSIFIED and DELETED, not softened.** `MAX_ROSTER_DEPARTURES = 2` at E-267, E-270 and HEAD; E-267 **locked** it deliberately (*"LOCKED as a real spec value… no dangling calibrate-before-dispatch decision"*), E-270's only `git log -S` hit is a reference addition, and a full-tree grep found **no proposal to change the value anywhere**. IDEA-160 proposed a *different, new* cap; IDEA-186 proposes changing this cap's **scoping, not its value**, and was filed by the claim's own author during this epic's planning — circular, and cannot support it. **The half that survives independently is *"it is a policy constant"*** (the operator personally set the sibling `MAX_GAME_RETIREMENTS = 2` by explicit decision, 2026-07-21). **A prediction about the future was doing load-bearing work in a scope argument**, which is exactly what the falsifier was written to catch.
- **"a post-upsert grain is the template the next grain copies" — HOLDS, and is now CITED rather than asserted.** DE flagged this as its weaker leg and expected it to fall; it is the stronger, and the evidence predates this epic. **`.project/ideas/IDEA-154-per-perspective-game-retire.md`** (CANDIDATE, indexed live, filed 2026-07-19 during E-267-02 AC verification) proposes exactly a fourth grain and carries DE's own costing note: *"A refused game has NO grain positioned to retire it… this is NOT a small extension of an existing grain — it needs its own retire path with its own perspective-scoped delete surface and its own bias-to-refuse corroboration."* The "next grain" is therefore a **costed backlog item, not a supposition**, and its gap sits inside `games` / `player_game_*` — the reconcile seam's own territory, not absorbed by E-273's reference tier. A future author writing "its own bias-to-refuse corroboration" copies from the three in-tree examples; leaving one of three broken leaves a broken template.

**Precision worth keeping, because a looser reading gets it wrong in both directions**: three adjacent ideas exist and **exactly one** counts. IDEA-146 and IDEA-147 are **refresh** ideas (changed-in-place rows), not retire grains — IDEA-146 says so itself. IDEA-140 is PROMOTED and *became* E-267's game grain. The surface is open by precisely one documented item.

**Recorded because the reviewer argued against its own verdict**: the observation window for leg 1 is ~5 days and two epics, so *"stable since E-267"* is near-trivially true and that conjunct is weak. **The falsification rests on the second conjunct** — after a deliberate lock and a subsequent epic that re-affirmed it unchanged, nobody has proposed moving it — which is not window-limited.

**One qualitative reading, DERIVED and not executed [DERIVED, SE]:** a pre-load roster that small is *plausibly* not an exotic corner — it is the state a sparse or truncated earlier crawl would leave behind, which is the degraded-data condition this gate exists to handle. **What would promote this to executed:** the prior-run roster sizes actually observed in production, which requires the live DB and was therefore out of reach for this planning work.

**Why this one carries a tier mark when it reads like a throwaway.** It is the **first claim in this epic to arrive in the self-protecting direction** — it makes the region sound more consequential, in support of a scope ruling everyone already favours, at the exact moment the quantitative case shrank from 222 to three shapes. Every one of the five safety-prose claims caught during this planning ran the *other* way, against what the authors wanted. **That asymmetry means the review's hit rate is evidence about the easy direction only**, and a claim nobody wants to challenge — because challenging it looks like arguing against caution — is exactly the shape `.claude/rules/tool-output-integrity.md` says concentrates in safety prose. The tier marks are what kept three false claims out of this document; the first flattering claim is precisely the one that must not get an exemption.

### The refuted "benign" ruling

`.claude/agent-memory/claude-architect/epic-codifications.md` already described this exact mechanism at E-267 closure — "`prior` is `old ∪ fresh`" — and ruled it **"benign, since dedup would have merged the rows anyway."** That assessment is wrong in general, for three independent reasons in descending order of decisiveness (SE):

1. **Ordering.** The retire runs *before* `dedup_team_players` by explicit design in both grains, and both call sites state the reason. Dedup cannot have merged anything yet. This alone refutes it, structurally.
2. **Detection requires both ids co-rostered.** `find_duplicate_players` joins `team_rosters` twice; a churned id appearing only in a boxscore is invisible to dedup entirely.
3. **Merging is not resurrection.** Dedup requires a last-name match plus a first-name prefix relation and refuses forks outright; and even a successful merge only re-points *surviving* rows — it cannot restore what the retire already hard-deleted.

Worth carrying as a shape: **a mitigation named in prose, never executed, protecting a path it structurally cannot reach.**

## Goals

- **On the two grains that keep a gate (game and player-line)**: restore the health gate's intended population — the set already loaded as of the start of this load, captured before any of this run's writes to that grain's delete scope.
- **On the roster grain: REMOVE the floor gate entirely**, on the operator's ruling to invert the bias there. Its permit becomes a non-empty fresh payload AND `MAX_ROSTER_DEPARTURES`, which becomes the grain's sole guard. **This goal is not "restore the gate" and must never be written as one** — there is no gate left there to read anything, and story 05 AC-3 forbids the smoothed "all three grains now read their prior correctly" phrasing for exactly this reason. *(Goal 1 previously covered "all three grains" and was false on the third; it carried none of the swept terms, which is why the mechanical sweep could not reach it.)*
- Prove the fix with tests that fail against current code and pass after, at each grain, including the churn shape that no existing test covers.
- Correct every piece of prose the fix falsifies, in the same change that falsifies it.
- Leave the gate's invariant stated in a form that would **catch** this defect rather than pass it.

## Non-Goals

- **No cap changes.** `MAX_GAME_RETIREMENTS` and `MAX_ROSTER_DEPARTURES` are untouched. `MAX_GAME_RETIREMENTS` in particular is doing the masking work that bounded the audit's game-grain blast radius to 2; changing it in the same commit destroys the before/after demonstration this epic rests on.
- **No new player-line cap — RE-AFFIRMED at the R1 disposition (2026-07-26) on much stronger grounds, and its ORIGINAL reason is now known to be incomplete.** *(This read: "With the gate honest, full churn refuses on the standalone `fresh_count > 0` check before any ratio is consulted." **That is true of run 1 and false by run 3** — a refusal still writes, so the population grows until the gate permits at the floor. The old sentence made this Non-Goal look like a consequence of the fix already being sufficient. It is not.)* The bar is no longer "a cap is unnecessary" but **"every mechanism that closes the window closes it by refusing forever, and a permanent refusal on this grain doubles the coach-facing season aggregate"** — measured, so a doubled stat line reaches a coach who reads the report as fact. **Three mechanisms were evaluated by construction — a cap, an `extra_guard`, and a churn-signature gate — and none was adopted.** The original masking argument still stands on its own (a cap would mask this epic's regression tests exactly as the roster cap masks the roster gate today), but it is now the *second* reason, not the first. Residual accepted and surfaced via the story 01 AC-15 diagnostic; the real closer is merge-not-delete → **IDEA-185**. See `WHAT CHANGED FROM THE COMMISSION`, item 5.
- **No delete-targeting changes.** The candidate/absent set is already correct; only the gate population is wrong.
- **No `not_final ∩ fresh` restoration.** See Technical Notes TN-7 — the asked shape is a provable no-op.
- **Partial id churn is out of scope** and goes to idea capture (TN-8) → **IDEA-185**.
- **The same-canonical-id capture residual is out of scope** — two source games redirecting onto one canonical id within a run, so the second game's capture sees the first's rows. **Pre-existing and genuinely fix-neutral here** (today's post-upsert read already contains them, because the payload loader commits per game), and **structurally REACHABLE** — an earlier "unreachable" assessment was retracted on a full read of `_find_duplicate_game`. Full statement, including the falsifier and the memoize-per-canonical-id closure if it is ever wanted, is **TN-15**. Listed here because TN-15 declares itself a non-goal and this section is where a reader looks for the list.
- No schema change, no migration, no crawl, no network, no touching `data/app.db`.

## Success Criteria

1. At each of the three grains, a test exists that FAILS against pre-fix code and PASSES after, driving the real `ScoutingLoader.load_team` — not a direct helper call.
2. `python -m pytest tests/` reports 0 failed. The **72 tests in the three grain files** (34 + 20 + 18 — the space is named because this count was previously stated as though it were the whole reconcile suite) stay green, **with EXACTLY TWO existing assertions changed epic-wide, both named and expected**, plus mechanical kwarg churn at the 9 direct call sites. **All three figures re-measured and CORRECT** [PM-VERIFIED, 2026-07-25]; note they are **collection** counts, not `def test_` counts — the game file has 30 `def test_` plus one parametrize over the 5-entry `_PERSPECTIVE_CHILD_TABLES`. Counting `def test_` gives 68 and looks like a discrepancy; it is not. **`tests/test_reconcile_at_load.py` is a fourth file, 19 further tests** — see TN-13.

   **⛔ THIS CRITERION READ "stay green with no assertion changed" AND WAS FALSE. Corrected 2026-07-25 at the second Codex spec pass.** Codex raised the same defect against **story 01 AC-12** and **story 02 AC-9**; the sweep for it found **two further sites, including this Success Criterion** — a structural field, and the third time in this epic that a defect Codex located in an AC also sat in top matter nobody re-read.

   **The two expected changes, epic-wide:**

   | # | Test | Story | Why |
   |---|---|---|---|
   | 1 | `tests/test_reconcile_at_load.py::test_empty_payload_refused_even_with_empty_prior` | **01**, AC-12 | asserts `crawl_is_authoritative(fetch_ok=True, fresh_count=0, prior_count=0) is False` — **precisely the input TN-1(c)'s vacuous-permit inverts**. **Vacuous-permit is OPT-IN, so the call as written above does NOT invert**: the test is REPURPOSED to the opted-in configuration and a SIBLING test pins the default-off refusal. Story 01 AC-12 carries the reconciliation; **the sibling is an addition, not a second changed assertion**, so this table's total stays two |
   | 2 | `tests/test_roster_grain_reconcile.py::test_catastrophic_roster_shrink_refuses_on_the_floor` | **03**, AC-11 | keeps its OUTCOME (still refuses) and **loses its REASON** — by the cap, not the floor. Its `"floor_ratio" in warnings[0]` assertion fails and its name and docstring become false |

   **Change 2 lands INSIDE the 72**, because `tests/test_roster_grain_reconcile.py` is one of the three grain files (the 18). **That is what made the old wording false rather than merely imprecise** — this criterion asserted the 72 were untouched while a story in the same epic required touching one of them.

   **The mechanism, and it is the epic's own subject once more:** change 2 arrived with the roster design's reversal, *after* TN-13 had established the "exactly one" count against the fourth file. **TN-13's count was correct for its own space and became an epic-wide claim by being read as one.** Every count carries its space — and a count's space can be invalidated by a change elsewhere without a single word of the count being edited.

   **Evidence scope, stated because it is narrower than it reads** [CR]: the zero-divergence probes behind "no assertion flips" patched only the **player-line and game** grains. **No roster figure exists** — the grain that produced every correction in this planning session was never measured both ways. Either run the roster probe before READY, or treat this as an obligation on the implementer with its scope named. Do not let a measured-sounding claim cover an unmeasured grain.
3. The deletion-neutrality property (TN-5) is asserted, not merely argued — **on game and player-line, the two grains where it holds** (story 01 AC-8, story 02 AC-7). **On roster it is deliberately FALSE**, as a prediction of the same `W ⊆ fresh` premise rather than an exception to it, so there is nothing to assert there and its absence is not a gap. *(Scoped 2026-07-25; the unqualified form read as covering all three grains.)*
4. No prose in `src/`, `CLAUDE.md`, or the context layer still states the falsified claims (TN-9).

## Stories

| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-276-01 | Shared gate primitive + player-line grain | **DONE** | None | software-engineer |
| E-276-02 | Game grain | **DONE** | E-276-01 ✅ | software-engineer |
| E-276-03 | Roster grain | **DONE** | E-276-01 ✅, E-276-02 ✅ | software-engineer |
| E-276-04 | End-to-end churn regression through `generate_report()` | **DONE** | E-276-01 ✅ | software-engineer |
| E-276-05 | Correct the context-layer prose the fix falsifies | **DONE** | E-276-01 ✅, E-276-02 ✅, E-276-03 ✅ | claude-architect |

**ALL FIVE STORIES DONE (2026-07-26). The epic is `COMPLETED` — see the Status block at the top of this file, which is authoritative.**

**Why the epic HELD `ACTIVE` through five DONE stories, kept because it is a real record and this is the only place it sits beside the table where a reader meets the statuses**: `COMPLETED` is authored at the implement skill's Step 8 sub-step 3 and finalizes only on a green full suite in the main checkout (`.claude/rules/workflow-discipline.md`, Full-Suite-Green Closure Gate). **All-stories-DONE is not archivable**; four items stood between the two states — F-7 (software-engineer, `src/` prose), `docs/admin/operations.md` (docs-writer), PM's `epics/` + `.project/` identifier sweep, and the TN-11 crash-path ruling. **All four landed, and the closure passes ran.**

> **⛔ THIS PARAGRAPH READ *"the epic remains ACTIVE"* WITH THOSE FOUR ITEMS LISTED AS OUTSTANDING, AND EVERY CLAUSE OF IT WAS TRUE WHEN WRITTEN.** *(Corrected 2026-07-26, at the merge, found by the team lead.)* **It was falsified by the work COMPLETING** — nobody edited it, and **no sweep would have flagged it**: it was accurate at the moment of writing, self-consistent, and its falsifier was the epic finishing. **The 9th mechanism, landing on the Status-adjacent text of the epic that catalogues it, at the last possible moment.**
>
> **And it is the twin of the hazard the Status block's own note anticipates, from the other side**: that note warns a reader of an *unmerged worktree* not to read COMPLETED as shipped; **this line told a reader who reached the Stories table first that the epic was ACTIVE with work outstanding.** One file, two readers, opposite errors — **which is why the Status block is named as authoritative here rather than the statement being duplicated.**

**02 before 03, and the ordering is required rather than preferred.** All three of 01, 02 and 03 modify `src/db/reconcile_at_load.py`; 01 blocks both, but 02 and 03 were left unordered against each other, which the project's own story rule forbids for stories sharing a file. The direction is not arbitrary: the game grain is the straightforward application of the settled shape, while the roster grain is the one that deliberately diverges on candidate population (TN-3). **Landing the plain case first means the roster story edits a file where the uniform shape is already visible in two grains, so a divergence is legible as a divergence.** Reversed, the roster's candidate rule would be the only example present when the game story lands, and "harmonize the grains" — the exact move TN-3 exists to prevent — becomes the natural-looking one.

**Sequencing constraint, stated so a future reader does not "improve" the split:** tests and fix land **together** within each story. The ACs require tests that fail before and pass after; a tests-only story ends on a red suite and cannot pass code review. The split is therefore by grain, never by test-vs-code. Likewise the shared primitive is not its own story — with no consumer it is a no-op whose tests can only pin arithmetic, and it would leave the tree half-migrated (one grain on the new gate population, two on the old).

## Dispatch Team
- software-engineer
- claude-architect

## Technical Notes

> # GATE SEMANTICS — RESOLVED PER GRAIN (2026-07-25, joint SE+DE artifact, team-lead ruled)
>
> **The conjunction is DROPPED. Do not implement from the "settled shape" recorded further below — that is history.** The outstanding review pass has since run: see the READY Scorecard, which records what its sweep found in these Technical Notes and what it deliberately left alone.
>
> **⚠️ SPEC-INTEGRITY OBLIGATION, and it is this epic's own subject at one further remove.** The design was settled in a joint software-engineer / data-engineer artifact that **exists only in agent context — it is on no filesystem.** A reviewer looking for it ran the search correctly (ERE, one path per invocation, with a positive control after hitting the documented ugrep silent-empty quirk) and confirmed the absence is real. **This epic therefore MUST NOT depend on that artifact by section reference**; every load-bearing conclusion from it is inlined above and below, and any surviving `§N` citation is a citation that resolves to nothing — the exact defect TN-9 exists to prevent and TN-16 records for evidence (*"a construction that exists only in a transcript is not a regression test"*). **GATE SATISFIED 2026-07-25 — TWICE, and both files should be kept.**

- **`.project/research/E-276-roster-design-recommendation.md`** — the **authors' artifact** (software-engineer + data-engineer), all eleven addenda applied inline and reconstructed **verbatim from session transcripts** rather than from memory, since the reviewer's findings turn on specific words. Its §11 is the change log and retraction chain; its §12 preserves the original §6 unrepaired so the repair can be audited against the assigned text. **This is the primary source.**
- **`.project/research/E-276-roster-design-record.md`** — PM's independent record, written before the authors' file landed, when it was unclear that it would. **Explicitly not the authors' artifact**: assembled from relayed executions, every result attributed and marked `[EXECUTED, <agent>]` because PM ran none of it.

**Keep both, and DIFF rather than delete.** Two records of one design written from different vantage points, neither derived from the other, is a stronger artifact than either — and this epic has spent a day establishing that a claim's *provenance* is where its defects live. Where they disagree, the authors' file is primary and the disagreement is the interesting object.

> **⚠️ "BOTH FILES" ACCOUNTS FOR TWO OF FIVE. The full `E-276-*` research set, added 2026-07-25** — an independent enumeration found three artifacts this epic never mentioned, **two of them carrying retired figures**:
>
> | File | Status |
> |---|---|
> | `E-276-roster-design-recommendation.md` | **LIVE — primary source** on the roster design |
> | `E-276-roster-design-record.md` | **LIVE — PM's independent record**, kept for the diff |
> | `E-276-process-findings.md` | **LIVE** — the extracted process mechanisms; read by claude-architect at the trigger-8 gate |
> | `E-276-triage-handoff.md` | ⛔ **SUPERSEDED, header added.** Carried *"13 direct `crawl_is_authoritative` calls"* (now **7**) and *"exactly one assertion inverts"* (now **two**) |
> | `E-276-conjunction-removal-draft.md` | ⛔ **SUPERSEDED, header added.** An executed work order that quotes removed and replacing text side by side |
>
> **Neither superseded file was reachable by anything this epic does.** `.project/research/` is outside story 05's sweep scope (`CLAUDE.md`, `.claude/rules/`, `.claude/agent-memory/`), and no term or structural sweep covers it. **The retired count survived in a sibling of the directory story 05 is instructed to write into** — and it survived *because* the sentence above said "both files", which reads as a complete accounting and is a count over a space nobody checked. **The seventh host, in the sentence that scopes the artifact set.**

**Why PM wrote it rather than waiting for its authors**: a gate its setter then waives is worse than no gate, and this one exists precisely because *a design settled in an artifact on no filesystem is a citation that resolves to nothing.* The record's destination also makes the History extraction cheaper — see the size note.
>
> | Grain | Shape | Basis |
> |---|---|---|
> | **game** | corrected gate (pre-upsert snapshot population) | **multi-run CLEAN** — newly-completed games raise numerator and denominator together, so the strand cannot outgrow the recurring set. A checked clearance *with its mechanism*. |
> | **player-line** | corrected gate | design **not reopened**. ⛔ **The former basis — *"the dedup sweep closes the one-run window in both dominant shapes"* — is FALSE and is retired** (R1, 2026-07-26; reached independently by SE and DE). The sweep closes it in **one** shape only. Corrected basis: **the one-run window is CLOSED for dedup-mergeable churn on the scouted team's own block, and OPEN otherwise** — `dedup_team_players` is scoped to the **scouted** team, so the **opponent block has no closer in any shape**, and the detector matches on **name prefix**, so non-prefix churn (`Mike`→`Michael`) is invisible to it. **Accepted, documented residual** — story 01 AC-14 regime B pins it; closer is [[IDEA-185]]. |
> | **roster** | **V1 — NO floor ratio.** `permit = (fresh payload non-empty) AND (|absent ∩ previously| ≤ MAX_ROSTER_DEPARTURES)` | operator ruling to invert the bias, plus five required inputs |
>
> **The mechanism behind V1, which explains every failed alternative rather than cataloguing them** [SE+DE]: *a payload-size numerator recovers when rows strand; an overlap numerator does not — and **V1 has no numerator to ratchet at all.*** Every overlap-based design failed for one reason.
>
> ### THE FORK RESIDUE HAS THREE CASES, NOT ONE — and "team sums correct either way" is true of only the first
>
> An earlier version stated the residue as a single shape (a split per-player line, team sums correct). **That holds only for a REFUSED fork.** `merge_player_pair` is delete-or-update, so a BROKEN fork splits by branch [EXECUTED, SE]:
>
> | Case | Effect | Team sums |
> |---|---|---|
> | **Fork REFUSED** | split per-player line; one human's season understated | **correct** |
> | **Fork BROKEN, ids share a game** | colliding stat rows **DELETED** — stats destroyed | **WRONG, low** |
> | **Fork BROKEN, distinct games** | rows re-pointed; canonical line **inflated** | correct; the other human's season vanishes |
>
> **In a real id re-issue both broken branches occur across a season.** The reassuring summary — *"team sums count each at-bat once either way"* — was the **refused** case generalised to all three, which is the same safer-qualifier shape recorded three times elsewhere in this epic.
>
> **And the three `team_rosters` delete paths are COUPLED, not independent** — the correction that makes the above reachable at all. The retire (`retire_departed_roster_players`) can **trigger** the merge (`_delete_or_update_rosters`) within the same run, by collapsing a fork to a mergeable pair. Listing them as three separate surfaces understates the exposure, and that coupling is the mechanism of the finding above.
>
> **NON-TRANSFER — three of them, and they are the point.** A payload-size numerator lets a payload arbitrarily unlike what we stored clear the gate by being large enough; that is survivable on roster **only because the cap covers it**, and **player-line has no cap**. Prefer-delete is defensible on roster — but **re-derivability is NOT what carries the case, and leading with it over-claims in the very input the ruling turned on** [CR-2]. The load-bearing argument is **which-wrongness**: under sustained truncation both designs are permanently wrong in opposite directions, and **a wrong delete converges on the only evidence available while a strand persists *against* evidence.** Re-derivability is the *supporting* argument, true of **the `team_rosters` ROW** under an eventually-healthy crawl — false on player-line, where a deleted stat row is gone.

> **⚠️ Why the ordering matters rather than being a stylistic preference.** The design was ruled on **sustained truncation without recovery** — named in story 03 as the input that discriminates V1 from every floor-bearing design, and the one both rejected alternatives passed the other four without. **That is precisely the case where re-derivability is FALSE**: the mechanism that would restore the row is the thing that is broken. An argument resting on re-derivability rests on a premise that fails in the deciding case.

> **⚠️ CARVE-OUT, and this epic committed the defect it identifies one section from identifying it.** The **row** is re-derivable; **the delete's downstream effect on the identity graph is not.** A delete that collapses a refused dedup fork into a mergeable pair triggers a merge in the same run, and restoring the roster row on the next crawl **does not un-merge the identity or restore the merged-away stat row.**
>
> The sentence was scope-accurate about **rows** and was doing duty about **deletes** — the same shape as every other finding in this epic, committed inside the argument that licenses the design. The prefer-delete case survives **for the ordinary case, which is what it was written for**; it does not extend to a fork member. Consequence for the composition headline: *"12 self-undo + 1 pre-existing"* assumes the pre-existing row is ordinary — **if it is a fork member it is not self-undoing in any sense.** And the fork residue below is roster-shaped. **Never describe a roster-specific shape as *the* reconcile gate.**
>
> ### THE BOUND IS A RATE, NOT A TOTAL — and PROTECTION RUNS BACKWARDS WITH RESPECT TO SEVERITY
>
> General guarantee: **≤2 pre-existing roster rows deleted as departures per *retire invocation*, per `(team_id, season_id)`** — any crawl, any roster size, any churn. It does **not** bound cumulative loss. The **static-crawl sharpening** is ≤2 across all runs, because deleting the missing rows leaves survivors fully covered and the next run sees zero. **"≤2 across all runs" unqualified is FALSE for the progressive case — and it is the reassuring half, the one that survives summarisation.**
>
> **The finding that must ship with the bound, because "bounded at ≤2" reads as a bound on DAMAGE and is a bound on SPEED** [CR, independently verified by SE against its own bound]:
>
> ```
> PROGRESSIVE to empty (11,9,7,5,3,1)   per-run [2,2,2,2,2,2]   total 12 of 13   survivors 1
> CATASTROPHIC (drops to 1, repeated)   per-run [0,0,0,0,0,0]   total 0          survivors 13
> CATASTROPHIC (drops to 3, repeated)   per-run [0,0,0,0,0,0]   total 0          survivors 13
> ```
>
> **A gently degrading crawl can empty a 13-player roster two rows at a time with the cap permitting every single step. A catastrophically broken crawl loses nothing, because the cap refuses.** Same class of overclaim as `permanent-while-broken`.
>
> **And it is a genuine TRADE, not a defect — this half must never be dropped** [CR]: the same 2-per-run shape is *exactly correct behaviour* for a real roster losing two players a week. **The cap cannot distinguish a genuine progressive departure sequence from a progressively degrading crawl — they are byte-identical at every step**, and any gate that could tell them apart would need evidence the crawl does not carry. So: **the bound is a rate; the rate is indistinguishable between correct behaviour and slow degradation; the residual is therefore ACCEPTED, not closed.** It is a further argument for stating the composition rather than reaching for another gate.
>
> The unit is per *retire invocation*, not per run. **Three `team_rosters` delete paths exist** — `retire_departed_roster_players` (`src/db/reconcile_at_load.py`, the capped retire), `_delete_or_update_rosters` (`src/db/player_dedup.py`, the merge — **uncapped**, and later in the same `_load_team_core`), and `_delete_team_scoped_data` (`src/reports/lifecycle.py`, orphan reclamation) — and one `generate_report` reaches all three; morning-run walks several teams per process.
>
> **⚠️ Symbol anchors, not line numbers, and one of them is a trap.** These were originally cited as line numbers, which breaks `.claude/rules/tool-output-integrity.md`'s stable-anchor rule — *an artifact establishing a bound while breaking that rule is the shape this epic exists to catch.* Re-anchored and verified. The trap: a naive lookup from the old `reconcile_at_load.py:1364` lands on **`_cap_on_genuine_departures`, a NESTED def at indent 4** — the DELETE sits in the **enclosing** `retire_departed_roster_players`. Anyone re-deriving these from the old numbers will hit it.
>
> The strong form: the bound holds because **the guard and the delete consume the identical set object** — no drift surface between check and action, a stronger artifact than two computations agreeing.
>
> **The composition statement, with its limit applied — do NOT soften this to "self-healing."** V1's pre-existing loss is **permanent-while-broken, not self-healing.** Re-derivability is conditional on a subsequent healthy crawl, and sustained truncation has none — the mechanism that would restore the row is the thing that is broken. Today's alternative is *also* permanent, in the other direction. **Both are wrong rosters; the operator's ruling picks which wrongness.** (The team lead's own ruling described it as self-healing; the artifact carries the corrected form.)
>
> **`W ⊆ fresh` is a NAMED PREMISE for neutrality on game and player-line, not a structural guarantee** — stated as what it is: could not be falsified (one `INSERT INTO games` path; 179 runtime invocations across the full suite), which is not proof. Story 02's runtime assertion is what guards it.
>
> ### STANDING FORWARD OBLIGATION — the wording at the constant is operator-facing and must say RATE
>
> With no floor on roster, `MAX_ROSTER_DEPARTURES` becomes the only thing between a truncated crawl and pre-existing rows. "No cap moves in this epic" is now a forward obligation that must be written **at the constant**, where a future tuner reads it — not only here.
>
> **The wording matters more than its size, and the obvious phrasing is wrong.** *"Raise the cap to 5 and per-invocation pre-existing loss becomes ≤5"* is technically correct **and reads as a bound.** Executed, from a 26-row roster against a progressively degrading crawl over 5 invocations:
>
> ```
> cap=2   per-invocation [2,2,2,2,2]   cumulative 10   survivors 16
> cap=5   per-invocation [5,5,5,5,5]   cumulative 25   survivors  1
> ```
>
> **Raising the cap to 5 does not mean "5 lost". It means 5 per invocation — `5N`, unbounded in N** — and morning-run walks several teams per process, so N is not one. Required wording at the constant:
>
> > This constant sets the **per-invocation RATE** of pre-existing roster loss, not a total. Cumulative exposure is unbounded in the number of invocations against a progressively degrading crawl. **It is also the SOLE guard on the roster grain — there is no floor ratio beneath it.**
>
> **Both sentences are required and they are independent** [CR-2]: a tuner who reads "this sets a rate" still does not learn there is nothing underneath it. Only the first was previously mandated.
>
> ### ⛔ THE PIN IS NOT A MITIGATION FOR THE RESIDUE, AND NEVER COULD BE — recorded in full at **TN-19**
>
> **Promoted out of this banner into a numbered Technical Note** so a story and a future cap-tuner can cite it, and so it is not read as part of the superseded design history this box also carries. **Do not re-record it here.** The three things that must not be lost in any summary of it, including this one:
>
> 1. It is a **FALSE MITIGATION**, not a resolved tension — a defect in how the cap was **characterized**, not a contradiction to close out. Writing it up as *"orthogonal — resolved"* converts the finding into its own dismissal.
> 2. **Orthogonality is the EXPLANATION of why the pin cannot fire on the residue. It is never the verdict.**
> 3. The rider is **non-droppable and load-bearing**: *"the cap is locked"* is a true statement about change control and **carries ZERO adequacy content.** The first clause sounds complete without it, which is exactly why an editor will trim it as redundant.
>
> **⛔ THIS SENTENCE PREVIOUSLY CLAIMED TO BE "the last place in the whole design where 'bounded' could be read as a bound on damage rather than on speed." THAT WAS FALSE, AND IT WAS FALSIFIED BY A REVIEWER CHECKING THE ASSURANCE INSTEAD OF TRUSTING IT.**
>
> The joint artifact's §6 — the section arguing the cap is **adequate** — used the word three times, none qualified: *"an adequate **bound** on pre-existing loss when the failure it **bounds** is re-derivable … doing visible, **bounded**, stated work."* Occurrence 1 is a **truth-level** failure, not a clarity one: unqualified, *"an adequate bound on pre-existing loss"* is **false**, because the cap bounds the **rate** while cumulative loss is unbounded — 13 rows to 1 at the shipped value, with the cap permitting every step.
>
> **And the location was the worst available**: §6 is the future cap-tuner's highest-traffic paragraph, sitting **upstream** of this corrected wording. The reader most likely to be misled met the false sentence first and the correction second.
>
> **The shape, recorded because it is this epic's signature defect committed by the epic's own closing assurance**: a scope claim carried past its case, *inside the sentence asserting the defect has nowhere left to appear.* An assurance of completeness is exactly the claim that stops anyone checking — which is why it was found only by a reviewer who checked it rather than relied on it.
>
> **The correct, non-absolute form**: this is the wording a future cap-tuner reads at the point of changing the value, and it must say **rate**. It is not the only place the confusion can arise, and no sentence should claim to be.
>
> ### How it got here — the conjunction's failure, kept because the reasoning transfers
>
> A code-reviewer counterexample (F1) was **reproduced through the real `ScoutingLoader` by data-engineer, both regimes side by side**: the conjunction gate permanently locks the roster grain on a reachable input where today's code converges to a clean roster — three players stranded on the coach-facing grid and every subsequent genuine departure blocked. **The lock is fed by two mechanisms, not one**: `MAX_ROSTER_DEPARTURES` counting the stranded rows, *and* the corrected gate's own denominator being inflated by rows its own refusals stranded. A fix addressing only the cap leaves the second intact.
>
> The operator then ruled that the roster grain's bias **INVERTS** — delete rather than refuse there — with bias-to-refuse unchanged on the other two.
>
> **Five required inputs, and the fifth is the one that matters** [SE+DE]: DE's truncated crawl · CR-2's churn sequence · CR's truncation-plus-churn · SE's 13-row-plus-14-churn · **sustained truncation without recovery.** The fifth exists because **both rejected floor-bearing designs passed the first four — precisely because all four recover.** Without that sentence a future reader adds a sixth input without understanding why four were not enough.
>
> ### The losing design was RULED against, not withdrawn — recorded so the ruling can be attacked, not only its outcome
>
> The two designs differ **only at `snapshot = 3`** (derived, then independently re-derived and executed: V4 ≡ V1 for every snapshot ≥ 4). That region splits:
>
> - **Transient truncation**: V4 refuses once and recovers; V1 deletes and the next healthy crawl **restores the roster row**. V4's advantage is avoiding one run of a short grid — **visible discontinuity**. Framing it as *"protection"* is what gave it weight, and the relay layer did so.
>
>   **⚠️ "V1 does not lose data there" was FALSE and is corrected to "restores the roster row"** — the weaker claim, which is true unconditionally. [CR derived it and named the experiment; SE EXECUTED it.] **For a member of a refused fork, V1 loses a stat row inside the transient run, with no sustained truncation required**:
>
>   ```
>   1  intact fork, dedup runs      batting=[janet:3, john:4, jstub:2]   roster=[janet, john, jstub]
>   2  retire deletes Janet         batting unchanged                    roster=[john, jstub]
>   3  SAME RUN, dedup sweep        batting=[janet:3, john:4]            roster=[john]
>   4  next healthy crawl restores  batting=[janet:3, john:4]            roster=[janet, john]
>   ```
>
>   Fork members are **not exempt**, so the retire deletes one, **the fork collapses to a pair, and the same run's dedup sweep executes the merge.** At step 4 the recovery crawl restores the roster row and **does not restore the merged-away stat row or un-merge the identity.**
>
>   **⚠️ DISPOSITION, IN ITS THIRD AND CURRENT FORM: PRE-EXISTING **and** WIDENED by V1. Filed as an idea, not a blocker.** The chain was first reported as a mis-stated cost of the new design, then as pre-existing-and-not-widened. **Today's code fires it identically** — that leg holds and is what keeps this an idea. **The "not widened" leg is RETRACTED.**
>
>   Executed at loader tier on a 13-row roster containing a fork trio plus 10 unrelated players, the fresh crawl dropping one player, with `c` jersey-backfill churn rows:
>
>   ```
>   c=10  today refused=False  janet_gone=True   fork_merged=True
>   c=10  V1    refused=False  janet_gone=True   fork_merged=True
>   c=14  today refused=True   janet_gone=False  fork_merged=FALSE  <- fork INTACT
>   c=14  V1    refused=False  janet_gone=True   fork_merged=True   <- breaks under V1 only
>   ```
>
>   Today refuses iff `|fresh| < 0.5(|S| + c)` — with `|S| = 13, |fresh| = 12`, that is **`c > 11`**. Found by CR, confirmed independently by DE and SE.
>
>   **⚠️ THE STRUCTURAL ARGUMENT IS NARROWED, NOT REFUTED — and the distinction is the finding.** The derivation (V1-permits-while-today-refuses forces a stored roster ≤3; at 3 you delete 2 of 3, **destroying** the fork rather than collapsing it) **is not wrong. It rests on an UNSTATED PREMISE: churn = 0.** With churn present, today's floor denominator is the **live** population (`snapshot + churn`) while the cap counts only `absent ∩ previously` — the two populations diverge, so today can refuse while the cap sees a single genuine departure, and the step `survivors < absent ≤ 2 ⟹ stored ≤ 3` fails because it silently assumed both guards read the same population. **The honest statement, which replaces the unqualified one: no widening in the churn-free case.** Once more the session's signature defect — a correct derivation carried past the case that produced it.
>
>   **MISSED or EXCLUDED? Excluded — parameterization, not coverage.** The sweep covered `{stub, m1, m2}` + 0-11 unrelated rows and every absence subset **with churn held at 0**; the independent search covered the ≤3-row region, **also churn-free.** The axis was held constant by both, independently.
>
>   **⚠️ THE WIDENED REGION SPLITS INTO THREE RÉGIMES, AND A ONE-TRADE SUMMARY OF IT WAS WRONG.** An earlier version of this paragraph — DE's, corrected by CR and re-executed by DE — said the widening was *"structurally the same trade as sustained truncation, which the operator has already ruled on."* **True in most of the region, false in a two-value band, and the band is where it matters most.** Executed on a 13-row roster (`R = 13`):
>
>   ```
>   c    healthy_refused  churn_left_after_healthy  departure_refused  janet_alive
>   11      False                 0                     False            False
>   12      False                 0                     True             True     <- BAND
>   13      False                 0                     True             True     <- BAND
>   14      True                 14                     True             True     <- LOCK
>   ```
>
>   The two thresholds differ because a healthy run compares `R` against `0.5(R + c)` while a departure run compares `R − 1`: **today LOCKS at `c > R` but refuses DEPARTURES from `c > R − 2`.** The decisive column is `churn_left_after_healthy` — in the band today clears **all** churn on a healthy run, so it is **functioning normally and refusing only the departure**, not locked.
>
>   | régime | today | V1 | the trade |
>   |---|---|---|---|
>   | `c ≤ R − 2` | permits | permits | no widening |
>   | **`R − 2 < c ≤ R` (BAND)** | healthy; churn clears; **stats untouched**; Janet stranded on the grid | Janet retired correctly; **fork breaks; a stat row destroyed or misattributed** | **grid clutter vs a CORRUPTED STAT** |
>   | `c > R` | locked (the roster lock) | converges | the ruled trade — both permanent |
>
>   **Why the band changes the disposition rather than decorating it.** The roster grain's own docstring says its failure mode is *"grid clutter, **never a corrupted stat**, which is what separates this grain from the game and player-line grains."* **In the band, a roster-grain delete produces exactly the corrupted stat that sentence rules out.** The operator's prefer-delete ruling rests on roster failures being recoverable grid-level issues — so *"the same trade already ruled on"* **claims a coverage the ruling does not have.**
>
>   **STILL NOT A BLOCKER**, and the reason must ship with the widening: the band is **two values of `c` for any roster size**, and **its occupancy is unmeasured.** At `c ≥ R + 1` the original argument stands untouched. **State the trade PER RÉGIME; do not claim fix-neutrality, and do not claim the ruling covers the band.**
>
>   **Same family as the roster cap lock, and not by coincidence**: the churn-inflated denominator is the **one** place today's floor is stricter than V1, so it is the only place removing the floor can widen anything. Both ideas describe one region.
>
>   **The retraction is worth more than the fact** [SE, in its own words]: the sweep confirming the original claim was run *to verify another agent's result*, and **reproduced that agent's blind spot** — both had held churn constant. **"I did not verify your claim. I reproduced your blind spot with different arithmetic."** Two agents, one fixed axis, and **the agreement made the claim more credible than the original rather than testing it.** Found by a third varying the axis the other two had fixed.
>
>   **And the lesson is one level up from where it was first recorded, not a new one** [DE]. It was reported as *"a finding's disposition needs its own control run, not just its mechanism"* — but **the control run WAS made** (today vs V1); it was the control that was under-covered, on the churn axis. Correct form: **a control run needs its own parameterization check.**
>
>   **Do not write "V1 does not introduce this chain" in any form — and do not flip to "a cost of V1" by elimination either.** It is not a cost of V1 in origin; V1 extends its reach. **Two refuted dispositions do not make a third by elimination**, which is the same substitution addendum 7 was itself correcting.
>
>   **The wording fix — *"restores the roster row"* rather than *"does not lose data"* — stands regardless of disposition**, and that separation is the point: the stronger phrasing is false for a fork member whether or not this design caused it. The cosmetic-vs-permanent asymmetry the ruling turns on survives intact, and the ruling still goes to V1.
> - **Sustained truncation, no recovery**: **both designs are permanently wrong, in opposite directions.** V4 strands two rows indefinitely; V1 deletes rows the crawl no longer evidences, and re-derivability is conditional on a healthy crawl this case does not have — **permanent-while-broken, not self-healing.**
>
> **The ruling chooses which wrongness; it does not choose between a wrong option and a costless one.** It goes to V1 because the operator ruled prefer-delete on this grain, and because a wrong delete at least converges on the only evidence available while a strand persists *against* evidence.
>
> **The losing argument, stated strongly enough to attack**: V4 restores the protection V1 loses in exactly the region V1 loses it and nowhere else, because a payload-size numerator recovers when rows strand while an overlap numerator does not. **That is true, and it is a better argument than the one originally made for V4.**
>
> **Struck wherever it appears — the team lead's own withdrawn clause**: *"V1's cost under persistent truncation: none — it converges to the truth."* Too clean; it holds only if the truncation reflects reality. Recording only the outcome would have preserved retracted words under their author's authority, which is worse than an under-attributed ruling.
>
> **And the provenance of the deciding comparison, which a reader will otherwise underestimate**: the cosmetic-vs-permanent comparison only became available **because two agents had each executed a different half of the region.** *The comparison was cheap; producing the halves was not.*
>
> **Two floor-bearing alternatives died to inputs nobody had run**, and the authorship of the error is recorded in DE's own words because the shape is transferable: *"I derived the exact region where V4's floor is active and then treated that region as homogeneous. **The narrowing is what made it feel safe to stop.**"* A correct narrowing that licenses stopping is more dangerous than an under-covered input set, **because the narrowing is real work and feels like rigour.** Neither author caught it; the counterexample and its execution landed within one exchange.
>
> **A framing that must NOT be carried**: V4 was called elegant for making `crawl_is_authoritative`'s false docstring true. Overturned, verbatim — **"matching stale prose is not evidence of correctness — it is the epic's thesis run backwards."** The docstring describes a *weaker* gate someone rejected in code and never updated the words for.
>
> **ACs still phrased as *"the legacy gate permitted and the corrected gate refused"* are STALE** — the conjunction is gone, so there is one gate per grain and no second conjunct to attribute a refusal to. They are rewritten with the design, not before it.
>
> **Why this box replaced a "SETTLED" one.** This epic was reopened three times by an interim position relayed as settled. The historical record of how the conjunction was reached is kept below — as history, not spec.
>
> ### The superseded shape, kept as HISTORY (2026-07-25, morning)
>
> The gate shape below was software-engineer's joint recommendation, **explicitly endorsed by data-engineer**, who withdrew its competing position and named its own artifacts as superseded. PM took this from both primary sources directly rather than a relay. **It is recorded because the reasoning that produced it — and the reasoning that broke it — is this epic's most transferable content. It is not the spec.**
>
> **The settled shape:** gate = the **conjunction** of the legacy live-population gate and the corrected snapshot-population gate; candidate population = **live prior, uniformly, with no intersection on any grain**; snapshot feeds the **gate only**, as a required timing-named parameter; vacuous-permit on an empty protected population; caps untouched.
>
> **Superseded — MUST NOT survive anywhere in this epic** (DE flagged the incompatible-merge risk explicitly): the `prior_at_start ∩ prior_now` intersection in any form; "gate strictly narrower"; "the fix never newly deletes a row that existed before the run"; the three-part roster-specific neutrality wording naming `MAX_ROSTER_DEPARTURES` as the bound; and the note that neutrality is "relocated to the cap". Each was correct for a design we did not adopt. A reviewer finding one of these beside the blanket form should treat it as a defect, not a nuance.
>
> ### THE BANNER MUST BE SWEPT MECHANICALLY, NOT READ
>
> **Two prohibited shapes survived a 24-finding triage and were caught only on a later reader's first pass** — story 02's *"to compute the intersection"* and story 03's *"the roster carve-out"*, both in **implementation guidance** rather than prose, which is the worst place for them: that is the sentence an implementer reads while deciding what to build. **A prohibition list that relies on a reader noticing is not a prohibition.**
>
> So the banner carries its own check. Grep the epic directory for each forbidden term as a **standing step of every consistency sweep**, and adjudicate each hit individually: `prior_at_start`, `strictly narrower`, `never newly deletes`, `relocated to the cap`, `carve-out`, `compute the intersection`.
>
> **Every hit will need reading, not just counting** — this banner, TN-1's removal statement, the retired-formulations list and the History all legitimately contain the forbidden strings. That is `.claude/rules/doc-sweep.md`'s "error hiding behind a legitimate neighbouring use of the same token", and it is why the step is *grep then read each hit*, never *grep and check the count*.
>
> ### ⛔ THE LITERAL-PHRASE FORM OF THIS SWEEP IS DEFECTIVE. Use emphasis-tolerant patterns.
>
> **Markdown emphasis interpolated INSIDE a phrase silently defeats a literal grep.** Searching `adequate bound on pre-existing` returns nothing against text reading `adequate **bound** on pre-existing` — the `**` breaks the match mid-phrase. **These are not synonyms**, so `doc-sweep.md`'s synonym-expansion step does not cover them: they are *the same words with markup between them*, which is a gap that rule does not currently name.
>
> **Demonstrated on this epic**: a literal-phrase sweep for a defective sentence returned **2** hits repo-wide; the emphasis-normalized sweep returned **7**. The conclusion drawn from the literal sweep happened to be correct — but only because a second, broader alternation pattern was run and its hit was then READ. **Had the literal grep been the whole check, it would have shipped a false clean**, and this repo's prose emphasizes load-bearing terms as a matter of style, so the exposure is systematic rather than incidental.
>
> **The corrected method**: strip `**`/`__` before any literal-phrase sweep, or use patterns tolerant of interpolated markup (`carve.{0,4}out`, `compute the .{0,4}intersection`). Single words are safe; **multi-word phrases are not.**
>
> ### ⚠️ AND THE "15 vs 6" I REPORTED FOR IT WAS A CONFOUNDED COMPARISON. Partitioned; the method's cost here is at most 1 and plausibly 0.
>
> PM reported the tolerant sweep returning **15** against the earlier literal run's **6**, and characterized the gap as *"partly new text, partly method."* **Partitioning it — same discipline as the count discrepancy — shows the method contributed almost none of it.** The two runs used **different term lists**: the tolerant run added `carve-out` and `compute the intersection`, which the original never searched for.
>
> **The clean experiment is same-terms, tolerant-vs-literal**: the original five terms, run emphasis-tolerant, return **7** against the original **6** — a delta of **1**, against a file that has grown substantially since. **So "15 vs 6" measures TERM-LIST EXPANSION, not emphasis tolerance**, and the emphasis method's demonstrated cost on this epic is at most one hit and plausibly zero.
>
> **THE SINGLE DELTA HIT IS CLASSIFIED, AND THE ACTIONABLE CELL IS EMPTY. Demonstrated cost on this epic: ZERO.** The one line the tolerant run adds is TN-1's **prohibition statement** — *"`prior_at_start ∩ prior_now` is REMOVED ENTIRELY and must not appear in any form"* — which is **bottom-row on axis 2: the epic doing its job, and must not be touched.** No live assertion was missed. **State it flatly: the method was defective and cost nothing here.**
>
> **And the deflation goes one step further than that.** The missed line contains `prior_at_start` with **no emphasis inside the term**, so **emphasis cannot be the cause of the miss.** The emphasis method's demonstrated cost on this epic is not "at most one." **It is zero, and the one delta hit is not an instance of it either.**
>
> ### ⚠️ OPEN AND UNEXPLAINED — a literal grep missed a plain unemphasized string and nobody knows why
>
> **Do not let this close as "not the thing under investigation."** That is the right thing to say about *attribution* and the wrong place to stop: **an uncharacterized failure mode in a sweep method is worse than a characterized one**, and that phrasing is exactly what lets a loose thread read as resolved — this epic's own shape, in the sentence retiring it. **Recorded as a known-unknown in the method the final sweep will use.** Not a blocker, not a finding.
>
> **HYPOTHESIS, UNTESTED — flagged as such, settleable in one command by whoever runs the final sweep**: the emphasis-tolerant pattern may be **more permissive than its name** — a pattern admitting arbitrary markup between words also admits **line breaks, whitespace variation, and other interpolations.** If so the extra hit is the mitigation catching a **different member of the same class**, most plausibly the *phrase-wrapped-across-a-line-break* case, which would match a term containing `∩` and its surrounding spacing.
>
> **If the hypothesis holds, the arc's ending changes usefully**: not *"one hit, wrong cause"* but ***"one hit, caught by the fix, from a sibling failure mode the fix also covers"* — which would make the tolerant pattern MORE valuable than its name suggests, not less.** Do not write that ending until it is tested.
>
> ### ⚠️ TWO SEPARATE QUESTIONS WITH DIFFERENT ANSWERS — do not let the second deflate the first
>
> | Question | Answer | Evidence |
> |---|---|---|
> | **Is the emphasis hazard real and material?** | **YES, with a clean specimen** | SE's own `adequate bound` sweep: **2 literal vs 7 emphasis-normalized** — *same pattern, same paths, SINGLE VARIABLE.* A literal sweep found 2 of 7 real hits: **it missed more than two-thirds and reported the smaller number as the result.** |
> | **Did it cost THIS epic's banner sweep anything?** | **At most one, and on classification, zero** | the delta hit is a prohibition statement, and carries no emphasis inside the term |
>
> **Neither answer implies the other, and the natural write-up gets this wrong.** *"The method's cost was plausibly zero"* reads as deflating the hazard — which would be **over-correction: fixing an overstatement into a categorically weaker claim, in the same position the original defect occupied.** This epic has already shipped that shape once and named it.
>
> **The accurate pair, both true**: the emphasis hazard is demonstrated by a single-variable measurement to miss most of a phrase's real occurrences; **its cost to this particular sweep was zero.** *A fact about one run does not bear on a claim about the method* — the same axis discipline the cap characterization now carries.
>
> **And the SUPERSEDED call never rested on PM's number.** It rests on the mechanism — a method that **cannot** fail toward false-clean — plus SE's clean specimen. **The deflation costs it nothing.**
>
> **Recorded at this strength deliberately.** A finding about PM's own method failure had every incentive to keep the larger number, and three successive checks each shrank it: 15 → confounded → 7-vs-6 → **one hit, wrong cause, zero cost.** Then a fourth check caught the deflation going too far. **Both directions needed correcting, by different people.**
>
> **The hazard is still real and the SUPERSEDED call still stands** — a method that *cannot* fail in the false-clean direction is not the same as one that happened not to. But **"the method was defective and cost nothing here" is a different claim from what "15 vs 6" implies**, and shipping the larger number would have inflated a methodology finding about PM's own method failure. **Reported as 15 vs 6, the two causes are indistinguishable and the number is unusable in either direction** — it cannot show the gap had teeth, and it cannot show it was harmless.
>
> **STATUS: the last CLEAN result is SUPERSEDED and not citable** — produced by a method now known incapable of failing in one direction, which is not a weaker result but not a result. **Re-run with the full term list, emphasis-tolerant, and READ the hits individually at the final sweep pass.** ✅ **DONE 2026-07-25 — eleven terms, three normalizations (markup, hyphenation, case), every hit read and adjudicated. The result is recorded two subsections below; the top-left cell was NOT empty.**
>
> ### THE FINAL SWEEP ADJUDICATES ON TWO AXES, NOT ONE — and only one cell of four is actionable
>
> | | **existed at the earlier run** | **written since** |
> |---|---|---|
> | **live assertion** | ⚠️ **the only defect cell — and the only evidence the method gap had teeth** | not a method failure |
> | **finding-record / preservation copy / worked example** | **MUST NOT BE TOUCHED** | **MUST NOT BE TOUCHED** |
>
> **Everything in the bottom row is the epic doing its job.** Classify by **reading each hit's surrounding prose**, never by the match — the strings are identical across rows, so no pattern can separate them.
>
> **This is the "editing a retraction into agreement with the text it retracts" shape arriving as LIVE WORK rather than as a recorded lesson, and the sweep is the operation that would commit it.**
>
> **If the top-left cell comes back EMPTY, say so plainly**: the method was defective and cost nothing here. That is a real result, and a different claim from what any headline count implies.
>
> ### ✅ RUN 2026-07-25 — RESULT: THE TOP-LEFT CELL WAS **NOT** EMPTY
>
> **Twenty-six live assertions in this file carried superseded design**, plus four repairs each to `IDEA-186` and `IDEA-187` in both index row and file. **The bottom row was left untouched throughout** — every prohibition, preservation copy and retraction record in these Technical Notes survives unedited, including the WITHDRAWN fix-neutrality quotation and the three formulations that were wrong first.
>
> **Where they were is the transferable part: every single one was in a TECHNICAL NOTE or a tracking artifact, and not one was in an acceptance criterion.** The stories had been swept when the conjunction was dropped; **their upstream had not.** A reviewer checking the ACs — the natural place to look, and the place the banner's own warning pointed — would have found them clean and concluded the epic was consistent.
>
> **The two that would have cost implementation time rather than reading time**: TN-16 instructed an implementer to assert the exact inverse of story 03 AC-2, and precondition (c) stated the prohibited conjunction shape as a live precondition **four lines below precondition (a), which had been rescoped in the same edit pass.**
>
> **The banner's premise is therefore CONFIRMED, and more sharply than it was stated**: a prohibition list that relies on a reader noticing is not a prohibition — and the reader who most needs the mechanical sweep is the one who has *already* swept the obvious surface and found it clean.
>
> ### ⛔ AND THE TERM SWEEP HAS A STRUCTURAL BLIND SPOT IT CANNOT CLOSE — three more hits, found only after it finished
>
> **The Overview, Goal 1 and Success Criterion 3 all asserted the fix across "all three grains"** — false on roster, which loses its gate rather than gaining a corrected one, and which is the exact smoothing **story 05 AC-3 forbids in terms**. **None of the three contained a single one of the eleven swept terms**, so no amount of normalization could have reached them. They were found by targeting **structural positions** — a summary paragraph, a goal bullet, a numbered criterion — rather than by matching strings.
>
> **This is `doc-sweep.md`'s "a retired claim survives in forms carrying none of its tokens", and it lands hardest on the epic's own top matter.** The retired claim here is *uniformity across three grains*; what survived it is not a restatement but **a scope word in a structural field** — "all three", "each grain" — which reads as ordinary summary language and is the last thing anyone re-reads.
>
> **The consequent limit on what this sweep can claim**: a term sweep bounds the terms it searched, never the concept. The concept-level check is a **read of every structural field** — tables, file lists, bullet indexes, headings, goal and criterion lists, and characterising clauses — because *prose gets rewritten when the design changes; structural fields get updated only if someone remembers they exist.* Every top-left hit in this epic, on both the story-file sweep and this one, was in a structural position.
>
> ### ⛔ AND THE SWEEP MUST NOT STRIKE THE FINDING RECORD — doc-sweep's hazard in reverse [CR-2]
>
> `epic.md` contains the defective §6 phrase **twice**, and **neither is a live assertion**: one quotes §6's three unqualified uses and states why the first is false, the other uses the phrase as the worked example for the emphasis hazard. **A grep for the defective phrase now returns the finding's own obituary alongside any real defect, and the two are indistinguishable by match count.**
>
> `.claude/rules/doc-sweep.md` warns that a **retired claim survives in forms carrying none of its tokens.** Here the inverse bites: **a correctly recorded claim carries ALL of the tokens of the live defect.** A sweep tuned to find the defect will find its own record of finding it — and **striking those lines would delete the finding in the name of fixing it.**
>
> **The mitigation differs from the emphasis case and that is why it needs saying separately**: for emphasis you normalize before matching. **Here no normalization helps, because the strings are genuinely identical. Only reading separates them.**
>
> Getting here took four retracted positions, each correcting a real error. The convergence worked; what failed repeatedly was snapshotting it mid-flight. That history is kept in TN-5 because it is the epic's most transferable finding, not as hedging.
>
> ### Evidence labelling (standing convention for this epic)
>
> Because two experts have used the same word for different properties here, every load-bearing claim below is tagged. A reader six months out cannot recover this from consensus prose:
>
> - **[EXECUTED]** — someone ran it and observed the result.
> - **[DERIVED]** — reasoned from reading the code; not run.
> - **[PM-VERIFIED]** — PM resolved it against the repo first-hand rather than relaying it.
>
> The distinction has changed this epic's answer three times. It is not bookkeeping.

### TN-1 — The fix shape

Three parts. `old ∩ fresh` is **not recoverable** from post-upsert state (a fresh id present in the DB is indistinguishable between "was already there" and "we just wrote it"), so there is no in-seam-only fix.

**(a) A pre-upsert snapshot, captured by the caller, threaded in as a REQUIRED keyword parameter.** No default. This is squarely the evidence-parameter rule in `.claude/rules/python-style.md` — a default here would silently restore the exact bug — and matches the existing no-default precedent on the roster grain's pre-load input. The SQL stays in `src/db/reconcile_at_load.py` as public snapshot helpers the caller invokes at the right moment: **the caller owns *when*, the seam still owns the *SQL*.** That keeps the ordering coupling in the signature without spreading schema knowledge into the loaders.

> **⚠️ (a) describes the GAME and PLAYER-LINE grains. The ROSTER grain is an EXEMPTION, and saying so is not a carve-out in the TN-3 sense.** On roster the correctly-timed capture **already exists** in `scouting_loader.py` and is already threaded to the retire as `previously_rostered_ids`; there is no new caller-invoked snapshot helper to add, and story 03 states that the capture site and its ordering must not move. A reader applying (a) literally to roster would go looking for a helper to write and a loader line to add, and the epic's own guidance is that touching that site is how the deadlock returns.
>
> **⚠️ THIS BOX ONCE POSED TWO OPEN IMPLEMENTER DECISIONS FOR ROSTER. THE DESIGN HAS SINCE ANSWERED BOTH, AND LEAVING THEM OPEN WOULD SEND AN IMPLEMENTER LOOKING FOR A GATE THAT DOES NOT EXIST.** Both turned on there being a *corrected roster gate* to wire; **V1 has none.** Recorded rather than deleted, because a note written to defer a question outliving the question's answer is one of this epic's own codification candidates, and this box is a live specimen of it.
>
> 1. ~~**Does the corrected roster gate REUSE `previously_rostered_ids`, or take a new parameter?**~~ **MOOT — there is no corrected roster gate.** `previously_rostered_ids` continues to scope **the cap**, exactly as today, and nothing re-wires it. Story 03 AC-5 states this as a requirement: the capture site and its ordering do not move, and the only change on this grain is the floor's removal from the authority decision.
> 2. ~~**Is the CORRECTED half exempt-filtered?**~~ **NO LONGER A LIVE QUESTION — precondition (e) is MOOT under the shipped design, and the reason is structural rather than incidental.** The only filter on any grain's prior read is `exempt_player_ids`, which is **roster-only**; roster has **no snapshot-population gate** for a filtered-vs-unfiltered snapshot to skew, and the departure cap is provably invariant to it (`absent` derives from an already-exempt-filtered `prior_ids`, so `absent ∩ exempt = ∅` by construction). **The one grain with a filter has no gate; the two grains with a gate have no filter.** (e) carries its own wake-up triggers in TN-5 — read them there if either fires. *(This item previously reasoned about a "legacy half" and precondition (a)'s equality; there is no legacy half, and (a) has been rescoped.)*

**(b) ONE GATE PER GRAIN. The candidate population is unchanged.**

- **Candidate population = live prior, uniformly on all three grains.** Unchanged from today. **No intersection with the snapshot on any grain.**
- **Game and player-line**: the gate is the **corrected gate alone** — the floor ratio over the **pre-upsert snapshot** population. The legacy live-population gate is **replaced, not conjoined**.
- **Roster**: **no floor gate at all.** Its refusers are (i) an empty fresh payload and (ii) `MAX_ROSTER_DEPARTURES`.

**The shape is no longer uniform, and that is the design.** Uniformity was never the goal — it was a property the superseded shape happened to have, and citing it as a virtue is how the conjunction survived three reopenings.

**The discriminator still has to be stated, because it is what makes the non-uniformity principled rather than arbitrary.** `W ⊆ fresh` — everything the run writes into the delete scope comes from the fresh payload — holds on game and player-line and **fails on roster**, where the jersey backfill writes rows the fresh roster crawl never listed, by design. That one premise produces the gate shape, the deletion-neutrality guarantee (TN-5), and the grain where neutrality is deliberately false. A reader who sees only "the grains differ" will try to re-unify them, and that re-unification is the TN-3 deadlock.

**Added to the superseded-shapes list, and prohibited in every form:**

- the gate as `legacy AND corrected` on any grain — **the conjunction**, as a shape, as the basis of a neutrality proof, and as a value reaching `classify_absences`;
- *"the gate is one uniform shape across three grains"*;
- any AC phrased as *"the legacy gate permitted and the corrected gate refused"*.

**`prior_at_start ∩ prior_now` is REMOVED ENTIRELY and must not appear in any form.** Its original motivation was refuted by DE itself (the twin merge is keyed on the source event id captured *before* the canonical-id rebind, so the merged-away id is always in `fresh`, classifies PRESENT, and can never be a retire candidate), and with candidates now uniformly the live prior read the question is moot for both experts. If any reviewer proposes reinstating it, note that its comment must never cite E-261's twin merge — shipping a refuted causal claim inside a safety comment is the precise defect class this epic exists to close.

**(c) Vacuous-permit.** When the protected population is empty (`prior_count == 0`), return the fetch-ok value: nothing pre-existing is being protected, so the ratio question is vacuous. Required, or the empty-snapshot first load reaches the TN-3 deadlock by a second route. [EXECUTED, SE]

It does not touch the ratio — at `prior_count == 0` the floor is vacuously satisfied already, so the rule only bypasses the standalone empty-payload check, which there is protecting an empty population. The roster grain's real protection survives via its fetch-ok signal being derived from a non-empty fresh crawl.

**Vacuous-permit applies to the CORRECTED gate on GAME and PLAYER-LINE ONLY** — roster has no floor gate for it to apply to. It must not silently widen anything: `crawl_is_authoritative` is **shared** (roster still calls it for its fetch-ok signal, and the primitive's own test file exercises it directly), so the rule is exposed opt-in rather than applied unconditionally. That is precondition (a) in TN-5. *(This previously read "the legacy gate is untouched by it… keeps the legacy half genuinely equal to today's gate" — the superseded form, which presupposed the conjunction; TN-5's (a) records the rescoping.)*

**Contract impact:** the pure classifier is **unchanged** — it never sees the snapshot; only the two counts fed to the authority check change. Connection-in / no-commit / caller-owns-the-transaction is **unchanged** — the snapshot is one more read on the same connection inside the same transaction.

**Rejected alternatives**, recorded so they are not re-proposed:
- *Timestamp discrimination* (`created_at < run_start`) — converts a set-membership question into a wall-clock one; second-granularity ties, upserted rows keep their original timestamp, and it degrades silently rather than failing.
- *Subtract-the-just-written-ids* — algebraically equivalent but needs INSERT-vs-UPDATE discrimination that `changes()`/`rowcount` will not give under `ON CONFLICT DO UPDATE`; strictly more machinery with a new failure mode.
- *A loader-registered "ids I wrote this run" channel* — a second bookkeeping channel that drifts the moment a new write path forgets to register. The snapshot is correct regardless of which path wrote the row.
- This is **not** a "snapshot table". The no-snapshot-table rule concerns persisted history; this is an in-memory set living for one load.

### TN-2 — Capture anchors, forced per grain

The rule that generates the answer: **the anchor is immediately before the first write of this run that can touch this grain's delete-scope key, keyed on that same scope.**

| Grain | Delete scope | Anchor |
|---|---|---|
| player-line | **`(table, canonical game_id, perspective_team_id, team_id)`** — see the ⚠️ below; `table` is NOT optional | top of `GameLoader._upsert_game_and_stats` |
| game | `(team_id, season_id)` | top of `ScoutingLoader._load_team_core`, **after** the season-id derivation (it needs the derived season id) and above the boxscore load |
| roster | `(team_id, season_id)` | the existing pre-load capture — already correct, just not wired to the gate |

> ### ⚠️ THE PLAYER-LINE SCOPE KEY OMITTED `table`, AND THAT MEANS FOUR SNAPSHOT SETS PER GAME, NOT ONE
>
> Corrected 2026-07-25 after a clean read of `retire_absent_player_lines` [PM-VERIFIED]. The helper loops `for block in blocks: for label, table in _PLAYER_LINE_TABLES:` and reads its prior through `_prior_line_player_ids(conn, table, game_id, perspective_team_id, block.team_id)`. **Batting and pitching are separate diffs with separate health gates**, and each team block in the boxscore is gated independently — the function's own docstring says the results are *"keyed by `(table, team_id)` because each team block in the boxscore is gated independently; a single per-table key would collide between the two."*
>
> So an implementer must capture **one snapshot per `(table, team_block)` pair — two tables × two team blocks = four sets for a typical game**, not a single per-game set.
>
> **Why getting this wrong is worse than it sounds, and why it is not caught by the neutrality property.** A snapshot keyed without `table` unions the batting and pitching prior sets. That inflates every gate's denominator *and* its numerator with rows from the other table, so the ratio still looks plausible and the gate still refuses on catastrophic shrink — it just stops measuring the block it is gating. Per the congruence precondition in TN-5, a snapshot keyed more coarsely than the live read makes the gate **look healthier than it is**, which is this epic's original defect in a new key. Nothing crashes and no test that only counts surviving rows would notice.

**A whole-run pre-capture is not available for the player-line grain.** The prior set must be keyed on the *canonical* game id, and that id does not exist until mid-loop: the loader computes the canonical id, records the redirect, rebinds the summary's event id to it, and only then calls `_upsert_game_and_stats`. A whole-run capture would have to guess ids that do not yet exist. (Verified independently by PM, DE, and SE.)

The chosen anchor also keeps the coupling visible at both ends inside one function — unlike the roster pre-load capture, which travels ~85 lines and needed a long comment at each end to stay safe.

**First-ever load is safe — but NOT by short-circuiting, and the difference is a hazard.** ⚠️ An earlier version of this paragraph said the prior set is empty so the retire short-circuits with no gate computed. **That describes the abandoned snapshot-only design.** Under the settled design (TN-1(b)) the *candidate* population is the **live** prior read on every grain, which on a first-ever load holds the rows written moments earlier — so the pass runs, the corrected gate is computed and permitted vacuously, and **nothing is retired because every live prior id is present in `fresh`.**

Gating an early return on the **snapshot** instead would re-open the TN-3 deadlock: run 1 retires no churn, those rows enter run 2's snapshot, and the roster grain refuses permanently. That is precisely what TN-1(c)'s vacuous-permit exists to prevent — so this paragraph's original wording was a trap, not a nicety.

### TN-3 — The roster deadlock trap (reproduced; the shape is UNIFORM, only roster's data reaches it)

The roster grain **deliberately retires churn rows** — rows the boxscore jersey backfill re-created this run for a player cut mid-season. They are outside the snapshot by construction. Applying TN-1(b)'s game/player-line candidate rule uniformly makes them unretirable, and SE reproduced the resulting deadlock:

- First load (empty snapshot, 13 rostered + 3 backfill churn rows): a snapshot-gated pass refuses → the 3 churn rows survive.
- Next run they ARE in the snapshot → `absent ∩ previously = 3 > MAX_ROSTER_DEPARTURES` → **whole-set refusal, permanently.** Executed: run 2 refuses, `retired=[]`, and every subsequent run does the same.

That is the E-267 self-trapping deadlock restored — H2 back, the exact defect this grain exists to close.

**DE traced it further and it is worse than a deadlock: the churn player OSCILLATES.** [DERIVED, DE] Retired at the end of run N+1; outside the snapshot at the start of N+2 so excluded rather than retired; back inside the snapshot at N+3 so retired again — **and on every snapshot run they count as a GENUINE departure against the cap**, because the cap's narrowing catches them. One or two mid-season cuts who appear in a played boxscore merely burn cap slots. Three gives a whole-set refusal, after which all three sit in the snapshot permanently. That is precisely the self-trapping mode the cap's genuine-departure scoping was added to prevent, restored by the narrowing that was supposed to be a safety improvement.

Keeping roster's candidate population as the live read defuses it, and the vacuous-permit rule handles the first-load route. SE re-ran the ordinary case (13 roster, 13 fresh, 3 churn) and the first-load case: both retire exactly the 3 churn rows, unrefused — identical to today. [EXECUTED, SE]

**Frame the CANDIDATE POPULATION rule as uniform across the three grains, not as a roster carve-out** — and **name the discriminator, not just the uniformity.** [SETTLED, DE + SE both insist on it]

**⚠️ Name the object, because the bare word is prohibited and for a good reason.** TN-1(b) bans *"the gate is one uniform shape across three grains"* and states flatly that **the GATE shape is no longer uniform** — game and player-line run the corrected gate, roster runs none. What is uniform is the **candidate population** (live prior, all three grains, no intersection), which is this note's whole subject. Two different objects, one set of words; an unqualified "one uniform shape" here reads as the banned claim and invites exactly the re-unification the rest of this note exists to prevent.

The discriminator is `W ⊆ fresh`, where `W` is what this run writes into the grain's delete scope: **everything the run writes comes from the fresh payload — true on game and player-line, false on roster**, where the jersey backfill writes rows the fresh roster crawl never listed, by design. That is *why* the uniform shape degenerates to identical candidate behaviour on two grains and not the third.

Stating only "it is uniform" is not enough: a reader who knows the shape is uniform but not why it degenerates will re-unify the grains the first time roster looks like an outlier — and that re-unification is the deadlock above. Stating only "roster is special-cased" invites the same thing from the other direction.

The same `W ⊆ fresh` premise is the one DE proved deletion-neutrality from and later withdrew, having asserted it universally without checking the one grain that violates it. It is a good discriminator and was a bad universal; both facts belong here.

**Two independent derivations converged on this corrective, by DIFFERENT METHODS, neither knowing of the other:**

- **SE, from reproducing a failure** — a uniform narrowing produces a permanent whole-set refusal; executed.
- **SE-2, from breaking a premise** — `GameLoader._upsert_roster_jersey` writes `team_rosters` rows during the **boxscore** load for players absent from the fresh roster crawl, so this run's writes are not all in `fresh`. Its one-line cause is the one this epic uses throughout: **roster is the only grain with a run-local writer producing rows absent from `fresh`.**

The differing **method** is what makes the convergence load-bearing. Two agents reaching the same corrective by a shared method would be weaker evidence than two reaching it from opposite directions.

**An attribution error was caught here, and it is worth more than the correction.** Earlier drafts credited SE-2 with the 862-of-6560 sweep. **That sweep is SE's**; SE-2 never ran a combination sweep at all — its route was purely mechanistic. The convergence claim was **true while its stated support was wrong**, so a reader checking the citation would have found SE-2 ran no such sweep and could reasonably have discarded the whole convergence as inflated. **A true claim discarded because its stated support is false** — this epic's subject, appearing in the sentence that nominates itself as the strongest evidence. SE caught it only by recognising the numbers as its own.

### TN-4 — Staleness

- **Downward** (a captured row disappears before the retire) — **moot, and its motivating case was refuted.** It was thought real on the game grain via E-261's live twin-merge; DE read the redirect site and withdrew, because the merged-away id is always in `fresh` and so can never be a retire candidate. With the candidate population now uniformly the live prior read (TN-1(b)), there is no snapshot-derived candidate set for a vanished row to haunt. **Write no defense here** — a guard whose stated cause has been retracted is worse than no guard.
- **Upward** (rows appear that are not ours — a concurrent writer under WAL) — the snapshot misses them, so they cannot inflate the gate's protected population. [DERIVED, DE] Worth keeping as an independent property of the shape: **the current post-upsert read is fail-OPEN against concurrency; a pre-write capture is fail-safe.**

### TN-5 — Deletion-neutrality — STRUCTURAL, conditional on `W ⊆ fresh`

**Neutrality is not a blanket property and it is not a swept result. It is a two-line consequence of one premise — and the same premise predicts the grain where it fails.**

Let `P_pre` be the pre-upsert snapshot, `W` everything the run writes into the delete scope, `F` the fresh set, and **`k = |W \ P_pre|`** — the rows the run *adds*, however written. Where `W ⊆ F`:

```
P_post        = P_pre ∪ W
|P_post ∩ F|  = |P_pre ∩ F| + k        (W ⊆ F, so W\P_pre joins the numerator)
|P_post|      = |P_pre|     + k

corrected permits:  |P_pre ∩ F|      >= 0.5·|P_pre|
legacy LHS       =  |P_pre ∩ F| + k  >= 0.5·|P_pre| + k
                                      >= 0.5·(|P_pre| + k)  = legacy RHS     ∎
```

**Every added row contributes 1 to the legacy numerator and 1 to its denominator, and `1 ≥ 0.5·1`.** So the legacy gate permits whenever the corrected gate permits, at any sizes, with slack `0.5·k`. **The result is scale-free** — it holds at 2 games and at 200.

**State it in `k`, never in "new rows".** Insert-vs-update is never distinguished, which matters because TN-1 already rejected a design requiring exactly that discrimination (`changes()`/`rowcount` will not give it under `ON CONFLICT DO UPDATE`). A reader told "new rows" will think the proof needs a distinction it does not.

**All three gate conditions transfer, not only the ratio** — `crawl_is_authoritative` is a three-way AND:
- `fetch_ok` — the identical signal for both, unmodified;
- `fresh_count > 0` — corrected permitting implies `|P_pre ∩ F| > 0`; legacy's count is that plus `k`;
- the ratio — above.

| Grain | Neutrality | **Evidence tier** |
|---|---|---|
| **game** | holds | **Structural, given the named premise `W ⊆ fresh`** |
| **player-line** | holds | **Structural, given the same premise** |
| **roster** | **FALSE — deliberately** | **RULED**; and a **prediction of the same rule**, not an exception |

**The premise carries its own honest tier and must keep it.** `W ⊆ fresh` is a **NAMED PREMISE, not a structural guarantee** — on game it rests on one `INSERT INTO games` path whose ids come from `summary.event_id` (a fresh schedule id or a canonical redirect target, both in `fresh_ids`); on player-line the written ids *are* the block's fresh ids. It could not be falsified across 179 runtime invocations, **which is not proof.** Story 02's runtime assertion is its guard. The chain: **neutrality is proved from `W ⊆ fresh`; `W ⊆ fresh` is a named premise with a runtime guard; the sweeps are corroboration, not load-bearing.**

#### Scope the claim to DELETIONS, not to permits

State neutrality as *"never permits a **deletion** today's code refuses"* — never as *"permits whenever today permits."* The two gates **genuinely disagree** in one region: at `P_pre = ∅` **and** `W = ∅`, the corrected gate permits vacuously (TN-1(c)) while the legacy gate refuses on its `fresh_count > 0` check.

**The region is protected TWICE, and the two protections fail differently — so record both:**

1. **Empty candidate set.** **Executed: 32 such cases, and in all 32 `P_post = ∅` — 0 of 32 have anything to delete.** [EXECUTED, SE]
2. **Unreachable in the implementation.** All three helpers early-return on an empty *live* prior before any gate is computed — `retire_absent_games` (`if not prior_ids: return result`), `retire_absent_player_lines` (`if not prior_ids: continue`), `retire_departed_roster_players` (same, post-exempt-filter). `P_post = ∅` never reaches `crawl_is_authoritative` at all. [CR-2]

**Why both**: protection 1 survives a refactor that removes the early return; **protection 2 does not.** Recording only the unreachability would leave the claim resting on a guard someone may delete as redundant.

**And the reachable sub-case is fine on its own terms**: at `P_pre = ∅` with `W ≠ ∅` — the first-ever load — legacy's population is `W`, `|W ∩ F| = |W| >= 0.5·|W|`, and **both gates permit**. The disagreement is confined to the doubly-protected corner.

Recorded because a future reader checking *gates* rather than *deletions* will find a real disagreement and conclude something is broken. **Every AC binding this note inherits the deletion scoping, not the gate scoping.**

#### The roster grain — the premise is FALSE, and the failure follows from it

On roster `W ⊄ F`: the jersey backfill writes rows the fresh roster crawl never listed, so churn rows land in the legacy **denominator only** and make the legacy gate *stricter* than the corrected one. Executed [DE's construction; CR-2 re-derived independently]:

```
snapshot 10 · fresh 8 · churn 20  →  live prior 30
  today (legacy floor):  8 >= 15   REFUSES  → deletes 0
  V1  (no floor):                  PERMITS  → deletes 22, of which 2 are PRE-EXISTING
```

**This is the fix working as ruled, not a regression.** The operator ruled prefer-delete on this grain: today's alternative is not safety but a **permanent strand** — the same construction re-run leaves the roster wrong forever, while V1 converges on the only evidence available. The 2 pre-existing rows are bounded by `MAX_ROSTER_DEPARTURES` as a **per-invocation rate, not a total** (TN-19).

**This is why the statement is not a carve-out.** The property holds by construction everywhere it holds at all, and where it fails it fails for a stated structural reason: `W ⊄ F`. One premise produces the guarantee *and* its failure — which satisfies TN-5's original anti-carve-out requirement rather than breaking it.

**Scale, with its limit stated.** An exhaustive roster sweep found **862 neutrality violations across 6560 reachable combinations** (four parameters over `0..8`, less the degenerate case) for the **corrected-gate-only** shape. **That is a LOWER BOUND for V1, not V1's count** — so `violations(V1) ⊇ violations(corrected-only) ⊇ 862` within the swept space, and V1's exact figure is **unmeasured**. Do not report 862 as V1's number. *(This sweep was previously recorded as "historical, since the conjunction closed those cases." **The conjunction is gone, so those cases are open again** and the sweep is now the measurement of how roster neutrality fails.)*

**⚠️ AND THE RANGE IS A STATED LIMITATION, NOT A CITATION DETAIL — the same disclosure its game-grain neighbour carries** (added 2026-07-25; the neighbour had it and this did not). **`0..8` does not reach a 12-15 player roster**, which is this project's production roster size (CLAUDE.md, "Scope"). So the sweep's space stops short of production on the very grain whose sole remaining guard is a per-invocation cap over a production-sized roster. **Cite it with its range or not at all.** Note the direction differs from the neighbour's and both need saying: over there a **zero** count over a short range reads as strong evidence *because* it is zero; here a **non-zero lower bound** over a short range understates a failure count that production sizes would only increase. **A short range flatters a clean result and deflates a dirty one — the limitation binds in both directions.**

**State the MECHANISM, not "no floor is more permissive"** [CR-2's sharpening, adopted]. The relation holds because **V1 drops two conjuncts and adds none**:

```
corrected-only = fetch_ok ∧ (|P_pre ∩ F| > 0) ∧ (|P_pre ∩ F| >= 0.5·|P_pre|) ∧ cap
V1             = fetch_ok ∧ cap
```

Same `fetch_ok` (`bool(fresh)`), same cap, two conjuncts removed — so V1 cannot refuse where corrected-only permits. **A future edit that dropped the floor while tightening `fetch_ok` would falsify the relation**, which is why the mechanism is stated rather than the slogan.

**Tier: proved from three identity premises, of which only the candidate-set identity is falsifiable by a future edit.** The three, all verifiable by **reading** rather than running:

1. `fetch_ok` is the same signal in both designs — `bool(fresh)` on roster. *Design statement.*
2. The cap is the same — `roster_departure_guard(absent ∩ previously)`, untouched. *Design statement.*
3. **The candidate set is the same** — live prior under both, so `absent`, and hence the cap's input, are identical. **The only one a future edit could falsify**: if V1 ever changed the candidate population, the cap would see a different set and the subset relation would not transfer.

**⛔ DO NOT label this "derived but not executed", and do not try to execute it.** That phrasing implies execution is a missing rung it could be promoted by. It is not: the relation reduces to `A ∧ B ⟹ A`, which **cannot fail on any input**, so sweeping it would sample a tautology and return a zero that means nothing. **Not executing it is the correct disposition, not a gap.** The general boundary this instances: *execution is the stronger instrument for a claim about BEHAVIOUR and the weaker one for a claim that is DEDUCTIVE — the test being whether the claim could fail on some input; if not, there is nothing to sample.*

#### Verification tiers, stated separately so no sentence carries two

| Evidence | What it covers | Tier |
|---|---|---|
| The algebra above | all sizes, both grains | **proof**, conditional on `W ⊆ F` |
| Exhaustive set-structure execution — **0 violations in 55,728 combinations**: all `(P_pre, F, W)` with `W ⊆ F` over universes of 4, 5 and 6 elements [EXECUTED, SE] | set *structure*, not merely counts | **corroboration** |
| The pre-existing parameter sweep — **0 violations / 2197 combinations**, three parameters over `0..12` | counts only, and **`0..12` does not reach a 20–30 game season** | **corroboration; cite with its range or not at all** |
| The same execution with the premise **removed** (`W` unrestricted) — **296 violations at n=4, 2890 at n=5**; minimal counterexample `P_pre={0} F={0} W={1,2}` [EXECUTED, SE] | the roster grain | **the failure is reproducible, not hypothetical** |

**Each count carries its space deliberately** — a sweep result without its bounds is a quantity asserted over a range the author chose and then reported as though it were given, which is the seventh host recorded in the process findings and the one this codebase is most exposed to. **The `0..12` gap is a stated limitation, not a citation detail**: zero failures over a space that stops short of production reads as strong evidence *because* the count is zero.

#### The preconditions — THE ONES WE FOUND, not a closed set

**Stated as an open list deliberately, and the openness has already paid.** These are the properties a search along four axes turned up: what flows into the classifier (its *value* → (c); its *population* → (d) — mirror halves, and originally only one was written); the *scope* of a rule → (a); and the candidate/gate population split → (b). **A reviewer hunting for an (e) should look on an axis not in that list**, because these four are where we thought to look. **One did, and (e) below is the result** — a *filter* applied on the way in, which is none of what/which/scope/split. The invitation stands for (f).

**⚠️ TWO PROPERTIES SATISFY (a)-(d) AND ARE ENFORCED ELSEWHERE. The list is not the whole surface.**

- **Capture TIMING** — the snapshot must be taken before *every* writer into that grain's delete scope. **This is the original defect restated.** A snapshot captured one line too late satisfies (a)-(d) perfectly and reproduces the bug exactly. *Enforced by the capture anchors in TN-2 and in each story, NOT by this list.*
- **Scope-key CONGRUENCE** — the snapshot must be keyed identically to the live read (player-line by **`(table, game_id, perspective_team_id, team_id)`**; game and roster by `(team_id, season_id)`). A snapshot keyed without `team_id` would span both boxscore blocks, and one keyed without **`table`** would union the batting and pitching prior sets — either way inflating the protected population and making the gate **look healthier than it is**. **`table` was missing from this list and from TN-2 until 2026-07-25** [PM-VERIFIED against `retire_absent_player_lines`, which gates per `(block, table)` — four snapshot sets per game]. *Enforced by TN-2's scope table and its ⚠️ box.*

**Why naming them here is not optional:** this epic's most load-bearing property — the one it exists to fix — is absent from its own precondition list. That is not an error, since the capture anchors do enforce it. But a reader checking preconditions would not find it, and would reasonably infer the list is the whole surface. Combined with the open-list framing above, which actively invites a reviewer to hunt for an (e), handing them a list that silently excludes the central property is the worst available arrangement. One place, whole surface, with "enforced at X" against the two that live elsewhere.

The four below were left unstated in the three earlier formulations, which is how each was broken:

- **(a) RESCOPED, because there is no legacy gate to leave untouched.** Vacuous-permit applies to the **corrected gate on game and player-line**; **roster has no gate for it to apply to.** (The superseded form read *"applies ONLY to the corrected gate; the legacy gate is untouched"*, which presupposed the conjunction. The substance survives — vacuous-permit must not silently widen anything — but its object changed.)
- **(b)** The candidate population is the live prior set on all three grains, with no intersection.
- **(c) RESCOPED with (a), and for the same reason.** Exactly one gate VALUE reaches the classifier: on **game and player-line**, the **corrected gate's verdict**; on **roster**, none at all, because that grain computes no floor gate. **No second gate is composed at the call site.** (The superseded form read *"the conjunction"* — the exact shape TN-1(b) prohibits as a value reaching `classify_absences`. The requirement is unchanged: one value, not two. Story 01 AC-9a carries it.)
- **(d)** The classifier receives the **live** prior set as its prior ids on all three grains. The snapshot computes the corrected gate value ONLY, **never** the classification universe.
- **CHECKED ABSENCE, recorded because a checked absence is a result and silence is not** [software-engineer, 2026-07-25]: the `FLOOR_RATIO` / `MAX_ROSTER_DEPARTURES` **joint** coupling — where one constant's value determines the other's reach — **has no analogue on the game or player-line grains.** Both keep `FLOOR_RATIO`, but neither has a second constant jointly load-bearing with it: `MAX_GAME_RETIREMENTS` composes as an **independent narrowing** (`extra_guard` can only tighten), not as a joint property. **FINALISED — the roster design settled and the deferral is discharged**: the floor is removed, so the joint coupling **dissolves on roster** and there is no `FLOOR_RATIO` / `MAX_ROSTER_DEPARTURES` interaction left anywhere. The checked absence therefore stands unconditionally: no grain has two jointly load-bearing constants. *(This bullet previously read "cannot be finalised until the roster design is" — a note written to defer a question, still standing after the question was answered. Recorded rather than silently updated, because that shape is one of this epic's own codification candidates.)*
- **(e) POPULATION-FILTER congruence — the (e) the open-list framing invited, and it was duly found** [named by **CR-2**, 2026-07-25; its *direction* subsequently corrected by CR]. **The snapshot must carry the same FILTERS as the live read, not merely the same scope key.** On the roster grain today's prior set is **exempt-filtered**; a snapshot captured unfiltered contains exempt rows the live read does not.

  **THE REQUIREMENT IS CONGRUENCE, NOT A DIRECTION: filter both or filter neither, and SAY WHICH.**

  **⚠️ Three characterisations of the DIRECTION were wrong, and the sharpest available form names the one fact that would flip it** [DE, from a first-hand read of `_pending_collapse_player_ids`]:

  > **The direction is stable — never fail-open — UNLESS a single roster payload lists the same human twice.** Every collapse component contributes `k = 1` otherwise, and `2k > E` is then unreachable.

  **The mechanism**: with `E` = the total exempt ids and `k` = those present in `fresh`, the unfiltered snapshot permits where the filtered one refuses **iff `2k > E`**. Exempt = all members of executable collapse components, detected among co-rostered ids. A component is `n ≥ 2` ids for **one human**, and a roster payload normally lists each human **once** — so `k = 1` per component regardless of `n`, the other members being historical ids accumulated in `team_rosters` from earlier crawls and the jersey backfill. With `k = 1` and `E = n ≥ 2`, `2k ≤ E` always.

  The `k = 2` case therefore requires a **within-payload duplicate** — one payload listing the same human twice — which is a different phenomenon from the cross-payload id churn dedup exists for. **Whether that occurs is deliberately left unsettled: it is an API-shape question, not a code question**, and the congruence fix makes it moot. It is named here, not routed and not blocking.

  **Why this beats the "data-dependent" form it replaces**: it names the single fact a reader can go and check, instead of telling them the direction is unknowable. And it *strengthens* the requirement rather than weakening it — **a direction that is stable only under an unverified assumption about payload shape is exactly what should be made structurally impossible rather than reasoned about.** The unresolved API question is what justifies congruence, not what blocks it.

  ```
  E=1 k=1  -> permits   (the parameterization that produced "fail-open" — the INERT case)
  E=2 k=1  -> refuses   (canonical load-bearing pair)
  E=3 k=2  -> permits
  E=4 k=2  -> refuses
  ```

  **Wrong, and instructive because of who was wrong**: CR-2 characterised it as fail-open; SE executed a table supporting that, whose model set `E = k` — every exempt id in `fresh`, i.e. the case where the exemption *cannot matter at all*; and CR's own SHOULD-14 asserted the opposite direction. **Two reviewers each generalised from a single parameterization, inside a disagreement about exactly that failure.** A swept check (`E` 1-8 × `k` 0-E × `a` 0-8 × `n` 1-12) finds **zero** cases where unfiltered permits while filtered refuses under `2k ≤ E`.

  **⚠️ POLARITY — state the taxonomy explicitly wherever this is recorded, because leaving it implicit is how the inversion propagated:**

  | Direction | Effect | Concern class |
  |---|---|---|
  | **fail-CLOSED** — unfiltered snapshot enlarges the denominator, gate **stricter** | spurious *refusals* | **availability** |
  | **fail-OPEN** — gate **looser**, permits where it should refuse | wrong deletions | **safety** |

  An earlier version of this note called the **surviving** (fail-closed) direction a safety concern — **backwards, and in the direction most likely to be correct**, which misdirects both urgency and fix. **The inversion was inherited, not originated**: an upstream report described the asymmetry as *"fail-open, the dangerous one"*, and PM applied caution to that phrasing rather than checking it. **Caution about a word is not the same as checking it** — and note this is the fourth qualifier error of the session and the only one that drifted toward sounding *dangerous* rather than *safe*, committed while being deliberately careful about that exact adjective.

  **⚠️ AND (e) IS MOOT UNDER THE SHIPPED DESIGN — verified, not inferred** [CR, grep across `src/`]. `exempt_player_ids` appears in exactly two places: `retire_departed_roster_players` and its single caller in `scouting_loader.py`. **The dedup-exempt filter exists on the roster grain and nowhere else**; game and player-line apply no filter to their prior reads at all. Under V1 the roster grain has **no snapshot-population gate**, so there is no floor for a filtered-vs-unfiltered snapshot to skew — and the **cap is provably invariant to it**, because `_cap_on_genuine_departures` computes `absent & previously` where `absent` derives from the already-exempt-filtered `prior_ids`, so no exempt id can be in `absent` and whether `previously` is filtered is unobservable. **The one grain with a filter has no gate; the two grains with a gate have no filter.**

  **Recorded as CONDITIONAL rather than deleted or live, in the TN-15 shape — a stated non-goal carrying its own wake-up conditions**, which is more useful than either alternative because it tells the next author exactly when it fires:

  > **(e) Population-filter congruence.** Whatever filter is applied to a grain's live prior read must be applied to its snapshot.
  >
  > **CURRENTLY MOOT.** The only such filter (`exempt_player_ids`) is roster-only; the roster grain has no snapshot-population gate under the ruled design; and the departure cap is invariant **structurally, not empirically** — `absent` derives from an already-exempt-filtered `prior_ids`, so `absent ∩ exempt = ∅` by construction and filtering `previously` cannot change `absent & previously`, for **any** exempt set.
  >
  > **IT WAKES IF** (i) the roster grain regains a snapshot-population gate, or (ii) any grain adds a filter to its prior read.
  >
  > **IF EITHER TRIGGER FIRES, the fix is CONGRUENCE, not a direction: filter both or filter neither, and say which. Do not attempt to resolve the direction** — no fixture pins it. A test built from 2-member pairs shows one direction, a 3-member component shows the other, **and both authors will believe they characterised the behaviour.** (The direction is stable — never fail-open — *unless a single roster payload lists the same human twice*, which is an API-shape question deliberately left open because congruence makes it moot.)

  **Why the argument sits under the trigger and not in the body** [CR]: its job is to say what shape the fix must take *if* (e) wakes. In the body of a moot precondition the same sentences read as a live hazard — the currency problem in miniature. Conditional mood, and DE's within-payload-duplicate condition stays adjacent to the thing it conditions.

  **CR-2's finding survives intact** — it named the congruence correctly, and that is the substantive contribution. Only the direction falls, along with its supporting execution and CR's own opposite claim. The correction is narrower than it looks.

  **This is a genuinely new axis, not a restatement of (a)-(d).** Those four cover what flows into the classifier (its *value*, its *population*), the *scope* of the vacuous-permit rule, and the candidate/gate split. **(e) is about neither what nor which — it is a predicate applied on the way in**, and a snapshot can satisfy every one of (a)-(d), be keyed identically per the congruence property, and still fail it.

  **The open-list framing earned its keep**: the list was published as *"the ones we found, not a closed set"*, with an explicit invitation to hunt on an axis outside the four. A reviewer did, and found one. Keep the framing open — (f) is now more likely than it was, not less.

**(d) must be its own AC with the mechanism stated, and must not be folded into (a)-(c).** (c) governs the gate VALUE; (d) governs the POPULATION — mirror halves, and only one was originally written.

**Why (d) is structurally uncatchable downstream** [EXECUTED, SE, after DE raised it from reading]: the classifier returns a classification covering exactly the prior ids it is handed, so that argument IS the candidate universe. The natural slip — *"the corrected gate uses the snapshot, so pass the snapshot to the classifier"* — reads as obviously correct while writing it, and makes the candidate set `snapshot − fresh`. Executed: run 1 retires nothing where the correct form retires the 3 churn rows; run 2 those rows are now pre-existing, trip the departure cap, and are **permanently** unretirable. That is the TN-3 deadlock re-entered through the classifier rather than the gate.

And the reason it needs its own AC rather than trusting the neutrality property: **the slip only ever SHRINKS the candidate set, so it permits strictly fewer deletions and the neutrality absolute stays TRUE while the thing it guards breaks.** A second instance of this epic's own defect class, sitting inside the epic's own preconditions.

#### The requirement the blanket form was reaching for — and how the shipped design meets it WITHOUT being blanket

**⚠️ This subsection previously argued FOR a blanket property, in the words *"No carve-out, no per-grain premise, no reasoning for a reviewer to audit… a property holding by construction on every grain beats one holding with reasoning on two of three."* That is a description of the SUPERSEDED formulation and it contradicts this note's own opening sentence** — neutrality is *not* blanket, it holds on two grains, and it rests on exactly the per-grain premise that sentence disowned. Rescoped rather than struck, because the requirement underneath it is live and is what the shipped form must keep satisfying.

**The live requirement**: **an invariant with a documented exception is the exact shape that let this defect through** — the same-population invariant was true-as-written and false-in-effect, and four review layers read past it. A guarantee a reviewer must audit case-by-case is a guarantee that gets waved through.

**How the shipped form satisfies it without a blanket claim**: `W ⊆ F` is **one** premise, and it produces the guarantee *and* predicts the single grain where the guarantee fails. There is no exception to audit — the two-grain scope is a *consequence* of the premise, not a carve-out bolted onto it. That is the argument already made above under "This is why the statement is not a carve-out", and it is why the non-blanket form is not a weakening.

SE ran five attacks on the original blanket formulation before sending it, per the counterexample rule: DE's whole-set construction; vacuous-permit widening the legacy side; the roster exemption set inflating the protected denominator; cap populations; and an implementation slip using the corrected gate alone at some site. It survived all five, and the fifth became precondition (c). **Recorded because the attacks transfer** — four of the five bear on the shipped form unchanged; only the second names a half that no longer exists.

#### HISTORICAL — the conjunction, and why it was dropped

> **The two subsections that follow are HISTORY, not spec.** They record why the conjunction was adopted, and they are kept because the reasoning transfers — but **the conjunction does not ship on any grain** (TN-1(b)).
>
> **Its decisive argument was that DE's whole-set construction refuses under it, deleting 0. That is now precisely the behaviour the operator ruled AGAINST on roster.** The argument was sound and **the objective moved underneath it** — history, not error. Read them for the attack patterns, never as a description of the shipped gate.

##### Why the conjunction earned its place (both objections withdrawn on evidence)

- **SE's objection, withdrawn by SE.** Its cost table showed the conjunction refusing a genuine departure at 12 churn rows — but it had compared against the split-only *ideal*, not against today. Re-run against today, at 12 churn the legacy gate is `12 >= 0.5 * 25` → False, so **today's code already refuses that departure.** The conjunction preserves that behaviour rather than introducing it. [EXECUTED, SE; independently re-verified by DE]
- **DE's objection, withdrawn by DE.** Its form was that on roster the new deletions *are* the fix, so a blanket property buys a provable AC by weakening the correction. DE checked it and it did not survive: the conjunction still refuses on every motivating case (the audit's 9-stored/9-new churn, and DE's own 3-player roster case), and what it forgoes is **scope extension, not the fix** — shapes where today already refuses. Declining those is leaving today's behaviour alone, which is the right default for a tight-scope epic on a destructive path.
- **The decisive turn:** DE's own counterexample — 10 rostered, fresh crawl drops 2, 20 backfill-churn rows, where a split-only gate permits and deletes 22 rows including 2 pre-existing — evaluates under the conjunction as `legacy=False → refuse`, deleting 0. The same holds for **all 862** of the roster violations.

  **DE built that construction specifically to defeat the neutrality wording, and it refuses under the conjunction.** A design vindicated by the construction built to defeat it is in a **different evidentiary class** from one that merely survived review — which is what should stop a reviewer re-litigating the conjunction from first principles at CR.

##### The conjunction still delivered the fix in full — the objection's actual answer (HISTORICAL)

DE's objection was that the conjunction buys a provable AC by neutering the correction on the grain that needed it most. Executed against the discriminating fixtures (legacy permits, cap permits, corrected refuses): [EXECUTED, SE]

| Grain | Today | Under the conjunction |
|---|---|---|
| player-line | deletes 9, 0 of 9 survive | deletes 0, **9 of 9 survive** |
| game | retires 2, 0 of 2 survive | retires 0, **2 of 2 survive** |
| roster | deletes 2, 0 of 2 survive | deletes 0, **2 of 2 survive** |

The objection conflated two directions. **Over-deletion** (the gate permits where it should refuse) is the commissioned defect and is fixed on **all three grains, roster included**. **Under-deletion** (the gate refuses where it could retire) was never chartered. Only the second is affected, and only on roster.

**⚠️ "clutter identical to today" is STRUCK from that sentence — it was false and it was load-bearing.** The added refusals are *not* identical to today, and they are not merely clutter: refused rows persist into the next run's snapshot, where the cap counts them as genuine departures. The retracted roster-lock ruling above is what that compounds into. **The phrase did real damage by making the under-deletion direction sound like a cosmetic difference not worth checking**, which is precisely why the lock was never re-run against the conjunction. A dismissive adjective inside an otherwise careful comparison is the compressed form `.claude/rules/doc-sweep.md` warns about — one word carrying a whole claim.

And *"the grain that needed it most"* is **player-line, not roster**: roster's over-deletion is already backstopped by its departure cap, while player-line has **no cap at all** and destroys 9 live rows. On player-line the conjunction is a no-op. It constrains exactly one grain, in exactly the direction that is not the defect.

Two arguments both experts now regard as decisive:
- **The asymmetry.** Declining to improve roster cleanup is a SCOPE decision with no regression and a clean follow-up. Newly permitting deletion of pre-existing live rows is a SAFETY decision.
- **The guarantee does not depend on us being right.** It follows from the `AND` alone. Between these two experts a safety claim about this exact gate has been wrong three times. Choosing the formulation whose safety property does not depend on our own demonstrated error rate on this gate is not cosmetic provability.

#### The three formulations that were wrong first, and the check they earned

Kept because this is the epic's most transferable finding, not as hedging. Each was broken by the other expert:

1. *"The capture removes only ids this run wrote, all of which are in `fresh`"* — DE. False on roster (the jersey backfill writes out-of-`fresh` rows by design).
2. *"Candidate population unchanged, gate strictly narrower"* — DE. A gate that permits where today refuses is not narrower.
3. *"The fix never newly deletes a row that existed before the run"* — SE. The gate is a **whole-set** decision, so a permit releases in-snapshot candidates too.

**Every failure had the same shape**: a true-sounding absolute asserted uniformly across the three grains without checking the one grain whose writers violate its premise. DE made it twice, SE once. In each case the claim was retired only when someone **built the counterexample** rather than re-reading the argument.

**Standing review check, empirically earned** [DE, adopted]: *any AC phrased as an absolute about deletions gets a counterexample attempt before it ships.* This is the epic's own defect class, committed three times inside the acceptance criterion written to prevent it.

SE-2's checkable general form is the useful diagnostic for a future grain: neutral **iff** `W ⊆ F`, where `W` is what the run writes into the delete scope and `F` the fresh set the grain diffs against — with the mechanical test *enumerate every writer into the delete scope and confirm each draws from the same fresh payload; one writer with a different source falsifies it for that grain.*

**⚠️ This paragraph previously ended *"Under the conjunction the AC no longer depends on it"* — which is now exactly BACKWARDS and was the sharpest live inversion in the file.** With the conjunction gone, `W ⊆ F` is the **sole** support for deletion-neutrality: story 01 AC-8 and story 02 AC-7 both state the property holds *"by construction from the premise `W ⊆ fresh`… **not** from a conjunction and **not** from a sweep."* So the ACs depend on it **more** than they did, not less, and a future grain must run SE-2's mechanical test before claiming neutrality at all — there is no second conjunct left to carry it.

#### The roster lock, disposed in THREE BUCKETS — and (c) is NOT empty

**⛔ Do not write "the lock is gone."** One route is genuinely closed, one is pre-existing and untouched, and a third is an identified candidate whose reachability is unverified. The leap from *"the floor route is closed"* to *"no route exists"* requires a monotonicity argument that is **false** — see (c).

**(a) The F1 route — CLOSED. Established.** The counterexample that reopened this design required: the gate refuses → stale rows survive → enter the next snapshot → `absent ∩ previously` exceeds the cap → permanent. Its first step was a **floor refusal**, and **V1 has no floor**, so the step has no mechanism. Verified against code [CR-2]: the only whole-set refusers under V1 are the cap and the two upstream early returns (`if not fresh_player_ids`, `if exempt_player_ids is None`), **both predating this epic**. The superseded counterexample is preserved in the historical subsection above, where its `legacy | corrected` columns are legible as history.

**And it is EXECUTED, not only reasoned** [SE, scenario A at `R = 13`, four runs]: **today locks at `[27, 27, 27, 27]` — 27 stored rows against a 12-player truth — while V1 converges to `[12, 12, 12, 12]` on run 1 and holds.** That is the floor-lock route the History entry describes, and **it is this epic's clearest single demonstration that the fix does what it exists to do.**

**(b) The 3-or-more-departures lock — PRE-EXISTING and unchanged.** A crawl dropping **3+ genuine departures at once** gives `absent ∩ previously = 3 > 2` → whole-set refusal → rows stay → next snapshot, still absent → refuse again. **Permanent absent a crawl change, and identical before and after E-276.** [[IDEA-186]]'s truncated-crawl entry is the same lock by a longer path; this is its short form. **This must not read as fixed, and must not read as newly created.**

**Independently confirmed by execution** [SE, scenarios B (3 dropped at once) and C (5 dropped at once)]: **both lock byte-identically under both designs — `[13, 13, 13, 13]` either way.** SE's phrasing is the one to carry: ***"the lock is not gone; one route into it is."***

**(c) NOT ESTABLISHED EMPTY — and the strongest result in this bucket is a POSITIVE one, so read it first.**

> **Route B, executed** [SE] — `p` added by the backfill, the strongest available route because it lets `p` be absent in the run the pair forms:
>
> **V1 converges to the correct 2-row roster while today floor-locks at 11 rows against that same 2-player truth** — in the exact region the chain was supposed to live.
>
> **The construction built to find harm found the reverse.** *"No new lock route found"* is the smaller claim underneath this one; led with the negative, the section reads as a near-miss rather than as a demonstration.

> **The heading is deliberately weaker than the finding beneath it, and the ORDER is the point.** A reader who reads only the heading must get the **conservative** claim. The body below is stronger and genuinely earned — but it is also the version a summariser under pressure compresses to *"no lock route,"* and an untested residual is exactly what *"not established"* exists to say. **Conservative label on top means the compression is safe by default; the fuller finding is the reward for reading on.** This is the epic's own prohibition on collapsing buckets to a verdict, applied to a bucket. Both reviewers are on record accepting it: the conservative label was proposed by one, and the other stated it would not argue if the untested residual made that the honest heading. It does.
>
> **⚠️ SAY THIS PLAINLY, or the gap gets resolved in whichever direction suits a later reader: the heading is deliberately MORE CONSERVATIVE than the body, to bound how it compresses.** The body is **not** overclaiming — the mechanism was executed, the chain built including its ordering constraint, the window given a structural reason, and the whole thing survived an adversarial attack. **The heading wins on compression-safety, not on evidence.** Left unstated, the mismatch reads as an inconsistency rather than as a deliberate margin.

**No route FOUND — and the word is "not found," never "unreachable."** Two fixtures came back clean, which exhausts the routes we could build; that is weaker than a negative result and must not be written as one. The candidate mechanism is **confirmed REAL** — the exempt sets genuinely do desynchronise, verified at T2: today detects the pair `(p, q)`; **V1 has no `q` and detects nothing.** It is shown **INERT** by execution plus two structural obstacles.

> ### TWO INDEPENDENT OBSTACLES — recording them as one is how a future change reopens half of it and nobody notices
>
> They were **put to both reviewers as one mechanism reached from opposite directions, and both declined that framing.** They were right.
>
> | | Binds | Statement |
> |---|---|---|
> | **Obstacle 1** [CR-2] | the **DELETION** end | Exempt rows are **not deletion candidates**, so the pair must not be detected at the moment V1 deletes `q`. |
> | **Obstacle 2** [SE] | the **COUNTING** end | When the pair does form, the newly-arrived half contributes **0** to the cap, and the merge dissolves the pair before a later run. |
>
> **The falsifier test that proves they are separate, and it belongs in the text rather than in a review thread:** *make exempt rows deletable and **CR-2's obstacle falls while SE's holds**; defer the collapse across runs and **SE's falls while CR-2's holds**.* Two changes, each breaking exactly one.
>
> **Attribution, because an assertion and a proof of the same proposition are not the same contribution.** SE **asserted** its dichotomy was exhaustive. **CR-2 established WHY** — hunting the one shape with a lever on the cap, an exempt id **both absent from fresh AND in `previously`**, which SE's dichotomy does not cover because it is a half rostered in an **earlier** run. It collapses back: for `(p, q)` to be detected in run N both must be co-rostered, so if both were already rostered **the pair would have been detected and merged in the earlier run when the second arrived. A pair cannot sit undetected across runs.** **Only CR-2's version closes it.**
>
> Two extensions checked and closed with it: a **divergent second plan** (exempt members are not deletion candidates, so the pair survives the retire intact and the two plans cannot diverge for our pair), and **fork refusal** (verified in source — *"Only members of EXECUTABLE collapses are exempt"*).

**The residual is a COMPOUND, not a fourth open item in this bucket** [CR-2's classification]. A merge that **FAILS** rather than refuses would leave the pair co-rostered *and* exempt into a later run — but that is **neither (b) nor (c): it is conditioned on a pre-existing fault, to which V1 supplies a new lever.** Three reasons it is flagged rather than chased:

1. **The precondition is independently the worse defect** — a split identity the code itself says does not self-heal.
2. **Constructing it means injecting a persistent exception**, which tests the fault rather than the design.
3. **The cheaper closure is at the other end** — whether a repeated collapse failure is actually surfaced to an operator. That is an operator-visibility question, not a design one, and it is captured as an idea rather than folded in.

**And the structural finding stands INDEPENDENTLY of all of the above** — which is why it is recorded separately rather than as a preamble to the result: the only available argument for an empty (c) is **FALSE**. That argument is monotonicity — *V1's permit conditions are a subset of today's, so V1's roster stays a subset, so the cap trips no more often.* **It breaks because `exempt` is not an input; it is COMPUTED from the current roster.** `find_duplicate_players` self-joins `team_rosters` (`src/db/player_dedup.py`), so a pair is detected **only while both halves are co-rostered.** V1 deletes more rows, so V1 can have a **smaller** exempt set, and a row exempt today can be a live candidate under V1. **The bucket is therefore not closed by proof** — it is closed by exhaustion of the reachable cases with a stated reason, which is a different and weaker thing.

**Route A, executed** [SE] — `p` added by the roster crawl: V1 reaches a cap refusal, **but today locks at the same point via the floor.** No route V1 created. (Route B is the headline above.)

**One sub-path was closed outright**: a refused fork persisting across runs cannot cause this, because **fork members are explicitly not exempt**.

> ### WITHDRAWN — SE's proof that (c) was provably empty. Kept, not deleted.
>
> SE claimed *"(c) NEW under V1 — none, and this is provable"*, resting on `refusals(V1) ⊆ refusals(today)`. **That is the monotonicity argument this section records as false**, and SE withdrew it unqualified.
>
> **It is kept at SE's own request, and the reason is the point: it is this epic's own defect committed inside its own remediation, by a party cataloguing that defect.** A **single-evaluation lemma carried to a multi-run conclusion** — and corroborated by five executed scenarios **in which the mechanism under test was structurally inert**, so the corroboration confirmed the proof only on inputs where it was never in doubt.
>
> **Deleting it would leave the record showing only the defects other people made.** The corroboration's worthlessness is the transferable half: *executed scenarios that do not contain the mechanism under test are not evidence about it.*

**And the coupling resolves the OPPOSITE way from the concern.** Erosion does supply the desync — **but route B shows erosion's deletions driving V1 toward the truth while today accumulates 9 phantom rows.** Record it as real, and as running against the direction it was feared to run.

> **THE OPERATOR'S FOUNDING PREMISE WAS RE-EXAMINED AND HELD — stated explicitly, because an epic that quietly leaves its own founding ruling unexamined is worse than one that says "we looked."** The prefer-delete ruling rested on *a wrong delete self-heals, a wrong refuse compounds.* **Two routes were constructed and no counterexample was found: in both, the deletes converged and the refusals compounded — on today's side.**

**Two couplings that must not be assessed as independent:**

- **Erosion is not itself a lock** — verified to converge, since deleting more shrinks the live prior, which shrinks future `absent` and relieves cap pressure. **But it is the supply line for the candidate's step 2**: the divergence deletions that desynchronise the exempt set *are* erosion's deletions.
- **The band régime touches the same seam.** The fork residue is dedup-**merge**; the candidate is dedup-**detection**. Both hang off the `team_rosters` ↔ dedup coupling ([[IDEA-188]]).

**Recorded as failed attempts rather than as absence** [CR-2, attacked and could not break]: a lock from erosion alone (converges); a lock from a depleted roster meeting the cap (locks — but today locks on the same input via the floor, so it is **(b)**, not (c)).

**What was WITHDRAWN, kept so the retraction is not re-edited into agreement with the text it retracts:** *"Today's code and the conjunction behave byte-identically through it… it is therefore **pre-existing and fix-neutral** — E-276 neither causes nor worsens it."* That claim was retracted against the **conjunction**; the design has since changed underneath it, which is why the disposition above is by bucket rather than by verdict.

**The evidence that was over-read, because the lesson outlives the finding.** DE's five-run trace was real, executed and step-identical — **for the input it ran.** *"Both regimes, side by side, byte-identical"* reads as settling the question when it settles one entry route. A fix-neutrality claim is universally quantified; **a trace is a single input, and the quantifier attached itself silently.** Deletion-neutrality (TN-5) is a different property in a different direction and is untouched by any of this — conflating the two is how the original claim survived.

**The mechanism is the CAP, not the gate** [EXECUTED at loader tier, DE]. After the crawl recovers **both gates permit and `MAX_ROSTER_DEPARTURES` refuses**: the churn rows that survived the refused run are now in the snapshot, so the cap's genuine-departure narrowing counts them as departures. One bad crawl locks it, and real departures are blocked thereafter.

An earlier account attributed this to the corrected gate's ratio being self-reinforcing. **That account is refuted at loader tier**, not merely in simulation.

**A tier flag that was correct practice, now discharged.** When DE first produced the replacement mechanism it was gate-and-cap simulation, and DE flagged that tier itself rather than letting it inherit the credibility of the executed results beside it. This epic accordingly asserted *neither* version for a period. DE then re-ran it through the real `ScoutingLoader` and the flag is discharged. Recorded rather than deleted, because the flag was right and the record should show it being retired by evidence — that is the benign twin of the defect this epic exists to fix, and the doc-sweep rule's residue-that-no-longer-looks-like-a-claim in its harmless form.

#### Binding on the ACs (this is why TN-11 got stricter, not looser)

A test asserting "refused" proves nothing about **which** mechanism refused, and several produce "0 retired" independently: the gate, the boxscore-completeness signal, and — on game and roster — an absolute cap. The which-mechanism-refused requirement (TN-11) is therefore binding on **every** grain. Without it we ship a suite that goes green whether or not the fix works, which is how the defect being fixed survived four review layers.

**⚠️ The stated reason changed; the conclusion did not, and that is precisely why this was easy to miss.** This paragraph previously derived the requirement from *"two gates in the conjunction — the legacy gate could be firing"*, a justification the conjunction's removal deleted while leaving the conclusion correct. **A reviewer checking "is the which-mechanism requirement still binding?" gets yes and stops** — the same correct-conclusion-on-a-removed-support shape this epic catalogues, sitting in the note that binds the ACs. The requirement is if anything **stronger** under V1: on roster there is no gate at all, so `refused_by` is that grain's only structural discriminator.

### TN-6 — Transaction and locking verdict: the capture is free

- **No new lock, no lengthened write window.** Python's `sqlite3` in legacy isolation mode implicit-BEGINs only before DML, so a bare SELECT takes no write lock. The player-line capture moves a read a few statements earlier within one function; the game capture moves it to a point where no write transaction is open at all.
- **Per-boxscore commits are a non-issue for the captured set** — it is a plain Python set. Precedent: the roster pre-load capture already survives that exact loop.
- **But those commits are exactly why the game grain is broken.** The payload loader commits per game, so by the time the game reconcile runs, this run's new rows are not merely visible-uncommitted, they are **committed**. Worth stating plainly: on the game grain the pollution is not an artifact of reading inside an open transaction, and **no isolation-level change could fix it.**
- **No snapshot-isolation subtlety is relied on.** A connection always sees its own uncommitted writes; that IS the player-line defect, and reading earlier is the entire fix.
- **The `busy_timeout` / WAL cross-process invariant is untouched.** Both pipelines are in-memory crawl-to-load, fully fetched before the load is entered, so there is no network fetch anywhere between capture and retire.

### TN-7 — `not_final ∩ fresh`: FILE NOTHING (SE and SE-2 independently)

The asked shape is one line, but it is a **provable no-op on every input**, so cheapness is not the binding constraint — value is.

`not_final` is consulted at exactly one site in the module, and that site sits inside the `PRESENT` branch, where fresh-membership already holds by construction. So `game_id in (not_final & fresh)` ⟺ `game_id in not_final` for every id that reaches it. The intersection cannot change any evaluation. This is the same no-op E-270-05 deleted on the loader side, relocated.

Stronger, per SE-2: in the broken-invariant case the comment warns about (an id in `not_final` but NOT in `fresh`), the intersection would be **counterproductive** — it would strip the errant id out of `not_final`, and the id would still classify REMOVED and still be deletable. E-270-05's deletion was strictly correct, not merely safe.

A genuinely protective change exists in the neighbourhood (make the not-final refusal fire regardless of classification — a ~4-line move of an existing check). Both SE instances flagged it and neither argued for it: it is a different change from the one asked about, and specifying it under the handoff's rationale would ship a behaviour change under a description of something else. **Decision: file nothing.** If wanted later it is an idea, not this epic.

### TN-8 — Stated residual: partial id churn still deletes

After this fix, **partial** churn still hard-deletes: prior 9, fresh = 5 survivors + 4 brand-new ids gives `comparable 5 >= 4.5`, so the 4 churned lines go. That is genuinely the shape `bb data dedup-players` exists to merge.

Stated here so the epic's prose does not imply the grain now refuses all churn. Closing it needs a different instrument — a same-game name-prefix dedup-candidate check, not a ratio and not a cap → **IDEA-185**, not this epic.

### TN-9 — Prose the fix falsifies (cite by stable anchor, never line number)

Line citations rot, so every reference below is by symbol, function, or heading.

**A correction, recorded because it is a live specimen of this epic's own subject.** An earlier draft of this section claimed the originating handoff carried a stale *symbol* name for the roster pre-load input, and used that as the worked example. **That claim is FALSE.** PM inherited it, restated it confidently without resolving it, and it reached this document — inside an epic whose entire subject is an unverified claim about this module surviving four review layers.

All three roster symbols are real, live, and distinct [PM-VERIFIED, grep + read against `src/`]:

| Symbol | What it is |
|---|---|
| `pre_load_roster_ids` | the caller's local in `_load_team_core`, captured at the correct pre-upsert point |
| `previously_rostered_ids` | the keyword **parameter** of `retire_departed_roster_players`, bound at the call site as `previously_rostered_ids=pre_load_roster_ids`. No default, deliberately |
| `_prior_roster_player_ids` | the helper the retire calls to read its OWN gate prior set, at retire time — **this is the broken one** |

Keeping them distinct is load-bearing for the roster story: the correctly-captured value already reaches the departure cap through `previously_rostered_ids`, while the gate separately re-reads a polluted set through `_prior_roster_player_ids`. Collapse the three names and a wiring change becomes a redesign, or a real parameter gets edited away.

**The better specimen is the correction itself**, and it is the reason for this epic's executed-vs-derived labelling: the false claim originated with the team lead, was relayed to PM twice, and PM wrote it down. Neither party had resolved it against the repo. The rule this epic is about binds the people writing the epic.

| Site | Anchor | Story |
|---|---|---|
| `src/db/reconcile_at_load.py` | *(row merged 2026-07-25 into the more specific one below — it named the same file, same anchor, same story, and was a strict subset. **A duplicate row in an inventory three consumers treat as complete, corrected one revision earlier for being INCOMPLETE** — over- and under-enumeration of the same table, one round apart.)* | — |
| `src/db/reconcile_at_load.py` | `crawl_is_authoritative` docstring — the `fresh_count` **Args** entry and numbered condition 2. **ALREADY FALSE TODAY, PRE-FIX** — see below | 01 |
| `src/db/reconcile_at_load.py` | `retire_absent_player_lines` docstring, the "Health gate:" paragraph ending "an id churn should REFUSE rather than delete" | 01 |
| `src/db/reconcile_at_load.py` | `retire_absent_games`, the comment block at the `comparable` assignment — the "Two population mismatches were tried and rejected here" paragraph, specifically the bullet claiming newly-completed games "are not in prior either" | 02 |
| `src/db/reconcile_at_load.py` | `retire_absent_games`, the **"WHICH gate refused"** comment above the three-branch `transient_reason` — it enumerates **three** causes named apart *"because the remedies differ"*, and that enumeration stops being exhaustive once `refused_by` names the mechanisms explicitly and **`boxscores_incomplete` is separated from the cap** as its own member. **An accurate comment falsified by a change elsewhere, not by an error in it** — and the branch's single unlabelled `(fresh_comparable_count, prior_count, floor_ratio)` triple degrades with it, since it no longer says which population it reports. Found by reading the source during final triage, not from the handoff. [PM-VERIFIED] | 02 |
| `src/db/reconcile_at_load.py` | the **module docstring's result-type summary** (the `RosterRetireResult -- refused: bool + refusal_reason` line and its siblings) — the grain results gain the gate-outcome record of TN-11, so a summary listing only `refused` + a prose reason understates what each type carries | 01 |
| `src/db/reconcile_at_load.py` | **the module docstring's "Bias to refuse" paragraph** — its lettered conjunct list `(a) fetched OK, (b) returned a NON-EMPTY payload, (c) did not shrink catastrophically`, and the sentence *"`crawl_is_authoritative` computes that gate from **those three inputs**"*. **Falsified on TWO axes, and the second is the one that matters.** (i) The function now takes **four** parameters and conjunct **(b) is conditionally bypassed** by `permit_empty_prior`, so "those three inputs" is false and the list reads as unconditional when it is not. (ii) ⛔ **(b) also carries the SAME pre-existing payload-size falsehood that AC-11 exists to fix** — `fresh_count` is the **OVERLAP**, not a payload size, so "returned a NON-EMPTY payload" was already wrong before this epic touched anything. **AC-11 names `crawl_is_authoritative`'s docstring as that claim's home; the claim had TWO homes and AC-11 reaches one.** So AC-11 can be fully satisfied as written while its own target survives three paragraphs above it. *(Added 2026-07-26 on CR's round-1 routing; anchor resolved by PM against the source, not from the relayed line number. **This is the 10th mechanism — a verified repair verifies what it was pointed at** — arriving on the repair for a pre-existing falsehood.)*<br><br>**⛔ FOURTH SITE OF THE SAME CLAIM — `crawl_is_authoritative`'s OWN docstring, not the module's** *(added 2026-07-26, CR round 2, NSF-1)*: its header *"only when **ALL THREE** conditions hold"*, plus **condition 2's gloss** *"with `prior_count == 0` the ratio test is vacuously satisfied, so the check must stand alone."* Counterexample [CR; **PM-verified against the function body**]: `fetch_ok=True, fresh_count=0, prior_count=0, permit_empty_prior=True` returns **`True`** while condition 2 does **not** hold. ⚠️ **Condition 2's gloss is not incidentally stale — it is the EXACT sentence `permit_empty_prior` exists to override**, naming the same `prior_count == 0` input, and **the parameter's own Args entry documenting that override sits ~40 lines BELOW it in the same docstring.** One docstring now states opposite things about one input, and the correct statement is the newer one. *(Provenance named by CR as its own: its round-1 citation pointed at the MODULE docstring, SE fixed what it was pointed at, and the function's own docstring was never in the citation. **The 10th mechanism landing on the REVIEWER's citation rather than an implementer's repair — CR and SE have each now produced it within two rounds of naming it.**)* | 01 |
| `src/db/player_dedup.py` | **`_fold_name`'s docstring — the "SINGLE fold" enumeration**: *"the SINGLE fold shared by detection (`find_duplicate_players`, via a registered SQLite function) and the planner's terminal-name test (`_terminal_names`), so the two never diverge (E-253-08)."* Story 01's `_dedup_candidate_victims` imports `_fold_name` and is a **THIRD consumer**, so "shared by X and Y" and "the two never diverge" are both falsified. **Correct the enumeration; do NOT weaken the single-fold guarantee** — one fold with three consumers is still the property E-253-08 established, and the claim to fix is the *count*, not the invariant. ⚠️ **The only CROSS-FILE row in this table, and that is why it needs one**: nothing in `reconcile_at_load.py` prompts an editor to open `player_dedup.py`, and story 05's sweep is scoped to context-layer files plus this inventory. *(Added 2026-07-26; found by CR, anchor resolved by PM. **Enumerations drift downward-only — the site that ADDS a member is rarely the site that LISTS them**, and here they are not even the same file.)* | 01 |
| `src/db/reconcile_at_load.py` | `retire_departed_roster_players` docstring + the `_cap_on_genuine_departures` comment — the arrangement described as a cap layered *under* a floor, and the pre-load capture as feeding only the cap | 03 |
| `src/db/reconcile_at_load.py` | **`retire_departed_roster_players` docstring, the SEPARATE *"grid clutter, **never a corrupted stat**, which is what separates this grain from the game and player-line grains"* sentence.** V1 falsifies it **in the band régime** — a roster delete there can collapse a refused dedup fork into an executed merge and silently reassign a stat row ([[IDEA-188]]). **SCOPE IT, DO NOT DELETE IT**: it is true outside the band, and it is the sentence the operator's prefer-delete ruling rests on, so a reader must not be left believing it holds unconditionally. **Added to this table 2026-07-25** — see the note below. | 03 |
| `src/db/reconcile_at_load.py` | **THE FOURTH PRE-EXISTING FALSE CLAIM** — the `MAX_GAME_RETIREMENTS` comment asserting *"a refused retire self-heals, a wrong delete is irreversible"* **and citing the `MAX_ROSTER_DEPARTURES` cap as its precedent.** True for the game grain, **backwards for roster** (executed in both directions, independently confirmed by two agents). **SCOPE IT TO THE GAME GRAIN — DO NOT DELETE IT**; it is correct where it was written. DE's characterisation is the one to use: **this is the sentence that made bias-to-refuse feel *safe* on roster**, which is why the analogy went unchallenged by all four reviewers. *(A separately-raised roster-docstring citation was retracted by its author as a fusion of inference with a real quotation — **that retraction withdraws the fabricated clause, NOT this correction.** ⛔ **The retraction's closing clause — "The roster docstring is clean; this comment is not" — is now FALSE and is corrected here, 2026-07-25.** The roster docstring is **not** clean: it carries the *"grid clutter, never a corrupted stat"* sentence that V1 falsifies in the band régime, now its own row above. **The retraction was right about the fabricated clause and wrong in its generalization** — the verdict held and its closing scope claim did not, which is the reason-rots-independently-of-the-verdict shape `.claude/rules/tool-output-integrity.md` records for retractions, landing in a retraction.)* | 03 |
| `src/gamechanger/loaders/scouting_loader.py` | **`_reconcile_absent_games`' docstring — the "floor-ratio health gate" paragraph** *(added 2026-07-26, found by CR at story 02 review; prose corrected by SE within that story)*. Falsified **twice**: (i) *"derives its own narrower population inside the helper (`prior & fresh`) **rather than taking one from here**"* — the gate now takes its population from exactly here; (ii) *"newly-completed games … cannot be in the prior-loaded denominator"* — **the identical false claim as the `retire_absent_games` row above**, which SE fixed in the callee while this copy survived in the caller that describes it. ⚠️ **Two homes again — the third such pair in this epic.** | 02 |
| `.claude/rules/python-style.md` | **the missing-safety-signal rule's EXCLUSION paragraph** — its policy-hook carve-out reads *"A policy hook (`extra_guard: Callable | None = None`) ... may stay optional — absence there is a real intended configuration that disables nothing, **and the universal floor still applies underneath**."* ⛔ **That final clause is FALSIFIED on the roster grain by E-276-03**, which removes that grain's floor: with `extra_guard=None` there is nothing underneath at all. **EXECUTED, not reasoned** — 13 stored / 1 fresh, `extra_guard=None`: under V1 **12 classify REMOVED**; pre-V1 the floor made it **0**. The rule's justification for letting a policy hook stay optional therefore rests on a guarantee that no longer holds for one of three grains. **SCOPE IT, DO NOT DELETE IT** — the carve-out is still right for game and player-line, and the rule's EVIDENCE-vs-policy-hook distinction is untouched; only the "floor underneath" reassurance needs a per-grain qualifier. *(Found 2026-07-26 by story 03's binding contract-anchored identifier sweep — `extra_guard`/`exempt_player_ids`/`previously_rostered_ids`. **Nothing in `reconcile_at_load.py` prompts an editor to open a rules file**, and this site sits near no line story 03 changed, so no diff-anchored sweep of any width reaches it. Reported here rather than fixed in place, per AC-9.)* | 05 |
| `CLAUDE.md` | the **Canonical reconcile-at-load (retire-absent)** Architecture bullet, its "KNOWN DEFECT (2026-07-25 audit, fix in flight)" paragraph | 05 |
| `CLAUDE.md` | **A SECOND COPY of the falsified invariant, in the SAME bullet**: *"the health-gate ratio's numerator and denominator MUST be drawn from the same population."* Story 05 replaces only the KNOWN-DEFECT paragraph, so without this row the retired claim survives **two paragraphs from its own replacement**, in the file every session loads. It must take TN-10's necessary-but-not-sufficient wording, not merely be deleted. | 05 |
| `src/db/reconcile_at_load.py` | the module docstring's **"What IS uniform across all three, and must stay so"** paragraph — **specifically its same-population sentence**, the in-module twin of the CLAUDE.md copy above. **Correcting the sentence is the deliverable; the surrounding paragraph is the anchor for finding it.** Cited by anchor deliberately; a line number given for it in review has already rotted once. | 01 |
| `docs/admin/operations.md` | ⚠️ **THE ONLY OPERATOR-FACING SITE IN THIS TABLE, AND IT PROMISES THE OPPOSITE OF WHAT SHIPS** *(added 2026-07-26; found by claude-architect at story 05 by sweeping a tree **outside this table's declared reach, on its own initiative**)*. The "Reconcile-at-Load" section's **Bias to refuse** paragraph says the roster grain applies its cap *"**in addition to the shrink ratio**"* — **that ratio no longer exists on that grain** — and closes *"a transient failure, a postponed game, or a partial/degraded crawl **never causes data loss**."* **PM-VERIFIED verbatim.** That closing promise is now **FALSE precisely where the operator INVERTED the bias**: a truncated roster crawl can now delete, bounded only by `MAX_ROSTER_DEPARTURES`. **Route to docs-writer at closure.** | **closure (docs-writer)** |
| `.claude/agent-memory/claude-architect/epic-codifications.md` | the E-267 entry's T1/T2 bullet (pinned "same population" invariant) and the "STANDING CODIFICATION CHECK — verify CONCLUSIONS harder than STATEMENTS" paragraph (the "benign" ruling) | 05 |

**`crawl_is_authoritative`'s docstring is false BEFORE this epic changes anything** [PM-VERIFIED by clean read, originally found by DE]. Its `Args` entry documents `fresh_count` as *"Size of the fresh payload for this grain"*, and numbered condition 2 glosses it as *"an empty payload proves nothing"* — but **all three call sites pass `len(comparable)`, the overlap `prior & fresh`**, not a payload size. Verified at the three call sites in `retire_absent_games`, `retire_absent_player_lines`, and `retire_departed_roster_players`; each computes `comparable = set(prior_ids) & fresh` immediately above its call.

This is worth more than a prose fix, and it belongs in the epic's evidentiary record rather than only in its task list: it is a **pre-existing** false claim about the semantics of the very function whose semantics this epic corrects, found while fixing it. It is evidence FOR the epic's thesis rather than a consequence of it — the parameter has been documented as one thing and fed another since it was written, which is exactly the gap through which "the same population on both sides" stayed true-sounding while the gate measured something else.

**In-module prose corrections belong inside the grain story that changes the behaviour**, never in a separate prose story — same-commit rule per `.claude/rules/tool-output-integrity.md` ("prose you author is a claim"). Only the context-layer files are deferred to 05, and 05 is sequenced last so the prose describes what shipped.

#### ⛔ THIS TABLE SHIPPED KNOWN-INCOMPLETE, AND THE NOTE SAYING SO WAS NOT A FIX — corrected 2026-07-25 (second Codex pass)

**Story 03 AC-9(c) recorded a required prose site as *"NEW, and it is not in TN-9's table"* and then left it out of the table.** Meanwhile **two downstream consumers NAME this table as the complete inventory**: story 05's Technical Approach (*"The full list of prose sites, with stable anchors, is Technical Notes TN-9"*) and **Success Criterion 4** (*"No prose … still states the falsified claims (TN-9)"*). A third, **story 05 AC-6's residue sweep**, depends on it *implicitly* — it sweeps for "the falsified claims" without naming where they are enumerated. **The site is now a row above and the inventory is actually complete**; the alternative fix — narrowing the "full list" claim — was rejected because the consumers want an inventory, not a partial list.

**⛔ THE COUNT IN THIS PARAGRAPH WAS WRONG WHEN FIRST WRITTEN, AND IT WAS MINE.** It read *"three downstream consumers"* and named **story 05's own AC-1 chain** as the third. **AC-1, AC-2, AC-2b and AC-3 cite CLAUDE.md sites directly and never reference TN-9** — they are not consumers of this table at all. Caught by the edge-walk one round after I wrote it, **inside the note whose whole subject is a claim about another artifact that nobody resolved against that artifact.** Corrected to **two explicit plus one implicit**, with the implicit one marked as implicit rather than folded in to preserve a total of three — **restoring the count by re-labelling a weaker member is the move this epic has already named as inflation.**

**This is `.claude/rules/testing.md`'s *annotating a fixture limitation is not covering it*, arriving on a SPEC inventory rather than a test.** The rule's own words: *"an accurate scope note SUBSTITUTES for covering the region, because accuracy about a gap reads as management of it."* Story 03's note was accurate, honest, and load-bearing in the wrong direction — **it is precisely what made the omission feel handled.** A reader of story 03 saw a documented gap; a reader of story 05 saw a complete inventory; **and both were reading the same absent row.**

#### ⛔ THIRD REACTIVE EXTENSION — THE DEFECT IS THIS TABLE'S CONSTRUCTION METHOD, NOT ITS CONTENTS. **Binding on story 03, which is next and edits the same file.**

**Three consecutive stories have now had a TN-9-scoped sweep that was complete against the table while the table was incomplete** (story 01: the module docstring, then NSF-1; story 02: `scouting_loader.py`). **Every extension came from a reviewer, never from the sweep.** A fourth patch to the contents would leave the generator intact, so this states the generator.

**How the table was built, and why it under-collects.** Rows were found by **reading the site of the change** — the paragraph stating the claim being fixed. That finds prose *adjacent to changed lines*. **But contract prose is scattered by design**: the same contract is described at module level, at function level, in the callee, and in the caller, and a change touches only one of them. **All four misses were prose about a contract the fix changed, sitting where the fix does not reach**:

| Miss | Where it hid |
|---|---|
| module docstring's "Bias to refuse" | same file, **different scope level** (module vs function) |
| `crawl_is_authoritative`'s own header + condition-2 gloss | same file, same function, **a different paragraph from the one cited** |
| `player_dedup.py::_fold_name` | **a CALLEE**, newly acquiring a third consumer |
| `scouting_loader.py::_reconcile_absent_games` | **the CALLER**, describing the callee's contract |

> ### THE CONSTRUCTION RULE, and it is mechanical
> **For every CONTRACT the fix changes, grep the IDENTIFIERS across the repo and inspect each hit's prose — do not read the diff and collect what is near it.** Identifiers: the changed function name, each changed or added parameter name, and any constant whose meaning moves.
>
> **⛔ THE STOPPING RULE IS PART OF THE RULE — "whose contract this story changes" INCLUDES "whose CALLER SET this story changes."** *(Added 2026-07-26 by SE, at story 03 round 1, against the rule that binds it.)* A story that **removes a caller** changes that contract's **reach** without touching a line of it. So a sweep can hold the right identifier, grep it correctly, and still **discard every hit** on the ground that *"this story does not edit that function."* **All four of story 03's missed sites carried `crawl_is_authoritative` — which WAS in the swept identifier set.** The scope was right; the **termination condition** was wrong, and that is a different defect from the diff-versus-contract anchoring fixed above.
>
> **Concretely: never discard a hit because the story does not edit its subject.** Read each hit's prose against what the story changes **anywhere** — including caller removal, sole-guard promotion, and any change to which configurations of a function are reachable.
>
> **⛔ FIFTH INCOMPLETENESS, AND IT IS A GAP IN THIS TABLE'S REACH RATHER THAN ITS CONTENTS — `docs/` WAS NEVER IN SCOPE AT ALL** *(2026-07-26, story 05)*. Every row above lives in `src/`, `CLAUDE.md` or `.claude/`. **No sweep in this epic covered `docs/`, and Success Criterion 4 would have PASSED with an operator-facing runbook promising the opposite of what ships.** claude-architect found it by sweeping that tree **voluntarily, outside the declared reach.**
>
> **So the rule gains a scope clause: the identifier sweep runs over EVERY tree that describes the contract — `src/`, `tests/`, `docs/`, `CLAUDE.md`, `.claude/`, `epics/`, `.project/` — not the trees the change touches.** The `docs/` tree is the highest-consequence of these and was the last to be swept, because **it is the only one an operator reads.**

**Verified against all four misses [PM]: an identifier grep finds every one of them.** `crawl_is_authoritative` appears in the module docstring's sentence and in its own header; `_fold_name` appears in its docstring; `prior_snapshot` sits in the method whose docstring was wrong. **Not one required insight — only a grep nobody ran.**

**For story 03 specifically**: it changes `retire_departed_roster_players` and `previously_rostered_ids`, and it edits `scouting_loader.py`. **Grep both identifiers repo-wide before declaring AC-9 complete**, and add whatever the grep finds to this table rather than fixing it silently — the table is what Success Criterion 4 and story 05 consume.

**Why this is stated here rather than filed as an idea**: the next consumer of this table is three days away at most, and a construction defect that is understood but unwritten is the shape this epic exists to stop.

#### Second incompleteness, found by CR at story 01 round 1 — and the ADMISSION CRITERION this table had never written down

**Two rows added 2026-07-26** (module docstring "Bias to refuse"; `player_dedup.py::_fold_name`). CR surfaced **five** candidate sites and explicitly left the inventory-scope call to PM. **Three were declined, and the criterion that separates them is now stated here rather than re-derived each time:**

> **This table inventories PRE-EXISTING prose that this epic's change makes FALSE.** It is not a defect list for prose the epic newly WRITES — that is code review, and it reaches the author directly. A row earns its place when nothing in the changed file would prompt an editor to find it.

| CR's site | Verdict | Why |
|---|---|---|
| module docstring "Bias to refuse" | **ADMITTED** | Pre-existing; falsified on two axes; carries a second copy of AC-11's own target |
| `player_dedup.py::_fold_name` "SINGLE fold" | **ADMITTED** | Pre-existing; falsified by story 01 adding a third consumer; **cross-file**, so no editor of `reconcile_at_load.py` is prompted to it |
| `_player_line_refused_by`'s *"mapped to the conjunct … in the order the gate evaluates them"* | **DECLINED** | **Not falsified.** It omits the vacuous-permit branch, but that branch cannot produce a refusal, so this function is never called on it. **Partial ≠ false**, and admitting partial descriptions makes this table unboundable. Fine as a code-quality tightening |
| `_dedup_candidate_victims` *"mirrors `find_duplicate_players`"* | **DECLINED** | Prose story 01 **newly wrote**. If it diverges it is a review finding against its author, who is already fixing it — routing it here would launder a code-review finding into a spec obligation |
| the local `_fold_name` import | **DECLINED** | Not prose at all; a code-structure question for CR and SE |

**Why the boundary is drawn at pre-existing rather than "anything false"**: a row here becomes an obligation measured by **Success Criterion 4** and swept by **story 05**, both of which run *after* the author has gone. New prose does not need that machinery — its author is present and under review. **Putting a fresh review finding in a standing inventory costs the finding its urgency and costs the inventory its meaning.**

**⚠️ And a method note, because it decided two of the five.** CR cited all five by **line number**, which the heading of this section forbids. **Two of the five did not resolve** — the numbers landed on unrelated code, because SE was editing that file during the review round. **Every site above was re-anchored by CONTENT before it was ruled on**, and had the numbers been trusted, the two admitted rows would have been filed against the wrong code. *This is the section's own "cite by stable anchor, never line number" rule earning its keep inside the round that extends the section.*

**The sharper half: an annotation that names a gap is INVISIBLE to the consumer that depends on the gap being closed.** Story 05 never reads story 03. **A note only reaches whoever reads the file it is in** — so a gap annotated in one artifact and depended upon in another is not merely uncovered, it is *unreachable*. **Annotate where the dependency is, or close the gap.** This epic could not have found it by any sweep it ran: nothing was stale and nothing was contradictory in either file alone — the defect existed only in the relation between them.

### TN-10 — The corrected invariant (necessary-but-not-sufficient is the transferable part)

The stated invariant is **true of the broken code**: both sides of the ratio *are* drawn from the same set — the polluted one. It holds while the gate measures `|fresh| >= |stale|` and is not a health gate at all. That is why this survived four review layers, and why a prose-only correction is insufficient: without a temporal clause the same defect passes review again.

The replacement must carry **both** the temporal clause and the sufficiency note:

> …and the health-gate population. On the grains that have a gate, it computes over the set already loaded **as of the start of this load, captured BEFORE any of this run's writes to that grain's delete scope** — supplied by the caller, because only the caller knows *when*. (**The roster grain has no floor gate at all**; its refusers are an empty fresh payload and the departure cap.)
>
> The numerator `prior & fresh` and the denominator `prior` are drawn from **that same pre-upsert population**. **Same-population-on-both-sides is necessary but NOT sufficient** — a set read *after* the fresh upsert satisfies it while measuring `|fresh| >= |stale|`, which is not a health gate at all. **The temporal clause is the load-bearing half**: it is what the satisfied-but-meaningless form lacked, and it is why the same-population sentence alone would pass this defect again.

**⚠️ This wording was itself a defect and is corrected here.** The previous version said `prior_ids` is the pre-load set *in EVERY grain* and that *"this module never reads its own prior set for the gate"* — **both false under the conjunction**, since the legacy half reads the live set by design and precondition (a) requires it. It was written before the conjunction settled and never re-read against (a).

The damage it would have done is the reason to record it rather than quietly fix it: story 01 and story 05 bind this wording **verbatim** into the module docstring and **CLAUDE.md** — three sentences below a CLAUDE.md line stating the read returns `old ∪ fresh`, **which stays TRUE post-fix for the live read.** Applying it would have shipped a self-contradicting paragraph into the file every session loads, inside the epic whose subject is exactly that. **The eighth mechanism at the author's own desk: PM wrote it, so nobody re-derived it, including PM.**

The clause fixes this instance; **the sufficiency note is what stops a reviewer concluding "same population, therefore sound" next time.** It belongs in the CLAUDE.md replacement as well as in the module docstring.

### TN-11 — The wrong-reason trap. Binding on ALL THREE grains, not just game. [SETTLED under every candidate gate shape]

Several independent mechanisms each produce "0 retired": the health gate (which may itself be two gates), the boxscore-completeness signal, and — on game and roster — an absolute cap. **A refusal assertion therefore proves nothing about which mechanism refused.** A suite that goes green whether or not the fix works is the caps-masking failure arriving by a new route, and a green suite over a live defect is precisely how this epic's ancestor shipped.

#### The trap that would have shipped: the audit's own roster shape does NOT discriminate

**The 9-stored / 9-brand-new shape works at the player-line grain and FAILS at the roster grain.** [EXECUTED, SE] At roster, `absent ∩ previously` = 9, which exceeds `MAX_ROSTER_DEPARTURES`, so **the cap refuses too** — a post-fix "refused" assertion is satisfied by the cap alone, whether or not the fix works.

This matters beyond the one fixture: the shape came from the originating handoff's acceptance criteria. Inheriting it at the roster grain would have shipped a regression test that cannot fail, inside the epic written to fix a defect that survived because nothing could catch it.

#### The three discriminating fixtures

Each is constructed so the legacy gate **and** the cap both PERMIT, leaving the corrected gate as the only possible refuser, and each **deletes today**. [EXECUTED, SE; the roster fixture independently arrived at by DE]

| Grain | Fixture | Behaviour today | today | cap | gate |
|---|---|---|---|---|---|
| **roster** | 2 stored ids, 2 brand-new fresh ids | deletes both | permits | permits (2 ≤ cap) | **n/a — no gate under V1** |
| game | 2 prior loaded, fresh schedule = 2 brand-new completed games | retires both | permits | permits (2 ≤ cap) | refuses |
| player-line | 9 stored, 9 brand-new | retires 9 | permits | n/a (no cap on this grain) | refuses |

**⚠️ The roster row is RELABELLED, not deleted, and its meaning has changed.** Roster has **no gate** under V1, so this fixture no longer discriminates a gate — **it discriminates the REVERSAL**: today and V1 both delete both rows, identically. It is therefore a *characterization* test on that grain (story 03 AC-8(a)), not a discriminating one. **Story 03's discriminating fixture is a different shape** — a 3-row stored roster with 1 survivor, where today's floor refuses and V1 retires 2. Do not carry this row's sizing over to it.

The game and player-line sizings remain load-bearing and easy to get wrong — in particular, do not carry 9-vs-9 to the roster grain, where the cap refuses regardless.

**The RULE that generates the roster sizing, so a fourth fixture is derivable rather than guessed.** Write `a` for the snapshot rows still present in the fresh crawl (survivors) and `b` for the snapshot rows absent from it. The two permitting mechanisms and the one refusing mechanism pin the size directly:

> **`a < b ≤ MAX_ROSTER_DEPARTURES` (= 2), therefore the pre-load roster `a + b ≤ 3`.**
>
> `b ≤ 2` is what keeps the **cap** permitting. `a < b` is what makes the **corrected gate** refuse — its floor is `a >= 0.5(a + b)`, i.e. `a >= b`. Together they admit exactly `(a,b) ∈ {(0,1), (0,2), (1,2)}`, which is the three-shape bound in the Background restated as a construction recipe. Every discriminating roster fixture must additionally carry **at least one newly-rostered id in the fresh crawl** — that is what makes the live set differ from the snapshot and is the condition the boundary sentence's over-deletion scope names.

**And the CHURN COUNT the fixture needs falls out of the same arithmetic** [DERIVED, PM — re-derived rather than relayed, and it confirms the figure story 03 already carried]. Write `n` for the newly-rostered ids in the fresh crawl. The legacy gate must **permit**, over the live population `a + b + n` with overlap `a + n`:

| Shape | Legacy permits iff | Minimum `n` |
|---|---|---|
| `(0,1)` | `n >= 0.5(1 + n)` | **1** |
| `(0,2)` | `n >= 0.5(2 + n)` | **2** |
| `(1,2)` | `1 + n >= 0.5(3 + n)` | **1** |

That is the arithmetic reason the verified fixture is **2-vs-2 and not 2-vs-1**: `(0,2)` is the one shape needing two new ids, and a 2-vs-1 build of it makes **today's floor** refuse — producing a passing test that characterizes nothing, since story 03 AC-8(a) requires this fixture to behave **identically under today's code and under V1**, which needs today's floor to permit. *(This sentence previously read "since AC-2 requires the legacy gate to have permitted" — the AC phrasing TN-1(b)'s banner declares stale, against an AC number that never carried it.)*

**Stated as a rule and not as a third worked example, deliberately.** Three examples do not make a fourth derivable; this does. An implementer who needs a variant — a different `(a,b)`, a different churn count, a case built to fail — can construct it and check it against the two lines above, instead of perturbing a given fixture and hoping the discrimination survives.

#### Assertion targets, to be written into ACs specifically rather than as a general instruction

A general "assert which gate fired" instruction is what lets a wrong-reason pass slip through. Each grain's discriminating test asserts:

- **positive**: `refused_by` names the mechanism that refused — and on the game grain, `.refusals` is checked as well, since per-id protections live there and neither field alone closes the trap;
- **positive**: the protected count equals the **snapshot** size, not the live size (the audit's numeric tell: pre-fix the WARN reads a prior count of 18 where the true pre-run population is 9). **On player-line this is the keyed entry for the block and table under test, not a scalar** — see the keying rule above;
- **negative**: zero rows deleted **and** the specific prior ids still present;
- **mechanism-completed** — ⚠️ **and the obvious form of this is VACUOUS on two of three grains:**

  > **`LoadResult.errors == 0` is valid completion evidence on the PLAYER-LINE grain ONLY** — it is the only wrapper that counts (`game_loader.py`, `result.errors += ...`). On **game** and **roster** the wrappers swallow **without** counting and return `None`, so **a reconcile that RAISED still leaves `errors == 0` and satisfies the assertion.** There, completion MUST be certified by a call-through spy (TN-17) installed on the **helper** — `retire_absent_games` / `retire_departed_roster_players` — **never on the swallowing wrapper**, **and the assertion MUST be that the recorded value IS a result object, not merely that the list is non-empty.**

  **Why the install point is load-bearing, and why this is NOT redundant with TN-17.** TN-17 already requires *"the positive assertion that the spy captured something"* — but that was designed against a spy that **never fires** (wrong patch module → `results == []` → caught). It does **not** cover a wrapper-level spy, which **does** fire: the helper raises, the wrapper catches and returns `None` normally, the spy appends `None`, and a non-empty list **reads as a completion**. So TN-17's existing check **passes on the exact failure it was written to catch**, in a shape its author did not have. **The wrapper is the natural install point precisely because it is the method the ACs name** — which is what makes this worth stating rather than assuming. TN-17's table happens to point at the right module for game and roster (function-local imports mean patching `reconcile_at_load` reaches the helper), but **nothing states the reason, so the table's correctness is currently accidental**; this clause is what makes it deliberate.

  **State it as "only player-line counts," NEVER as "dedup deviates from a norm."** The second reading implies four sites drifted from a standard. The truth is the reverse: **swallow-with-count is the single exception, and it happens to be the one grain `.claude/rules/testing.md` documents.** The standard was never general.

#### Expose the gate outcome structurally, not in prose [SE's request, adopted]

Tests must assert on a small record carried by each result dataclass (which gates ran, what each decided, the protected counts) — **not** on WARN strings. There is precedent in the module: the roster result type already carries its count fields specifically so tests can assert the WARN payload structurally. A test that greps log text is a test that passes when someone rewords the message.

**This AC is justified by an instrument that actually failed this way during planning, not by argument alone.** DE's own loader probe derived "was anything retired?" by grepping for the WARNING-level hard-deleted line. On a first load the retire takes the **INFO-level** recurring-churn branch instead, so the probe read `retired=False` on a run that had retired all three rows — a confident wrong answer. DE caught it only by checking DB state, and disclosed it on the grounds that *"a log-derived assertion that silently missed the INFO path is exactly the kind of instrument defect I am about to go looking for in someone else's story."*

Note the shape: not a reworded message, but **a second log level the assertion never looked at.** An AC justified by a reasoned argument is weaker than one justified by an instrument that failed that exact way while the epic was being written, and the difference is between an implementer following the rule and an implementer understanding why it exists. Story 03's AC-4 carries the concrete case.

**⚠️ AND ON THE ROSTER GRAIN THE TRAP IS PRE-INSTALLED IN THE FILE THE IMPLEMENTER WILL EXTEND.** `tests/test_roster_grain_reconcile.py` carries its own `_roster_warnings()` helper, which filters `r.levelno == logging.WARNING`. A test reusing it to check the roster churn retire **silently misses the retire entirely**, because the first-load churn path emits at INFO — the same failure DE's probe committed, in the form an implementer is most likely to reach for. **A trap pre-installed in the file is worse than one described in prose**: reusing the file's own helper is the natural move, and it fails without a symptom. The observable requirement it binds is story 03's AC-4 — assert on `RosterRetireResult.retired_player_ids` and the resulting `team_rosters` contents, never on the WARN.

#### THE RECORD ITSELF — type and fields, because three stories require it and none defined it

Stories 01, 02 and 03 each mandate asserting on "a structural record carried by the result dataclass", and TN-17 establishes that no such field exists on any of the three grain results today. **Requiring a record and defining a record are different gaps**, and only the second makes the three stories agree on one shape. This is a cross-story interface, so it is specified here rather than left to whichever grain lands first:

**A gate-outcome record defined once in `src/db/reconcile_at_load.py` and carried by all three grain result dataclasses.** `legacy_*` is **GONE** — there is no second gate to report.

| Field | Meaning |
|---|---|
| `gate_evaluated` | **`False` for roster always, since roster runs no floor gate** — and `False` for any grain that early-returns before evaluating one. **MUST NOT read as a permit.** |
| `gate_permitted` | the gate's verdict, or `None` when `gate_evaluated is False` |
| `gate_prior_count` | the denominator used — **the pre-upsert snapshot**. **The numeric tell**: pre-fix the WARN reads 18 where the true pre-run population is 9 |
| `gate_comparable_count` | the numerator used |
| `refused_by` | **UNIT-level refusal only** — `None` \| `"gate"` \| `"cap"` \| `"boxscores_incomplete"` \| `"empty_payload"` \| `"fetch_not_ok"` \| `"skipped_no_exemption_plan"`. **The full set is below; it is NOT uniform across grains.** |
| `permitted` | the value the code acted on; carried though derivable, so a test asserts the acted-on value rather than recomputing it |
| *(the R1 permitted-branch member — **player-line only**)* | the **single-invocation matched-victim finding** of story 01 AC-15: on a retire this grain PERMITTED, the victim ids that name- or jersey-match a **surviving fresh** id. Computable from this call alone, so it satisfies the admissibility constraint below. **Everything else in this table concerns REFUSALS; this is the one member on the permitted branch.** Its NAME is the implementer's choice per the name-is-not-load-bearing line below; its presence and its single-run scope are not. **Added to this table 2026-07-26 at the dispatch flip** — the note four paragraphs down had said since the R1 disposition that *"the field set gained one member on the permitted branch"* and that this note *"is cited as authoritative for that set"*, while the table it was authoritative for never listed it. **That is this note's own 10th-mechanism warning recurring inside it one round later**: the site that ADDS a member is rarely the site that LISTS them. |

**`refused_by` replaces `legacy_*`'s discriminating power while generalizing it**: the wrong-reason trap was never about legacy-vs-corrected, it is that **several mechanisms each produce "0 retired."** Naming the mechanism beats inferring it from two booleans, and it is **the only formulation that works on roster**, which has no gate.

> ### ⛔ THE `refused_by` MEMBERSHIP IS PER GRAIN, AND STATING IT ONCE HERE IS THE FIX FOR A P1
>
> **Codex found this and it was real** [pre-dispatch amendment, second Codex pass, 2026-07-25]: the enum above omitted **`skipped_no_exemption_plan`** while the roster subsection below **REQUIRES the wrapper to synthesize exactly that value**, and story 03 AC-3 named a third, different set. **Three sources, three sets, on the surface an implementer builds and asserts against.** The member is now in the enum and the per-grain split is stated here rather than left to be inferred.
>
> | Member | game | player-line | roster |
> |---|---|---|---|
> | `None` (no unit-level refusal) | ✓ | ✓ | ✓ |
> | `"gate"` | ✓ | ✓ | **✗ — no floor gate exists under V1** |
> | `"cap"` | ✓ (`MAX_GAME_RETIREMENTS`) | **✗ — this grain has no cap** | ✓ (`MAX_ROSTER_DEPARTURES`) |
> | `"boxscores_incomplete"` | ✓ | ✗ | ✗ |
> | `"empty_payload"` | ✓ | ✓ | ✓ — **synthesized by the wrapper**, see below |
> | `"fetch_not_ok"` | ✓ | ✓ | ✓ |
> | `"skipped_no_exemption_plan"` | ✗ | ✗ | ✓ — **roster ONLY; synthesized by the wrapper**, see below |
>
> **Why the table rather than one flat list.** The flat list is what drifted: a reader adding a roster-only member to a set presented as universal has no prompt to check the other grains, and a story author reading the flat list has no way to know which members their grain can actually emit. **`refused_by == "gate"` is unreachable on roster and `"cap"` is unreachable on player-line** — a test asserting either would be asserting a state the code cannot produce.
>
> **⚠️ `"empty_payload"` and `"fetch_not_ok"` are NOT redundant on roster even though its `fetch_ok` is `bool(fresh)`** — they arrive from different sites (the wrapper's early return vs the authority check), and collapsing them re-creates the ambiguity this record exists to remove. If an implementer finds they are genuinely indistinguishable on that grain, that is a finding to raise, not a simplification to make.
>
> **The transferable shape, because this is the SECOND time this enum drifted**: the T6 round added `boxscores_incomplete` after CR-2 found the set non-exhaustive, SE repaired it, and CR-2 verified the repair. **The repair was correct and incomplete** — `skipped_no_exemption_plan` was introduced in the *same* Technical Note, in a later subsection, and never propagated back up to the enum it belonged to. **A verified repair verifies what it was pointed at.** Enumerations drift downward-only: the site that *adds* a member is rarely the site that *lists* them.

**`gate_evaluated` is the fail-closed field.** Do **not** merely null the old fields for roster — a nulled field is indistinguishable from an unset one, which is this codebase's documented missing-safety-signal shape (`.claude/rules/python-style.md`).

> ### ⚠️ THE RECORD IS NOT SCALAR ON EVERY GRAIN — it keys exactly as `.refusals` keys
>
> [CR-2 found this; SE verified in source.] `retire_absent_player_lines` evaluates the gate inside a **double loop** — `for block in blocks:` × `for label, table in _PLAYER_LINE_TABLES:` — calling `crawl_is_authoritative` per `(block, table)`, i.e. **up to four independent gate evaluations per call**, each with its own prior count, comparable count and verdict. A scalar `gate_prior_count` would capture **only the last iteration**.
>
> **This breaks a live AC.** Story 01 AC-2 requires asserting *"the protected count equals the pre-run population (9), not the post-upsert population (18)"* — with both blocks present, a scalar field cannot make that assertion unambiguous, and that count **is** the numeric tell the AC exists to pin.
>
> **The rule that gets all three grains right in one sentence:**
>
> > **The gate-outcome record keys exactly as `.refusals` keys on that grain** — both derive from the same loop structure.
>
> | Grain | Gate evaluations per call | Record keying |
> |---|---|---|
> | game | one, whole-pass | scalar `gate_*`; per-id refusals in `.refusals[game_id]` |
> | **player-line** | **up to four** (2 blocks × 2 tables) | **`gate_*` keyed by `(table, team_id)`**, matching `result.refusals[(table, block.team_id)]` |
> | roster | none under V1 | scalar, `gate_evaluated = False` always |
>
> This also disposes of the `.refusals` / `.refused` plural asymmetry **without a special case**: roster carries `.refused` because its decision is whole-set, and its gate record is scalar for the same reason.
>
> **⛔ IF WRITING THIS SECTION TEMPTS YOU TOWARD A TIDIER, UNIFORM SHAPE, THAT PULL IS THE DEFECT.** Two experienced reviewers each followed it once in a single pass, in opposite directions: SE corrected CR-2 for treating a **per-id refuser** as unit-level, and CR-2 corrected SE for treating a **per-block gate** as unit-level. **Both errors came from assuming one uniform record** over a module whose own docstring states the three grains model refusal differently and deliberately. The record is asymmetric because the grains are asymmetric; any simplification that makes it uniform reintroduces the bug.

> **⚠️ `refused_by` is UNIT-level and MUST NOT absorb the per-id refusers.** The exhaustiveness requirement **splits**, and the reason is a category error rather than a missing member:
>
> - **Per-id refusers already have a home.** `_game_is_cross_perspective_protected` and `not_final` refuse **individual ids**, and each already writes `result.refusals[game_id] = reason`. **Folding them into a scalar would lose *which* ids were held back** — strictly worse than today.
> - `refused_by` answers *"did this grain refuse as a unit, and why?"*; `.refusals` answers *"which ids were individually protected, and why?"* **A test asserting "0 retired" must check BOTH.** That is the wrong-reason trap's real closure on the game grain, and neither field alone provides it.
> - **`boxscores_incomplete` is a genuine missing member** and must be added: it is a separate `retire_absent_games(..., boxscores_complete=...)` parameter, distinct from the cap, and the existing WARN already distinguishes them *because the remedies differ*. Reporting it as `"cap"` would be false.

> **⚠️ AND TWO ROSTER PATHS PRODUCE NO RECORD AT ALL — the sharper half.** In `_reconcile_departed_roster`, **both** `if not fresh_player_ids: … return` and `if exempt_player_ids is None: … return` occur **before** `retire_departed_roster_players` is ever called [SE-verified in source]. So on the grain with no gate, two of the mechanisms that produce "0 retired" sit **upstream of the record meant to disambiguate them** — a fail-closed skip producing exactly the symptom the trap exists to catch.
>
> **REQUIRED — the wrapper synthesizes a result** for those two paths, carrying `refused_by="empty_payload"` and `refused_by="skipped_no_exemption_plan"` respectively. **This is PM's ruling rather than the implementer's choice**, because the alternative (documenting that these paths produce no record) leaves a test with nothing to assert on the grain where the record matters most — roster has no gate, so `refused_by` is its *only* structural discriminator. **Silence is not an option**: it is how the ambiguity re-enters through a different door.

**The record's NAME is not load-bearing; the field set and the keying rule are.**

**This record is also what MUST make the operator-facing refusal WARN nameable** — see the which-gate-refused requirement in each grain story (01 AC-13, 02 AC-10, 03 AC-10). The WARN is rendered *from* the record; the record is not derived from the WARN. That direction is the difference between one source of truth and two that drift.

**⚠️ THE FIELD SET GAINED ONE MEMBER ON THE PERMITTED BRANCH AT THE R1 DISPOSITION (2026-07-26), and this note is cited as authoritative for that set** (story 01's Handoff Context sends implementers here for it), so it is recorded rather than left to be discovered in a story. **⛔ NO CROSS-RUN FIELD IS ADDED TO THIS RECORD, AND ONE WAS ALMOST ADDED** *(corrected 2026-07-26)*. An earlier form of this note said story 01 AC-15 would record an **accumulation signature across invocations**. **That is withdrawn.** Building the predicate revealed why it cannot live here: it needs the **previous** invocation's record for the same key, and **nothing in production retains one** — this record is constructed per call and returned in the result dataclass. Retaining it across runs would be **a snapshot table by another name, which TN-2 rejects outright.**

So the split is: **the cross-run accumulate-then-delete predicate is TEST-SIDE and lives in story 01 AC-14** (where the multi-run harness supplies the history); **story 01 AC-15's production diagnostic is SINGLE-RUN** — victims that name- or jersey-match a surviving fresh id on a permitted retire, computable from one call. **Everything else in this note concerns REFUSALS; AC-15 concerns a retire that was permitted and deleted rows.** *(Also withdrawn in the same pass: `gate_prior_count ≈ 2 × gate_comparable_count`, which holds only at `m = P`. **Do not reinstate either.**)*

**The general constraint this record now carries**: a field is admissible here only if it is **computable from the call that produces it.** Anything needing a prior run belongs in a test, not in this dataclass.

**⚠️ Note precisely what that excludes, because it is easy to blur in either direction** [SE-R1]: `gate_prior_count` **is** computable from its own call and is admissible. What is not admissible is the **comparison across** calls. So the rule excludes the retained previous value without excluding the field itself.

**The detector, which is the usable form**: a field phrased as **"grew since"**, **"changed from"**, or **"unlike last time"** is **a test assertion wearing a field's clothes.** Those three phrasings are the tell; route them to a test and the record stays single-call by construction. Do not fold the two surfaces together: they answer different operator questions (*why did nothing happen?* versus *why did that deletion happen?*), and AC-15 states explicitly why it is not part of AC-13.

**⚠️ And that requirement is a PRESERVATION, not an addition — verified in the source rather than assumed** [PM-VERIFIED, clean read of all three refusal sites]. Each grain already emits a `fresh_comparable_count` / `prior_count` (roster: `roster_db_count`) / `floor_ratio` triple, and the game grain's three-branch `transient_reason` carries a comment stating explicitly that the causes are *"named apart"* because **"the remedies differ."** The discrimination exists today and is deliberate.

**What this epic does is degrade it silently — and the reason is NOT the conjunction, which is superseded.** It is that the refusing mechanisms multiply while the message stays the same shape: `boxscores_incomplete` separates from the cap, roster loses its floor entirely so its "not authoritative" branch changes meaning, and the same unlabelled triple can no longer say **which** mechanism it reports. The comment asserting the causes are named apart stays on the page, still reading as though it holds. On the player-line grain the loss is concrete: the polluted gate's **`9 of 18`** is exactly the healthy-looking message that hid this bug, where the corrected gate reads `0 of 9` on the same input.

**⛔ THIS FIGURE READ `18 of 18` UNTIL 2026-07-26 AND NO EXECUTION CAN PRODUCE IT.** *(Found by SE during story 01; PM-verified independently against the code rather than accepted on SE's arithmetic.)* `comparable` is an **intersection with `fresh`** (`gate_comparable = gate_prior & fresh`), so it is bounded by `|fresh| = 9`; a numerator of 18 requires a fresh payload carrying all 18 ids, which is not this input and would mean nothing was absent at all. **The polluted gate reads `9 of 18` — and `9 >= 0.5 · 18` is exact equality, so it PERMITS and hard-deletes all nine.** ⚠️ **The DENOMINATOR 18 was always correct** — the field-table entry above (*"pre-fix the WARN reads 18 where the true pre-run population is 9"*) is TRUE and must not be swept along with this fix. **The error was only ever the numerator.**

**This is the epic's own signature defect, inside the epic's own Technical Notes, and it survived every review pass**: a number that was *reasoned to* — "the polluted prior counts this run's writes on **both sides**", which is true of the population and false of the numerator — and never executed. Six passes checked whether the figure supported the conclusion; none computed it. **The conclusion was right the whole time, which is exactly why nobody checked the premise** (the two-pattern taxonomy's first probe: *does the premise support the conclusion?*). On roster it blunts `roster_db_count`, **the tell the original audit used** (a count of 4 on a roster that only ever held three rows).

**The transferable form**: adding a mechanism to a guarded path silently degrades every message and comment that enumerated the old mechanisms. Nothing fails; the enumeration just stops being exhaustive. Worth carrying because it is this epic's own defect class — an accurate claim made false by a change elsewhere — arriving inside the remediation for it, and because "we are adding a refuser" is a searchable trigger in a way "some prose may have gone stale" is not.

### TN-12 — Test design constraints (binding on every story's ACs)

- **Two runs through the real producer, always.** A test that hand-INSERTs prior rows and calls a retire helper directly passes before AND after the fix — the defect lives in the *ordering between* producer and reconcile, so a helper-level test cannot see it. This is exactly what the original audit's roster probe got wrong.
- **Assert the gate arithmetic, not just surviving row counts.** The refusal reason carries the comparable and prior counts. Assert the prior count is the pre-run value (e.g. 9, not 18); that is the assertion that fails pre-fix for the *right* reason. A bare "9 rows survive" can pass post-fix for a wrong reason, such as someone disabling the grain.
- **Pair every absence assertion with proof the mechanism completed — but the instrument DIFFERS BY GRAIN.** On **player-line**, `LoadResult.errors == 0` is valid: that reconcile catches all exceptions and returns 1 into `errors`. On **game** and **roster** it is **vacuous** — those wrappers swallow without counting, so a reconcile that blew up still reports `errors == 0`. Use a helper-level call-through spy there and assert the recorded value **is a result object**. See TN-11's mechanism-completed clause for the full statement and the install-point trap. **"The result object is the evidence; a spy is not" holds on player-line and inverts on the other two grains** — where the result object is not evidence at all.
- **Discrimination criterion for parametrized sweeps:** each case must yield DIFFERENT verdicts under the polluted and honest computations. The zero-overlap sweep (9/8, 9/9, 9/10) refuses uniformly post-fix — good as a floor, but it does not pin the ratio arithmetic. Add overlap-bearing cases that do: prior 10 with 5 survivors + 6 new (honest `5 >= 5` permits) versus prior 10 with 4 survivors + 6 new (honest `4 >= 5` refuses). **The polluted side permits both** — post-upsert prior 16, floor 8, numerators **11 and 10** respectively. (Corrected 2026-07-25; this previously read "the polluted numerator is 10 and permits both", which understated the first case. The cases discriminate exactly as intended either way — only the number was wrong.)
- **Mutation hygiene.** The capture is a *move* — a size-preserving edit class where stale `__pycache__` has inverted mutation results on this codebase before. If mutation is used to prove discrimination: no-mutation control first, cache cleared both ways, mutation asserted-applied, per-test outcomes rather than an aggregate count.
### TN-17 — Reaching the structural record: the mandated assertion target is NOT reachable by default

TN-11 requires tests to assert on the retire result dataclass rather than on WARN prose. **As the code stands, a test driving `ScoutingLoader.load_team` — which is what every affected AC specifies — cannot reach that record.** All three grain results are consumed and discarded inside their loader wrappers: the game and roster wrappers log a summary and discard; the player-line wrapper returns only an **int** error increment. `LoadResult` carries `loaded / skipped / errors / redirect_map` and no retire result.

**Left unstated, the implementer defaults to the WARN prose the ACs forbid** — because it is the only option that works without a decision. That makes this the sharper sibling of the log-assertion trap: TN-11 says *the natural assertion is wrong*; this says *the mandated alternative is unreachable*. It would be found mid-implementation rather than at review.

**The requirement, which is PM's to state:** the assertion target must be the returned dataclass.

**⚠️ A PRODUCTION CHANGE IS REQUIRED EITHER WAY — the spy solves REACHABILITY, not CONTENT.** [SE, verified by reading all three dataclasses] The ACs require asserting **which mechanism refused** — `refused_by` plus that mechanism's own counts. **No such record exists on any grain result today**: each carries its refusal as a **prose reason string** — `GameRetireResult.refusals`, `PlayerLineRetireResult.refusals`, `RosterRetireResult.refusal_reason` — which is precisely the surface these ACs forbid asserting on. The roster type's three count fields are structural but do not distinguish *which* mechanism refused. *(This sentence previously described the requirement as "the legacy gate permitted and the corrected gate refused" — banned phrasing, and the finding it supports is unaffected: a production change is required either way.)*

So gate-outcome fields must be added to all three dataclasses regardless of means. **A spy reaches the object; it cannot conjure fields that are not on it.**

**What those fields are is specified in TN-11 ("THE RECORD ITSELF")** — one record type, defined once and carried by all three grain results, with per-gate verdicts and per-gate counts. TN-17 establishes that a production change is unavoidable; TN-11 says what to build. Kept in two places on purpose: an implementer arrives here from the reachability problem and there from the assertion requirement, and either route alone leaves half the answer.

**Two means are sanctioned; the choice is the implementer's** — SE checked viability, found both workable, and explicitly declined to pick:

1. **Add the fields and spy the seam.** Strictly less plumbing.
2. **Add the fields and plumb the object up** through the loader's result object. Cleaner, gives durable telemetry, more scope.

The choice is therefore **not** "test-only versus production change" — both touch production. An AC worded as though the spy avoids production changes would strand an implementer at exactly the moment this Technical Note exists to protect.

**Not sanctioned: falling back to WARN prose.** If neither means is workable, that is a finding to raise, not a default to take. **An unsanctioned default is not a default** — which is why leaving two sanctioned means open is safe where leaving the *fallback* open was not.

**Why the spy precedent is sound rather than merely available** [SE read `tests/test_report_generator.py` rather than accepting the citation]: its call-through wrapper appends the result **after** the wrapped call returns, so a non-empty results list certifies the helper **COMPLETED**, not merely that it was entered. That is exactly the property `.claude/rules/testing.md` says a `side_effect` spy lacks — so this precedent satisfies the absence-claim rule as-is, where a hand-rolled spy would not. It already wraps all three grain helpers.

**The patch site differs BY GRAIN, and getting it wrong fails silently:**

| Grain | Import style | Patch target |
|---|---|---|
| game | function-local | `reconcile_at_load` |
| roster | function-local | `reconcile_at_load` |
| **player-line** | **module-level** | **`game_loader`** |

Patching `reconcile_at_load` does **not** reach the player-line helper. A test that gets this wrong and asserts only on row survival **passes for the wrong reason**, because the spy silently never fires. **The positive assertion that the spy captured something is therefore load-bearing, not decoration** — it is the thing that detects a wrong patch site. Another instance of the class this review swept for: an assertion that looks sufficient and is not.

**Sole exception — story 04, where the steer INVERTS.** See TN-18.

### TN-18 — At the `generate_report()` level the anti-WARN steer inverts

There is no structural record at that level at all (TN-17), so for story 04 the WARN — or a spy — is the **only** positive signal distinguishing a genuine refusal from *the reconcile never running for that game*.

That alternative is live rather than theoretical: the E-244 redirect footgun means a per-game stage keyed off source event ids silently no-ops on deduped games. "Rows survived" is satisfied by that too, and a clean result object does **not** exclude it — it rules out the blew-up case, not the never-ran case.

So story 04 sanctions the WARN or a spy as positive evidence and says why the epic's dominant instruction does not apply there. Stated explicitly because an implementer following the dominant steer would otherwise assert on a record that does not exist.

### TN-16 — Port the executed constructions into `tests/`. This is an AC, not a recommendation.

Every construction this epic's evidence rests on lives in a session-scoped scratchpad and **will not survive**. **A construction that exists only in a transcript is not a regression test** — this epic's own thesis applied to its own evidence. In scope: the operator scoped this epic as "the gate fix + **its tests** + the prose it falsifies", and these are its tests.

Port targets (PM's assignment; each story's ACs also state independently what its fixtures must demonstrate, so a vanished path cannot orphan a requirement):

| Construction | What it pins | Story |
|---|---|---|
| player-line 9-vs-9 churn | the commissioned defect; **the corrected gate refuses** (story 01 AC-1/AC-2) | 01 |
| game 2-prior / 2-brand-new-completed | game-grain discriminating case | 02 |
| **roster 3-row stored / 1 survivor, churn-free** | **the roster-grain DISCRIMINATING case** — today's floor refuses and retires 0; V1's cap permits and retires 2 (story 03 AC-1). **This row was missing while the non-discriminating one below stood in for it.** | 03 |
| roster 2-vs-2 | **CHARACTERIZATION, not discrimination** — under V1 this permits and retires both, **identically to today**, and fails only if someone re-adds a floor (story 03 AC-8(a)). Do not carry its sizing to the discriminating fixture above. | 03 |
| the whole-set construction (10 rostered / fresh drops 2 / 20 churn) | **the churn-region divergence at ordinary roster size** — pre-fix the floor refuses and **0** are retired; post-fix the cap permits and **22 are retired, of which exactly 2 are pre-existing** (story 03 AC-2) | 03 |
| the precondition-(d) slip (snapshot passed as the classification universe) | (d), which no other AC can catch | **03 owns the executed two-run construction. Story 01 AC-9b owns the primitive-level contract test only** — see below |
| the 0-of-2197 exhaustive sweep | deletion-neutrality on game and player-line — **CORROBORATION, not sole support**, since the property is now proved structurally from `W ⊆ fresh`. **Cite it with its `0..12` range or not at all** (story 02 AC-7). | 02 |
| ~~`scratchpad/t_divergence_sweep.py`~~ — **NOT PORTED, deliberately** | It measured divergence between a floor and a corrected floor on the roster grain. **Under V1 there is no floor, so it has no subject in the code.** Its finding — that a count is range-dependent while a characterization is not — is a **process** finding, not a property of the shipped design, and belongs with the process record rather than in `tests/`. Story 03's Notes states the same; this row is the correction it asked for. | — |
| **A MULTI-RUN sequence at EVERY grain — all three, no exceptions** | The blind spot that hid F1 from fifteen attacks: every existing probe and sweep is single-run, and the failure is multi-run. A grain with no multi-run regression test is untested against the whole class. | **01 AC-14 · 02 AC-11 · 03 AC-7 + AC-8(c)** — named individually because "each grain story" was not enough (see below) |
| **THE EROSION CONSTRUCTION — 26-row roster, progressively degrading crawl, 5 invocations, at cap 2 and cap 5** | **The executable form of "rate, not bound"** — cap 2 leaves 16 survivors, **cap 5 leaves 1**. **This was MISSING from this list**: it was found after the list was written and never added, so the epic's most operator-relevant finding about the shipped roster design existed only in prose. TN-16's own rule applies verbatim — *a construction that exists only in a transcript is not a regression test.* **Without it a cap tuner meets no gate at all.** | 03 |

> **⚠️ Why the erosion port is the one item here that is NOT documentation** [CR-2, by fixture enumeration]. `tests/test_reconcile_at_load.py::test_roster_cap_refuses_a_shrink_the_flat_floor_allows` and two siblings do fire if the cap is raised — but **every one of them fails for the reason "the cap moved", which is exactly what the tuner intends.** They are edits on the tuner's own change list. **Not one fails because the CONSEQUENCE of the new value is bad**, and **no test in the suite encodes that consequence at any cap value.** So a tuner who raises the cap and correctly updates all three failing tests gets a **green suite** and learns nothing about `5N`.
>
> The constant-pin (`assert MAX_ROSTER_DEPARTURES == 2`, the suite's only such assertion) is real and cannot be bypassed — but **it makes the change deliberate, it does not make it informed**, and those are different guarantees. Note also that the pin's protective value *fell* exactly when its subject became load-bearing: before V1 a raised cap still had the floor beneath it; under V1 there is nothing else on the grain. **A pin whose object just became the sole guard is worth less, not more.**
| id-churn e2e variant | pipeline-level regression | 04 |

**The 0-of-2197 sweep is the one a completeness pass nearly missed, and it is the one that matters most.** Story 02's AC-7 cites it as confirmation of deletion-neutrality, and it currently lives only in a scratchpad — **a cited-but-unported result, precisely what this Technical Note exists to prevent.** **⚠️ Do NOT contrast it against the 862 sweep as "now historical, since the conjunction closed those cases" — that phrasing is RETIRED and TN-5 says so explicitly.** The conjunction is gone, so those cases are open again and the 862 sweep is now the measurement of how roster neutrality fails. This is the retired claim surviving in a second location, two Technical Notes from its own retraction. Cheap to port as a parametrized property test over the three parameters.

#### ⚠️ THE MULTI-RUN ROW WAS PROMISED FOR EVERY GRAIN AND DELIVERED AT ONE — found at the pre-dispatch amendment, 2026-07-25

**The row above assigned itself to "each grain story". Only story 03 carried a matching AC** (AC-7's erosion sequence plus AC-8(c)). **Stories 01 and 02 had none** — no multi-run construction, at either grain, in any form. Now added as **01 AC-14** and **02 AC-11**, and the port row names all four ACs individually rather than a story class.

**Two things about how it was missed, and the second is the transferable one:**

1. **The row's own wording was ambiguous in the direction that hid the gap.** It read *"A MULTI-RUN sequence at every grain **that keeps one**"* — and this epic's own idiom for "keeps a gate" is exactly that (Goals: *"On the two grains that keep a gate (game and player-line)"*). Under that reading the row promised the construction at **precisely the two grains that did not deliver it**, while the grain that did deliver one — roster, which keeps **no** gate — was arguably outside the promise. **A row that can be read as excusing the two omissions and excluding the one delivery is not a requirement**, and the ambiguity turned on three words in a table cell.
2. **A story-class assignment ("each grain story") is not checkable, and a named-AC assignment is.** Every other row in this table names a construction and a story; this one named a *pattern* and a *category*. **Nothing to grep, nothing to tick off, and three stories each able to assume another carried it** — the same "a requirement claimed by two stories is a requirement written twice or not at all" shape Codex found at precondition (d), arriving in the opposite direction: claimed by *all* stories and written by one.

**And the structural-position finding holds again**: the defect was in a **table cell's assignment column**, not in prose — which is where every top-left hit in both sweeps landed. **The sweep that reported "not one was in an AC" was accurate and did not transfer**: this gap was an *absence* in three ACs, and no term sweep detects an AC that was never written.

#### The twin-accumulation threshold on the game grain — recorded so a fixture is derivable rather than guessed

Story 02 AC-11 pins it; the derivation belongs here so the AC does not have to carry it twice.

`_game_is_cross_perspective_protected` **refuses-and-KEEPS** a game held by another perspective, so a protected game is absent from the fresh array on every subsequent run and is never retired. The gate is computed **before** per-id protection is applied, so a protected id sits in the **denominator** (`prior_ids`) and not in the **numerator** (`comparable = prior_ids & fresh`). **Protected twins therefore degrade the floor ratio monotonically as they accumulate.**

With `P` present, `X` protected-absent and `g` genuinely-absent:

> **the corrected gate permits iff `P >= X + g`.**

[**DERIVED**, PM — arithmetic from `crawl_is_authoritative`'s `fresh_count >= prior_count * FLOOR_RATIO`; **not executed**.] **Its space, per this epic's standing rule**: game grain, corrected gate, `FLOOR_RATIO = 0.5`, protection applied after the gate. A function of one policy constant, not a property of the design.

**⚠️ THE FIX MAKES THIS BIND SOONER, AND IT IS NOT A NEUTRALITY VIOLATION.** With `N` rows written this run, today's polluted gate permits iff `P + N >= X + g` and the corrected gate iff `P >= X + g` — **stricter by exactly `N`**, because the fix removes the offset that was masking the accumulation. **TN-5 scopes deletion-neutrality to DELETIONS** (never permits a deletion today refuses) and states that the gates may disagree in the refusing direction; this is that disagreement, in the direction the epic deliberately chose. **Do not record it as an exception to TN-5** — it is a consequence of TN-5's own scoping, and writing it as an exception is how a scoped claim gets re-read as blanket.

**⚠️ AND THE MEASURED OCCUPANCY IS FAR BELOW THE THRESHOLD.** The E-270 probe measured twins at **~4% of stored ids (22 of ~583)**; `P >= X + g` needs more than half a team's stored games absent-and-protected. **Nothing observed is near it.** This is a **regression guard against accumulation, not a live defect** — and stating that with the threshold is required, because a boundary reported without its distance from production reads as an alarm. *(The same discipline TN-5's sweep ranges now carry: a number without its space misleads in whichever direction the reader is primed for.)*

#### Precondition-(d) OWNERSHIP — one story owns it, stated because four sites disagreed

Codex found the (d) regression claimed inconsistently across four places: story 01 AC-9b ("on all three grains"), this port table (assigning it to 03), story 03 AC-8 (independently requiring the port), and story 01's file list (which had the game and roster test files down as mechanical churn only). **A requirement claimed by two stories is a requirement written twice or not at all.** The split, now stated identically in all four:

| Deliverable | Owner |
|---|---|
| The **primitive-level contract test** — `classify_absences` receives the live prior set, on the grain story 01 wires | **story 01, AC-9b** |
| The **executed two-run slip construction** — snapshot passed as the classification universe, run 1 retires nothing, run 2 the rows are pre-existing and trip the cap permanently | **story 03, AC-8** |

The roster grain is the only one where the slip's *consequence* is demonstrable end-to-end, which is why the construction lives there rather than with the primitive. Story 01's file list no longer carries the other grains' test files (TN-13), which removes the fourth inconsistency at its root.

**⚠️ AND THE REASON IS `W ⊆ fresh` — stated because the sentence above was an assertion, and an assertion that a property holds at exactly one grain is precisely the shape this epic keeps finding wrong.** *(Added at the pre-dispatch amendment, 2026-07-25, after the claim was challenged. It survives, and now carries the premise that decides it.)*

The slip substitutes the **snapshot** for the **live prior** as the classification universe. Since `live_prior = snapshot ∪ W`:

```
correct candidates:  live_prior − fresh  =  (snapshot − fresh) ∪ (W − fresh)
slipped  candidates: snapshot   − fresh
```

The two differ by exactly `W − fresh`. **On game and player-line `W ⊆ fresh` holds** (TN-1's discriminator, TN-5's named premise, guarded at runtime by story 02 AC-8), so `W − fresh = ∅` and **the slip is a strict no-op there** — nothing to demonstrate, end-to-end or otherwise. **On roster `W ⊄ fresh`**, because the jersey backfill writes rows the fresh roster crawl never listed; those rows are the entire divergence, and they are what run 2 finds pre-existing and feeds to the cap.

**So the one-grain scope is a PREDICTION of the epic's own discriminator, not an observation about which grain someone happened to build a fixture for** — the same premise that produces the gate shape, deletion-neutrality, and the grain where neutrality is deliberately false. **It is not weakened by the game grain having a cap of its own**: a cap can only make a divergence permanent, and on game there is no divergence for it to make permanent.

**Do not read the twin-accumulation shape (above) as a counterexample to this.** That shape is about the gate's **denominator**; this is about the **classification universe**. Different mechanism, different section, and TN-1's framing note applies to both — *"the candidate/absent set is already correct; only the gate's numerator and denominator are wrong."*

**One thing no test guards, stated so nobody assumes otherwise:** the per-grain rows above pin the over/under-deletion result *per grain*, which is substantively correct, but **no single test asserts the cross-grain claim** that the epic delivers its fix across all three grains. Do not cite "the table" as though a test guards it.

**⛔ THE WHOLE-SET CONSTRUCTION'S ASSERTIONS INVERTED WITH THE DESIGN, AND THE SUPERSEDED FORM WOULD HAVE SHIPPED A TEST THAT FAILS.** Under the conjunction it was a regression guard asserting **refused, zero deleted, two pre-existing rows surviving**. **Under V1 it executes**: the floor is gone, the cap sees two genuine departures and permits, and the run retires **22 rows — the 20 churn rows plus exactly 2 pre-existing ones** — with the 8 survivors intact. That is TN-5's own executed table and it is what **story 03 AC-2 requires**.

**Carried at this length because an implementer following the superseded wording writes the exact inverse of the AC and watches it fail.** The construction's role has now changed twice — counterexample, then regression guard, now the executable form of the accepted rate residual — and each change silently invalidated the previous sentence. What survives unchanged is *why* it is ported: it was built to defeat a deletion-neutrality claim, and it is the test that pins **the cap, not a floor**, as the thing bounding pre-existing loss.

#### ⚠️ THE PORTING TRAP — verified, and invisible in a diff

Two of the probe files are **already named `test_*.py` and already contain `def test_` functions with ZERO assertions** (0 asserts against 4 and 9 `print` statements). [VERIFIED, SE — SE checked rather than relaying DE's warning, and found it sharper than reported.]

**Porting them is a copy. pytest collects the copy immediately and it passes unconditionally, forever, proving nothing — and it would not look wrong in a diff.**

That is this epic's defect class manufactured by the fix for it: a check that passes while checking nothing. The requirement is therefore an AC and not story prose, because **the failure is invisible either way — the suite is green whether the port was done right or not**:

> **Whoever ports a probe MUST treat its printed values as the assertions to write, never as output to preserve.** A ported file containing `def test_` with no `assert` fails this AC.

The plain-script probes carry no `def test_` so they will not silently collect, but they carry no assertions either and need the same treatment.

#### Assertion requirements on every ported construction

- Assert the roster count in the WARN — the tell distinguishing a polluted prior from an honest one (pre-fix 18 or 30; post-fix the snapshot size). The same numeric tell the original audit used.
- Pair every "nothing retired" assertion with proof the mechanism completed — **and use the right instrument for the grain.** A clean result object works on **player-line** only; on **game** and **roster** the wrappers swallow *without* counting, so `errors == 0` is satisfied by a reconcile that raised. Those need a helper-level spy asserting the recorded value **is a result object**. Full statement and the install-point trap: TN-11's mechanism-completed clause.
- Assert **`refused_by`** — the mechanism that refused — on every discriminating case, plus that mechanism's own counts. "Refused" alone does not identify which of the several refusers fired (TN-11), and on the game grain `.refusals` must be checked alongside it, since per-id protections live there and neither field alone closes the trap. *(This bullet previously read "assert the legacy gate permitted and the corrected gate refused" — the exact AC phrasing TN-1(b)'s banner prohibits, standing as a binding requirement on every ported construction. There is one gate per grain and none on roster, so there is no second conjunct to attribute a refusal to.)*

### TN-13 — Mechanical churn inventory

**9 direct helper call sites** need the new required keyword argument. **This is a WHOLE-EPIC inventory and MUST be split by story — story 01 must not cite all 9 as its own** [PM-VERIFIED; re-anchored to ENCLOSING TEST NAMES at the R2–R5 red-team repairs, 2026-07-26]:

| Story | File | Sites | Enclosing test (stable anchor) |
|---|---|---|---|
| **01** | `tests/test_player_line_reconcile.py` | **1** | `test_perspective_predicate_on_the_diff_is_observable_in_the_proposal` |
| **02** | `tests/test_game_grain_reconcile.py` | **6** | `test_retire_is_scoped_to_the_crawled_season` · `test_protection_with_no_matching_reason_still_refuses` · `test_unmatched_protection_does_not_inherit_a_previous_games_reason` · `test_boxscores_incomplete_refuses_even_below_the_cap` · `test_cap_refuses_even_when_boxscores_are_complete` · `test_refusal_reasons_distinguish_the_three_whole_set_causes` — **one site each** |
| **03** | `tests/test_roster_grain_reconcile.py` | ~~**2**~~ → **0 (MOOT)** | `test_previously_rostered_ids_scopes_the_cap_population` — **BOTH sites sit in this ONE test** |

**⛔ THE ROSTER ROW IS MOOT AND THE REAL TOTAL IS 7, NOT 9** *(self-reported by SE at story 03, 2026-07-26; corrected here rather than in each consuming AC)*. This inventory was built when **all three grains** were expected to gain a required snapshot parameter. **V1 gives the roster grain NO new parameter** — TN-1(a)'s roster EXEMPTION keeps the correctly-timed capture where it already is — so both sites compile and pass **unchanged**, and story 03 correctly made no churn edit. **Nothing shipped is defective; the design moved after the inventory was written.**

**Fixed HERE, at the inventory, deliberately.** Two ACs restate this count — story 01 AC-12 (*"the 9 direct call sites listed in TN-13"*) and story 03 AC-11 — and **story 01 is already DONE**, so patching consumers one at a time would mean editing a closed story and would leave the next consumer to rediscover it. **One correction at the source reaches every reader.**

**⚠️ This is the FOURTH count in this epic falsified by an edit that never touched it, and its DIRECTION is new.** The other three (`4207`, *"Both prose sites"*, *"plus one this story adds"*) were falsified by a later story's **ordinary success**, and the fix was *measure, do not quote*. **That fix does NOT apply here**: this count was falsified by a **DESIGN CHANGE**, and no measurement discipline would have helped — the number was correct for the design it was written against. **The applicable rule is different and worth stating separately: an inventory derived from a design decision must be re-checked when that decision changes, and the roster EXEMPTION was decided *after* this table was built.** *(Whether a general mechanism is warranted is a closure question, not a story-03 one — filed there, not fixed here.)*

**⚠️ THIS TABLE PREVIOUSLY GAVE LINE NUMBERS (934 · 900/1298/1367/1437/1464/1494 · 914/923) AND THEY WOULD HAVE ROTTED MID-EPIC.** All nine were re-verified and every one resolved correctly at the time of writing — this is a rot risk, **not** a stale-citation finding. But each story ADDS tests to the same file it then churns, so the numbers move before the implementer reaches them, and `tests/test_reconcile_at_load.py` is edited by story 01 and cited by story 03 — a cross-story rot. The epic's own rule (`.claude/rules/tool-output-integrity.md`, "Cite a stable anchor, not a line range") applies to the epic's own inventory, and line numbers in this epic have already rotted twice.

**One thing the numbers concealed, surfaced by the re-anchoring**: the roster grain's two "mechanical churn" sites are **both inside `test_previously_rostered_ids_scopes_the_cap_population`** — the same test story 03's Notes flags as having its MEANING changed by V1 (the parameter it pins becomes the sole guard's scope). It is one edit, not two unrelated ones, and the churn and the semantic re-read land in the same function.

Everything else drives the loader and picks up the new ordering for free.

**Consequence for story 01's file list**: the two other grain test files come OFF it. Story 01 touches its own grain's file plus the primitive's; the game and roster churn belongs to the stories that change those grains, in the same commit as the behaviour. Leaving all three on story 01 both overstates its size (a real concern — see the sizing note) and puts a file in two stories' lists with no ordering reason.

**⚠️ A FOURTH TEST FILE WAS MISSING FROM THIS INVENTORY, AND IT HOLDS AN ASSERTION THE FIX MUST INVERT.**

`tests/test_reconcile_at_load.py` — the primitive's **own** test file — collects **19 tests** (17 `def test_` functions, one parametrized over 3 cases) containing **7 direct `crawl_is_authoritative` call sites** across 6 test functions, and `test_empty_payload_refused_even_with_empty_prior` asserts:

```python
assert crawl_is_authoritative(fetch_ok=True, fresh_count=0, prior_count=0) is False
```

**That is precisely the input TN-1(c)'s vacuous-permit inverts.** [PM-VERIFIED by grep] So the claim "no existing assertion changes" is **false**, and it must be stated as: exactly one existing assertion inverts, named above, plus mechanical kwarg churn at the 9 sites.

**⚠️ "Inverts" is shorthand and the literal reading contradicts the opt-in rule this same Technical Note mandates below** *(clarified at the R2–R5 red-team repairs, 2026-07-26)*. Vacuous-permit ships **opt-in**, so the call exactly as printed above — no opt-in argument — **still returns `False` after the fix**. The test is REPURPOSED to exercise the opted-in configuration, and a SIBLING test pins the default-off refusal. **Story 01 AC-12 carries the full reconciliation and is the place to read it.**

**⚠️ AND THAT CORRECTED COUNT HAS SINCE BEEN OVERTAKEN — the epic-wide figure is TWO, not one.** *(Corrected 2026-07-25 at the second Codex spec pass.)* The "exactly one" above is **correct for THIS Technical Note's space** — the fourth file, `tests/test_reconcile_at_load.py`, and the vacuous-permit inversion. **It is not the epic-wide count**, because the roster design's reversal later required a second existing-assertion change: `tests/test_roster_grain_reconcile.py::test_catastrophic_roster_shrink_refuses_on_the_floor` (story 03 AC-11), which keeps its outcome and loses its reason. **Success Criterion 2 carries the epic-wide table and is the place to read the total.**

**This entry now instances its own lesson twice over, which is why the correction is recorded here rather than only upstream.** TN-13 exists to record that *a count was inherited and never measured*; its own correction then *asserted a fresh count that was never measured* (the 13-vs-7 error below); and now the corrected count has gone stale **a third way — without a single word of it being edited.** A change in a *different story* moved the boundary of the space this count ranges over. **A count can be falsified by an edit that never touches it**, and nothing in the sentence signals that it happened.

**How it was missed, which is the transferable part:** the three grain files collect 34 + 20 + 18 = **72** — *precisely* the "72 existing reconcile tests" this epic quoted throughout. **The number was inherited from the commissioning handoff and never measured**, so the regression frame was drawn around a count over a self-chosen space (three grain files) presented as the whole. **The seventh host, surviving in the epic's own success criteria** two rounds after the epic swept itself for exactly that. Every count in this epic carries its space — this one did not, and it was the count doing the most work.

**This is the third defect inherited from the commissioning handoff**, after the non-discriminating 9-vs-9 roster fixture and the stale symbol claim.

#### ⚠️ AND THE CORRECTION ITSELF SHIPPED AN UNMEASURED COUNT. Corrected 2026-07-25 at final triage.

The fix for the missing-fourth-file defect asserted **"19 tests with 13 direct `crawl_is_authoritative` calls."** The 19 is right. **The 13 was wrong — there are 7 call sites, across 6 test functions.** No reading recovers 13: sites are 7, executions counting the parametrize expansion are 9, test functions containing a call are 6.

**All four counts in this Technical Note were re-measured at final triage. Three hold, one did not** [PM-VERIFIED, clean reads]:

| Claim | Verdict |
|---|---|
| 9 direct helper call sites — game ×6, player-line ×1, roster ×2 | **CORRECT**, including the per-file split. *(Measured as line numbers; re-anchored to enclosing test names in the table above at the R2–R5 red-team repairs, 2026-07-26 — every number resolved, so the re-anchoring is rot-prevention, not a correction.)* |
| 72 tests in the three grain files as 34 + 20 + 18 | **CORRECT** — and only because these are COLLECTION counts: the game file has 30 `def test_` plus one parametrize over the 5-entry `_PERSPECTIVE_CHILD_TABLES`, giving 34 |
| 19 tests in the fourth file | **CORRECT** — 17 `def test_` plus one parametrize over 3 |
| 13 direct `crawl_is_authoritative` calls | **WRONG — it is 7** |

**Why this is the entry's most useful line rather than an embarrassment.** This Technical Note exists to record that a count was *inherited and never measured*, and its own correction then asserted a fresh count that was never measured — **the same defect, one paragraph below its own diagnosis, committed by the party writing the diagnosis.** Nothing about the corrected sentence looked unverified; it sat beside a `[PM-VERIFIED by grep]` tag and three counts that were right.

**Two things worth carrying:**

1. **`def test_` counts and COLLECTION counts differ wherever `parametrize` appears**, and on this file set they differ by exactly the amount that makes a naive check look like a mismatch — 30 vs 34, 17 vs 19. A reviewer counting `def test_` would have "refuted" two correct claims and still missed the wrong one. **The measurement method has to match the claim's unit**, which is the seventh host wearing different clothes: the *unit* is as much a part of a count as the space it ranges over.
2. **Correcting a count is exactly when a new one gets asserted unchecked**, because attention is on the claim being retired. Same shape as the two cap-based reconciliations recorded in Background, and the retraction case in `.claude/rules/tool-output-integrity.md`.

**Also required:** the file joins story 01's file list — AC-6's primitive-level tests of the **vacuous-permit rule and the corrected gate** are naturally at home there. *(Previously "the vacuous-permit and the conjunction", which story 01 AC-6 now prohibits in terms.)* And the mechanism must be specified, because **`crawl_is_authoritative` is SHARED** — the roster grain still calls it for its fetch-ok signal, and this file's pinned assertion exercises it directly — so an *unconditional* change to it is not available. Whether that is a new parameter or a separate corrected-gate function is the implementer's call under TN-17's pattern. *(This previously read "because TN-5(a) requires the legacy half to keep today's semantics" — precondition (a) was **rescoped** with the conjunction's removal and there is no legacy half; the conditionality now stands on the shared-callers argument, matching story 01 AC-6's calibration note and TN-13's own paragraph below.)*

**Calibration, recorded honestly** [CR]: applying vacuous-permit unconditionally would not widen the gate *in production*, because all three helpers early-return on an empty live prior, so the gate is never reached with `prior_count == 0`. **The unit test still fails**, which is why the mechanism is specified. **The earlier form justified the conditionality by keeping a *legacy conjunct* at today's semantics; there is no legacy conjunct, and the calibration now stands on the early-return alone.**

### TN-14 — Guardrails binding every story

- **Never touch `data/app.db`.** Report generation is destructive on two axes; the dev DB is not a test fixture. Synthetic DBs built from `migrations/` only. No real crawls, no network.
- **Silent seam detachment (`.claude/agent-memory/software-engineer/module-global-seams.md`).** If any function moves between modules, module globals re-bind to the new module's namespace — and the `get_connection` seam detaches **silently**, because the report generator swallows the sweep's exception by design. That produced a sweep running against the real 17 MB `data/app.db` with **zero test failures**. Stated rather than assumed, because it is the exact failure this epic's guardrail exists to prevent.

### TN-15 — Declared non-goal: the same-canonical-id capture residual (REACHABLE — earlier "unreachable" claim RETRACTED)

Two source games in one run can redirect onto the **same** canonical id; the second game's capture would then see the first's rows as prior.

**This was originally written here as unreachable. That was wrong, and the retraction is DE's own.** DE had read only the tolerant schedule-count guard, not the branch beneath it. On reading `_find_duplicate_game` to completion: the tolerant guard does fail closed as claimed, so a doubleheader never collapses through *it* — but after game A redirects onto canonical C, C carries the own perspective, so when B is processed later in the same run the cross-perspective test is False and B **falls through to the legacy same-perspective branch**, which returns the existing id when start times are equal, or — when either start time is absent — when the score **totals** match. That is precisely the same-total blindness the cross-perspective branch above it was hardened against in E-261, still live in the legacy branch. [DERIVED, DE, self-corrected]

So the shape is **structurally reachable**: same date, same opponent pair, equal start times, or absent start times plus equal totals. No claim is made about likelihood.

**What this changes for E-276: nothing — and that is the point.** The residual is **pre-existing and fix-neutral.** Today the second game's post-upsert prior read already contains the first's rows, because the payload loader commits per game. Under the pre-write anchor it contains them too. Identical exposure before and after; this epic neither introduces nor widens it.

**Falsifier, so this is an honest hypothesis rather than an annotation dressed as a result:** the claim "pre-existing and fix-neutral" is falsified by any input where the two anchors yield *different* candidate sets for the second game. The concrete closure, if wanted later, is to memoize the capture per canonical game id within the run, first capture wins.

Left as a stated non-goal rather than filed, on the team lead's ruling — but note the retraction is the load-bearing part. A TN asserting unreachability would have shipped a false safety claim into the closing document of an epic about false safety claims.

### TN-19 — ⛔ THE CAP PIN IS A FALSE MITIGATION FOR THE RATE RESIDUE, AND NEVER COULD HAVE FIRED ON IT — a defect in how the cap was CHARACTERIZED, not a resolved tension

**Read by**: anyone changing `MAX_ROSTER_DEPARTURES`, and any reviewer asked whether the roster grain's sole guard is adequate. Cited by story 03 AC-6 and AC-7 — **and that citation ran ONE WAY until 2026-07-25, which defeated this note's whole purpose.**

> **⛔ THE PROMOTION'S STATED PURPOSE WAS UNMET FOR THE LIFE OF THIS NOTE.** The banner records that this finding was *"promoted out of this banner into a numbered Technical Note **so a story and a future cap-tuner can cite it**."* **No story cited it.** `TN-19` appeared in `epic.md` five times and in the story files **zero** times, while this note asserted it was *"cited by story 03 AC-6 and AC-7."* **Both ends were individually correct** — TN-19 named the ACs, and the ACs stated their requirements soundly — **and the edge did not exist**, because citation is directional and only one direction was built.
>
> **Why that is worse here than anywhere else in the epic**: the reading guide instructs an implementer to read their story and then **only the TNs it cites by number.** Under that instruction **TN-19 was unreachable from the only story that touches `MAX_ROSTER_DEPARTURES`** — and TN-19 exists to stop exactly one thing, a tuner citing the constant-pin as evidence of adequacy. **A note written to be reached by a cap-tuner, that a cap-tuner's own story does not route to, is a note that fires for nobody.** Same failure as the promotion it replaced, one level up.
>
> **Found by an independent enumeration, not by this epic's own edge-walk — which marked the edge VERIFIED.** The walk confirmed the source end (TN-19 names the ACs; the ACs exist and carry their requirements) and did not test the return direction. **A both-ends check that walks one end and stops is indistinguishable from a passing check**, and its ✅ is worth less than no mark at all, because it forecloses the re-check. *(Recorded as a finding about the verification, not only about the edge — see the fifth-pass entry in `.project/research/E-276-process-findings.md`.)*

> **A note on this note's number.** The ruling that produced it (`.project/research/E-276-roster-design-recommendation.md` §6, *"Record this as a FALSE MITIGATION, not as 'resolved — orthogonal'"*) is recorded there as **binding on TN-10**. TN-10 is occupied by the corrected-invariant wording, which stories 01 and 05 bind verbatim, so the finding is carried here instead and the ruling's reference is recorded rather than left dangling. Whether "TN-10" was a mis-citation or referred to a numbering that no longer holds was **not resolvable** from the artifacts; it is not resolved by renumbering something else.

**Record this as a FINDING, not as a clearance.** The natural way to write it up — *"§3 and §6 do not conflict; orthogonal; resolved"* — **loses the entire point.** What was surfaced is not a contradiction. It is a **FALSE MITIGATION**: the change-control fact offers a comfort that reads as covering the adequacy residue and **structurally cannot.** **A reader taking the two together gets reassurance the design does not provide** — which is worse than a contradiction, because a contradiction announces itself and this does not.

The keeper sentence: **the mitigation could never have fired on the residue.**

> **The cap is a per-invocation rate-limit whose value is change-controlled. It is neither a bound on cumulative loss nor evidence of adequacy.**
>
> 1. **Change control.** The value is pinned (`assert MAX_ROSTER_DEPARTURES == 2`) and two behavioural tests flip at cap ≥ 3, so the constant cannot move silently. This guarantees any change is *deliberate*. It does **not** guarantee the value is correct, nor that a tuner understands the consequence of a new one — **every test that fires on a raise fails for the reason "the cap moved", which is the tuner's own intent.**
> 2. **Adequacy.** At the shipped value the cap permits **unbounded cumulative** pre-existing loss against a progressively degrading crawl (13 rows to 1, permitting every step), because it bounds the **rate**, not the total. **This failure requires no change to the constant.**
>
> These are orthogonal: (1) triggers only on mutation, (2) requires none. **"The cap is locked" is a true statement about change control and carries ZERO adequacy content.** Do not cite the pin as evidence the cap is sufficient.

**⚠️ THE SECOND CLAUSE IS THE FINDING AND IS NOT DROPPABLE — marked load-bearing here so a trim is visibly a deletion rather than a tidy.** *"Neither a bound on cumulative loss nor evidence of adequacy"* — and the zero-adequacy-content rider — carry the whole substance. **The first clause sounds complete on its own, which is exactly why a later editor will trim the rider as redundant.** Ship the first without the second and the finding is gone and the section reads as reassurance again.

**Orthogonality is the EXPLANATION of why the pin cannot fire. It is never the verdict.** The residue requires no mutation, so the pin has nothing to trigger on; the pin triggers only on mutation, which the residue does not involve. **They never touch — which is exactly why the pin READ as a mitigation.** It is true, verifiable, and about the same constant, just about a *different property* of it. Writing that up as "orthogonal — resolved" converts the finding into its own dismissal.

**The finding is against the CHARACTERIZATION, not against the DESIGN — and conflating them loses one of them.** Both claims are true, neither implies the other, and nothing about the pin or the cap needs to change. What is defective is how the two read *together*. Different objects.

**The false-confidence mechanism, named because the facts alone do not convey it**: orthogonality *manufactures* confidence. *"Pinned by a test"* reads as *"the cap is under control"* — true on the axis where nothing fails, silent on the axis where something does. **A reader checking "is the pin real?" gets yes, and stops.** That is why this survived four reviewers where every merely-insufficient premise in this epic did not: a premise that is merely insufficient still points at the right subject, so checking it harder eventually exposes it; **a fact on the wrong axis does not, so checking it harder confirms it harder.**

**The reason the residual is non-blocking is the accepted-residual argument, not the pin.** The operator ruled V1 knowing the trade, and the rate residual is recorded as *"ACCEPTED, not closed"* because the cap cannot distinguish a genuine two-a-week departure sequence from slow degradation — they are byte-identical at every step, and no gate could separate them on the evidence a crawl carries. The correct reason was on disk, one section away, the whole time.

**And a dead override exists on the sole guard, which is worth closing while someone is here**: `roster_departure_guard`'s `max_departures` keyword has **zero callers in `src/` or `tests/`** — the production site binds the default. Nothing structural prevents a future caller (IDEA-154's per-perspective grain is the obvious one) passing `max_departures=10` with no test noticing. **"No caller does X today" is an observation about the current tree, not an invariant** — and this one is under known pressure: the default binds at *definition* time, so monkeypatching the constant does not reach the guard, which makes the injection point **the only supported way to vary the cap in a test.** Story 03 AC-7's erosion test is the first caller, and it is the property's first deleter.

**Provenance, because it is the transferable half**: this was surfaced only because the party who found the tension **declined to resolve it**. Flagging something it could not settle, rather than picking a side to close it out, produced the last real finding in this epic. Had it been graded either way it would have closed as noise.

## Open Questions

None open. Consultation verdicts, one per domain this epic touches:

- **data-engineer — CONSULTED.** Capture anchors (TN-2), transaction and locking verdict (TN-6), staleness in both directions (TN-4), deletion-neutrality (TN-5), the corrected invariant (TN-10), and the roster verdict established by execution rather than derivation.
- **software-engineer — CONSULTED.** Independent confirmation of the executed gate and its general form, two load-bearing corrections to the fix shape (TN-3's roster candidate split, TN-1(c)'s vacuous-permit rule — both reproduced, both of which a uniform fix would have broken), the zero-divergence probes behind TN-13 and story 04, and the three-reason refutation of the "benign" ruling.
- **software-engineer (second instance) — CONSULTED.** The `not_final ∩ fresh` verdict (TN-7), reached independently and agreeing with the first instance, including the sharper point that the asked shape would be counterproductive rather than merely inert in the case its rationale invokes.
- **claude-architect — WAIVED for planning; owns the work.** This is a code epic with one context-layer prose story, not a context-layer epic. Story 05's required content is determined by the code change and by the invariant wording DE specified in TN-10; claude-architect is that story's implementing agent and owns the final wording, the placement judgment, and the residue sweep at dispatch. A planning-time design consultation would be advising on prose it will itself write.
- **api-scout — WAIVED.** No GameChanger payload, endpoint, or data-availability acceptance criterion. The fix is entirely internal to the load path's DB read ordering, and every test payload is synthetic or an already-committed fixture.
- **baseball-coach — WAIVED.** No coaching-facing surface, stat definition, or report content changes. The coach-visible effect is strictly "fewer live rows silently deleted", which needs no domain ruling.

**Honest ceiling on these verdicts:** they make the reasoning visible and challengeable, not correct. A waiver recorded here can still be wrong — in particular the claude-architect one, which is the judgment call rather than the obvious call.

## Size — a deliberate decision, not residue

**`epic.md` is 2,180 lines, and that is too large for the file an implementer reads first.** *(**Re-measured at the close of the R1 rounds, 2026-07-26: 2,180.** The R2–R5 pass earlier the same day measured **three times** — 2,095, then 2,097 after a Status note, then 2,099 after routing follow-ups — and the R1 round then added ~39 more. That is the standing step working rather than failing: a self-referential count has no natural trigger, so the only reliable discipline is to re-measure after every edit rather than after the edit you think is last. **Note what is deliberately ABSENT from this figure now: any claim that it is final.** The prior figure's defect was not its arithmetic but its warrant — see the **14th mechanism** in the process-findings index. The figure read "~213KB / ~1,300 lines" at first writing, "~1,855" at READY, "~1,919", "~1,976", then "2,073" — **stale five times, in the Size section of an epic whose subject is unverified claims.** The 2,073 figure was asserted as *"exact rather than approximate"* because it was taken at *"the last edit before the artifact freezes"* — **and the artifact did not freeze**, which is the fifth staleness and a new shape: not a count that was never measured, but a measured count whose **precision claim rested on a prediction about the future.** It is now current only because the standing step below was followed rather than remembered. Every count carries its space, including this one. **The transferable bit is that it goes stale by the file GROWING, which is the one way a self-referential count fails silently: nothing edits the sentence, so nothing prompts a re-measure.** A count about the artifact that contains it has no natural trigger — it needs a standing step, not a reader noticing. **It is now on that standing step: re-measure this figure as the last action of any pass that edits this file.**)* Recorded as a decision rather than left as an accident, because the diagnosis is the same lesson this epic keeps producing: **fixing one failure by maximising against it produces its mirror.** Inlining against citation-rot was right; an epic nobody finishes has the same practical effect as one whose citations do not resolve — **the content is unreachable, just for a different reason.**

**Two mitigations are in place now**: the reading guide at the top of the file, which routes each reader to the small part they need, and the persisted design artifact, which exists precisely so this file does not have to carry the derivations.

**One extraction remains, and it is specified rather than done:**

> **Extract the History's process mechanisms — the nine-plus named findings with their instances and derivations — to `.project/research/E-276-process-findings.md`, leaving a one-line-per-finding index plus a pointer in the History.**

**The test that selects them** (and it is the general test for anything else here): *is this needed at the point of implementing, or is it a record of how we arrived at the decision?* The first belongs in a story or a Technical Note; the second belongs in History or the artifact. The process mechanisms are unambiguously the second — story 05 hands them to claude-architect for codification, and the epic needs the list and the pointer, not every derivation.

**What stays inlined regardless, and must not be swept up in the extraction**: the design, the preconditions, the ACs' basis, the forbidden shapes, the five required inputs, the operator-facing scope section, the régime tables (though not their derivations), and the load-bearing prose corrections. Anything an implementer or reviewer must not have to fetch.

**Sequencing: the extraction runs as its OWN isolated pass, AFTER the story-03 rewrite, with nothing else in flight.** An earlier plan bundled it into that rewrite on the grounds that the material would be re-read anyway. **That reasoning was wrong twice**: the 03 rewrite re-reads *story 03*, the extraction re-reads *History* — different material — and bundling gives exactly the two-substantial-operations-in-one-pass shape the deferral was declining. **After** rather than before, because the 03 rewrite is design-critical and this is not; if capacity runs out, the thing to drop should cost readability, not correctness.

**Why it was deferred at all, recorded as a decision so a successor does not read it as an oversight**: *a migration I cannot verify is not one I should run.* Moving this epic's most transferable content between files is the operation where content is silently lost, and it was reached at a point where 1,300 lines could not be re-read faithfully. **In an epic whose subject is claims that were not checked, declining an operation that could not be checked is the consistent move, not a shortfall.** If capacity runs out before it happens, **ship without it and leave this specification in place** — a large epic with a reading guide and a written extraction plan is a fine outcome; a botched History migration is not.

## Note for the READY scorecard

**Sources are listed SEPARATELY, never aggregated** — data-engineer, software-engineer, software-engineer (second instance), code-reviewer, code-reviewer (second instance), PM self-audit, Codex — **with the self-audit as its own row.** A flattened count would misrepresent an epic that ran **two spec audits, two PMs, and a design reopened three times**; the interesting quantity is which check caught what, not how many.

**Record the pattern taxonomy as TWO patterns with TWO probes, never collapsed into one:**

| Pattern | Instances | Probe |
|---|---|---|
| Correct **verdict** on an **unsupporting premise** | §4 rows-vs-deletes · §6 re-derivability · §3 change-control-for-adequacy | **does the premise support the conclusion?** |
| Correct **fact** on the **wrong axis** | the pin vs the residue | **does the fact bear on the claim at all?** |

**A reviewer drilled on the first probe passes the second** — which is why the second survived four reviewers. Collapsing them loses a probe. And the sentence that explains *why* it survives, which belongs in this row verbatim: **a merely-insufficient premise still points at the right subject; a fact on the wrong axis does not, so checking it harder confirms it harder.** Every other defect in this record yields to more scrutiny; **this one is fed by it.**

**RECORD THE DEFLATION ARC AS AN OUTCOME — the clearest instance of the discipline this epic is about.** **15 → confounded → 7-vs-6 → one hit, wrong cause, zero cost** — then a fourth check catching the deflation going *too far*. Three successive checks each shrank a finding about **PM's own method failure**, every one against the incentive, on a number **nobody was going to re-derive**; the last removed it entirely, and then the over-correction had to be pulled back. **Both directions needed correcting, by different people.** What this epic does **not** provide is a case where the emphasis hazard bit — and saying so beats an unearned instance, because the next person deciding whether to normalize deserves the demonstrated cost. **The hazard survives on a clean single-variable 2-of-7 and on the mechanism; neither needed the number.** One thread is left **OPEN and unexplained** (a literal grep missing a plain unemphasized string), recorded as a known-unknown with an untested hypothesis rather than closed — because **an uncharacterized failure mode in a sweep method is worse than a characterized one.**

**TWO OF THE DAY'S CHECKING FAILURES WERE IN THE CHECKS THEMSELVES — and both were found by someone RE-RUNNING another agent's verification instead of accepting its result.** A sweep that under-reported and read clean; a content anchor that returned one match where it had returned two and looked exactly like a deletion. Neither was a wrong conclusion about the code — both were **verification instruments failing silently, in the direction of false clean.** That is the argument for re-running a check rather than reading its output, and it is a different practice from reviewing the claim the check was made about.

**Record SE's §12 disclosure as an OUTCOME, not a defect line.** SE established from the transcript that PM's relay was accurate and that **SE itself had rewritten the paragraph** — and that the paragraph it had omitted from the audit appendix was **the one carrying the claim the reviewer then falsified.** That is the worst-available reading of its own conduct, established by SE, reported unprompted, at a moment when *"the relay was loose"* was available and would have been believed.

**A CANDIDATE FINDING INVESTIGATED AND CORRECTLY DECLINED must appear as an outcome.** A count discrepancy (one party reported two occurrences of a word, another three) was routed as a possible relay failure. **It was not one**: the count went 2 → 3 because **the QUOTE grew from one sentence to three**, and both parties counted correctly for the text they held. Establishing that *before* recording it mattered, because recording it would have **flattered this epic's own thesis** — and a fabricated instance in a tally about fabricated claims is self-refuting. **An inflated tally makes the record unusable**, which is the same reason four participants corrected credit downward.

**And name the verification TECHNIQUE in the methodology row, not just the verdict.** The §6 repair was verified **mechanically**: stripping the three substitutions from the repaired text and the three original words from the preserved copy left **byte-identical 391-byte remainders**, proving *no collateral edit* — a negative that eyeballing cannot establish. Better than either party specified in advance.

**And at least one review outcome must be recorded as an ARGUMENT IMPROVED rather than as a finding count.** The adversarial read of the roster design found that the epic led with **re-derivability** to justify prefer-delete, when the input the ruling actually turned on — sustained truncation without recovery — is **precisely where re-derivability is false.** Reordering it (which-wrongness leading, re-derivability demoted to support with both its limits attached) left the epic with **a better argument than it had before the attack.** That is what an adversarial read is for, and a scorecard that renders it as "+1 finding" records the least interesting thing about it.

## READY SCORECARD (2026-07-25)

Written to the specification in the section above. **Sources are listed separately and never aggregated** — the interesting quantity is which check caught what, not how many.

### Sources, one row each

| Source | What it caught that nothing else did |
|---|---|
| **data-engineer** | The roster grain's own breakage, executed through the real `ScoutingLoader` (`roster_db_count=4` on a roster that only ever held three rows — the numeric tell). Capture anchors, the transaction verdict, staleness in both directions. Retracted its own TN-15 unreachability claim on a full read, and pre-registered two falsifiers against its own scope argument — **one of which fell.** |
| **software-engineer** | Independent derivation of the executed gate's general form; the two corrections a uniform fix would have broken (TN-3's roster candidate split, TN-1(c)'s vacuous-permit). The zero-divergence probes. The three-reason refutation of the "benign" ruling. **Declined to let DE absorb a shared error**, and disclosed in §12 that the paragraph it had omitted from its own audit appendix was the one carrying the claim a reviewer then falsified. |
| **software-engineer (2nd instance)** | The `not_final ∩ fresh` verdict, reached independently and *sharper* than the first instance: the asked shape is not merely inert but counterproductive in the case its own rationale invokes. Separately, the `W ⊆ fresh` discriminator, reached by breaking a premise rather than reproducing a failure. |
| **code-reviewer** | The F1 roster-lock counterexample that **reopened the design** and ended the conjunction. The rate-vs-bound finding. The re-derivability ordering fix. Ruled on the divergence-count dispute by re-deriving 20/26/44 **by hand** rather than re-running the script — *"re-running a script only confirms the script."* |
| **code-reviewer (2nd instance)** | Precondition (e) — found on the axis the open-list framing invited. The non-scalar record keying. The sixth game-child table. The false-mitigation finding at TN-19, **surfaced by declining to resolve a tension it could not settle.** |
| **PM self-audit** | The missing fourth test file and the inverting assertion. The `table` key omission (four snapshot sets per game, not one). The three roster symbols. **And its own defects**: a count asserted inside the correction of a count; a reconciliation reverted on a refuted counter-argument plus a misattributed source; a sweep method reported as costing 15 when it cost nothing. |
| **Codex — spec audit 1** | The precondition-(d) regression claimed inconsistently across **four** sites (story 01 AC-9b, TN-16's port table, story 03 AC-8, story 01's file list). *A requirement claimed by two stories is a requirement written twice or not at all.* |
| **Codex — spec audit 2** | Second pass over the reopened design. The completed tally across both passes: **seventeen defects, zero arithmetic** — which is why both passes were needed rather than one. |
| **Final consistency sweep (this round)** | See below. |
| **Independent READY verification + pre-dispatch amendment** *(added after READY; see the History entry)* | **An ABSENCE, which no sweep in this epic could reach**: TN-16 promised a multi-run construction at every grain and **only story 03 carried one**. Now **01 AC-14** and **02 AC-11**. Also the twin-accumulation threshold, the `0..8` range disclosure, and IDEA-187's second deflation. **One of its five items was DECLINED on the file's own evidence** (story 01 AC-9b's rationale holds, on `W ⊆ fresh`), which is the row's other result: **a verification is a claim too, and this one was right four times out of five.** |
| **Codex — spec audit 3 (post-amendment, scoped)** | The **roster `refused_by` P1**: TN-11's enum omitted `skipped_no_exemption_plan` while TN-11's own later subsection required the wrapper to synthesize it, and story 03 AC-3 named a third set. **Three sources, three sets.** Plus story 02 AC-11's self-cancelling escape hatch, story 05's undefined report destination, and the suite-bookkeeping staleness. **4 findings, 4 accepted, 0 dismissed** — and PM's sweep for the last one found **2 further sites** including a Success Criterion. |
| **Codex — spec audit 4 (post-amendment, unscoped)** | **TN-9's prose-site inventory shipped KNOWN-INCOMPLETE** — story 03 AC-9(c) recorded a required site as *"not in TN-9's table"* while story 05's Technical Approach and **Success Criterion 4** both treat that table as the complete inventory. **No sweep this epic ran could have found it**: nothing was stale or self-contradictory in either file alone; the defect existed only in the *relation* between them. Also sharpened audit 3's report-destination finding to the point that overturned PM's fix (see below). **Explicitly CLEARED, and recorded as a result rather than as silence: dependency sequencing, file-overlap/parallelism, agent routing, consultation coverage, repo-reality spot checks.** |
| **PM edge-walk (fifth pass, operator-scoped)** | 47 cross-artifact edges enumerated and both-ends verified. **2 findings, both in PM's own text** — an inflated consumer count inside the note about unresolved claims, and `AC-8a` cited twice against a story with no such label. **Its own most important result was a FAILURE**: it marked the TN-19 edge ✅ having walked one end only. |
| **Independent parallel enumeration (CR-3) + re-verify** | **78 edges, 6 findings, none of which the PM pass surfaced.** TN-19's one-way citation (**the edge PM had cleared**); IDEA-189 linked from nowhere; two exhaustive-class under-counts; two research artifacts carrying retired figures, **outside every sweep's scope**; a duplicate TN-9 row; three further routing gaps. **Enumerated four relation kinds PM did not conceive of** — `src/` prose sites, test files, TN→TN, scorecard→audit — **which is where five of the six live.** At re-verify it swept the claim rather than the forwarded list, and **self-reported that its own prior clean was a false clean caused by an exclusion it had added for precision.** |

**FINAL TALLY — and the caveat is the honest form of it, not decoration:**

> **Six review passes. 19 findings. 0 dismissed.**
>
> **⚠️ That reads cleaner than it is, and the qualification must travel with the number.** **Several findings were found only because a directed sweep went PAST the cited site** — the Success Criterion under F4, TN-9's third dependent, the fourth positional copy. **One overturned the previous pass's own fix.** So **the passes are not independent of the triage that followed them: the pass supplies the POINTER, the sweep supplies the EXTENT**, and reporting the pair as one number credits the pointer with the extent.
>
> **The two most transferable results are about verification instruments failing GREEN, not about the artifact** — a ✅ that forecloses its own re-check, and a clean that was a property of a pattern rather than of the tree. **That is the family where commissioning another pass has the worst expected return, because the next pass inherits the same instrument.** Recorded here so the tally cannot be read at closure as evidence that more passes would find more.

> **⚠️ TWO PASSES INDEPENDENTLY FOUND THE SUITE-BOOKKEEPING P1, AND ONE OF THEM OVERTURNED A PM FIX.** Independent corroboration is the strongest signal either pass produced. **And audit 4 was right where PM was wrong**: PM had answered audit 3's report-destination finding with *"the completion report to PM — not a file"*, which makes an AC verifiable only in-session by one party. Audit 4 named the consequence (*"verification depends on ephemeral agent output rather than a stable artifact"*), and **it is this epic's own TN-16 rule — "a construction that exists only in a transcript is not a regression test" — which PM applied to test constructions and then failed to apply to a verification artifact one pass later.** Destination is now a durable file.
>
> **⚠️ ONE RELAY CLAIM IN THE AUDIT-4 HANDOFF DID NOT VERIFY, and is recorded because the epic's own rule says a relayed claim is checked at the point it is restated.** The handoff stated that audit 4's Success-Criterion site was *"a site F4 did not name"* and that the union to reconcile was **five** sites. **PM's F4 sweep had already named and fixed that Success Criterion** — it was one of the two sites the sweep found beyond the two Codex cited, and it was reported as such. The union is **four**, all fixed. **The corroboration is real and the "new site" framing was not**, and separating those two is the whole of the check.

> **⚙️ WHY AUDIT 4's CITATIONS WERE STALE — a GATE-SEQUENCING defect, NOT a Codex defect. Disclosed by the team lead, and the distinction is the point.** PM's first account — *"audit 4 ran against the pre-amendment file"* — was true and named no mechanism. The mechanism: **audit 4 was launched in the background and the audit-3 findings were routed for fixing while it was still running**, so it read the tree **mid-edit** and its citations rotted before it reported. That is why `epic.md:308` resolves to Success Criterion **1** in the current file.
>
> **The general form, which is the transferable part: a review running concurrently with fixes to its own subject reports citations that are already stale.** Filing that as a reviewer defect would be wrong in the most expensive direction — it would tune the instrument to compensate for a scheduling choice. **The remedy is sequencing, not review design**: freeze the artifact for the duration of a gate, or run the gate serially against a known revision.
>
> **And it is a live specimen of this epic's own reason-rots-independently-of-the-verdict shape**: PM's verdict (*the citations are stale, verify by content*) was right, its stated reason was thin, and **the correct reason was only available from the party who ran the gate.** A reader could have checked the verdict forever without recovering it.

> **⚠️ WAS CODEX RUN ON *THIS* EPIC? — asked at the amendment, and the two rows above answer differently.** **Audit 1: YES, verifiably** — its recorded finding names E-276's own artifacts by ID (story 01 AC-9b, TN-16's port table, story 03 AC-8, story 01's file list), which no inherited reference to an earlier epic could produce. **Audit 2: asserted, not demonstrated here** — its row records only an aggregate tally and cites no E-276-specific finding, so this scorecard does not itself establish its subject. Recorded as the difference it is rather than smoothed into "both ran".
>
> **And neither pass covers the amendment**: both predate **01 AC-14** and **02 AC-11**, which land on the surface an implementer executes. **A third pass over the amended ACs is the cheap check, and this scorecard should not be read as covering them.**

### The final sweep, as its own result

Eleven prohibited terms, three normalizations (strip `**`/`__`, hyphenation, case-insensitive), **grep to enumerate and a read of every hit's surrounding prose to adjudicate**, on two axes.

**The top-left cell was NOT empty.** Twenty-six live assertions in `epic.md` carried superseded design, plus four repairs each to `IDEA-186` and `IDEA-187` in both index row and file. **Every one was in a Technical Note or a tracking artifact; not one was in an AC** — the stories had been swept and their upstream had not.

**The three sharpest, because they would have cost implementation time rather than reading time:**

1. **TN-16 instructed an implementer to write the exact inverse of story 03 AC-2.** The whole-set construction's assertions inverted with the design — *refused, zero deleted* under the conjunction; **22 retired including 2 pre-existing** under V1 — and only the AC was updated. An implementer following the Technical Note writes a test and watches it fail.
2. **Precondition (c) stated the prohibited shape as a live precondition** — *"exactly one gate VALUE — the conjunction — reaches the classifier"* — which TN-1(b) bans in terms. Precondition **(a), four lines above, had been rescoped in the same edit pass.** That is finding K exactly: the editor swept the passage they were editing, not the section they were in.
3. **The `W ⊆ F` diagnostic said the ACs no longer depend on it.** Backwards: with the conjunction gone it is the **sole** support for deletion-neutrality, and stories 01 and 02 both say so in terms.

**A retired claim was found surviving in a second location** — TN-16 contrasting the 862 sweep as *"now historical, since the conjunction closed those cases"*, the exact phrasing TN-5 retracts two Technical Notes away.

**And the sweep's own method produced a finding at the end.** Reading a line back **after** editing it — required by block-edit hygiene, not by the sweep — caught a *second* stale claim in the same line, on the half the edit had not touched. An edit's blast radius is the line, not the phrase.

### Outcomes that are not findings

**The deflation arc, recorded as an outcome.** **15 → confounded → 7-vs-6 → one hit, wrong cause, zero cost** — then a fourth check catching the deflation going *too far*. Three successive checks each shrank a finding about **PM's own method failure**, every one against the incentive, on a number nobody was going to re-derive. **Both directions needed correcting, by different people.** One thread is left **OPEN and unexplained** (a literal grep missing a plain unemphasized string), kept as a known-unknown with an untested hypothesis, because **an uncharacterized failure mode in a sweep method is worse than a characterized one.**

**A candidate finding investigated and correctly DECLINED.** A count discrepancy — one party reporting two occurrences of a word, another three — was routed as a possible relay failure. **It was not one.** The count went 2 → 3 because **the quote grew from one sentence to three**, and both parties counted correctly for the text they held. Establishing that *before* recording it mattered: recording it would have **flattered this epic's own thesis**, and a fabricated instance in a tally about fabricated claims is self-refuting.

**The same shape recurred in this round and was declined again.** The sweep's `conjunction` count came back **55** against a relayed **~54**. That is a units artifact — the tool counts matching *lines* while the relay counted occurrences — not a content change. It was resolved by enumerating and adjudicating all 55, never by reconciling the number. **An unexpected count is a cross-check trigger, never a finding**, in either direction.

**An argument IMPROVED rather than a finding counted.** The adversarial read of the roster design found the epic leading with **re-derivability** to justify prefer-delete, when the input the ruling turned on — sustained truncation without recovery — is **precisely where re-derivability is false.** Reordering it left the epic with **a better argument than it had before the attack.** A scorecard rendering that as "+1 finding" records the least interesting thing about it.

**A disclosure that cost its author.** SE established from the transcript that PM's relay was accurate and that **SE itself had rewritten the paragraph** — and that the paragraph it had omitted from its audit appendix was **the one carrying the claim the reviewer then falsified.** The worst-available reading of its own conduct, established by SE, reported unprompted, at a moment when *"the relay was loose"* was available and would have been believed.

### Methodology row

**Name the technique, not just the verdict.** The §6 repair was verified **mechanically**: stripping the three substitutions from the repaired text and the three original words from the preserved copy left **byte-identical 391-byte remainders**, proving *no collateral edit* — a negative that eyeballing cannot establish, and better than either party specified in advance.

**Two of the day's checking failures were in the CHECKS THEMSELVES**, and both were found by someone **re-running another agent's verification instead of accepting its result**: a sweep that under-reported and read clean, and a content anchor that returned one match where it had returned two and looked exactly like a deletion. Neither was a wrong conclusion about the code — both were **verification instruments failing silently, in the direction of false clean.**

**The pattern taxonomy stays TWO patterns with TWO probes** (see the Note above). A reviewer drilled on the first probe passes the second, which is why the second survived four reviewers: **a merely-insufficient premise still points at the right subject; a fact on the wrong axis does not, so checking it harder confirms it harder.**

### The five lines this epic is judged on

> **"A result that is 'not found' is not the same as 'cannot happen'."**
>
> **And the note that outranks it: neither reviewer applied it unprompted, and it held because the demand was in the process.**

> **"A process that produces good behaviour from people who cannot exempt themselves is a better result than one that requires good people."**

> **"That structure keeps working after everyone who understood the reason has gone"** — beside the lock section's heading-over-body explanation, where the conservative label sits deliberately above a stronger body so that any compression of it is safe by default.

> **Message crossings, recorded as their mechanism: nobody treated silence as agreement.**

> **"Nobody was right, and the process was."**

## Codification Recommendation (for the closure context-layer assessment, trigger 8)

**Recorded here so it is weighed with its reasoning rather than as one item among eight.** claude-architect owns what enters the context layer; this is PM's recommendation, not a decision.

**Recommended above all other candidates from this epic — the ASYMMETRIC-FRAMING pair** (both halves of the History entry "a word class", which must travel together):

> Neither an alarming nor a reassuring qualifier is the defect. **The asymmetry is.** The check is **not** "does the wording sound appropriately grave" — it is **"are BOTH sides of the trade stated?"**

**The reason it outranks the mechanism generalisation, and it is a property of the RULE rather than of the finding: it names a check a non-author can run in one pass.** *"Watch for soft qualifiers"* cannot be executed by a reviewer without re-deriving the author's evidence. *"Are both sides of the trade stated?"* is answerable **from the text alone, by someone who has read nothing else.** That is the difference between a rule and a caution, and it matters here because **every instance in this epic was caught from outside** — including the one that landed inside the section written to prevent it.

**The single-direction form is actively harmful, and this epic is the demonstration rather than the argument**: PM wrote the reassuring-qualifier finding, then committed its inverse **twice in the same document while consciously guarding against the first.** A rule that reliably generates its own inverse in the hands of the person who wrote it is worse than no rule.

**Gate conditions (per trigger 8) are met**: it cites specific defects it demonstrably caught — four reassuring drifts (*"self-healing"*, *"≤2 as a total"*, *"bounded"* vs *"rate"*, *"team sums correct either way"*) and two alarming ones (an inverted fail-closed/safety polarity, a one-sided operator summary). It **recurs** and **generalises past one agent**: five participants, both directions. It is a **narrowing and reframing** of an existing rule (`tool-output-integrity.md`'s safety-comment sub-class), so its natural home is that file and the ratchet cost is small.

**Also nominated, lower**: *a control run needs its own parameterization check* / *a confirmation is only as independent as its most-constrained axis — state which axes you varied, not just your result.* Same one-pass property; narrower applicability.

**PARKED — a STAFFING recommendation, and it is the only output of this epic that would change how an epic is STAFFED rather than how it is verified** [CR-2, in its own framing, which is narrower and better than the credit offered it]:

> The value of the outside seat was that **it had nothing to protect** — a property of the **seat**, not of the occupant. Worth staffing that way again rather than treating this as a one-off.

Weigh it separately from the verification extensions below. Supporting evidence from this epic: the outside seat produced the roster-lock counterexample that reopened the design, the population mis-description, the precondition-(e) direction, the false-mitigation finding, and the §12 auditability gap — **and it declined to grade its own §3 finding**, which is the same property working in the other direction.

**PARKED — a MEMORY-DISCIPLINE surface, distinct from the verification extensions because it is about WHERE a claim lands rather than how it is checked** [SE, after a withdrawn figure of PM's reached its memory file]:

> **Never write a number from a live thread into memory. Wait for it to settle, or record the MECHANISM instead of the MEASUREMENT.**

**The asymmetry that makes it worth a rule**: a handoff artifact is read **once, soon, by someone who might notice** it is stale. **A memory file is read cold, months later, by someone with no thread to check it against.** Evidence from this epic: a figure PM published, then retracted through three successive corrections, had already been written into another agent's durable memory — and was struck only because the retraction was relayed in time. **SE cut the magnitude entirely rather than revising it downward**, on the grounds that an accurate smaller number would still imply the lesson depended on a count it never depended on, and kept the retraction visible so a future reader knows the figure was *withdrawn* rather than never taken.

**⚠️ AND IT IS CURRENTLY MISFILED — the misfiling being the exact failure the lesson describes** [SE, raised and deliberately NOT acted on; recorded here as a recommendation, not a decision]. It lives in `.claude/agent-memory/software-engineer/testing-gotchas.md`. **It is not a testing gotcha. It is memory-write discipline**, and the agent who most needs it is one *writing a memory entry* — who has no reason to open a file about pytest and grep. That is precisely the *"recorded but never recallable"* failure `.claude/rules/context-layer-assessment.md` names: a high-value lesson landing in a file that loads for the wrong task.

By that rule's load-target classification SE reads it as **role-scoped** (it binds SE's own behaviour) → an agent definition or the `MEMORY.md` top-200, **not** a topic file. Possibly **universal-behavioral**, since the product-manager hit the same shape from the other side during this epic.

**SE's recommendation, verbatim**: *promote the general form to the universal target and leave a one-line pointer in `testing-gotchas.md`, rather than keeping the substance in a topic file. If it lands there, evict SE's copy — better pruned than two versions ageing differently.*

**Placement is claude-architect's call at this gate, and SE gave three reasons for not pre-empting it, all of which hold**: claude-architect is about to make exactly this call; a new file plus an index line is priced by the trigger-7 ratchet, which is not SE's spend; and context-layer placement routes to claude-architect regardless of who noticed it. **Recorded in the epic rather than left in a research file, because a research file does not reach this gate** — which is the same reason all four parked candidates are carried here.

**⚠️ AN ACTION REQUEST, NOT A NOTE — RETIRED RESIDUE IN A FILE NOBODY ON THIS TEAM MAY EDIT.** `.claude/agent-memory/data-engineer/health_gate_prior_set_must_be_temporal.md` carries the **"tunable"** phrasing — *"a guard whose only protection is a second, tunable guard is not a guard"* — which is the **ancestor of story 03's sentence**, since story 03 now reads *"a second, independently-owned policy constant."*

**Frame it as retired residue, not as a wording discrepancy between two artifacts.** A discrepancy invites a reader to decide which is canonical. **Retired residue is a claim withdrawn in one place that survives in another** — and it survives in a **memory file**, which carries the decay profile this epic established: *read cold, months later, by someone with no thread to check it against.* DE will recall that file in a future session and get the retired **sufficiency** reading with nothing marking it retired.

**Three things to carry with it:**

1. **The two wordings differ in exactly the direction under dispute** (*"tunable"* vs *"independently-owned policy constant"*), which is **affirmative evidence the rewording was deliberate** rather than incidental — it sharpens story 03's scope ruling rather than weakening it.
2. **The scope of story 03's "deleted rather than softened" is story 03's own paragraph**, not the corpus. Quoted unscoped it reads as a claim about every artifact, which is false and was corrected.
3. **The corroboration both reviewers cite is weaker than an unqualified citation implies** — that memory file's *substance* is concealment-framed but its *closing adjective* leans sufficiency. **Attach this caveat wherever the corroboration is cited, not only where it was challenged.**

**REQUIRED ACTION AT THE GATE: data-engineer or claude-architect must reconcile that file.** **No one on this epic's team has the authority** — not PM, not SE, not the reviewers, not the main session; it is DE's own memory directory under the ownership clause in `.claude/rules/context-layer-assessment.md`. **Stated as an action request precisely because, written as an observation, it reads as informational and dies at this gate.**

**PARKED FOR THIS GATE — three extensions to `.claude/rules/tool-output-integrity.md` that this epic produced first-hand evidence for. Recorded HERE rather than only in a research file, so they survive the gap between READY and closure:**

1. **A file-state verification is a claim with a timestamp, exactly like a handoff.** *"Verified on disk before reporting"* bounds **what was verified, not what is there now.** A genuine extension of the rule's existing *"a handoff artifact is a claim with a timestamp"* — same principle, a surface the rule does not name. Evidence: a reviewer's byte-clean audit window at 34,865 bytes against a file since grown to 39,898, with a quoted section shifting line **mid-audit**, disclosed by the reviewer rather than left to read as covering the current file. *That this arrived at the far end of a session which OPENED with a stale handoff brief is worth exactly one line.*
2. **A grep hit cannot distinguish an assertion from its RETRACTION.** Prohibition 3 currently warns that a hit does not tell you which *alternative* matched; this is sharper and the rule does not reach it. **The reader most likely to skip the confirming read is the one running a consistency sweep** — precisely the operation that would destroy the retraction. Pairs with the new failure shape *editing a retraction into agreement with the text it retracts.*
3. **A CORRECT GREP PATTERN SILENTLY NARROWS WHEN THE DOCUMENT'S MARKUP MOVES BENEATH IT — three members, one class, and it is NOT the known ugrep quirk.** This is the strongest of the three candidates because it has three independent instances from three agents in one session, and **"use ERE" does not catch any of them**:

   | Instance | What moved | Symptom |
   |---|---|---|
   | **Emphasis interpolated inside a phrase** — `adequate **bound** on` vs a literal search for `adequate bound on` | inline markup | literal sweep returned **2** where emphasis-normalized returned **7** |
   | **Blockquote nesting deepened** around a preserved quotation | block markup | a still-correct content anchor returned **1** match where it had returned **2** — *indistinguishable from the original having been deleted* |
   | **A quoted phrase wrapping across a line break** | line breaks | a single-line pattern returned **EMPTY** against text that is present |

   **Each was one step from a fabricated finding.** The second reads exactly as "the preservation copy was deleted"; the third would have produced *"this section cites a docstring phrase that does not exist"* — **this epic's defect class, committed by the reviewer checking for it.** None was a content change; in all three the content was intact and the *shape* moved.

   **The unifying reflex, in CR-2's generalized wording — which supersedes the narrower "unexpected empty" form and should be codified as written**:

   > **An unexpected count is a cross-check trigger, never a finding. ANY count you did not predict, in EITHER direction.** One match where there were two looks exactly like a deletion; two hits where you expected none looks exactly like a live defect. **Both were wrong today.**

   `doc-sweep.md`'s synonym expansion does not reach any of them — **these are not synonyms; they are the same words with markup or whitespace between them.** And it is a different cause from the ugrep alternation quirk the rule already names, so the existing guidance leaves it uncovered.

   **A FOURTH member with a DIFFERENT remedy, which is why it is listed apart**: a **correctly recorded finding carries every token of the live defect it records.** No markup moved and no normalization helps — **the strings are genuinely identical.** `doc-sweep.md` warns that a retired claim survives in forms carrying *none* of its tokens; this is the exact inverse. **Only reading separates them**, and the operation most likely to skip the read is the consistency sweep — which is the operation that would strike the record.

   **Where the third instance was found is the strongest evidence in the set**: by re-running **a verification of a verification** — one level further out than anyone would expect yield from. It did not fall off.

   **A FIFTH member, and the cheapest to guard: LETTER CASE.** A grep for `DO NOT label it` returned **zero** against text reading `Do NOT` — run by the author of the catalogue, while being careful, *inside the check the catalogue exists to protect*. **The catalogue does not protect its author.** The trigger was expectation-mismatch (a zero on text it had just written was implausible), not suspicion of the tool.

   **Consequent standing requirement — a sweep of this repo's prose needs THREE normalizations, not one**: strip `**`/`__`, expect **hyphenation** variants (`zero adequacy` greps to nothing; the epic writes `zero-adequacy-content`), and match **case-insensitively**.

---

## Additional codification candidates from this epic's own working

**Recorded here rather than only in the process-findings artifact, for the same reason as the three above: a research file does not reach this gate.**

### A0. ⛔ `Glob` DOES NOT MATCH DOTFILE DIRECTORIES — a repo-wide silent false-absence mode over this project's own governance surface

**Promoted out of a method note at the team lead's direction, because the blast radius is the whole context layer.** Recommended load target: **`.claude/rules/tool-output-integrity.md`, the "Silent-empty from a tool quirk, not from absence" family**, beside the ugrep alternation entry. *(claude-architect owns the call; this is the recommendation and its evidence.)*

**The observation** [PM-VERIFIED, fifth-pass edge-walk]: `Glob` on `/workspaces/baseball-crawl/.claude/agent-memory/*/*.md` returned **`No files found`** — for files read and edited **in that same session**. A brace-expansion form over four known-present paths returned the same. `Grep` over the identical directory returned 60 files immediately.

**Why it is not one quirk in one session: every context-layer path in this repo is dotted** — `.claude/rules/`, `.claude/agents/`, `.claude/skills/`, `.claude/hooks/`, `.claude/agent-memory/`, `.project/ideas/`, `.project/research/`, `.project/archive/`, `.project/baselines/`. **The governance surface is exactly the surface this fails on.**

**It fails in the direction that ships.** `No files found` reads as a clean negative, not an error — so an agent concludes *"no rule covers this,"* *"that memory file does not exist,"* *"the idea was never filed"* and proceeds. **A confident negative from a channel that structurally cannot answer the question.** This is the same failure direction as the emphasis hazard, and the reason both belong in the unexpected-empty family.

**The distinguishing feature, which is why it needs its own entry rather than a line on the ugrep one:**

| | ugrep alternation quirk | **this** |
|---|---|---|
| Nature | a **pattern-syntax** bug | a **path-shape** blind spot |
| Fix that reaches it | use ERE (`-E`), or one pattern / one path | **none of that helps** — no pattern change and no normalization reaches it |
| Mitigation | rewrite the pattern | **a second channel** (`Grep`), which is what was used |

**And note what made it reportable at all**: it was caught on files the searcher had **personally edited minutes earlier**. Against any unfamiliar path it would have looked like a true negative and been believed — **so the observed instance is not evidence about the rate, only about the existence.** Assume it has fired silently before.

**The rule it instances is already on the books and simply was not applied to `Glob`**: *"A 'no files found' Glob is NOT proof of absence under a flaky channel — confirm absence through a second channel before relying on it."* **That sentence exists in `tool-output-integrity.md` today.** What this adds is the **specific, reproducible, non-flaky cause** — dotted paths — which converts a general caution into a checkable condition: **if your path starts with a dot, `Glob` cannot answer, and the empty result carries no information.**

### A. Per-observation provenance — the discipline that makes every other timestamped claim mean what it says

> **Scope provenance PER OBSERVATION, not per message.** Pair each read with a `stat` taken *at that read*, and compare the two. A write-up spanning several calls carries one timestamp — usually the newest — so a stale read gets labelled with metadata from a later call that never covered it. **Quoting *a* timestamp reads as rigour and is worth less than quoting *the* timestamp.**

**Its strongest justification is that it caught something its author was not hunting**: a reviewer flagged a review-scope gap *"because I could not verify text I had not read, not because I suspected the sign-off had been extended."* That is the argument for **stating scope routinely rather than only when you suspect a problem.**

### B. A USAGE caveat on the mtime differential — TWO clauses, and it is NOT a limitation

**⛔ An earlier draft of this entry called it a limitation on the instrument. That was FALSE and is struck.** The differential was not defeated; **it was never applied.** The rule prescribes comparing `stat` **against the time of your read**, and in the incident the stat was merely *reported beside* an observation rather than *compared against* it — one operand was never supplied. **Codifying that as a limitation would have taught future readers the instrument is unreliable, when it is the same check that correctly diagnosed an empty grep as a moved file an hour earlier.**

Both clauses are required, and they are different errors:

1. **Operand** — compare against **your** read, not against the newest state you have seen in the session. A stat from a later call is not the operand.
2. **Ordering** — **take the stat at or AFTER the read.** A stat taken *before* a read authenticates nothing; the file can move in the gap. *(This is the error actually committed — a caveat covering only clause 1 would have appeared to explain the incident while leaving it unaddressed.)*

**Write the asymmetry, not a general warning**, because it preserves the instrument's real power: an mtime **later** than a read bounds when the file last *changed* and settles nothing about that read; an mtime that has **not advanced** past a checkpoint **is direct evidence no write has occurred since** — exactly what mtime is fit to answer.

**And the entry is "could not have failed if used," not "was not used"**: a genuine limitation was attempted and **could not be constructed** (monotonic advance on write, nanosecond granularity, no revert-to-identical path). **A failed falsification attempt is stronger than an absence of counterexamples.**

### C. The three-hop chain — the sharpest specimen this epic produced

> A **usage error** → relayed as a **variant** → arriving at codification as a **limitation on the instrument.** Each hop a reasonable compression of the previous one. **No hop careless.** The endpoint would have degraded `tool-output-integrity.md` itself — **the rule whose whole function is catching claims that outrun their evidence.**

**Different in kind from every other instance here: no individual error and no careless step**, and the damage lands on the rule designed to prevent exactly this.

**Record the propagation path, not only the endpoint** — *a retraction that reaches its author's own thread but not the artifact built from it downstream.* **Second confirmed instance today** (the first: a retracted figure reaching a memory file), which makes it a pattern rather than an anecdote.

**It fits the routing rule precisely**: the codification decision was heading to **the party that could not check the trace** — and that party was the router.

### D. The routing rule

> **Never route a decision to the party that cannot check the evidence — and that party is often the router.**

The diagnostic half explains why relay defects cluster where they do: **a router asked factual questions it had no channel to answer, answering them anyway because the question arrived shaped like a routing question.**

### E. The execution boundary — stated narrowly, with its test attached

> **Execution is the stronger instrument for a claim about BEHAVIOUR and the weaker one for a claim that is DEDUCTIVE. When a sweep would sample a tautology, the sweep adds nothing. The test is whether the claim COULD FAIL on some input — if not, there is nothing to sample.**

**Drawn this narrowly deliberately.** *"Execution is not always right"* invites reasoning instead of running whenever reasoning is cheaper; **a boundary wider than the tautology case would do more damage than the rule it qualifies**, given how hard this epic pushed the other way.

### F. Executed scenarios that do not contain the mechanism under test are not evidence about it

**Promoted out of the withdrawn-proof item, where it read as the explanation of one mistake.** As a general check anyone can apply, it **fired twice today from opposite directions**: five executed scenarios in which the coupling under test was structurally inert, and a sweep whose control never fired. **A green result over a space where the mechanism cannot appear is not a result.**

### G. A note written to DEFER a question survives the question's answer

**Four instances in one session**, all caught on the same reflex: a superseded blocker whose cause had been deleted; a banner pointer mistakable for a fix; a scope note reading *"for X and Y to confirm"* after they had; and a marker reading *"SE is attempting the fixture"* after SE reported.

**All four were correct when written. All four rotted on someone else's action. None would fail a test or a grep** — they read as current because they are grammatical and on-topic.

### H. A justification whose SUPPORT was removed, still standing where it was

The conjunction's removal deleted the reason behind an AC's conditionality while **the conclusion stayed correct**. *Vacuous-permit stays opt-in* — right before and after; the stated reason (*"the legacy half must stay byte-identical to today's gate"*) referred to a half that no longer exists.

**Harder to find than the stale ACs, and the contrast is the point: the stale ACs CONTRADICTED the banner and were findable. This one AGREED with the outcome and was wrong only about why.** Nothing greps for it, no test fails, and **a reviewer checking "is vacuous-permit still opt-in?" gets yes and stops.** Same family as correct-fact-on-the-wrong-axis — **checking it harder confirms it harder.**

### I. A tracking artifact is not exempt from what it tracks

`IDEA-187` exists to record that a stale invariant survives in another agent's memory file. **Its own index row went stale by the same mechanism**, asserting the conjunction as the shipped design and citing a refuted check as established.

**This is NOT entry G.** G is a note surviving its question's answer. This is: **a file whose purpose is recording that something is out of date carries no immunity — and its custodian is the least likely person to re-read it, because they know what it says.**

**⚠️ SECOND INSTANCE, AND IT IS STRONGER THAN THE FIRST — added at the pre-dispatch amendment (2026-07-25).** The entry above was written after repairing `IDEA-187`'s index row. **A later check of the same idea's *body* against the artifact it tracks found the tracked claim itself did not hold**: `IDEA-187` Defect 1 quoted a paragraph of the DE memory file **that does not exist in it** (a full read plus a second-channel grep across `.claude/agent-memory` confirmed the absence), and stated the sufficiency direction **backwards against TN-10** — the note it cites as authoritative — by attaching "necessary but not sufficient" to the temporal clause where TN-10 attaches it to same-population. The file already carried TN-10's version near-verbatim.

**Three things this second instance adds that the first does not:**

1. **The first repair pass touched the row, not the claim.** Repairing an index row's *design description* leaves the underlying report unchecked, and both surfaces then agree — which is what made it read as fixed. **Agreement between an artifact and its index is not evidence about either**, when the index was derived from the artifact.
2. **Acting on the report would have made the tracked file WORSE**, not merely wasted effort: the proposed edit was to attach the sufficiency note to the temporal clause, which would have introduced the inversion into a memory that did not have it.
3. **The report credited its own method as the careful one** — *"found by reading the file, not by grepping for the claim"* — and reading is precisely where it failed. **A grep for the quoted paragraph returns zero and settles it in one command.** Near-homograph forms defeat readers and greps in *different* ways, so neither instrument covers the other, and the instrument named as the safeguard was the one that broke. This is `.claude/rules/tool-output-integrity.md`'s quote-the-literal-text requirement arriving in the one artifact whose subject is unverified claims about another file's contents.

### J. Block-edit hygiene — a mechanical mitigation for a mechanical failure

**Two duplications in this session's editing, one cause**: an `old_string` that did not extend to the end of everything the new text superseded, leaving the tail beside the replacement.

> On a large-block replacement, the `old_string` must reach the end of **everything the new text supersedes** — not the end of the paragraph you were thinking about. **Read the region back regardless.**

**Why it survives review: a duplicate in prose reads as EMPHASIS, not error.** The two instances differed in kind — the first duplicated a paragraph the editor never intended to touch; the second duplicated the editor's **own earlier provisional text against their own final text**, which is harder to see because both copies are theirs and both are correct.

### K. An edit's blast radius is the SECTION, not the passage

> **A targeted rewrite creates a false sense of coverage over everything nearby, because you were just there.**

**The instance**: TN-11's record and its traps were rewritten for the one-gate design, and **the stale conjunction phrasing four lines above — in its own assertion-target bullets, in the exact wording the banner declares stale — was not touched.** The editor swept the section they were *editing*, not the section they were *in*.

**It is the closest neighbour to the sweep-normalization failures and it fails the OTHER way.** Normalization misses text you searched for with the wrong pattern; **this misses text you never searched, because you had just read past it.** No pattern catches it — the mitigation is that a rewrite's verification scope is the enclosing section, not the edited passage.

*(Found on a re-read that was not required. That is the only reason it is here rather than in the shipped epic.)*

### L. Accidental correctness — a document that is right without saying why

> **A document that is correct without stating WHY is one refactor away from being wrong, and nothing marks it.**

**The instance**: TN-17's patch-target table points at the correct module for the game and roster grains — function-local imports mean patching `reconcile_at_load` reaches the helper — but **nothing stated that this was the reason.** So a future editor moving the install point had no signal that the pointer was load-bearing rather than incidental.

**Accidental correctness is invisible to every check**: it reads as correct, it *is* correct, and it fails silently the moment its unstated premise moves. **It cannot be found by verifying the document, because verification passes.**

**The repair is structural and it recurs three times in this epic** — state the reason where the thing lives, not in the reasoning that produced it: the **falsifier test written into (c)** rather than left in the review thread, the **heading-conservatism line** written beside the heading, and **this table's reason** written into the table. Same move each time, and the justification is the same: **that structure keeps working after everyone who understood the reason has gone.**

## History

> ## The process findings have been EXTRACTED — full text at `.project/research/E-276-process-findings.md`
>
> **This is a pointer to a completed move, not a note that something still needs doing.** The named process mechanisms, with their instances and derivations, now live in that file. What remains below is the chronological record: what was decided, when, and what status the epic was in.
>
> **An implementer never needs the extracted findings.** The reader who does is **claude-architect at the closure Context-Layer Assessment Gate** — trigger 8 is scored from that file, and the Codification Recommendation section above names the four candidates drawn from it.
>
> **The framing that governs the extracted record, kept here because it is the one thing a reader must carry into it**: every failure recorded there was **CAUGHT, inside the session, by a named check** — the point is which instrument caught what, not that anyone was wrong. DE's form: *a claim that was flagged, executed, and overturned within the session is evidence FOR the rule that caught it; an unflagged version of the same claim would have shipped.*

### Index of extracted process findings

One line each; full text in `.project/research/E-276-process-findings.md`.

**The host / mechanism series** — a claim's carrier, numbered as found:

| # | Name | One line |
|---|---|---|
| 5th host | The **summary** of a claim | Inherits the truth-value of the moment it was written and carries it forward silently. Recurred within the hour, under active guard. |
| 6th host | A true claim with **false stated support** | Nearly discarded, because checking the citation would have discarded a sound conclusion. |
| 7th host | A quantity over a **space the author chose** | Reported as though the space were given. Every count carries its space or it is not a count. |
| 8th mechanism | **Provenance as authority** | A claim about X from the owner of X is the least-checked kind. The only one that *predicts*; carries a tripwire, not a policy. |
| — | A **printed conclusion inside an execution artifact** | Inherits the artifact's credibility without inheriting its verification. Companion: *"re-running a script only confirms the script."* |
| 9th mechanism | **A count falsified by an edit that never touches it** | Correct when written, invalidated **remotely** when its space's boundary moves elsewhere. **Distinct from the 7th host**: that is wrong at authoring time and fixed by stating the space; this one stated its space and the space moved. **No sweep finds it** — the text is unmodified and self-consistent. Instance: TN-13's *"exactly one existing assertion inverts"*, falsified by the roster reversal in a different story. |
| 10th mechanism | **A verified repair verifies what it was pointed at** | Enumerations drift **downward-only** — the site that ADDS a member is rarely the site that LISTS them. Instance: `refused_by` leaked past a failed review, a repair, and a verification of that repair; three sources carried three sets. |

| **14th mechanism** | **A measured count whose PRECISION CLAIM rests on a prediction about the future** | Not an unmeasured count (7th host) and not one falsified remotely (9th) — this one was **measured, exact, and correctly labelled "exact rather than approximate"**, because the label was conditioned on *"the last edit before the artifact freezes."* **The artifact did not freeze.** The measurement never rotted; **the warrant for calling it exact did**, silently, when a later edit landed. Instance: the Size section's `2,073`, stale within a day inside a sentence whose own parenthetical was tracking four prior stalenesses. Generalizes past line counts to any **"final as of"** assertion — a claim indexed to an event that has not happened yet is a claim about the future wearing a measurement's clothes. **Detector: if a precision claim names a terminal event, it is unverifiable until that event occurs; assert the measurement, date it, and do not warrant the terminality.** |

*(9 and 10 were found after the extraction, at the post-READY amendment and the four Codex passes. Full text: `.project/research/E-276-process-findings.md`, **Addendum 2**, which also carries two method notes — word **inflection** as a further grep-narrowing member, and the `count`-returns-**lines**-not-matches label trap that misled two agents in one session. **14 was found at the R2–R5 red-team repairs, 2026-07-26; full text: the same file, Addendum 3.**

⛔ **THIS TABLE IS A PARTIAL VIEW AND NUMBERING FROM IT PRODUCES COLLISIONS — one was committed here and caught.** The canonical series lives in `.project/research/E-276-process-findings.md`'s own Index, which carries **11th, 12th and 13th mechanisms that this table does not list.** The new finding was first numbered **"11th" by reading the highest number present HERE** — a collision with the existing 11th ("a one-way citation is not an edge"). **Corrected to 14th before it shipped.**

**The mechanism it instances is the 12th, committed while appending a row to the table that catalogues it**: *agreement with a derivative is not corroboration — open the primary, never consult a summary of it.* Numbering off a subset is the same move as verifying off a summary. **Anyone adding a row here MUST take the next number from the research file's Index, not from this table.**)*

**The two-pattern taxonomy** — do not collapse; a reviewer drilled on the first probe passes the second:

| Pattern | Probe |
|---|---|
| Correct **verdict** on an **unsupporting premise** (3 instances) | *does the premise support the conclusion?* |
| Correct **fact** on the **wrong axis** (1 instance — the cap pin, TN-19) | *does the fact bear on the claim at all?* |

**The rest, one line each:**

- **The signature defect, in checkable form** — *what region did I sample, and what region am I claiming?*
- **The correction of a defect is not a safer place than the defect was** — over-claim then over-correction, neither caught by its author; a defect and its fix are two claims.
- **Asymmetric framing** — the top codification candidate. Neither the alarming nor the reassuring qualifier is the defect; the asymmetry is. Check: *are BOTH sides of the trade stated?*
- **Verification that inherits what it was meant to catch** — a confirmation is only as independent as its most-constrained axis; state which axes you varied, not just your result.
- **A correct narrowing licenses stopping** — more dangerous than an under-covered input set, because it is real work that retires the wrong question.
- **Editing a retraction into agreement with the text it retracts** — a new failure shape, one instruction away from happening.
- **The grep cannot tell an assertion from its retraction**, and a hit can be the correct form that looks like the error. Plus the markup/whitespace/hyphenation narrowing class.
- **The divergence-count gap** — four successive wrong reconciliations, each accepted because it corrected its predecessor; the cheapest check beat all three.
- **Single-run blindness** — fifteen failed attacks, all single-run, against a multi-run effect.
- **The completed tally** — seventeen defects, zero arithmetic; why both review passes were needed.
- **Review design** — the two-pass self-audit, and the three techniques re-reading cannot replace.
- **The orchestration layer's own failures** — seven instances, one with a structural fix (*do not assert what you structurally cannot verify*).
- **Attribution and credit** — four participants corrected a credit downward; an inflated tally is unusable.
- **Blanket rules have needed bounding as often as correcting** — five times; on this material an unbounded rule more likely needs a boundary than a retraction.
- **What worked** — persisting a throwaway probe was the cheapest high-value act of the session.
- **Retros in participants' own words** — DE's, SE's.

### Chronological record

- 2026-07-26: **CLOSURE ASSESSMENTS — PM. Both remediations landed; artifacts frozen at 26 files, +5126/-193.**

  **PM's `epics/` + `.project/` identifier sweep — RUN, and CLEAN.** The residual story 03 declared and PM accepted. Swept `FLOOR_RATIO` / "floor ratio" / "shrink ratio" / `MAX_ROSTER_DEPARTURES` over `.project/ideas/` and `.project/research/`; `epics/` holds only E-276, and `.project/archive/` is a frozen historical record that must not be edited. **Every live hit already carries the V1 scoping** — IDEA-186 and IDEA-187 both state the roster grain ships with no floor ratio at all, in the file and in their README rows; IDEA-160 was corrected earlier in this dispatch. **No stale claim found. The one tree nobody swept during the stories was `docs/` — and that is where the single operator-facing defect was.**

  **⚖️ TN-11 CRASH-PATH `refused_by` — RULED: NO sixth member. Captured, not fixed.** `_reconcile_departed_roster`'s swallowed-exception branch returns a bare `RosterRetireResult()` byte-identical to the "nothing to decide" state, on the one grain whose wrapper swallows without an `errors` backstop. **Inventing a member now re-opens the P1 that three sources carrying three different sets produced at the second spec pass**, against an AC-3 that pins the set to five. Blast radius nil today — the production call site discards the return. **Recorded where it will be found: it ANSWERS [[IDEA-189]]'s own Open Question 3** (*"is there a third channel — the reconcile result objects E-276 introduces?"*) with **no, not unaided**: any fix must give the crash path a *distinguishable state*, not merely add a record.

  **📋 REVIEW SCORECARD.** **01** CR round 2 APPROVED (2 MUST FIX, 9 SHOULD FIX, all valid, 0 dismissed) · **02** APPROVED round 1 (0 MUST, 3 SHOULD) · **03** APPROVED round 2 (1 MUST FIX, all AC-9 prose, plus a fourth site SE found itself) · **04** **APPROVED with NO findings — the only clean first review** · **05** context-layer-only, **PM-verified alone** per the dispatch protocol, per-story CR skipped by design. Closure: **Step 1a invariant audit FIRES** (team-lead's ruling — a canonical seam's signature changed: `retire_absent_player_lines` gained a required kwarg and `crawl_is_authoritative` a parameter; TN-13 is the Technical-Notes declaration; no migrations, so that trigger did not fire) → CR; then the **unconditional Closure CR Integration Review** over the full diff. **CODEX — RAN. ONE finding, Priority 2, VALID, remediated** *(row filled 2026-07-26; this previously read "INCOMPLETE until its outcome is recorded")*. `_dedup_candidate_victims()` reads `team_rosters` by `team_id` + `player_id` only, but that table is **season-scoped by primary key**, so story 01's AC-15 diagnostic is **season-ambiguous** — the WARN can be emitted **or suppressed** by rows from another season. False positive reproduced by Codex and **independently by CR**. **SHOULD FIX, severity floor HELD**: no live consequence in a single-season DB, but **latent rather than speculative** — the schema represents it, `bb data dedup-players` requires `--season-id` once 2+ seasons exist, and E-250-01 made season scoping structural in `find_duplicate_players`, **so the diagnostic naming that instrument is unscoped in exactly the dimension the instrument was hardened on.**

  **⚖️ IT WAS CR'S OWN STORY-01 SHOULD FIX, CLOSED THEN BY SCOPING THE DOCSTRING — AND CR REVERSED ITSELF. The reason is the finding, not the reproduction.** Its justification had been that `retire_absent_player_lines` has no `season_id` in hand: **true of the parameter list, FALSE of what is reachable** — `games.season_id` is `NOT NULL` and the caller holds `game_id`, so the season is one join away. The rule it broke was **in CR's own rubric** (*"when a query must supply a dimension the source table lacks, a JOIN through an anchor table is required"*), which it had **applied to other agents' code twice in this same epic.**

  > **⛔ A NEW SHAPE — the first in this epic where the VERDICT does not survive.** *A SHOULD FIX accepted on a cost argument that turns out to be wrong is not a SHOULD FIX.* **The cost WAS the disposition, so the disposition does not outlive the cost being checked.** Every prior instance here was a false premise under a verdict that held; **this is a correct-looking verdict whose premise, once checked, FLIPS it.** Reproduction alone would not have moved it — CR had already granted the mechanism. **Re-opening its own reasoning did.**

  **CR also WITHDREW its Step 1c APPROVED verdict as premature, unprompted** — *"an approval issued before the Codex adjudication is exactly the approval that stretches."* It re-runs the Step 1a sweep after the fix, since a threaded parameter changes a signature it audited.

  **📄 DOCUMENTATION ASSESSMENT — FIRED, dispatched, complete.** `docs/admin/operations.md` said the roster cap applied *"in addition to the shrink ratio"* and closed *"a partial/degraded crawl never causes data loss"* — **false precisely where the operator inverted the bias.** docs-writer replaced it with three paragraphs (bias-to-refuse scoped to game and player-line; the roster grain's absent floor with both operator-facing consequences; an explicit statement that no-data-loss does **not** hold for roster), swept `docs/`, and declared its scope. **The only defect this epic found that would have reached the OPERATOR rather than an agent — and Success Criterion 4 would have PASSED with it standing.**

  **🧩 CONTEXT-LAYER ASSESSMENT — eight explicit per-trigger verdicts. FIVE FIRE → claude-architect codification required BEFORE archival.**
  1. **New convention/pattern/constraint — YES.** TN-9's **construction rule** (grep the identifiers of every changed CONTRACT, not the diff), its **stopping rule** (*includes whose CALLER SET the story changes*), and its **scope clause** (every tree that DESCRIBES the contract, `docs/` included).
  2. **Architectural decision with ongoing implications — NO.** The gate population and the roster floor removal are behavioural rulings already carried by CLAUDE.md and TN-1/TN-3; no technology or integration choice was made.
  3. **Footgun / failure mode / boundary — YES, the epic's largest output.** Two families: **a false premise under a correct conclusion** (execution 4-of-4; careful re-reading 0-of-4) and **the instrument failing while looking like it worked** (bad positive control → false alarm; vacuous mutation probe → false clean; under-specified fixture → a green test over a fixture that does not do what its name says). Detectors in `.claude/agent-memory/product-manager/e276-health-gate-triage.md`.
  4. **Agent behaviour / routing / coordination — YES, narrowly.** The **message-channel finding** (*re-reading a carrier is a no-op as a check; if re-reading a thing cannot change what it says about the world, it is not a source*), plus **five crossed-message chases**, all in one direction: assuming an artifact was unchanged rather than reading it.
  5. **Domain knowledge for future epics — NO.** No baseball, API or data-model insight surfaced; the findings are process- and code-contract-shaped.
  6. **New CLI command / workflow / procedure — NO.** No `bb` subcommand, script or skill added, renamed or retired.
  7. **Context-layer growth ratchet — FIRES, and it is NOT this epic's to clear.** The baseline was already **4 deferrals stale (+972, mostly inherited agent-memory growth)** before E-276 opened, and this epic adds more agent-memory. **Frame it to the operator as "stale for N epics", never as "E-276 broke the ratchet."** Needs an **operator-signed exception** or an offset; **an agent may not wave it through**, and only the operator runs `--update-baseline`.
  8. **Reusable behavioural lesson — YES, gated.** Candidates: the two detector families (3), the message-channel item (4), and **CR's criterion-versus-evidence cut — the strongest, because CR reinvented it under load before it was named.** Each cites a specific defect it demonstrably caught, so gate (a) passes; **gate (b) is the ratchet, which trigger 7 says it does not fit.** Promotion is therefore **gated on the same operator decision as 7**; claude-architect decides placement, not whether to grow past baseline.

  **✅ TRIGGER 7 — OPERATOR-SIGNED EXCEPTION GRANTED, 2026-07-26. Baseline NOT re-snapshotted.**
  - **The ratchet stands at +2,871 over baseline in the main checkout before this epic merges** — `.claude/agent-memory` +2,670, `.claude/rules` +193, `.claude/agents` +8.
  - **E-276's own net contribution is ~196 lines.** ⚠️ **State it as "the baseline has been stale for several epics", NEVER as "E-276 broke the ratchet"** — the inherited +2,675 predates this epic and is not its debt.
  - **The exception covers E-276's own ~196 lines ONLY.** The operator **declined `--update-baseline`**, deliberately: **the inherited +2,675 stays VISIBLE AS DEBT rather than being absorbed by a re-snapshot.** That is the more conservative of the two available rulings and it keeps the counterweight meaningful for the next epic.
  - ~~**Trigger-8 promotions are capped at ~100 lines total, a hard ceiling.**~~ **⚠️ AMENDED BY THE OPERATOR MID-PASS, 2026-07-26 — the ceiling is WITHDRAWN.** *"You can let it grow. We're about to refine the context layer anyway."* claude-architect promotes **what the material warrants**, and was told to **reinstate anything it had cut for SIZE rather than MERIT, and to name which those were.**

    **⛔ DO NOT OVER-READ "let it grow" — three things did NOT change. This is an amendment, not a replacement:**
    1. **The baseline is STILL NOT re-snapshotted.** The operator declined `--update-baseline` and has not revisited it. **The inherited +2,675 stays VISIBLE AS DEBT**, and E-276's own growth remains an operator-signed exception. **Lifting a promotion ceiling is not absorbing the overrun.**
    2. **Deletion-side eviction and memory retirement still fire unconditionally** — they prune, they do not grow.
    3. The standing warning stands: **a codification MUST NOT quietly resolve trigger 7 by growing the layer.**

    **The STATED REASON is what makes this an amendment rather than a waiver**: a **context-layer refinement pass is coming**, so rationing at closure is premature — **compression gets done deliberately in that pass rather than by budget here.** That reframes the debt from **UNPAID to SCHEDULED**, a materially different History entry. **⛔ A later reader must NOT cite this as precedent for waiving the ratchet.**

    **The measured-delta and declined-list requirement is KEPT, on NEW grounds.** Its original justification — *a promotion list without a declined list cannot be audited against a ceiling* — **died with the ceiling.** **The incoming refinement pass is now the consumer**: whoever runs it needs to know what this dispatch promoted, what it deliberately left out, and why, or they re-derive both. **A declined list is the cheapest possible input to a compression pass.**

    **⚙️ And the cap was getting credit for work SELECTION was doing.** The quality bar — *a lesson reinvented independently under load beats one that was agreed to* — **is a merit test, not a budget test, and it survives the ceiling's removal intact.** **Nothing is promoted merely because there is now room.**

  **✅ CLOSURE CR INTEGRATION REVIEW (Step 1c) — APPROVED, 2026-07-26**, over the remediated diff and the Codex finding together, after CR **withdrew its own earlier APPROVED as premature**. Final state **27 files, +5,343/-193**; CR states every line of the +195 beyond its reviewed baseline has been read.

  **On the sweep disposition CR went beyond the remediation and reached a stronger result**: instead of re-checking SE's hits it swept the claim's **FORMS** repo-wide — `season-UNSCOPED`, `"season_id in hand"`, `"same number in two seasons"`, **0 hits each**. **The retired claim's headline forms are gone from the repository entirely; the docstring was their only home.** The two `season-ambiguous` survivors are an archived E-249 record and this scorecard — **both EVIDENCE, not criteria**, and editing either would be the error. *(Accounting note, no action: SE reported three hits, CR's form-targeted sweep finds two — PM's triage file is not among them, its `UNSCOPED` hits being a different sense of the word. **Third instance this epic of a count over another artifact.**)*

  **⛔ ARCHIVAL REMAINS BLOCKED** on claude-architect's codification (triggers 1, 3, 4, 8, under the ~100-line cap), then the closure merge: patch to main, **Step 1b full-suite gate**, **Step 1d runtime smoke**, archive rename, and the operator's commit-approval gate. **PM authors `COMPLETED` in the worktree at Step 8 sub-step 3 — not before, and it finalizes only on a green suite in main.**

- 2026-07-26: **ALL FIVE STORIES DONE. Epic stays `ACTIVE` pending two closure remediations and the closure passes.** Staged: 25 files, +5072/-191. Per-story send cost **41 / 18 / — / 11 / —**; story 01 carried the shared primitive plus four spec corrections, story 04 was the only clean first review.

  **⛔ THE DISPATCH CORRECTED ITS OWN SPEC ROUGHLY A DOZEN TIMES, AND THE PATTERN — NOT THE COUNT — IS THE FINDING: every correction was to a claim this epic had ALREADY REVIEWED AND PASSED.** The recurring shapes, each now with a written repair:
  1. **A false premise under a correct conclusion** — `18 of 18` (a figure no execution can produce, through six passes), AC-12's roster justification (contradicted by AC-6's own calibration 45 lines above), and two more. **Caught by EXECUTION 4 of 4; by careful re-reading 0 of 4.**
  2. **TN-9 incomplete FIVE times** — and the fifth was a gap in its **reach**, not its contents: `docs/` was never in scope, so **Success Criterion 4 would have passed with an operator-facing runbook promising the opposite of what ships.** Repaired with a construction rule (grep the identifiers of every changed CONTRACT), a stopping rule (*includes whose CALLER SET the story changes*), and a scope clause (*every tree that DESCRIBES the contract*).
  3. **Four counts falsified by edits that never touched them** — `4207`, *"Both prose sites"*, *"plus one this story adds"*, TN-13's roster row. Three fixed by *measure, do not quote*; the fourth needed a different rule, because a **design change**, not a later story's success, falsified it.
  4. **Three stale Files lists** (`player_dedup.py`, `scouting_loader.py`, `python-style.md`) — **a distinct mechanism, because both artifacts are individually correct and only their RELATIONSHIP is broken**: the AC keeps looking satisfiable while the work becomes unreachable.

  **⚙️ AND A SECOND FAMILY EMERGED THAT BOUNDS THE FIRST — the INSTRUMENT failing while looking like it worked**: a positive control that could not match (false alarm), a mutation probe whose mutation never applied (false clean), and a fixture that did not do what its name said. **Since finding 1's remedy is "run it", this family is the qualification: run the check AND validate the check's own preconditions.** Full record, with detectors: `.claude/agent-memory/product-manager/e276-health-gate-triage.md`.

  **Three ideas captured, all raised while closing something else**: [[IDEA-189]] (extended twice; two of its Open Questions answered), [[IDEA-190]], [[IDEA-191]].

- 2026-07-26: **E-276-01 DONE — first story landed; 02 IN_PROGRESS, 04 now eligible.** Both gates cleared (CR APPROVED round 2; all 15 ACs PM-verified). Two review rounds plus a prose pass, **2 MUST FIX + 9 SHOULD FIX, all valid, none dismissed** *(counts from the team lead's running tally, to be reconstructed from the artifacts at closure — where they disagree, the artifacts win)*.

  **⛔ THE STORY PRODUCED FOUR SPEC CORRECTIONS, AND EVERY ONE WAS A CLAIM THIS EPIC HAD ALREADY REVIEWED.** Recorded together because the pattern is the point, not the individual fixes:
  1. **AC-13's `18 of 18`** — a figure no execution can produce (`comparable` is an intersection, bounded by `|fresh| = 9`), naming a **refusal branch that input cannot reach** (`9 >= 0.5·18` permits). Four homes, originating in the process-findings file. **Reasoned to, never run, through six review passes** — the conclusion was right, which is why nobody computed the premise.
  2. **AC-12's justification** — *"an unconditional vacuous-permit would make an empty roster payload read as authoritative"*. **False**: `fetch_ok` is checked first and roster passes `fetch_ok=bool(fresh)`. **The epic already held the TRUE version 45 lines above in AC-6's calibration** — two live claims of unequal strength pointing the same way, which is why no consistency sweep could see it.
  3. **TN-9 gained two rows and a fourth-site fold** (module docstring; `player_dedup.py::_fold_name`'s now-third consumer; `crawl_is_authoritative`'s own header + condition-2 gloss). The table has now shipped incomplete **three times**.
  4. **Two hardcoded counts retired** — story 02 AC-6's *"Both"* (correct-but-fragile) and story 03 AC-9's *"plus one this story adds"* (**already stale**, contradicted by its own body four paragraphs below).

  **The transferable finding, and it is new**: `.claude/rules/tool-output-integrity.md`'s reason-rots detector is *reopen the cited file* — useless here, because **both sentences were present, both checkable, and the file was open.** The detector is **executing the stronger claim**. Persisted for the trigger-8 gate in `.claude/agent-memory/product-manager/e276-health-gate-triage.md`, alongside the message-channel item.

- 2026-07-26: **DISPATCHED — status `READY` → `ACTIVE`, on the operator's authorization, with review.** Stories execute serially in the epic worktree `/tmp/.worktrees/baseball-crawl-E-276/`; PM owns status transitions and AC verification, code-reviewer gates every code story. **No design change and no AC change accompanies this transition** — it records the operator's dispatch decision only. The READY freshness gate stops applying at this point (`ACTIVE` epics are exempt).

  **Two stale Status-block claims were corrected in the same edit, both falsified by the R1 round without anything editing them**: *"R1 is still outstanding"* (R1 landed as the AC-14 rewrite plus AC-15), and *"dispatch … nothing here authorizes it"* (dispatch is now authorized). Both were accurate when written during the R2–R5 round. **This is the 9th mechanism firing inside the Status block itself** — the section a dispatching reader is most likely to treat as current state.

  **Standing guardrails restated for every agent on this dispatch (operator-set)**: never touch `data/app.db`; synthetic databases built from `migrations/` only; no real crawls.

- 2026-07-26: **THE PREDICATE WAS EXECUTED, AND EXECUTING IT MOVED IT TO A DIFFERENT AC.** Final R1 round. Verdict untouched; status READY.

  **The decision.** SE-R1 offered an accumulate-then-delete predicate and **labelled it "checked against data, not separately executed."** It was held out of the artifact on that basis and SE was asked to build and run it. It **holds 8/8** — fires on regime B run 3 at both measured block sizes and on the opponent block, silent on regime A, the sub-boundary case, a first-ever-load-then-clean-reload, a clean re-scout, and a new game joining the season.

  **⛔ AND BUILDING IT REVEALED THE THING THAT DISQUALIFIED IT FROM WHERE IT WAS HEADED.** The predicate needs the **previous invocation's record for the same key**, and **nothing in production retains one** — the record is constructed per call and returned in the result dataclass. Retaining it across runs is **a snapshot table by another name, which TN-2 rejects outright.** So the routing instruction to "record the run-3 signature in the gate-outcome record" was **withdrawn**, and the artifacts were split: **the predicate is TEST-SIDE and lives in AC-14**; **AC-15's production diagnostic is SINGLE-RUN** (victims name- or jersey-matching a surviving fresh id, computable from one call). TN-11 now carries the general constraint: **a field is admissible in that record only if it is computable from the call that produces it.**

  **⚖️ THIS IS THE EPIC'S OWN THESIS DEMONSTRATED ON THE EPIC'S OWN REPAIR.** The predicate was **correct**. Its author labelled its status **honestly**. It would still have shipped into the wrong AC — and the disqualifying fact was visible **only to someone building it.** *Checked-against-data and executed are different epistemic states, and the gap between them is exactly where this class of defect lives.* The defect E-276 fixes survived six review passes because a property had been **reasoned to rather than run**; pinning a reasoned-to predicate inside the repair would have reproduced that defect in the fix.

  **Two further executed results, both narrowing what the artifact may claim:**
  - **The `> 0` clause is REQUIRED, established by running without it.** Dropped, three scenarios false-fire — including a game added on invocation 2, which fires **twice**: a first-ever load records `prior=0, permitted=True` under the vacuous permit, so the next clean load reads as growth-with-permit. **Without the clause the predicate misfires on every new game of the season.**
  - **The 8/8 was run against a harness record dict, NOT the real `ScoutingLoader`** — SE flagged this itself rather than let the number be read as broader than it is. AC-14 states the predicate is validated **at the record level** and that expressing it against the real loader is the story's implementation work. The team lead declined SE's offer to build that version: story 01 is `TODO`, and a consultation-mode agent writing it pre-dispatch would execute the story outside the story (Work Authorization Gate). **PM concurs on work-definition grounds.**

  **Also folded:** SE's **`m ≥ P`** generalization replacing the literal 12 (measured at P=12 and P=9; everything beyond labelled algebra, not measurement) — a regime-B fixture built at a different P against a bare "12" would be **silently wrong**, since in that fixture 12 is both the original and the churn block size. Plus **"two co-resident generations, not a doubling"** for the sub-boundary case, and a **sourcing constraint**: `drv5` printed 3-tuples only, so `absent`/`retired` may be pinned from the two fully-sourced rows alone (m=12 from `drv2`; P=9,m=9 from `drv1`).

  **⛔ CLOSING REPAIR — the stale positional denominator was live in SIX artifacts, not the two we were discussing.** DE's legitimate append made its memory file 41 lines; every *"line 21 of **35**"* went false while **line 21 itself stayed correct**, so the natural check (*is the cited line still where we said?*) **passed for two independent parties**. Repaired in story 05 AC-9, IDEA-187, the ideas README row, PM's triage memory and the process-findings file; **`.claude/agent-memory/code-reviewer/` was NOT edited** (another agent's own directory — flagged for its owner, the same boundary that makes IDEA-187 an idea rather than a one-line edit). **The fix changed the FORM, not the value**: all editable copies now identify the paragraph by its **opening words**, with coordinates demoted to dated evidence, so no future append can falsify it. Two traps inside the repair: the first pass fixed three of story 05's four copies and **missed the one inside a paragraph correcting an earlier positional error**, and the **README row was producing `doc-sweep.md`'s index-row shape for the fourth time in the very parenthetical that names it.** Full log in `.project/research/E-276-process-findings.md`, Addendum 3.

  **📌 THE MECHANISM THAT RAN THROUGH THIS ENTIRE ROUND, recorded because three parties hit it independently: EVERY ONE OF US ANSWERED FROM A RECONSTRUCTION WHILE THE PRIMARY SAT ON DISK, CHEAP TO OPEN.** PM numbered a finding off `epic.md`'s **partial copy** of the findings index and collided with an existing number; SE presented an m-sweep as 5-tuples when its harness printed **3-tuples**, inferring `absent`/`retired` from row counts; the team lead relayed **five** figures, paths or literal strings that did not survive contact with the file or the runtime, including a product chain that computes to 936. **Same mechanism, three actors, one session.** The reconstruction is always more available than the source, and it is always confident — which is why the standing instruction that emerged (*take no number, no formula and no literal string from the router; get it from the agent that executed it or from the file*) is infrastructure rather than etiquette. **Every one of these was caught by someone opening the primary.**

- 2026-07-26: **R1 FIGURES RECONCILED AGAINST SE-R1's EXECUTED RECORD — two relayed claims WITHDRAWN before they shipped.** Same round as the R1 disposition below; recorded separately because what changed is the *evidence*, not the verdict. **The verdict is untouched.**

  **Two items were withdrawn from the routing instruction by the team lead after SE-R1 specified what it had actually measured** — both would have put a false claim into an acceptance criterion:

  1. **The 72-row figure was attached to the wrong regime.** It measures **run 2**, where 3 of 13 is *below* the floor and the gate permits immediately — **TN-8's partial-churn residual at season scale ([[IDEA-185]]), not the R1 run-3 accumulate-then-delete window.** It has been **moved** to the production-scale argument it genuinely supports, with its regime named. SE's own words: it was *"one label away from supporting the wrong claim."*
  2. **`gate_prior_count ≈ 2 × gate_comparable_count` does not hold and is not pinned.** SE swept it against its own rows: exact at `m = P`, false otherwise (2.00 / 1.92 / 1.86 / 1.80 at `m = 12/13/14/15`) — **an artifact of the equality case, not a signature.** Replaced with the across-invocation form (*prior count grew since the previous invocation while the payload did not, and the retire was permitted*), which is testable and `m`-independent. `retired == prior − comparable` is recorded as an **observation of the delete run**, never an invariant — it is false on run 2.

  **Three further corrections from SE-R1, all narrowing claims this epic would otherwise have overstated:**
  - **The sizing rule is `m ≥ P`, not "m ≥ 12"** — measured at `P = 12` (m=11 refuses, m=12 deletes, exact equality, no gap) with one confirming point at `P = 9`. Everything beyond those two points is algebra consistent with measurement, **not measurement**, and is now labelled as such.
  - **Below the boundary the outcome is DIFFERENT, not smaller** — two **co-resident generations**, not "duplicates"; the exact doubling appears only at `m = P`.
  - **Regime A had no dedicated mechanism assertion.** SE's evidence was a row-count-plus-id-identity pair from which the sweep is *inferred*. The AC now requires that observable and **does not credit SE with a direct one**; it also records that a **spy is insufficient** ([[IDEA-189]]: a failing collapse is swallowed without incrementing `LoadResult.errors`) and that the stronger `dedup_team_players` return value is discarded at the call site.

  **⛔ AND THE SWALLOWED-EXCEPTION FINDING IS WORSE THAN "THE SAME TRAP TWICE."** SE corrected the framing: **its instance was a guard that crashed and read as a REFUSAL; DE's was a reconcile that crashed and read as a CLOSURE.** Same seam, **opposite directions** — each agent got the outcome it was probing for, and the row count cooperated with both hypotheses. **A trap that fires twice the same way can be named and dodged; a seam that converts a crash into whichever outcome the observer expected cannot**, because the confirming evidence arrives exactly where you were already looking. The ACs now state that **the row count is not an admissible witness for EITHER outcome on this grain.**

  **PROCESS NOTE, recorded because it changed how this round was run.** The team lead relayed four figures, paths or literal strings wrongly in one session — including a product chain (`24 × 13 × 3 = 72`) that computes to 936 and that SE never wrote — and then issued a standing instruction: **take no number, no formula and no literal string from the router; get it from the agent that executed it or from the file.** Both withdrawals above were caught by that discipline, and the first was caught by PM refusing to restate arithmetic that did not compute. **A router that compresses fixture descriptions into pinnable claims is a lossy channel that reads as precise.**

- 2026-07-26: **R1 DISPOSITION — DIAGNOSTIC ONLY, NO GATE (operator ruling).** A **separate and later round** than the R2–R5 repairs below; recorded distinctly so neither inherits the other's work. Status stays **READY**. **Nothing refuses a retire that today permits one**, so deletion behaviour is unchanged by construction and AC-8's deletion-neutrality is untouched.

  **The verdict.** Three mechanisms that would close the sustained-churn window — an `extra_guard`, a cap, and a churn-signature gate — were evaluated **by construction**, independently, by SE-R1 and DE-R1. **None was adopted.** The deciding finding was reached **twice, from different fixtures**: *every mechanism that closes the window closes it by refusing forever, and a permanent refusal on this grain **doubles the coach-facing season aggregate*** — measured against the shipped `get_season_batting` at 27→54 AB and 36→72 AB. A doubled season line reaching a coach is worse than the deletion. **Residual ACCEPTED and SURFACED; the closer is merge-not-delete → [[IDEA-185]].**

  **The crux, reached independently by both agents**: **`W ⊆ fresh` constrains the CANDIDATE set, not the GATE POPULATION — and it is the population that grows.** A refusal still WRITES, so each refused run adds its generation until the gate permits at the floor. The epic's headline is therefore true for **one run**.

  **Edits**: AC-14 **fully rewritten** (the "must not ratchet" property was FALSE under the shipping design, on the fixture the AC itself mandates — an unsatisfiable assertion, now a two-regime pin with the opponent-block gap named as an accepted residual); **new AC-15** for the permitted-retire diagnostic; AC-2 **fail-open hardening** (operator-ordered); the DoD's AC-14 entry replaced with a **three-way split**; the false **player-line grain-table row** retired; **WHAT CHANGED item 5** added; the **"No new player-line cap" Non-Goal** re-affirmed on new grounds; one **code-prose citation** fix routed into AC-11.

  **⛔ THE FINDING THAT SHOULD OUTLIVE THIS EPIC: A SWALLOWED EXCEPTION IN `_retire_absent_player_lines` PRODUCES EXACTLY THE OBSERVABLE OF A SUCCESSFUL REFUSAL, AND THE SURVIVING-ROW COUNT CANNOT DISTINGUISH THEM.** This is not one engineer's stumble. **Two independent agents, both experienced with this module, both writing code specifically to probe this seam, both produced a FALSE PASS from a swallowed exception — and neither knew the other had.** SE's guard raised and was swallowed, returning the refusal observable; DE passed `PlayerRef` objects into a set intersection, the `TypeError` was swallowed, the reconcile aborted, and its harness printed **"CLOSES the fork window"** — the right answer for the wrong reason. **In both cases the row count showed the desired result.** DE caught it on `LoadResult.errors`, not on rows. It therefore binds the **tests** as much as the implementation: any AC asserting a refusal by counting surviving rows is **satisfiable by a crash**. Pinned in AC-14, AC-15 and AC-2, and connected there to the operator-ordered fail-open hardening, since both are the same root — **this gate's failure modes are silent and look like success.**

  **⚖️ RECORDED BECAUSE IT IS THE BEHAVIOUR THIS EPIC IS TRYING TO MAKE ROUTINE**: DE reported **both** of its own defects against its own work rather than quietly fixing them — the swallowed `TypeError` that produced a false PASS, and a **mislabelled baseline** (*"true team AB = 27"* where the post-departure truth is **24**) that would have let a reader see agreement where there was none. Neither was discoverable from the artifacts; the sole detector for that class is **the actor volunteering it** (`.project/research/E-276-process-findings.md`, Addendum 2). A record that shows only the findings agents made about *others'* work misrepresents how this epic actually worked.

  **PM's own error this round, caught before it shipped**: the new process-finding was first numbered **"11th mechanism"** by reading the highest number in `epic.md`'s **partial copy** of the findings index — colliding with the existing 11th. The canonical series lives in `.project/research/E-276-process-findings.md` and carries 11th–13th. Corrected to **14th**; the epic's table now instructs future authors to take the next number from the research file. **The instanced mechanism is the 12th — *agreement with a derivative is not corroboration* — committed while appending a row to the table that catalogues it.**

- 2026-07-26: **RED-TEAM ARTIFACT REPAIRS R2–R5 (PM, pre-dispatch).** Status stays **READY**; **no design change**, and nothing here alters what ships. R1 is handled separately (SE-R1 / DE-R1) and arrives later as an AC-14 rewrite; story 01's AC-14 and its "holds under both regimes" DoD line were **not touched** by this round. **All four premises were verified against the files before acting; all four held, two with corrections to the brief's characterisation.**

  1. **R2 — story 05 AC-9 gains a second sanctioned flag on the data-engineer memory.** Its line 23 justifies the roster exemption on *"a wrong delete self-heals"* and *"the operator ruled prefer-deleting on that basis"* — **both framings the roster banner explicitly retires** (*"permanent-while-broken, not self-healing"*; *"re-derivability is NOT what carries the case"*). Scoped to the first sentence only: the second (*"Do NOT port this to `player_game_*`"*) is correct and must survive. **Not covered by IDEA-187**, whose surviving scope after two deflations is structural.

     **⛔ The AC as written would have SUPPRESSED this flag.** It said *"one residual … Flag that, and nothing else in this file"* — while sanctioning a second one four paragraphs below. The prohibition, not the count, was the active harm. **A closed-set instruction has to be re-counted every time the set grows, and nothing in the sentence signals when it has** — the 9th mechanism, in the imperative mood.

  2. **R3 — story 01 AC-12 now reconciles the mandated assertion change with AC-6's opt-in requirement.** The tension was **real and unstated in all three sites**: AC-6 and TN-1(c) require vacuous-permit to be opt-in, so `crawl_is_authoritative(fetch_ok=True, fresh_count=0, prior_count=0)` — the call SC-2 and TN-13 both print — **does not invert**. Resolution: the pinned test is **repurposed** to the opted-in configuration and a **sibling** test holds the default-off refusal, which is the position protecting the roster grain's shared fetch-ok use. **The sibling is an addition, not a second changed assertion**, so SC-2's epic-wide total of two is unchanged. *(The brief attributed the "restores the bug" stake to AC-6; that phrasing is AC-7's. The tension it named was right regardless — a verdict can be right on an imprecise premise.)*

  3. **R4 — ACCEPTED, and the brief marked it only "recommended".** New **story 03 AC-5b** pins the consequence of an empty `previously_rostered_ids`: the cap sees zero departures and permits at any size, so post-V1 it **disables the sole guard** where today the floor still refuses. The fixture is the existing catastrophic-shrink shape with **one input varied** and opposite outcomes. Its empty branch **discriminates** (0 retired pre-fix, 12 post-fix) and the DoD says so. **AC-9(a)** now names the two prose sites that say "disables the cap" — the `previously_rostered_ids` Args entry and the `scouting_loader.py` snapshot comment. Accepted because `.claude/rules/testing.md` already binds here (*"when a change makes an input load-bearing, go re-read the tests asserting it is NOT"*) and story 03's Notes already invoke it for a test that **will keep passing** while its subject becomes the only guard on the grain.

     **This produced a file-list finding the repair itself surfaced**: `scouting_loader.py` was listed on story 03 as *"conditional, and only under TN-17's second sanctioned means"*, which would have made AC-9(a)'s required prose edit **unreachable whenever the implementer chose the spy means.** Split into an unconditional prose edit and a conditional code edit. Story 02 already modifies that file unconditionally and blocks story 03, so no ordering changed.

  4. **R5 — test-file line-number citations swapped for test-name anchors** in TN-13's inventory table and its verdict row, story 01's file list, and story 03's AC-7 and Notes. **Every one of the nine call-site line numbers resolved correctly**, so this is rot-prevention, **not a stale-citation finding** — but each story adds tests to the file it then churns, and `tests/test_reconcile_at_load.py:191` was cited by story 03 while story 01 edits that file, a **cross-story** rot. **Deliberately NOT swept — RATIFIED by the team lead, and recorded here so a later sweep does not "fix" them**: `reconcile_at_load.py:1364` and `epic.md:308`, both quoted *as examples of rot* where the stale number IS the evidence; and story 05 AC-9 / IDEA-187's *"line 21 of 35"*, which is a **positional claim about a file's structure** — the finding is that the rule and its scope sit far apart with no pointer between them — not a citation anyone follows. **Converting any of the three to a stable anchor would destroy what it is there to show.** The general rule: a line number is a citation when a reader is meant to GO there, and evidence when the reader is meant to see that it MOVED or that a distance exists. Sweep the first kind; preserve the second.

     **The re-anchoring surfaced something the numbers concealed**: the roster grain's two "mechanical churn" sites both sit inside `test_previously_rostered_ids_scopes_the_cap_population` — the same test whose MEANING V1 changes, and the same parameter AC-5b now pins. One function, three obligations, previously reading as three unrelated items.

     **⚙️ AND THE RATIONALE DEMONSTRATED ITSELF INSIDE THE SAME SESSION — executed evidence, not predicted risk.** While R5's argument was being written, **`epic.md:394` rotted to `396`**: an agent read the player-line grain row at 394, concurrent PM edits moved it, and 394 now lands on the table's `|---|---|---|` separator. **The rule was written against a hypothetical and was falsified into a fact within the hour, on the same file.** Worth recording because a rule of this kind is normally defended only by the incident it prevents — which, by construction, never happens. Here it happened.

- 2026-07-25: **READY RE-AFFIRMED on the operator's authorization.** The hold below is discharged; the Status block is authoritative. **Six review passes, 19 findings, 0 dismissed** — every one fixed on the closing route rather than the self-consistency route. **Dispatch remains a separate operator gate and is not implied by this line.**

- 2026-07-25: **PRE-DISPATCH AMENDMENT (PM successor, 5th), after an independent READY verification returned five items.** No design change. **READY deliberately NOT re-affirmed** — see Status. *(⚠️ **That hold was TRUE when written and was discharged by the entry above** — the operator authorized READY after four further passes. Left standing rather than edited, because it records a real decision and its reason; **but note it is exactly the shape this epic documents — a claim accurate at authoring, falsified by an event that never touched it.** A reader following its "see Status" pointer lands on the current state, which is why the pointer was written that way.)*

  **Four items actioned, one DECLINED on the file's own evidence:**

  1. **Multi-run ACs added at the two grains that lacked them** — **01 AC-14** (player-line: the no-ratchet property, N ≥ 4 invocations, per-run prior count, production scale) and **02 AC-11** (game: the cross-perspective twin-accumulation shape, with `refused_by == "gate"` at the boundary). TN-16 had promised this construction and **only story 03 delivered it.** ⚠️ *(**The "no-ratchet property" named here was FALSIFIED at the R1 disposition** — see the 2026-07-26 R1 entry above. This line is left as an accurate record of what THIS round did; it is not a live description of AC-14. Annotated rather than rewritten, because a History entry silently updated to match a later verdict destroys the record of what was believed when.)*
  2. **The twin-accumulation threshold recorded in TN-16** — `permit iff P >= X + g` [DERIVED, PM, not executed], with its space (`FLOOR_RATIO = 0.5`, protection applied after the gate), the consequence that **the fix binds sooner by exactly `N`** (a TN-5-scoped availability effect, *not* a neutrality violation), and the measured occupancy (~4%, E-270) that puts production far from the boundary.
  3. **The `0..8` roster sweep now carries its range disclosure**, matching its game-grain neighbour — and the addition notes the disclosure binds in **both** directions: a short range flatters a zero count and deflates a non-zero one.
  4. **IDEA-187 deflated a second time**, in the file and in the index row, plus the **story 05 AC-9** correction that followed from it.

  **⛔ ITEM 3 OF THE VERIFICATION WAS DECLINED — story 01 AC-9b's punt rationale is CORRECT.** The challenge held that the game-grain accumulation shape refutes *"the roster grain is the only one where the slip's consequence is demonstrable."* It does not: the slip differs from the correct form by exactly **`W − fresh`**, which is **empty on game and player-line** under the epic's own `W ⊆ fresh` discriminator, so the slip is a strict no-op there. The rationale survives and now **carries that premise** in both TN-16 and the story, converting an assertion into a derivation. **The two mechanisms are different objects** — twin accumulation is about the gate's *denominator*, the slip is about the *classification universe* — and conflating them is what made the challenge look sound.

  **The finding worth carrying from this round: an ABSENCE is invisible to every sweep this epic built.** The final sweep reported *"not one [defect] was in an AC"* and was **accurate**; the multi-run gap was three ACs that were never written, and **no term sweep detects an AC that does not exist.** Two contributing shapes, both structural: TN-16's assignment column said *"each grain story"* — **a story CLASS, not named ACs, so there was nothing to tick off and three stories could each assume another carried it** — and the row's own title said *"at every grain **that keeps one**"*, which under this epic's own idiom (*"the two grains that keep a gate"*) reads as promising it at **exactly the two grains that omitted it** while excluding the one that delivered. **A requirement addressed to a category is a requirement nobody owns**; the port row now names all four ACs individually.

  **And the self-referential count went stale a second time** (~1,300 → ~1,855 → **1,919**), by the file *growing* rather than by anyone editing the sentence — the one failure mode a count about its own container has, and the one with no natural trigger.

- 2026-07-25: **READY (PM successor, 4th).** Three passes: the P3 mechanics migration, the final consistency sweep, and the scorecard.

  **P3 — mechanics moved out of ACs into Technical Notes, MOVED not deleted.** Story 01 AC-2's per-grain patch-site paragraph now states the observable outcome (assert positively that the spy captured a result object) and defers the mechanism to TN-17's table, **which was verified to carry all of it before the source was stripped.** Story 03 AC-4's `_roster_warnings()` prohibition moved to TN-11's log-assertion subsection, beside DE's probe failure it is an instance of; TN-11's citation of "story 03's AC-3" was corrected to AC-4.

  **⛔ THE FINAL SWEEP FOUND A NON-EMPTY TOP-LEFT CELL: 26 live assertions in `epic.md` carrying superseded design, plus 4 repairs each to IDEA-186 and IDEA-187 in both index row and file.** Full result in the banner subsection and the READY Scorecard. **The bottom row was left untouched throughout.**

  **Three things to carry, and the first is the one that generalises.** **(1) Every hit was in a Technical Note or a tracking artifact; not one was in an acceptance criterion.** When the conjunction was dropped the stories were swept and their upstream was not — so a reviewer checking the ACs, which is where the banner's warning pointed, would have found them clean. **The surface that gets swept is the surface someone thought to sweep, and the ACs were that surface twice.** **(2) The sharpest hit inverted an instruction**: TN-16 told an implementer to assert *refused, zero deleted, two pre-existing rows surviving* for the whole-set construction — the conjunction-era outcome — where story 03 AC-2 requires **22 retired including exactly 2 pre-existing**. Not a stale description but a working instruction pointing the wrong way. **(3) Precondition (c) stated the prohibited conjunction shape as a live precondition, four lines below precondition (a), which had been rescoped in the same pass** — finding K in live form, inside the note that catalogues it.

  **Two method notes.** A `conjunction` count of **55** against a relayed **~54** was resolved by enumerating and adjudicating all 55, never by reconciling the number — the gap is a units artifact (the tool counts matching *lines*), which is TN-13's own "the measurement method has to match the claim's unit" in a new dress. And **reading a line back after editing it caught a second stale claim in the same line**, on the half the edit had not touched: TN-13's *"TN-5(a) requires the legacy half to keep today's semantics"*, sitting beside a correction I had just made. Block-edit hygiene found a sweep defect the sweep had missed.

  **Also discharged this round**: TN-5's CHECKED-ABSENCE bullet, which said it *"cannot be finalised until the roster design is"* after the roster design was finalised; TN-1(a)'s box of *"two things left unspecified for roster, both the implementer's call"*, both of which turned on a corrected roster gate V1 does not have; and TN-16's `t_divergence_sweep.py` port row, which story 03's Notes had asked to be corrected.

- 2026-07-25: **FINAL TRIAGE ROUND (PM successor).** The process findings this round produced are extracted to `.project/research/E-276-process-findings.md` — the divergence-count gap's three wrong reconciliations and the arithmetic check that beat all three, the handoff artifact that kept growing after the brief was built from it, and the count asserted inside the correction of a count. What follows is what was decided.

  **⛔ THE ROSTER-LOCK FIX-NEUTRALITY CLAIM WAS RETRACTED THIS ROUND — the epic is NOT READY.** A code-reviewer counterexample against the final spec shows **E-276 creates a new route into the permanent roster lock**, needing neither a truncated crawl nor churn: today's code converges to a clean roster where the fix strands three players and the cap then refuses forever. Retracted in TN-5, IDEA-186 and its README row; *"clutter identical to today"* struck from the under-deletion comparison, because that dismissive adjective is what made the direction sound not worth checking. **Two things to carry.** The chain is TN-3's own, run in the direction nobody ran it — **ruled out via the CANDIDATE population, never re-checked through the GATE.** And the evidence was over-read: DE's five-run trace is executed and step-identical *for the input it ran*, while fix-neutrality is universally quantified — **a trace is one input, and the quantifier attached itself silently.** Deletion-neutrality is untouched and still holds; conflating a property proved in one direction with safety in both is how this survived.

  **⚠️ SCOPE, added when the History was trimmed — read this before treating the paragraph above as a live blocker.** That finding is against the **CONJUNCTION**, and it is *why the conjunction was dropped* (see the drop entry below, and `.project/research/E-276-roster-design-record.md` §4, whose heading is literally "Why the conjunction was dropped — the roster lock"). Under the shipped roster design there is **no floor to refuse**, so the specific route described above — refusals stranding rows that then trip the cap — has no first step. **ANSWERED — see TN-5's three-bucket disposition, which is where the current statement lives.** The F1 route is **(a) closed**; the 3-or-more-departures lock is **(b) pre-existing and unchanged**; and **(c) is NOT empty** — one identified candidate with unverified reachability, plus the structural finding that the monotonicity argument which would empty the bucket is **false**, because `exempt` is computed from the roster rather than supplied to it. **Do not read this entry as "the lock is gone"**, and do not summarize the disposition to a verdict — the three buckets have different statuses and collapsing them loses two of them.

  Also landed this round: the Background reachability boundary **scoped to the over-deletion direction** (a counterexample exists in the churn-inflation direction — the epic's own decisive-turn construction, `P`=10 / fresh ⊆ `P` with 8 survivors / live 30, where both stated conditions are false and the gates diverge anyway); the roster **sizing rule** `a < b ≤ 2 ⟹ pre-load roster ≤ 3` placed in TN-11 beside the fixture table, because a third worked example does not make a fourth derivable and a rule does; the **gate-outcome record's type and fields** specified in TN-11, closing a gap where three stories required a record none of them defined (*requiring* and *defining* are different gaps); an **operator-facing which-gate-refused AC** on each grain story; explicit **02-before-03 ordering** on the file they share; and two superseded shapes still living in story *implementation guidance* — story 02's "to compute the intersection" and story 03's "roster carve-out" — both prohibited by TN-1's own banner and both missed by a 24-finding triage, which is mild evidence the banner is not being swept against mechanically.

  **Count corrections in TN-13**: *"13 direct `crawl_is_authoritative` calls"* re-measured to **7 call sites across 6 test functions** (no reading recovers 13; executions counting the parametrize expansion are 9). The note's other three counts — the 9 helper call sites with their per-file split, the 72 as 34 + 20 + 18, and the 19 — **all verified correct**.

  **The which-refuser AC was drafted as an addition and reading the source inverted it into a PRESERVATION.** The refusal messages are not undifferentiated: all three grains already emit a comparable/prior/floor triple, and `retire_absent_games` carries an explicit comment stating its three causes are *"named apart"* because *"the remedies differ."* Adding a refuser degrades that silently — the enumeration stops being exhaustive while the comment asserting it stays on the page. Two concrete signals at stake: the player-line grain's `18 of 18`, the exact healthy-looking message that hid this bug, and roster's `roster_db_count`, **the tell the original audit used**. Two prose sites were added to TN-9 off the back of it.

  **One reclassification worth its own line, because it changes what story 05 hands to claude-architect.** The three-instance pattern is now **two** instances plus one prior case: `crawl_is_authoritative`'s docstring is a **stale contract**, and `.claude/rules/python-style.md` already carries that class *and* the sweep it prescribes. Counting it as a third instance of a mechanism we have no rule for would have invited a second rule for a class already written down — the context layer paying twice. Stated at the weaker strength this leaves ("two, plus one already covered") rather than preserved at three, and this is the **fifth** bounding of a blanket claim on this surface, consistent with the standing prior that unbounded rules here need boundaries more often than retractions.
- 2026-07-25: **⛔ THE CONJUNCTION WAS DROPPED — THIS SUPERSEDES THE ENTRY BELOW, WHICH RECORDS THE SETTLEMENT IT REPLACED.** Recorded as its own entry because the entry below states the conjunction as settled and would otherwise read, to a later agent, as the current design. Per the banner at the top of Technical Notes and `.project/research/E-276-roster-design-record.md` §1 and §10: **corrected gate (pre-upsert snapshot population) on GAME and PLAYER-LINE; NO floor ratio at all on ROSTER; the conjunction is dropped as inert everywhere.** The roster grain's shape is `permit = (fresh payload non-empty) AND (|absent ∩ previously| ≤ MAX_ROSTER_DEPARTURES)`, on the operator's ruling to invert the bias on that grain — so **it ships with less gating than it started with, deliberately.**

  **What this leaves outstanding, stated so the drop is not mistaken for a completed reconciliation**: stories 01 and 02 and several Technical Notes still carried conjunction-shaped text when this was written, and **TN-5's blanket deletion-neutrality sentence is not merely weakened by the drop — on roster it is INVERTED** (DE's construction: 10 rostered, fresh drops 2, 20 churn → today refuses and deletes 0; V1 permits and deletes 22, two of them pre-existing). That is the ruled outcome and correct. **TN-5's replacement text and its per-grain evidence tiers were HELD at the time of this entry** pending SE and CR-2 settling whether game/player-line neutrality is structural (via `W ⊆ fresh`) or swept — see the Technical Notes for the resolved form, and do not infer a tier from this entry.

  **The banner warned about exactly this and the stale ACs survived anyway.** `epic.md`'s Technical Notes banner declared the conjunction dropped and declared the affected AC phrasing stale, in the file's own text — and stories 01 and 02 still carried it. **A warning is not a sweep**, and to a later reader a banner saying "the text below is stale" reads as evidence that someone is on top of it. It bought the defect cover rather than removing it.
- 2026-07-25: **Gate semantics SETTLED — SUPERSEDED, see the entry above** — SE's joint recommendation, explicitly endorsed by DE, which withdrew its competing position and named its own superseded artifacts. Conjunction gate, candidates unchanged, no intersection, blanket deletion-neutrality. Reached after gate semantics were deliberately held OPEN through four successive positions that were each relayed as settled and each retracted (intersection load-bearing → intersection as fail-closed insurance → intersection withdrawn entirely → deletion-neutrality as a global property). Every retraction corrected a real error, so the convergence worked; what repeatedly failed was snapshotting it mid-flight into a spec. **Holding the sections stubbed rather than writing whichever position arrived last is what kept three false safety claims out of this document.**
- 2026-07-25: Created as DRAFT. Consultations complete (DE, SE, SE-2; api-scout and baseball-coach waived with reasons above).
- 2026-07-25: **Numbered E-276 rather than E-275.** E-275 was already reserved for the P2 classifier-hardening epic by predecessor artifacts — baseball-coach memory (`e275-classifier-hardening-rulings.md`, filename plus in-body references), PM memory, the 2026-07-25 session handoff, and two ux-designer artifacts — roughly 18 references across committed files. Renumbering those was judged more expensive than skipping a number. The on-disk gap between E-274 and E-276 is deliberate, not a lost epic.
