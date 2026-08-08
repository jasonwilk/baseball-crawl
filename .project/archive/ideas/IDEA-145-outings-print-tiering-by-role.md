# IDEA-145: Tier the Outings Breakdown print artifact by pitcher role

## Status
`CANDIDATE`

## Summary
In the printed/PDF scouting artifact, show the full per-outing game log only for probable/likely starters, and a season-line-only view for relief arms — instead of E-266's uniform "force-open every pitcher's full log for print." Keeps the printed page scannable when a coach is prepping 30 minutes before first pitch rather than turning into 9 full game logs.

## Why It Matters
E-266's print fix (`matchMedia('print')` open-toggle, TN-2) force-opens ALL pitchers' full per-outing logs uniformly for print. baseball-coach's original artifact-shape tiering (`.claude/agent-memory/baseball-coach/pitcher-outings-scouting-consultation.md`) recommended full per-outing logs only for the arms a coach is actually preparing to face (probable/likely starters), with season-line-only for relievers, specifically so the pre-game PRINT artifact stays short. A 9-pitcher staff × full game logs can make the printed page long and reduce its at-a-glance value in the dugout. This is a content-scope refinement, not a rendering defect — E-266 correctly kept content/derivation off the table (Non-Goals), so it belongs in a follow-on.

## Rough Timing
After E-266 ships and the fixed Outings Breakdown is used in real printed reports. Promote if the printed artifact turns out too long in practice, or when the report gains a probable-starter signal robust enough to drive the tiering (predicted-starter / Most Likely Arms already exists — `FEATURE_PREDICTED_STARTER`).

## Dependencies & Blockers
- [ ] E-266 (Outings Breakdown disclosure/print fix) ships — this refines its print path
- [ ] A reliable probable-starter / role signal to decide which pitchers get the full log vs. season-line-only (the Most Likely Arms / predicted-starter machinery is a candidate source)

## Open Questions
- What role signal drives the tier — the existing predicted-starter flag, season GS count, or a coach-set list?
- Does the tiering apply to print ONLY (screen keeps the uniform collapse/expand), or to both?
- How to handle a staff with no clear starter signal (fall back to uniform, or IP-threshold)?

## Notes
Raised during E-266 planning (2026-07-17) by baseball-coach as a non-blocking backlog observation on the print force-open. Related: E-266 (parent), E-265 (Pitcher Outings Breakdown), `FEATURE_PREDICTED_STARTER` / Most Likely Arms, `.claude/agent-memory/baseball-coach/pitcher-outings-scouting-consultation.md` (artifact-shape tiering), IDEA-144 (template split).

---
Created: 2026-07-17
Last reviewed: 2026-07-17
Review by: 2026-10-15
