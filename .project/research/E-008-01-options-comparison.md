# E-008-01: Intent/Context Layer -- Architectural Options Comparison

**Produced by**: claude-architect (acting)
**Date**: 2026-02-28
**Inputs**: E-008-R-01 (intent-systems summary), E-008-R-02 (agent-skills summary), direct audit of baseball-crawl context layer

---

## Status Quo Audit

Before evaluating alternatives, here is what baseball-crawl's current context layer actually is -- based on file inspection, not assumption.

**Files that constitute the current context layer:**

| File / Directory | Lines | Scope | Purpose |
|-----------------|-------|-------|---------|
| `/CLAUDE.md` | 232 | Global (every session) | Project purpose, tech stack, code style, HTTP discipline, security rules, agent ecosystem, workflow contract |
| `.claude/rules/workflow-discipline.md` | 26 | Global (every session) | Work authorization gate, routing rules, direct-routing exceptions |
| `.claude/rules/crawling.md` | 20 | Global (every session) | Crawling behavior rules |
| `.claude/rules/ideas-workflow.md` | 83 | Global (every session) | Ideas capture and promotion rules |
| `.claude/rules/project-management.md` | 49 | Global (every session) | PM-specific rules |
| `.claude/rules/python-style.md` | 17 | Global (every session) | Python code style rules |
| `.claude/rules/testing.md` | 17 | Global (every session) | Testing conventions |
| `.claude/agents/*.md` | 41-486 each | Agent-specific | Per-agent identity, domain knowledge, tools, workflow |
| `.claude/agent-memory/claude-architect/MEMORY.md` | ~100 | Agent-specific | Persistent memory across sessions |
| `.claude/agent-memory/product-manager/MEMORY.md` | ~200 | Agent-specific | Persistent memory across sessions |
| `.claude/skills/` | 0 files | -- | Directory exists; empty |
| `epics/E-NNN-*/epic.md` | varies | Task-specific | Epic context loaded per story |
| `epics/E-NNN-*/E-NNN-SS.md` | varies | Task-specific | Story file loaded for each task |

**What is absent:**
- No directory-level context files under any subdirectory (`src/`, `tests/`, `epics/`, etc.)
- No installed skills in `.claude/skills/`
- No `src/` directory yet (code implementation is still early)
- 8 epics exist, with E-007 archived and E-009 listed (E-009 not reviewed)

**Baseline assessment**: The current system is effective and opinionated. Rules files load globally; agent files scope by agent; story files scope by task. The major gap is the absence of directory-level structural context -- but the cost of that gap is low today because `src/` does not yet exist. The gap will become real when E-002 and E-003 deliver the crawling and database code.

---

## Option 1: Status Quo with Refinements

**Description**: Keep the existing CLAUDE.md + rules/ + agent-memory/ + story-file pattern. Make targeted improvements to address known gaps: tighten CLAUDE.md sections that generate agent confusion, add a few missing rules files, and improve story file quality over time.

**How it would be implemented in baseball-crawl**: No structural changes. Specific refinements would include:
- Auditing CLAUDE.md for sections that are no longer current (e.g., "Commands: To be populated..." has been empty since day one)
- Adding a `docs/architecture-decisions.md` for ADRs that are currently scattered across epic Technical Notes
- Ensuring each new epic's Technical Notes section carries enough codebase context that an implementing agent does not need to read CLAUDE.md line by line

### Evaluation Scorecard

| Criterion | Rating | Justification |
|-----------|--------|---------------|
| Token efficiency | **Adequate** | All rules files load globally into every session, including rules irrelevant to the current task (e.g., crawling.md loads even when claude-architect is doing agent config work). Wasteful but tolerable at current scale. |
| Agent onboarding clarity | **Adequate** | Agents have enough context to begin work. The main gap is structural codebase context, which matters more once src/ has substantial code. |
| Maintenance burden | **Strong** | Minimal. Files are updated when conventions change; no new system to learn or maintain. |
| Compatibility with workflow contract | **Strong** | No changes needed. The workflow contract in CLAUDE.md and workflow-discipline.md is the source of truth and remains unmodified. |
| Implementation complexity | **Strong** | No implementation required. Refinements are iterative edits to existing files. |
| Reversibility | **Strong** | Nothing to reverse. Any refinement can be undone by editing the same file. |

