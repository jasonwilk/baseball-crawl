# E-028: Documentation System and Docs-Writer Agent

## Status
`COMPLETED`
<!-- Lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED) -->
<!-- PM sets READY explicitly after: expert consultation done, all stories have testable ACs, quality checklist passed. -->
<!-- Only READY and ACTIVE epics can be dispatched. -->

## Overview
Create a documentation agent and structured documentation for both audiences of baseball-crawl: Jason (system operator/developer) and the coaching staff (dashboard consumers). Today the project has six technical docs in `docs/` -- all developer-facing, none providing an overview of how the system works, and nothing at all for coaches. This epic establishes a docs-writer agent, creates initial documentation for both audiences, and puts conventions in place to keep docs current as the project evolves.

## Background & Context
The project has accumulated significant complexity across its agent ecosystem (6 agents), data pipeline (GameChanger API -> crawl -> parse -> SQLite -> FastAPI dashboard), deployment infrastructure (Docker Compose + Cloudflare Tunnel + Zero Trust), and project management system (epics, stories, ideas). All of this knowledge is scattered across CLAUDE.md, agent definitions, epic files, and individual docs -- useful for agents but not for a human trying to understand or operate the system.

The coaching staff audience does not exist yet as documentation consumers because the dashboard (E-004) is not built. However, the documentation system and agent should be in place before the dashboard ships so that end-user docs ship alongside the feature.

**Expert consultation**: Baseball-coach consultation is needed before writing E-028-04 (end-user documentation) to determine what coaching staff need explained, their technical level, and preferred format. This consultation should happen during story execution, not during epic formation, because the coaching dashboard (E-004) is still in DRAFT. The consultation question is captured in E-028-04's Technical Approach. For all other stories, no expert consultation is required -- they are agent infrastructure (claude-architect domain) or developer documentation (PM + docs-writer domain).

## Goals
- A `docs-writer` agent exists in the agent ecosystem with clear responsibilities, conventions, and PM dispatch routing
- Admin/developer documentation provides a comprehensive overview of the system for Jason as operator
- End-user documentation structure is established with initial content appropriate for the current state of the dashboard
- Documentation maintenance is enforced as a required workflow step in the PM's epic completion protocol -- not a convention that relies on agents remembering to check

## Non-Goals
- Exhaustive API reference documentation (api-scout maintains `docs/gamechanger-api.md` -- docs-writer does not duplicate this)
- Auto-generated code documentation (docstrings and type hints serve this purpose)
- Documentation hosting or publishing infrastructure (docs are markdown files in the repo for now)
- Rewriting existing docs in `docs/` -- the docs-writer may cross-reference them but does not replace agent-maintained docs
- End-user documentation for features that do not yet exist (dashboard is E-004 DRAFT)

## Success Criteria
- `docs-writer` agent file exists at `.claude/agents/docs-writer.md` with full system prompt following the canonical section skeleton
- CLAUDE.md Agent Ecosystem table includes docs-writer with role description
- `docs/admin/` directory contains at minimum: architecture overview, getting started guide, and operations guide
- `docs/coaching/` directory contains at minimum: a landing page explaining what the system does for coaches and a placeholder structure for feature docs
- `.claude/rules/documentation.md` defines when and how docs are updated, including a mandatory PM assessment step
- The PM's epic completion checklist (in dispatch-pattern.md, workflow-discipline.md, and the PM agent definition) includes documentation assessment as a required step
- CLAUDE.md Agent Ecosystem table includes docs-writer

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-028-01 | Create docs-writer agent definition | DONE | None | claude-architect |
| E-028-02 | Documentation maintenance rules and workflow integration | DONE | None | claude-architect |
| E-028-03 | Admin/developer documentation -- initial content | DONE | E-028-01 | docs-writer |
| E-028-04 | End-user documentation -- structure and initial content | DONE | E-028-01 | docs-writer |
| E-028-05 | CLAUDE.md and workflow integration updates | DONE | E-028-01, E-028-02 | claude-architect |

## Technical Notes

### Documentation Architecture

**Two audience directories:**
- `docs/admin/` -- System operator/developer documentation. Audience: Jason. Assumes technical competence (Python, Docker, SQL, CLI). Covers architecture, data flows, agent ecosystem, deployment, operations.
- `docs/coaching/` -- End-user documentation. Audience: coaching staff. Assumes zero technical knowledge. Covers what the system shows them, how to read the data, what the stats mean.

**Existing docs stay in place:**
The six files currently in `docs/` are agent-maintained technical references. They remain at their current paths. The new admin docs cross-reference them rather than absorbing them. Specifically:
- `docs/gamechanger-api.md` -- owned by api-scout, referenced from admin docs
- `docs/http-integration-guide.md` -- owned by general-dev stories, referenced from admin docs
- `docs/safe-data-handling.md` -- standalone safety reference, referenced from admin docs
- `docs/cloudflare-access-setup.md` -- deployment reference, referenced from admin docs
- `docs/agent-browsability-workflow.md` -- development workflow, referenced from admin docs
- `docs/database-restore.md` -- operations reference, referenced from admin docs

