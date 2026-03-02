# E-008: Intent/Context Layer -- Design Recommendation

**Author**: claude-architect
**Date**: 2026-02-28
**Status**: Awaiting user decision (see E-008-03)

---

## Decision Required

**Recommended approach**: Hybrid intent node hierarchy + selective skill adoption, implemented in two phases.

**Rationale summary**: Baseball-crawl's current context layer works well for today's project state, but will become a friction point when E-002 and E-003 deliver the crawling and database code. A phased hybrid -- skills now (low cost, immediate value), intent nodes after E-002/E-003 are DONE (higher cost, higher value) -- delivers the right investment at the right time.

**Implementation scope**: Phase 1 is 2-4 hours (skill files). Phase 2 is 4-6 hours (intent nodes after E-002/E-003 complete). Total follow-on epic: approximately 4-6 stories.

**Your options**:
```
A) Approve -- proceed to Phase 1 of the implementation epic (E-009 or next available)
B) Reject -- return to analysis or pursue a different option
C) Defer -- revisit when E-002 and E-003 are complete (skip Phase 1, begin Phase 2 only)

If choosing A, note any constraints (e.g., "Phase 1 only for now", "keep changes
confined to .claude/", "do not add CLAUDE.md files until I review each one").
```

---

## Recommended Approach

**Option 5 (Hybrid), executed in two phases.**

Phase 1 (immediate): Copy and adapt 3 specific skill files from the muratcankoylan Agent Skills for Context Engineering repository into `.claude/skills/`. Adapt each to baseball-crawl's conventions with project-specific examples. Skills to adopt: `filesystem-context`, `multi-agent-patterns`, `context-fundamentals`.

Phase 2 (triggered by E-002 and E-003 reaching DONE): Write intent nodes -- directory-scoped CLAUDE.md files -- at semantic boundaries in the codebase. Target directories: `src/`, `src/gamechanger/`, `src/http/`, `src/safety/`, `src/db/` (or equivalent), `epics/`, `tests/`. Each node is 100-300 lines covering purpose, entry points, contracts, anti-patterns, and downlinks to related nodes.

The two phases are independent. Phase 1 can proceed immediately without waiting for Phase 2 conditions to be met. Phase 2 should not begin until E-002 and E-003 are DONE, because the module structure those epics establish is what the intent nodes will describe.

---

## Rationale

The recommendation is grounded in four specific facts about baseball-crawl as it exists today:

**1. The current system works.** The CLAUDE.md (232 lines) + 6 rules files (212 lines total) + 7 agent definitions (1,202 lines total) + per-agent memory system is coherent and functional. E-007 deliberately designed the workflow contract enforced by `workflow-discipline.md`. Any recommendation that disrupts that contract requires a strong justification. This recommendation does not change the workflow contract.

**2. The critical gap is module-level structural context, and that gap is not yet painful.** Baseball-crawl's `src/` directory does not yet exist. There is no code for intent nodes to describe. Writing intent nodes now would be writing against a codebase that does not yet exist -- wasted work. The gap becomes real and painful when implementing agents begin working in `src/gamechanger/` and `src/db/` and must rediscover module invariants (rate limiting, idempotency, session factory contract, credential handling) from the root CLAUDE.md on every story.

**3. The skills gap is real and the cost to close it is low.** Three skills from the muratcankoylan repository (`filesystem-context`, `multi-agent-patterns`, `context-fundamentals`) describe patterns that baseball-crawl already uses but has not codified for agent consumption. `filesystem-context` describes how story files and research artifacts work as file-based context stores -- something every agent does but no skill explicitly teaches. `multi-agent-patterns` explains the supervisor bottleneck risk -- directly applicable to baseball-crawl's orchestrator routing and the telephone game risk when orchestrator paraphrases specialist outputs. Phase 1 costs 2-4 hours and does not require any conditions to be met first.

**4. The dedicated context-manager agent option is not proportionate.** Adding an eighth agent to manage the context of seven others -- and updating the workflow contract to route through that agent -- introduces more complexity than the problem justifies. Baseball-crawl's agent onboarding pain is not severe enough to warrant a structural fix of that magnitude.

---

## What We Are Not Doing

**Option 3 alone (skills only)**: Skills teach behavioral patterns but do not describe the specific codebase. An agent reading `multi-agent-patterns.md` learns about supervisor bottlenecks but still does not know baseball-crawl's routing chain unless the skill is project-customized. Skills alone are insufficient.

