# E-029: Context-Layer Routing Enforcement

## Status
`COMPLETED`
<!-- Lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED) -->
<!-- PM sets READY explicitly after: expert consultation done, all stories have testable ACs, quality checklist passed. -->
<!-- Only READY and ACTIVE epics can be dispatched. -->

## Overview
Establish enforceable routing rules so that any story touching context-layer files (CLAUDE.md, `.claude/rules/`, `.claude/agents/`, `.claude/agent-memory/`, `.claude/hooks/`, `.claude/skills/`, `.claude/settings.json`) is always dispatched to the claude-architect, never to general-dev or other implementing agents. This closes a recurring dispatch routing gap that has caused mis-routed stories in E-019 and E-027.

## Background & Context
During E-027 (Devcontainer-to-Compose Networking), story E-027-02 added a troubleshooting section to CLAUDE.md. The PM dispatched it to a general-dev agent. But CLAUDE.md is part of the agent context layer -- it is loaded into every agent's system prompt. Changes to it affect how all agents behave. This should have been routed to the claude-architect.

This is the second occurrence of this class of error. E-019-02 and E-019-04 also touched `.claude/hooks/`, `.claude/settings.json`, `.claude/rules/`, and CLAUDE.md, and were dispatched to general-dev. The PM's lessons-learned.md already documented the E-019 error, but a memory note proved insufficient -- the same mistake recurred in E-027.

The root cause: the dispatch-pattern routing table says "Agent config, CLAUDE.md, rules, skills -> claude-architect" but this description is ambiguous. It does not enumerate the specific file paths that constitute context-layer work, and there is no procedural check in the PM's dispatch flow that forces a file-path scan before selecting an agent type. The PM must remember to classify the domain correctly, which is error-prone when a story's primary domain is something else (e.g., "document networking" in E-027) but happens to touch a context-layer file.

No expert consultation required -- this is a PM + claude-architect process fix within the existing dispatch infrastructure. Both agents' definitions and the shared dispatch-pattern rule are well-understood. The solution is straightforward: define context-layer paths explicitly and add a file-path-based routing check.

## Goals
- Define "context-layer files" as an explicit, enumerated set of file paths in the dispatch pattern
- Add a procedural check to the PM's dispatch flow that scans each story's "Files to Create or Modify" against the context-layer path list before selecting an agent type
- Eliminate the class of error where stories touching context-layer files are dispatched to the wrong agent

## Non-Goals
- Changing which agent types exist or creating new agents
- Modifying the claude-architect's responsibilities or capabilities
- Automated enforcement via hooks or tooling (a clear rule + procedural check is sufficient for now)
- Retroactively fixing E-019 or E-027 deliverables (both are completed and correct)

## Success Criteria
- The dispatch-pattern routing table includes an explicit "Context-layer files" entry with enumerated path patterns
- The PM agent definition includes a dispatch pre-check step that scans story file lists against context-layer paths
- A hypothetical story that modifies only CLAUDE.md would be unambiguously routed to claude-architect by following the documented procedure

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-029-01 | Expand dispatch-pattern routing table with context-layer file paths | DONE | None | claude-architect |
| E-029-02 | Add context-layer routing pre-check to PM agent definition | DONE | None | claude-architect |

## Technical Notes

### Context-Layer File Paths
The following file paths and path patterns constitute "context-layer" work. Any story whose "Files to Create or Modify" section includes one or more of these paths MUST be dispatched to `claude-architect`, regardless of the story's primary domain.

| Path Pattern | Description |
|-------------|-------------|
| `CLAUDE.md` | Project instructions loaded into every agent's system prompt |
| `.claude/agents/*.md` | Agent definitions |
| `.claude/rules/*.md` | Shared rules loaded by all agents |
| `.claude/skills/**` | Skill definitions and documentation |
| `.claude/hooks/**` | Lifecycle hooks (pre-commit, statusline, etc.) |
| `.claude/settings.json` | Claude Code configuration |
| `.claude/settings.local.json` | Local Claude Code overrides |
| `.claude/agent-memory/**` | Agent persistent memory files |

### Routing Rule
The context-layer routing rule takes precedence over domain-based routing. Example: a story that adds a "troubleshooting" section to CLAUDE.md is context-layer work even though the content being added is about Docker networking. The file being modified determines the routing, not the content being written.

**Exception**: PM updating its own memory files (`.claude/agent-memory/product-manager/`) during normal status-update work does not require routing to claude-architect. The rule applies to stories that modify context-layer files as their deliverable.

### Files Modified by This Epic
- `/.claude/rules/dispatch-pattern.md` -- expanded routing table (E-029-01)
- `/.claude/agents/product-manager.md` -- dispatch pre-check step (E-029-02)

### No File Conflicts
E-029-01 modifies `dispatch-pattern.md`. E-029-02 modifies `product-manager.md`. No shared files -- stories can run in parallel.

## Open Questions
- None.

## History
- 2026-03-03: Created. Prompted by E-027 dispatch routing error (CLAUDE.md edit dispatched to general-dev instead of claude-architect). READY -- no expert consultation needed; both target files are well-understood context-layer artifacts.
- 2026-03-03: COMPLETED. Both stories executed and verified. E-029-01 expanded dispatch-pattern.md routing table with 8 explicit context-layer path patterns and added a Routing Precedence note. E-029-02 added a context-layer routing pre-check step to the PM's Dispatch Procedure and added Anti-Pattern #4 citing the E-019/E-027 failure pattern. Archived to /.project/archive/E-029-context-layer-routing/.
