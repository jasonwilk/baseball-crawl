# E-108-01: Update dispatch-pattern.md and workflow-discipline.md with PM Dispatch Role

## Epic
[E-108: PM as Dispatch Teammate](epic.md)

## Status
`TODO`

## Description
After this story is complete, `dispatch-pattern.md` documents the PM as a spawned teammate during dispatch with clear responsibility boundaries: PM owns status management (story and epic status transitions, epic table updates) and AC verification. The main session retains spawning, routing, merge-back, and cascade. `workflow-discipline.md` reflects the PM's dispatch role.

## Context
The current dispatch pattern (established by E-065) gives the main session all coordination responsibilities. This story adds PM as a fourth role in the Team Composition section and threads PM responsibilities through the Dispatch Flow and Closure Sequence.

## Acceptance Criteria
- [ ] **AC-1**: Team Composition section has four roles: main session (spawner + router), PM (status owner + AC verifier), specialist agents (implementers), code-reviewer (quality gate).
- [ ] **AC-2**: PM role description specifies: story status file updates (TODO -> IN_PROGRESS -> DONE), epic Stories table updates, epic status transitions (READY -> ACTIVE -> COMPLETED), AC verification ("did they build what was specified"), epic History entries, PM memory updates, ideas/vision signal review during closure.
- [ ] **AC-3**: Main session role description is narrowed: spawning agents, routing work (implementer -> code-reviewer + PM), merge-back protocol, cascade decisions, user escalation. Explicitly does NOT manage status updates or verify ACs.
- [ ] **AC-4**: Dispatch Flow step 4 (currently "marks them IN_PROGRESS") routes to PM for status update instead of main session doing it directly.
- [ ] **AC-5**: Dispatch Flow steps 6-8 (completion/review loop) include PM AC verification as a parallel gate alongside code-reviewer. Both must pass before merge-back.
- [ ] **AC-6**: Dispatch Flow step 8 (mark DONE after merge-back) routes to PM for status update.
- [ ] **AC-7**: Closure Sequence steps that involve status updates or validation-ownership attribution (step 9: validate all work -- validation attribution reflects PM's AC verification role, step 10: update epic, step 14: update PM memory, step 15: review ideas, step 16: review vision signals) are attributed to PM, not main session.
- [ ] **AC-8**: `workflow-discipline.md` Workflow Routing Rule section reflects PM's dispatch role (PM is spawned during dispatch for status management and AC verification).
- [ ] **AC-9**: No references to "No PM teammate during dispatch," "PM is not spawned as a teammate during dispatch," or "no PM intermediary during dispatch" remain in any file listed in Files to Create or Modify.
- [ ] **AC-10**: Implementer role description explicitly states: implementing agents MUST NOT modify story status files, check AC boxes, or update the epic Stories table. Only PM performs these actions after independent verification.
- [ ] **AC-11**: Main session role description explicitly prohibits: writing or modifying application/test code, updating story/epic status files, checking AC boxes, verifying acceptance criteria. If a code fix is needed (e.g., from code review), the main session routes the finding to the implementer — never fixes it directly. (Addresses E-100 incident 4: team lead applied code fix instead of routing to SE.)
- [ ] **AC-12**: Main session role includes a "never absorb" rule: if an agent is missing or crashed, respawn it rather than taking over its responsibilities. The main session must not perform PM, code-reviewer, or implementer work in their absence. (Addresses E-100 incident 1: PM not spawned, main session absorbed PM duties.)
- [ ] **AC-13**: Implementer role includes: "Respond to code-review findings on their own work (main session routes findings back to the implementer who wrote the code)." This clarifies that code fixes from review go to the original implementer, not to the main session or a different agent.
- [ ] **AC-14**: The Dispatch Flow documents that code-review findings (MUST FIX, accepted SHOULD FIX) are routed by the main session back to the implementer who wrote the code. The main session triages SHOULD FIX findings (accept/dismiss) but NEVER applies fixes itself.
- [ ] **AC-15**: PM role in Team Composition explicitly states PM is spawned WITHOUT `isolation: "worktree"` — PM reads/writes status files in the main checkout and needs direct access.
- [ ] **AC-16**: Dispatch Flow includes a Gate Interaction paragraph: when PM rejects ACs, route feedback to implementer alongside code-review findings. After revision, both gates re-evaluate. PM AC rejection does NOT have its own circuit breaker — the code-reviewer's 2-round circuit breaker governs the overall loop. If it fires, escalate to user regardless of PM AC status.
- [ ] **AC-17**: `workflow-discipline.md` Workflow Routing Rule includes a concise version of the main session prohibitions (no code, no status updates, no AC verification). Full prohibition list lives in `dispatch-pattern.md`; `workflow-discipline.md` carries a defense-in-depth summary.
- [ ] **AC-18**: `CLAUDE.md` Workflow Contract step 5 updated to reflect PM as a spawned dispatch teammate (replacing "PM is not spawned as a teammate during dispatch").
- [ ] **AC-19**: `.claude/agents/product-manager.md` "How Work Flows" step 5 updated to reflect PM's dispatch role (status management + AC verification), replacing "PM's role is limited to setting the epic to READY and presenting it to the user for dispatch authorization."
- [ ] **AC-20**: Dispatch Flow includes a PM-override mechanism for reviewer AC findings: when code-reviewer flags an AC as MUST FIX but PM verifies that AC as PASS, the main session removes the AC-based finding from the MUST FIX list before routing to the implementer. If removing AC-based items empties the MUST FIX list, the story passes the review gate (effectively APPROVED for merge-back). Non-AC MUST FIX findings (bugs, security, conventions) remain the reviewer's exclusive domain and are unaffected by PM override.
- [ ] **AC-21**: Dispatch Flow step 6 (context-layer-only skip condition) routes AC verification and status update to PM instead of the main session doing it directly. The code-reviewer is still skipped for context-layer-only stories -- PM verifies ACs alone.
- [ ] **AC-22**: The routing-precedence exception in the Agent Selection section (currently "The only exception is the main session updating PM memory files during normal closure work") is updated to reflect that PM updates its own memory files during closure. The main session no longer needs this exception.
- [ ] **AC-23**: `workflow-discipline.md` opportunistic fixes applied: (a) PM Task Types section lists six modes (including curate), and (b) Consultation Mode Constraint includes a clarifying sentence explaining that `.claude/` paths are intentionally excluded from the MUST NOT list because consultation-mode agents may write to their own agent memory.

## Technical Approach
Refer to the epic Technical Notes for role boundaries and interaction flow. The changes are additive to `dispatch-pattern.md` (expand Team Composition, thread PM through Dispatch Flow and Closure Sequence) and a focused update to `workflow-discipline.md` (Workflow Routing Rule section). Do not change merge-back protocol, worktree isolation, or code-reviewer behavior.

### Opportunistic Fixes (workflow-discipline.md)
While editing `workflow-discipline.md`, address two stale items folded in from E-107 code review SHOULD FIX findings:

1. **PM Task Types count**: The "PM Task Types" section says "five modes" but there are six -- curate mode was added in E-068. Update the count to "six" and include curate in the list.
2. **Consultation Mode `.claude/` path clarification**: The "Consultation Mode Constraint" MUST NOT list blocks `docs/` but is silently permissive toward `.claude/` paths. The intent is correct (context-layer files are intentionally unblocked so agents like claude-architect can write to their own memory), but the asymmetry is not explained. Add a brief clarifying sentence noting that `.claude/` paths are intentionally excluded from the prohibition because consultation-mode agents may write to their own agent memory.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-108-02

## Files to Create or Modify
- `/.claude/rules/dispatch-pattern.md`
- `/.claude/rules/workflow-discipline.md`
- `/CLAUDE.md`
- `/.claude/agents/product-manager.md`
- `/.claude/agent-memory/product-manager/lessons-learned.md`
- `/.claude/agent-memory/product-manager/MEMORY.md`
- `/.claude/skills/multi-agent-patterns/SKILL.md`

## Agent Hint
claude-architect

## Handoff Context
- **Produces for E-108-02**: Updated `dispatch-pattern.md` with PM role definitions. `implement/SKILL.md` must align with the new role boundaries.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] No contradictions between dispatch-pattern.md and workflow-discipline.md
- [ ] Code follows project style (see CLAUDE.md)
