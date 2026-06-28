# Scouting-Coverage Lever — Quantified Gap & Disposition Recommendation

**Type:** Standalone research memo (read-only analysis; no `src/`, DB, or production changes).
**Provenance:** Originated from the E-243 probable-starter design work. Pulled out of that dispatched epic (was E-243-06) to be written now against the main checkout, where `data/app.db` and the backtest harnesses live. The backtest that produced these numbers is documented in `.project/research/starter_backtest.py` and `.project/research/starter_backtest_rerank.py` (throwaway spikes that import the real `src/reports/starter_prediction.py` engine).
**Date:** 2026-06-28
**Author:** data-engineer

---

## 1. The question

The E-243 backtest established that the probable-starter engine's *ranking logic is sound* (it beats naive baselines 2-3x) but its absolute accuracy is modest (top-1 ~20%, top-2 ~40% pooled over 357 labeled games / 17 real opponent seasons). This memo answers: **how much of that modest accuracy is a coverage problem — incomplete opponent game history — versus an algorithm problem, and is it worth building fuller opponent-season ingestion to fix it?**

## 2. The coverage metric: novel-starter rate

We do **not** have an independent record of each opponent's full season schedule. The dev DB contains only the games we ingested: a per-team check shows the count of all games referencing each team (any status) equals the count of games we have pitching data for, within 0-2 games for every one of the 17 teams. So there is no internal "games-played" denominator to divide "games-covered" by, and the brief correctly scoped external full-schedule fetching as best-effort-where-cached only (it is **not** cached — confirmed).

The right internal proxy is the **novel-starter rate**: the share of scored games whose actual starting pitcher had **zero prior starts in the history we hold as-of that game**. A novel starter is, by definition, a pitcher the engine has never seen start — so it *cannot* rank them, and neither can any baseline. Every novel-starter game is an automatic miss for everyone. The novel rate is therefore a direct, lower-bound estimate of how much of our miss rate is caused by missing history rather than by a weak model.

### Per-team coverage table

| team_id | name | games w/ data | scored games | novel-starter % |
|---|---|---|---|---|
| 160 | LSB Varsity (own, fully charted) | 30 | 26 | **7.7%** |
| 186 | Braxter Construction | 24 | 20 | 10.0% |
| 189 | Papio Post 32 Reserves | 20 | 16 | 12.5% |
| 290 | Gretna 216 Seniors | 24 | 20 | 15.0% |
| 114 | Five Star Bath | 23 | 19 | 15.8% |
| 227 | Cornhusker JV (2024) | 47 | 43 | 16.3% |
| 202 | Griffs 216 Juniors | 21 | 17 | 17.6% |
| 147 | LSB Freshman (own) | 26 | 22 | 18.2% |
| 91 | PrimeTime Reserve | 23 | 19 | 21.1% |
| 3 | Epp Foundation Juniors | 35 | 31 | 22.6% |
| 126 | GI Home Federal 18U | 25 | 21 | 23.8% |
| 279 | Jr Bluejays 15U | 16 | 12 | 25.0% |
| 128 | Lincoln Hotel 18U | 29 | 25 | 32.0% |
| 215 | Cornhusker LSW 2026 | 25 | 21 | 33.3% |
| 100 | Lincoln East Reserve 15U | 22 | 18 | 33.3% |
| 185 | Gretna 216 Reserve | 21 | 17 | 35.3% |
| 336 | Neb Prospect 15U | 14 | 10 | 50.0% |
| **Pooled** | | | **357** | **21.6% (77/357)** |

Per-team games-with-data ranges **14-47**. Pooled novel-starter rate is **21.6%** — roughly **1 in 5** scored games has a starter no method could have predicted from the history we hold. But that blended 21.6% is **not** the number to plan against; the next section decomposes it.

### 2a. Decomposition: temporal cold-start vs. structural floor

Is the 21.6% an early-season cold-start effect that self-resolves as games accumulate, or a structural gap that persists? Bucketing the novel-starter rate by each team's **own within-season game index** answers it directly. We compare the fully-charted control (LSB Varsity, season 2026) against the under-charted opponents (the other 16 seasons pooled):

