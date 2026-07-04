# E-252: Scheduled-Reports Reliability (Cron-Grade Morning-Run) — DRAFT STUB (audit CE-2)

## Status
`DRAFT`
<!-- This is a capture stub from the 2026-07-03 platform audit (PLATFORM-AUDIT.md, repo root, UNCOMMITTED).
     It carries the audit's CE-2 scope, absorbed findings, size, owners, and sequence position so a future
     session can PLAN it without re-reading the whole audit. It is NOT refined: no stories/ACs yet.
     Refine to READY (stories + acceptance criteria) before dispatch. Do NOT dispatch a DRAFT. -->

## Overview
Make the morning-of-game scheduled-report path (E-240, `bb report morning-run`) cron-grade. The unattended path is the forward feature of the product and currently its most fragile component: one HIGH data-integrity defect (the slot-wipe) is triggered by a documented daily workflow, and a cluster of reliability gaps mean a single transient error aborts the whole run and suppresses the only missed-run signal.

## Audit Provenance
- **CE #**: CE-2 · **Size**: M · **Owners**: software-engineer · **Sequence**: position 4 — after CE-1 (E-251), the curate-the-vision session, and E-250 dispatch. The forward feature is the product's future; the slot-wipe HIGH fires on documented daily workflows, so this leads the post-E-250 remediation epics.
- **§4 scope row (verbatim)**: "Slot wipe (F-H2), per-team isolation, summary-email guarantees, `_upsert_slot` isolation + busy_timeout/connection factory, write-txn-across-network, 429 handling, target-date timezone, team_resolver hardening, stuck-'generating' reaper, slot reservation race."
- **Absorbs**: F-H2 (HIGH) + 8 medium + 4 low.

## Absorbed Findings (one-liners copied from the audit)
- **F-H2 (HIGH)** — Morning-run idempotency skip wipes `report_id`/`report_slug` from the audit row, causing duplicate regeneration on the next run (`morning_run.py:300`). Same-day re-run (documented workflow after `map-opponent`) → skip branch upserts NULLs → run 3 does a full duplicate crawl+generate. Fix: carry prior slug/id onto the skip slot, or `COALESCE` in the upsert.
- **Per-team failure isolation covers only 403** (`morning_run.py:483`) — a transient 5xx/429/connect error on team 1 aborts teams 2-4, records nothing, and suppresses the "always-sent" summary. Fix: broaden the per-team catch; try/finally around `run_morning` so a crash still emails; broaden preflight's catch.
- **Nothing guarantees the summary email** (`cli/report.py:507`, `email.py:52/148`) — send result discarded (exit 0 on failure); unset `ADMIN_EMAIL` silently disarms the heartbeat; unset `MAILGUN_API_KEY` logs the body and returns True ("sent"). Fix: validate alerting config in non-dry-run preflight; check/retry the send; tri-state the dev fallback.
- **`_upsert_slot` outside per-slot isolation; no `busy_timeout` on any connection; ad-hoc connection setup** (`morning_run.py:540`, `src/api/db.py:52`) — one slot-recording DB error aborts all remaining teams; zero contention tests exist. Fix: shared connection factory (WAL+FK+busy_timeout ~30s), move the audit write inside isolation, add one contention test.
- **Morning-run holds an open write transaction across network I/O; no-slot runs roll own-team INSERTs back on close** (`morning_run.py:477`) — fresh-DB/pre-season: WAL write lock held across a multi-team crawl; rolled-back rows re-INSERT every morning. Fix: commit after `ensure_team_row`; never hold a write txn across an HTTP fetch.
- **429 handling: unbounded server-controlled sleep then raise anyway; `RateLimitError` escapes every per-game isolation** (`client.py:499/508`, `exceptions.py:41`) — one `Retry-After: 3600` stalls the cron an hour then aborts the run. Fix: cap Retry-After, retry-or-raise-immediately, add RateLimitError to crawl-loop catches.
- **target-date timezone** (part of the systemic UTC-date family) — morning-run's default target date uses UTC while the product reasons in venue-local dates; evening manual morning-runs use tomorrow's date. Fix: one operating-timezone convention (env-configured `ZoneInfo`, mirroring `derive_local_date`).
- **stuck-'generating' reaper** (`generator.py:241`) — process death mid-generation leaves reports stuck at 'generating' forever; admin meta-refreshes indefinitely; delete button hidden for generating rows. Fix: stale-run reaper in lifespan and/or `cleanup_expired_reports`.
- **team_resolver hardening** (`team_resolver.py:93`, LOW) — `team_resolver` catches only `TimeoutException` and bypasses the proxy/pacing posture; a `ConnectError` crashes the whole morning run. Fix: broaden the catch and respect the HTTP posture.
- **slot reservation race** (`morning_run.py:387`, LOW) — slot idempotency is read-then-act, recorded only after generation; overlap/SIGKILL double-generates. Fix: reserve the slot before generation.

## Non-Goals (boundary vs. adjacent epics)
- Deletion-cascade / data-integrity fixes → CE-3 (E-253). The `game_date` UTC + reconcile + stat-key items live there; only morning-run's own target-date timezone is in CE-2.
- The unattended-path timezone fix should adopt the same operating-timezone convention CE-3 introduces for `game_date` — coordinate the shared `ZoneInfo` convention across the two epics at refinement.

## Refinement Notes (for the future planning session)
- Consult api-scout on the 429/Retry-After cap and RateLimitError isolation (client behavior) and data-engineer on the connection-factory/busy_timeout contention model before writing stories.
- Add at least one SQLite contention test (the documented third-writer topology: admin UI + CLI + cron).

## History
- 2026-07-04: Created as a DRAFT capture stub from the platform audit (CE-2). Not refined; not dispatchable until taken to READY.
