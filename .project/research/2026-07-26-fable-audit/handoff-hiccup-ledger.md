# Handoff hiccup ledger (running; classified per eval protocol axis D)

## E-276 DISPATCH PHASE (2026-07-26/27)

7. Hub SKIPPED the "and review" Codex pass (Phase 4), sent CR straight to
   Phase 5. Caught by the OPERATOR (four-word question), not a gate. Recovery
   high-quality: CR held so it adjudicates Codex findings with the final diff
   (the approve-then-reverse failure the ordering exists to prevent; 3 prior
   epics). Classification: LAYER/procedure-fidelity + probable compaction
   assist (post-compact skill = relayed procedure).
8. Hub stopped at the closure COMMIT and dropped steps 7-11 (worktree/branch
   removal, shutdowns, straggler sweep); operator prompted twice. Hub's own
   diagnosis, verbatim-worthy: "I treated the procedure as a list of things to
   report on rather than a sequence to execute" and "I was the one participant
   with no second party checking my sequencing." n=2 same class, same epic ->
   promoted to the layer pass as deliverable 4b (artifact preconditions +
   checked end-state + navigator-as-sequencing-checker). Note: the navigator
   thread independently flagged the surviving worktree BEFORE the operator
   asked — the two-party sequencing check exists when a navigator is present.
   Also: ugrep silent-empty bit this dispatch TWICE despite its dedicated
   rules paragraph (salience dilution evidence, feeds the rehome mandate);
   CR designed it out with an AST-based sweep (the knowledge works when
   retrieved). Operator raised dispatch send-cap thresholds mid-flight
   (dc1cc9e). E-276 closure commit: bfc614a. Total epic cost: 24.2h span /
   12.0h ACTIVE / 61MB / 21 subagents — vs 2.5-4h / 8-13MB full-epic bands.

## DESIGN CORRECTION (operator reveal, ~22:2xZ): the navigator's bounded-finish
instruction was NEVER RELAYED to P1 — operator deliberately withheld it to observe
the unsteered state. Therefore: ALL P1 behavior after the pivot flag is UNSTEERED.
Reinterpret accordingly:
- P1 is now the CONTROL ARM (zero external structure); P2/P3 run as treatment arms
  (system-encoded protections from workflow-amendment-list.md). This is a better
  experiment than the one I designed.
- The self-derived countermeasures (file-wins, pre-registration, counterexample-
  before-ship, PM drain) emerged with NO steering — strongest possible evidence for
  promoting them: they are what the system converges to when it works, so encoding
  them is codifying the attractor, not imposing a foreign process.
