# Workflow amendment list — system encodings of what worked (running)

Promotion bar: >=2 independent confirmations with named mechanism + defect citation.
Landing path: routed through claude-architect (context-layer owner) at P1-closure
codification or a dedicated codification pass; every entry carries its citations so
the meta-layer freeze (defect-cited-changes-only) is satisfied.

## PROMOTABLE NOW (bar met)

A1. Brief-is-a-relay; the file wins. Every inter-agent brief/handoff declares itself
    a relay; the receiver verifies against the durable artifact before acting; on
    conflict the artifact wins. — 3 in-P1 confirmations (PM3 catch, CR-2 refuting the
    brief pre-review, hub's 9 relay defects as the counterfactual) + E-267 handoff
    incident + navigator's own 2 misses. Target: dispatch-pattern.md + implement
    skill spawn templates.

A2. Safety absolutes require an attempted counterexample before READY. Any AC/TN
    phrased as an absolute about deletions/destruction gets someone assigned to
    BUILD the counterexample; surviving = shippable. — E-270 (7 prose defects),
    E-272 (NRBL), P1 (4-5 wrong gate absolutes, all killed by construction).
    Target: codex-spec-review checklist + code-reviewer checklist.

A3. Spawn prompts name the delivery channel. Any named-agent spawn states "deliver
    via SendMessage to <target>" + report-size contract. — audit session 8-of-10
    idle-without-delivery, audited session 6-of-8, transcript analyst reproduced it
    on itself. Target: dispatch-pattern.md one-liner + skill spawn templates.

A4. Discovery artifact precedes planning; planning may not re-derive it. When
    executed-evidence research exists (audit report, probe, POC), the planning team
    STARTS from it, verifies citations instead of re-deriving, and the epic lists
    up-front every decision the evidence does NOT settle, routed to its authority
    (operator/coach) BEFORE stories firm up. Conversely: contested/destructive
    designs get a discovery phase producing such an artifact BEFORE a planning team
    spawns. — P1: four committee rounds re-deriving audit-settled ground, 24.8MB
    pre-READY vs 7.6-13.3MB full-epic band; the one genuine open item (roster
    prefer-delete) needed an operator ruling round one. Target: plan skill
    Prerequisites + PM agent definition.

A5. Context-health self-report + drain protocol. Long-lived teammates state context
    pressure when material; a "low" report triggers bounded-tasks-then-stop and
    respawn-from-disk-artifacts. — P1 PM drain (worked, 3 PM generations);
    07-25 session degradation as counterfactual. Target: dispatch-pattern.md.

A6. Compaction boundary = session boundary (post-compact re-grounding). CONFIRMED
    MECHANISM in P1: hub auto-compacted 21:21:42Z; relay defects #8 (~21:37, the
    false "design is settled" premise handed to PM3) and #9 are both post-compact
    assertions of pre-compact state from the summary — structurally unverifiable
    from memory. Encoding: after any auto-compact, the orchestrator re-reads the
    authoritative artifacts (epic file, story statuses) BEFORE asserting any prior
    state or briefing any agent — file-wins applied to one's own past. Companion
    drain rule: at context-pressure threshold mid-judgment-phase, deliberately
    flush state to the epic file FIRST (same family as PM drain / the operator's
    existing stop-at-pass-boundary feedback memory), so what compaction summarizes
    is already secondary to a durable artifact. — Evidence: P1 compact timestamp
    + relay #8/#9 timing; A1's file-wins catching both is the antidote proof.
    Target: dispatch-pattern.md + implement skill.

## ONE MORE CONFIRMATION NEEDED

B1. Warning-is-not-a-sweep. A banner naming stale content INOCULATES it (reads as
    someone-is-on-top-of-it; survived four reviewers in P1). Fix: marking content
    stale REQUIRES the sweep in the same pass, or a blocking item — never a banner
    alone. — P1 (1 sharp instance). Target: doc-sweep.md retired-claims section.

B2. Fixture ranges must cover production sizes. Zero-failure sweeps below
    production scale read as strong evidence and are not. — P1 CR-2 catch
    (0-12 range vs 20-30-game seasons); audit's NRBL-tests-skip-Priority-2 is
    arguably the same class (structurally-incapable evidence). Target:
    code-reviewer checklist / testing rules.

