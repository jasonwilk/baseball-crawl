---
name: e236-integrity-hardening-review
description: E-236 coaching consultation outcomes — no_games copy, Option A confirm, partial-stage scope, SQ1 hard failure, 403/404 reconciliation
metadata:
  type: project
---

## E-236 Report Integrity Hardening (2026-06-14 to 2026-06-15)

Epic E-236 (Report Self-Reporting Integrity Hardening, ROADMAP slice B2). Coach consulted during planning and performed holistic review of story 05 (no_games copy), story 06 (Option A), story 07 (admin-only partial-stage), and the SQ1/SQ1-refinement product decisions.

### C1 — no_games Two-Case Copy (Authoritative)

Footer copy for the no_games page:
- **M=0** (no games played yet): `"No games on record for {team_name} this season."`
  - "No games on record" avoids implying the system would know if they played
- **M>0, N=0** (games played, no scorebook): `"{team_name} has played {M} games this season, but no box score data is available in GameChanger."`
  - Interpolates **M** (games actually played), NOT N (which is 0 here)
  - Names "GameChanger" so the coach knows the limitation is source-specific — they can look elsewhere
  - Confirms the team is game-tested (coaching-relevant distinction from M=0)
- **Negative AC**: copy MUST NOT say "check back later" — at pre-game, later is irrelevant

### C2 — Option A Confirmed (season_fallback drop)

Season_fallback contribution dropped from coach-visible degraded line. `degraded_confidence = bool(self.identity_match_method == "name_only")` only.
- No coaching regret — a coach can act on *whether* data may be limited, not *why*
- The generic "Data accuracy may be limited. Contact your operator." line covers the coaching need
- `report_generation_runs.season_fallback` stays as operator-only telemetry
- Holds for E-236 (confirmed 2026-06-15, same rationale as 2026-06-14 original ruling)

### C3 — Partial-Stage Degradation: Operator-Only

Partial-stage degradation (#1 plays, #2 boxscore, #3 spray) is strictly operator telemetry — never surfaces on the coach footer.
- The coach footer already carries the coaching-relevant signal through game counts: "Pitch detail for K of N games" and "N of M games"
- Whether the gap is pipeline artifact or genuine absence, the coaching response is identical
- Coach footer signals = game counts (N of M, K of N) + spray line + degraded_confidence (name-only only)
- Partial-stage derived "operator-degraded" flag is admin-view-only

### SQ1 — All-Boxscores-Blocked = Hard Failure (No Coach Page)

When M>0 but games_crawled==0 (every boxscore fetch failed): hard `failed` outcome.
- No shareable page; CLI non-zero exit; operator gets alert
- Rationale: "we were blocked" is operator-actionable (re-auth); must not masquerade as "no data exists"
- Coach sees nothing; operator gets the signal

### SQ1 Refinement — 403/404 Distinction Not Needed

Initial concern (2026-06-15): 404 (no scorebook ever created) should route to no_games, not failed, to avoid false operator alerts on everyday no-scorebook opponents (alarm fatigue — same harm class as the season_fallback false alarm).

**Resolved by api-scout live data:** The M=0 filter already handles this. GC's `game_status=="completed"` is the "scorebook exists" marker. No-scorebook opponents produce zero completed games → M=0 → no_games path already. They never reach the failed gate.

The failed gate's only real-world trigger is M>0 with games_crawled==0 (auth-expiry or transient mass failure) — genuinely fixable by operator. No 403/404 build needed. Document as known limitation if GC data inconsistency ever produces M>0 + all-404 on completed games (not observed in 72/72 real opponent fetches).

### Holistic Review Gap Found

**K=0 copy ownership**: Story 08 AC-4 asserts "No pitch-detail data" when K==0, but no E-236 story explicitly owns implementing this copy in the renderer/template. E-235 left this "to implementer judgment." PM verified/resolved before READY (either E-235 implemented it, or story 05 received a one-line AC addition — story 05 is the logical home since it already touches renderer.py).

### Key Field Insight Logged

No-scorebook opponents are the everyday scouting case at HS level — any team whose coach doesn't keep a GC scorebook (common). They produce M=0, not all-404-with-M>0. In live data: 72/72 real completed-game boxscores returned 200-with-data; 403 never occurs on public boxscore reads (not ownership-gated). The all-blocked→failed path is strictly auth-expiry territory.
