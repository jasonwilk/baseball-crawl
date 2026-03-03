# E-021: Agent Workflow Guardrails

## Status
`COMPLETED`
<!-- Lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED) -->
<!-- PM sets READY explicitly after: expert consultation done, all stories have testable ACs, quality checklist passed. -->
<!-- Only READY and ACTIVE epics can be dispatched. -->

## Overview

Harden agent configurations, rules, and CLAUDE.md to prevent three recurring workflow violations: the PM doing implementation work directly, unverified assumptions propagating into epic documentation, and the orchestrator bypassing the dispatch pipeline. These violations have caused wasted effort and incorrect deliverables. This epic fixes root causes in agent definitions and rule files so violations are structurally prevented, not just verbally prohibited.

## Background & Context

Three classes of agent workflow violations have occurred repeatedly in this project:

### Violation 1: PM Doing Implementation Work

The PM was instructed (by the orchestrator) to use Write/Edit/Bash tools to implement code changes directly, violating the workflow contract. The PM's system prompt says "You do NOT write code, run tests, or execute commands" -- but the PM agent frontmatter has **no `tools` field**, which means it receives ALL tools by default (including Write, Edit, Bash, Glob, Grep, WebFetch, and everything else). Every other agent in the ecosystem has explicit tool restrictions in its frontmatter. The PM is the only agent where the prohibition is purely prose-based with no technical enforcement.

**Root cause**: Missing `tools` field in `/Users/jason/Documents/code/baseball-crawl/.claude/agents/product-manager.md` YAML frontmatter. The PM needs Read/Glob/Grep (to read project state), Write/Edit (to write spec files like epics and stories), and team/task tools (to dispatch work). It does NOT need Bash, WebFetch, or any tool that enables code execution or testing.

### Violation 2: Unverified Assumptions in Epic Documentation

Research spikes produced findings about deployment infrastructure (VPS hosting, Hetzner, etc.) that were promoted into epic Technical Notes and propagated across multiple epics without ever being verified with the user. The user actually hosts on home Linux servers with Cloudflare Tunnel -- not on a VPS. No PM rule or prompt section requires verifying user-facing assumptions before baking them into epic documentation.

**Root cause**: No "assumption verification" checkpoint in the PM workflow. Research spike findings are treated as facts and propagated into Technical Notes without a user-confirmation step. The PM prompt has a "Completing a research spike" checklist that says "Note key findings in epic Technical Notes if decision-relevant" but never says "verify with user if findings involve user infrastructure, preferences, or constraints."

### Violation 3: Orchestrator Bypassing Dispatch Pipeline

When the PM could not use the Agent tool to spawn implementing agents, the orchestrator improvised two workarounds: (a) dispatching implementing agents directly (skipping PM), and (b) instructing the PM to do the implementation work itself. Both are routing violations. The orchestrator's Anti-Patterns section says "Never route implementation work directly to general-dev or data-engineer" but provides no guidance for what to do when the normal dispatch path fails.

**Root cause**: No "dispatch failure protocol" in either the orchestrator prompt or `workflow-discipline.md`. The orchestrator has prohibitions but no fallback procedure. When the happy path breaks, there is no defined escalation path -- so the agent invents one, and the invention violates the rules.

### Expert Consultation

**Claude Architect consultation**: COMPLETED. The PM audited all 7 agent configuration files, both rule files (`dispatch-pattern.md`, `workflow-discipline.md`), and the `multi-agent-patterns` skill. CA review findings:

