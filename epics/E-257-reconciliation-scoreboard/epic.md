# E-257: Plays→Boxscore Reconciliation Scoreboard (productization) — DRAFT STUB

## Status
`DRAFT`
<!-- Capture stub for a dropped thread: the E-245 closure deferred "reconciliation scoreboard
     productization" to a future epic; E-253 (CE-3) planning spun it out but filed nothing, so it
     was on no list anywhere. This stub homes it. NOT refined: no stories/ACs. Refine to READY
     before dispatch. Do NOT dispatch a DRAFT. -->

## Overview
CLAUDE.md's north-star Operating Principle ("Always Get Closer to Byte-Identical Play Ingestion") states its enforcement mechanism — a plays-to-boxscore reconciliation scoreboard, plus the rule that ingestion changes must not regress it — "is being designed in E-245 and lands when that scoreboard exists; until then, this principle binds intent." That scoreboard does not yet exist as a durable, repeatable artifact. data-engineer built it once as a manual, session-local SQL baseline (`.project/research/E-245-plays-boxscore-reconciliation-baseline.md`, reproduced from `scratchpad/recon.sql`). This epic productizes that baseline into a standing measurement + gate so the principle stops binding only intent and starts binding mechanically.

## Provenance
- **Not a CE-numbered audit epic.** This is a dropped thread surfaced by the 2026-07-03 platform audit review: E-245 deferred scoreboard productization to a future epic; E-253 (CE-3) planning referenced resuming it (the audit's recommended sequence put CE-3 "with the E-245 reconciliation-scoreboard resumption") but never filed a tracking artifact.
- **Owner**: data-engineer (the baseline author; the reconciliation grain and axis policy are data-model decisions).
- **Size**: M (estimate — refine).
- **Sequence**: **before or alongside E-256 (CE-6)**. E-256's REVISIT cutover (retire stored `player_season_*` in favor of query-time derivation) and the north-star enforcement both reason about the same plays-vs-boxscore fidelity surface; the scoreboard should exist as the measurement baseline before or beside that simplification, not after it.

## Scope (from the E-245 baseline)
Productize the plays-vs-boxscore reconciliation scoreboard from data-engineer's manual query. The baseline doc (`.project/research/E-245-plays-boxscore-reconciliation-baseline.md`) carries the current-state numbers, the grain decision, and the proposed metric:
- **Per-stat fidelity metric**: exact% + abs-Δ, computed at the **player-level grain** (`game_id` + `perspective_team_id` + `player_id`), **perspective-scoped** (the honest grain for report fidelity — a perspective-agnostic grain over-credits coverage), and **excluding no-plays units** (units where the boxscore has the player but plays has zero matching rows — those measure coverage, not parser accuracy).
- **Three axis counters** tracked alongside the per-stat metric: (1) dropped-pitch-events (pitch text stranded as `event_type='other'`), (2) no-plays units (coverage / perspective-misalignment), (3) self-games (`home_team_id = away_team_id`).
- **The gate rule**: "no stat's abs-Δ regresses and no axis counter increases" for any ingestion, parser, or reconciliation change. This is the concrete enforcement mechanism CLAUDE.md's Operating Principle says "lands when that scoreboard exists."

## Already-landed dependency (do NOT re-plan)
- **E-253 (CE-3) already shipped the stat-key drift canary** the audit said "belongs with the E-245 scoreboard" (`game_loader.py` group-grain stat-key drift canary + `scouting_loader.py` mirror). This epic does NOT re-plan the canary; it consumes/complements it. The canary catches a GC field rename zeroing a stat on both sides (which the scoreboard alone can't see because both sides share the corrupted source); the scoreboard measures fidelity where data exists. They are companions, not duplicates.

## Refinement Notes (for the future planning session)
- Decide the artifact form: a `bb`/`bb report` subcommand vs. a script vs. a test-suite gate — and where the gate binds (CI, a pre-commit check, or a manual operator diagnostic like `bb report verify-aggregates`). The metric is defined; the surface is not.
- Decide the baseline snapshot policy: the gate rule "does not regress" needs a committed baseline to diff against, and a defined refresh procedure when a fix legitimately moves a number.
- Coordinate with E-256 (CE-6): if the query-time-aggregate cutover lands, confirm the scoreboard's grain and the aggregate-parity script (`aggregate_parity.py` / `bb report verify-aggregates`) do not overlap or conflict — they measure different things (aggregate parity = stored vs. recomputed season rows; scoreboard = plays vs. boxscore per-game) but both touch the same tables.
- The baseline doc's open coordination items name a baseball-coach question (stat-priority weighting for the headline metric — is BF/FPS the headline, or AB/H/BB/SO equally?) and whether the abandoned-PA residual (cause 5) is acceptable — resolve before locking the gate's severity weighting.
- Related but distinct: IDEA-062 (Plays-vs-Boxscore Reconciliation Engine, promoted to E-198) is the *corrective* engine (detect + fix misattribution); this epic is the *measurement + gate* artifact. Do not conflate — one fixes data, the other measures and guards fidelity.

## History
- 2026-07-06: Created as a DRAFT capture stub to home the dropped E-245 scoreboard-productization thread (E-253 planning spun it out without filing). Not refined; not dispatchable until taken to READY.
