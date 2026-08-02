---
paths:
  - "epics/**"
  - ".project/archive/**"
---

# Context-Layer Assessment Rules

## Purpose

After every epic, evaluate whether the work produced conventions, decisions, boundaries, or knowledge that should be codified in the context layer (CLAUDE.md, agent definitions, rules, skills, hooks, agent memory). This assessment runs independently of the documentation assessment -- both gates must pass before an epic can be archived.

## Assessment Triggers

The main session evaluates each trigger with an explicit **yes** or **no** verdict. Every verdict is recorded in the epic's History section.

1. **New convention, pattern, or constraint established.** Did the epic introduce a coding pattern, naming convention, file organization rule, or operational constraint that future work should follow?
2. **Architectural decision with ongoing implications.** Did the epic make a technology choice, integration pattern, or structural decision that affects how future epics are planned or implemented?
3. **Footgun, failure mode, or boundary discovered.** Did the epic reveal a gotcha, a common mistake, or an operational boundary (host vs container, auth vs public, etc.) that agents could trip over in future work?
4. **Change to agent behavior, routing, or coordination.** Did the epic modify how agents are dispatched, what they can do, how they communicate, or how the closure sequence works?
5. **Domain knowledge discovered that should influence agent decisions in future epics.** Did the epic surface baseball domain insights, API behavior patterns, or data model knowledge that agents should carry forward?
6. **New CLI command, workflow, or operational procedure introduced.** Did the epic add a new `bb` subcommand, a new script, a new skill, or a new operational workflow that should be documented in the context layer? If a workflow skill was added, renamed, or retired, also update the `/workflow-help` cheat sheet (`.claude/skills/workflow-help/SKILL.md`) and the CLAUDE.md Workflows section.
7. **Net context-layer growth (counterweight).** Did the layer grow materially this epic? Run `.claude/hooks/context-ratchet.sh` -- an **on-demand diagnostic, not a gate** -- which counts `*.md` + `*.sh` lines across the four subtrees (`.claude/rules`, `.claude/agents`, `.claude/skills`, `.claude/agent-memory`) against `.project/baselines/context-layer-ratchet.json`, and record the reading in the epic History. A **yes** carries that reading into the periodic refinement pass (see Cadence below), which is where growth is acted on; nothing is offset at this closure and no exception is signed. The one-way gate against that baseline was retired 2026-08-02 on the operator's ruling that gating and ratchets were not working. Only the operator runs `--update-baseline`.
8. **Reusable behavioral lesson surfaced (promote-to-load-target, gated).** Did a reusable behavioral lesson surface this epic that RECURRED (it also appeared in a prior epic) OR GENERALIZES beyond one agent? If yes, it MAY be promoted to its correct load target per the Learning-Loop Lifecycle below -- but a promotion is GATED on two conditions: (a) it cites the specific defect it demonstrably caught (not a hypothetical), and (b) it is recorded with trigger 8's verdict in the epic History, which is what the **periodic refinement pass** reads (see Cadence below): every promotion made since the last pass is re-examined against (a) and retired if it has not earned its load cost. An ungated "promote NOW" is what turned trigger 8 into a growth pump; (a) prices a promotion when it is made, (b) prices it again once its value is observable. The Learning-Loop Lifecycle's Deletion-Side Eviction and Memory Retirement hygiene still fire unconditionally -- they prune, they do not grow.

## Assessment Procedure

