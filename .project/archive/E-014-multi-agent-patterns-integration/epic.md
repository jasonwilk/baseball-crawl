# E-014: Multi-Agent Patterns Skill Integration

## Status
`ABANDONED`

## Overview
The `multi-agent-patterns` skill (created in E-010-02) teaches agents the three coordination patterns used in this project, the telephone game problem, and how to relay context without distorting it. This epic wires that skill into every agent that has a role in the orchestrator -> PM -> implementing agent chain, with priority given to the agents where information distortion risk is highest.

## Background & Context

E-010-02 (DONE, 2026-02-28) created `.claude/skills/multi-agent-patterns/SKILL.md`. The skill documents:
- The three coordination patterns (supervisor, peer-to-peer, hybrid) and which one baseball-crawl uses
- The telephone game problem -- how context is distorted when relayed through multiple agents
- Verbatim relay as the mitigation: passing original content rather than summaries at each hop
- The two highest-risk relay points in the project (orchestrator -> PM, PM -> implementing agent)
- Why direct-routing exceptions (api-scout, baseball-coach, claude-architect) are safe
- A PM dispatch checklist and an orchestrator relay checklist

Like the `filesystem-context` skill, the `multi-agent-patterns` skill was installed but never referenced by any agent definition. No agent currently knows this skill exists or when to load it. This means the telephone game problem and its mitigations remain as prose in `CLAUDE.md` and `workflow-discipline.md` -- rules that agents read but have no active self-check mechanism for.

**Relationship to E-012**: E-012 adds `filesystem-context` skill references to project-manager and claude-architect. This epic is parallel and complementary: it adds `multi-agent-patterns` skill references across the full agent ecosystem. E-012 can complete independently; this epic does not depend on E-012 being DONE first, but the two epics touch some of the same files and should be sequenced carefully (see Technical Notes).

**Relationship to E-010-06**: E-010-06 (BLOCKED on E-002+E-003) was planned to add skill references to orchestrator, general-dev, and data-engineer for `filesystem-context`. This epic pre-empts that work for `multi-agent-patterns` by adding those references now. When E-010-06 eventually unblocks, it should note that `multi-agent-patterns` references are already present in those agent definitions and only add `filesystem-context` references.

**Expert consultation**: The `multi-agent-patterns` skill itself (authored by claude-architect in E-010-02) is the authoritative design document for this integration. The skill specifies trigger conditions, explains which agents play which roles, and calls out the two risk points. The PM consulted the skill directly rather than requesting a separate claude-architect consultation, since the architect already encoded the recommendations in the skill file.

No additional expert consultation required -- all architectural guidance is captured in the skill file and the existing workflow-discipline rules.

## Goals
- Every agent whose behavior is governed by the orchestrator -> PM -> implementing agent chain contains a `## Skills` section with an explicit trigger-condition reference to `multi-agent-patterns`.
- The orchestrator's definition explicitly instructs it to load the skill before constructing any Task tool dispatch, and to relay the user's request verbatim rather than paraphrasing.
- The project-manager's definition explicitly instructs it to load the skill before entering Dispatch Mode, linking it to the telephone game risk at the PM -> implementing agent relay point.
- The implementing agents (general-dev and data-engineer) reference the skill as a guide for understanding why they receive full story files and what to do if the dispatch context is incomplete.
- The consultative agents (baseball-coach and api-scout) reference the skill so they understand their role as direct-routing exceptions and why their outputs must be written to durable files rather than passed verbally through the chain.
- Claude-architect references the skill as part of its agent design methodology, specifically when designing relay steps or adding new agents to the chain.

## Non-Goals
- Adding `filesystem-context` or `context-fundamentals` skill references -- those are E-012 and E-010-06.
- Modifying the workflow contract itself (CLAUDE.md, `workflow-discipline.md`) -- the contract is correct; this epic only makes agents explicitly aware of the skill that explains it.
- Writing new coordination rules or changing routing logic.
- Creating new agents.
- Addressing Phase 2 intent nodes (those are E-010-04 and E-010-05, blocked on E-002+E-003).
- Modifying story files or epic files for other active epics.

