# Parallel-mode experiment evaluation — 2026-07-27

Two threads run concurrently from navigator-issued kickoff prompts, evaluated per
`2026-07-26-fable-audit/handoff-eval-protocol.md` (axes A-E) plus the parallel-mode
questions the night was designed to answer. Evaluator: the navigator session (this
file's ledger lived in its task store; findings were logged live as they occurred).

- **Thread 1**: E-275 classifier-hardening planning from `handoff-P2v2-classifier-spec-seed.md`.
  Ended: parked at DRAFT on `epic/E-275` (3504f56), landed onto main in a566cc3.
- **Thread 2**: E-277 reclamation follow-ups from `handoff-P3-reclaim-hardening.md`
  under `sublead-experiment-design.md`. Ended: closed at 9f8ff39 (plus hook fix 390d61c).

## E. Cost per deliverable (transcript-byte proxy, per protocol)

| | transcript | landed ins | KB/ins | band (2.0-4.5) | densest consumers |
|---|---|---|---|---|---|
| Thread 1 | 15.1 MB (4.0 main + 11.1 sub) | 3,598 (3504f56) | **4.3** | top of band | PM lineage: 3 generations, 5.6 MB combined |
| Thread 2 | 43.1 MB (9.0 main + 34.1 sub) | 4,473 (9f8ff39) | **9.8** | ~2.2x band | pm4 6.2 MB, se 5.5 MB, sub-lead 3.1 MB |

Thread 2's overage decomposes mostly into NECESSARY discovery and deliberate extra
gates, not re-litigation: the sub-lead experiment itself (spawn, failure, corrected
post-mortem — producing the result was the point), the operator-ordered Codex spec
review + triage round, the send-cap incident (detection, cross-check, refusal to
stretch authorization — which found a live cross-contamination defect), the Step-1d
smoke waiver rounds, and two ratchet rounds. Thread 1 at 4.3 KB/ins for a
planning-only session is high-normal; its drivers were the remediation doubling
(52KB epic, later trimmed), the falsifier corpus work, and five send-cap firings.
Wall-clock: both spanned ~7h overnight with heavy operator-idle; active-hours
decomposition not computed (span dominated by gate waits — see axis C, which is the
real story of the night).

## A. Deliverable verification

- **P2/Thread 1**: became planning-only by operator instruction (stop at READY →
  then, on the trim decision, park at DRAFT). The protocol's P2 checks (coach ruling
  before reorder, tripwire discriminates, fixture pack green) are DISPATCH-time
  checks and transfer to whenever E-275 runs; what was verifiable tonight was
  verified: coach D1 ruling obtained first, falsifier executed (0 of 563 real names
  affected — which drove the trim), PII certification PASS/REAL on the branch
  commit, landing verified by command output (worktree clean → branch → a566cc3).
- **P3/Thread 2**: MAJOR-1 decision explicit (pin — DE recommendation, operator
  ratified; DE first refuted the handoff's migration-contradiction premise by
  literal read, so option B died on evidence). MAJOR-3 shipped *stronger* than the
  handoff spec: raised error above the reap call in both public passes (assert
  rejected for -O stripping). Evidence accepted in lieu of a fresh verifier spawn:
  per-story CR gates (incl. a 2-round breaker correctly escalated), full suite 4298
  passed run twice, Step-1d runtime smoke with honestly re-scoped verdicts (MAJOR-1
  pin recorded UNEXERCISABLE on live data — zero audit rows — and pinned by
  synthetic tests instead), and the navigator's end-state command checks.

## B. Prompt adherence

Both threads honored their kickoff gates: number-by-glob (Thread 2, corrected once
by navigator band allocation), coach-ruling-first (Thread 1), staged-diff closure
pause with operator approval (Thread 2 — including catching an `add -A` sweep of an
operator-staged PII file in the review), sibling-worktree isolation (held all
night, verified both directions), closure-diff-base = merge-base, serialized
closure through the navigator. Scope riders: three DE-surfaced additions in E-277,
each operator-approved at a gate, none silent. Deviation of record: Thread 1 ended
at DRAFT rather than READY — an operator-instructed pivot (trim + park), not drift.

