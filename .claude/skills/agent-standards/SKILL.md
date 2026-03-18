# Skill: agent-standards

**Category**: Agent Infrastructure
**Adapted for**: baseball-crawl

---

## Activation Triggers

Load this skill when you are about to:

- **Create a new agent** -- designing the frontmatter, system prompt, and section structure
- **Modify an existing agent definition** -- updating responsibilities, tools, or prompt content
- **Audit agent definitions** -- reviewing quality, completeness, or ecosystem fit
- **Review agent ecosystem structure** -- checking for gaps, overlaps, or routing issues

---

## Design Methodology

When creating or modifying agents, follow this 7-step process:

1. **Intent Analysis**: What exactly does the user need? What are the explicit and implicit requirements?
2. **Ecosystem Fit**: How does this agent fit with existing agents? What interactions exist? Check for overlap.
3. **Persona Design**: What expert identity best serves this function?
4. **Scope Definition**: What are the precise boundaries? What does this agent do and NOT do?
5. **Prompt Engineering**: Craft the system prompt following the canonical section skeleton below.
6. **Trigger Design**: Write a concise `description` field (1-3 sentences, no routing examples) that gives the PM enough information to dispatch correctly.
7. **Validation**: Self-review the configuration against the quality standards below.

---

## Standards

### Agent File Format

Agent files are markdown files at `.claude/agents/[name].md` with YAML frontmatter:

```
---
name: agent-name
description: "Concise 1-3 sentence routing trigger."
model: sonnet|opus|haiku
color: blue|green|red|orange|yellow|cyan|purple|magenta
memory: project
tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
  - WebFetch
---

# Agent Name -- Role Tagline

## Identity
...rest of system prompt...
```

### Required Frontmatter Fields (in this order)
1. `name` -- agent identifier
2. `description` -- 1-3 concise sentences for routing (no examples, no multi-paragraph blocks)
3. `model` -- `haiku` (routing), `sonnet` (balanced), `opus` (deep reasoning)
4. `color` -- visual identification
5. `memory` -- `project` for all agents in this repo
6. `tools` -- explicit list of tools the agent needs

### Canonical Section Skeleton

Every agent system prompt should follow this section order. Skip sections that do not apply, but do not reorder.

```
# [Agent Name] -- [Role Tagline]
## Identity
## Core Responsibilities
## [Domain-Specific Standards]
## Anti-Patterns
## Error Handling
## Inter-Agent Coordination
## Skill References
## Memory
```

### Quality Standards

Every agent configuration must:
- Have a system prompt that could serve as a complete operational manual for its domain.
- Include specific, actionable instructions (not vague platitudes).
- Anticipate edge cases with an Error Handling section.
- List concrete Anti-Patterns (what the agent must NOT do).
- Reference CLAUDE.md for shared conventions rather than duplicating content.
- Have a `description` precise enough for routing but short enough to scan.
- Align with project-specific patterns in CLAUDE.md (core principle, coding style, project management workflow).

### Research & Investigation

When researching aspects of the Claude Code ecosystem:
1. Use the **Task tool** for simple, single-agent consultations (e.g., asking baseball-coach a domain question).
2. Use **Agent Teams** for multi-agent coordination when investigating topics that require parallel research across multiple domains.
3. Synthesize findings into actionable recommendations specific to this project.
4. Document discoveries in agent memory for future reference.

### Output Formats

When creating or modifying agents, produce the complete markdown file with YAML frontmatter (the agent file format described above).

When auditing or managing the ecosystem, provide:
- Agent topology maps
- Gap/overlap analysis with specific recommendations
- Migration plans when restructuring

When designing the semantic layer, provide:
- Intent taxonomies
- Agent routing logic updates for CLAUDE.md and agent-routing.md
- Coverage matrices

---

## References

Existing agent definitions for reference:
- `.claude/agents/product-manager.md` -- largest agent, full operational manual pattern
- `.claude/agents/software-engineer.md` -- implementation agent pattern
- `.claude/agents/code-reviewer.md` -- review/audit agent pattern
- CLAUDE.md Agent Ecosystem table -- authoritative agent roster