**Option 4 (dedicated context-manager agent)**: Rejected. Over-engineered for 7 agents, conflicts with the E-007 workflow contract, and adds coordination overhead disproportionate to the problem.

**Option 2 alone (intent nodes only)**: Intent nodes alone are premature and deliver no value until `src/` has substantial code. The phased hybrid avoids this by sequencing Phase 2 after the codebase is ready.

**Full muratcankoylan plugin install**: The repository includes 13 skill modules, several of which (BDI mental state modeling, LLM-as-Judge advanced evaluation, hosted agents) are academically sophisticated and inapplicable at this project's scale. Installing the full plugin would add noise. The hybrid adopts 3 specific, applicable skills manually.

---

## Implementation Sketch

### Phase 1: Skill Files (2-4 hours, can begin immediately)

**Files to create:**
- `/Users/jason/Documents/code/baseball-crawl/.claude/skills/filesystem-context/SKILL.md`
- `/Users/jason/Documents/code/baseball-crawl/.claude/skills/multi-agent-patterns/SKILL.md`
- `/Users/jason/Documents/code/baseball-crawl/.claude/skills/context-fundamentals/SKILL.md`

**Content approach**: Start from the muratcankoylan source material (fetched in E-008-R-02) and adapt each file to include baseball-crawl-specific examples and context. Example adaptations:
- `filesystem-context.md`: Add a section explaining how story files, epic files, and research artifacts implement the pattern in this project. Describe the `.project/research/` pattern explicitly.
- `multi-agent-patterns.md`: Add a section on baseball-crawl's orchestrator -> PM -> specialist chain. Call out the telephone game risk for PM -> general-dev dispatch. Reference the workflow contract.
- `context-fundamentals.md`: Add a section on baseball-crawl's context budget -- what loads per session (CLAUDE.md + rules files) vs. per task (story file + epic Technical Notes).

**Owner**: claude-architect
**Story count**: 1 story (Phase 1 skill files)

### Phase 2: Intent Nodes (4-6 hours, trigger: E-002 and E-003 both DONE)

**Files to create** (as modules are created by E-002/E-003):
- `/Users/jason/Documents/code/baseball-crawl/src/CLAUDE.md` -- scope: all of src/; covers module organization, Python conventions, testing requirements
- `/Users/jason/Documents/code/baseball-crawl/src/gamechanger/CLAUDE.md` -- scope: GC API client; covers credential handling, rate limiting, session factory contract, idempotency
- `/Users/jason/Documents/code/baseball-crawl/src/http/CLAUDE.md` -- scope: HTTP layer; covers session factory, browser headers, rate limiting, no-parallel-requests rule
- `/Users/jason/Documents/code/baseball-crawl/src/safety/CLAUDE.md` -- scope: PII safety module; covers scanner, pre-commit hook, never-commit rules, synthetic test data marker
- `/Users/jason/Documents/code/baseball-crawl/src/db/CLAUDE.md` (or equivalent) -- scope: database layer; covers D1 schema, migration conventions, ip_outs convention, soft referential integrity
- `/Users/jason/Documents/code/baseball-crawl/epics/CLAUDE.md` -- scope: epic/story system; covers numbering scheme, status lifecycle, dispatch rules
- `/Users/jason/Documents/code/baseball-crawl/tests/CLAUDE.md` -- scope: test conventions; covers no-real-HTTP rule, pytest conventions, fixture patterns

**Construction order**: Leaf-first (src/gamechanger/ before src/; tests/ before root-level). Parent nodes derived by summarizing child nodes, not by re-reading raw code.

**Owner**: claude-architect
**Story count**: 2-3 stories (one for src/ module nodes, one for epics/ and tests/ nodes, one for review pass and integration)

**Total Phase 2 story estimate**: 3 stories

---

## Agent Impact