**Verdict**: Status quo with refinements is the right choice for a project in active early development. The system is working. The gaps are real but modest. The cost of change must be justified against the cost of the problem, and that case has not been made for baseball-crawl today. This option is appropriate for a project of this scale that has not yet felt the pain of missing structural context (because src/ does not yet exist).

---

## Option 2: Intent Node Hierarchy (intent-systems.com approach)

**Description**: Add hierarchical CLAUDE.md files at semantic boundaries throughout the project: at minimum `src/`, `epics/`, `tests/`, and individual module directories like `src/gamechanger/`, `src/http/`, `src/safety/` as they are created. Each file explains what that area is responsible for, its entry points and invariants, anti-patterns, and downlinks to related nodes. Parent nodes are derived by summarizing leaf nodes.

**How it would be implemented in baseball-crawl**:
- Write 4-7 new CLAUDE.md files at semantic boundaries (src/, epics/, tests/, and top-level module dirs as they emerge)
- Each file: 100-300 lines covering purpose, entry points, contracts, anti-patterns, and downlinks
- Leaf-first construction: write src/gamechanger/CLAUDE.md before src/CLAUDE.md
- Maintenance process: after each story adds significant code, update the relevant node (5-10 min per story)
- Total build investment at current codebase size: ~4-6 hours

### Evaluation Scorecard

| Criterion | Rating | Justification |
|-----------|--------|---------------|
| Token efficiency | **Strong** | Directory-scoped loading means agents working in src/gamechanger/ only load root + src/ + gamechanger/ nodes, not everything. The LCA optimization prevents duplication. Once src/ is populated, this is a meaningful improvement over global rules files. |
| Agent onboarding clarity | **Strong** | An implementing agent landing on E-002-01 (write the team crawler) would load root CLAUDE.md + src/CLAUDE.md + src/gamechanger/CLAUDE.md automatically. The local invariants (rate limiting, credential handling, idempotency) are right there without reading the full root CLAUDE.md. |
| Maintenance burden | **Adequate** | 5-10 min per story/PR. At baseball-crawl's rate (~1-2 stories per week), this is manageable but represents a new obligation. Drift risk is real if nodes are not updated after significant code changes. |
| Compatibility with workflow contract | **Strong** | No changes to workflow contract needed. Intent nodes coexist with rules files and agent files; they serve a different purpose (structural context vs. behavioral rules). |
| Implementation complexity | **Adequate** | Writing the initial nodes requires genuine thought about each module's invariants. Cannot be done mechanically. Requires someone with domain knowledge of the project. |
| Reversibility | **Strong** | Easy to reverse. Removing intent nodes means deleting CLAUDE.md files from subdirectories; no other system components are affected. |

**Verdict**: A strong option for the near-term future, but premature today. The value of intent nodes is proportional to the complexity of the codebase they describe. Baseball-crawl's `src/` directory does not yet exist. Writing intent nodes for a codebase that is 0-100 lines of code is wasted effort; they would need complete rewrites after E-002 and E-003 deliver the crawling and database code. The right trigger for this option is: "E-002 and E-003 are DONE and src/ has substantial, stable module structure." At that point, intent nodes for `src/gamechanger/`, `src/http/`, `src/safety/`, and `src/db/` (or equivalent) would deliver immediate, computable value.

---

## Option 3: Agent Skills Adoption (muratcankoylan approach)

**Description**: Install context-engineering skills from the muratcankoylan repository into `.claude/skills/`. Agents load skill content on demand (progressive disclosure) when facing relevant problems. The most applicable skills are: `filesystem-context`, `multi-agent-patterns`, `context-fundamentals`.

**How it would be implemented in baseball-crawl**:
- Copy 3-4 specific SKILL.md files from the repository into `.claude/skills/<name>/SKILL.md`
- Adapt content to baseball-crawl conventions (e.g., add baseball-crawl-specific examples to multi-agent-patterns to call out the orchestrator -> PM -> specialist routing chain)
- Agent definitions reference skills when relevant in their system prompts
- Skills are updated when the patterns they describe change

### Evaluation Scorecard

