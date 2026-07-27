# Sub-lead dispatch experiment — P3 (E-277) post-mortem

Author: PM4 (product-manager, third PM successor on the E-277 dispatch). Written at
E-277 closure, 2026-07-27. Design doc: `sublead-experiment-design.md` (same dir).
Eval axes: `handoff-eval-protocol.md` (same dir).

**Scope limit, stated first because it bounds everything below.** PM has no Bash tool
by design. **Axes C (steering burden) and E (cost per deliverable) are NOT ANSWERED
here** — both require running scripts (`steering_scan.py`, `corpus_scan.py`). They are
left explicitly blank rather than estimated. A post-mortem that guessed them would be
this epic's own signature defect landing in the document recording it.

---

## VERDICT: ANSWERED NEGATIVE — but the reason is a CONDITION, not a property

**The two-coordinator topology did not work in P3.** Two failures, one fatal.

**F1 — the sub-lead could not spawn named teammates.** Surfaced ~15 minutes in, and it
is fatal to the design as written: the whole topology depends on the sub-lead standing
up PM, implementers and code-reviewer itself.

**✅ CAUSE RESOLVED 2026-07-27 — CONFIGURATION, NOT A PLATFORM LIMIT.** Found by `ca-2`,
and it needed no transcript read: it was already documented in
`.claude/rules/workflow-discipline.md` (Consultation Compliance Gate), a rule loaded on
**every** interaction, corrected the **day before** this dispatch:

> **Why PM cannot spawn (corrected 2026-07-26): not a platform limit.** Subagent nesting
> works — a subagent called the `Agent` tool and produced four depth-1 children, verified
> in transcripts on Claude Code 2.1.220. **PM cannot spawn because PM's `tools:`
> frontmatter does not grant the `Agent` tool, as is true of every agent definition in
> this repo. That is a configuration choice and it is changeable.**

**So F1 is a one-line frontmatter change, not a constraint. Do NOT record it as
"teammates cannot spawn named teammates"** — that phrasing rode the running checklist
all night and was never derivable from what was observed.

**⚠ BUT THE ORIGINAL RISK IS ONLY HALF-ANSWERED, AND THE HALF THAT SURVIVES IS THE ONE
THE EXPERIMENT EXISTED TO TEST.** Design-doc risk #2 asked **two** questions:

1. ***Can a subagent spawn at all at depth 2?*** — **ANSWERED. Yes; gated only by the
   `tools:` grant.**
2. ***Do NAMED-TEAMMATE semantics work at depth 2 — SendMessage addressing, long-lived
   PM resume, the shared task list?*** — **STILL UNPROVEN. The spawn block prevented us
   from ever reaching it.** The rule's cited evidence is *four depth-1 children* via the
   `Agent` tool; it says nothing about SendMessage team semantics, which is a different
   mechanism.

**A reader who takes "F1 was config" as "the topology works once the tool is available"
will spend the experiment a second time.** Once that configuration lands, question 2
becomes **the** open risk of the next run.

**⚠ HOW THIS DOCUMENT GOT IT WRONG, recorded because it is the sharper finding.** The
first draft **quoted the rule above, as "candidate 2," and still filed the cause as
unresolved.** The evidence was inside the document asserting it was missing. The framing
error was mine: I posed the question as *"which of two causes explains the spawn block?"*
— **for which that rule is dispositive** — while the genuine residual was question 2,
which I never named. **The hedge was not wrong to exist; it was attached to the wrong
question.**

**F2 — `TaskUpdate(owner=…)` is dispatch.** Setting `owner` rebroadcasts the task's
STORED DESCRIPTION to the assignee as if it were a fresh instruction. **It fired twice**:
once assigning story 01 roughly four hours early, and once producing a false absence
report. This is a harness-semantics trap, independent of F1, and it would bite any
topology that assigns work through the shared task list.

**RETRACTED — do not carry forward.** An earlier draft of this record claimed a
one-way-channel failure. **That was a latency batch, not a finding.** It is named here
so a reader who saw it elsewhere knows it was withdrawn rather than never taken.