## C. Steering burden

Not comparable to the handoff baseline and not scored by script: parallel mode made
the operator the transport for every cross-thread decision, and the sub-lead
design's own target ("operator interventions: kickoff + closure approval only") was
exceeded ~15x. Decomposition (finding-04): (1) transport role is inherent to
two-session parallelism; (2) threads gated agent-owned decisions upward — visible
penalty for improvising, none for over-asking; (3) the navigator added ratification
pauses. Fix applied live mid-run: the decision-class charter (decide-and-disclose
by default; interactive gates only for scope change / destructive / PII-security /
standing-rule override). Post-charter gate volume dropped to genuine operator
moments. The charter is amendment #3 below.

## D. Hiccups, each with one named cause

1. **Send-cap hook** — LAYER. Three defects in one hook: `ls | head -1` worktree
   resolution shared one counter across both threads and would have written Thread
   2's staging rows into Thread 1's tracked dispatch log (fixed mid-run, 390d61c,
   verified at two live staging boundaries); reset mechanism existed only at
   dispatch staging boundaries so planning had one unresettable team budget; deny
   message hardcoded thresholds two generations stale (three sites).
2. **Behavior distortion under a visible budget** — LAYER (incentive design).
   Thread 1's hub began economizing sends ("costs a send"), trading process
   fidelity for budget — caught only because it narrated the tradeoff. The damage
   mode is silent. Core input to amendment #1.