- HONEST SCORING OF MY OWN INSTRUCTION: my STOP condition ("design change -> halt
  and escalate") would have HALTED CR-2's structural-proof round, which was a
  design-premise change AND the most valuable correction of the epic. Unchecked,
  it self-corrected productively. My boundary was mis-designed on at least that
  clause — treated design-premise movement as a failure signal when P1's design
  movements have all been improvements. Carry into the closure eval: score my
  recommendations against the unsteered path's actual outcomes.
- Prior entries reading "the bounded instruction holds/stands" describe an
  instruction that was never active; treat those judgments as predictions, and
  score them, not as descriptions.

## ACCOUNTABILITY (navigator, 2026-07-25 ~22:00): my P1 prompt chose the wrong work
shape. I wrote "plan an epic" — the discovery/committee shape my own corpus data
grades 2-4/5 burden ON EVERY MODEL — for a problem whose discovery I had already
done (mechanism, failing inputs, fix shape, ACs all in the audit). The planning team
re-derived the design space with a committee; the one thing that genuinely needed
deciding (conjunction/roster direction) needed an OPERATOR RULING, not four design
rounds to surface it. P1's 8 relay failures also refute my implicit claim that
bounded PROMPTS bound the work: relay failure follows the HUB ROLE in judgment-heavy
phases, not mandate width. Corrections for P2/P3: (1) hand off implementation SPECS
with decisions pre-made and operator decision points named up front, not "plan an
epic"; (2) shallow teams — minimize relay hops; (3) every brief declares itself a
relay, file wins (2nd independent confirmation; promote to amendment list).

## REDTEAM VERDICT (2026-07-26): DISPATCHABLE-WITH-NAMED-REPAIRS. W⊆fresh premise
survived path-by-path falsification; all central claims reproduced by execution;
roster-ruling honesty verified. F1 (P1-severity): story 01 AC-14 pins a no-ratchet
property the design provably lacks — refusal does NOT stop the upsert (X2: 9+3
churn-refused = 12 rows), so identical churn repeated 3 runs hits the 0.5 floor
exactly and the CORRECTED gate retires all 9 originals, uncapped (X3). Design's
real protection = one-run window + dedup sweep (epic.md:394, stated once, no story
surface). AC-14 unsatisfiable vs correct code, or green only via dedup-mergeable
names (the wrong-reason trap its own file documents).
**NAVIGATOR ACCOUNTABILITY: AC-14 implements MY commissioned amendment item 1. I
specified "originals survive every invocation" — a safety absolute I never
attempted to construct. The P1 team built what I asked; the red team broke what I
specified. AMENDMENT-LIST addition: a reviewer-commissioned AC is a claim the
reviewer AUTHORED — the counterexample-before-ship rule binds verifiers' repair
prescriptions exactly as it binds specs (this is A2 turned on the auditor).**
F2 story-05 AC-9 bans flagging a third genuine retired-claim residue (DE memory
:23 self-heals framing). F3 AC-12/SC-2 vs AC-6 one-sentence reconciliation.
F4 previously_rostered_ids=[] unpinned as sole-guard post-V1 (recommend test).
F5-F7 low. Repairs: 3 story edits + 1 operator-facing sentence; story 01 blocked
until AC-14 rewritten; 02-05 clean.

## P1 READY-GATE VERDICT (2026-07-26, all six pre-registered checks complete):
CONDITIONAL — amend two stories, then authorize. (1) residue sweep PASS (~130 hits,
all bannered-with-replacement or AC-banning; one disclosed DE-memory residue tracked
IDEA-187); (2) TN-5 neutrality PASS all grains incl. unsoftened roster ruling;
(3) multi-run coverage FAIL on game+player-line (TN-16 promises per-grain, only
roster delivers; story-01 AC-9b punt rationale "only roster demonstrable" is FALSE —
audit's game-grain accumulation shape is a demonstrable multi-run consequence);
(4) fixture ranges PASS in ACs (one prose-only undisclosed 0..8 roster sweep at
epic.md:812); (5) executability/citations PASS (every citation resolves; 72-test
count re-derived; fail-first discipline per-AC scoped); (6) design records PASS,
IDEA-187 pointer PARTIAL (its Defect-1 quote is stale vs committed file — the
inherited-claim pattern in miniature, non-blocking).
Amendment-list note: 3rd instance of "TN promises, stories don't deliver, nothing
cross-checks the promise" -> TN-level commitments need promise-to-story sweep at
READY (candidate for spec-review checklist).
Open pre-authorization item: confirm whether Codex spec review ran; if not, run it
on the amended epic (house gate, plan skill standard).

## P1 (health-gate epic) — mid-flight observations, 2026-07-25

1. HARNESS/coordination — SE and DE each reported the OTHER's endorsement of opposite
   positions; hub relayed mid-convergence snapshots as settled 3x, retracted 3x.
   Team-lead's own remedy (halt PM; require ONE artifact both agents explicitly
   endorse; if none, both positions come up for a ruling) is correct and matches the
   layer's existing handoff-artifact lesson. Adjacent to IDEA-175 (two competing
   rulings with equal standing). NOT new layer text yet — recurrence counter: 1 in
   handoff era. If P2/P3 reproduce it, propose one sentence in dispatch-pattern.md:
   "a relayed position is settled only when a single jointly-endorsed artifact exists."

