---
name: invariant-audit-sibling-writer
description: When an epic adds a provenance/row-ownership guard to ONE writer, sweep sibling DELETE+INSERT paths that can defeat it by deleting the protected row first
metadata:
  type: feedback
---

# Provenance guards can be defeated by sibling delete-then-recompute paths

When an epic introduces a row-ownership invariant by adding a guard to ONE writer
(e.g. E-237 `canonical_recompute` added a `NOT EXISTS (... full/supplemented ...)`
guard so it never overwrites member-authoritative season rows), the guard only
protects the rows that still EXIST when that writer runs. A sibling path that
DELETEs the protected row *before* the guarded recompute runs silently defeats it.

**E-237 concrete case:** `merge_player_pair` (player_dedup.py) did an unconditional
`DELETE FROM player_season_* WHERE player_id IN (canonical, duplicate)` (all
provenances), THEN `recompute_affected_seasons` → `canonical_recompute`. Because the
full row was already deleted, the NOT EXISTS guard saw nothing and recreated the
player as `boxscore_only` — re-opening the exact data-loss the epic's guard closed,
but only for *merged* players. Pre-existing bug, but exactly the class the invariant
audit targets. Fix: provenance-scope the DELETE to `boxscore_only` + re-point
surviving member rows to the canonical id (with canonical-wins collision resolution).

**Audit heuristic (invariant-audit mode):**
- Grep ALL writers of the guarded table, not just the epic diff.
- For each writer that does `DELETE ... WHERE <key>` (no provenance filter) followed
  by a recompute/INSERT, ask: can this delete a guard-protected row before the guard
  runs? If yes → FLAG.
- Distinguish "presence/EXISTS checks" and "per-player display reads" (provenance-safe)
  from "whole-scope re-aggregation/recompute" and "unconditional DELETE+rederive"
  (the real risks).
- Verify the FIX with the remediation-regression guard: correctly scoped (not
  over/under-reaching), composes with the rest of the operation (re-point ordering),
  and the final UPDATE/INSERT can't violate the unique PK (trace all provenance
  combinations to prove collision-free).

Be honest when a flagged site is pre-existing (not an epic regression) — report it as
such and let main/PM triage fix-in-closure vs follow-up; the audit mandate is to find
ANY violating site, not only epic-introduced ones.