| Agent | Current Behavior | Changed Behavior Under Recommendation |
|-------|-----------------|---------------------------------------|
| **orchestrator** | Routes based on CLAUDE.md agent ecosystem table and workflow-discipline.md rules | No change in routing logic. Optionally: could reference `multi-agent-patterns` skill when dispatching complex multi-agent tasks to avoid telephone game bottleneck. |
| **claude-architect** | Designs agents, rules, CLAUDE.md; owns agent memory | Owns Phase 1 (skill files) and Phase 2 (intent nodes). After implementation, owns maintenance of both: updates skill files when behavioral patterns change, updates intent nodes after significant stories. |
| **product-manager** | Writes epics/stories, manages backlog, dispatches stories | No change in core workflow. When dispatching stories, will have an `epics/CLAUDE.md` intent node available that codifies the story system's invariants -- reduces reliance on PM memory file for this context. |
| **baseball-coach** | Domain expert; consulted for coaching requirements | No change. baseball-coach does not interact with the codebase directly; structural context is not relevant to its role. |
| **api-scout** | Explores GC API, maintains docs/gamechanger-api.md | No change in exploration behavior. A `src/gamechanger/CLAUDE.md` intent node (Phase 2) would provide api-scout with the module's contracts and invariants when it is asked to update the client code. Minor benefit. |
| **data-engineer** | Database schema, D1 migrations, ETL pipelines | Direct beneficiary of Phase 2. A `src/db/CLAUDE.md` intent node captures the ip_outs convention, soft referential integrity policy, migration file naming, and local vs. prod DB distinctions -- currently discoverable only by reading CLAUDE.md or epic Technical Notes. |
| **general-dev** | Python implementation, testing | Direct beneficiary of both phases. Phase 1 `filesystem-context` skill codifies the file-based context pattern general-dev already follows. Phase 2 intent nodes for `src/gamechanger/` and `src/http/` provide module-level invariants at the working directory, reducing the chance of violating contracts (e.g., bypassing the session factory). |

---

## Success Definition

The intent/context layer is working correctly when:

1. **An implementing agent (general-dev or data-engineer) completes a story in `src/gamechanger/` without violating the rate limiting, session factory, or credential handling contracts defined in `src/gamechanger/CLAUDE.md`** -- where the agent's compliance is attributable to reading the intent node rather than the story file author having to spell out all invariants in every story's Technical Approach section.

2. **After E-008's implementation, the PM can write a story whose Technical Approach section contains fewer than 3 "reminder" lines** (lines that repeat contracts already documented in CLAUDE.md or rules files) -- because the agent's working-directory context nodes carry that information automatically.

---

## Risks and Mitigations

**Risk 1: Phase 2 intent nodes drift from the codebase**

As E-002, E-003, and later epics add and modify code, intent nodes become stale. A node that says "credential handling lives in src/gamechanger/client.py" becomes wrong when a refactor moves it. Stale nodes are worse than no nodes -- they actively mislead agents.

*Mitigation*: The implementation epic (E-009) must include a maintenance protocol: each story whose Definition of Done touches a module with an intent node must also include "update the relevant intent node if this story changes the module's contracts or structure." This is a one-line addition to the standard Definition of Done template.

**Risk 2: Skills become checkbox noise rather than active tools**

If skill files are installed but agents never load them (because they pre-load everything or ignore them), the progressive disclosure mechanism fails. Three files that are never read add no value.

*Mitigation*: Agent definitions for claude-architect, orchestrator, and general-dev should explicitly reference the relevant skill by name in their system prompts, with a trigger condition. Example: "When coordinating multiple agents on a complex story, read `.claude/skills/multi-agent-patterns/SKILL.md` before dispatching." This makes the loading decision explicit rather than relying on agent judgment.

---

## Next Steps

If approved, the follow-on implementation epic (E-009 or next available) would contain:

1. **Phase 1 story**: Write and adapt 3 skill files into `.claude/skills/`. Owner: claude-architect. Estimated 1 story, 2-4 hours.
2. **Phase 2 trigger story** (blocked on E-002 + E-003 DONE): Write 5-7 intent node CLAUDE.md files at src/ module boundaries, epics/, and tests/. Owner: claude-architect. Estimated 3 stories.
3. **Integration story**: Update agent definitions for orchestrator, general-dev, and data-engineer to reference relevant skills and intent nodes in their context. Update the Definition of Done template to include intent node maintenance. Owner: claude-architect. Estimated 1 story.

Total estimated stories: 5 stories. Estimated total effort: 8-12 focused hours.

Reference: [E-008 epic](/Users/jason/Documents/code/baseball-crawl/epics/E-008-intent-context-layer-design/epic.md)