2. MODEL/discipline (but self-caught) — three successive false safety ABSOLUTES about
   deletions ("W ⊆ fresh", "never newly deletes a pre-existing row", "strictly
   narrower"), each asserted cross-grain without construction, inside the very AC
   written to prevent the class. All three killed by constructed counterexamples
   before shipping — the E-272/ground-truth lesson operating as intended. Team adopted
   binding check: any deletion-absolute AC gets an attempted counterexample before it
   ships. GOOD candidate for P1 closure codification (context-layer assessment gate);
   do NOT add layer text from here — it's tool-output-integrity "EXECUTE behavioral
   claims" applied at AC-time, and the epic is already carrying it as practice.

3. PROMPT/LAYER interaction (mine to own) — the conjunction debate exists because the
   team reached for a PROVABLE absolute ("fixed gate never deletes anything today's
   gate refuses"). My P1 prompt did not ask for that AC; it asked for documented-
   semantics restoration + construction-tested refusals. Plausible inducement: the
   layer's bias-to-refuse language reads as "more refusal is always safer," inviting
   monotonicity-vs-today as a safety spec. Bias-to-refuse governs UNCORROBORATED
   ABSENCES, not gate-vs-gate monotonicity against a KNOWN-BROKEN gate. If this
   recurs, the refinement is one clarifying clause where bias-to-refuse is defined,
   not a new rule.

RESOLUTION (same day) — my held input was WRONG; operator correctly never relayed it.
1. The SE/DE "contradiction" was messages CROSSING IN FLIGHT (DE had withdrawn its
   rejection in a message SE hadn't seen) — comms latency, not divergence. Reclassify
   item 1: crossing, cost = one halt + churn; team protocol (jointly-endorsed
   artifact) still the right remedy.
2. The conjunction question was settled BY EXECUTION: discriminating fixtures on all
   three grains show every wrongful deletion (9 player-line / 2 game / 2 roster)
   blocked under the conjunction; the conjunction is a NO-OP on player-line (the
   uncapped grain); the only cost is roster under-deletion identical to today —
   never chartered. The clinching argument: the conjunction's safety guarantee holds
   INDEPENDENT of the corrected gate's semantics, i.e., robust to the team's own
   demonstrated error rate (4 wrong safety claims about this one gate).
3. MY held input repeated DE's backwards framing ("trades away the roster-grain
   correction") without executing it — would have been wrong claim #5, carrying
   audit authority. Lesson for the eval frame: the failure class is
   RELAYED-FRAMING-WITHOUT-EXECUTION and it is model-, tier-, role-, and
   channel-independent — it got the 07-25 hub, DE, SE, the P1 hub (5 self-counted
   relays), and the audit navigator. The ONLY thing that killed claims, every
   time, in every session: construction/execution.
4. Positive signals to carry into the P1 closure eval: hub SELF-diagnosed its relay
   failure mid-flight (07-25 hub needed external catch); SE ran five attacks on its
   own formulation unprompted and promoted the survivor to an AC. PM self-reported
   low context -> graceful drain (bounded tasks, stop) — protocol adopted into
   sub-lead experiment clause 5.

5. OPEN — major mid-epic direction change reported by operator (~late in run, long
   session). Eval questions pre-registered BEFORE seeing the outcome:
   (a) Pivot provenance: does it trace to an EXECUTED artifact (counterexample,
       failing fixture — legitimate discovery) or to argument/re-litigation (drift)?
   (b) Do the original P1 ACs still hold post-pivot (churn refusal both grains,
       positive direction per shipped spec, prose replacements)? Outcome bar is
       unchanged by the pivot.
   (c) Did the pivot re-open anything already settled by execution (the conjunction
       settlement)? Re-litigating executed settlements = drift marker.
   (d) Cost of the abandoned path (turns/bytes) and whether the drain protocol held
       across the long run.
   (e) Judge path from the TRANSCRIPT script-first, not from the session's closure
       narrative — self-characterizations are the one artifact class the audit
       proved unreliable.
   Pre-commitment: session LENGTH alone is not a defect metric (audit finding);
   path quality = necessary-discovery density, not duration.

5b. (~22:1xZ round) Relay defect #9 (hub passed PM3's "neutrality is swept-not-
   structural on two grains" without checking; CR-2 refuted the brief BEFORE
   reviewing — file-wins working a THIRD time). CR-2's structural proof: every row a
   run writes adds 1 to numerator AND denominator of the legacy gate, 1 >= 0.5*1, so
   legacy permits whenever corrected does, at any size — neutrality on game/player-
   line grains is BY CONSTRUCTION; the same premise PREDICTS the roster exception
   (jersey backfill writes rows the fresh crawl never listed -> churn hits legacy
   denominator only). One premise, both results — design simplified into a stronger
   shape. NOTE the navigator was also bitten: I relayed "strongest verification any
   epic carried" citing the 2,197 sweep; CR-2 showed the sweep ranged 0-12 per
   parameter vs 20-30-game real seasons — zero-failure evidence that never reached
   production sizes. Protocol updated: verify fixture RANGES, not counts.
   TWO new amendment-list candidates with named mechanisms:
   (a) brief-is-a-relay/file-wins: now 3 confirmations (PM3, CR-2, plus the E-267
       handoff lesson) — promote at P1 closure codification.
   (b) "a warning is not a sweep" (CR-2): a banner naming stale ACs INOCULATES them
       — reads to later agents as someone-is-on-top-of-it, so the residue ships
       under the warning's protection. Candidate one-liner for doc-sweep.md's
       retired-claims section, cite P1.
   Positive: CR-2 pre-registered six criteria before seeing SE's draft —
   pre-registration discipline independently re-derived (3rd countermeasure the
   team converged on without being told).
   Hub honesty note: "the work was always this size, and we believed otherwise" —
   consistent with navigator accountability entry; my "one sweep from READY"
   estimate an hour earlier was over-optimistic via the SAME mechanism (I graded
   PM3's characterization without independent check).

6. FOLLOW-UP AT P1 CLOSE (operator-flagged, binding, in no story at flag time) —
   P1's own pre-dispatch note, verbatim: "the game and player-line grains have never
   been checked multi-run. They share the denominator structure that produced F1,
   and every design reopening today came from a multi-run sequence. If either
   drifts, that's an F1-class finding rather than a detail." (F1 = P1's internal
   finding label; resolve it against their epic at eval time.)
   At close, verify ONE of these is true:
   (a) a story/AC covers multi-run sequences on the game and player-line grains
       (not just roster) — with executed multi-run fixtures, or
   (b) the gap is consciously deferred in a durable artifact (epic non-goals, an
       idea file, or closure notes) with the F1-class risk stated — not silently
       dropped.
   Silent absence = a real finding at eval, blocking my "verified" verdict.
   Cross-reference: the 2026-07-25 audit already found one multi-run drift property
   on the game grain — exempt/protected absences recur every run, inflating the
   floor denominator while excluded from the numerator (refusal deadlock once
   protected twins near half of prior; audit-reconcile MINOR-1). Any multi-run
   check they add should catch exactly this shape; if their multi-run analysis
   misses it, that's a second data point.
