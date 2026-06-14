# IDEA-077: Re-evaluate the season_fallback Trust Flag (and Season Scoping) in the Report-Only Direction

## Status
`CANDIDATE` — **direction DECIDED (coach-authoritative, 2026-06-14): Option A.** Status stays
CANDIDATE because the implementation has not been scheduled, but the *what* is settled: drop
the coach-visible `season_fallback` degraded-confidence line; keep the column as operator-only
telemetry. The implementation is a small follow-up — fold into Epic D or a small dedicated
epic. Option B (blend-detector) is REJECTED — do not revive.

## Decision (2026-06-14, baseball-coach, authoritative)
**Option A chosen, decisively.** Coach verdict: a single GameChanger `public_id` does NOT blend
multiple programs/levels within a calendar year in the real world — one GC team entity = one
continuous program; HS spring vs. summer legion are separate teams with separate public_ids;
travel orgs register each squad separately. Therefore year-only scoping is essentially always
correct, and the `season_fallback` trigger (`no program_type`) has **zero correlation with real
data-quality problems** — it fires on the cleanest data (the 48/48 travel report) and would NOT
fire on genuinely dirty data. The coach-visible "⚠️ Data accuracy may be limited" line is noise
that is actively harmful: it erodes pre-game trust, generates unresolvable operator pings, and
costs the coach's pre-game cognitive budget. **Option B (a real blend-detector) was explicitly
rejected**: "solves a problem that does not exist in the field — engineering effort for zero
coaching value."

**Resolution to encode:**
- DROP the coach-visible `season_fallback` contribution to the footer degraded-confidence line.
  Precise code implication (for whoever implements later): `degraded_confidence` should drop the
  `season_fallback` term and keep ONLY `identity_match_method == 'name_only'`; coverage severity
  stays its own separate N/M signal.
- KEEP the `report_generation_runs.season_fallback` column as operator-only run-record telemetry
  (it still shows in the `/admin/reports` list — that's fine; it just shouldn't drive anything
  coach-visible).

## Summary
E-235 added a `season_fallback` operator trust flag that drives a coach-visible "Data accuracy may be limited" degraded-confidence line whenever `derive_season_id_for_team()` resolves a season via fallback (program_type missing → year-only season id, or season_year missing → current-year). Because nearly every travel/USSSA team lacks `program_type` in GameChanger, this flag fires on essentially every travel-team report -- even with a perfect identity match and full data coverage. Re-evaluate whether year-only season scoping should be treated as "degraded" at all in the reports-first frame, where season_id matters far less.

## Why It Matters
- **Alarm fatigue makes the flag worse than nothing.** Real-world observation (dev, 2026-06-14): generating a report for "MBA Top Dogg Gold 14U" (a 14U travel team, public_id `dD9PtF0YbKad`) fired `season_fallback=1` with `season_id_used="2026"` (bare year-only), DESPITE an anchor identity match and 48/48 (N==M) full data coverage. The fallback fired purely because travel/USSSA teams have no `program_type`. If the operator sees this warning on every travel-team report, they will learn to ignore it -- and then it provides no signal when something is genuinely wrong.
- **For a single-season travel team, year-only IS the correct, complete scope** -- not a degraded condition. The flag currently conflates "we used a fallback code path" with "the data is less trustworthy," and those are not the same thing.
- **Season precision matters much less in the reports-first frame.** Per `docs/ROADMAP.md` (reports-first reframe, 2026-06-12), multi-season rollups, longitudinal tracking, and cross-team identity are explicit NON-GOALS. `season_id` was the load-bearing partition key for exactly those use cases. In report-only mode, `season_id` is mostly a within-report game filter, so precise season labeling carries little coaching value.
- **The one residual real risk is narrow:** a single `public_id` that blends distinct programs within one calendar year (e.g., spring-HS + summer legion under one team entity) -- year-only scoping would then blend different rosters/levels into one report. But you scout an opponent by their specific `public_id`, usually one program, so the blending risk is narrow. The current flag does NOT detect this risk; it uses "program_type missing" as a coarse proxy that fires far too broadly.

## Rough Timing
- Not urgent. Capture as CANDIDATE.
- Trigger to promote: operator confirms alarm fatigue is real in practice (the flag is firing on most travel-team reports and being ignored), OR a coach + product decision confirms cross-program blending does/does not occur for the teams LSB actually scouts.
- Worth pairing with the next reports-flow refinement pass.

## Dependencies & Blockers
- [x] Coach + product call: "Does cross-program blending actually occur for the teams LSB scouts?" — **RESOLVED 2026-06-14 (baseball-coach): NO. A single `public_id` does not blend programs within a calendar year. Option A wins; flag is pure noise on the coach-visible line.**
- [ ] No code blocker -- this builds directly on E-235's `report_generation_runs.season_fallback` column and the coach-footer degraded-confidence line.

## Open Questions
*(All resolved by the 2026-06-14 coach decision — see the Decision section.)*
- ~~Should the coach-visible degraded-confidence line drop the `season_fallback` trigger entirely, or only the year-only sub-case?~~ → **Drop it entirely from the coach-visible line** (keep ONLY `identity_match_method == 'name_only'`).
- ~~Is "program_type missing" ever a meaningful trust signal in report-only mode?~~ → **No — it is purely an artifact of how travel teams are represented in GameChanger; zero correlation with data quality.**
- ~~If we want to flag the real risk (cross-program blending within one report), how do we detect it?~~ → **We don't — the risk does not exist in the field; a blend-detector (Option B) was rejected as zero coaching value.**

## Notes
**Candidate directions (now DECIDED — Option A; see the Decision section):**
- **Option A (CHOSEN, 2026-06-14, coach-authoritative):** Stop treating year-only as degraded -- drop `season_fallback` from the coach-visible degraded-confidence signal entirely, since year-only is the expected scope for a shared single-team report in report-only mode.
- **Option B (REJECTED — do not revive):** A real blend-detector (flag only when a report's games span more than one program / age-level / season-window) was considered and rejected: it "solves a problem that does not exist in the field — engineering effort for zero coaching value."
- **Either way (KEPT):** Keep the `report_generation_runs.season_fallback` column as cheap operator telemetry. The decision is specifically that it should NOT drive the COACH-visible degraded-confidence line, only operator-visible telemetry.

**Cross-references:**
- E-235 (Report Run Records, Trust Signals & Quality Gates) -- introduced the `season_fallback` flag, the `report_generation_runs` column, and the coach-footer degraded-confidence line. Archived at `.project/archive/E-235-report-run-records/`.
- `docs/ROADMAP.md` -- reports-first reframe (2026-06-12): multi-season rollups, longitudinal tracking, and cross-team identity are explicit non-goals; this is why season scoping matters less.
- A matching vision signal was logged in `docs/vision-signals.md` dated 2026-06-14 (season scoping matters less in report-only mode).
- Related: IDEA-061 (Derive season_id from Team Context) -- PROMOTED to E-197; IDEA-066 (League/Level Detection) -- PROMOTED to E-218.

---
Created: 2026-06-14
Last reviewed: 2026-06-14 (direction decided — Option A, baseball-coach authoritative)
Review by: 2026-09-12 (90 days from created)
