# E-183-01: Add Scouting Data Flows Distinction to CLAUDE.md

## Epic
[E-183: Codify Opponent Flow vs Reports Flow in Context Layer](epic.md)

## Status
`DONE`

## Description
After this story is complete, CLAUDE.md will contain a "Scouting Data Flows" section that clearly distinguishes the opponent flow (dashboard exploration) from the reports flow (ad-hoc snapshots). The section will include a comparison table, naming convention, architectural conventions, and a routing note. The reports flow will also be represented in the Commands and Architecture sections, achieving parity with the opponent flow's existing coverage.

## Context
E-172 shipped the standalone reports flow but no context-layer assessment captured it in CLAUDE.md. The opponent flow has existing coverage across multiple CLAUDE.md sections (scouting pipeline, opponent resolution, admin UI, spray chart auth exception), but the reports flow has zero representation. Both flows deal with "scouting reports," creating naming ambiguity. This story closes that gap with a structured comparison and the missing reports flow entries.

## Acceptance Criteria
- [ ] **AC-1**: CLAUDE.md contains a "Scouting Data Flows" section (under or near the Architecture section) with a structured comparison drawing from the dimensions in TN-1 of the epic. At minimum, the comparison must cover auth model, data freshness (live vs frozen), and lifecycle (persistent vs ephemeral) -- these are the core differentiators. Additional TN-1 dimensions are at the implementer's discretion given the line budget constraint in TN-4
- [ ] **AC-2**: The section includes a naming convention note per TN-2 -- "scouting report" means opponent flow, "standalone report" or "generated report" means reports flow
- [ ] **AC-3**: The section includes architectural conventions per TN-3, including the serving invariant: the `/reports/{slug}` route MUST NOT query stats tables or render Jinja2 templates at serve time -- only `reports` table lookup + file read from disk. Also: no `team_opponents` dependency, ephemeral 14-day lifecycle, self-contained `src/reports/` package
- [ ] **AC-4**: The Commands section mentions `bb report generate` and `bb report list` with brief descriptions
- [ ] **AC-5**: The Architecture section mentions the `src/reports/` package (`generator.py` orchestrates crawl->load->query->render->write; `renderer.py` produces self-contained HTML) and the reports serving route (`/reports/{slug}`, no auth)
- [ ] **AC-6**: The section includes a brief routing note: stories modifying `src/reports/`, `src/api/routes/reports.py`, report handlers in `src/api/routes/admin.py`, or `src/api/templates/admin/reports.html` belong to the reports flow; stories modifying opponent dashboard routes/templates or `src/gamechanger/loaders/scouting_loader.py` belong to the opponent flow

## Technical Approach
The CLAUDE.md file needs updates in three locations: a new "Scouting Data Flows" section (placement per TN-4), additions to the Commands section, and additions to the Architecture section. The comparison table in TN-1 and conventions in TN-3 provide the content; the implementer determines exact wording and formatting to match CLAUDE.md's existing style. Keep the new section concise (~15-20 lines for the comparison plus convention bullets). See TN-4's line budget note: CLAUDE.md is already ~191 lines against a ~150-line target. Prioritize brevity -- not all 8 TN-1 rows may be needed. The implementer has latitude to trim/move existing content or accept the overshoot with justification.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `/workspaces/baseball-crawl/CLAUDE.md`

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] No regressions in existing CLAUDE.md content
- [ ] Code follows project style (see CLAUDE.md)
