<!-- synthetic-test-data -->
# Lessons Learned (Product Manager)

Detailed notes on patterns and lessons from past epics. MEMORY.md links here.

## Epic Authoring Patterns
- A vague epic is worse than no epic. When scope is unclear, write an idea, not an epic.
- E-002 and E-003 were written as DRAFT intentionally -- they depend on E-001-03 (API spec) before implementing agents can fill in real endpoint names.
- E-004 has no stories yet -- needs a conversation with user about specific dashboard views before stories can be written with real acceptance criteria.
- E-005-03 (retrofit GC client) may become a no-op if E-001-02 is written after E-005-02 exists.

## Story Dependency Patterns
- E-006-03 pattern: when a story depends on another agent's design decision, mark it BLOCKED with an explicit unblock condition (file path + what the file must contain). Do not write a research spike when another agent is doing the research -- just block on their deliverable.
- E-006 refinement pattern: initial stories written before the architect's design doc will have vague "technical approach" sections. After the design doc exists, rewrite those sections to be specific.
- E-012 pattern: when a Phase 2 story is BLOCKED on unrelated deps, extract the unblocked subset into a separate focused epic that can ship immediately.

## Process Patterns
- E-007: general-dev.md and data-engineer.md were created from scratch (did not exist before E-007-05).
- E-007 Dispatch Mode execution: PM can execute infrastructure stories directly without Task tool when PM is the coordinating agent in a single session.
- Decision Gates pattern (E-007-09): Evaluation epics need a gate story as their final story. PM executes it directly. Criteria must be in Technical Notes before stories are written. Three outcomes: APPROVED, REJECTED, DEFERRED.
- E-009 failure: status updates drifted out of sync. E-011 addresses with atomic status update protocol.
- Numbering collision (2026-02-28): before assigning a new epic number, ALWAYS ls /epics/ -- do not rely solely on memory's "next available" number.
- E-011 pattern: process-domain research spikes can be resolved by PM directly (no expert consultation).

## Platform Constraints
- Agent Teams (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`) is the dispatch mechanism. PM uses TeamCreate + Agent tool with team_name to spawn implementing agents. No nesting limit.
- Task tool: use for single-agent consultations (e.g., consulting baseball-coach). Cannot nest further.
- E-015 consultation pattern: when the consultation itself would trigger the bug being diagnosed, read the expert's memory files directly instead.

## Agent Routing Lessons

- **E-019 routing error**: E-019-02 (`.claude/hooks/`, `.claude/settings.json`, `.claude/rules/`) and the CLAUDE.md edit in E-019-04 were dispatched to `general-dev`. These are `claude-architect` domain. The dispatch-pattern table is clear: "Agent config, CLAUDE.md, rules, skills" → `claude-architect`. For future epics touching `.claude/` infrastructure or `CLAUDE.md`, route those stories to `claude-architect`, not `general-dev`.

## E-019 Dispatch Lessons
- Agent Teams spawn tool was not available in PM's tool set during this session. PM executed all 4 stories directly. **This was a workflow violation** -- the PM should never execute implementation stories directly. The root cause was the PM agent having no `tools` field in frontmatter, giving it all tools by default including Bash. E-021 addresses this by adding explicit tool restrictions to PM frontmatter.
- The E-019 lesson that "PM has all the tools needed (Read/Write/Edit/Bash)" was itself wrong -- the PM should NOT have Bash. Bash enables code execution and test running, which are implementation tasks, not PM tasks.
- Scanner source files containing pattern descriptions (regexes, examples) triggered the scanner itself. Fixed by adding `synthetic-test-data` marker to `pii_patterns.py` and `pii_scanner.py`. Any file that documents PII patterns needs this marker.
- Relative imports in `pii_scanner.py` fail when run as standalone script from hook (`python3 src/safety/pii_scanner.py`). Fixed with try/except fallback to absolute import. Any module called both as package import (tests) and standalone script (hooks) needs this pattern.
- Test data containing long hex strings (e.g., `abcdef1234567890`) can false-positive on the phone regex. Use obviously non-numeric fake values in test data.
- `Path(".env").suffix` returns `""` not `".env"`. Dotfile handling requires checking the filename itself when suffix is empty.
- Git repository must exist for hook verification. E-019 stories assume git init has already happened. The project root had no `.git/` -- had to initialize for testing.

## Workflow Violation Root Causes (E-021)

Three recurring violations identified in 2026-03-02 audit:

1. **PM tool gap**: PM agent frontmatter had no `tools` field -- only agent in the ecosystem without one. Got all tools by default. Prose prohibition ("do NOT write code") is not enforceable without tool restrictions.
2. **Assumption propagation**: Research spike findings about user infrastructure (VPS/Hetzner) were promoted to epic Technical Notes without user verification. No checkpoint in PM workflow requires user confirmation for infrastructure assumptions.
3. **Orchestrator improvisation**: When PM dispatch failed, orchestrator had no defined fallback -- improvised workarounds (direct dispatch, telling PM to implement) that violated routing rules. Needs an explicit "dispatch failure protocol" that escalates to user.

**Key lesson**: Prose prohibitions without technical enforcement are insufficient. If an agent should not do X, restrict the tools that enable X.

## MCP Research
- See mcp-research.md for full findings. No MCP servers recommended today. github/github-mcp-server worth adopting when GitHub remote established. GitNexus worth revisiting at ~100 Python files.
