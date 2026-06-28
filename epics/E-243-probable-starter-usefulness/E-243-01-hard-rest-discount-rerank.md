# E-243-01: Hard rest-discount re-rank tiebreaker

## Epic
[E-243: Make the Probable-Starter Analysis Useful on Game Morning](epic.md)

## Status
`TODO`

## Description
After this story, the deterministic engine ranks a fully-available starter ahead of a still-tired (preferred-rest-window) one. A hard re-rank partitions the engine's already-ranked starter candidates into fully-available vs. discounted-by-rest groups and orders all available arms ahead of all discounted arms, preserving the engine's relative order within each group. This directly addresses the user's complaint that the report sometimes recommends a tired arm over a fresh one.

## Context
The backtest found the engine ranks a tired arm #1 in 22% of games and is only 8.9% right there. A hard rest-discount tiebreaker was validated to move aggregate top-1 from 20.2% to 24.9% and the tired-arm subset from 8.9% to 30.4% (22 wins vs 5 breaks). Soft/graduated penalties did nothing — the hard variant is required. The engine currently implements only the hard exclusion gate (UNAVAILABLE); the "available-but-discounted" tier does not exist in code yet and is introduced here. This is the first of three stories that modify `starter_prediction.py` (see epic TN-7); E-243-03's per-candidate eligibility display consumes the discounted-tier computation introduced here.

## Acceptance Criteria
- [ ] **AC-1**: Given a candidate set where the engine's #1-ranked starter is inside its preferred-rest window (cleared the hard gate but `days_rest < preferred`) and a lower-ranked starter is fully available, when the prediction is computed, then the fully-available starter is ranked first in `top_candidates` (per Technical Notes TN-1).
- [ ] **AC-2**: Given a candidate set where all remaining starters share the same rest state (all available, or all discounted), when the prediction is computed, then their relative order is unchanged from the engine's pre-rerank order (stable partition).
- [ ] **AC-3**: The preferred-rest thresholds are exactly: ≤30 pitches → 2 days, 31-60 → 4 days, 61+ → 5 days, computed from the summed pitch count of the candidate's most recent game day (doubleheader aggregation per Technical Notes TN-1).
- [ ] **AC-4**: Given a candidate whose most-recent-day pitch count is unavailable (null), when rest state is determined, then the **IP proxy** is applied (≤2 IP → 0-30 bucket, 3-4 IP → 31-60, 5+ IP → 61+), the result is flagged as an estimate, and the candidate is treated as DISCOUNTED if the proxied bucket maps to a non-zero preferred-rest requirement (per Technical Notes TN-1). Null is NOT treated as fully-available — the conservative-when-uncertain principle holds, especially because the null path goes live exactly for youth/travel where pitch tracking is least reliable (baseball-coach M1 ruling).
- [ ] **AC-5**: The re-rank operates only on candidates that already cleared the hard exclusion gate; no candidate is added to or removed from the candidate pool by this story (only ordering changes). The partition runs over the **post-truncation** final candidate list (the same arms the engine already surfaces), per Technical Notes TN-1 — it never pulls a fresh arm in from below the truncation cut.
- [ ] **AC-6**: The re-rank is applied **in place** so the engine's named `predicted_starter`/`alternative` selection and the Tier-2 LLM both consume the re-ranked order (not a display-only copy), per Technical Notes TN-1.
- [ ] **AC-7**: Each candidate dict carries its attached rest-state — `days_rest`, `last_outing_pitches`, and `rest_eligibility` (`available` or `discounted`) — so E-243-03 reads it directly instead of recomputing (per Technical Notes TN-1; the per-line eligibility on ranked arms is two-valued, available/discounted only — hard-excluded arms are handled separately by E-243-03's `unavailable_arms`).
- [ ] **AC-8**: A deterministic unit test asserts the resulting `top_candidates` order, pinning these cases (per Technical Notes TN-2 — the backtest harness is provenance, not the regression gate): (i) anti-soft-regression — a discounted #1 at likelihood 1.0 vs an available #2 at 0.3 → the available arm becomes #1 (proves hard partition, not a graduated penalty); (ii) tired-#1-with-rested-alternative win case; (iii) all-discounted and all-available sets → order unchanged in both directions (stability); (iv) threshold boundaries — `days_rest == preferred` is AVAILABLE (`>=`), and pitch-band edges 30/31 and 60/61 (60 → 4-day bucket, 61 → 5-day); (v) IP-proxy on a null pitch count: null pitches + 5 IP → 61+ bucket → preferred 5 → DISCOUNTED (not available); (vi) doubleheader 20+20=40 → 31-60 band → preferred 4. The available-before-discounted stable-partition semantics match the `rerank_hard` function in `.project/research/starter_backtest_rerank.py`; the null-pitch handling **intentionally diverges** from that throwaway harness's `rest_state` (which treated null as available) per the baseball-coach M1 ruling — the harness is provenance, not the contract.
- [ ] **AC-9**: No regression in existing `tests/test_starter_prediction.py`; any existing assertion that encodes the pre-rerank ordering or the confidence-tier interaction is updated to the new contract (treated as a stale-test update, not a regression, per `.claude/rules/testing.md`).

## Technical Approach
Introduce the preferred-rest-window ("discounted") computation described in Technical Notes TN-1/TN-3 and apply it as a stable partition **in place** over the engine's already-ranked, already-truncated candidate list — after candidates are built and cut to the top N, and **before** the confidence-tier block that selects `predicted_starter`/`alternative` — so the named pick and the Tier-2 LLM both consume the re-ranked order. Partitioning post-truncation (not over the full pre-truncation pool) is what reproduces the validated +17-net numbers; pulling a fresh arm in from below the cut would diverge from `rerank_hard`. Also attach each candidate's rest-state (`days_rest`, `last_outing_pitches`, `rest_eligibility`) onto the candidate dict for E-243-03 to consume. The rest-state computation parallels the existing pitch-count/doubleheader aggregation already present in `_is_excluded`. The shape of any helper is the implementer's choice; keep the change additive and confined to ordering + the attached fields. Reference `.project/research/starter_backtest_rerank.py` for the validated partition semantics and `.claude/agent-memory/baseball-coach/probable-starter-model.md` (two-tier availability model, preferred-rest thresholds) for the domain model.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-243-02, E-243-03

## Files to Create or Modify
- `src/reports/starter_prediction.py`
- `tests/test_starter_prediction.py`

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-243-03**: the per-candidate attached rest-state (`days_rest`, `last_outing_pitches`, `rest_eligibility` = available/discounted) on each candidate dict, which E-243-03 reads directly for the per-arm display instead of recomputing.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
The discounted tier is a *re-rank only* — it must never promote a candidate above the hard exclusion gate or resurrect an excluded arm. Excluded (UNAVAILABLE) arms remain excluded.

**M1 (RESOLVED — null pitch count).** baseball-coach ruled (option b): keep the IP proxy (≤2 IP → 0-30 bucket, 3-4 IP → 31-60, 5+ IP → 61+); a null pitch count is NOT treated as fully-available. Reasoning: null→available would invert the conservative-when-uncertain safety principle, and the null path goes live exactly for youth/travel where pitch tracking is least reliable. AC-4 and AC-8 now encode this, and the model doc's L87 IP-proxy language (correct) stays — E-243-05 AC-6 confirms doc and code agree.
