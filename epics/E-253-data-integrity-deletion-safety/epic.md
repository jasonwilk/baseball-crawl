# E-253: Data-Integrity & Deletion Safety — DRAFT STUB (audit CE-3)

## Status
`DRAFT`
<!-- Capture stub from the 2026-07-03 platform audit (PLATFORM-AUDIT.md, repo root, UNCOMMITTED).
     Carries the audit's CE-3 scope, absorbed findings, size, owners, sequence. NOT refined: no stories/ACs.
     Refine to READY before dispatch. Do NOT dispatch a DRAFT. -->

## Overview
Close the data-destroyer and data-integrity defects that sit on routine operations: the report-deletion cascade that permanently destroys shared-game plays another live report depends on (F-H1), plus a cluster of ingestion, migration-safety, dedup, and reconciliation correctness gaps. This is the epic that also DISCHARGES the F-H1 guard required-but-deferred by the E-250-02 TN-5 amendment.

## Audit Provenance
- **CE #**: CE-3 · **Size**: L · **Owners**: software-engineer, data-engineer · **Sequence**: position 5 — after E-250 lands, and **sequenced with the deferred E-245 reconciliation-scoreboard resumption** so the stat-key drift canary and the reconcile fixes land on the same foundation the scoreboard measures.
- **§4 scope row (verbatim)**: "Deletion-cascade shared-game guard (F-H1, incl. E-250-02 TN-5 amendment), spray chart_type UNIQUE migration, game_date timezone + backfill, migration-runner transactionality, stat-key drift canary (E-245 alignment), game-dedup DB backstop, 0-0 coercion, dedup fold/wildcard fixes, reconcile atomicity, Tier-2 suppress gate."
- **Absorbs**: F-H1 (HIGH) + 6 medium + 7 low.

## Absorbed Findings (one-liners copied from the audit)
- **F-H1 (HIGH)** — Report deletion cascade destroys shared-game plays another live report depends on; whole-game plays idempotency makes the hole permanent (`generator.py:2694`). Delete X's report; X and Y played each other → Y's pitcher FPS%/P-BF plays rows deleted and never re-fetched → silently wrong or blank forever. Fix: add a shared-game/reports-based eligibility guard OR scope anchor-pass DELETEs to exclude perspectives with live reports. **This epic implements the guard that E-250-02's TN-5 amendment declared REQUIRED but deferred here.** **Operator hold until this lands: no report deletions (user decision 2026-07-04, accepting the interim risk in lieu of an in-E-250 guard).**
- **All defensive spray rows silently discarded** (`scouting_spray_loader.py:526` + `migrations/001:417`) — offense/defense share event ids; UNIQUE omits `chart_type`, so 100% of defensive rows hit INSERT OR IGNORE and are miscounted as idempotent skips; data-model.md's ~16% defensive-coverage claim is false at the DB layer. Fix: widen UNIQUE via migration, stop counting collisions as skips, correct the rule. *(data-engineer)*
- **Systemic UTC-date derivation — game_date portion** (`game_loader.py:594`) — evening games file under the next day, skewing rest math, the 7-day window, and cross-perspective dedup at UTC midnight. Fix: the operating-timezone convention (env-configured `ZoneInfo`) at the game_date site **plus a backfill** of existing rows. (The report reference-date site is a report-render concern; morning-run's target date is CE-2 — coordinate the shared convention.)
- **Migration runner is not transactional** (`migrations/apply_migrations.py:131`) — `executescript()` autocommits per statement; a mid-file failure in a multi-ALTER migration (003, 007, planned 008 have the shape) wedges the DB into a permanent duplicate-column crash-loop. Fix: wrap file + `_migrations` INSERT in one transaction; correct the false docstring. *(data-engineer)*
- **Missing stat-key drift canary** (`game_loader.py:932`) — a GC field rename silently zeroes a stat for every player on both teams; verify-aggregates passes (both sides share the corrupted source). Fix: ERROR + `LoadResult.errors` when a core key is absent from ALL rows of a non-empty group; failing-input tests. Belongs with the E-245 scoreboard.
- **Tier-2 LLM enrichment runs on suppressed starter predictions; template renders the hallucinated narrative under "Not enough games yet"** (`generator.py:2214`, `scouting_report.html:607`). Fix: skip enrichment on `confidence == 'suppress'`; move the template block inside the non-suppress branch.
- **Cross-perspective game dedup is SELECT-then-INSERT with no DB UNIQUE backstop** (`game_loader.py:1100`, LOW) — narrow cross-process duplicate-game window. *(data-engineer)*
- **Missing game-summary scores coerced to 0-0** (`game_loader.py:500`, LOW) — a scoreless doubleheader can collapse into one game.
- **Load-path dedup deletes canonical `boxscore_only` season rows in scopes the end-of-load recompute never rebuilds** (`player_dedup.py:850`, LOW — latent, multi-season only).
- **Dedup detection uses ASCII-only NOCASE** (`player_dedup.py:201`, LOW) — misses accented-name duplicates; diverges from the planner's Unicode fold.
- **Unescaped LIKE wildcards create spurious dedup edges** (`player_dedup.py:207`, LOW) — welds legit collapses into refused forks.
- **Reconcile `--execute` commits plays mutations per team before discrepancy rows are written** (`engine.py:1124`, LOW) — crash window leaves corrections unrecorded.
- **`get_summary_from_db` dedup partition omits `perspective_team_id`** (`engine.py:1161`, LOW) — collapses distinct cross-perspective signals; matters for the E-245 scoreboard.

## Non-Goals (boundary vs. adjacent epics)
- Morning-run reliability cluster → CE-2 (E-252). Only `game_date` timezone + backfill is here; morning-run's target-date timezone is CE-2 (share the `ZoneInfo` convention).
- The query-time-aggregate cutover (upheld REVISIT) → CE-6 (E-256).

## Refinement Notes (for the future planning session)
- Resume the deferred E-245 reconciliation-scoreboard work as part of scoping so the stat-key canary and reconcile-atomicity fixes align with the scoreboard the north-star principle needs.
- data-engineer owns the spray UNIQUE migration, migration-runner transactionality, and the game-dedup DB backstop; software-engineer owns the F-H1 guard, timezone, dedup, reconcile, and Tier-2 gate. Consult baseball-coach on the Tier-2 suppress behavior (coach-facing narrative honesty).
- The Watch List §6 item "GS aggregate on partially-populated `appearance_order`" should be checked once during this epic.

## History
- 2026-07-04: Created as a DRAFT capture stub from the platform audit (CE-3). Not refined; not dispatchable until taken to READY.
