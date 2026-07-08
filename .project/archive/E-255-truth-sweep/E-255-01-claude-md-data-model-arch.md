# E-255-01: CLAUDE.md + data-model.md + arch-subsystems.md + migrations.md truth corrections

## Epic
[E-255: Truth Sweep — Context Layer, API Docs, Runbooks](epic.md)

## Status
`DONE`

## Description
After this story is complete, the most cross-referenced context-layer files — `CLAUDE.md`, `.claude/rules/data-model.md`, `.claude/rules/architecture-subsystems.md`, and `.claude/rules/migrations.md` — describe the current reports-first system. No ambient dashboard-as-live references, no deleted machinery presented as live, no phantom migration-number citations, and no stale helper names or "cached boxscore JSON" framing survive except where explicitly framed as history.

## Context
These four files are touched by multiple audit docket items and by several intervening epics (E-250/252/253/254 all edited `CLAUDE.md` and/or `data-model.md`). Clustered into one story so no other story edits them (conflict isolation, TN-3). Corrections reflect CURRENT reality (TN-2) and are re-verified against the current file before applying (TN-1). The `team_season` shape claim in `data-model.md` L18 is settled by E-255-R-01 (do not guess).

## Acceptance Criteria
- [ ] **AC-1**: Given `CLAUDE.md`'s Purpose/Scope dashboard-era wording (audit cited L17/L29/L32/L51/L60 — an ILLUSTRATIVE, non-exhaustive list; also catch any other dashboard-era line found on re-verification, e.g. the docket's L172 citation), its L21 self-caveat flagging that prose as the CE-5 item, the L137 admin-ui pointer, and the two agent-table rows carrying dashboard-era wording (L176 docs-writer row; L177 ux-designer row, literally "UX/interface designer for coaching **dashboard**…"), when each is re-verified and corrected, then no `CLAUDE.md` line presents the dashboard/member-sync surfaces as live product surfaces (historical "removed in E-239" mentions retained as history), the L21 self-caveat is removed once its referenced prose is fixed, the admin-ui-pointer line reflects current behavior, and **the L176/L177 agent-table rows are reframed to AGREE with the E-255-03 refocused charters** (docs-writer → reports/morning-run runbooks; ux-designer → the full **report-layout / trust-surface / tools-hub** triad — "report-layout/trust-surface" elsewhere is a deliberate abbreviation of that triad, not a narrower scope; cite E-255-03 / the curation handoff as the framing source). This is the CLAUDE.md-table analogue of TN-7; no hard 03→01 dependency (REPURPOSE is locked), just keep the two files' framing consistent. (The audit's "L131 race caveat" is NOT in scope — see AC-5.)
- [ ] **AC-2**: Given phantom migration-number citations — `data-model.md` L22 cites "migration 015" (appearance_order), `arch-subsystems.md` L94 cites "migration 012" (reconciliation_discrepancies), and `.claude/rules/migrations.md` L12/L13 say "latest is 004" / "currently 005" — when re-verified against `ls migrations/` (live set 001–010, next = 011; those tables actually live in the consolidated `001_initial_schema.sql` per E-220), then no phantom or superseded migration number is presented as current (prefer dropping the concrete number — `migrations.md` itself says "always `ls`, this list rots").
- [ ] **AC-3**: Given `data-model.md` L18-20 describing deleted machinery as live, when corrected, then `data-model.md` describes only tables/columns that exist post-migration-010 and its `team_season` shape (L18) matches the E-255-R-01 verified shape. NOTE: the L31/L32 E-104 "awaits" text is ALREADY fixed (now says abandoned, E-250-07) — verify and exclude, do not re-touch.
- [ ] **AC-4**: Given `architecture-subsystems.md`'s stale renamed-helper name and its "cached boxscore JSON" framing, when re-verified against the current code seams and corrected, then the helper is referenced by its current name and the boxscore-derivation framing matches how the code actually sources the data.
- [ ] **AC-5**: Given the re-verify mandate (TN-1), when any audit-cited claim in these files is found already-correct (fixed by an intervening epic), then the story notes record it as discharged and the prose is left unchanged — no regression to already-accurate text. SPECIFICALLY: the audit's "CLAUDE.md L131 race caveat" is DISCHARGED — the L128–134 region is now CURRENT, load-bearing canonical-helper concurrency INVARIANTS (esp. L134's `get_connection()` "busy_timeout is false safety without commit discipline / lock overlap waits" invariant, which is ACCURATE). Record it discharged and do NOT edit the L134 connection-factory invariant — editing it would be a regression, not a fix.
- [ ] **AC-6**: Given the whole-file review, when complete, each file's staleness/"Last updated" convention line (where present) reflects this correction pass.
- [ ] **AC-7** (TN-9 runbook-path coupling with E-255-05): Given `CLAUDE.md`'s deployment pointer `See docs/production-deployment.md for the verified deployment runbook` (~L40; verify the exact line at drafting) and E-255-05 relocates that runbook into `docs/admin/`, when updated, then the CLAUDE.md pointer reads **`docs/admin/production-deployment.md`** — the identical new path story 05 moves the file to (this is the one inbound ref outside docs-writer's ownership; CLAUDE.md is CA's file, so the update lands here, not in story 05).

## Technical Approach
Read each file in full first; the audit line numbers are stale. Hunt the *class* of error, not the exact line. Cross-check migration numbers against `migrations/`. Consume `.project/research/E-255-verified-facts.md` (E-255-R-01) for the `team_season` shape. Keep historical references as history (TN-2).

## Dependencies
- **Blocked by**: E-255-R-01 (verified `team_season` shape for data-model.md L18)
- **Blocks**: None

## Files to Create or Modify
- `CLAUDE.md`
- `.claude/rules/data-model.md`
- `.claude/rules/architecture-subsystems.md`
- `.claude/rules/migrations.md`

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Migration numbers verified against `migrations/` (none phantom)
- [ ] `team_season` shape matches E-255-R-01 artifact
- [ ] E-104 "awaits" NOT re-touched (already fixed in E-250-07)
- [ ] Discharged-already items recorded in story notes

## Notes
Audit CA docket items landing here: CLAUDE.md Purpose/Scope dashboard wording + L21 self-caveat + L131 race caveat + L137 admin-ui pointer; phantom migrations (data-model L22, arch-subsystems L94, migrations.md L12/L13); data-model L18-20; arch-subsystems renamed-helper + "cached boxscore JSON". Excluded (already fixed): data-model E-104 "awaits" (E-250-07); `PlayerTeamSeason` scrub (E-250).
