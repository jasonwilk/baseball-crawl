# CR-vs-Codex Gap Re-measurement (agentic-flow-review item 25)

**Date:** 2026-07-13
**Author:** product-manager (deferred process obligation, run in normal PM capacity — not a dispatch)
**Obligation:** `.claude/agent-memory/product-manager/project_cr_codex_gap_remeasurement.md` (installed by E-258-04, 2026-07-08)
**Hypothesis under test:** `.project/research/AGENTIC-FLOW-REVIEW-2026-07-07.md` §3.2 / §3.3 (the "routing-era test")

> **STATUS: RECORD OF A ONE-TIME INTERIM RUN — does NOT close item 25 in the pre/post sense it was written for.** After this run the operator asked whether the measurement should be re-anchored to after E-260, then CONFIRMED (2026-07-13): **RETIRE + keep the corrected forward design DORMANT.** Item 25 is answered-as-far-as-possible: its E-251-pivot hypothesis is permanently unanswerable (no pre-E-251 canonical-scorecard cohort exists or can ever exist — the schema postdates E-251), structural-class CR-misses dominate, and the reviewer-quality "narrowing" claim is unprovable with any scorecard cohort. RETIRED (not re-armed) because under the E-260 meta-layer freeze with no rubric epic planned, a standing trigger would feed no live decision — proportionality bars machinery that informs nothing. The corrected forward design (post-E-260 anchor + count Codex-RUNNING epics, N=5) is preserved DORMANT and non-self-triggering in `.claude/agent-memory/product-manager/project_cr_codex_gap_remeasurement.md`, to be pulled only on a fresh defect-cited rubric decision. This document stands as the honest snapshot; its per-class tally is a caveated read, not the item-25 verdict.

---

## 1. Headline verdict

**The structural half of the routing-era hypothesis is borne out; the reviewer-quality (narrowing) half is directionally consistent but NOT rigorously demonstrable from this cohort.**

- **Structural classes persist and dominate post-E-251.** Of the accepted CR-missed / Codex-caught findings in the qualifying cohort, **structural classes account for the large majority** (6 of 8 strict-set; 8 of 11 strict+boundary): cross-cutting/mirror-path drift (×3, E-259), doc & context-layer drift (×3), test-integrity (×1), concurrency (×1). Every structural class the §3.2 taxonomy flagged as *persisting* or *recent-skewed* recurred in the post-E-251 cohort. Prediction "structural classes do not move" → **supported**.
- **Reviewer-quality classes are thin** (2 strict-set / 3 strict+boundary across the whole cohort — 0–2 per epic). This is *consistent* with the "already thin post-E-233 → narrows further" prediction, but **cannot be proven as a narrowing** because there is no pre-E-251 canonical-scorecard cohort to compare against (see §5, the honest limitation).

---

## 2. The qualifying set (real closure dates, canonical Review Scorecard present)

The obligation's countable fire-condition: **≥5 epics archived AFTER 2026-07-08 carrying the canonical Review Scorecard schema** (the schema landed in E-255, 2026-07-08). Closure dates are the REAL dates from each epic's `## History` / Status block, NOT the git-last-commit proxy (the 2026-07-12 endgame-sweep program re-touched many archived dirs, inflating last-commit).

| Epic | Real closure date | Canonical Review Scorecard? | Ran a Codex dispatch/closure pass? | In strict qualifying set? |
|---|---|---|---|---|
| E-256 Post-Descope Simplification | 2026-07-12 | Yes (dispatch scorecard, 16-story table) | **No** (plain "implement"; Step 1c CR only) | Yes |
| E-257 Reconciliation Scoreboard | 2026-07-09 | Yes (planning + dispatch scorecards) | **No** (explicit "No Codex row — plain implement") | Yes |
| E-259 Query-Time Season Aggregates | 2026-07-12 | Yes (planning scorecard + closure Codex list) | **Yes** (closure Codex, 5 findings) | Yes |
| E-260 Dispatch Cost Accounting | 2026-07-12 | Yes (Review Scorecard) | **No** (AC-2: deliberately not run — conflict of interest) | Yes |
| E-261 Cross-Perspective Game-Dedup | 2026-07-13 | Yes (Review Scorecard) | **Yes** (Codex code review, 3 findings) | Yes |
| E-262 Post-Program Housekeeping | 2026-07-13 | Yes (dispatch+closure scorecard) | **Yes** (Codex Phase-4, 2 findings) | Yes |
| **Strict qualifying set** | | | | **6 epics** |
| E-258 Review-System Hardening | **2026-07-08** (boundary — ON the date, not after) | Yes | **Yes** (Codex Phase 4b, 3 findings) | Boundary/corroborating |
| E-255 Truth Sweep | **2026-07-08** (boundary; schema-INSTALLING epic) | Yes (schema origin) | **Yes** (Codex Phase 4b, 5 findings) | Excluded (schema origin) |

