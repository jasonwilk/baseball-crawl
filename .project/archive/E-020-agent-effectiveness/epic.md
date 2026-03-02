# E-020: Agent Effectiveness Audit & Refinement

## Status
`COMPLETED`
<!-- Lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED) -->
<!-- PM sets READY explicitly after: expert consultation done, all stories have testable ACs, quality checklist passed. -->
<!-- Only READY and ACTIVE epics can be dispatched. -->

## Overview
The four specialist agents (api-scout, baseball-coach, general-dev, data-engineer) have clean frontmatter after E-018, but their system prompt bodies remain first-draft quality -- bloated with CLAUDE.md duplication, structurally inconsistent, missing anti-patterns and error handling guidance, and carrying redundant memory sections. The claude-architect agent itself still has E-018-era problems (bloated frontmatter description, outdated JSON output format references). This epic brings all five agents up to the quality bar set by the orchestrator and product-manager, making each one a self-contained operational manual that an implementing session can follow without guessing.

## Background & Context
E-018 (COMPLETED) fixed YAML frontmatter -- concise descriptions, explicit tools lists, consistent field ordering. But E-018's scope was explicitly "frontmatter only; do NOT change system prompt bodies." The user now wants these agents to be "truly effective," which means the system prompt bodies need the same level of care.

A side-by-side comparison of the seven agent files reveals clear quality gaps:

**Reference agents** (orchestrator, product-manager):
- Tight identity sections with clear boundaries
- Anti-patterns / "what NOT to do" lists
- Structured task taxonomies or routing tables
- Consolidated memory instructions (no duplication)
- No CLAUDE.md content copied into the prompt

**Target agents** (api-scout, baseball-coach, general-dev, data-engineer, claude-architect):
1. **CLAUDE.md duplication**: general-dev copies ~60 lines of HTTP Request Discipline and security rules verbatim from CLAUDE.md. data-engineer copies ~20 lines of database conventions. This wastes context window tokens since CLAUDE.md is always loaded.
2. **Memory section duplication**: general-dev and data-engineer each have BOTH a "Memory Instructions" section AND a separate "Persistent Agent Memory" block with overlapping guidelines.
3. **Missing anti-patterns**: None of the five target agents have a "What you do NOT do" or "Anti-Patterns" section. The orchestrator has one. The PM has "Technical Delegation Boundaries." These sections prevent agents from drifting into work that belongs to other agents.
4. **Missing error handling**: No agent has guidance for what to do when things go wrong -- stale specs, conflicting story criteria, missing files, failed tests.
5. **claude-architect outdated references**: Still references JSON output format (`identifier`, `whenToUse`, `systemPrompt`) which was the old agent config format. This project uses markdown files with YAML frontmatter. Still has the bloated multi-paragraph description with routing examples (same problem E-018 fixed for others). References "deploy sub-agents using the Task tool" but should reference Agent Teams for multi-agent work.
6. **Inconsistent section structure**: Each agent organizes its content differently. A consistent skeleton (Identity, Responsibilities, Standards, Anti-Patterns, Inter-Agent, Skills, Memory) would make agents easier to maintain and audit.

**Expert consultation**: claude-architect is both the implementing agent and one of the targets for this epic. No external consultation needed -- the PM's comparative analysis of all seven agent files provides sufficient diagnostic specificity. The quality bar is defined by the orchestrator and product-manager files, which the architect can reference directly.

## Goals
- All five target agents have consolidated, non-duplicative system prompts that reference CLAUDE.md rather than copying it
- All five target agents have explicit Anti-Patterns / boundary sections
- All five target agents have error handling guidance appropriate to their role
- general-dev and data-engineer have a single, consolidated memory section (no duplication)
- claude-architect has correct frontmatter (matching E-018 standard) and updated system prompt references (markdown files, not JSON; YAML frontmatter, not `identifier`/`whenToUse`)
- All agent files follow a consistent section skeleton

