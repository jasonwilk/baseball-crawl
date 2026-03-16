# IDEA-029: L/R Split Data Population

## Status
`CANDIDATE`

## Summary
Populate the nullable vs-LHP/RHP (batting) / vs-LHB/RHB (pitching) split columns on player_season_batting and player_season_pitching tables. E-100 created the columns; this idea covers data source identification, population logic, and likely a manual entry path for handedness data that GameChanger may not provide. Home/away splits are deprioritized per coach consultation.

## Why It Matters
L/R splits remain the highest-value pre-aggregated split for coaching decisions: knowing how a batter performs against left-handed vs. right-handed pitchers directly informs lineup construction. However, the data sourcing challenge is significant — handedness data likely requires operator input rather than pure API ingestion.

**Coach priority assessment (2026-03-16):** L/R splits are high-value but blocked by handedness data. Home/away splits have LOW coaching value at HS/youth level (no real home field advantage, small samples = statistical noise). The 20 home/away split columns should be kept as insurance but NOT prioritized for population or display. The most valuable "splits" for HS coaches are actually query-time computations over per-game data (recent form, season phase) — see IDEA-038.

## Rough Timing
Low urgency until handedness data is resolved. Promote when:
- api-scout has confirmed what handedness data GC provides (or confirmed it's absent)
- If manual entry is needed: admin UI can support player attribute editing
- E-117 (base stat population) has shipped
- Coaching dashboard needs L/R split views for scouting reports

## Dependencies & Blockers
- [ ] E-117 (base stat population) — splits build on top of populated base stats
- [ ] **api-scout investigation**: Confirm what handedness data GC actually returns across all endpoints (roster, season-stats, per-player stats). User doubts most teams enter bats/throws in GameChanger — this data may be sparse or absent for most players.
- [ ] If GC doesn't provide handedness reliably: need a manual entry path (admin UI for operator to enter bats/throws "as we watch games") before L/R splits can be computed
- [ ] Determine data source for split computation: does the season-stats API return pre-computed splits, or must splits be computed from per-game data with pitcher handedness metadata?

## Open Questions
- **Critical: Does GC reliably provide bats/throws?** User suspects most teams don't enter handedness in GameChanger. If the field is empty/null for most players, API-sourced handedness is unreliable. This fundamentally changes the scope: from "map API fields" to "build a manual entry path + API hybrid."
- Does the season-stats endpoint return pre-computed L/R split data? If so, this is straightforward field mapping regardless of handedness.
- How do we get opposing pitcher handedness for historical games? This may require the plays endpoint, per-player stats endpoint, or manual operator entry.
- If manual entry is needed, what's the UX? Per-player edit page? Bulk import? Scouting notes during games?
- **Small sample warning (coach requirement):** Any sub-split must be flagged as small sample. HS seasons are 80-100 PA; sub-splits have 20-40 PA. The dashboard must communicate this clearly to coaches.

## Notes
- E-100 Non-Goal: "L/R split data population: Schema supports nullable split columns; population is follow-up."
- 10 L/R split columns on player_season_batting (vs_lhp_*, vs_rhp_*), 10 on player_season_pitching (vs_lhb_*, vs_rhb_*).
- 10 home/away split columns on each table — **deprioritized** per coach consultation (low value at HS/youth level). Keep columns as insurance, do not prioritize population.
- **Coach insight (2026-03-16):** The most valuable "splits" for HS coaching are query-time computations over per-game data (recent form last 5-7 games, season phase, doubleheader fatigue). These don't need pre-aggregated columns — they need E-117's per-game stat population. See IDEA-038.
- **User insight (2026-03-16)**: Player handedness (bats/throws) may not be populated by most teams in GameChanger. The operator may need to enter this data manually based on observation during games.
- Related: IDEA-038 (Query-Time Splits and Streaks) covers the higher-priority coaching splits that don't need handedness data.

---
Created: 2026-03-16
Last reviewed: 2026-03-16
Review by: 2026-06-14