**Count: 6 epics closed strictly after 2026-07-08 with a canonical scorecard — the fire-condition (≥5) is met; the trigger fires.**

Two epics closed ON the boundary date 2026-07-08: E-255 (which *installed* the canonical schema at its own closure — the obligation explicitly treats it as the schema origin, "no epic has yet closed under it") and E-258 (which installed *this* trigger). Neither is "after 2026-07-08" by a strict reading. Both are post-E-251 and both ran a Codex pass, so both are reported below as **corroborating boundary data**, kept visually separate from the strict-set tally.

### The most important structural fact about the cohort

**Only 3 of the 6 strict-qualifying epics ran a Codex pass at all** (E-259, E-261, E-262). E-256, E-257, and E-260 ran plain "implement" dispatches with no "and review" modifier, so no Codex pass ever ran — including E-256, the largest epic in the cohort (16 stories). The CR-vs-Codex gap is only observable where Codex actually runs; on the other three epics any CR-missed findings are simply **undetected, not proven absent**. This materially bounds the completeness of the tally and is itself a finding: the routine post-program default remained plain "implement," so most of the cohort produced no gap data.

---

## 3. Per-class tally — accepted CR-missed / Codex-caught findings

Bucketing follows §3.3's explicit split:
- **Structural** = cross-cutting integration & mirror-path drift, test-integrity & missing coverage, doc & context-layer drift, concurrency/atomicity races, security, migration/deploy. (§3.3: "does not move.")
- **Reviewer-quality** = function-contract & edge-case bugs, spec/AC-compliance drift. (§3.3: "narrows.")

Only findings **accepted as genuine CR-misses that Codex caught** are counted. Codex findings that were **dismissed** (false-positive or pre-existing/out-of-scope) are listed separately and NOT counted in the gap.

### 3a. Strict qualifying set (Codex-running epics only: E-259, E-261, E-262)

| Class | Bucket | Count | Per-epic source |
|---|---|---|---|
| Cross-cutting integration & mirror-path drift | Structural | 3 | E-259 F3a (`src/db/player_dedup.py:554` stale docstring), F3b (`docs/api/flows/opponent-scouting.md`), F3c (`docs/ROADMAP.md` §2/§3) — the deletion-side-eviction scope gap; systemic lesson → IDEA-125 |
| Test-integrity & missing coverage | Structural | 1 | E-259 F1 (rate-stat test relied on the dropped `player_season_*` surface → trivially passed; teeth restored) |
| Doc & context-layer drift | Structural | 1 | E-262 F1 (`operations.md` creds recipe validated a WEB import with bare `bb creds check` → mixed-profile-mask false-green; fixed → `--profile web`) |
| Concurrency / atomicity races | Structural | 1 | E-261 P2 (twin-merge read-then-write TOCTOU: concurrently-deleted source twin → uncaught `GameMergeError`; fixed fail-closed) |
| Security | Structural | 0 | — |
| Migration / deploy | Structural (dormant) | 0 | (E-259 F2 raised, DISMISSED as false-positive) |
| **Structural subtotal** | | **6** | |
| Function-contract & edge-case bugs | Reviewer-quality | 1 | E-261 P1 (`_build_schedule_counts` doubleheader undercount when a sibling summary lost its opponent name — fail-OPEN edge case; fixed fail-CLOSED) |
| Spec / AC-compliance drift | Reviewer-quality | 1 | E-261 P3 (`bb data merge-duplicate-games` advertised an inert `--dry-run` flag — contract vs behavior mismatch; vestigial flag removed) |
| **Reviewer-quality subtotal** | | **2** | |
| **Strict-set total (accepted gap)** | | **8** | |

