# E-183: Codify Opponent Flow vs Reports Flow in Context Layer

## Status
`READY`

## Overview
Codify the architectural distinction between the two scouting data flows -- the opponent flow (dashboard exploration) and the reports flow (ad-hoc snapshots) -- in the project's context layer. E-172 shipped the reports flow but no context-layer update captured it, leaving agents without guidance on which flow a story belongs to or how the two differ.

## Background & Context
The project now has two architecturally distinct ways to view scouting data:

1. **Opponent flow** (dashboard exploration): Auth-required, live DB queries, dashboard-embedded at `/dashboard/opponents`. Coach explores opponents tied to their team's schedule. Admin resolves and manages opponents at `/admin/opponents`. Data is always fresh (queried on each page load).

2. **Reports flow** (ad-hoc snapshots): Generated on demand from any GameChanger URL via `/admin/reports` or `bb report generate`. Produces a self-contained HTML file served publicly at `/reports/{slug}` (no auth). Frozen at generation time. 14-day expiry. Designed for "paste URL -> get link -> text to coach."

**The gap**: CLAUDE.md has decent coverage of the opponent flow (scouting pipeline, opponent resolution, admin UI, spray chart auth exception) but zero coverage of the reports flow. No context-layer artifact distinguishes the two flows or explains when to use which. Both flows deal with "scouting reports," creating naming ambiguity that can lead agents to conflate them.

**Expert consultations completed:**
- **claude-architect**: Recommends a "Scouting Data Flows" comparison table in CLAUDE.md (not a separate rule file -- the distinction is conceptual, not a procedural guard). Reports flow should also be added to existing CLAUDE.md sections (Commands, Architecture). Naming convention: "scouting report" = opponent flow; "standalone report" or "generated report" = reports flow.

No expert consultation required for baseball-coach (no coaching domain questions), api-scout (no API questions), or data-engineer (no schema questions).

## Goals
- CLAUDE.md contains a clear comparison of the two scouting data flows so agents can identify which flow a story belongs to
- The reports flow has representation in CLAUDE.md's Commands and Architecture sections (parity with the opponent flow's existing coverage)
- A naming convention disambiguates "scouting report" (opponent flow) from "standalone report" (reports flow)
- Coaching docs cover the standalone reports feature so coaching staff know it exists and how to use it

## Non-Goals
- Code changes to either flow (this is context-layer and docs only)
- New rule files (CA assessed this and recommends CLAUDE.md sections, not rules)
- Changing the reports flow architecture or the opponent flow architecture
- Agent routing changes (both flows route to SE; no override needed)

## Success Criteria
- An agent reading CLAUDE.md can determine which flow a story belongs to based on routes, file paths, and terminology
- The reports flow's routes, serving model, snapshot semantics, and public access pattern are documented in CLAUDE.md
- `docs/coaching/` contains guidance for coaching staff on how to access and use standalone reports

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-183-01 | Add scouting data flows distinction to CLAUDE.md | TODO | None | - |
| E-183-02 | Add standalone reports to coaching docs | TODO | None | - |

## Dispatch Team
- claude-architect
- docs-writer

## Technical Notes

### TN-1: Two-Flow Comparison Model
The CLAUDE.md section should use a structured comparison (table or parallel descriptions) covering these dimensions:

| Dimension | Opponent Flow (dashboard) | Reports Flow (standalone) |
|-----------|--------------------------|--------------------------|
| Entry point | `/dashboard/opponents` | `/admin/reports` or `bb report generate` |
| Auth | Required (session + permitted_teams) | Generation: admin auth. Serving: none (`/reports/{slug}` is public) |
| Data freshness | Live DB queries on each page load | Frozen snapshot at generation time |
| Lifecycle | Persistent (exists as long as `team_opponents` link) | Ephemeral (14-day expiry, deletable) |
| Output | Server-rendered Jinja2 template | Self-contained HTML file on disk (`data/reports/`) |
| Target user | Authenticated coach exploring their schedule | Anyone with the link (shared via text/email) |
| Data source | `team_opponents` + scouting pipeline (tracked teams) | Ad-hoc crawl of any GC `public_id` (no `team_opponents` required) |
| DB tables | `teams`, `team_opponents`, season stats, spray charts | `reports` table (metadata only -- content is the HTML file) |

### TN-2: Naming Convention
- **"scouting report"** or **"opponent scouting"** = the opponent flow (dashboard)
- **"standalone report"** or **"generated report"** = the reports flow
- Stories and commits should use the appropriate term to avoid ambiguity

### TN-3: Architectural Conventions to Codify
These conventions distinguish the reports flow's architecture:
- Reports are self-contained HTML files. `/reports/{slug}` reads a file from disk -- it MUST NOT query the DB for stats or render templates. Only DB access is the `reports` table lookup (slug -> file path, status, expiry).
- Reports have no `team_opponents` dependency. Generation takes any GC `public_id`.
- Reports are ephemeral: 14-day expiry, no versioning, no update-in-place.
- The `src/reports/` package is self-contained (`generator.py`, `renderer.py`). Neither module is imported by the opponent flow.

### TN-4: CLAUDE.md Placement and Line Budget
CA recommends:
- New "Scouting Data Flows" subsection under Architecture (or as a peer to "Admin UI")
- Add `bb report generate` and `bb report list` to the Commands section
- Add `src/reports/` package mention to Architecture section
- Keep the section concise (~15-20 lines for the comparison, plus bullets for conventions)

**Line budget note**: CLAUDE.md is currently ~191 lines; the context-layer guard (`.claude/rules/context-layer-guard.md`) targets ~150. Adding content will push it further over. The implementer should prioritize brevity (e.g., not all 8 TN-1 rows may be needed in CLAUDE.md -- pick the most disambiguating dimensions). The implementer has latitude to either (a) condense existing CLAUDE.md content to make room, or (b) accept the overshoot with justification that the two-flow distinction is genuinely ambient context every agent needs. Note: moving content to new scoped rule files is out of scope for this epic (see Non-Goals). The line budget is a constraint for the implementer to manage through concision, not through creating new files.

### TN-5: Coaching Docs Scope
`docs/coaching/scouting-reports.md` covers the full coaching dashboard (schedule, batting/pitching tabs, opponent scouting, spray charts) but does not mention standalone reports. A new section in this file (or a companion file like `docs/coaching/standalone-reports.md`) should explain:
- What standalone reports are and when to ask for one
- How to open and print a standalone report link
- That reports expire after 14 days
- Difference from the dashboard opponent view

## Open Questions
None -- all questions resolved during discovery and CA consultation.

## History
- 2026-03-29: Created. CA consultation completed during discovery.
- 2026-03-29: Set to READY after 2 internal review iterations and 2 Codex spec review iterations.

### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 -- CR spec audit | 3 | 3 | 0 |
| Internal iteration 1 -- Holistic team (PM) | 1 | 1 | 0 |
| Internal iteration 1 -- Holistic team (CA) | 2 | 2 | 0 |
| Codex iteration 1 | 5 | 4 | 1 |
| Codex iteration 2 | 4 | 3 | 1 |
| **Total** | **15** | **13** | **2** |

Note: Some internal review findings overlapped (dedup to 4 unique). Counts above are raw per-source. Both dismissals were the same underlying issue (AC-5 file-level metadata for existing file's pre-existing format -- out of scope).
