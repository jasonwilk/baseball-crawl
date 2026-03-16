# E-112-01: Fix MEMORY.md Truncation for 5 Agents

## Epic
[E-112: Context Layer Optimization](./epic.md)

## Status
`DONE`

## Description
After this story is complete, all 6 agent MEMORY.md files will be concise indexes under 150 lines, with detailed content extracted to topic files in each agent's memory directory. This fixes silent truncation where content beyond line 200 is dropped -- currently affecting 5 of 6 agents, with the most valuable memory entries (coaching decisions, ETL patterns, DB conventions) being invisible.

## Context
The 200-line MEMORY.md limit is a system constraint that silently drops content beyond line 200. Five agents exceed this limit, losing critical operational knowledge. This is the highest-impact story in the epic because it restores information that agents are currently operating without.

## Acceptance Criteria
- [ ] **AC-1**: baseball-coach MEMORY.md is under 150 lines and all content from the original file (especially coaching decisions starting at line ~274) is preserved in topic files within `.claude/agent-memory/baseball-coach/`
- [ ] **AC-2**: data-engineer MEMORY.md is under 150 lines and all content (ETL patterns, pagination patterns, token scheduling) is preserved in topic files within `.claude/agent-memory/data-engineer/`
- [ ] **AC-3**: software-engineer MEMORY.md is under 150 lines and all content (DB conventions, auth patterns, testing rules) is preserved in topic files within `.claude/agent-memory/software-engineer/`
- [ ] **AC-4**: api-scout MEMORY.md is under 150 lines and all content (boxscore facts, JWT tips, security rules) is preserved in topic files within `.claude/agent-memory/api-scout/`
- [ ] **AC-5**: product-manager MEMORY.md is under 150 lines and all content (archived epics list is the primary extraction target) is preserved in topic files within `.claude/agent-memory/product-manager/`
- [ ] **AC-6**: claude-architect MEMORY.md (currently 174 lines, under limit) is reviewed and left as-is or lightly trimmed if beneficial -- no content loss
- [ ] **AC-7**: Each extracted topic file uses plain markdown (heading + content), consistent with the existing agent-memory topic file convention (e.g., `claude-architect/semantic-layer.md`, `claude-architect/agent-design.md`). No YAML frontmatter -- the MEMORY.md index serves as the discovery and relevance-matching mechanism.
- [ ] **AC-8**: Each MEMORY.md index entry links to its topic file with a brief description sufficient for relevance matching

## Technical Approach
Read each agent's MEMORY.md, identify logical topic groupings, extract detailed content to topic files, and restructure the index. The index should be organized semantically (not chronologically). Topic file names should be descriptive of their content. Topic files use plain markdown (heading + content) with no YAML frontmatter -- consistent with existing agent-memory topic files. The MEMORY.md index provides discovery; topic files provide content.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `.claude/agent-memory/baseball-coach/MEMORY.md` (modify)
- `.claude/agent-memory/baseball-coach/*.md` (create topic files as needed)
- `.claude/agent-memory/data-engineer/MEMORY.md` (modify)
- `.claude/agent-memory/data-engineer/*.md` (create topic files as needed)
- `.claude/agent-memory/software-engineer/MEMORY.md` (modify)
- `.claude/agent-memory/software-engineer/*.md` (create topic files as needed)
- `.claude/agent-memory/api-scout/MEMORY.md` (modify)
- `.claude/agent-memory/api-scout/*.md` (create topic files as needed)
- `.claude/agent-memory/product-manager/MEMORY.md` (modify)
- `.claude/agent-memory/product-manager/*.md` (create topic files as needed)
- `.claude/agent-memory/claude-architect/MEMORY.md` (review, modify only if beneficial)

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] No agent memory content is lost (restructured, not deleted)
- [ ] All MEMORY.md files are under 150 lines

## Notes
- The 200-line limit is a system constraint, not a convention -- content beyond line 200 is literally invisible to the agent
- baseball-coach is the worst case: coaching decisions (the most valuable content) start at line ~274 and are completely invisible
- product-manager is barely over (203 lines) -- the archived epics list is the extraction target
- claude-architect is under the limit (174 lines) but should be reviewed for consistency
- Index descriptions should be specific enough that an agent can determine relevance without opening the topic file. Prefer concrete nouns over abstract labels (e.g., "ETL pagination patterns and 5xx retry behavior" over "data pipeline notes")
