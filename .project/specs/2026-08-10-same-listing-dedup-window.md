<!-- NO REAL NAMES OR IDENTIFIERS — no person's name, ever; for teams, orgs, ids and UUIDs use the PII-Safe Placeholder Taxonomy in `.claude/rules/api-docs.md`. -->

# Same-listing dedup window misses minutes-apart double-listings

**Date**: 2026-08-10 · **Status**: `STUB` — DETECTION half is DONE; residual observations remain.

> **The DETECTION half of this stub landed 2026-08-15** via
> `.project/specs/done/2026-08-13-same-listing-dedup-detection.md` — the window widened to
> 1,800s and an opponent-divergence second pass was added. Do not re-plan detection from here.
>
> The **REPAIR** half is DE-SCOPED by the Regeneration hazard ruling (2026-08-12): the full
> regenerate replaces it and `bb data merge-duplicate-games` is untouched.
>
> ⚠ **The Addendum below is REFUTED and kept only as history.** Its claim (1) — "the tolerance
> branch is not reached on at least one path" — is FALSE. `_is_same_listing_delta` returns True
> on the 0.96s pair's real stored start strings. That twin survived because the step BEHIND the
> redirect, `merge_duplicate_game`, structurally REFUSES when the two rows share a
> `perspective_team_id`, and both rows carry the same single perspective. A same-perspective
> twin therefore can never self-heal in place; only a fresh load avoids creating one.
>
> This stub stays `STUB` for its remaining residual observations (the enumerated candidate
> groups and the spray/degraded-badge fallout chain), not for the detection rule.
**Source**: read-only probe of a degraded Aug-3 report (operator ask). Evidence in the probe
report relayed 2026-08-10; re-derive with the queries below, do not inherit counts.

## The defect

`_find_duplicate_game`'s same-perspective rule (E-278-02) narrows score agreement by
`_is_same_listing_delta` ≤ 1.0 second — calibrated on sub-second double-listings. A real
double-listing arrived 600 seconds apart: same date, same teams, same final score, 56
byte-identical plays, own-side batting lines identical including player ids. The rule failed
closed, a twin `games` row was filed mid-report-run, and the fallout chain was: twin has zero
spray rows → spray loader errors every run (its skip gate needs ≥1 row) → `spray_status=partial`
→ admin `degraded` badge, self-perpetuating across regenerations. Coach-visible damage: the
season record and every aggregate double-count the game ("35 of 34 games").

## Shape of the fix (spec decides; both halves)

1. **Detection**: the discriminator that actually separates this twin from a genuine
   doubleheader (per the E-278 taxonomy: 120-min gaps, different scores) is play-level
   identity — same date + same teams + same score + near-identical play count/content.
   Do NOT just widen the seconds window; pick a principled rule and re-verify the genuine
   doubleheaders stay unmerged.
2. **Repair**: `bb data merge-duplicate-games` (dry-run first) for the confirmed twin, then
   the four unverified candidate groups (2026-04-27, 2026-05-24, 2026-07-21 ×3 rows,
   2026-07-25 — the last is sub-second and today's rule should already catch it; verify).
   Then regenerate the affected report(s). Regeneration is DESTRUCTIVE; backup first.

## Addendum (2026-08-10 log audit)

Two facts for the spec's detection half: (1) a **960ms-apart** pair (2026-07-25 group) sits
WITHIN the 1.0s tolerance and still did not collapse — so the tolerance branch is not reached
on at least one path; establish why before redesigning the rule. (2) A new twin (identical
score AND identical start_time, rows created 10s apart under concurrent generation) was
race-created on 2026-08-10 — the concurrency stub (`2026-08-10-admin-generate-concurrency.md`)
owns the race; this spec owns merging the row and the detection rule.

## Candidate twin groups (verify each; genuine doubleheaders stay unmerged)

Post-load validation flagged two MORE groups during the 2026-08-10 serial repair, beyond the
four from the log audit: 2026-07-15 (teams 3/5) and 2026-04-10 (teams 427/642). Six candidate
groups total now; every one needs the doubleheader-vs-twin adjudication before any merge.

**Seventh group, and a NEW EVASION SHAPE (2026-08-10 probe):** a same-date, same-score,
same-start pair where the two rows record DIFFERENT home_team_ids for the same real opponent —
the natural key ({away, home_a} vs {away, home_b}) structurally cannot match them, so this class
evades the dedup entirely regardless of any timing window. Both rows carry full spray/plays, so
stats double-count. The detection redesign must handle opponent-identity divergence, not only
timing.

## Also observed, separate

- One never-crawled orphan one-sided game for the same team (created 2026-07-25, absent from
  the fetched schedule) — belongs to the residual-one-sided-game probe, not this chunk.
- A one-sided-perspective predicate found 5 such perspectives where the backfill's found 1 —
  likely predicate mismatch, worth reconciling when measured properly.

## Progress log

- **2026-08-10** — Stubbed from the probe. No writes, no merges run.
