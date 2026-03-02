# E-018: Agent Frontmatter Refinement

## Status
`COMPLETED`
<!-- Lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED) -->
<!-- PM sets READY explicitly after: expert consultation done, all stories have testable ACs, quality checklist passed. -->
<!-- Only READY and ACTIVE epics can be dispatched. -->

## Overview
Four agent configuration files (api-scout, baseball-coach, general-dev, data-engineer) have incomplete YAML frontmatter -- bloated description fields with embedded routing examples, missing `tools` restrictions, and inconsistent field coverage. This epic brings them up to the quality standard established by the orchestrator and product-manager agents, using a documented frontmatter standard based on the Claude Code subagent documentation.

## Background & Context
The user observed that four agent files "don't have good frontmatter." Comparing them against the orchestrator (which has a concise one-sentence `description` and explicit `tools` list) and the product-manager (concise description, appropriate fields), the four target agents all share the same problems:

1. **Bloated `description` fields**: Each embeds 5 multi-line routing examples directly in the YAML description string. Per the Claude Code docs, the description field tells Claude "when to delegate to this subagent" -- it should be a concise routing trigger, not a manual.

2. **Missing `tools` field**: None of the four specify tool restrictions. Per the Claude Code docs best practice: "Limit tool access: grant only necessary permissions for security and focus."

3. **No `skills` preloading**: All four reference skills in their system prompt body with "Load when:" directives, but none use the `skills` frontmatter field. After analysis, on-demand loading is preferred (preloading injects full skill content into context at startup, wasting tokens when skills are conditionally needed).

**Expert consultation**: The PM produced the frontmatter standard directly based on the Claude Code subagent documentation (https://code.claude.com/docs/en/sub-agents) and analysis of the seven existing agent files. The standard is documented at `/.project/research/E-018-frontmatter-standard.md`. The implementing agent (claude-architect) will execute the four implementation stories against this standard.

## Goals
- All four agent files have concise, 1-3 sentence `description` fields that clearly communicate when to delegate to the agent
- All four agent files have explicit `tools` fields scoped to their actual needs
- Frontmatter fields appear in a consistent order across all agent files: `name`, `description`, `model`, `color`, `memory`, `tools`
- Routing examples removed from YAML description fields entirely

## Non-Goals
- Rewriting agent system prompts (body content) beyond removing relocated routing examples
- Adding new agents or changing agent responsibilities
- Modifying the orchestrator, product-manager, or claude-architect agent files (they are the reference standard, not targets)
- Changing agent models, colors, or memory scope
- Adding `skills` preloading, `maxTurns`, `permissionMode`, `hooks`, `isolation`, or `background` fields (decisions documented in the standard with rationale)

## Success Criteria
- All four target agent files have exactly these frontmatter fields: `name`, `description` (concise), `model`, `color`, `memory`, `tools`
- No agent has multi-paragraph routing examples embedded in its YAML `description` field
- Each agent's `tools` list matches its actual role (consultative agents restricted, implementing agents explicit)
- All seven agent files in `.claude/agents/` follow a consistent frontmatter pattern

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-018-R-01 | Define the frontmatter standard | DONE | None | PM |
| E-018-01 | Refine api-scout frontmatter | DONE | None | claude-architect |
| E-018-02 | Refine baseball-coach frontmatter | DONE | None | claude-architect |
| E-018-03 | Refine general-dev frontmatter | DONE | None | claude-architect |
| E-018-04 | Refine data-engineer frontmatter | DONE | None | claude-architect |

## Technical Notes
### Frontmatter Standard Reference
The full frontmatter standard is at `/Users/jason/Documents/code/baseball-crawl/.project/research/E-018-frontmatter-standard.md`. Key decisions:

1. **Description**: 1-3 concise sentences. No routing examples. Pattern: "[Role]. [Key domain/trigger]. [Boundary if needed]."

2. **Tools allowlists**:
   - api-scout: Read, Write, Edit, Bash, Glob, Grep, WebFetch
   - baseball-coach: Read, Write, Edit, Glob, Grep (most restricted -- no Bash, no WebFetch)
   - general-dev: Read, Write, Edit, Bash, Glob, Grep, WebFetch
   - data-engineer: Read, Write, Edit, Bash, Glob, Grep, WebFetch

3. **Skills**: On-demand loading (current approach) preferred over frontmatter preloading. No changes needed to skill references in system prompt body.

4. **Field ordering**: name, description, model, color, memory, tools

5. **Routing examples**: Remove entirely. The orchestrator's routing table and CLAUDE.md Agent Ecosystem section already handle delegation logic.

### File Paths
- `/Users/jason/Documents/code/baseball-crawl/.claude/agents/api-scout.md`
- `/Users/jason/Documents/code/baseball-crawl/.claude/agents/baseball-coach.md`
- `/Users/jason/Documents/code/baseball-crawl/.claude/agents/general-dev.md`
- `/Users/jason/Documents/code/baseball-crawl/.claude/agents/data-engineer.md`
- Reference: `/Users/jason/Documents/code/baseball-crawl/.claude/agents/orchestrator.md`
- Reference: `/Users/jason/Documents/code/baseball-crawl/.claude/agents/product-manager.md`
- Standard: `/Users/jason/Documents/code/baseball-crawl/.project/research/E-018-frontmatter-standard.md`

### Parallel Execution
All four implementation stories (E-018-01 through E-018-04) touch different files and can run in parallel with no conflicts.

## Open Questions
None remaining. All questions resolved in E-018-R-01 (see standard document).

## History
- 2026-03-02: Created as DRAFT. Identified problems and open questions.
- 2026-03-02: PM produced frontmatter standard based on Claude Code docs research. E-018-R-01 marked DONE. Created E-018-04 story file. Updated all story ACs with concrete, testable criteria. Set to READY.
- 2026-03-02: All four implementation stories completed by claude-architect. All frontmatter refined per standard. Epic COMPLETED.
