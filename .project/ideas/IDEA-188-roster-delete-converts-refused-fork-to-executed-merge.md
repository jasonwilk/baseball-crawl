---
name: idea-188-roster-delete-converts-refused-fork-to-executed-merge
description: A roster-grain delete silently converts a REFUSED player-dedup fork into an EXECUTED merge in the same run, bypassing refuse-don't-guess with no signal. Pre-existing; unchanged by E-276.
metadata:
  type: project
---

# IDEA-188: A Roster Delete Silently Converts a REFUSED Fork Into an EXECUTED Merge

## Status
`CANDIDATE`

## Summary

> **A delete in the roster grain silently converts a REFUSED fork into an EXECUTED merge.**

`plan_player_dedup` **refuses** a fork — a stub prefix-matching two or more distinct fuller names — because prefix matching cannot tell one human from two ("refuse, don't guess"). The roster-grain retire runs **before** the dedup sweep in the same load, and **fork members are not exempt from it**. So when the retire deletes one maximal member, it **destroys the ambiguity that caused the refusal**. The planner then sees an unambiguous pair and merges.

The refusal is bypassed by another grain's delete, in the same run, **with no signal** — no WARN, no result flag, nothing distinguishing it from an ordinary merge.

Executed end-to-end:

```
1  intact fork, dedup runs      batting=[janet:3, john:4, jstub:2]   roster=[janet, john, jstub]
2  retire deletes Janet         batting unchanged                    roster=[john, jstub]
3  SAME RUN, dedup sweep        batting=[janet:3, john:4]            roster=[john]
4  next healthy crawl restores  batting=[janet:3, john:4]            roster=[janet, john]
```

**Step 4 is the damaging part**: the recovery crawl restores the roster row and **does not restore the merged-away stat row or un-merge the identity.** `team_rosters` is re-derivable; a merged `player_game_*` row is not.

## Why It Matters

`merge_player_pair` is **delete-or-update**, so a wrongly-executed fork merge splits by branch — and one branch corrupts totals:

| Case | Effect | Team sums |
|---|---|---|
| Fork **REFUSED** (intended behaviour) | split per-player line; one human's season understated | **correct** |
| Fork **BROKEN**, the two ids share a game | colliding stat rows **DELETED** — stats destroyed | **WRONG, low** |
| Fork **BROKEN**, distinct games | rows re-pointed; canonical line **inflated** | correct; the other human's season vanishes |

**In a real id re-issue both broken branches occur across a season.** The reassuring summary that "team sums count each at-bat once either way" is true of the **refused** case only.

The stakes are the ones `plan_player_dedup`'s refusal exists to protect: merging re-points `player_game_*` rows from one human onto another — **stat misattribution that no crawl recovers, because the source rows are gone. A duplicate roster row is a display artifact; a wrong merge is corrupted history.**

## ⚠️ ONE RÉGIME WITH [[IDEA-186]] — PROMOTE TOGETHER, AND DO NOT FIX ONE WITHOUT THE OTHER

**This idea and [[IDEA-186]] are the same mechanism seen from two sides**, and DE's point that filing them apart hides it is correct. The **churn-inflated denominator** — today's floor reading a live population while the cap reads `absent ∩ previously` — is the **only** place today's floor is stricter than V1. That makes it simultaneously:

- the only place removing the floor can **widen** anything (this idea's threshold, `c > 2·|fresh| − |S|`), and
- a place where today is **already broken** (IDEA-186's permanent lock).

Which is why the two appear as a trade rather than a regression: in that region today strands the roster permanently and V1 breaks the fork.

**PM call — kept as TWO FILES, deliberately, and the reasoning is here so it can be overruled.** The régime is shared but the *harms* and the *fixes* are not: IDEA-186 is a liveness failure (a roster that never updates again) whose candidate fixes touch the cap's scoping; this is an identity-corruption failure whose candidate fixes touch fork exemption or merge-time ambiguity. Collapsing them into one idea would force one disposition onto two different decisions. **What was missing was not a merge — it was this section.** Binding instruction instead:

> **Promote them together, review them together, and treat a fix to either that does not account for the other as incomplete.** Anything touching `MAX_ROSTER_DEPARTURES`, its scoping, or the roster floor must read both.

## Rough Timing

Not blocking. **Pre-existing and not widened by E-276** (see Dependencies), so there is no deadline pressure. Promote when any of:

- Player-dedup work is next opened — [[IDEA-089]] (Tier 2 co-occurrence fork disambiguation) is the natural carrier, since a real co-occurrence signal would let the planner keep refusing on evidence rather than on ambiguity that a delete can erase.
- A coach or the operator reports a player's season stats disappearing or a line looking inflated.
- Any work changes the **ordering** between the roster retire and the dedup sweep, or makes fork members exempt from the retire — both touch this directly.

## Dependencies & Blockers

- [x] **Confirmed PRE-EXISTING.** Today's code fires the chain identically. Established by execution, not inference. **This leg is what keeps it an idea rather than a blocker.**
- [x] **⛔ V1 DOES WIDEN IT. A "not widened" claim was filed here and is RETRACTED.**
- [ ] Nothing blocks investigation. A fix needs a design decision (below), not new evidence.

**THE WIDENING — retracted claim and its correction, recorded because the retraction is more instructive than the fact.**

Executed at loader tier — a 13-row roster containing the fork trio plus 10 unrelated players, fresh crawl dropping one player, `c` jersey-backfill churn rows:

```
c=10  today refused=False  janet_gone=True   fork_merged=True
c=10  V1    refused=False  janet_gone=True   fork_merged=True
c=14  today refused=True   janet_gone=False  fork_merged=FALSE   <- fork INTACT
c=14  V1    refused=False  janet_gone=True   fork_merged=True    <- breaks under V1 only
```

Today refuses iff `|fresh| < 0.5(|S| + c)` — with `|S| = 13, |fresh| = 12`, that is **`c > 11`**. **At normal roster size with heavy churn, today's floor refuses (live-population denominator inflated by the churn) while V1's cap sees one genuine departure and permits.**

**The structural argument is NARROWED, not refuted, and the distinction is the finding.** The derivation was sound; it rested on an **unstated premise: churn = 0.** With churn present, today's floor denominator is the **live** population (`snapshot + churn`) while the cap counts only `absent ∩ previously` — the two diverge, so the step `survivors < absent ≤ 2 ⟹ stored ≤ 3` fails because it silently assumed both guards read the same population. **The honest form: no widening in the churn-free case.**

**MISSED or EXCLUDED? Excluded — parameterization, not coverage.** The sweep covered `{stub, m1, m2}` + 0-11 unrelated rows and every absence subset **with churn at 0**; the independent search covered the ≤3-row region, **also churn-free**.

**⚠️ THE WIDENED REGION SPLITS INTO THREE RÉGIMES — a one-trade summary of it was shipped and corrected.** Today **LOCKS** at `c > R` but refuses **DEPARTURES** from `c > R − 2`, because a healthy run compares `R` against `0.5(R + c)` while a departure run compares `R − 1`. Executed at `R = 13`:

```
c    healthy_refused  churn_left_after_healthy  departure_refused  janet_alive
11      False                 0                     False            False
12      False                 0                     True             True     <- BAND
13      False                 0                     True             True     <- BAND
14      True                 14                     True             True     <- LOCK
```

`churn_left_after_healthy` is decisive: in the band today clears **all** churn on a healthy run — **functioning normally, refusing only the departure**, not locked.

| régime | today | V1 | the trade |
|---|---|---|---|
| `c ≤ R − 2` | permits | permits | no widening |
| **`R − 2 < c ≤ R` (BAND)** | healthy; churn clears; **stats untouched**; the player stranded on the grid | player retired correctly; **fork breaks; a stat row destroyed or misattributed** | **grid clutter vs a CORRUPTED STAT** |
| `c > R` | locked ([[IDEA-186]]) | converges | the ruled trade — both permanent |

**Why the band changes the disposition rather than decorating it.** `retire_departed_roster_players`' own docstring says this grain's failure mode is *"grid clutter, **never a corrupted stat**, which is what separates this grain from the game and player-line grains."* **In the band, a roster-grain delete produces exactly the corrupted stat that sentence rules out** — and the operator's prefer-delete ruling rests on roster failures being recoverable grid-level issues. *"The same trade already ruled on"* **claims a coverage the ruling does not have.**

**Still not a blocker**: the band is **two values of `c` for any roster size** and **its occupancy is unmeasured** — which is the first thing to measure if this is promoted. At `c ≥ R + 1` the original argument stands untouched.

**How the correction was found, and it is the third instance today**: a reviewer checked the *reason* rather than the verdict. The reason had been stated precisely so it could be checked, and it was — **the conclusion survived at `c ≥ R + 1` and the scope was wrong again.**

**The retraction's transferable lesson**, in its author's words: the sweep confirming the original claim was run *to verify another agent's result* and **reproduced that agent's blind spot** — *"I did not verify your claim. I reproduced your blind spot with different arithmetic."* Two agents, one fixed axis, and **the agreement made the claim more credible than the original rather than testing it.**

**And the lesson is one level up from where it was first recorded**: it was reported as *"a finding's disposition needs its own control run"* — but the control run **was** made (today vs V1); the **control itself** was under-covered on the churn axis. Correct form: **a control run needs its own parameterization check.**

## Open Questions

- **Exempt fork members from the roster retire?** Cleanest-looking fix and it mirrors the existing `exempt_player_ids` mechanism — but it makes a *fork* into a retire-blocker, which is a new coupling in the opposite direction, and E-276 established that the exempt set interacts with gate populations in ways that are hard to characterise.
- **Or re-check ambiguity at merge time**, so the planner refuses on the *pre-retire* component rather than what survives it? That preserves refuse-don't-guess without giving dedup a veto over the roster grain.
- **Should the conversion at least be LOUD?** It is currently indistinguishable from an ordinary merge. A WARN naming "this component became mergeable because a member was retired this run" is cheap and would make the population measurable before anyone designs a fix.
- How often do live forks actually co-occur with a roster departure in the same run? Unmeasured — and per E-276's standing discipline, that measurement should precede a design rather than follow it.

## Notes

**The coupling that hid it.** E-276's artifact listed the three `DELETE FROM team_rosters` paths — `retire_departed_roster_players`, `_delete_or_update_rosters` (the merge), `_delete_team_scoped_data` — as **independent surfaces**. They are **coupled**: the first can *trigger* the second inside one run. Understating that is what let the chain go unnoticed, and it is why "enumerate the delete paths" was not sufficient without asking which ones can cause each other.

**How it was found, and the sequence is the lesson.** A reviewer *derived* the chain and filed it explicitly as DERIVED, naming the experiment precisely enough that running it was mechanical. Software-engineer ran it and confirmed. **Neither the reviewer nor data-engineer would have caught it by reading** — both had the false sentence *"V1 does not lose data there"* in front of them repeatedly. The qualifier was invisible from inside the case that produced it.

**And a disposition error worth carrying**, in its author's words: the finding was first reported as *"a cost of V1 that was mis-stated"* and is in fact *"a pre-existing defect that the wording mis-stated."* The reporter shipped a disposition **before checking whether today's code does the same thing** — the same omission as running one leg of a region without its control. **A finding's disposition needs its own control run, not just its mechanism.**

Related: [[IDEA-089]] (the co-occurrence signal that would make fork refusal evidence-based), [[IDEA-185]] (partial id churn — the other player-identity residual routed out of E-276), [[IDEA-186]] (the roster cap lock — same class: pre-existing, unchanged by the design, filed rather than folded in).

---
Created: 2026-07-25
Last reviewed: 2026-07-25
Review by: 2026-10-23