B3. Hub-no-assert extension: the routing hub never characterizes file contents or
    teammate positions without a full Read / jointly-endorsed artifact, in ALL
    session modes (not just dispatch). — 07-25 session (16-25 errors), P1 hub
    (9 relays), navigator (2). Arguably already at bar; held at B only because the
    encoding needs care (it must bind open-mandate sessions, where existing rules
    don't trigger). Target: feedback_main_session_no_verify memory + possibly
    tool-output-integrity.md.

A7. Surgical layer pruning: remove SELF-verification scaffolding, keep RELAY
    verification. Vendor docs (platform.claude.com "Prompting Claude Opus 5"):
    Opus 5 "verifies its own work without being told to"; explicit verification
    instructions and legacy verification scaffolding "cause over-verification...
    wasted tokens with no loss in quality"; it "can expand the scope of a task";
    it "delegates to subagents more readily"; instructions compound with intrinsic
    behavior. This is a DOCUMENTED mechanism for the operator's model x layer
    interaction hypothesis — our 453KB layer is dense with verify/re-check
    injunctions tuned for 4.8. THE SPLIT IS LOAD-BEARING: our own data (P1's 9
    relay defects, the 07-25 session's 16-25 errors) shows Opus 5 does NOT
    intrinsically verify INHERITED/RELAYED claims — so prune only the
    "re-check your own work / add a verification step / double-check" class;
    KEEP brief-is-a-relay, file-wins, counterexample-before-ship, doc-sweep.
    Also add the vendor scope-constraint snippet ("Deliver what was asked, at
    the scope intended...") to handoff/spawn boilerplate, and the delegation cap
    ("do not use subagents to verify your own work... keep spawn counts low").
    Target: CA-led pass over CLAUDE.md + rules + agent definitions, each removal
    citing this doc + the cost data. Fold into / sequence with P4-P5.

A7b. Facts in the layer, behavior in the agent definition. The four vendor model
    guides (opus-5, fable-5, sonnet-5, opus-4-8 prompting docs) show behavioral
    coaching is MODEL-SPECIFIC (4.8 "favors reasoning over tool calls" and needed
    verify-nudges; Opus 5 self-verifies and over-complies with them; Fable finds
    prior-model skills "too prescriptive... can degrade output quality"; Sonnet 5
    and 4.8 both follow review-bar instructions literally). The layer serves a
    multi-model fleet, so: CLAUDE.md/rules keep model-INDEPENDENT truth (API
    quirks, canonical seams, invariants, relay/construction discipline); model-
    dependent behavioral tuning moves to agent DEFINITIONS, where model+effort
    are already pinned in frontmatter. This is the principled version of A7's
    prune, and the explanation for why the 4.8-era layer mis-serves Opus 5: the
    verify-scaffolding was behavior coaching for a reasoning-over-tools model,
    fossilized as universal law.

A7c. Give claude-architect a model-behavior reference. CA designs agents and the
    layer for a multi-model fleet with zero model-behavior knowledge on file. Add
    a CA memory/reference distilling the four vendor guides (per-model deltas,
    effort guidance, review-prompt literalism, delegation defaults, the
    fresh-context-verifier-beats-self-critique note), with the standing rule:
    evaluate any agent-definition or layer change against the TARGET model's
    documented behavior, and re-check the reference when models change.
    Validation step for the A7 pass: one Opus 5 table-read of the pruned layer
    ("which instructions would you over-comply with?") before commit.

A8. Re-run the effort sweep on agent definitions. Vendor docs: low/medium effort
    "produce strong quality at a fraction of the tokens"; effort defaults carried
    from a prior model should be re-swept; review prompts saying "only report
    high-severity / be conservative" get followed literally — ask for everything,
    filter separately (check code-reviewer/CR prompt for this pattern).
    Target: agent frontmatter audit (respects feedback_agent_model_override).

MEASUREMENT CAVEAT (recorded 2026-07-26): the self-corr/100-turns metric is
PARTIALLY CONFOUNDED — vendor docs state Opus 5 "narrates corrections to its
earlier statements more than prior models," including no-op slips. Cross-era
selfcorr comparisons (0.0/0.2 vs 1.2-5.5) overstate the error-rate delta by an
unknown narration factor. The 16d8be7b error catalog stands (25 errors derived
from exchanges, not from narration counts); the corpus-wide metric needs the
narration discount noted wherever cited.

## EXPERIMENT-PENDING (P2/P3 will decide)

C1. Spec-seeded handoff shape (A4's practical template): navigator/discovery hands a
    provenance-labeled draft epic; receiving PM verifies-not-trusts; gates unchanged.
    P2 is the test: if it runs near dispatch-band cost, promote alongside A4.
C2. Sub-lead dispatch (depth-2 teams, navigator context flat) — P3 is the test;
    design + risks in sublead-experiment-design.md.
C3. One-query telemetry as standing practice: steering_scan.py (self-corr/100 turns,
    relay-corrected pushback) + bytes/insertion + active-hours per epic. Candidate:
    a tiny scripts/ addition run at epic closure. Needs operator call on whether the
    upkeep is worth it (CLAUDE.md simple-first pushes back).

## NOT ENCODABLE (honest residue)

- Judgment about when evidence suffices / when to stop a design round. Mitigated by
  A2/A4 + budgets (e.g., "escalate after N rounds"), not solved.
- Operator rulings themselves. A4 makes them arrive EARLIER; nothing makes them
  automatic — by design.
