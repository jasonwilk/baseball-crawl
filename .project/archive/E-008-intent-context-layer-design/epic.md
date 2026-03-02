# E-008: Intent/Context Layer Design

## Status
`COMPLETED`

## Overview
This epic produces a design document recommending how baseball-crawl should manage its intent/context layer -- the structured system by which AI agents understand project structure, constraints, and tribal knowledge when entering a codebase. The output is a design document suitable for team review and decision-making, delivered by claude-architect.

## Background & Context
As the baseball-crawl agent ecosystem has grown (7 active agent roles as of E-007), the project increasingly relies on agents reading CLAUDE.md, rules files, and story files to orient themselves before doing work. This is an implicit intent/context layer -- it works, but it has grown organically without a deliberate design.

Two external systems have emerged that address this problem explicitly:

1. **Intent Systems (https://intent-systems.com/blog/intent-layer)**: A hierarchical context system of small opinionated files placed at semantic boundaries. Each "Intent Node" loads automatically when an agent works in that directory, providing a T-shaped view of context: broad at the top, specific at the leaf. The system uses compression + enrichment, least-common-ancestor optimization, and fractal compression to maximize token efficiency.

2. **Agent Skills for Context Engineering (https://github.com/muratcankoylan/Agent-Skills-for-Context-Engineering)**: A reusable skill library organized into five categories (Foundational, Architectural, Operational, Development, Cognitive) that teaches agents to manage context windows effectively. Uses progressive disclosure -- agents load skill names first, fetch full content only when relevant. Platform-agnostic, with BDI (Belief-Desire-Intention) mental state modeling as one of its Cognitive skills.

The project needs an informed opinion on whether to adopt one of these systems, adapt elements from both, or continue with the current approach -- and if adopting, how to implement it in the baseball-crawl context.

### Current State
- CLAUDE.md is the primary agent-orientation document (project-level, loaded into every session)
- `.claude/rules/workflow-discipline.md` enforces the story-to-implementation gate
- `.claude/agent-memory/` provides per-agent persistent memory
- `.claude/agents/` contains agent definitions
- No directory-level intent nodes exist; all context is global or in story files
- Skills exist (`.claude/skills/`) but are not organized around context engineering

### Architectural Options to Evaluate
1. **Status quo with refinements**: Improve CLAUDE.md and rules files; no new system adopted
2. **Intent Node hierarchy (intent-systems.com approach)**: Add hierarchical AGENTS.md/CLAUDE.md files at semantic boundaries (src/, tests/, epics/, etc.)
3. **Agent Skills adoption (muratcankoylan approach)**: Install context-engineering skills from the repo into `.claude/skills/`, integrate with claude-architect's role
4. **Dedicated context-manager agent**: A new partner agent whose sole role is maintaining and serving context/intent
5. **Hybrid**: Intent Node hierarchy for structural context + skills for agent behaviors

## Goals
- Produce a written comparison of the two external systems against the baseball-crawl project's actual needs and constraints
- Produce a concrete architectural recommendation with rationale tailored to baseball-crawl's scale (small team, 7 agents, ~12-15 active stories at any time)
- Specify what implementation would look like for the recommended approach (file locations, agent changes, workflow changes)
- Ensure the recommendation is actionable: another agent could implement it without additional research

## Non-Goals
- This epic does NOT implement the recommended approach (that is a follow-on epic, created only after E-008-03 records an APPROVED decision)
- This epic does NOT evaluate every possible context-management system -- only the two specified and any direct derivatives
- This epic does NOT redesign the agent roles or the workflow contract established in E-007
- This epic does NOT begin implementation work -- E-008-03 is the explicit gate that authorizes a follow-on epic

## Success Criteria
- A research artifact for each external system exists in `/.project/research/` summarizing key concepts, design principles, and applicability to baseball-crawl
- A comparison document exists evaluating all five architectural options against a defined set of criteria
- A final design document exists at `/.project/research/E-008-intent-context-layer-recommendation.md` that includes: options evaluated, recommended approach, rationale, and an implementation sketch sufficient for a follow-on epic
- The recommendation explicitly addresses: token efficiency, agent onboarding time, maintenance burden, and compatibility with the existing workflow contract
- A decision log entry exists at `/.project/research/E-008-decision-log.md` recording the user's explicit decision (APPROVED / REJECTED / DEFERRED) with any constraints or loop-back actions
- No follow-on implementation epic is created until the decision log records an APPROVED entry

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-008-R-01 | Research: Intent Systems intent-layer approach | DONE | None | claude-architect |
| E-008-R-02 | Research: Agent Skills for Context Engineering | DONE | None | claude-architect |
| E-008-01 | Compare and evaluate architectural options | DONE | E-008-R-01, E-008-R-02 | claude-architect |
| E-008-02 | Design and document the recommendation | DONE | E-008-01 | claude-architect |
| E-008-03 | Decision gate -- user review and approval | DONE | E-008-02 | project-manager |

## Technical Notes
- **Assignees**: claude-architect owns E-008-R-01, E-008-R-02, E-008-01, E-008-02. project-manager owns E-008-03 (the decision gate). No implementing agent (general-dev, data-engineer) is involved in this epic.
- **Output format**: All deliverables are markdown files. No code is written in this epic.
- **Research artifact location**: `/.project/research/` with filenames prefixed `E-008-`
- **Final recommendation file**: `/.project/research/E-008-intent-context-layer-recommendation.md`
- **Decision log file**: `/.project/research/E-008-decision-log.md` -- created by E-008-03, append-only if multiple rounds occur
- **Evaluation criteria** (must be used in E-008-01): token efficiency, agent onboarding clarity, maintenance burden, compatibility with existing workflow contract, implementation complexity, reversibility
- **Scale constraint**: baseball-crawl is a small project (one operator, 7 agents, ~30-game season, no CI/CD pipeline). Recommendations must fit this scale -- enterprise-grade context systems are out of scope.
- **Precedent**: The current CLAUDE.md + rules/ + agent-memory/ pattern works. Any recommendation must clearly justify the cost of change.
- **Gate behavior**: E-008-03 has three outcomes -- APPROVED (epic closes, follow-on authorized), REJECTED with loop-back (relevant story reset or new spike created, epic stays ACTIVE), DEFERRED (epic moves to BLOCKED with a review date). A follow-on implementation epic is created ONLY on APPROVED.
- **Follow-on epic**: The implementation epic will be E-009 (next available number per PM memory). It is not created speculatively -- only after E-008-03 records an APPROVED decision.

## Open Questions
- Do the intent-systems.com and muratcankoylan systems have overlapping or competing philosophies, or are they complementary?
- Does the baseball-crawl project already implement a de facto intent layer that just needs documentation and naming?
- What is the actual agent-onboarding pain today? Is there evidence of agents missing context, or is this anticipatory?
- Would a dedicated context-manager agent add enough value to justify the coordination overhead?

## History
- 2026-02-28: Created
- 2026-02-28: Added E-008-03 (decision gate); updated Non-Goals, Success Criteria, and Technical Notes to enforce the gate before any implementation epic is authorized
- 2026-02-28: E-008-03 DONE. User approved Option 5 (Hybrid). Decision log written to /.project/research/E-008-decision-log.md. Follow-on epic authorized as E-010. Epic marked COMPLETED and archived to /.project/archive/E-008-intent-context-layer-design/