---

## A. Deliverable verification (P3's three criteria, from the eval protocol)

**A1 — "MAJOR-1 decision explicit (pin vs document, not silence)": PASS.** The decision
is **pin**, delivered by E-277-01 as a fourth reachability root
(`scheduled_report_runs.own_team_id`) in `_TEAM_BASE_PRED`.

**⚠ But it passed by a route the handoff did not anticipate, and that is the more useful
finding: the handoff's REASON for calling MAJOR-1 a defect was refuted.** PM and DE
independently established that migration 005's cited comment is scoped to **report**
deletion, and that the same migration's CASCADE MIRROR INVARIANT affirmatively REQUIRES
audit-row deletion on **team** deletion — so no doc/code contradiction existed, and the
handoff's *"status quo is the only wrong option"* framing collapsed. **The BEHAVIOUR
reproduced on HEAD; only the justification was wrong.** Both halves belong in the record.

**A2 — "`in_transaction` fail-fast present in both public passes": PASS, and exceeded.**
`_require_clean_connection` is defined once in `src/reports/lifecycle.py` and called at
**three** entry points, cited by symbol rather than line: `reap_stale_generating_reports`,
`cleanup_expired_reports`, `reclaim_orphan_reference_data`. **The criterion named two;
three shipped.** Not a defect — recorded because a reader comparing the criterion to the
code will otherwise think one is wrong.

**A3 — "migration-005 comment consistent with the chosen behavior": PASS by
non-modification.** `migrations/005_scheduled_report_runs.sql` is frozen by story 04's
AC-4 and verified unmodified. Consistency holds because A1's refutation established the
comment was already correct — **the handoff's proposed "correct the migration comment"
option was near-empty work.**

---

## B. Prompt adherence