**Dismissed by triage (raised by Codex, NOT counted as gap):** E-259 F2 (migration-011 evidence gap — false-positive; the terminal-state DROP assertions are stronger than a row-count check), E-262 F2 (`/plays` token contradiction — proven byte-for-byte pre-existing → routed to IDEA-138). = **2 dismissed**.

### 3b. Adding boundary-date corroborating epic E-258 (closed 2026-07-08)

E-258's Codex Phase 4b caught 3 findings (Phase 4a CR integration review had returned 0), all accepted:

| Class | Bucket | Count | Source |
|---|---|---|---|
| Function-contract & edge-case bugs | Reviewer-quality | 1 | E-258 (read-receipt guard enforced marker *existence* only, not the exact-once/in-order contract — fail-closed contract gap; guard strengthened) |
| Doc & context-layer drift | Structural | 2 | E-258 (`codex-review/SKILL.md` L94/L104 read-receipt contradiction; stale L360 rubric-source claim) |

**Strict-set + E-258 totals:** structural **8**, reviewer-quality **3**, **total 11 accepted**; dismissed still 2.

### 3c. Further corroboration — E-255 (boundary, schema origin, NOT in the countable tally)

E-255's Codex Phase 4b caught 5 CR-missed findings, ALL structural — 4 cross-cutting integration / mirror-path drift (F2 `workflow-discipline.md` "Task tool", F3 `CLAUDE.md:77` `game_stream_id`, F4 opponent-scouting "completed games only", F5 coach-memory id/dashboard drift) + 1 **security** (F1 `secret-read-guard.sh` relative-path bypass). This is not counted (E-255 is the schema-installing origin epic), but it is a strong directional corroborator: the very first post-E-251 epic to run Codex under the new itemized regime produced an *entirely structural* CR-miss set, including the cohort's only security finding.

---

## 4. Reading the hypothesis against the data

The routing-era prediction (§3.3): after E-251 replaced bare `general-purpose` review spawns with defined agents (2026-07-05), the CR-vs-Codex gap **narrows for reviewer-quality classes** but **does not move for the structural classes** (integration drift = review scope; test-integrity = no execution; doc drift = CR skipped; concurrency + security = no rubric).

