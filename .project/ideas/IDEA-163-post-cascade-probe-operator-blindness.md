# IDEA-163: Post-Cascade Probe — report-delete operator blindness

## Status
`DEFERRED`

## Summary
`_delete_report` (`src/api/routes/reports_admin.py`) swallows cascade failure with a `logger.warning` and returns `None`; the route flashes `"Report deleted."` unconditionally. Full delete, partial retention, and cascade exception are all indistinguishable to the operator — the 46 retentions behind E-273 were structurally invisible. `.claude/rules/admin-ui.md` already contains a "Post-Cascade Probe for Retention UI" convention written for exactly this helper, but it is NOT implemented. This idea is to implement it: probe post-cascade DB state and emit an accurate flash.

## Why It Matters
Operator honesty: a flash that claims a full deletion after a retention-path (or failed) cascade is a lie the operator can catch by refreshing. It is a legitimate independent UI-honesty gap.

## Rough Timing
Low urgency. E-273 (orphan reference reclamation) REDUCES the pressure: once the terminal reclamation pass runs at the end of every `_delete_report`, a retained team is swept by the end of the SAME delete request, so the `"Report deleted."` flash becomes accurate again (the team really is gone). The probe remains legitimate for the cascade-EXCEPTION case (where the flash still lies), but it is no longer masking silent data retention. Promote if the operator wants delete-path failure surfaced, or when the admin UI is next touched.

## Dependencies & Blockers
- [ ] None hard. E-273 changes the framing (see Rough Timing) but does not block this.

## Open Questions
- Post-E-273, is the remaining exposure only the cascade-exception path (worth a small probe), or is the whole probe now low-value enough to leave as-is?
- Does the flash need to distinguish "team data removed; team row retained" now that reclamation makes retention transient within the request?

## Notes
Deferred at E-273 planning (2026-07-21) per team-lead decision. The Post-Cascade Probe convention already exists in `.claude/rules/admin-ui.md`; this idea is about implementing it. Related: E-273 (orphan reference reclamation), which is the completeness fix that makes the retention transient. `.claude/rules/admin-ui.md` "Post-Cascade Probe for Retention UI".

---
Created: 2026-07-21
Last reviewed: 2026-07-21
Review by: 2026-10-19 (90 days)
