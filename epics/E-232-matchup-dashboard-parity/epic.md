# E-232: Matchup dashboard parity

## Status
`DRAFT`

## Overview
After E-228 v1 ships and validates that the matchup engine produces value, this epic surfaces a lighter matchup variant on the opponent dashboard (in addition to the standalone scouting report where v1 lives). The standalone report's `MatchupAnalysis` dataclass is the consumable artifact; the dashboard renders a simplified version inline on the existing opponent detail page.

## Background & Context
claude-architect noted in E-228 discovery (2026-04-27) that a lighter matchup variant should appear on the opponent dashboard, not just the standalone report. v1 of the matchup engine produces a `MatchupAnalysis` dataclass that the dashboard could consume; v2 surfaces it.

This follows the precedent established by E-212 predicted-starter, which shipped on BOTH the standalone report (with optional Tier 2 LLM enrichment) AND the dashboard (Tier 1 deterministic only -- LLM latency unacceptable on a live page load).

**Discovery decisions locked (from architect's E-228 note, 2026-04-27):**
- "Lighter version" implies fewer sub-sections, no LLM Tier 2 (deterministic only), inline on the existing opponent dashboard.
- Latency constraint: a 30s LLM call is unacceptable for a live page load. Dashboard MUST use Tier 1 only (mirroring E-212 predicted-starter dashboard treatment).

**Promotion trigger**: After E-228 v1 ships AND validates that the engine produces value AND coach asks "can I see this on the dashboard too?"

## Goals
- The opponent dashboard (`/dashboard/opponents/{opponent_team_id}`) shows a lighter matchup variant that uses the same `MatchupAnalysis` dataclass as the standalone report.
- Dashboard latency stays under the existing page-load budget (no LLM call).
- The shared `compute_matchup()` engine is used by both surfaces (no duplicate logic).
- The print variant of the dashboard (`/dashboard/opponents/{opponent_team_id}/print`) includes the lighter matchup variant.

## Non-Goals
- LLM Tier 2 enrichment on the dashboard (latency constraint, permanent).
- A separate dashboard-only matchup engine (the v1 engine is reused).
- Major redesign of the existing opponent dashboard layout (only the new section is in scope).
- Re-introducing v1-cut content on the dashboard (head-to-head, lineup card, three-gate starter prediction) -- those are out of v1 entirely.

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| | To be written during planning | | | |

## Dispatch Team
- ux-designer (consulting)
- software-engineer

## Technical Notes

### Engine Reuse
The dashboard route handler calls the same `build_matchup_inputs()` + `compute_matchup()` from `src/reports/matchup.py` that the standalone report calls. Inputs scoped to the dashboard's "us team" context (see Open Question 2 below). Output is the `MatchupAnalysis` dataclass; the dashboard template renders a simplified subset.

### Latency Budget
Dashboard page-load budget for the existing opponent detail page is documented in repo conventions (or implicit -- planning may need to measure). The matchup section's added latency is dominated by the input builder's DB queries; the engine itself is sub-millisecond. If the input builder's latency is unacceptable, planning must decide caching or lazy-loading strategies.

### Subset Selection
"Lighter version" -- which sub-sections survive on the dashboard? Architect's note suggests fewer. Planning decides per-sub-section:
- Top-3 dangerous hitters (with cue) -- LIKELY YES.
- Pull-tendency notes -- LIKELY YES (small, useful).
- Stolen-base profile -- LIKELY YES.
- First-inning pattern -- MAYBE.
- 3-bucket loss recipe -- MAYBE (deterministic counts only; LLM prose absent).
- Eligible opposing pitchers -- LIKELY YES (already on the dashboard separately as the existing pitching section).
- Eligible LSB pitchers -- DEPENDS on dashboard's "us team" context (see Open Question 2).

### "Us Team" Context on the Dashboard
The standalone report's `our_team_id` comes from a checkbox + dropdown. The dashboard has no such picker today. Options for v2 planning:
- **Option A**: Add a "us team" picker to the dashboard.
- **Option B**: Auto-resolve from `team_opponents` -- if exactly one member team has played the opponent, use it; if multiple, default to a documented heuristic (most recent matchup? user preference?).
- **Option C**: Show only opponent-side content on the dashboard (no LSB context, no eligible LSB pitchers, no LSB-aware sub-sections).

Planning chooses one and documents the rationale.

## Open Questions
1. **Which sub-sections survive on the dashboard?** Subset Selection above lists candidates; planning + UX consultation finalizes.
2. **How is "us team" context resolved on the dashboard?** Three options above; planning decides.
3. **How to scope the dashboard refresh boundary** -- live computation vs. cached? Live is simpler but adds latency; cached requires invalidation logic. Planning decides.
4. **Order vs. E-230 and E-231**: does dashboard parity ship before, after, or interleaved with engine v2 + visual polish? Planning decides based on coach feedback priority after v1 ships.
5. **Multi-LSB-team head-to-head ambiguity** (from E-228 v1 Open Question 1): when an opponent appears under multiple member teams' `team_opponents` rows, the dashboard auto-resolution (Option B above) needs a tiebreaker. Resurfaces here.

## Promotion Triggers
This epic is gated on coach feedback after v1 ships:
1. **E-228 v1 has shipped** (status COMPLETED, archived).
2. **Coach has used the standalone matchup report** in real game-prep workflow.
3. **Coach asks for the matchup content on the dashboard** -- explicit ask, not assumed need. If the standalone report is sufficient (e.g., coach generates one report per game-prep session and the dashboard remains the in-season scouting browser), the dashboard variant may be unnecessary and the epic could be DEFERRED or DISCARDED.

## History
- 2026-04-28: Created as DRAFT stub during E-228 v1 refinement. Discovery context preserved from E-228 planning sessions (2026-04-27 -- claude-architect dashboard-parity note in original Non-Goals). Originally listed as a Non-Goal in E-228 v1 ("dashboard parity (lighter matchup version on opponent dashboard) -- captured as follow-on idea per architect's recommendation"); promoted to its own epic because the dataclass artifact (`MatchupAnalysis`) and engine (`compute_matchup`) become consumable after v1 ships, making the dashboard wire-up a clean follow-on rather than a v1 scope expansion.
