# Skill: implement

**Category**: Workflow Automation
**Adapted for**: baseball-crawl

---

## Activation Triggers

Load this skill when the user says any of:

- "implement E-NNN", "implement epic E-NNN"
- "start epic E-NNN", "start E-NNN"
- "execute E-NNN", "execute epic E-NNN"
- "dispatch E-NNN", "dispatch epic E-NNN"
- "run epic E-NNN", "kick off E-NNN"
- Any request that implies dispatching an epic's stories for implementation

**Chaining modifier**: The user may append "and review" or "and codex review" to any trigger phrase (e.g., "implement E-NNN and review", "start E-NNN and codex review"). This chains a code review after implementation completes. See Phase 3.

---

## Purpose

Codify the full workflow for dispatching an epic when the user requests implementation. The team lead reads the epic to extract team composition, creates the team, spawns PM and all implementing agents, and remains available for additional spawn requests. PM coordinates all dispatch, status management, and closure via `SendMessage` per `/.claude/rules/dispatch-pattern.md`.

This skill is deliberately thin. The coordination logic lives in dispatch-pattern.md and the PM agent definition. This skill handles trigger recognition, prerequisite checks, team composition extraction, and correct team spawning.

---

## Prerequisites

Before spawning PM, verify:

1. **The target epic exists.** Check that `/epics/E-NNN-slug/epic.md` exists. If not found, search `/epics/` for a directory starting with `E-NNN`. If no match, report to the user: "Epic E-NNN not found in `/epics/`." and stop.

2. **The epic status is `READY` or `ACTIVE`.** Read the epic file and check the `## Status` section.
   - If `READY` or `ACTIVE`: proceed.
   - If `DRAFT`: refuse. Tell the user: "Epic E-NNN is in DRAFT status. The PM must mark it READY after refinement is complete before it can be dispatched."
   - If `COMPLETED`: refuse. Tell the user: "Epic E-NNN is already COMPLETED."
   - If `ABANDONED`: refuse. Tell the user: "Epic E-NNN has been ABANDONED."
   - If `BLOCKED`: report the blocked status and any blocking details to the user. Do not proceed.

---

## Phase 1: Team Composition

Read the epic's `## Dispatch Team` section.

- **If present and non-empty**: Note the listed agents. These are the agents the team lead will spawn alongside PM.
- **If absent or empty**: Note "no team composition specified." The team lead will spawn PM only; PM will determine required agents from story domains and message the team lead to spawn them.

---

## Phase 2: Dispatch

Create the team and spawn all agents. The team lead is the only agent that can spawn teammates.

### Step 1: Create the team

Use `TeamCreate` to create a dispatch team for the epic.

### Step 2: Spawn PM

Spawn the product-manager (PM) as a teammate with the following context:

```
Dispatch epic E-NNN.

Epic directory: /epics/E-NNN-slug/
Epic file: /epics/E-NNN-slug/epic.md

Teammates spawned: [list of agent types spawned from Phase 1, or "none yet -- no Dispatch Team section found. Determine required agents and message me to spawn them."]

[If "and review" modifier was specified]:
After all stories are DONE and before the closure sequence, chain into the review-epic workflow at `.claude/skills/review-epic/SKILL.md`.

Coordinate per `/.claude/rules/dispatch-pattern.md`. Read the epic, identify eligible stories, and assign to teammates via messaging.
```

### Step 3: Spawn implementing agents

If the Dispatch Team section listed agents in Phase 1, spawn each one with the following context:

```
You are [agent-type] on the dispatch team for epic E-NNN.
Epic directory: /epics/E-NNN-slug/

The PM (product-manager) will assign your stories via messaging. Wait for the PM's instructions before starting work.
```

If no Dispatch Team section was found, skip this step -- PM will determine required agents and message the team lead to spawn them.

### Step 4: Remain available

After spawning all agents, the team lead **remains available for spawn requests from PM**. If PM messages requesting an additional agent for a newly unblocked story, the team lead spawns it promptly and notifies PM.

The team lead does NOT:
- Assign stories to implementers (PM does this via messaging)
- Update story or epic statuses
- Verify acceptance criteria
- Make routing decisions

---

## Phase 3: Optional Review Chain

If the user specified the "and review" modifier (e.g., "implement E-NNN and review"):

- The team lead includes this flag in the PM spawn prompt (see Phase 2 template above).
- PM chains into the review-epic workflow (`.claude/skills/review-epic/SKILL.md`) after all stories are verified DONE but before the closure sequence.
- The team lead does NOT invoke the review-epic skill separately. PM handles the chain.

If the modifier was not specified, this phase is skipped entirely.

---

## Workflow Summary

```
User says "implement E-NNN" (optionally "and review")
  |
  v
Team lead loads this skill
  |
  v
Prerequisites: verify epic exists, status is READY or ACTIVE
  |
  v
[If DRAFT/COMPLETED/ABANDONED: refuse and stop]
  |
  v
Phase 1: Read epic's Dispatch Team section
  - Extract team composition (or note "not specified")
  |
  v
Phase 2: Create team, spawn PM + implementing agents
  - PM gets: epic path, teammate roster, review flag
  - Implementers get: epic path, "wait for PM"
  |
  v
Team lead remains available for spawn requests from PM
  |
  v
PM coordinates via messaging per dispatch-pattern.md
  |
  v
[If "and review": PM chains into review-epic skill before closure]
  |
  v
PM runs closure sequence and presents summary
```

---

## Edge Cases

### Epic Not Found
If no directory matching `E-NNN` exists under `/epics/`, report to the user and stop. Do not search the archive (`/.project/archive/`) -- archived epics are completed or abandoned.

### Epic Is DRAFT
Refuse with explanation: "Epic E-NNN is in DRAFT status. The PM must complete refinement and mark it READY before dispatch." Do not offer to mark it READY -- that is the PM's responsibility after verifying stories have testable acceptance criteria and expert consultation is done.

### Epic Is COMPLETED or ABANDONED
Refuse: "Epic E-NNN is already [COMPLETED/ABANDONED] and cannot be dispatched."

### No TODO Stories With Satisfied Dependencies
The team lead does not check for this. PM will read the epic, discover the situation, and report back. The team lead relays PM's report to the user.

### "And Review" With No Uncommitted Changes
If the review chain runs but there are no uncommitted changes to review, the review-epic skill handles this gracefully. The team lead does not need special handling.

### PM Spawn Fails
Follow the Dispatch Failure Protocol in `/.claude/rules/workflow-discipline.md`: report the failure to the user with the specific reason and ask how to proceed. Do not improvise a workaround.

### Implementer Spawn Fails
If spawning an implementing agent fails, report the failure to PM via `SendMessage` and to the user. PM and the user decide how to proceed. Do not silently skip the agent or attempt a different agent type.

---

## Anti-Patterns

1. **Do not bypass PM.** The team lead spawns agents but does NOT assign stories, update statuses, or verify acceptance criteria. Those are PM's coordination responsibilities. See `/.claude/rules/dispatch-pattern.md`.
2. **Do not read story files to make routing decisions.** The team lead reads only the epic file (for status and Dispatch Team section). Story-level routing is PM's job.
3. **Do not start implementing before PM has updated statuses.** Implementation begins only after PM marks stories `IN_PROGRESS`.
4. **Do not invoke the review-epic skill directly.** If the "and review" modifier is specified, pass it as a flag to PM. PM chains into the review skill at the right point in the closure sequence.
5. **Do not modify the epic file.** The team lead reads the epic for prerequisites and team composition. All epic file modifications (status updates, history entries) are PM's responsibility.