## Success Criteria
1. `.claude/agents/orchestrator.md` contains a `## Skills` section referencing `multi-agent-patterns` with a trigger condition tied to Task tool dispatch construction and verbatim relay obligations.
2. `.claude/agents/project-manager.md` contains a `## Skills` section entry for `multi-agent-patterns` with a trigger condition tied to Dispatch Mode entry.
3. `.claude/agents/general-dev.md` contains a `## Skills` section referencing `multi-agent-patterns` with a trigger condition tied to receiving an incomplete or summarized dispatch context.
4. `.claude/agents/data-engineer.md` contains a `## Skills` section referencing `multi-agent-patterns` with a trigger condition tied to receiving an incomplete or summarized dispatch context.
5. `.claude/agents/baseball-coach.md` contains a `## Skills` section referencing `multi-agent-patterns` with a trigger condition tied to its direct-routing exception role and the requirement to write outputs to durable files.
6. `.claude/agents/api-scout.md` contains a `## Skills` section referencing `multi-agent-patterns` with a trigger condition tied to its direct-routing exception role and the requirement to write outputs to `docs/gamechanger-api.md`.
7. `.claude/agents/claude-architect.md` contains a `## Skills` section referencing `multi-agent-patterns` with a trigger condition tied to designing new agents that add relay steps to the chain.
8. Each skill reference names the skill file path (`.claude/skills/multi-agent-patterns/SKILL.md`) and includes at least one specific trigger condition that is actionable for that agent, not a paraphrase of the generic activation triggers in the SKILL.md.
9. A new agent onboarded to the project can read any agent definition and understand when to load the skill without reading the E-010 or E-014 epic history.

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-014-01 | Add multi-agent-patterns skill reference to orchestrator | TODO | None | claude-architect |
| E-014-02 | Add multi-agent-patterns skill reference to project-manager | TODO | E-012-01 | claude-architect |
| E-014-03 | Add multi-agent-patterns skill reference to general-dev and data-engineer | TODO | None | claude-architect |
| E-014-04 | Add multi-agent-patterns skill reference to baseball-coach and api-scout | TODO | None | claude-architect |
| E-014-05 | Add multi-agent-patterns skill reference to claude-architect | TODO | None | claude-architect |

## Technical Notes

### Skill Reference Format

All agents use the same format established in E-012 for `filesystem-context`. Each agent definition that references a skill should contain a `## Skills` section in the system prompt body (not YAML frontmatter):

```
## Skills

### multi-agent-patterns
**File**: `.claude/skills/multi-agent-patterns/SKILL.md`
**Load when**: [specific trigger conditions for this agent]

[One to two sentences describing why this skill is relevant to this agent's work.]
```

The trigger condition must be specific to the agent's named role in the routing chain, not a paraphrase of the generic activation triggers in the SKILL.md. This is the same principle established in E-012.

### Trigger Conditions by Agent

**orchestrator**:
- Primary trigger: "Constructing a Task tool dispatch -- before writing the prompt that will be passed to project-manager or any implementing agent, to apply verbatim relay (not paraphrase) and check for telephone game distortion risk"
- Secondary trigger: "Receiving complex output from multiple specialist agents and needing to aggregate it before relaying to the user -- to quote findings directly rather than summarizing"

**project-manager**:
- Primary trigger: "Entering Dispatch Mode -- before constructing the context block for an implementing agent, to verify the block contains the full story file and full epic Technical Notes (not summaries), and to check that this dispatch does not introduce telephone game distortion"
- Secondary trigger: "Receiving a work-initiation request from the orchestrator that appears to be a paraphrase rather than verbatim user intent -- to decide whether to ask the orchestrator for the original wording"

**general-dev**:
- Primary trigger: "The dispatch context block appears to be a summary rather than the full story file -- before beginning implementation, to understand that a summarized dispatch is a protocol violation and to request the full story file from PM"

**data-engineer**:
- Primary trigger: "The dispatch context block appears to be a summary rather than the full story file -- before beginning implementation, to understand that a summarized dispatch is a protocol violation and to request the full story file from PM"

**baseball-coach**:
- Primary trigger: "Completing a consultation and about to communicate findings verbally -- to understand that outputs must be written to a durable file (not held as conversational memory) so the PM can read them verbatim rather than relying on a relay"

**api-scout**:
- Primary trigger: "Completing an API exploration session and about to communicate findings -- to understand that all discoveries must be written to `docs/gamechanger-api.md` so downstream agents (PM, data-engineer, general-dev) read the original spec, not a relay"

