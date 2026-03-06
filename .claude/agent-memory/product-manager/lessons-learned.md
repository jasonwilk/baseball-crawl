<!-- synthetic-test-data -->
# Lessons Learned (Product Manager)

Detailed notes on patterns and lessons from past epics. MEMORY.md links here.

## Epic Authoring Patterns
- A vague epic is worse than no epic. When scope is unclear, write an idea, not an epic.
- E-002 and E-003 were written as DRAFT intentionally -- they depend on E-001-03 (API spec) before implementing agents can fill in real endpoint names.
- E-004 has no stories yet -- needs a conversation with user about specific dashboard views before stories can be written with real acceptance criteria.
- E-005-03 (retrofit GC client) may become a no-op if E-001-02 is written after E-005-02 exists.
- **"Lanes" evaluation (2026-03-03)**: E-034 used lane-style headers in Technical Notes to scope workstream-specific content (Lane A: Code Review, Lane B: Spec Review, Lane C: Workflow Integration). Evaluated whether to formalize as a convention. **Decision: DEFER.** Lanes are a useful writing technique for scoping Technical Notes when an epic has 3+ independent workstreams with workstream-specific technical details. They are NOT useful as a formal convention, template section, or dispatch rule -- the Stories table dependency column, Parallel Execution Analysis, and execution waves already communicate dispatch-relevant information. The PM should use lane-style Technical Notes headers when they naturally fit, without formalizing. **Adopt trigger**: project regularly produces epics with 6+ stories across 3+ independent workstreams AND implementing agents report confusion about which Technical Notes apply to their story.

## Story Dependency Patterns
- E-006-03 pattern: when a story depends on another agent's design decision, mark it BLOCKED with an explicit unblock condition (file path + what the file must contain). Do not write a research spike when another agent is doing the research -- just block on their deliverable.
- E-006 refinement pattern: initial stories written before the architect's design doc will have vague "technical approach" sections. After the design doc exists, rewrite those sections to be specific.
- E-012 pattern: when a Phase 2 story is BLOCKED on unrelated deps, extract the unblocked subset into a separate focused epic that can ship immediately.

## Process Patterns
- E-007: software-engineer.md and data-engineer.md were created from scratch (did not exist before E-007-05).
- E-007 Dispatch Mode execution: PM can execute infrastructure stories directly without Task tool when PM is the coordinating agent in a single session.
- Decision Gates pattern (E-007-09): Evaluation epics need a gate story as their final story. PM executes it directly. Criteria must be in Technical Notes before stories are written. Three outcomes: APPROVED, REJECTED, DEFERRED.
- E-009 failure: status updates drifted out of sync. E-011 addresses with atomic status update protocol.
- Numbering collision (2026-02-28): before assigning a new epic number, ALWAYS ls /epics/ -- do not rely solely on memory's "next available" number.
- E-011 pattern: process-domain research spikes can be resolved by PM directly (no expert consultation).
- E-022 archive gap (2026-03-02): the PM's Atomic Status Update Protocol had checklists for completing stories and spikes, but NOT for completing epics. E-022 was marked COMPLETED but never archived. E-024 fixes by adding an explicit "Completing an epic" checklist and a PreToolUse hook. Pattern: every status transition that triggers downstream work needs its own checklist, not just a mention in a flow description.

## Platform Constraints
- Agent Teams (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`) is the dispatch mechanism. **Only the team lead can spawn teammates** -- teammates cannot spawn other teammates. PM runs as a teammate and coordinates via SendMessage; the team lead handles all spawning. (Corrected in E-056; previous note incorrectly claimed "no nesting limit".)
- Task tool: use for single-agent consultations (e.g., consulting baseball-coach). Cannot nest further.
- E-015 consultation pattern: when the consultation itself would trigger the bug being diagnosed, read the expert's memory files directly instead.

## Agent Routing Lessons

- **E-019 routing error**: E-019-02 (`.claude/hooks/`, `.claude/settings.json`, `.claude/rules/`) and the CLAUDE.md edit in E-019-04 were dispatched to `software-engineer`. These are `claude-architect` domain. The dispatch-pattern table is clear: "Agent config, CLAUDE.md, rules, skills" → `claude-architect`. For future epics touching `.claude/` infrastructure or `CLAUDE.md`, route those stories to `claude-architect`, not `software-engineer`.
- **E-027 routing error (recurring)**: E-027-02 added a troubleshooting section to CLAUDE.md, dispatched to software-engineer. Same class of error as E-019. The memory note from E-019 was insufficient -- the PM forgot to check. Root cause: no procedural step in dispatch flow that forces a file-path scan before agent selection. E-029 addresses this by (1) enumerating context-layer paths explicitly in dispatch-pattern.md, (2) adding a mandatory pre-check step to the PM dispatch procedure. Key insight: memory notes and domain descriptions are not enforceable; procedural checklists are.

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

## Consultation Compliance

**Incident (E-058 formation)**: User said "work with SE to propose a fix." PM wrote the epic solo without consulting SE.

**Root cause**: Three compounding factors:
1. PM was spawned one level deep and could not spawn SE (spawning is one-level-deep -- a platform constraint).
2. No escalation path existed -- when PM could not spawn, it had no procedure for messaging the team lead/user with specific questions for the requested expert.
3. The user-directed override rule in the Consultation Triggers section used guidance language ("honor that request") rather than MUST language with an enforcement mechanism. A prose guideline with no procedural checkpoint is not enforceable.

**Fix (E-059)**:
- Anti-pattern 5 added to `product-manager.md`: "Never skip a user-requested consultation." Includes spawning constraint explanation and escalation path.
- User-directed override paragraph strengthened to MUST language with escalation path and concrete negative example.
- Refinement pre-step added to "How Work Flows" step 3: scan for collaboration directives before writing stories; consult or escalate.
- Consultation Compliance Gate added to `workflow-discipline.md` (defense-in-depth -- loaded for all agents, not just PM).

**Pattern**: Prose guidance is not enforceable; procedural checkpoints are. This echoes the E-029 lesson (routing errors) and E-021 lesson (tool restrictions). When a rule fails because it is descriptive rather than procedural, add a mandatory checkpoint step to the workflow.

## Implementation Prescriptiveness

**Incident (E-058 formation)**: PM prescribed specific bash patterns (e.g., `${BASH_SOURCE[0]}` vs `$0`) in story Technical Approach sections, crossing the Technical Delegation Boundary.

**Principle**: PM decides what to build and why; the implementing agent decides how. Story Technical Approach sections describe the problem and constraints, not the code solution -- no specific function names, variable names, bash patterns, or code snippets.

**Fix (E-059-04)**:
- Anti-pattern 6 added to `product-manager.md`: "Never prescribe implementation details in stories." References the E-058 incident.
- Technical Delegation Boundaries section strengthened: "Story Technical Approach sections describe the problem and constraints, not the code solution."
- Quality Checklist item added: "Technical Approach sections describe the problem and constraints, not the code solution (no specific function names, variable names, or code patterns)."
