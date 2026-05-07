# WIL-5 Plan: Transition PM system to Linear

## Objective
Transition current PM artifacts from repo-based epics/stories to Linear-native Projects/Issues with minimal disruption to delivery, agent workflows, and historical traceability.

## Current-to-Target Mapping

| Current system | Linear target | Notes |
|---|---|---|
| Epic (`E-NNN`) | Project | One epic becomes one Linear Project. |
| Story (`E-NNN-SS`) | Issue | Story status, AC, and owner map to issue fields + description sections. |
| Research story (`E-NNN-R-SS`) | Issue with `type: research` label | Keep research discoverable with dedicated label/workflow state. |
| Epic file metadata | Project brief + custom fields | Preserve goals, scope, dependencies, and acceptance gates. |
| Story file metadata | Issue description template | Preserve AC, technical notes, and verification checklist. |
| `.project/archive/` | Closed/archived projects + repo snapshot | Keep static docs for audit/historical context. |

## Transition Principles
1. **No loss of planning intent**: Every epic/story must map to a concrete Linear object.
2. **Deterministic IDs**: Preserve `E-NNN` and `E-NNN-SS` in Linear titles for traceability.
3. **Single source of truth**: After cutover, status updates happen in Linear first.
4. **Bounded dual-write window**: Temporary mirror period (max 2 weeks) for confidence.
5. **Agent-safe migration**: Update prompts/skills so agents route planning and dispatch through Linear context.

## Proposed Phases

### Phase 0 — Prep (1–2 days)
- Confirm target Linear workspace/team, required project templates, and workflow states.
- Define required labels: `story`, `research`, `blocked`, `tech-debt`, `ops`.
- Define custom fields (if needed): legacy ID, epic family, readiness gate.
- Freeze creation of new repo-only epics at phase end.

### Phase 1 — Data Model + Import Spec (2–3 days)
- Create migration spreadsheet/JSON with one row per epic/story.
- Include mappings for:
  - Title (`E-NNN` prefix retained)
  - Description body (scope, AC, notes)
  - Status/state
  - Assignee
  - Priority
  - Labels
  - Parent project relationship
- Dry-run on 1–2 completed epics plus 1 active epic.

### Phase 2 — Import + Validation (2–4 days)
- Import all active epics/stories first.
- Validate:
  - Story counts per epic/project match pre-migration counts.
  - State distribution is accurate.
  - Critical links/dependencies are preserved.
- Import archived items second (optional as closed projects/issues).

### Phase 3 — Agent and Workflow Cutover (1–2 days)
- Update agent guidance so planning/dispatch references Linear IDs and links.
- Update templates/checklists in repo docs to:
  - Point to Linear project/issue as authoritative tracker.
  - Keep repo docs for design/technical artifacts only.
- Add a “Linear-first PM” section to operator docs.

### Phase 4 — Stabilization + Dual-Write Exit (1–2 weeks)
- During dual-write window, validate that:
  - New work is opened in Linear.
  - Repo artifacts are linked from Linear, not vice versa.
- Exit criteria:
  - 100% active work tracked in Linear.
  - No new story status updates committed solely to repo files for 7 consecutive days.

## Agent Update Plan

## 1) Routing and command vocabulary
- Add explicit Linear-oriented trigger language:
  - “plan issue”, “create Linear project”, “dispatch issue”, “review issue”.
- Preserve backward compatibility for `E-NNN` references by resolving legacy IDs to linked Linear URLs.

## 2) Context loading behavior
- Default planning context source: Linear issue/project description and comments.
- Repo `epics/` files become supplemental context when legacy items are referenced.
- Keep selective loading behavior (no bulk `.claude/` scans).

## 3) Definition of done gates
- READY/IN-PROGRESS/DONE transitions should be reflected in Linear status.
- Code-review and spec-review outputs should post summary back to the linked Linear issue.

## 4) Documentation updates
- Update `CLAUDE.md` PM section to describe Linear canonical flow.
- Add a migration note documenting old-to-new ID conventions.

## Risks and Mitigations
- **Risk: hierarchy mismatch** (nested stories/subtasks).  
  **Mitigation**: represent deep breakdown as sub-issues under the mapped story issue.
- **Risk: status drift during migration window**.  
  **Mitigation**: time-box dual-write and assign migration owner for daily reconciliation.
- **Risk: broken traceability for historical references**.  
  **Mitigation**: retain legacy IDs in titles and custom field; keep repo archive immutable.
- **Risk: agent confusion across systems**.  
  **Mitigation**: explicit “Linear is source of truth” instruction and updated trigger examples.

## Acceptance Criteria for WIL-5
1. Mapping spec approved for epic→project and story→issue conversion.
2. Active backlog imported to Linear with validated counts and parent relationships.
3. Agent instructions updated to Linear-first PM flow.
4. Team runbook updated with cutover steps and rollback plan.
5. Dual-write window completed and formally closed.

## Suggested Rollback Strategy
If migration quality checks fail:
- Pause new imports and status edits.
- Keep repo epics/stories as temporary source of truth.
- Fix mapping defects and re-run import for affected project set only.
- Resume cutover after validation pass.

## Success Metrics (first 30 days)
- 100% of new work items created directly in Linear.
- <5% weekly mismatch between repo references and Linear statuses.
- Planning-to-dispatch cycle time unchanged or improved relative to pre-migration baseline.
- Zero critical work items lost due to mapping/import error.
