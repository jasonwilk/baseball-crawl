---
name: operator-followups
description: Open operator-owned obligations carried across epic closures — context-ratchet baseline drift, prod backup, feature-flag decision, doc sweeps
metadata:
  type: project
---

# Open Operator Follow-Ups

Canonical discharge record for the bulk of these: `.project/research/2026-07-12-program-endgame-sweep.md` §4 (nearly all were discharged at that sweep). Only the items below remain open.

**How to apply:** surface these at epic closure, not mid-dispatch. Items 1, 2 and 4 are operator actions PM can only remind about; item 3 is the one that will actively FAIL a closure gate.

## 1. PROD backup at next deploy
Migration 011 (E-259, dropped the stored `player_season_*` tables) applies to production on next deploy. Take a backup first.

## 2. `FEATURE_PREDICTED_STARTER` promote-to-default decision
Unrecorded. Audit residual #12.

## 3. CONTEXT-RATCHET BASELINE IS STALE AND COMPOUNDING — four deferrals

**Why:** the 2026-07-13 baseline (12404) vs 13275 at E-270 closure = **+871**, of which only ~+30 was E-270's own. **+728 is `.claude/agent-memory` growth** across E-261/E-262/E-264/E-267/E-273. A fourth deferral landed at E-272 closure (own +101, total +972 — E-272 is 10.4% of the overrun; +22 of its own came from the trigger-8 codification itself, i.e. recording the context-growth lesson grew the context layer).

Deferrals so far: E-262, E-273, E-270 (2026-07-25), E-272.

Each time, the operator was shown the full number with the inherited/own split and **signed an exception rather than re-snapshotting or offsetting** — which DEFERS the drift, it does not resolve it.

**How to apply:** expect the next epic to close and FAIL trigger 7 with a larger gap. The honest framing for the operator is **"the baseline has been stale for N epics"**, NOT "this epic broke the ratchet" — do not let an epic absorb blame for inherited drift. Only the operator runs `--update-baseline`. If an offset is ever preferred over another exception, the largest single candidate is this directory's own `archived-epics.md` (several pre-E-250 entries describe surfaces that no longer exist).

## 4. Corpus-wide `docs/api` doc-PII sweep
IDEA-137, raised at E-262 closure. Related: IDEA-170 (the byte-gate structurally cannot see `src/`).

## Discharged, recorded so they are not re-raised

- **`age_group` is a polymorphic 3-family LEVEL field** (raised at E-272 closure as follow-up #5) — **PROMOTED to E-274, 2026-07-25.** The evidence gap it flagged (school-family values seen only on our own teams via `/me/teams`) is **CLOSED POSITIVE**: 25 non-managed opponent public profiles, all three HS values confirmed unauthenticated. Its "materially weakens E-263-02c's premise" reading was **refined during E-274 discovery** — both baseball-coach instances concluded independently that a populated field raises the inference FLOOR but does not reach the CEILING operator knowledge covers, so E-274 narrows how often the pick is needed and E-263-02c's priority is unchanged.
- **api-scout's `docs/api/endpoints/get-public-teams-public_id.md` corrections** (follow-up #6) — **LANDED** during E-274 discovery, correctly outside the epic (api-scout is a direct-routing exception). Covered the `age_group` mischaracterization, the flat `team_season` shape, the two junk-empty `ngb` forms (`"[]"` and `""` — note `"[]"` is TRUTHY in Python), and the stable key set.

## Standing do-nots
Do NOT re-add `backfill-appearance-order` (retired E-256-02) or `canonical_recompute` / `verify-aggregates` (retired E-259).
