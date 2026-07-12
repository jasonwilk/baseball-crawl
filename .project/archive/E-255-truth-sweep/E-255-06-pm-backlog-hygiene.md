# E-255-06: PM backlog hygiene — ROADMAP consistency + stale-READY triage + artifact disposition

## Epic
[E-255: Truth Sweep — Context Layer, API Docs, Runbooks](epic.md)

## Status
`DONE`

## Description
After this story is complete, `docs/ROADMAP.md` is internally consistent, the ideas README is swept of moot CANDIDATEs and the unnumbered file is indexed, `docs/E-221-HANDOFF.md` is dispositioned, dead-table retention is captured as an idea, and the stale-READY epics are triaged with recommendations surfaced to the user.

## Context
PM-owned backlog hygiene from the audit PM docket. Two docket items are already done (E-211 flip + IDEA-056/060 repair, 2026-07-04) and VISION/vision-signals curation is done (2026-07-05) — all descoped per epic Non-Goals. This story does the mechanical hygiene directly AND applies the dispositions <OPERATOR-REDACTED> decided on 2026-07-07 (TN-5): E-193 archive ABANDONED, E-073 shrink/archive, E-072/E-174/E-175 one-time triage, and — reversing the same-day SKIP — codification of the stale-READY re-confirmation rule (AC-6; rule-creation portion routes to claude-architect). The dead-table set is confirmed by data-engineer during docket-confirmation (not a user decision).

## Acceptance Criteria
- [ ] **AC-1**: Given `docs/ROADMAP.md` is still `Status: DRAFT` while §0 shows slices A–E COMPLETED, when corrected, then the status header reflects the executed state and the §4 Cruft Inventory / §5 D2 prose no longer describe D1/D2 removal as *future* work (E-238/E-239 shipped it) — header, §0 table, and §4/§5 prose are mutually consistent.
- [ ] **AC-2**: Given the ideas README may carry moot CANDIDATEs (surfaces removed post-descope) and one unnumbered/unindexed idea file, when swept, then moot CANDIDATEs are marked DISCARDED with a reason and the unnumbered idea file is either numbered+indexed or removed with rationale (a scan confirms every `.project/ideas/IDEA-*.md` file has a matching README row and vice versa).
- [ ] **AC-2b**: Given `IDEA-010-docs-port-map-consistency.md` references `agent-browsability-workflow.md` (which E-255-02 deletes), when this story completes, then that stale reference is removed or updated in the IDEA-010 file (this cleanup is routed here because `.project/ideas/` is PM-owned; flagged from E-255-02 AC-6).
- [ ] **AC-3**: Given `docs/E-221-HANDOFF.md` is a dead session-handoff targeting deleted code, when dispositioned, then the file is removed OR explicitly marked SUPERSEDED with a pointer to why (no live artifact references it as actionable).
- [ ] **AC-4**: Given the inert-but-retained tables — set confirmed by DE + PM verification (2026-07-07) to be exactly **`crawl_jobs`** (sole ref = one DELETE in the team-deletion cascade; never INSERT/SELECT) and **`coaching_assignments`** (2 DELETEs + a docstring; never INSERT/SELECT) — when captured, then a new idea file records the retention rationale and the drop-blocker (cascade-logic rewrites). EXCLUSIONS baked in: `user_team_access` is LIVE (non-admin team-access grant mechanism — W=3/R=7 across auth.py + reports_admin.py; do NOT capture); `team_opponents` was already DROPPED in migration 008 (E-250) so it is gone, not retained (PM verified `DROP TABLE team_opponents` at migrations/008 L75); `programs` is unqueried in app code but FK-load-bearing (migration 001 bootstraps `lsb-hs`, `teams.program_id` FKs to it) — flag as "unqueried-but-load-bearing," keep OUT of the dead set.
- [ ] **AC-5**: Given the decided dispositions (<OPERATOR-REDACTED> 2026-07-07): **E-193 → archive ABANDONED** (dashboard premise deleted in E-239, agent-browser never installed) — moved to `.project/archive/` with ABANDONED status + reason; **E-073 → archive or shrink** (E-255-04 owns the endpoint-doc corrections; PM decides archive-vs-shrink-to-remainder at triage — and MUST confirm the `docs/api` `game_stream.id`/`event_id` cross-file consistency sweep is covered by E-255-04 AC-5b before archiving E-073, so that work does not fall between epics); **E-072/E-174/E-175 → triaged once** with a written re-confirm/replan/archive recommendation per epic noting the premise drift. When this story completes, each of the four stale-READY epics has its disposition applied or its recommendation recorded.
- [ ] **AC-6** (REVERSED 2026-07-07 — <OPERATOR-REDACTED> ADOPTED the rule after agentic-flow-review evidence, reversing the same-day SKIP: five epics sat READY 99-122 days on invalidated premises, E-072/E-073 target surfaces E-239 deleted; AGENTIC-FLOW-REVIEW.md §2.2): Given stale READY epics accumulate against premises later descopes invalidate, when this story completes, then a stale-READY re-confirmation rule is codified — an epic in READY for more than 60 days is STALE, and PM must either re-confirm it against `docs/ROADMAP.md` or demote it to DRAFT — and the staleness check is wired into BOTH the plan-skill and implement-skill Prerequisites. **Routing note**: the rule text + the two `SKILL.md` Prerequisite edits are context-layer work → route that portion to **claude-architect** (already on the epic team via E-255-01/02/03); the one-time triage of the currently-stale epics stays with PM under AC-5. Likely rule home: `.claude/rules/workflow-discipline.md` (alongside the existing READY gate) — CA's design call.