3. **ID-namespace collisions** — PROCESS GAP. Sequential IDEA/E numbers + per-thread
   globs collide by construction (one real collision cost Thread 1 a ten-file
   renumber; one guaranteed collision — "skip to 210-211" landing inside the
   sibling's consumed 201-214 — was averted only by navigator ground truth).
   A correct glob is a snapshot, not a reservation; concurrent reservations exist
   nowhere on disk. Navigator band-allocation adopted live; the ask-first ruling
   STANDS (PM re-derived its second premise independently).
4. **Delivery black hole** — PROMPT + HARNESS. Three spawns "idled without
   delivering"; all three had delivered via plain final message, which does not
   route to main for NAMED spawns — and one prompt (navigator's own) explicitly
   said "final message". Named spawns must be told: deliver via SendMessage to
   "main".
5. **Sub-lead experiment** — ANSWERED-NEGATIVE, reason corrected at closure. The
   sub-lead could not spawn named teammates; carried all night as a platform limit,
   corrected to CONFIGURATION (`tools:` frontmatter grants, per
   workflow-discipline.md). Depth-2 named-teammate semantics (resume, shared task
   list, addressing) remain UNPROVEN. No workflow amendment until that is tested
   deliberately.
6. **Peer-to-peer message failures** — HARNESS, convergent across BOTH threads
   independently: replies routed to a live agent that never arrived; blocked sends
   surfacing a plausible summary line while discarding the body (three
   "reports" whose findings never existed in the receiver's context). Plus
   TaskUpdate rebroadcasting stored descriptions on any update (3x). Needs a
   claude-code-guide consult; until then, hub-mediated star topology is the only
   message path treated as reliable, and no delivery is assumed without an ack.
7. **Malformed tool batch** — MODEL. Thread 2's hub emitted a Write and an Agent
   spawn as one malformed call; spawn dropped, reissued, Write read back.
8. **Operator session-close** — EXTERNAL; the recovery is a positive finding: the
   resumed thread re-derived state from disk (worktree staging boundary, story
   statuses, task store) rather than asserting from memory, and the dispatch
   survived intact.
9. **Ratchet instrument** — LAYER. Counts lines, not bytes: blind to a 5,034-byte
   ambient-tier growth AND to a 312-byte remedy inside a long line (both
   demonstrated within one hour, same epic). Exception signed on the merits after
   the offset proved uncreditable; whole-rule deletion to move the counter was
   correctly refused.
10. **PII/repo hygiene near-miss** — PROCESS. `git add -A` at closure swept an
    operator-staged untracked file of live GC identifiers; caught in staged-diff
    review, quarantined by operator hand, then made structurally unsweepable via
    .gitignore. The staged-diff pause earned its keep in the exact way it was
    designed to.

**Positives worth keeping** (conduct that should be named, not just defects):
relay discipline held under pressure at every level — a refuted option presented
transparently instead of dropped, DE refuting a handoff premise by literal read,
coach refusing a navigator's wrong relayed figure, PM refusing to overwrite a row
claiming operator approval on its own inference, and PM correcting its own
"premise dissolved" claim before it reached the operator as policy. pm4's
content-anchored verdicts survived a mutation-and-restore that would have falsely
failed mtime-bracketed ones. Pre-implementation spec audit caught 8 defects on one
story before a line was written. The hub surfaced a hard-stop hook verbatim rather
than routing around it, and separately refused to stretch a file-deletion
authorization to a different path in a forbidden tree.

## Workflow-amendment list (each cited to tonight; layer edits route to claude-architect)

1. **Send-counter redesign**: counting invisible to agents (silent count +
   operator-facing alert; any hard stop only at an unreachable-runaway level);
   reset semantics that exist in planning, not only dispatch. [D.1, D.2]
2. **Parallel-mode kickoff template**: pre-allocated ID bands; sibling-worktree
   rules; merge-base diff rule; serialized-closure clause; expect-README-conflict
   note; a preflight audit of hooks for single-worktree assumptions. [D.3, D.1]
3. **Decision-class charter** into dispatch-pattern.md: decide-and-disclose by
   default; four interactive-gate classes; over-asking named as a failure mode
   with tonight as citation. [C]
4. **Named-spawn delivery contract** in spawn conventions: deliver via SendMessage
   to "main"; final-text is a black hole for named agents. [D.4]
5. **CR guidance — content-anchored verdicts**: build verdicts on quoted literal
   content, never mtime brackets; survives mutation-and-restore. [pm4/se episode]
6. **Ratchet instrument**: measure bytes, tiered by load scope (ambient/every-turn
   vs agent-scoped), instead of flat lines. [D.9]
7. **Measured-agent clause**: any agent whose message volume is being measured is
   told escalations and questions are never counted against it. [D.2 corollary]
8. **Message-reliability note**: star topology only; no assumed delivery without
   ack; claude-code-guide consult on the peer-delivery and summary-without-body
   failures before any further multi-agent reliance on peer sends. [D.6]
9. **Deferred, explicitly**: sub-lead / nested-dispatch amendments wait until
   depth-2 named-teammate semantics are tested with a tools-granted sub-lead. [D.5]

## Agent-grant decision input (operator's "decide later with data")

- Thread 1: **zero** PM spawn-escalations across three PM generations. Binding
  constraints were file operations (rename/delete need Bash) and the peer-messaging
  failures. Its report's verdict verbatim: "Bash would have helped; the Agent tool
  wouldn't."
- Thread 2: **two** escalations, both correct-by-rule (circuit breaker round 3;
  numbering allocation).

The data does not support giving PM the Agent tool. The live gap is narrow file
operations, served adequately tonight by PM-specifies/hub-executes — the same
shape the READY-freshness rule already uses when PM needs a commit date it cannot
query itself. A Bash grant for PM would close the gap but reverses a deliberate
anti-pattern decision; that trade belongs to the operator, and nothing tonight
makes it urgent.

## Parallel-mode verdict

**Workable at two-thread scale, adopted-with-amendments.** Sibling isolation held;
serialized closures worked; both deliverables landed clean (one shipped epic, one
parked planning branch since landed). The night also found and fixed two structural
defects live (shared-counter hook, ID allocation) and priced the real cost: the
operator is the transport layer, and without the decision-class charter that role
balloons ~15x past design targets. Run the next parallel round only with amendments
1-4 in place; expect the second closure to resolve the ideas-README conflict
additively (observed and handled cleanly tonight).
