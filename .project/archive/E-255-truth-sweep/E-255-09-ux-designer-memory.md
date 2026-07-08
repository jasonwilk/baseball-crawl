# E-255-09: ux-designer own-memory truth sweep

## Epic
[E-255: Truth Sweep — Context Layer, API Docs, Runbooks](epic.md)

## Status
`DONE`
<!-- ux repurpose-or-retire RESOLVED 2026-07-07 by Jason: REPURPOSE. The REPURPOSED ACs below apply;
     the RETIRED branch is retained for record only (moot). -->

## Description
After this story is complete, ux-designer's own memory (`.claude/agent-memory/ux-designer/`) is rewritten around the surviving report/serving surfaces, consistent with the refocused charter (E-255-03).

## Context
Own-memory edit routed to ux-designer under the own-memory carve-out. The ux repurpose-or-retire question is RESOLVED (Jason 2026-07-07: REPURPOSE — refocus, do not retire; matches VISION D4), so the REPURPOSED ACs below are the operative branch (the RETIRED branch is kept for record only and does not apply). The ux-designer docket recon (relayed via main) verified the current surviving surfaces and the stale content. The story depends on E-255-03 (the refocused charter must land first, so the memory aligns to it).

Verified surviving surfaces (ux recon): `base.html` = top-nav "Baseball Stats" + single "Admin" link (NO bottom nav); `admin/_subnav.html` = 2 tabs Reports|Users; live surfaces = `admin/{reports,users,edit_user}.html`, `reports/scouting_report.html`, `auth/*`, `errors/*`. STALE (all deleted in E-239): Base Layout "bottom nav 4 tabs Batting/Pitching/Games/Opponents"; Admin Sub-Nav "Users|Teams|(Opponents)" (teams.html deleted); Card Pattern dashboard framing; E-178 Coach-Friendly Language table; E-088 Status Badge (opponent link state); Key File Paths (4 of 5 dead — only base.html survives). KEEP: generic Table/Button/Form/Flash/Back-Link patterns; Reference Impl → `admin/reports.html`; `feedback_coach_async_workflow.md`; `design_principles.md` principles 1 & 2 (principle 3 "Unified Verbs Sync/Merge/Connect" references deleted flows).

## Acceptance Criteria (REPURPOSED branch — OPERATIVE, decided 2026-07-07)
- [ ] **AC-1**: Given the Base Layout memory describing a deleted "bottom nav 4 tabs Batting/Pitching/Games/Opponents", when rewritten, then it describes the current top-nav ("Baseball Stats" + single "Admin" link, no bottom nav).
- [ ] **AC-2**: Given the Admin Sub-Nav memory listing "Users|Teams|(Opponents)", when corrected, then it reads the current two tabs Reports|Users.
- [ ] **AC-3**: Given the E-178 Coach-Friendly Language table and the E-088 Status Badge pattern (both for deleted flows), when handled, then each is deleted or marked SUPERSEDED such that no live reference presents them as current design targets. **Verification note (for the code-reviewer):** the check targets terminology-as-current-guidance FRAMING, not bare tokens — a SUPERSEDED tombstone will legitimately still contain the words "Sync"/"opponent", so a raw token grep would false-positive; verify no *live-guidance* framing remains, not token absence.
- [ ] **AC-4**: Given the Key File Paths section (4 of 5 paths dead), when corrected, then every listed path resolves to an existing file (a spot-check confirms each), anchored on `reports/scouting_report.html` and `admin/reports.html` as the reference implementations.
- [ ] **AC-5**: Given `design_principles.md` principle 3 ("Unified Verbs Sync/Merge/Connect") references deleted flows, when reconciled, then it no longer prescribes verbs for surfaces that no longer exist (principles 1 & 2 and `feedback_coach_async_workflow.md` are KEPT unchanged).
- [ ] **AC-6**: Given the refocused ux-designer charter from E-255-03, when this rewrite completes, then the memory is consistent with that charter (report-layout / trust-surface / tools-hub docket).

## Acceptance Criteria (RETIRED branch — MOOT, record only; NOT applied)
- [ ] ~~**AC-R1**~~: (Would have applied only if the agent were retired — Jason decided REPURPOSE, so this branch does not apply. Kept for record.)

## Technical Approach
Read the refocused charter (E-255-03 output) and the current templates first; rewrite around surviving surfaces; verify each Key File Path resolves. Keep it lightweight (net-growth counterweight).

## Dependencies
- **Blocked by**: E-255-03 (the refocused charter)
- **Blocks**: None

## Files to Create or Modify
- `.claude/agent-memory/ux-designer/MEMORY.md`
- `.claude/agent-memory/ux-designer/design_principles.md` (REPURPOSED branch, principle 3 only)
- (confirm the full file list by listing `.claude/agent-memory/ux-designer/`; `feedback_coach_async_workflow.md` is KEPT untouched)

## Agent Hint
ux-designer

## Definition of Done
- [ ] All REPURPOSED-branch ACs (AC-1..AC-6) pass
- [ ] Memory aligned to the refocused charter (E-255-03)
- [ ] Every Key File Path resolves; no dashboard surface presented as a live design target

## Notes
The repurpose-or-retire question is decided (Jason 2026-07-07: REPURPOSE); the RETIRED branch above is moot and kept for record only.
