# IDEA-037: Scouting Report Redesign

## Status
`CANDIDATE`

## Summary
Redesign scouting reports with rate stats (OBP, K/9, BB/9), proactive flags (hot/cold streaks, recent form), and PDF export for game-day use. E-100's UX consultation surfaced these needs but scoped them out.

## Why It Matters
Scouting reports are the primary coaching deliverable. Current reports show raw counting stats. Coaches need:
- Rate stats (computed at query time from the counting stats we store) for meaningful comparison
- Proactive flags that surface actionable patterns (e.g., "this pitcher has walked 5+ in 3 of last 4 games")
- PDF export so coaches can print reports for the dugout (no Wi-Fi at most HS fields)

## Rough Timing
After IDEA-028 (stat population) and dashboard development. Promote when:
- Stat data is flowing and the dashboard can display it
- Coaching staff is actively using the system for game prep
- Baseball-coach consultation to define which rate stats and flags matter most

## Dependencies & Blockers
- [ ] IDEA-028 (stat population) — need data to compute rates and detect patterns
- [ ] Dashboard must be functional for coaches
- [ ] Baseball-coach consultation for flag definitions and report layout priorities

## Open Questions
- Which rate stats are highest priority? (OBP, SLG, ERA, WHIP, K/9, BB/9 are standard)
- What proactive flags would coaches actually use? Streak detection? Workload alerts? Matchup advantages?
- PDF generation approach: server-side rendering (WeasyPrint, ReportLab) or print-friendly CSS?
- Should flags be computed at crawl time (stored) or query time (computed)?

## Notes
- E-100 Non-Goal: "Scouting report redesign: Rate stats, proactive flags, PDF export — all follow-up epics."
- UX designer consultation surfaced these needs during E-100 coach interview.
- Rate stats are computed from counting stats — no additional API data needed, just query logic.
- Related to IDEA-029 (L/R splits) — split data would enhance scouting reports significantly.

---
Created: 2026-03-16
Last reviewed: 2026-03-16
Review by: 2026-06-14
