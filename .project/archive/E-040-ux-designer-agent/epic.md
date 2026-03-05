# E-040: UX Designer Agent

## Status
`COMPLETED`

## Overview
Create a UX designer agent that owns interface design for the baseball-crawl coaching dashboard and any future UI work. This agent will design layouts, component structure, user flows, and wireframes within the FastAPI + Jinja2 + Tailwind server-rendered HTML stack, consulting baseball-coach for domain requirements and reviewing existing templates to ensure design coherence.

## Background & Context
The project is approaching dashboard implementation (E-004, READY). Currently, no agent owns the design side of UI work -- software-engineer implements routes and templates, but there is no specialist thinking about information architecture, visual hierarchy, mobile-first layout decisions, or coaching-workflow-driven page design.

Adding a UX designer agent fills this gap. The agent does not write application code; it produces design artifacts (wireframes, layout specs, component inventories, user flow diagrams) that software-engineer implements. This separation keeps design intent explicit and reviewable before implementation begins.

**No expert consultation required** -- this is a context-layer epic (new agent creation) squarely in claude-architect's domain. The agent's constraints (FastAPI + Jinja2, Tailwind CDN, server-rendered HTML, mobile-first) are fully documented in CLAUDE.md and E-004 Technical Notes. The coaching domain requirements are documented in CLAUDE.md Key Metrics and `docs/gamechanger-stat-glossary.md`.

## Goals
- A fully defined UX designer agent at `.claude/agents/ux-designer.md` following the canonical agent section skeleton
- Agent ecosystem references updated (CLAUDE.md, dispatch-pattern.md) so PM can route design work correctly
- Clear boundaries between UX designer (design) and software-engineer (implementation)
- Agent equipped to consult baseball-coach for domain context and review existing templates for design coherence

## Non-Goals
- Building any actual dashboard UI (that is E-004's scope)
- Creating design system documentation or a component library (future work if needed)
- Adding client-side JavaScript or a CSS build pipeline
- Changing the tech stack or introducing new frontend frameworks

## Success Criteria
- The UX designer agent can be invoked and produces design artifacts appropriate for a Jinja2 + Tailwind stack
- CLAUDE.md Agent Ecosystem table includes the new agent with correct role description
- dispatch-pattern.md agent selection table includes a row for UX/design work
- The agent's scope does not overlap with existing agents (no ambiguity with software-engineer, docs-writer, or baseball-coach)

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-040-01 | Create UX designer agent definition and update ecosystem | DONE | None | claude-architect |

## Technical Notes

### Agent Design Constraints
- **Stack awareness**: The agent must understand that all UI is server-rendered HTML via Jinja2 templates with Tailwind CSS (CDN, no build step). No React, no Vue, no client-side JS frameworks. Design artifacts must be implementable within this stack.
- **Output format**: Since this is a text-based agent (no Figma, no image generation), design artifacts should be structured text: ASCII wireframes, HTML/Tailwind mockups, component inventories, layout specifications, and user flow descriptions. The agent should be explicit about what format it uses.
- **Mobile-first**: Coaches use dashboards from the dugout on phones (375px minimum). This constraint shapes every layout decision.
- **Tailwind conventions**: Use Tailwind utility classes. Responsive prefixes (`sm:`, `md:`, `lg:`) for progressive enhancement beyond mobile.

### Agent Ecosystem Integration
- **Consults baseball-coach** for domain requirements: what data coaches need to see, in what order, with what emphasis. Baseball-coach validates that designs serve real coaching workflows.
- **Produces artifacts for software-engineer**: Design specs, wireframes, and component descriptions that SE implements as Jinja2 templates and route handlers.
- **Does NOT overlap with docs-writer**: UX designer designs interfaces; docs-writer documents them after implementation. Different audiences, different artifacts.
- **Does NOT overlap with software-engineer**: UX designer specifies what the UI should look like and how it should behave; SE writes the code. UX designer may produce HTML/Tailwind mockups as design specs, but these are reference artifacts, not production code.

### Existing UI Assets to Reference
- `src/api/templates/base.html` -- base layout with Tailwind CDN, nav bar
- `src/api/templates/dashboard/team_stats.html` -- existing batting stats table
- `src/api/routes/dashboard.py` -- existing route structure
- E-004 Technical Notes -- route structure, mobile design principles, computed stats formulas

### Context-Layer Files Modified
All files modified by this epic are context-layer files, requiring claude-architect as the implementing agent:
- `.claude/agents/ux-designer.md` (new)
- `CLAUDE.md` (Agent Ecosystem table)
- `.claude/rules/dispatch-pattern.md` (Agent Selection table)
- `.claude/agents/claude-architect.md` (MODIFY -- agent list in Identity section)

## Open Questions
None -- scope is clear and well-bounded.

## History
- 2026-03-05: Created and set to READY
- 2026-03-05: Set to ACTIVE, dispatched E-040-01 to claude-architect
- 2026-03-05: E-040-01 DONE, all 10 ACs verified. Epic COMPLETED. UX designer agent created at .claude/agents/ux-designer.md, CLAUDE.md and dispatch-pattern.md updated, claude-architect agent list updated to 8 agents. No documentation impact (context-layer only, no user-facing docs affected).
