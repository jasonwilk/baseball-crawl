# E-213: Context Layer Optimization

## Status
`READY`
<!-- Lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED) -->
<!-- PM sets READY explicitly after: expert consultation done, all stories have testable ACs, quality checklist passed. -->
<!-- Only READY and ACTIVE epics can be dispatched. -->

## Overview

Reduce the project's ambient context load by extracting domain-specific content from CLAUDE.md into scoped rules, deduplicating universal rules, restructuring PM memory, and fixing rule frontmatter issues. A context-layer audit (2026-04-05) found CLAUDE.md at 239 lines (60% over its 150-line target), ~40 lines of content duplication across universal rules, and PM memory dominated by filesystem-derivable enumerated state. This epic addresses findings F-01 through F-20 and recommendations R-01 through R-10 from the audit.

## Background & Context

Organic growth across 200+ epics has introduced measurable inefficiencies in the context layer. Every agent, every session pays for CLAUDE.md (239 lines), plus 8 universal rules (400 lines). The audit measured actual ambient load at 794-1,100 lines per session -- 40%+ higher than the context-fundamentals skill's stale budget estimate of 560-870 lines.

The highest-impact changes are: (1) extracting CLAUDE.md domain sections to scoped rules so they load only when relevant, (2) deduplicating the dispatch/workflow rules, and (3) restructuring PM memory to replace enumerated state with filesystem pointers.

Expert consultation: claude-architect performed the audit and designed all 5 stories (context-layer domain). PM framed ACs and owns epic structure.

## Goals
- Reduce CLAUDE.md from 239 lines to ~140-160 lines (near the 150-line target)
- Eliminate ~600 words of content duplication between universal rules
- Reduce PM MEMORY.md from 146 lines to under 100 lines
- Fix rule frontmatter issues that cause incorrect scoping behavior
- Recalibrate context-fundamentals skill budget numbers with post-optimization actuals

## Non-Goals
- Creating new context-engineering skills (R-11 -- deferred per "simple first" principle)
- Changing agent definitions or skill files (beyond budget recalibration in context-fundamentals)
- Modifying any implementation code (`src/`, `tests/`, `migrations/`, `scripts/`)
- Addressing LOW-priority findings F-12, F-13 that are platform-handled or intentional design

## Success Criteria
- CLAUDE.md line count is between 140 and 160 lines
- Every extracted section's content appears in its target scoped rule file (bullet splitting permitted where MUST constraints remain in CLAUDE.md)
- A full-text search for any key term (FPS%, QAB, appearance_order, two-tier enrichment, ensure_team_row, finalize_opponent_resolution) finds it in the context layer
- No agent behavioral regression -- all information is preserved, only relocated
- Duplicated dispatch content in universal rules is consolidated (Workflow Routing Rule paragraph replaced with pointer)
- PM MEMORY.md is under 100 lines
- context-fundamentals skill budget numbers reflect post-optimization actuals

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-213-01 | Extract CLAUDE.md domain sections to scoped rules | TODO | None | claude-architect |
| E-213-02 | Deduplicate dispatch-pattern.md and workflow-discipline.md | TODO | None | claude-architect |
| E-213-03 | Restructure PM MEMORY.md and archived-epics.md | TODO | None | claude-architect |
| E-213-04 | Fix rule frontmatter and compress universal rules | TODO | None | claude-architect |
| E-213-05 | Recalibrate context-fundamentals budget and clean up memory | TODO | E-213-01, E-213-02, E-213-03, E-213-04 | claude-architect |

## Dispatch Team
- claude-architect

## Technical Notes

### TN-1: No-Regression Constraint

Every extraction, deduplication, and restructuring MUST preserve all information and agent behavior. Specifically:

1. **CLAUDE.md extractions**: Each extracted section's content must appear in the target scoped rule (bullet splitting permitted where a MUST constraint must remain in CLAUDE.md as a 1-line invariant). CLAUDE.md retains a 1-line pointer (e.g., "See `.claude/rules/key-metrics.md` for stat definitions and coaching priorities.").
2. **Rule deduplication**: Any content in `workflow-discipline.md`'s Workflow Routing Rule section that does NOT already exist in `dispatch-pattern.md` must be migrated to `dispatch-pattern.md` before the pointer replacement.
3. **PM memory restructuring**: The next-available epic number, next-available idea number, and promotable ideas must remain discoverable. The restructured format must still let PM quickly identify READY/ACTIVE epics.

### TN-2: New Scoped Rule Files

