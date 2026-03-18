# E-126-02: Consolidate MEMORY.md with Topic Files

## Epic
[E-126: Optimize Claude-Architect Context Footprint](epic.md)

## Status
`TODO`

## Description
After this story is complete, the architect's MEMORY.md will be under 110 lines. Historical ingest workflow logs and Codex configuration details will live in dedicated topic files. Duplicated content (Agent Ecosystem, Agent Frontmatter) will be removed with pointers to authoritative sources.

## Context
The architect's MEMORY.md is 174 lines -- the largest agent memory file, approaching the 200-line truncation threshold. ~76 lines are historical reference material (ingest logs ~50 lines, Codex config ~9 lines) or duplication of content available elsewhere (Agent Ecosystem ~12 lines duplicates CLAUDE.md, Agent Frontmatter ~5 lines will be covered by the agent-standards skill from E-126-01).

## Acceptance Criteria
- [ ] **AC-1**: A topic file exists at `.claude/agent-memory/claude-architect/ingest-workflow-log.md` containing the per-endpoint integration history currently inline in MEMORY.md. MEMORY.md contains a 2-line summary linking to this topic file in place of the full log.
- [ ] **AC-2**: A topic file exists at `.claude/agent-memory/claude-architect/codex-config.md` containing the Codex configuration details currently inline in MEMORY.md. MEMORY.md contains a 1-line reference in place of the full content.
- [ ] **AC-3**: The Agent Ecosystem section is removed from MEMORY.md (CLAUDE.md is authoritative).
- [ ] **AC-4**: The Agent Frontmatter section is removed from MEMORY.md (covered by the agent-standards skill).
- [ ] **AC-5**: MEMORY.md is under 110 lines.
- [ ] **AC-6**: Every section removed from MEMORY.md exists verbatim (or with only formatting changes) in a topic file, or is covered by an explicit reference to an authoritative source (CLAUDE.md, agent-standards skill). Verified by diff comparison of removed content against topic file contents.

## Technical Approach
The architect should read its own MEMORY.md, identify each section targeted for extraction or removal, create the topic files, and update MEMORY.md with references. Per TN-3 in the epic.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `.claude/agent-memory/claude-architect/ingest-workflow-log.md` (create)
- `.claude/agent-memory/claude-architect/codex-config.md` (create)
- `.claude/agent-memory/claude-architect/MEMORY.md` (modify)

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] No regressions in existing agent behavior
- [ ] Code follows project style (see CLAUDE.md)

## Notes
- Line counts are approximate -- the architect should use actual content when determining what to extract.
- The Agent Frontmatter removal (AC-4) is safe regardless of whether E-126-01 has completed, since the content is duplicative of what will be in the skill.
- Sections NOT listed for extraction or removal are retained as-is: Core Principle, Project, Key Architectural Decisions, User Preferences, Topic File Index, Claude Code Platform Facts, Epic History, Skills Index, Domain Reference Documents, Known Hallucination Traps.
- The 2-line ingest log summary (AC-1) should include the endpoint count and date range so the architect can judge whether to load the full log (e.g., "19 endpoints ingested (2026-03-04). Full per-endpoint integration log: `ingest-workflow-log.md`").
- When creating the new topic files (`ingest-workflow-log.md` and `codex-config.md`), add corresponding entries to the Topic File Index section in MEMORY.md so future conversations can discover them.
- When extracting the ingest workflow logs to `ingest-workflow-log.md`, consolidate the 18 fragmented `## continued` headers into a single `## Ingest-Endpoint Workflow Executions` section with per-endpoint entries. The topic file should be well-organized, not a raw copy of the fragmented MEMORY.md structure.
- The "When to Create New Agents" guideline (inside the Agent Ecosystem section) is covered by Anti-Pattern #4 in the claude-architect agent definition. The implementer should verify this coverage during the AC-6 diff review. If the anti-pattern wording is insufficient, add a one-line equivalent to a retained section before removing Agent Ecosystem.