## Technical Approach
ROADMAP edits are the one mechanical AC that changes a doc directly; the rest is triage + idea capture + surfacing. Verify the dead-table set against the live schema via data-engineer if needed. Keep triage recommendations concise; the user makes the disposition calls.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `docs/ROADMAP.md`
- `.project/ideas/README.md`
- `.project/ideas/IDEA-010-docs-port-map-consistency.md` (AC-2b: remove the stale `agent-browsability-workflow.md` reference)
- `.project/ideas/IDEA-NNN-dead-table-retention.md` (new — next number by glob at write time)
- `docs/E-221-HANDOFF.md` (DELETE or mark SUPERSEDED)
- `epics/E-193-browser-automation/` → `.project/archive/E-193-browser-automation/` (AC-5: archive ABANDONED with reason)
- E-073 disposition (archive `epics/E-073-api-validation-sweep/` → `.project/archive/`, or shrink its scope — PM's call at triage)
- `epics/E-072-*/`, `epics/E-174-*/`, `epics/E-175-*/` (triage note per epic; disposition applied per recommendation)
- (the unnumbered idea file, if present — number+index or remove)
- `.claude/rules/workflow-discipline.md` (AC-6: stale-READY rule text — claude-architect, context-layer; likely home, CA's call)
- `.claude/skills/plan/SKILL.md` + `.claude/skills/implement/SKILL.md` (AC-6: wire the staleness check into both Prerequisites — claude-architect, context-layer)

## Agent Hint
product-manager

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] ROADMAP header + §0 + §4/§5 mutually consistent
- [ ] Ideas README ↔ files reconciled; dead-table idea captured (DE-confirmed set); IDEA-010 reference cleaned
- [ ] E-193 archived ABANDONED; E-073 archived/shrunk; E-072/E-174/E-175 triaged; stale-READY rule codified + wired into plan/implement Prerequisites (rule-creation portion by claude-architect)

## Notes
Descoped (already done): E-211 archive flip, IDEA-056/060 repair, VISION/vision-signals curation. Do NOT redo. The idea number for the dead-table capture must be assigned by globbing `.project/ideas/` at write time (memory counters go stale). Archiving epics follows the project-management rule (move dir to `.project/archive/`, never delete); E-193 gets an ABANDONED status + reason in its epic.md before the move.
