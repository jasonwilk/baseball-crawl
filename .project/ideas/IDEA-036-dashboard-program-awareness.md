# IDEA-036: Dashboard Program Awareness

## Status
`CANDIDATE`

## Summary
Add program-based navigation or filtering to the coaching dashboard. E-100 updated the dashboard for INTEGER PK compatibility but did not add program awareness — the dashboard shows teams without program context.

## Why It Matters
When the operator manages teams across HS, USSSA, and Legion, coaches need to filter or navigate by program. A varsity coach doesn't want to see 14U travel ball data mixed into their view.

## Rough Timing
After multiple programs have teams. Promote when:
- More than one program has active teams
- Coaches report confusion from seeing teams across programs in the dashboard

## Dependencies & Blockers
- [ ] Multiple programs with active teams (currently only `lsb-hs` exists)
- [ ] IDEA-034 (program CRUD) — need a way to create programs first

## Open Questions
- Program filter in the team selector dropdown? Program-scoped dashboard routes? Program landing page?
- E-100 explicitly rejected "program-first dashboard navigation" — this should be team-first with optional program filtering, not program-first.
- UX designer and baseball-coach consultation needed.

## Notes
- E-100 Non-Goal: "Dashboard program-awareness: No program-based navigation or filtering. INTEGER PK compatibility only."
- Key constraint: "Team-and-season is the primary lens" (E-100 vision decision). Program is a secondary filter, never the primary navigation frame.

---
Created: 2026-03-16
Last reviewed: 2026-03-16
Review by: 2026-06-14
