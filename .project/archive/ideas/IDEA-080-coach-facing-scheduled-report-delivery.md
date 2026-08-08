# IDEA-080: Coach-Facing Scheduled Report Delivery

## Status
`CANDIDATE`

## Summary
Once the morning-run scheduler (E-240) reliably generates fresh opponent reports
and surfaces them to the operator, add **coach-facing email delivery**: email the
report link directly to the coaching staff the morning of each game, instead of
the operator forwarding links by hand. Includes the deferred
stable-URL/extended-expiry option set aside in E-240.

## Why It Matters
E-240 (the forward feature) ships operator alerts + run records only — the
operator manually forwards report links to coaches. The actual product payoff is
coaches getting the link automatically, with zero operator step in the loop, the
morning of every game. This is the last mile of the reports-first vision
(`docs/ROADMAP.md` §1, §5 Epic E item 6).

## Rough Timing
After E-240 is complete and has soaked (the morning run reliably produces and
records reports). Promote when the operator feels the friction of manually
forwarding links, or when coaching-staff onboarding makes per-coach delivery
worth the subscription model.

## Dependencies & Blockers
- [ ] E-240 (morning-of-game scheduled reports) complete — the generic Mailgun
  sender it extracts (E-240-06) is the substrate this builds on.
- [ ] A decision on recipient management (a `report_subscriptions` table vs. a
  simpler per-team coach-email config) — see Open Questions.

## Open Questions

### Email content (baseball-coach MUST-HAVEs, captured at E-240 planning)
The coach-facing email must carry, at minimum:
- **Opponent + date in the subject** (so the coach can triage at a glance from a
  phone notification).
- **An at-a-glance coverage summary in the body** (e.g. "Through {date}, {N} of
  {M} games") — the same honest, data-bearing coverage signal the report footer
  carries (`.claude/rules/data-model.md` Data-Bearing Coverage).
- **An auto-generated provenance note** (this report was generated automatically
  the morning of the game).
- **A low-coverage warning in the subject** when coverage is thin (so the coach
  knows the report is light before opening it).
- **A name-only-match note** when the opponent team was matched by name only (no
  `public_id`/`gc_uuid` anchor) — the existing identity trust flag, surfaced to
  the coach.

### Stable URL / extended expiry (deferred from E-240)
E-240 deliberately kept the existing 14-day report expiry and did NOT add a
`source` column, expiry extension, or a stable "latest-per-opponent" URL
(operator decision: the 14-day window already outlives game morning, and doing
nothing keeps morning-run out of the protected-core generator). For coach-facing
delivery, reconsider whether an emailed link clicked days later (past expiry)
should resolve — i.e. whether scheduled/coach-delivered reports need either an
extended expiry or a stable per-opponent URL so a late click does not 404. This
is the freshness/expiry question `docs/ROADMAP.md` §5 item 5 raised; it was set
aside for E-240 and belongs here.

### Recipient model
- Per-coach subscriptions (`report_subscriptions` table) vs. a simpler per-team
  coach-email list? Operator decision #4 in `docs/ROADMAP.md` §5 keeps E-240
  admin-free; coach delivery is the thing that could push toward a management
  surface — decide whether to keep it config-only or introduce a UI.

## Notes
Parent epic: **E-240** (morning-of-game scheduled reports). E-240 extracts the
generic Mailgun sender and ships operator-only alerts; this idea is the
coach-facing half deliberately deferred. Related: `docs/ROADMAP.md` §5 Epic E
items 5 (freshness/expiry) and 6 (delivery); `.claude/rules/data-model.md`
Data-Bearing Coverage (the honest coverage signal the email summary reuses).

---
Created: 2026-06-17
Last reviewed: 2026-06-17
Review by: 2026-09-15
