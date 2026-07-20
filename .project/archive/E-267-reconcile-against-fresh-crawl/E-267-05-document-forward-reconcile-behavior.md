# E-267-05: Document the Forward Reconcile-at-Load Behavior + the Clean-Slate Purge Command

## Epic
[E-267: Reconcile-at-Load Against the Fresh Crawl](epic.md)

## Status
`DONE`

## Description
After this story is complete, the operator/admin documentation describes (a) the new forward reconcile-at-load behavior — a re-scout now retires games/player-lines/roster entries that vanished from the fresh crawl (corroborated), redirects rescheduled games, and refuses to retire on a transient absence — AND (b) the new clean-slate purge command from E-267-06. This makes both discoverable so the operator understands why a re-scout may now remove data and how to start a clean data slate while preserving logins.

## Context
The reconcile-at-load retire is new behavior in the normal load path (no new command for that part). E-267-06 DOES add a new destructive CLI command (`bb db purge-scouting`). An operator needs to know both: that data can now be retired on a re-scout (transient absences deliberately NOT retired — bias-to-refuse), and how/when to run the purge to clean-slate while keeping user identity/auth.

## Acceptance Criteria
- [ ] **AC-1**: Given the reports/admin documentation, when an operator reads the re-scout/generate section, then it explains that a re-scout reconciles loaded data against the fresh crawl and retires corroborated-removed games/player-lines/roster entries, redirects rescheduled games, and refuses to retire on a transient/postponed absence.
- [ ] **AC-2**: The documentation states this is forward-only prevention-at-load (no retroactive repair) and references the E-257 reconciliation-scoreboard as the fidelity gate.
- [ ] **AC-3**: The documentation covers the `bb db purge-scouting` clean-slate command (E-267-06) — what it purges vs. preserves, the `--force` production behavior, and the on-disk HTML unlink — as the operator's clean-start path. It MUST state the `user_team_access` consequence explicitly: the purge preserves LOGIN (users + passkey + magic-link + sessions survive) but DOES purge `user_team_access`, so non-admin team-access grants are lost and are **NOT** automatically restored — an admin must re-grant them explicitly through the user-management UI (admins themselves are unaffected — admin-sees-all). "Logins preserved" alone is insufficient.

  <!-- AC-3 CORRECTED 2026-07-20 (PM; found by code-reviewer during E-267-05 review). This AC
       originally said grants are "lost and re-granted as teams regenerate". That is FALSE and the
       shipped doc correctly says the opposite. CR traced every `user_team_access` write in `src/`:
       the only automatic INSERT is `_assign_member_teams` (`api/auth.py:122-135`), whose sole caller
       is `_create_dev_user` (`:155`) via the non-production dev-user path (`:309`), and which is
       scoped to `membership_type = 'member'` teams — a category the E-239 reports-first descope left
       behind, since the reports flow creates `tracked` teams. The only other INSERTs
       (`reports_admin.py:231, 260`) are explicit admin action. NO re-scout or team-regeneration path
       grants access. An operator trusting the original wording would wait for a restoration that
       never comes — a worse failure than the "logins preserved alone is insufficient" gap this AC was
       written to close. Wrong about the world, therefore corrected (not merely recorded). -->

- [ ] **AC-4 (report generation is now DESTRUCTIVE — operator-facing warning)**: The documentation states that generating a report can now HARD-DELETE `games` rows and their full child surface. `src/reports/generator.py:1815` calls `load_team`, which runs the reconcile, so the reports surface — previously read-and-write-forward only — acquires a destructive side effect for the first time. This is the epic's intent, not a defect, but an operator MUST be able to learn it from the docs rather than by observing rows disappear. Surfaced by code-reviewer during E-267-02.
- [ ] **AC-5 (cross-perspective removed-game limitation)**: The documentation states the known coverage gap: a removed/voided game that was loaded from BOTH team perspectives is NOT retired — the game-grain retire deliberately refuses to hard-delete a `games` row another perspective owns, because that would destroy a second team's data. Consequence for the operator: such a game persists in recent form, the query-time season lines, W-L, and the freshness count. State it as a deliberate safety refusal with a known consequence, NOT as a bug. Tracked for a possible follow-on as IDEA-154. Do NOT document the pitcher-rest angle as a safety risk: a stale game can only ADD an appearance, so the error direction is toward MORE caution (a false positive), never toward masking a real rest violation.
- [ ] **AC-6 (orphaned report HTML after an interrupted purge — manual sweep)**: The documentation states that if `bb db purge-scouting` is interrupted between the transaction commit and the file unlink, HTML files may be left in `data/reports/` that NOTHING will ever clean up automatically — `cleanup_expired_reports()` works off `reports` rows, and the purge has already deleted them. One line telling the operator to sweep `data/reports/` manually after an interrupted purge is sufficient. This is the deliberate residual of the AC-5 unlink-after-commit ordering in E-267-06 (orphaned files with no dangling rows, chosen over dangling rows with missing files) — document it as a known trade-off, not a defect. Surfaced by code-reviewer during E-267-06.
- [ ] **AC-7 (a stale "Through {date}" / coverage count has a known cause)**: The documentation notes briefly that the report's "Through {date} (N games)" freshness line and footer coverage count can, in a narrow case, include a game whose player data is no longer live — so an operator seeing a stale date or an unexpectedly high N has a documented cause rather than a mystery. Keep it to a sentence or two: the cause is a known pre-existing predicate gap (IDEA-156), NOT a defect introduced by this epic, and it cannot affect any stat number (season lines, workload, and pitching history are all correctly scoped). Pairs naturally with the AC-6 orphaned-HTML note — both are "what looks wrong but is known" operator items.
- [ ] **AC-8 (roster departures are not retired for a team with no completed games)**: The documentation states that roster departures are reconciled only on a load that produced boxscores, so a team with no completed games keeps its full prior roster. One or two sentences. Frame it accurately: this is deliberate and fail-safe (a stale roster is never a wrongly-deleted one), and in practice it is not operator-visible for a true-preseason team, because a team with no completed games gets the explicit "no games" page rather than a full report. The operator-relevant point is simply that they should NOT expect a preseason roster cut to disappear from the grid before the team has played. Ruled and reasoned in E-267-04 AC-1c.
- [ ] **AC-9**: The docs match the behavior actually shipped in E-267-02/03/04 and the `bb db purge-scouting` command actually shipped in E-267-06 (verify against the merged behavior + command surface, not the plan). This is a docs story — exempt from the TN-7 regression-test requirement (per TN-7); verification is doc-accuracy, not a test.

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
