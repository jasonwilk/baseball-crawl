---
name: health-gate-prior-set-must-be-temporal
description: A "same population on both sides" ratio-gate invariant is satisfiable by a polluted set; the load-bearing clause is WHEN the prior set was captured. Plus - an absolute cap masking a broken ratio gate is not evidence the gate works.
metadata:
  type: project
---

Any gate that compares a FRESH payload against a PRIOR DB set (`comparable = prior & fresh` over `prior`) must specify **when `prior` was captured**, not just that both sides come from the same set. Stating only "same population on both sides of the ratio" is insufficient: a `prior` read AFTER the same run's upsert satisfies that invariant while the gate degrades to `|fresh| >= |stale|`, which is not a health gate at all.

**Why:** discovered across all three grains of `src/db/reconcile_at_load.py` during E-276 planning (2026-07-25). The module docstring asserted the same-population invariant, and the invariant was TRUE of the broken code — both sides were drawn from the polluted set. That is why it survived four review layers and a Codex pass. A correct-sounding invariant that the defect satisfies is worse than no invariant, because it terminates review.

**How to apply:**

1. When designing or reviewing a retire/reconcile/parity gate, ask *when* the prior set is read, not just what it is intersected with. Required wording: "as of the start of this load, captured BEFORE any of this run's writes to that grain's delete scope."
2. Make the capture the CALLER's job — pass `prior_ids` as a required parameter rather than letting the helper read the DB at call time. Ordering couplings enforced by comment keep failing here (three long E-270-05 coupling comments in one module); a required parameter makes it structural. Same reasoning as the evidence-parameter rule in `.claude/rules/python-style.md`.
3. The anchor is set by the grain's DELETE-SCOPE KEY, not by run-vs-item preference. Per-item scope (player-line, keyed on canonical `game_id`) forces a per-item capture — a whole-run pre-capture is not even implementable there, because the canonical id does not exist until `_find_duplicate_game` rebinds it mid-loop.
4. Test discrimination: a test that seeds prior rows by direct INSERT and calls the retire helper DIRECTLY passes identically before and after the fix. Only a two-run test through the real loader discriminates. The original E-267 audit probe made exactly this mistake on the roster grain and wrongly cleared it.

**A cap is not evidence the gate under it works.** The roster grain's `MAX_ROSTER_DEPARTURES` masked its broken ratio gate rather than protecting it: the windows overlap (divergence needs `prior_pre < 2 x absent`, the cap binds at `absent <= 2`, so any roster of <=3 pre-load rows losing 2 sits in the intersection — demonstrated by execution, 2 live rows hard-deleted). When auditing a guarded destructive path, evaluate each guard against inputs where the OTHER guards permit; a guard whose only protection is a second, tunable guard is not a guard.

**Where E-276 actually landed (corrected — an earlier version of this note recorded an outcome the same session overturned):** the corrected snapshot-population gate applies to the **game and player-line** grains only. The **roster grain gets NO floor ratio at all** — `permit = (fresh payload non-empty) AND (|absent ∩ previously| <= MAX_ROSTER_DEPARTURES)`. A `legacy AND corrected` conjunction was adopted mid-session and later dropped as inert: `corrected ⟹ legacy` wherever everything the run writes comes from the fresh payload, and the roster grain ended with no floor for either conjunct to gate.

**Why the roster grain is exempt — the reasoning, because the conclusion does not travel.** `team_rosters` is fully re-derivable from the roster crawl plus the jersey backfill, so a wrong delete self-heals while a wrong refusal compounds; the operator ruled prefer-deleting on that basis. **Do NOT port this to `player_game_*`** — a deleted stat row is gone, is not re-derivable without re-fetching the boxscore, feeds season aggregates directly, and that grain has no cap.

**Any floor over a capped population is inert above a small roster.** With `cap = 2`, a floor can only refuse-where-the-cap-permits when `survivors < absent <= 2`, forcing a stored roster of <= 3. The cap therefore binds first at every realistic size — which is why removing the roster floor changed nothing above three rows, and why the inertness is CONTINGENT on the cap's value (`stored <= 2*cap - 1`).

**`MAX_ROSTER_DEPARTURES` now sets a RATE, not a bound.** It caps pre-existing loss per retire invocation; cumulative exposure is unbounded in the number of invocations. Executed: a gently degrading crawl (11,9,7,5,3,1) empties 12 of a 13-row roster two at a time with the cap permitting every step, while a catastrophic drop to 1 loses nothing because the cap refuses. **The protection runs backwards with respect to severity** — and that is an accepted limit rather than a defect, because a real roster shedding two players a week is byte-identical to a slowly decaying crawl at every step.

**Two failure shapes from that session, worth keeping distinct:**

- *Authorship*: a true-sounding absolute asserted across grains without construction-testing it. Detector — **any claim phrased as an absolute about deletions gets a counterexample attempt before it ships**, not a re-read of the argument.
- *Quantified*: **a sweep count carries its bounds — state the characterization, not the number.** I reported "222 diverging shapes" as a fact about the code; the same criteria give 15 / 26 / 100 / 222 as the sweep range moves 0..3 / 0..4 / 0..8 / 0..12. The bound-free answer was 3 shapes, derived from the constraints (the cap forces `b <= 2`, the gate refuses only when `a < b`, so `prior_pre <= 3`) — smaller, complete, and unattackable, where the count was inflated and range-dependent. A colleague's independently-bounded sweep collapsed to the identical 3 shapes. Applies to every parameter sweep: **the count is correct and the frame is yours; say the frame or drop the count.**
- *Verification*: **verification that does not include the claim's baseline or scope is not verification.** I re-derived a colleague's cost-table arithmetic and missed that it was measured against the wrong baseline; the computation was right and the frame was the defect, and the frame was the claim. Notably, the only baseline error caught that day was caught by its own author re-measuring — reviewing someone else's claim is where the frame goes unexamined, because the claim arrives already framed.

Related: [[games_row_vs_stat_rows_coupling]], [[schema_drop_test_blast_radius]], [[scouting_query_role_vs_dedup_filters]].
