---
paths:
  - "epics/**"
  - ".project/archive/**"
---

# Context-Layer Assessment Rules

## Purpose

After every epic, evaluate whether the work produced conventions, decisions, boundaries, or knowledge that should be codified in the context layer (CLAUDE.md, agent definitions, rules, skills, hooks, agent memory). This assessment runs independently of the documentation assessment -- both gates must pass before an epic can be archived.

## Assessment Triggers

The main session evaluates each trigger with an explicit **yes** or **no** verdict. All eight verdicts are recorded in the epic's History section.

1. **New convention, pattern, or constraint established.** Did the epic introduce a coding pattern, naming convention, file organization rule, or operational constraint that future work should follow?
2. **Architectural decision with ongoing implications.** Did the epic make a technology choice, integration pattern, or structural decision that affects how future epics are planned or implemented?
3. **Footgun, failure mode, or boundary discovered.** Did the epic reveal a gotcha, a common mistake, or an operational boundary (host vs container, auth vs public, etc.) that agents could trip over in future work?
4. **Change to agent behavior, routing, or coordination.** Did the epic modify how agents are dispatched, what they can do, how they communicate, or how the closure sequence works?
5. **Domain knowledge discovered that should influence agent decisions in future epics.** Did the epic surface baseball domain insights, API behavior patterns, or data model knowledge that agents should carry forward?
6. **New CLI command, workflow, or operational procedure introduced.** Did the epic add a new `bb` subcommand, a new script, a new skill, or a new operational workflow that should be documented in the context layer? If a workflow skill was added, renamed, or retired, also update the `/workflow-help` cheat sheet (`.claude/skills/workflow-help/SKILL.md`) and the CLAUDE.md Workflows section.
7. **Net context-layer growth ratchet (counterweight).** Run the ratchet: `.claude/hooks/context-ratchet.sh` (a manual operator diagnostic) counts `*.md` + `*.sh` lines across the four subtrees (`.claude/rules`, `.claude/agents`, `.claude/skills`, `.claude/agent-memory`) and diffs them against the committed baseline `.project/baselines/context-layer-ratchet.json`. If it exits non-zero (the layer grew past baseline), the epic MUST either offset the growth (compress, consolidate, or retire) back to at-or-below baseline, or record an operator-signed exception -- net growth past baseline is not accepted on an agent's say-so. Record which of these happened in the epic History. This is the hard mechanism trigger 7 declined to be for the whole 1,652 → 4,061 growth; it replaces the old soft prompt that accepted any answer. The operator owns every baseline re-snapshot: only the operator runs `--update-baseline`, and the committed JSON diff is the human review point.
8. **Reusable behavioral lesson surfaced (promote-to-load-target, gated).** Did a reusable behavioral lesson surface this epic that RECURRED (it also appeared in a prior epic) OR GENERALIZES beyond one agent? If yes, it MAY be promoted to its correct load target per the Learning-Loop Lifecycle below -- but a promotion is GATED on two conditions: (a) it cites the specific defect it demonstrably caught (not a hypothetical), and (b) it fits within the ratchet baseline (a promotion that grows the layer past baseline needs the same operator-signed exception as trigger 7). An ungated "promote NOW" is what turned trigger 8 into a growth pump; the gate keeps the pipeline but prices it. The Learning-Loop Lifecycle's Deletion-Side Eviction and Memory Retirement hygiene still fire unconditionally -- they prune, they do not grow.

## Assessment Procedure

1. After all stories are DONE and the documentation assessment is complete, the main session evaluates each of the eight triggers above.
2. For each trigger, record an explicit **yes** or **no** verdict in the epic's History section. A blanket "no context-layer impact" without per-trigger verdicts is **not sufficient** -- every trigger must be individually evaluated.
3. **If any trigger is "yes"**: Spawn `claude-architect` (if not already on the team) to codify the findings in the appropriate context-layer files (CLAUDE.md, `.claude/rules/`, `.claude/agents/`, `.claude/skills/`, `.claude/hooks/`, `.claude/agent-memory/`). The epic MUST NOT be archived until the codification is complete. Triggers 7 and 8 additionally invoke the **Learning-Loop Lifecycle** below (offset accounting, promote-to-load-target, deletion-side eviction, memory retirement).
4. **If all triggers are "no"**: Record the per-trigger verdicts in the epic's History section and proceed to archival.

## Learning-Loop Lifecycle

Triggers 7 and 8 make the context layer prune and re-home knowledge, not only accrete it. When trigger 8 fires (a reusable behavioral lesson surfaced), the lesson is promoted to a load target NOW -- and the load target is chosen by classification, because the failure this closes is "recorded but never recalled" (a high-value lesson left in a non-auto-loading topic file loads for nobody).

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

Symmetry with promotion: for each file, flag, column, table, command, or agent this epic DELETED or RENAMED, grep `.claude/rules/`, `.claude/agents/`, `CLAUDE.md`, and the `MEMORY.md` indexes for references and strike or annotate each as history. Accretion without eviction is how stale identifiers accumulate (the cross-season saga -- the user asked ~5x while passes only leaf-patched -- is the standing proof this direction is missing).

### Memory Retirement

At closure, PM greps its Pending-Work / active-epic memory for the archived epic's ID and retires the entry (an epic left listed as READY/active months after completing is the failure this prevents).

### Cadence and the ratchet

The promote / evict / retire hygiene of this lifecycle is a per-epic review cadence -- the loop prunes and re-homes as deliberately as it records. The layer's SIZE is a separate matter and IS hard-bounded: trigger 7's ratchet (`.claude/hooks/context-ratchet.sh`) gates the four-subtree line count against the committed baseline, and net growth past it needs an operator-signed exception.

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
