# E-267-05: Document the Forward Reconcile-at-Load Behavior + the Clean-Slate Purge Command

## Epic
[E-267: Reconcile-at-Load Against the Fresh Crawl](epic.md)

## Status
`TODO`

## Description
After this story is complete, the operator/admin documentation describes (a) the new forward reconcile-at-load behavior — a re-scout now retires games/player-lines/roster entries that vanished from the fresh crawl (corroborated), redirects rescheduled games, and refuses to retire on a transient absence — AND (b) the new clean-slate purge command from E-267-06. This makes both discoverable so the operator understands why a re-scout may now remove data and how to start a clean data slate while preserving logins.

## Context
The reconcile-at-load retire is new behavior in the normal load path (no new command for that part). E-267-06 DOES add a new destructive CLI command (`bb db purge-scouting`). An operator needs to know both: that data can now be retired on a re-scout (transient absences deliberately NOT retired — bias-to-refuse), and how/when to run the purge to clean-slate while keeping user identity/auth.

## Acceptance Criteria
- [ ] **AC-1**: Given the reports/admin documentation, when an operator reads the re-scout/generate section, then it explains that a re-scout reconciles loaded data against the fresh crawl and retires corroborated-removed games/player-lines/roster entries, redirects rescheduled games, and refuses to retire on a transient/postponed absence.
- [ ] **AC-2**: The documentation states this is forward-only prevention-at-load (no retroactive repair) and references the E-257 reconciliation-scoreboard as the fidelity gate.
- [ ] **AC-3**: The documentation covers the `bb db purge-scouting` clean-slate command (E-267-06) — what it purges vs. preserves, the `--force` production behavior, and the on-disk HTML unlink — as the operator's clean-start path. It MUST state the `user_team_access` consequence explicitly: the purge preserves LOGIN (users + passkey + magic-link + sessions survive) but DOES purge `user_team_access`, so non-admin team-access grants are lost and re-granted as teams regenerate (admins are unaffected — admin-sees-all). "Logins preserved" alone is insufficient.
- [ ] **AC-4**: The docs match the behavior actually shipped in E-267-02/03/04 and the `bb db purge-scouting` command actually shipped in E-267-06 (verify against the merged behavior + command surface, not the plan). This is a docs story — exempt from the TN-7 regression-test requirement (per TN-7); verification is doc-accuracy, not a test.

## Technical Approach
Update the appropriate `docs/admin/` (and `docs/coaching/` if a coach-facing note is warranted) surface describing report generation / re-scouting and the purge command. Keep it concise and current-state.

## Dependencies
- **Blocked by**: E-267-02, E-267-03, E-267-04, E-267-06
- **Blocks**: None

## Files to Create or Modify
- `docs/admin/` report-generation / re-scout + purge-command documentation (exact file per the docs-writer's assessment)

## Agent Hint
docs-writer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Documentation reflects the shipped behavior
- [ ] No regressions in existing tests

## Notes
Master record: `.project/research/2026-07-19-rerun-accumulate-only-audit.md`.