1. After all stories are DONE and the documentation assessment is complete, the main session evaluates each of the triggers above.
2. For each trigger, record an explicit **yes** or **no** verdict in the epic's History section. A blanket "no context-layer impact" without per-trigger verdicts is **not sufficient** -- every trigger must be individually evaluated.
3. **If any trigger is "yes"**: Spawn `claude-architect` (if not already on the team) to codify the findings in the appropriate context-layer files (CLAUDE.md, `.claude/rules/`, `.claude/agents/`, `.claude/skills/`, `.claude/hooks/`, `.claude/agent-memory/`). The epic MUST NOT be archived until the codification is complete. Triggers 7 and 8 additionally invoke the **Learning-Loop Lifecycle** below (promote-to-load-target, deletion-side eviction, memory retirement, and the refinement cadence, which is where trigger 7's reading lands).
4. **If all triggers are "no"**: Record the per-trigger verdicts in the epic's History section and proceed to archival.

## Learning-Loop Lifecycle

Trigger 8 and the periodic refinement pass make the context layer prune and re-home knowledge, not only accrete it; trigger 7 measures the growth that pass acts on. When trigger 8 fires (a reusable behavioral lesson surfaced), the lesson is promoted to a load target NOW -- and the load target is chosen by classification, because the failure this closes is "recorded but never recalled" (a high-value lesson left in a non-auto-loading topic file loads for nobody).

### Load-Target Classification

Every codified lesson is typed by who must recall it. Only the last type may terminate in a non-auto-loading file:

| Type | Load target |
|------|-------------|
| Universal-behavioral (binds every agent/session) | a `paths: "**"` rule or CLAUDE.md |
| Role-scoped (one agent's behavior) | that agent's definition, or its `MEMORY.md` top-200 |
| Path-scoped (fires only for certain files) | a rule with a `paths:` glob |
| Workflow procedure | the relevant skill under `.claude/skills/**` |
| Reference-only lookup material | a topic file linked from a `MEMORY.md` index (the ONLY type that may live in a non-auto-loading file, and only for lookup material) |

A lesson that must be recalled by an agent but lands only in a non-auto-loading topic file is the default failure -- "recorded, not recallable." Promotion under trigger 8 means moving it to the auto-loading target its type requires. (The two immediate promotions proving this pipeline landed in `.claude/rules/tool-output-integrity.md`.)

### Deletion-Side Eviction

Symmetry with promotion: for each file, flag, column, table, command, or agent this epic DELETED or RENAMED — **and for each CLAIM it RETIRED, which no identifier grep reaches** — grep `.claude/rules/`, `.claude/agents/`, `CLAUDE.md`, and **every agent's own `.claude/agent-memory/<agent>/` directory -- the `MEMORY.md` index AND its topic files, not just the index** -- for references, and strike or annotate each as history. Reconcile-not-strike: a hit is a *candidate* for eviction, not an automatic strike; preserve still-valid guidance.

**Ownership (who edits which dir).** Each agent's memory dir is reconciled by the OWNING agent. An agent ON the dispatch team reconciles its own dir at closure (its edits ride the closure patch); a hit in the dir of an agent NOT on the team is flagged by the main session as a follow-up sweep. Whoever runs the deletion-side sweep (typically claude-architect) MAY read ANY dir to IDENTIFY hits and report them as the closure seed, but only the owning agent edits its own content.

Accretion without eviction is how stale identifiers accumulate (the cross-season saga -- the user asked ~5x while passes only leaf-patched -- is the standing proof this direction is missing). **Grepping only the `MEMORY.md` indexes and skipping the topic files is how stale references survive a sweep**: E-259's deletion-side sweep found the stale data-engineer references hiding in topic files (`season_aggregate_writers.md`, `season_tables_are_a_pure_cache.md`, `fixture_seed_not_rollup_consistent.md`), not in the index — an index-only grep would have shipped a false-clean.

### Memory Retirement

At closure, PM greps its Pending-Work / active-epic memory for the archived epic's ID and retires the entry (an epic left listed as READY/active months after completing is the failure this prevents).

**A retired CLAIM strands copies the retiring epic cannot fix, and it is the retiring epic's job to leave them findable.** Sweep for the JUDGEMENTS that rested on the claim, not its wording (`.claude/rules/doc-sweep.md`) — E-276 retired *"a wrong roster delete self-heals / grid clutter, never a corrupted stat"* and its live twin in another agent's memory shared **no token** with it, surfacing only from the judgement step. Every hit outside your own dir is **flagged, never edited**, and a flag that lives only in a completion message is a handoff to nobody: file it as an idea against the owning agent with a resolution trigger (IDEA-187, IDEA-191), because the owner may not be spawned for weeks.

**Never write a number from a live thread into a memory file. Wait for it to settle, or record the MECHANISM instead of the MEASUREMENT.** A handoff artifact is read once, soon, by someone who might notice it is stale; **a memory file is read cold, months later, by someone with no thread to check it against.** In E-276 a figure that was retracted through three successive corrections had already reached another agent's durable memory, and was struck only because the retraction happened to be relayed in time. When a figure does turn out wrong, cut the magnitude rather than revising it downward if the lesson never depended on the count — and leave the withdrawal visible, so a later reader knows it was withdrawn rather than never taken.

### Cadence

The promote / evict / retire hygiene of this lifecycle stays **per-epic** -- it prunes and re-homes at every closure and does not wait. The layer's SIZE is **not gated**; it is refined on a schedule instead. Both cadences below are counted in **epic closures**, not weeks, so they scale with work done and are checkable by counting `.project/archive/` since the last run. Each run is recorded in the History of the epic whose closure triggered it, and that entry is the next count's origin. **Where a cadence has no run on record, the next closure owes one** -- the two cadences are counted independently, so a closure can owe one and not the other.

**Periodic context-layer refinement pass -- once per FIVE epic closures.** Re-read the four subtrees and deliberately prune: retire what no longer earns its load cost, re-home what sits in the wrong delivery mechanism, collapse restatements, and re-examine every trigger-8 promotion made since the last pass against condition (a). Trigger-7 readings accumulated since the last pass are the input, not a threshold. **It produces a dated refinement record in the History of the epic whose closure triggers it**, naming what was retired, what was re-homed, what was kept and why, and the readings it acted on. A pass that retires nothing records why -- that is a finding, not a skipped pass.

**Batched adversarial audit -- once per THREE epic closures**, and reviewed as one clause of the pass above rather than tracked separately. The Fable-model audits -- independent context-layer audit and adversarial spec/design review (`.claude/rules/agent-routing.md`, model escalation) -- run on that interval instead of per epic. **This reduces frequency; it never eliminates the audit.** These audits found a CRITICAL that same-tier review had missed twice, so **three closures is a ceiling on the gap, not a budget** -- shorten it freely, never skip. Record each run in the same History entry.

## Blocking Semantics

The epic MUST NOT be archived until the context-layer assessment is complete and any required codification is done. This gate is independent of the documentation assessment gate -- both must pass.

## Context-Layer File Ownership

| Files | Owner |
|-------|-------|
| `CLAUDE.md` | claude-architect |
| `.claude/rules/*.md` | claude-architect |
| `.claude/agents/*.md` | claude-architect |
| `.claude/skills/**` | claude-architect |
| `.claude/hooks/**` | claude-architect |
| `.claude/agent-memory/**` | claude-architect (structure); individual agents (content) |
| `.claude/settings.json`, `.claude/settings.local.json` | claude-architect |
