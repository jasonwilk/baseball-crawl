# IDEA-186: One Truncated Roster Crawl Can Permanently Lock the Roster Retire

## Status
`CANDIDATE`

## Summary

A single truncated roster crawl puts the roster-grain retire into a **permanent** whole-set refusal that blocks all later genuine departures. Once locked it does not self-heal when the crawl recovers.

**Reproduced through the real `ScoutingLoader`, not inferred** — see Notes for the five-run trace. The hedged phrasing this summary carried until 2026-07-25 ("appears to") was accurate when written and was left standing after the evidence arrived; it is corrected here because a hedge outliving its blocker reads as an unverified claim and gets triaged as one.

> ### ⚠️ READ FIRST — THE DESIGN CHANGED UNDERNEATH THE RETRACTION BELOW (2026-07-25, later the same day)
>
> **The retraction below is against E-276's interim CONJUNCTION design, which was DROPPED.** The shipped roster grain has **no floor ratio at all** — its permit is a non-empty fresh payload AND `MAX_ROSTER_DEPARTURES` — so the new route the retraction identifies, in which a **floor refusal** strands rows that then trip the cap, **has no first step**.
>
> **The retraction body is preserved unedited and must stay that way**: it records a real counterexample that is *why* the conjunction was dropped. What follows it is history about a design decision, not a live claim about what E-276 ships.
>
> **⛔ Do NOT compress this to "the lock is gone."** E-276's TN-5 disposes of it in **three buckets** with different statuses: **(a)** the floor route above — **CLOSED**; **(b)** a crawl dropping **3+ genuine departures at once** — **PRE-EXISTING and unchanged**, which is this idea's own truncated-crawl route by a longer path, and is what keeps this idea alive; **(c)** an identified candidate whose reachability is **NOT established empty** — no route was found, which is weaker than a negative result, and the monotonicity argument that would empty the bucket is *false* because the exempt set is computed from the roster rather than supplied to it. Collapsing the three loses two of them.
>
> ### ⛔ RETRACTED 2026-07-25: "pre-existing, and E-276 does not worsen it"
>
> **That claim was FALSE and is withdrawn.** This file, and E-276's TN-5, both asserted the lock was *"pre-existing — not caused by E-276 and E-276 does not worsen it."* A code-reviewer counterexample against E-276's final spec **refutes it: the fix creates a NEW route into this lock**, needing neither a truncated crawl nor backfill churn.
>
> ```
> DB {a,b,c}; cap=2
> Run 1  fresh {a,n1}      legacy 2>=2 PERMIT | cap 2<=2 PERMIT | corrected 1>=1.5 REFUSE
>        TODAY retires b,c -> {a,n1}           FIX refuses -> {a,b,c,n1}
> Run 2  fresh {n1,n2,n3}  TODAY retires a -> clean.   FIX refuses -> {a,b,c,n1,n2,n3}
> Run 3+ healthy crawl, both gates PERMIT.
>        cap: absent {a,b,c} ∩ previously = 3 > 2  -> CAP REFUSES, FOREVER
> ```
>
> **Today's code converges to a clean roster; the fix locks the team-season permanently.** The chain is the same one the trace below shows — the conjunction *adds refusals*, refused rows persist, persisted rows enter the next run's snapshot, and the cap counts them as genuine departures. What changes is the entry condition: E-276 supplies one that today's code does not have.
>
> **It does NOT contradict E-276's deletion-neutrality guarantee**, which is only ever about never *permitting* a deletion today's code refuses. This is the opposite direction — a refusal that compounds. Keep the two apart; conflating them is how the error survived.
>
> **Why it was missed, and it is E-276's own defect class**: the lock was ruled out for the adopted design by reasoning about the **candidate** population and never re-checked through the **gate**. The mechanism was already written down in E-276's TN-3; nobody re-ran it against the conjunction. And the region it lives in is the pre-load roster of 1-3 rows that E-276 itself calls *"not an exotic corner."*
>
> Whether E-276 must close it, or may accept it as a named residual, is an open call for the operator — see Open Questions.

## ⚠️ ONE RÉGIME WITH [[IDEA-188]] — PROMOTE TOGETHER

This lock and [[IDEA-188]] (a roster delete converting a REFUSED dedup fork into an EXECUTED merge) are **the same mechanism seen from two sides.** The **churn-inflated denominator** — today's floor reading a live population while the cap reads `absent ∩ previously` — is the **only** place today's floor is stricter than the shipped design, which makes it simultaneously the place today **locks** (this idea) and the only place removing the floor can **widen** anything (IDEA-188, threshold `c > 2·|fresh| − |S|`).

Executed, in that region: **today** leaves the fork intact and the roster **permanently stranded**; the shipped design breaks the fork and the roster **converges**. Both wrong, neither costless.

Kept as two files because the harms and the candidate fixes differ — this is a liveness failure touching the cap's scoping, that one an identity-corruption failure touching fork exemption. **But promote them together, review them together, and treat a fix to either that does not account for the other as incomplete.** Anything touching `MAX_ROSTER_DEPARTURES`, its scoping, or the roster floor must read both. (Full reasoning is in IDEA-188's matching section.)

## Why It Matters

The roster grain exists so a departed player stops rendering on the coach-facing roster grid as a false lineup option. A permanent lock silently returns the system to that pre-E-267 behaviour (H2) for the affected team-season, with no operator signal beyond a recurring refusal WARN that looks like ordinary bias-to-refuse.

The failure is quiet in the way that matters: it looks exactly like the guard working.

