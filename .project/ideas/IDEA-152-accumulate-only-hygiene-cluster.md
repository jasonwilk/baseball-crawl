# IDEA-152: Accumulate-Only Hygiene Cluster (no-coach-impact re-run residues)

## Status
`CANDIDATE`

## Summary
A consolidated cluster of seven accumulate-only re-run residues that are DB bloat / internal-only — real mechanisms, but none corrupts a number or view a coach sees. Grouped because each is individually low-value and they share the same "second run leaves a residue nothing prunes" root; promote as a batch (or cherry-pick) when the pain is felt. (Hazards H5, H6, H7 + corner cases CC-3, CC-5, CC-6, CC-7.)

## Why It Matters
None of these are coach-facing (verified two-channel for H5/H6/H7; single-channel for the CCs), so none is urgent. But they steadily accumulate and one (CC-7) monotonically degrades a real operation (team-deletion cascade) over a season. Worth a batch clean-up eventually.

## The findings (each with file:line anchor — full detail in the master record)
- **H5** — `reconciliation_discrepancies` unbounded per-regeneration accumulation. Fresh `run_id`=uuid4 per game per run; full signal row-set (incl. MATCH) re-written every regen; nothing prunes. Readers take latest-per-key so summaries self-heal → bloat, not corruption. `engine.py:111-112,251-257`; `generator.py:964-975`; migration `001:536`. Fix direction: prune old run_ids.
- **H6** — Renamed-opponent duplicate `teams` row + orphaned prior-run child anchors. Name-only resolution misses a rename → new team row; per-run `_cleanup_orphans` reaps only THIS run's teams. REFUTED corruption (reports are `public_id`-anchored + subject-scoped, stranded rows never queried). `teams.py:167-187`; `generator.py:2225-2251`. Fix direction: retire renamed-opponent orphans.
- **H7** — `season_id` drift orphans children when `teams.season_year` changes. COLLAPSED: only SPRAY vanishes (`_query_spray_charts` filters `spray_charts.season_id`); plays refuted; roster self-heals. Low prob under single-season scope. `generator.py:1664`; `game_loader.py:1371`. Fix direction: re-key or re-derive spray `season_id` on drift.
- **CC-3** — Jersey NULL-clobber: roster upsert overwrites jersey unconditionally incl. with NULL (`scouting_loader.py:418-426`); boxscore path is backfill-only (`game_loader.py:1556-1565`) — divergent. A roster payload omitting `number` nulls a known jersey. Coach-facing-MINOR (a jersey number can blank), but grouped as hygiene. Fix direction: unify the two upsert paths (backfill-only for both).
- **CC-5** — ERA basis `innings_per_game` write-once (`teams.py:357-380`): a mid-season 7→6 change never propagates; ERA computed on stale basis WITHOUT the "(assumed)" flag. Fix direction: allow the basis to update on re-scrape.
- **CC-6** — Failed-after-HTML-write generations leak orphan HTML files no sweep reaps (`generator.py:2494-2519`). Disk-only. Fix direction: reap failed-row on-disk files.
- **CC-7** — Reports-row accumulation monotonically degrades team-deletion cascade: `_live_report_perspective_ids` treats any reports row as a live dependency (`lifecycle.py:363-381`); nothing auto-deletes reports/`report_generation_runs`/`scheduled_report_runs` → cascade-delete becomes progressively partial over a season. Fix direction: age-out or cascade the report rows.

## Rough Timing
Promote (whole cluster or a subset) on real pain: a bloated table observed, a partial team-deletion, or a blanked jersey. No urgency. CC-3 (jersey) is the most coach-adjacent — pull it first if a jersey blanks.

## Dependencies & Blockers
- [ ] None hard-blocking. Cross-link [[IDEA-134]] (play-level cross-perspective duplication — same accumulate-only / redundant-storage family).

## Open Questions
- Soft-retire (marker/flag) vs. hard-delete for the bloat tables — the same open question E-267 must answer for its retire-absent machinery; align on one convention.
- Which of the seven are worth a fix at all vs. accepted steady-state (H6 corruption is refuted; H7 is spray-only under single-season scope).

## Notes
- Source: 2026-07-19 accumulate-only re-run audit (H5/H6/H7 two-channel; CC-3/5/6/7 single-channel). Master record: `.project/research/2026-07-19-rerun-accumulate-only-audit.md`.
- Related: E-267 (retire-absent machinery — shares the soft-vs-hard retire decision), [[IDEA-134]] (play-level cross-perspective dup).
- **Standing test requirement (operator directive 2026-07-19):** any future promotion of any finding in this cluster MUST ship a regression test that reproduces the residue (fails pre-fix) and asserts the clean state (passes post-fix). Gate every ingestion change against the E-257 reconciliation-scoreboard ratchet.

---
Created: 2026-07-19
Last reviewed: 2026-07-19
Review by: 2026-10-17 (suggest 90 days from created)