| game-index bucket | LSB Varsity (fully charted) novel % (n) | Opponents pooled (under-charted) novel % (n) |
|---|---|---|
| 5-9   | 20% (1/5)  | 48% (38/80) |
| 10-14 | 0% (0/5)   | 20% (16/80) |
| 15-19 | 0% (0/5)   | 12% (9/72)  |
| 20+   | 9% (1/11)  | 12% (12/99) |
| **all** | **8% (2/26)** | **23% (75/331)** |

**The 21.6% is two components, and only one is addressable:**

1. **A self-resolving early-season cold-start.** Both series start high in games 5-9 (opponents 48%) and decay fast as history accumulates — this component is temporal and resolves itself with more games, for everyone. A coverage lever does **not** need to fix it.
2. **A structural ~12% persistent opponent floor.** The two series *separate and stay separated*: the fully-charted control decays to ~0% by games 10-19, while the under-charted opponents **plateau at ~12% and hold there through 20+ games**. That persistent floor does not self-resolve — and the control proves a *complete* schedule would drive it to ~0%. This ~12% is the structural coverage gap.

**The honest number to plan against is the ~12% structural floor, not the blended 21.6%.** The "it's just early-season cold-start" objection is refuted: cold-start explains the early spike but not the sustained ~12% opponent floor that a complete schedule eliminates. Crucially, this structural gap is **concentrated in mid/late season (games 10+)** — exactly when scouting reports are generated and matter most — so closing it pays off precisely where the feature is used.

**Caveats:** the control's per-bucket n is small (5/5/5/11); the decay-to-~0 trend is clear but the single late-season point (LSB 20+ = 9%, 1/11) is one game — a genuine late first-time starter, consistent with the irreducible ~7.7%/~0% floor (Section 3) rather than a coverage miss. The opponent buckets are well-powered (72-99 each), so the ~12% structural plateau is solid.

## 3. The argument: coverage gates accuracy, not the algorithm

Three observations from the data make the case:

1. **The coverage ceiling, not the algorithm, is the binding constraint.** With a 21.6% novel rate, the maximum achievable top-1 accuracy is ~78% before any model quality enters. The engine's actual top-1 is ~20% and top-2 ~40%. The gap between 40% and the 78% ceiling is the addressable space — but a large part of the residual miss is *irreducible* committee entropy (see point 3), and a meaningful part is *missing history* (this section). The novel games are coverage loss: ~77 of 357 games are unwinnable because we never saw the arm — though, per Section 2a, the *addressable* slice is the ~12% structural floor (mid/late season), not the full 21.6% blended rate (which includes a self-resolving early-season cold-start).

2. **The fully-charted control proves the gap is real.** LSB Varsity (team 160) is our **own** team — we ingest every one of its games, so its history is essentially complete. Its novel rate is **7.7%**, the lowest in the set. The *scouted opponents* — where we only hold the subset of games GameChanger charted and we crawled — cluster at **15-50%**, 2-6x higher. The same engine, same level of play, same committee structure: the only thing that changed is **how complete the game history is**. That contrast is the cleanest available evidence that incomplete opponent coverage is what inflates the novel rate and deflates accuracy. A "novel" opponent starter is frequently not a true first-timer — it is a veteran whose earlier starts we simply never ingested.

