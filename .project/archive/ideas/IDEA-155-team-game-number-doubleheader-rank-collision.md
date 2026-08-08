# IDEA-155: `team_game_number` DENSE_RANK Has No Tiebreak — a doubleheader collapses to one game number

## Status
`CANDIDATE`
<!-- Pre-existing defect in current main, surfaced incidentally by data-engineer during the E-267-02
     doubleheader check (2026-07-19). NOT introduced by E-267 and outside its scope — filed rather
     than fixed because no E-267 story modifies this query. -->

## Summary
`team_game_number` in `src/api/db.py:298-300` is:

```sql
DENSE_RANK() OVER (
    ORDER BY g.game_date ASC, g.start_time ASC NULLS LAST
) AS team_game_number
```

There is **no `game_id` tiebreak**. Two games sharing a `game_date` with equal or NULL `start_time` therefore receive the SAME rank, so a real doubleheader collapses to a single game number instead of occupying two. Verified verbatim against the file on 2026-07-19 (not inferred from the report).

## Why It Matters
- **Doubleheaders are normal in HS ball** (baseball-coach), so this is a LIVE defect, not a theoretical one.
- `team_game_number` feeds **rotation-cycle detection**. A collapsed rank distorts where in the cycle a pitcher sits.
- **NOT a safety issue** — it does not feed rest-day or pitch-count math. `rest_days` is computed by the separate `LAG(g.game_date)` window immediately above it (lines 292-296), which is unaffected by the DENSE_RANK tiebreak gap.

## Scope Note
Small and self-contained: a tiebreak added to the window's ORDER BY. The care needed is in choosing a tiebreak that is STABLE across runs (a `game_id` tiebreak is deterministic; anything derived from insertion order is not), and in checking whether any caller depends on the current collapsing behavior before changing it.

## Notes
- Found incidentally while DE was checking whether a same-date collision could UNDERCOUNT pitcher appearances for [[IDEA-154]]. That question resolved NO (no `DISTINCT` anywhere in `src/api/db.py`, every `GROUP BY` is on a player key, `LAG` operates over rows — per-row across the board). This ranking defect is a separate finding from that same read.
- Filed rather than fixed: outside E-267's scope, and no story in that epic touches this query. It should not evaporate just because it was found in passing.

---
Created: 2026-07-19
Last reviewed: 2026-07-19
Review by: 2026-10-17