## Rough Timing

Not blocking. **The former gating step — confirming the mechanism through the real loader — is DISCHARGED**, so the remaining triggers are demand-side rather than evidence-side. Promote when any of:

- A coach or the operator reports departed players persisting on a roster grid across several report generations.
- Any future work touches `MAX_ROSTER_DEPARTURES` or the roster grain's cap scoping — the lock is entangled with both, and changing either without understanding it risks making it worse.

## Dependencies & Blockers

- [ ] E-276 lands first — not because it fixes this (it does not), but because it changes the surrounding gate and any repro should be written against the post-E-276 code so the finding does not go stale immediately. **Sharpened 2026-07-25**: E-276 additionally *adds* an entry route (see the retraction), so a pre-E-276 repro would not even cover the same population. Whether E-276 closes its own route is that epic's open call.

*(The former blocker — "mechanism not verified through the real producer" — is **DISCHARGED**. DE reproduced it through the real `ScoutingLoader`; see Notes.)*

## Open Questions

- ~~Is the entry condition really a truncated crawl, or is that one of several routes in?~~ **ANSWERED 2026-07-25: no.** A truncated crawl is one route; the counterexample above is a second, needing no truncation and no churn — **and E-276 introduces it.** The general entry condition is *any refused run whose refused rows then enter the next run's snapshot*, which makes every refusal a potential entry point rather than only the degraded-crawl case.
- ~~**NEW, and it is E-276's to decide**: does E-276 close its own route, or accept it as a named residual?~~ **ANSWERED 2026-07-25 (later the same day) — by design change rather than by ruling.** The conjunction was dropped and the roster grain ships with no floor, so the route E-276 would have had to close **no longer exists**: bucket (a) is CLOSED because a floor refusal is its required first step. **What remains open is bucket (c)** — a candidate route with unverified reachability, closed by exhaustion of the cases anyone could construct rather than by proof. E-276 records it as *"not established empty"*, deliberately weaker than *"no route exists."*
- What is the intended recovery path? Today there appears to be none short of operator intervention.
- Should the cap's genuine-departure scoping exclude rows that survived a *refused* run specifically? That targets the mechanism directly — but it is a cap change, which E-276 deliberately declined to touch.

## Notes

**Evidence and its tier — carry this caveat with the finding.**

Observed [EXECUTED, data-engineer, self-audit] with today's code and E-276's conjunction gate run **side by side and byte-identical, including which gate refuses at each step** — **on THIS input.** That step-identity is real and is not withdrawn; what is withdrawn is the general conclusion drawn from it. **Byte-identical behaviour on one entry route is not fix-neutrality across all routes**, and the counterexample in the retraction above is an input on which the two regimes differ decisively. The trace establishes the *truncated-crawl* route is shared; it never had the power to establish there is no other:

```
                          refused_by   roster   churn_in_roster
run1 NORMAL (13/13)       none         13       0
run2 TRUNCATED (2/13)     gate         16       3    <- refuses; churn SURVIVES
run3 crawl RECOVERS       cap          16       3    <- gates PERMIT; the CAP refuses
run4 RECOVERS again       cap          16       3
run5 genuine departure    cap          16       3    <- real departure NOT retired
```

**Mechanism — EXECUTED at loader tier, and it is the CAP, not the gate.** Churn rows created by the boxscore jersey backfill survive a refused run, enter the *next* run's pre-load snapshot, and are then counted as genuine departures by the cap's `absent & previously` narrowing — 3 against a cap of 2 — refusing permanently. In normal operation churn never enters the snapshot, which is why it only triggers after a refusal.

**Evidence tier note, kept because the practice was right.** DE first established this by simulating the gate and cap, flagged that tier itself rather than letting it inherit the credibility of the executed results beside it, and then re-ran it through the real `ScoutingLoader` when asked. **The flag is now discharged** — the mechanism is executed, both regimes step-identical. The tier caveat is recorded rather than deleted so the record shows a correct flag being retired by evidence.

**A superseded account, recorded so it is not revived.** An earlier explanation attributed the accumulation to the corrected gate's ratio being self-reinforcing, with a boundary of `|snapshot ∩ fresh| < 0.5·|snapshot|` and a claim that the transient path does not lock. **Both are refuted**: after the crawl recovers *both gates permit* and the **cap** is what refuses, and the transient path is exactly the entry condition. If someone re-derives the ratio story, this is why it is wrong.

Surfaced during E-276 planning and deliberately kept out of that epic: filing it there as an "accepted consequence" would have wrongly implied E-276 caused it. **That reasoning is now partly overtaken** — E-276 does not cause the *truncated-crawl* route, but it does create a second route (see the retraction). The idea stays here rather than moving into the epic, because the lock is genuinely wider than E-276; what belongs in the epic is the **decision about its own route**, not the whole finding.

**A methodological note worth more than the correction, and it is the general form of the mistake this file made.** The step-identical five-run trace is strong evidence and was read as stronger than it is: *executed, byte-identical, both regimes side by side* reads as settling the question, when it settles it **for the input that was run**. A fix-neutrality claim is universally quantified; a trace is one input. Nothing about the evidence was wrong — only the quantifier silently attached to it. That is the same shape E-276's History records three times over (a true-sounding absolute asserted across a space without checking the case that violates its premise), and here it was committed by an idea file written to record one of those instances.

Related: [[IDEA-185]] (the other roster/player-line retire residual routed out of E-276).

---
Created: 2026-07-25
Last reviewed: 2026-07-25
Review by: 2026-10-23
