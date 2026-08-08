# IDEA-164: `generate_report()` carries a SECOND terminally-wired destructive pass

## Status
`CANDIDATE`

## Summary
E-267 made report generation destructive (reconcile-at-load can hard-delete `games` and their full child surface). E-273 added a SECOND hard-deleting pass to the same entry point: `generate_report()` calls `cleanup_expired_reports()` at its very start (`src/reports/generator.py:1517-1519`), which runs `reclaim_orphan_reference_data()` (`src/reports/lifecycle.py:300`), hard-deleting unreachable `teams` / `team_rosters` / `players`. Both passes are wired terminally/opportunistically rather than behind an explicit destructive command, so generating a report destroys data on two independent axes with no operator confirmation, no dry-run, and no pre-pass snapshot. This idea is to ask whether the reclamation axis warrants the same guard treatment E-270 is giving the reconcile axis (absolute cap, refusal distinguishability, informed confirmation).

## Why It Matters
E-270 exists because the E-267 audit found the destructive surface under-guarded on the reconcile axis. The reclamation axis is structurally the same shape — an unattended hard delete reachable from a command an operator thinks of as read-only, including via `bb report morning-run` cron. The counterargument is real and may be decisive: E-273 shipped its own guards (reachability predicate over all six game-child FK tables, three preserved operator/security roots, reap-then-gate on live `generating` reports, and a fixed-point self-assert that rolls back rather than committing a half-correct state) and landed with a full review round including a Codex finding. So this is a "should we look?" flag, not a defect claim.

## Rough Timing
No urgency. Natural trigger: the first time a live reclamation deletes something the operator did not expect, OR the next time the E-270-class question ("is this destructive surface adequately guarded?") is asked about the reports pipeline. Also worth revisiting if the reclamation's ordering ever moves after the crawl/load — today it runs BEFORE them, which is what keeps the two axes from compounding within one run.

## Dependencies & Blockers
- [ ] None hard. E-270 should close first so the reconcile-axis guards are the settled comparison baseline.

## Open Questions
- Is a cap/confirmation even meaningful here? The reclamation's population is derived by reachability, not by a diff against a fresh crawl, so the "truncated payload mass-deletes" failure mode that motivates `MAX_GAME_RETIREMENTS` may have no analogue.
- Is there an observability gap? The pass logs counts at INFO and defers silently; an operator running `bb report generate` sees nothing about what was reclaimed.
- Does the two-pass compounding matter across runs? Run N's retire can orphan a team whose only game it deleted; run N+1's reclamation then sweeps that team. No single run shows the operator the whole chain.

## Notes
Raised by PM during the 2026-07-24 E-273 premise re-check at E-270 dispatch, and explicitly held OUT of E-270 scope by team-lead decision (E-270 is chartered on the E-267 reconcile axis; expanding it mid-dispatch would be scope creep). E-270-03 AC-6 now pins the attribution boundary between the two passes in test, which is the narrow piece that belonged in E-270. Related: E-267 (reconcile-at-load), E-273 (orphan reference reclamation), E-270 (this hardening epic), [[IDEA-160]] (`MAX_GAME_RETIREMENTS`, promoted into E-270-01).

---
Created: 2026-07-24
Last reviewed: 2026-07-24
Review by: 2026-10-22 (90 days)