- **Epic number by glob: YES.**
- **Scope stayed tight: YES**, with two deliberate, recorded exceptions —
  `.project/ideas/` was declared OUT of story 04 on **domain/routing** grounds (PM-owned,
  not claude-architect's) rather than left silent, and AC-6b was added as a
  **REPORT-ONLY** sweep with its permitting asymmetry written into the AC.
- **Gates honoured: YES.** Code review and PM AC verification both ran on every story;
  the staged-diff pause held.
- **Report-back format: PARTIAL.** The per-story ≤3-sentence boundary was not sustained
  under the defect volume this epic generated. **This is a design-doc calibration
  question, not a compliance failure** — see amendment 3.

---

## C. Steering burden — **NOT RUN**

Requires `steering_scan.py` against the session transcripts. **Not estimated.**

One input for whoever runs it: **PM-escalation events = 1** (the story-02 circuit
breaker), plus **1 numbering escalation** at closure that was correct by rule — the
operator had drawn a cross-thread idea-number boundary, making it a class-4
override-a-prior-ruling decision under the decide-and-disclose posture. **No
spawn-failure escalations originated from PM.**

## E. Cost per deliverable — **NOT RUN**

Requires `corpus_scan.py`. **Not estimated.** The band is ~2.0-4.5 KB transcript per
landed insertion; landed insertions at the staging boundary were **3,855 across 27
files**. **Report the number with its densest consumer**, per the protocol.

---

## D. Hiccup classification (one cause each)

| # | Hiccup | Cause |
|---|---|---|
| F1 | Sub-lead could not spawn named teammates | **HARNESS or PROMPT — UNRESOLVED.** See the two candidates above. Classification is the follow-up. |
| F2 | `TaskUpdate(owner=…)` rebroadcasts the stored description as dispatch | **HARNESS.** Fired twice. |
| H1 | A `Write` and an `Agent` spawn emitted as one malformed call; PM spawn lost and re-issued | **MODEL** (navigator tool-batching), planning phase, pre-sub-lead. |
| H2 | A false "THREAD KILL" entry written into the navigator's scratchpad by an unidentified third party, asserting operator authority for a message never sent | **HARNESS.** Refuted by execution — PM replied alive. **It PRESCRIBED an action** (respawn all three); acting on it would have destroyed a live healthy team. |
| H3 | Navigator briefed all agents that line numbers were stale; SE measured four of five cited files **byte-identical** to the audit commit | **MODEL** — an unfounded staleness warning is itself a relay defect. Cost nil (ACs cite symbols), but the claim was not derivable when made. |
| H4 | Idle notifications reaching the navigator | **HARNESS**, benign, 2 in the planning phase; no chase warranted. |

**Uncategorized: none.** F1's cause is unresolved but its *class* is bounded to two.

---

## Workflow-amendment list

Each entry: observed misfire → **smallest** change. Layer edits carry the misfire as
citation.

1. **F1 → the cause is RESOLVED, so the amendment is now a DIFFERENT amendment.**
   **Smallest change: grant the `Agent` tool in the sub-lead's `tools:` frontmatter** —
   one line, `ca-2`'s to make, on the operator's decision. **No rule edit is warranted**:
   the rule that explains this is already correct, already universally loaded, and
   already defect-cited. **What must accompany that change is a stated expectation that
   risk #2's second half — named-teammate/SendMessage semantics at depth 2 — is UNTESTED
   and is the next run's primary risk.** Making the configuration change without carrying
   question 2 forward converts a resolved question into a rediscovered one: **the rule's
   evidence is `Agent`-tool children, a different mechanism from SendMessage team
   semantics, and it says nothing about them.**
2. **F2 → spawn-prompt clause.** Any topology using the shared task list must state that
   **setting `owner` rebroadcasts the stored description as dispatch**, so a task
   description must be assignment-ready before an owner is set. Not a skill edit — it is
   harness semantics, and the spawn prompt is the model-matched surface.
3. **Per-story ≤3-sentence contract → design-doc calibration, not a rule.** The contract
   assumed a defect-light dispatch. E-277 was defect-dense by construction (it exists to
   repair a six-defect audit handoff). **Smallest change: make the budget a function of
   findings — a clean story reports in three sentences, a story with MUST-FIX findings
   reports the findings.** Do not amend `implement/SKILL.md`; this is experiment framing.
4. **The "brief is a relay; artifact wins" instruction → NONE, worked as written, and
   it paid.** Four handoff defects were caught **before any AC was pinned**, including a
   mechanism claim (`BEGIN IMMEDIATE` implicit-commits) that two agents independently
   refuted by execution — it RAISES — and a chunking test that would have been
   **vacuous** because this build reports `SQLITE_LIMIT_VARIABLE_NUMBER = 250000`, not
   999. **Keep the clause verbatim in every future handoff prompt.**

5. **Post-packaging writes → an ORDERING rule, not a diligence rule. Name the re-stage
   as a step.**

   **The misfire, observed three times in one closure**: a write landed after the
   orchestrator's last `git add -A` and would have been silently dropped from the
   closure patch. The third instance was agent-memory eviction content — real,
   load-bearing, and invisible in the packaged diff. All three were caught only because
   the orchestrator re-checked the worktree instead of trusting its own staging from ten
   minutes earlier.

   **⚠ THE FRAMING MATTERS MORE THAN THE COUNT, AND THE FIRST FRAMING WAS WRONG.** The
   natural reading is *"a write after packaging is silently dropped unless someone
   re-checks"* — **a diligence problem.** It is not.

   > **The late writes were CAUSED by the late review. Any review landing after packaging
   > GUARANTEES the condition it is checking for. The more valuable the late catch, the
   > more certain the late write.**

   **That inverts the remedy.** Carelessness is not the mechanism: a dispatch that
   reviews thoroughly at the end will **always** generate post-packaging writes, and
   telling people to "be more careful" prescribes vigilance for a condition that gets
   **worse the better they review.**

   **Smallest change — an ordering rule with two acceptable branches:** either **the last
   review precedes the last `git add -A`**, or **packaging is DEFINED to include a
   re-stage after every accepted finding.** The second branch is what actually happened
   here — performed by hand, correctly, three times, **and never named as a step.**
   **An unnamed step performed correctly three times is one somebody skips the fourth.**

   **The anchor, in the orchestrator's own words:** *"my staging was a measurement of a
   moment, and the moment had moved."* **That is the TIMING half of this epic's
   frame/timing pair, arriving against the ORCHESTRATOR's instrument rather than a
   reviewer's** — the pair was derived entirely from reviewers' enumerations and nobody
   had pointed it at the packaging step.

   **⚠ THIS ENTRY IS ITSELF THE FOURTH INSTANCE, WRITTEN DELIBERATELY.** Authoring it
   required a post-packaging write, which the orchestrator then folded in on purpose.
   **A fourth instance caught and folded by design is better evidence for the rule than
   three caught by attention** — and it is the cheapest available demonstration that
   branch two is executable. Prose-only, in `.project/research/`, so it cannot affect the
   test suite the closure gate was running.

   Source: the dispatch lead (the observation, the three catches, and the anchor
   sentence); PM4 (the causal inversion and the ordering-rule form). **A
   DISPATCH-PROCEDURE finding, not an E-277 content finding** — which is why it lives
   here and not in the epic's TN-15.

---

## The counterexample to the remedy this epic is shipping

**`ca-2` volunteered this against its own closure codification, and the post-mortem is
its right home precisely because it undercuts that work rather than supporting it:**

> **I spent this pass migrating *"a rule in the wrong place is an absent one"* and
> applying the audience test. This rule was in the RIGHT place — universally loaded,
> current, defect-cited — and it still did not reach the people reasoning about F1 for a
> whole dispatch. Correct placement is necessary and demonstrably not sufficient.**

**The evidence for it is F1 itself, and it is worse than "nobody read the rule."** The
rule was loaded on every interaction for every participant. It was quoted **inside this
very document** as a candidate cause and still not treated as dispositive. **Four
parties reasoned about F1 all night — a navigator, a PM, a code-reviewer and `ca-2` —
with the answer ambiently loaded the entire time.**

**This is the same shape as the frame finding in E-277's TN-15, one layer out.** There,
*stating the scope* turned out to be necessary and not sufficient: three agents knew the
rule, two had written it, all three still shipped a bare count. **Here, correct
placement is necessary and not sufficient.** Both say the same uncomfortable thing —
**the remedies this epic is shipping raise the floor and do not close the gap**, and a
reader who takes them as closures will be surprised in exactly the way we were.

**Do not resolve this by adding another rule.** The failure mode under discussion is a
correctly-placed rule failing to be recalled; a further rule inherits the same defect.

## Preserved for a topology that is now ONE CONFIG CHANGE away

**Two findings are recorded HERE rather than in the rules layer, deliberately.** Both
are real; both are artifacts of a **two-coordinator window** that `dispatch-pattern.md`
does not sanction as the standing topology. **Codifying them would document an anomaly
as the pattern** (`ca-2`'s judgment, and it is right for today).

1. **The baton / ACK lock** — coordination discipline for two coordinators sharing a
   dispatch.
2. **An instruction outliving withdrawn authority** — a directive issued by a
   coordinator continued to be acted on after that coordinator's authority had lapsed.

**⚠ THE CONDITION IS NO LONGER SPECULATIVE — UPDATED 2026-07-27.** The original text
here said these could be *"discarded unread if F1 resolves to a platform limit."* **F1
resolved to CONFIGURATION.** So there is no discard branch: **the two-coordinator
topology is one `tools:` frontmatter line away, and both findings become live the day
the operator grants it.**

They live here rather than in the rules layer because **codifying them would document an
anomaly as the standing pattern** (`ca-2`'s judgment, still correct — the topology is not
sanctioned by `dispatch-pattern.md` today). This is the audience test run forward in time
rather than backward: *name the next person who needs this rule and ask whether they will
open the file it is in.* **Nobody opens an archived epic to learn dispatch topology;
whoever revives this experiment opens this directory first** — and they now have a
concrete reason to, rather than a hypothetical one.