**docs-writer agent scope:**
- Model: sonnet (documentation is structured writing, not deep reasoning)
- Tools: Read, Write, Edit, Glob, Grep (no Bash -- docs-writer reads code and docs, does not execute)
- Color: purple (unused in current ecosystem)
- Responsibilities: Create and maintain documentation for both audiences. Consult baseball-coach for coaching terminology and end-user needs. Read source code and agent definitions to produce accurate technical docs.
- Anti-patterns: Does not write code, does not modify agent definitions, does not maintain `docs/gamechanger-api.md` (api-scout's territory)
- Inter-agent: Consults baseball-coach for end-user content accuracy. Reads general-dev and data-engineer outputs for technical accuracy. PM dispatches docs-writer for documentation stories.

**Documentation maintenance rule and workflow integration:**
A new rule at `.claude/rules/documentation.md` defines both conventions and enforcement:

*Conventions (what, who, when):*
1. When docs must be updated (triggers: new feature ships, architecture changes, new agent created, deployment config changes, epic completes that changes system behavior)
2. Who updates which docs (docs-writer for both audience directories; api-scout for API spec; each agent for its own memory)
3. How staleness is detected (docs reference their "Last updated" date and the epic/story that produced them)

*Enforcement (how it is required, not optional):*
4. Mandatory documentation assessment: the PM must assess documentation impact when completing any epic, before archiving. If any update trigger fires, PM dispatches docs-writer. If none fire, PM records "No documentation impact" in epic History.
5. Documentation update task format: PM provides docs-writer with what changed, which docs are affected, and what needs updating. This is a lightweight dispatch, not a full story.

*Workflow integration (done by E-028-05):*
The documentation rule is then wired into existing workflow infrastructure:
- `dispatch-pattern.md` gets a documentation assessment step in the epic completion flow
- `workflow-discipline.md` gets a Documentation Assessment Gate section
- The PM agent definition gets a documentation step in its "Completing an epic" checklist

The key mechanism: the PM cannot complete an epic without assessing doc impact because it is in the PM's own completion checklist -- the same checklist that governs status updates, archiving, and MEMORY.md updates.

**Admin documentation initial content plan:**
1. `docs/admin/architecture.md` -- System overview: components (FastAPI app, SQLite, Docker Compose, Cloudflare Tunnel, agents), data flow diagram (text-based), directory structure, tech stack rationale
2. `docs/admin/getting-started.md` -- Clone, install deps, run devcontainer, seed database, start the stack, verify health check
3. `docs/admin/operations.md` -- Deployment checklist, credential rotation, database backup/restore (references existing doc), monitoring, troubleshooting
4. `docs/admin/agent-guide.md` -- What each agent does, how to invoke them, the agent routing model, epic/story workflow from an operator perspective
5. `docs/admin/README.md` -- Index page linking to all admin docs

**End-user documentation initial content plan (subject to baseball-coach consultation):**
1. `docs/coaching/README.md` -- Landing page: what this system does for coaches, what to expect, how to access it
2. `docs/coaching/understanding-stats.md` -- Glossary of statistics shown in the dashboard, with sample size caveats and interpretation guidance (baseball-coach must validate)
3. `docs/coaching/scouting-reports.md` -- Placeholder: how to read scouting reports (content depends on E-004 dashboard features)

### Parallel Execution Analysis

- **E-028-01** and **E-028-02** have no file conflicts and can run in parallel. Both are claude-architect work.
- **E-028-03** and **E-028-04** both depend on E-028-01 (the agent must exist before it can be dispatched) but have no file conflicts with each other (different directories). They can run in parallel after E-028-01 completes.
- **E-028-05** depends on both E-028-01 (agent definition) and E-028-02 (documentation rule). It must wait for both to complete before starting. Once both are done, E-028-05 can run in parallel with E-028-03 and E-028-04 (no file conflicts: E-028-05 modifies CLAUDE.md, dispatch-pattern.md, workflow-discipline.md, product-manager.md; E-028-03/04 create files in docs/).

**Execution waves:**
1. Wave 1: E-028-01 + E-028-02 (parallel)
2. Wave 2: E-028-03 + E-028-04 + E-028-05 (parallel, after Wave 1 completes)

## Open Questions
- Baseball-coach consultation for E-028-04: What is the coaching staff's technical level? What format works best -- long-form guides, quick reference cards, or embedded help? What statistics need the most explanation? This consultation happens during E-028-04 execution, not during epic formation.

## History
- 2026-03-03: Created
- 2026-03-03: Refined and set to READY. Quality checklist passed. Baseball-coach consultation deferred to E-028-04 execution.
- 2026-03-03: Re-refined per user feedback. Documentation maintenance must be a required workflow step, not just a convention. E-028-02 expanded to define mandatory PM assessment step. E-028-05 expanded to wire the requirement into dispatch-pattern.md, workflow-discipline.md, and PM agent definition. E-028-05 now depends on both E-028-01 and E-028-02 (was: E-028-01 only). Epic remains READY.
- 2026-03-03: Revised per E-030 to remove references to the deleted routing agent. Goals, Success Criteria, Stories table (E-028-05 title), Technical Notes, and Background updated. Agent count corrected from 7 to 6.
- 2026-03-03: Post-E-030 cross-check refinement. E-028-05 AC-2 and Technical Approach referenced "step 10" of dispatch-pattern.md, but E-030-01 renumbered the dispatch flow from 10 steps to 9. Updated E-028-05 to reference steps by content description rather than number, making ACs resilient to future renumbering. All other concerns (agent counts, routing model, CLAUDE.md table structure, E-028-03 agent-guide scope) verified clean.
- 2026-03-03: Dispatch started. Epic set to ACTIVE. Wave 1 dispatched: E-028-01 + E-028-02 (parallel, both claude-architect).
- 2026-03-03: All 5 stories completed. Wave 1 (E-028-01 + E-028-02) completed first, then Wave 2 (E-028-03 + E-028-04 + E-028-05) dispatched in parallel. All acceptance criteria verified. Epic set to COMPLETED. Artifacts created: docs-writer agent definition, documentation maintenance rule, 5 admin docs in docs/admin/, 3 coaching docs in docs/coaching/, workflow integration updates to CLAUDE.md, dispatch-pattern.md, workflow-discipline.md, and product-manager.md.