| Criterion | Rating | Justification |
|-----------|--------|---------------|
| Token efficiency | **Adequate** | Progressive disclosure works in theory -- agents load skill content only when needed. In practice, if agents pre-load skills "to be safe," the efficiency gain evaporates. Baseball-crawl has no enforcement mechanism for selective loading. |
| Agent onboarding clarity | **Weak** | Skills teach *how to think about a problem*, not *what this codebase does*. An implementing agent reading `multi-agent-patterns.md` learns about supervisor bottlenecks but still does not know baseball-crawl's specific routing chain unless the skill is customized. Generic skills are lower-value than project-specific context. |
| Maintenance burden | **Adequate** | Upstream skills are maintained by the repository author. Custom adaptations need project-owned maintenance. Three skills = three additional files to keep current. |
| Compatibility with workflow contract | **Strong** | No conflict. Skills coexist with rules files; they are not enforcement mechanisms. |
| Implementation complexity | **Adequate** | Copying and adapting 3 skill files is straightforward. The risk is over-adoption: installing all 13 skills "because they might be useful" adds noise without value. |
| Reversibility | **Strong** | Easy to reverse. Skills are standalone files; removing them does not affect any other system component. |

**Verdict**: Weak standalone option, but useful as a component of a hybrid. The three most applicable skills (`filesystem-context`, `multi-agent-patterns`, `context-fundamentals`) describe patterns baseball-crawl already uses, and codifying them in SKILL.md files would be valuable orientation for new agents. However, skills alone do not solve the structural codebase context problem -- an agent reading `filesystem-context.md` learns the pattern but not how baseball-crawl specifically applies it. Skills are a complement to intent nodes or to improved documentation, not a replacement.

---

## Option 4: Dedicated Context-Manager Agent

**Description**: Add an eighth agent role -- a `context-manager` -- whose sole responsibility is maintaining and serving context: keeping intent nodes current, answering agent questions about codebase structure, summarizing context on demand, and managing the agent-memory/ system.

**How it would be implemented in baseball-crawl**:
- Write a new `context-manager.md` agent definition
- Define the context-manager's responsibilities: own `.claude/agent-memory/`, own intent node maintenance, respond to "what does this module do?" queries from other agents
- Add routing rules to the orchestrator: structural questions go to context-manager before implementation
- Context-manager would be invoked at the start of each story dispatch to provide a codebase orientation brief

### Evaluation Scorecard

| Criterion | Rating | Justification |
|-----------|--------|---------------|
| Token efficiency | **Weak** | Every agent interaction now has a potential round-trip through context-manager for orientation. At baseball-crawl's scale, this adds latency and token overhead without proportionate benefit. The codebase is small enough that CLAUDE.md + story file is sufficient orientation for most tasks. |
| Agent onboarding clarity | **Adequate** | A context-manager could theoretically provide perfect just-in-time context. In practice, the agent's output quality depends on how well the context-manager is maintained -- adding a dependency on a new agent that must itself be kept current. |
| Maintenance burden | **Weak** | Highest of all options. A dedicated agent is a new role to define, maintain, and route through. The coordination overhead (orchestrator -> context-manager -> implementing agent) adds steps to every workflow. |
| Compatibility with workflow contract | **Weak** | The workflow contract (E-007) was carefully designed. Adding a new mandatory intermediary (context-manager) between orchestrator and implementing agents changes the contract and invalidates E-007's routing documentation. |
| Implementation complexity | **Weak** | Requires a new agent definition, updates to orchestrator routing, updates to all agent definitions that now reference context-manager, and a new class of maintenance obligation. |
| Reversibility | **Weak** | Hard to reverse cleanly. Removing the context-manager means re-updating all agent definitions that reference it and re-simplifying the orchestrator routing. |

**Verdict**: Over-engineered for baseball-crawl's scale and incompatible with the existing workflow contract. A dedicated context-manager agent makes sense in a system with dozens of agents, frequent agent onboarding, and a large, frequently-changing codebase. Baseball-crawl has 7 agents, infrequent onboarding, and a small codebase. Adding an eighth agent to manage the context of seven others introduces more complexity than it solves. Rejected.

---

## Option 5: Hybrid (Intent Node Hierarchy + Skills)

