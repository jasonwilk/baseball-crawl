<!-- NO REAL NAMES OR IDENTIFIERS — no person's name, ever; for teams, orgs, ids and UUIDs use the PII-Safe Placeholder Taxonomy in `.claude/rules/api-docs.md`. -->

# Unbounded concurrent report generation exhausts busy_timeout

**Date**: 2026-08-10 · **Status**: `STUB` — measured from live logs; needs a small code chunk + a repair pass
**Source**: read-only log audit of the 2026-08-10 13:25–13:52Z operator run (51 admin-UI
generations, up to 14 in flight). Log capture and extracted merge-pair CSV in the trainer
session's scratchpad; re-derive from logs, do not inherit counts.

## The defect

51 `POST /admin/reports/generate` in 27 minutes reached 14 simultaneous generations against
one SQLite file. The 30s `busy_timeout` on the canonical connection seam was exhausted at the
concurrency peaks: **243 `database is locked` tracebacks** — 121 `merge_player_pair` failures,
121 `dedup_team_players` collapse failures, 1 orphan-reclamation failure.

**Persisting damage (verified, not inferred):** all 121 failed merge pairs still have both
rows; 13 teams carry roster bloat (worst: 123 roster rows / 24 distinct names against a
12–15-player roster), surfaced in 34 post-load validation warnings. One duplicate `games`
row (identical score AND start_time, two ids, both created 10s apart in this run) is the same
race expressed at game grain.

NOT covered by archived IDEA-099 (scoped to non-triad `bb data` writers; this failure is
inside the triad that already has the timeout).

## Repair (operator-run, no code, self-healing by design)

Re-generate the 13 affected teams SERIALLY — `player_dedup` documents partial dedup as
self-healing on re-run. Verify per team: roster rows vs distinct names before/after.
Generation is DESTRUCTIVE (reconcile-at-load + reclamation); that is its normal job here.
Team ids at audit time: 47, 49, 61, 43, 92, 278, 94, 63, 3, 293, 370, 427, 283.
Merge the race-created duplicate game via the canonical seam first (dry-run, then merge).

## Durable fix (the chunk)

A concurrency cap on the admin generate path (queue or reject-with-retry past N in flight;
N=2–3 likely plenty for one operator). Spec decides mechanism; keep it boring. Do NOT raise
busy_timeout as the fix — waiting longer just moves the cliff.

## Progress log

- **2026-08-10** — Stubbed from the log audit. No writes, no merges, no regenerations run.
