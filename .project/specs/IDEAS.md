# Ideas

Someday-work, one line per idea. No template, no numbering, no statuses, no index. Add a line when
something is worth remembering but is not broken and not owed; curate the list at the per-3-chunk
audit. An entry becomes a spec only when the operator decides to work it.

**The three-way split, so it cannot blur**: broken or owed → a spec stub in this directory; someday →
one line here; product direction → `docs/vision-signals.md`.

The pre-2026-08-08 ideas tree is frozen at `.project/archive/ideas/` (234 ideas + its README). It is
history: salvage from it on demand, never bulk-migrate it here.

**PII posture, stated narrowly.** `.project/specs/` is not in the pattern scanner's `SKIP_PATHS`, so
unlike the frozen tree this file is scanned — but that buys **credential / email / phone** coverage
and **nothing against names**, which is the class that actually bit (a real minor's name in an idea
file, remediated in E-254 Phase-4b). Both trees are, and were, covered by the doc-PII byte-gate. So
this is a real improvement in a class orthogonal to the one failure on record — it does not make
ideas safe. Never paste a real name or identifier here; use the placeholder taxonomy in
`.claude/rules/api-docs.md`.

## Ideas

- Jersey-corroborated scorekeeper spelling variants in converged rosters (chunk-14 measurement:
  8 pairs across 13 teams, 6 jersey-corroborated) — coach-visible wart the dedup deliberately
  leaves; candidate polish after the ingestion campaign closes. First routed here at audit 5,
  which found this list empty three audits in.
- Index the six `_TEAM_STAT_EXISTS` columns, or stop asking the question per-team. The orphan
  deletability check is a correlated EXISTS evaluated per candidate, and four of its six
  subqueries have no usable index (`spray_charts.team_id`, `plays.batting_team_id`,
  `reconciliation_discrepancies.team_id`, and `perspective_team_id` on those three) — so a team
  with NO stat rows, which is exactly the deletable case, costs four full table scans. Measured
  on the live dev DB during the orphan-cleanup chunk (2026-08-17): ~50 ms warm per stat-free
  team, ~2.5 s on a 50-team batch, against a generation already spending tens of seconds on
  network. Both closers are worse trades today — a hand-written six-table set query reintroduces
  the drift that chunk existed to close, and an index migration pays write amplification on
  ~770k rows of load-path inserts. Revisit if orphan batches reach the hundreds or
  `reconciliation_discrepancies` keeps growing.
