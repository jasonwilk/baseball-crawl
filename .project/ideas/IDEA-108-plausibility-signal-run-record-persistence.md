# IDEA-108: Persist the report-time plausibility signal on the run record

## Status
`CANDIDATE`

## Summary
Upgrade E-257-03's report-time plausibility guard from a generate-time WARNING-log (the shipped E-257 form) to a persisted, queryable operator trust flag on `report_generation_runs`, surfaced in `/admin/reports` like E-236's per-stage status honesty split. This is the "(b)" option that E-257 deliberately deferred in favor of the simpler "(a)" WARNING-only form.

## Why It Matters
The WARNING-log form (E-257-03) reproduces the human-eyeball catch at generation time — the operator sees the warning when they run the generation. But a WARNING is transient: it is not queryable after the fact, does not surface in the admin reports list, and an unattended morning-run generation (E-240) writes it only to logs the operator may not read. Persisting the signal as a run-record trust flag would let an operator see "this report had an implausible FPS%" in `/admin/reports` days later, and would make the signal survive an unattended run — the same operator-vs-coach honesty split E-236 established for per-stage degradation.

## Rough Timing
Promote if operators, after living with the E-257-03 WARNING-log form, find they miss implausible values that scrolled past in logs — especially on unattended morning-run generations where no operator was watching the console. No urgency until that pain is felt.

## Dependencies & Blockers
- [ ] E-257 complete (E-257-03 ships the WARNING-log form + the FPS/P-PA plausibility bounds this would persist)
- [ ] Operators express a need to see the signal persisted/queryable rather than at generate-time only

## Open Questions
- New boolean column vs. a structured field capturing which rate was out of range and by how much?
- Does it feed the derived `degraded` read (E-236: `overall_status == "completed"` AND any per-stage status in {partial, failed}), or stand as a separate trust dimension?
- Requires a migration + `_RUN_RECORD_COLUMNS` allowlist update + a real-schema round-trip test (the documented silent-drop footgun in `.claude/rules/architecture-subsystems.md`, Run-Record Column Allowlist) — makes it a DE+SE story, not SE-only.

## Notes
Deferred out of E-257-03 at planning (2026-07-08). SE and the planning lead both recommended the simpler WARNING-log form (a) for E-257, aligning with CLAUDE.md's "simple first, complexity as needed," and capturing this persistence option (b) as a follow-on idea. Coach's framing ("operator-facing flag, review before sharing") is satisfied by the generate-time WARNING; this idea is the persistence upgrade if that proves insufficient. Related: E-236 (per-stage status honesty split, the persistence pattern this would mirror), `.claude/rules/architecture-subsystems.md` (Report-stage status honesty; Run-Record Column Allowlist footgun).

---
Created: 2026-07-08
Last reviewed: 2026-07-08
Review by: 2026-10-06