3. **But there is a hard floor coverage cannot lift: structural committee entropy.** Every one of the 17 teams is a committee (no team's top starter exceeds ~31% of starts) because pitch-count rules at this level make a dominant ace physically impossible. Even with *perfect* history, the next starter in a deliberately-spread 6-9-arm committee is genuinely high-entropy. So fuller coverage raises the ceiling and converts "novel" misses into rankable arms, but it will **not** push committee top-1 toward the 78% ceiling — the realistic target is moving top-2 from ~40% toward ~50-55% (the combined start-share of the top two arms on the better-covered teams), not turning the feature into a single-name oracle.

**Net:** coverage is the largest *addressable* lever (it directly attacks the structural ~12% persistent novel floor — Section 2a — concentrated in the mid/late-season window when reports are generated), the algorithm is already validated as good, and the product framing (E-243 surfaces a ranked top-2/3 "most likely arms," not one name) is exactly the framing that benefits most from better coverage — more complete history makes the ranked shortlist more often contain the actual starter.

## 4. What specifically would move the needle

The novel-starter losses come from **opponent games that exist but we did not ingest**. The lever is fetching more of each opponent's *completed* schedule before (or independent of) report generation. Concretely, in rough order of cost/benefit:

| Lever | What it does | Cost / complexity | Expected effect |
|---|---|---|---|
| **A. Report-time schedule fill** | At report generation, read the opponent's public completed-game schedule (`/public/teams/{public_id}/games`) and crawl/boxscore any completed games we are missing for the season, before computing the prediction. | **Low-moderate.** Reuses the existing opponent-scouting pipeline (`docs/api/flows/opponent-scouting.md`); the public schedule endpoint needs no auth. Bounded by ~30 games/opponent. Main cost is added per-report latency and more boxscore fetches. | **Highest.** Directly converts novel-starter games into rankable history. Should pull the 15-50% opponent novel rates down toward the 7.7% fully-charted floor. |
| **B. Scheduled backfill pass** | A periodic (e.g., nightly) job that backfills completed-game history for known/tracked opponents, decoupling coverage from report latency. | **Moderate.** New scheduled job + idempotent ingest; overlaps the morning-run cron infrastructure that already exists. | High, same mechanism as A but pre-warmed (no per-report latency hit). |
| **C. Deeper history (prior seasons)** | Ingest opponents' prior-season game history. | **Higher, low payoff.** Cross-season is an explicit project non-goal (CLAUDE.md / ROADMAP), and rotations turn over year-to-year, so prior-season arms rarely predict the current starter. | Low — **not recommended.** |

Lever **A** is the cheapest high-impact move and the natural unit of work: it is the "auto-ingest the opponent's full completed season at report time" idea, now data-justified.

## 5. Caveats

- **Novel-rate is a proxy, not a measured coverage ratio.** Without an external games-played denominator (not cached, and out of scope to fetch live), we infer the gap from the novel rate and the fully-charted control rather than measure "games missing" directly. The LSB-vs-opponent contrast makes the inference strong, but it is an inference.
- **Some novel rate is genuinely irreducible** (true first-time starters, call-ups, committee experimentation). Coverage will not drive the opponent novel rate all the way to zero — 7.7% (the fully-charted floor) is the realistic asymptote, not 0%.
- **The benefit is bounded by committee entropy** (Section 3, point 3). Better coverage improves *which arms are on the shortlist*, not the fundamental unpredictability of who starts next in a spread rotation. Expectation management matters: this is a top-2 improvement, not a single-name-accuracy breakthrough.
- **Cost is mostly latency and fetch volume**, not complexity — lever A reuses existing pipeline machinery. The real trade-off is per-report generation time vs. accuracy.

## 6. Disposition recommendation

**Worth building — as a bounded follow-on epic, scoped to lever A (report-time completed-schedule fill), with lever B as a fast-follow if per-report latency proves unacceptable.** Rationale:

- It attacks the single largest *addressable* accuracy lever — the structural **~12%** persistent novel floor (Section 2a), not the blended 21.6% (which folds in a self-resolving early-season cold-start). The fully-charted control shows this floor is a coverage artifact, not a model weakness, and it concentrates in mid/late season — exactly when reports are generated.
- It reuses the existing opponent-scouting pipeline and the no-auth public schedule endpoint, so it is low-moderate cost and consistent with "Simple first."
- It compounds with the E-243 presentation/ranking fixes: a more complete history makes the ranked "most likely arms" shortlist hit more often, which is the exact product surface being shipped.

**Do not** absorb it into E-243 (keep that epic's focused presentation/ranking scope intact), and **do not** pursue cross-/prior-season history (lever C — project non-goal, low payoff). Frame the follow-on epic around two decisions for the planning session: (1) report-time fill vs. scheduled backfill (latency trade-off), and (2) an explicit per-report fetch budget / latency ceiling.

---

### Three-bullet summary
- **Coverage, not algorithm, is the binding accuracy lever:** the 21.6% blended novel rate decomposes (Section 2a) into a self-resolving early-season cold-start plus a **structural ~12% persistent floor** that holds through late season for under-charted opponents while our fully-charted own team decays to ~0%. The honest number to plan against is the **~12% structural floor**, concentrated in mid/late season (games 10+) — exactly when reports are generated.
- **The fix is fetching more of each opponent's completed season** (lever A: report-time schedule fill via the existing no-auth public-schedule pipeline) — cheapest high-impact move; expectation is a top-2 lift (~40%→~50-55%), bounded by structural committee entropy, not a single-name oracle.
- **Recommend a bounded follow-on epic** scoped to lever A (B as fast-follow); do not absorb into E-243, do not pursue cross-season history (project non-goal, low payoff).