**Structural half — SUPPORTED.** Every structural class the taxonomy named as persisting/recent recurred in the post-E-251 Codex-running epics, and structural findings dominate the gap (6/8 strict, 8/11 with E-258, and E-255's corroborating set is 5/5 structural):
- Cross-cutting / mirror-path drift persists as the single largest class (E-259's 3-way deletion-eviction scope gap — exactly the "defects live outside the story diff, in untouched twin paths" root cause; the systemic lesson became IDEA-125).
- Test-integrity persists (E-259 F1 vacuous test — the "CR barred from worktree pytest → evaluates assertions textually" root cause, verbatim).
- Doc & context-layer drift persists (E-258 ×2, E-262 ×1 — the "context-layer stories skip per-story CR / token-grep misses prose" root cause).
- Concurrency persists and remains recent-skewed (E-261 P2 TOCTOU — precisely the "admin UI + CLI + cron = three SQLite writers" hazard §3.4 item 4 named; dual review "didn't move it").
- Security remained a Codex-only catch where it appeared (E-255 F1).

**Reviewer-quality half — DIRECTIONALLY CONSISTENT, NOT PROVEN.** Reviewer-quality findings are thin in absolute terms (2 strict / 3 with E-258, spread 0–2 per epic), which is consistent with "already thin, narrows further." But a *narrowing* is a pre-vs-post comparison, and this cohort cannot supply the "pre" term (§5). We can only say reviewer-quality misses are now few — not that they measurably fell relative to a like-measured pre-E-251 baseline.

---

## 5. Honest limitation — no pre-E-251 canonical-scorecard comparison exists

The hypothesis asks for a **pre- vs post-E-251** per-class comparison. That comparison **cannot be drawn from the qualifying scorecards**, because:

- E-251 landed **2026-07-05**; the canonical Review Scorecard schema landed **2026-07-08** (E-255). Every epic that carries the canonical schema is therefore **already post-E-251**. The qualifying cohort is 100% post-E-251 — there is no pre-E-251 canonical-scorecard epic to compare against.
- The pre-E-251 picture exists only as the **§3.2 taxonomy itself** — the 217 CR-missed findings tallied across the whole (pre-E-251-dominated) review history, in a mix of count-only and itemized scorecards, not the canonical schema. That taxonomy is the de-facto "before"; this re-measurement is the "after."

So the rigorous claim this exercise can support is one-directional: **the post-E-251 cohort's CR-miss set is structural-dominated, and every structural class the pre-E-251 taxonomy flagged as persisting/recent is still present** — the "structural classes don't move" prediction holds. The "reviewer-quality narrows" prediction is consistent with the thin post-E-251 counts but is not measured here, and I have not manufactured a pre-E-251 canonical figure to fake the comparison.

A second limitation compounds this: only 3 of 6 strict-qualifying epics ran Codex at all (§2), so the observable gap rests on a small, self-selected base (the epics whose operators opted into "and review"). The tally is a floor, not a census.

---

## 6. Implication for the E-258 rubric-edit spend

E-258-01/02/03 added CR rubric coverage aimed squarely at the structural classes (consumer-audit/twin-path checklist, adversarial assertions, standing concurrency question, security trigger, unconditional closure CR integration review). This measurement is the check on whether that spend is earning its keep. The read:

- The structural classes those edits target **are exactly the classes still leaking to Codex** post-E-251 — so the edits address the right classes; the gap has not closed yet in the epics measured.
- BUT several of the leaks (E-259 F3 deletion-eviction scope gap; E-261 P2 three-writer TOCTOU) are **scope/execution** problems the rubric can prompt for but not mechanically guarantee — consistent with §3.3's framing that these are structural (scope/execution), not reviewer-skill, problems. The E-258 edits raise the odds CR catches them; they do not make CR diff-complete or pytest-capable.
- No further rubric-spend recommendation is warranted on this data alone. The clearer lever is **coverage**: half the cohort ran no Codex pass, and the largest epic (E-256) ran neither Codex nor (by its plain-implement path) anything beyond the Step 1c CR integration review. If the goal is to shrink the *observed* gap, running Codex on more epics (or making the closure Codex pass less optional on large/structural epics) would surface more of it than another rubric line would.

---

## 7. Sources

- `.project/archive/E-256-post-descope-simplification/epic.md` — dispatch Review Scorecard (no Codex row); closure 2026-07-12.
- `.project/archive/E-257-reconciliation-scoreboard/epic.md` — "No Codex row — plain implement"; closure 2026-07-09.
- `.project/archive/E-258-review-system-hardening/epic.md` — dispatch scorecard: Phase 4a CR 0 findings, Phase 4b Codex 3 findings; closure 2026-07-08.
- `.project/archive/E-259-query-time-season-aggregates/epic.md` — closure Codex review F1/F2/F3a/F3b/F3c (4 fixed + 1 dismissed); closure 2026-07-12.
- `.project/archive/E-260-dispatch-cost-accounting/epic.md` — Review Scorecard (AC-2: no Codex); closure 2026-07-12.
- `.project/archive/E-261-cross-perspective-game-dedup-fidelity/epic.md` — Review Scorecard: Codex code review P1/P2/P3 (all accepted); closure 2026-07-13.
- `.project/archive/E-262-housekeeping-audit-residuals/epic.md` — Dispatch & Closure Review Scorecard: Codex Phase-4 2 findings (1 fixed + 1 dismissed); closure 2026-07-13.
- `.project/archive/E-255-truth-sweep/epic.md` — Dispatch Review Scorecard: Codex Phase 4b 5 findings (all accepted); schema-installing epic; closure 2026-07-08.
- `.project/research/AGENTIC-FLOW-REVIEW-2026-07-07.md` §3.2 (taxonomy), §3.3 (routing-era test).
</content>
</invoke>