## Non-Goals
- Changing agent responsibilities, tool lists, models, or colors
- Rewriting the orchestrator or product-manager agents (they are the reference standard)
- Adding new agents or removing existing ones
- Changing frontmatter fields (E-018 already standardized those for the four specialist agents)
- Adding skills preloading or other frontmatter extensions
- Changing how agents interact with each other (routing, delegation patterns)

## Success Criteria
1. No agent system prompt contains content that duplicates CLAUDE.md verbatim (a brief "see CLAUDE.md for X" reference replaces copied blocks)
2. Every target agent has an "Anti-Patterns" or equivalent section listing 3-5 concrete things it must NOT do
3. Every target agent has error/edge-case handling guidance (2-5 items appropriate to its role)
4. general-dev and data-engineer each have exactly ONE memory section (no "Memory Instructions" + "Persistent Agent Memory" duplication)
5. claude-architect frontmatter matches the E-018 standard (concise description, explicit tools, canonical field order)
6. claude-architect system prompt references markdown agent files with YAML frontmatter (not JSON with `identifier`/`whenToUse`/`systemPrompt`)
7. All five target agent files follow the same section skeleton in the same order

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-020-01 | Refine claude-architect agent | DONE | None | claude-architect |
| E-020-02 | Refine api-scout system prompt | DONE | None | claude-architect |
| E-020-03 | Refine baseball-coach system prompt | DONE | None | claude-architect |
| E-020-04 | Refine general-dev system prompt | DONE | None | claude-architect |
| E-020-05 | Refine data-engineer system prompt | DONE | None | claude-architect |

## Technical Notes

### Section Skeleton (Canonical Order)
Every agent system prompt should follow this section order. Not every agent needs every section -- skip sections that do not apply, but do not reorder.

```
# [Agent Name] -- [Role Tagline]

## Identity
Who you are, what you do, what you do NOT do. 2-4 sentences.

## Core Responsibilities
### 1. [Primary responsibility]
### 2. [Secondary responsibility]
...

## [Domain-Specific Standards]
Agent-specific standards that are NOT already in CLAUDE.md.
- api-scout: "Security Rules" (credential handling specific to API exploration)
- baseball-coach: "Key Baseball Analytics Knowledge" (domain knowledge)
- general-dev: "Work Authorization" (story reference gate)
- data-engineer: "Work Authorization" + "Database Standards" (only conventions NOT in CLAUDE.md)
- claude-architect: "Design Methodology" + "Quality Standards"

## Anti-Patterns
Numbered list of 3-5 things this agent must NOT do. Concrete, not vague.

## Error Handling
What to do when: [role-specific failure modes]. 2-5 items.

## Inter-Agent Coordination
How this agent interacts with each other agent it works with. Brief -- 1-2 sentences per agent.

## Skill References
"Load [skill] when:" directives. Unchanged from current.

## Memory Instructions
Single consolidated section. Includes what to save, what NOT to save, and the Persistent Agent Memory block.
```

### CLAUDE.md Deduplication Rules
The following content categories are ALWAYS available via CLAUDE.md and must NOT be duplicated in agent system prompts:

1. **HTTP Request Discipline** (headers, session behavior, rate limiting, pattern hygiene) -- currently duplicated in general-dev
2. **Security Rules** (credentials, .env, gitignore) -- currently duplicated in general-dev and partially in data-engineer
3. **Code Style** (type hints, docstrings, pathlib, logging) -- currently duplicated in general-dev
4. **Testing conventions** (pytest, mock HTTP) -- currently duplicated in general-dev
5. **Git Conventions** (conventional commits, story IDs) -- currently duplicated in general-dev
6. **Project structure** (src/, tests/, data/, docs/) -- partially duplicated in multiple agents
7. **Database conventions** (ip_outs, soft referential integrity, timestamps) -- currently duplicated in data-engineer