1. **Tool restriction via frontmatter is the correct approach.** The `tools` field in YAML frontmatter is the standard enforcement mechanism used by all other agents. The orchestrator confirms this works (Anti-Pattern #4: "You have no Write, Edit, or Bash tools. This is intentional."). No PreToolUse hook is needed -- that mechanism is for content checking (e.g., PII scanning), not tool access control.
2. **Additional gap identified: PM has no Anti-Patterns section.** Every other implementation-adjacent agent has one (orchestrator, general-dev, data-engineer). The PM needs an Anti-Patterns section explicitly prohibiting code execution, web browsing, and direct implementation. This is addressed in E-021-01.
3. **Assumption verification belongs in PM prompt only.** The checkpoint applies specifically to the PM's "Completing a research spike" checklist. No other agent promotes research findings into epic Technical Notes, so a rule file would add noise. The detailed checkpoint goes in the PM prompt; workflow-discipline.md does not need it.
4. **All PM changes fit in one story.** The frontmatter `tools` field, Anti-Patterns section, and assumption verification checkpoint are three independent additions to different sections of `product-manager.md`. No ordering constraint exists between them. One story, one file.
5. **CLAUDE.md does not need updates.** The Agent Ecosystem section describes agent roles and routing, not tool restrictions. The existing description of the PM ("owns what to build, why, and in what order") remains accurate. Tool restrictions are implementation details in agent files, not CLAUDE.md-level documentation.

## Goals

- PM agent is structurally prevented from executing code (Bash) or running tests, enforced by tool restrictions in frontmatter
- PM agent prompt includes explicit anti-patterns and a verification checkpoint for infrastructure/deployment assumptions
- Orchestrator agent prompt includes a dispatch failure protocol that escalates to the user rather than improvising workarounds
- `workflow-discipline.md` rule file codifies the dispatch failure escalation path for all agents
- All changes are internally consistent (agent prompts, rule files, and CLAUDE.md Agent Ecosystem section aligned)

## Non-Goals

- Rewriting the entire PM or orchestrator agent prompt (targeted additions only)
- Changing the dispatch mechanism itself (Agent Teams is the correct approach)
- Adding automated enforcement hooks (PreToolUse) for PM tool restrictions -- frontmatter `tools` field is sufficient and simpler
- Addressing other agent prompt quality issues (covered by the completed E-020)
- Changing which tools the orchestrator has (it is already correctly restricted to Task, Read, Glob, Grep)

## Success Criteria

1. The PM agent frontmatter includes an explicit `tools` field that excludes Bash and WebFetch.
2. The PM agent prompt contains an Anti-Patterns section (or addition to existing) that explicitly prohibits code execution, test running, and direct implementation.
3. The PM agent prompt contains an assumption verification checkpoint for research spike findings that involve user infrastructure, deployment, or preferences.
4. The orchestrator agent prompt contains a "Dispatch Failure Protocol" section that instructs it to escalate to the user when PM dispatch fails, rather than improvising workarounds.
5. `workflow-discipline.md` contains a "Dispatch Failure Protocol" section consistent with the orchestrator prompt addition.
6. All agents' Anti-Patterns sections are consistent with the updated rules.

## Stories

| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-021-01 | Harden PM Agent -- Tool Restrictions, Anti-Patterns, and Assumption Verification | DONE | None | claude-architect |
| E-021-02 | Add Dispatch Failure Protocol to Orchestrator | DONE | None | claude-architect |
| E-021-03 | Add Dispatch Failure Protocol to Workflow Discipline Rule | DONE | None | claude-architect |

All three stories are independent (no file conflicts) and can be executed in parallel.

## Technical Notes

### Files to Modify

Each story modifies exactly one file, enabling full parallel execution:

1. **`/Users/jason/Documents/code/baseball-crawl/.claude/agents/product-manager.md`** (E-021-01) -- Add `tools` field to frontmatter. Add Anti-Patterns section. Add assumption verification checkpoint to research spike checklist.
2. **`/Users/jason/Documents/code/baseball-crawl/.claude/agents/orchestrator.md`** (E-021-02) -- Add Dispatch Failure Protocol section. Add fifth Anti-Pattern item.
3. **`/Users/jason/Documents/code/baseball-crawl/.claude/rules/workflow-discipline.md`** (E-021-03) -- Add Dispatch Failure Protocol section.

CLAUDE.md does not need updates -- the Agent Ecosystem section describes roles and routing, not tool restrictions.

### PM Tool Restriction Rationale

The PM needs these tools to do its job:
- **Read**: Read epic files, story files, research artifacts, project state
- **Glob**: Find files by pattern (e.g., scan `/epics/` directory)
- **Grep**: Search file contents (e.g., find status fields)
- **Write**: Create new spec files (epics, stories, ideas)
- **Edit**: Update existing spec files (status changes, AC refinements)

The PM does NOT need:
- **Bash**: The PM does not run scripts, tests, or commands. All its file operations use Read/Write/Edit.
- **WebFetch**: The PM does not browse the web. Research is delegated to other agents.

Note: The PM also needs access to TeamCreate, SendMessage, TaskCreate/Update/Get/List, and similar coordination tools. These are not restricted by the `tools` frontmatter field (they are always available to all agents).

### Assumption Verification Design

The PM prompt should include a checkpoint in the research spike completion workflow:

> When a research spike produces findings about user infrastructure, deployment environment, hosting preferences, or any decision that depends on the user's specific setup rather than pure technical evaluation -- verify the findings with the user before promoting them to epic Technical Notes. Research spikes evaluate options; the user selects.

This applies to the "Completing a research spike" checklist in the PM prompt.

### Dispatch Failure Protocol Design

When the orchestrator routes a dispatch request to PM and PM reports that dispatch cannot proceed (e.g., Agent tool unavailable, team creation fails, no eligible stories), the orchestrator should:

1. Report the failure to the user with the specific reason.
2. Ask the user how to proceed.
3. Never improvise a workaround (e.g., dispatching directly, asking PM to implement).

This is an escalation, not a retry. The user decides the next step.

## Open Questions

_All resolved during refinement. See Expert Consultation section for answers._

1. ~~**CA Review**: Does restricting PM tools via frontmatter fully prevent the violation?~~ **RESOLVED**: Yes. Frontmatter `tools` field is the standard enforcement mechanism. Same approach used by all other agents. No PreToolUse hook needed.
2. ~~**CA Review**: Are there additional agent configuration gaps?~~ **RESOLVED**: One additional gap -- PM missing Anti-Patterns section. Addressed in E-021-01.
3. ~~**CA Review**: Should assumption verification be in PM prompt only or also a rule file?~~ **RESOLVED**: PM prompt only. The checkpoint applies specifically to the PM's research spike workflow. No other agent performs this function.
4. ~~**Story boundaries**: One story or multiple for PM changes?~~ **RESOLVED**: One story (E-021-01). All three changes (frontmatter, Anti-Patterns, assumption verification) are independent additions to different sections of the same file. No ordering constraint.

## History
- 2026-03-02: Created as DRAFT. PM self-audited all 7 agent configs, 2 rule files, 1 skill file, and CLAUDE.md. Three root causes identified. CA consultation pending before writing stories and moving to READY.
- 2026-03-02: CA consultation completed (PM performed deep review of all agent configs, rule files, hooks, and settings). All 4 open questions resolved. 3 stories written. One additional gap identified (PM missing Anti-Patterns section). Epic moved to READY.