**claude-architect**:
- Primary trigger: "Designing a new agent that adds a relay step to the orchestrator -> PM -> implementing agent chain -- to evaluate whether that relay step creates a telephone game risk and how to mitigate it"
- Secondary trigger: "Reviewing or modifying the routing logic in any existing agent definition -- to check whether a proposed change increases the relay depth and therefore increases distortion risk"

### File Scope per Story and Conflict Analysis

| Story | Files Modified |
|-------|---------------|
| E-014-01 | `.claude/agents/orchestrator.md` |
| E-014-02 | `.claude/agents/project-manager.md` |
| E-014-03 | `.claude/agents/general-dev.md`, `.claude/agents/data-engineer.md` |
| E-014-04 | `.claude/agents/baseball-coach.md`, `.claude/agents/api-scout.md` |
| E-014-05 | `.claude/agents/claude-architect.md` |

**Conflict with E-012**: E-012-01 modifies `project-manager.md`. E-014-02 also modifies `project-manager.md`. These stories must be sequenced: E-014-02 depends on E-012-01 (see Stories table). If E-012-01 is not yet DONE when E-014-02 is dispatched, E-014-02 must wait. E-012-02 modifies `claude-architect.md`; E-014-05 also modifies `claude-architect.md`. However, E-012 stories are assigned to claude-architect, and E-014 stories are also assigned to claude-architect -- they will run sequentially in practice. Make E-014-05 dependent on E-012-02 if E-012 has not completed by the time E-014-05 is dispatched.

**Parallel execution within this epic**: E-014-01, E-014-03, E-014-04, and E-014-05 can all run in parallel -- they touch different files. E-014-02 must wait for E-012-01.

### Implementing Agent Trigger Wording

For general-dev and data-engineer, the trigger is defensive -- it fires when the dispatch context looks wrong, not proactively at every dispatch start. This is intentional: these agents should not be burdened with loading the skill on every task; only when something looks off. The skill then gives them language to push back: "This dispatch context appears to be a summary. I need the full story file and epic Technical Notes to proceed."

### Skill Reference Placement in Agent Files

Agent definition files (`.claude/agents/*.md`) have a YAML frontmatter block followed by a system prompt body. The `## Skills` section should be placed after the agent's primary responsibilities sections and before any memory/output format sections. This placement keeps skills visible but not competing with core identity and behavioral rules.

For orchestrator, which currently has no `##` sections in its body (it uses bold headers for routing rules), the `## Skills` section should be added at the end of the system prompt, after "IMPORTANT Constraints."

For general-dev and data-engineer, which are short files, the `## Skills` section can be appended at the end.

### What This Epic Does NOT Change

The actual workflow contract is already correct and enforced by `workflow-discipline.md` and the existing agent instructions. This epic does not change any routing rules, dispatch procedures, or authorization gates. It only makes agents explicitly aware of the skill that explains WHY those rules exist and WHAT to do when something goes wrong (telephone game diagnostic).

### Relationship to E-010-06

When E-010-06 eventually unblocks (after E-002 and E-003 are DONE), the implementing agent writing E-010-06 should:
1. Note in the story that `multi-agent-patterns` references already exist in orchestrator, general-dev, and data-engineer (from E-014).
2. Only add `filesystem-context` references to those agents (the gap E-010-06 will fill).
3. Not duplicate the `multi-agent-patterns` `## Skills` entries already present.

## Open Questions
- Should the orchestrator's `## Skills` section reference both `multi-agent-patterns` and `filesystem-context`? The orchestrator is a relay agent and would benefit from both. However, the orchestrator currently has no filesystem tools -- it cannot read skill files directly. This is a constraint on whether a `filesystem-context` skill reference is meaningful for the orchestrator. Defer this question to E-010-06 or E-012's Open Questions.
- E-014-05 (claude-architect) will conflict with E-012-02 if E-012 is still in progress. At dispatch time, check E-012-02 status and add E-012-02 as a blocking dependency if it is not yet DONE.

## History
- 2026-02-28: Created. The `multi-agent-patterns` skill (E-010-02 DONE) exists but no agent references it. This epic closes that gap across all seven agents. E-012 closes the `filesystem-context` gap for PM and architect; E-010-06 (BLOCKED) will close it for orchestrator, general-dev, and data-engineer. This epic runs in parallel to both without conflict except for the `project-manager.md` sequencing with E-012-01.
- 2026-03-01: ABANDONED -- absorbed into E-013 during triage. All five stories (E-014-01 through E-014-05) became part of expanded E-013-04.