**Description**: Implement both Option 2 (intent node hierarchy for structural codebase context) and Option 3 (selective skill adoption for behavioral patterns). Intent nodes handle "what does this module do and what are its invariants?" Skills handle "how should an agent reason about multi-agent coordination or context window management?" The two systems answer different questions and do not overlap.

**How it would be implemented in baseball-crawl**:
- Phase 1 (now): Copy 3 SKILL.md files into `.claude/skills/` (filesystem-context, multi-agent-patterns, context-fundamentals) -- low cost, immediate value
- Phase 2 (after E-002 + E-003 are DONE): Write 4-6 intent nodes at module boundaries in `src/` -- high value once the codebase is substantial
- Maintenance: skills updated when behavioral patterns change; intent nodes updated when module structure changes

### Evaluation Scorecard

| Criterion | Rating | Justification |
|-----------|--------|---------------|
| Token efficiency | **Strong** | Skills load on demand; intent nodes load by directory scope. Neither system front-loads all content into every session. Better scoped than the current global rules approach. |
| Agent onboarding clarity | **Strong** | Structural context from intent nodes + behavioral patterns from skills = complete agent orientation. An agent working in src/gamechanger/ gets codebase invariants from the intent node and multi-agent coordination patterns from the skill -- without reading the full CLAUDE.md. |
| Maintenance burden | **Adequate** | Two separate maintenance obligations (skills + intent nodes) rather than one. But the obligations are independent and scoped: skills are stable once written; intent nodes update as code evolves. |
| Compatibility with workflow contract | **Strong** | Neither system modifies the workflow contract. Both coexist with existing rules files and agent definitions. |
| Implementation complexity | **Adequate** | Phased implementation reduces complexity. Phase 1 (skills) is a few hours. Phase 2 (intent nodes) is a few hours after E-002/E-003 are done. Neither phase is technically complex; both require judgment about what content is most useful. |
| Reversibility | **Strong** | Both components are standalone file sets. Either can be removed independently without affecting the other or the existing system. |

**Verdict**: The strongest option for the medium term, with a clear phasing that avoids premature investment. It is not the right choice if Phase 2 never arrives -- but if the project reaches the post-E-003 stage where src/ has substantial, stable code (which it will), the intent node layer will pay for itself quickly. The hybrid's advantage over intent nodes alone is that the skills are immediately deployable and provide value before the codebase is complex enough to need structural intent nodes.

---

## Shortlist

After evaluating all five options, two emerge as the leading candidates:

### Primary Recommendation: Option 5 (Hybrid) with Phased Execution

Adopt both the intent node hierarchy and selective skill adoption, but phase them to match project maturity:

- **Phase 1 (now)**: Copy 3 specific SKILL.md files into `.claude/skills/` and adapt them to baseball-crawl conventions. Cost: 2-4 hours. Value: immediate, codifying patterns that are already used but not explicitly documented for agents.
- **Phase 2 (after E-002 + E-003 are DONE)**: Write intent nodes for `src/`, `src/gamechanger/`, `src/http/`, `src/safety/`, `src/db/` (or equivalent), `epics/`, and `tests/`. Cost: 4-6 hours. Value: high, as implementing agents will be working in a codebase with substantial module structure and the structural context will be immediately actionable.

The total investment is 6-10 hours spread across two phases. The ROI justification: once E-002 and E-003 deliver the crawling and database code, general-dev will be doing repeated work in `src/gamechanger/` and `src/db/`. Every story in those areas benefits from intent nodes that codify rate limiting contracts, idempotency requirements, and schema invariants without those rules needing to be rediscovered from CLAUDE.md each time.

### Conservative Alternative: Option 1 (Status Quo with Refinements)

If the user's priority is minimizing process overhead and the project is actively in motion on other epics (E-001 through E-006), Option 1 is entirely defensible. The current system works. The gap (no directory-level context) is real but not yet painful. Deferring the hybrid until the first time an implementing agent makes a mistake attributable to missing structural context is a valid strategy.

The key signal to watch for: if general-dev or data-engineer completes a story with an error that would have been prevented by a module-level intent node (e.g., violating the session factory contract, writing to wrong db file path), that is the moment to trigger Phase 2 of the hybrid.