**Replacement pattern**: Where an agent currently copies CLAUDE.md content, replace the copied block with a brief reference:
```
Follow the [topic] conventions in CLAUDE.md. Key points specific to [this agent's role]:
- [Only agent-specific additions or emphasis]
```

### claude-architect Specific Updates
The claude-architect system prompt has these specific problems that must be fixed:

1. **Frontmatter**: Still has the bloated multi-paragraph description with 5 routing examples. Apply the E-018 frontmatter standard:
   - Description: `"Agent infrastructure architect for Claude Code configurations, CLAUDE.md, memory systems, skills, rules, and hooks. Designs and manages the agent ecosystem, ensuring agents are precisely scoped, properly coordinated, and collectively effective."`
   - Tools: `Read`, `Write`, `Edit`, `Bash`, `Glob`, `Grep`, `WebFetch`
   - Field order: name, description, model, color, memory, tools

2. **JSON output format references**: The system prompt says to "output valid JSON" with `identifier`, `whenToUse`, and `systemPrompt` fields. This project uses `.claude/agents/*.md` files with YAML frontmatter. All JSON references must be replaced with the markdown/YAML format.

3. **"Deploy sub-agents using the Task tool"**: Should reference Agent Teams as the multi-agent mechanism (see `/.claude/rules/dispatch-pattern.md`).

4. **Generic "elite-tier expert" identity**: The current identity is generic boilerplate. Rewrite to be specific to this project's agent ecosystem and conventions.

### Memory Consolidation Pattern
For general-dev and data-engineer, merge the two memory sections into one:

**Current structure** (duplicated):
```
## Memory Instructions
Update your memory with: [list]
Do NOT save: [list]

# Persistent Agent Memory
You have a persistent memory directory at [path]...
Guidelines: [overlapping list]
What to save: [overlapping list]
What NOT to save: [overlapping list]
```

**Target structure** (consolidated):
```
## Memory
You have a persistent memory directory at [path]. Contents persist across conversations.

`MEMORY.md` is always loaded into your system prompt (lines after 200 truncated). Create separate topic files for detailed notes and link from MEMORY.md.

**What to save:**
- [Combined, deduplicated list from both sections]

**What NOT to save:**
- [Combined, deduplicated list from both sections]
```

### Reference Files
The implementing agent (claude-architect) should read these files for reference:
- **Orchestrator** (reference): `/Users/jason/Documents/code/baseball-crawl/.claude/agents/orchestrator.md`
- **Product-manager** (reference): `/Users/jason/Documents/code/baseball-crawl/.claude/agents/product-manager.md`
- **E-018 frontmatter standard**: `/Users/jason/Documents/code/baseball-crawl/.project/research/E-018-frontmatter-standard.md`
- **Dispatch pattern**: `/Users/jason/Documents/code/baseball-crawl/.claude/rules/dispatch-pattern.md`
- **CLAUDE.md**: `/Users/jason/Documents/code/baseball-crawl/CLAUDE.md`

### Parallel Execution
All five stories touch different files and can run in parallel with no conflicts.

| Story | File Owned |
|-------|-----------|
| E-020-01 | `/Users/jason/Documents/code/baseball-crawl/.claude/agents/claude-architect.md` |
| E-020-02 | `/Users/jason/Documents/code/baseball-crawl/.claude/agents/api-scout.md` |
| E-020-03 | `/Users/jason/Documents/code/baseball-crawl/.claude/agents/baseball-coach.md` |
| E-020-04 | `/Users/jason/Documents/code/baseball-crawl/.claude/agents/general-dev.md` |
| E-020-05 | `/Users/jason/Documents/code/baseball-crawl/.claude/agents/data-engineer.md` |

## Open Questions
None. The quality bar is defined by the orchestrator and product-manager. The problems are diagnosed. The fixes are specific.

## History
- 2026-03-02: Created. E-018 closed (frontmatter done). This epic addresses system prompt body quality. Set to READY.