| New Rule | Source Section | `paths:` Scope |
|----------|---------------|----------------|
| `key-metrics.md` | "Key Metrics We Track" (CLAUDE.md lines 59-77) | `src/api/**`, `src/reports/**`, `src/charts/**`, `src/gamechanger/loaders/**`, `src/gamechanger/parsers/**`, `src/reconciliation/**` |
| `scouting-data-flows.md` | "Scouting Data Flows" (CLAUDE.md lines 150-173) | `src/reports/**`, `src/gamechanger/loaders/scouting*`, `src/api/routes/dashboard.py`, `src/api/routes/admin.py`, `src/api/routes/reports.py`, `src/pipeline/**` |
| `data-model.md` | "Data Model" (CLAUDE.md lines 174-193) | `migrations/**`, `src/db/**`, `src/gamechanger/loaders/**`, `src/gamechanger/parsers/**` |
| `admin-ui.md` | "Admin UI" (CLAUDE.md lines 194-205) | `src/api/routes/admin.py`, `src/api/templates/admin/**` |
| `architecture-subsystems.md` | Architecture sub-bullets: plays pipeline, spray pipeline, reconciliation, LLM, reports, charts, two-tier enrichment (CLAUDE.md lines ~128-148) | `src/reports/**`, `src/reconciliation/**`, `src/charts/**`, `src/llm/**`, `src/gamechanger/crawlers/**`, `src/gamechanger/parsers/**`, `src/gamechanger/loaders/**`, `src/pipeline/**` |

### TN-3: What Remains in CLAUDE.md

After extraction, CLAUDE.md retains these genuinely ambient sections:
- Core Principle, Project Purpose (scope, MVP target, deployment target), Data Philosophy, Tech Stack
- GameChanger API (summary-level auth, endpoints, HTTP discipline pointer)
- Commands, Workflows, App Troubleshooting, Proxy Boundary
- Security Rules, Architecture (general principles + 1-line canonical invariants with MUST constraints + shared query functions convention), Project Management, Git Conventions, Agent Ecosystem
- Pointer lines to each extracted scoped rule
- Note: The "shared query functions" bullet (CLAUDE.md line 144) stays in CLAUDE.md as an ambient MUST convention — it's a cross-surface architectural pattern, not subsystem-specific detail

### TN-4: Workflow Routing Rule Deduplication

The Workflow Routing Rule section in `workflow-discipline.md` (line 68-70) is a near-verbatim copy of `dispatch-pattern.md`'s Team Roles section. The dedup approach:
1. Diff the two texts to identify any unique content in the WD version
2. Migrate any unique content to `dispatch-pattern.md`
3. Replace the WD section with: `## Workflow Routing Rule` + a 2-line pointer to `dispatch-pattern.md`

### TN-5: PM Memory Restructuring

Target structure for PM MEMORY.md (under 100 lines):
- **Numbering State**: Keep next-available epic/idea numbers (2-3 lines)
- **Active Epics**: Replace 25-line table with a compact list of READY/ACTIVE epics only (~5-10 lines). Pointer: "For full details, read the epic file in `/epics/`."
- **Key Architectural Decisions**: Keep as-is (critical ambient context for planning)
- **User Preferences**: Keep as-is (4 lines)
- **Ideas Backlog**: Replace 62-line table with pointer to `/.project/ideas/README.md` plus curated list of all ideas with "Trigger met" or "Immediately promotable" annotations (~10 lines)
- **Key Workflow Contract**: Keep as-is (critical for PM dispatch behavior)
- **Topic File Index**: Keep as-is (5 lines)

For `archived-epics.md`: Convert from 152-line flat registry to ~30-line highlights format. Header note that `ls /.project/archive/` is the canonical source. Keep only key milestones and architectural decision points.

### TN-6: User Memory Exception (Outside Worktree)

E-213-05 AC-3 modifies user memory files at `/home/vscode/.claude/projects/-workspaces-baseball-crawl/memory/`. These files are outside the git repository and will NOT exist in the epic worktree. They are not captured by the staging boundary or closure merge. The implementing agent must write directly to these absolute paths during dispatch — this is a documented exception to normal worktree isolation. The main session should be aware that these changes are applied immediately (not deferred to closure).

## Open Questions
- None (all design questions resolved via CA consultation)

## History
- 2026-04-05: Created (CA audit -> PM epic formation)
- 2026-04-05: READY after 2 review rounds (13 findings accepted, 0 dismissed)

### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 — CR spec audit | 5 | 5 | 0 |
| Internal iteration 1 — Holistic team (PM + CA) | 10 | 9 | 0 |
| Codex iteration 1 | 4 | 4 | 0 |
| **Total** | **19** | **18** | **0** |

Note: PM+CA holistic review had 10 raw findings that deduplicated to 9 unique (1 overlap between PM-2 and CA-5). CR findings overlapped with PM/CA findings but were counted separately since they came from a different sub-pass.
