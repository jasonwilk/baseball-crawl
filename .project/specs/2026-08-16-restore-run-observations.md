<!-- NO REAL NAMES OR IDENTIFIERS — no person's name, ever; teams by id/role only. -->

# Restore-run observations — six needs-a-look items, none yet adjudicated

**Date**: 2026-08-16 · **Status**: `STUB` — a triage list, not a chunk. Adjudicate each item to
"fix chunk / noise / already-covered" at the next audit or when the counted rebuild is specced;
none is established enough to spec today.
**Source**: trainer log sweep of `ephemeral/2026-08-16-report-restore/regenerate-20260816-204714.log`
(34-of-71 snapshot) plus read-only DB cross-checks. Re-derive; counts move as the run finishes.

1. **Roster counts ~2× expected on 13 teams, ON A FRESHLY PURGED DB** — e.g. team 1174
   expected 17, found 48. First question: does the post-load validator measure BEFORE the
   dedup sweep runs (making this timing noise), or after (making it a regression of the
   chunk-14 fix)? Answer that before anything else.
2. **19 "duplicate game" validator warnings across 11 teams** — the validator's definition
   (same date, same team pair, ×2) also matches genuine doubleheaders, which the E-278
   taxonomy says are exactly that shape. Likely mostly false alarms from a validator that
   predates the taxonomy; verify against the doubleheader floor before treating as dedup
   escapes.
3. **Partial plays coverage never degrades a report** — 5 runs with plays_covered below
   expected (e.g. 42 of 45) still recorded `completed`, no `degraded` status, no explaining
   log line. Decide: is a coverage gap a degradation or expected charting absence?
4. **`enrichment_status` is NULL for every CLI-generated run and 'success' for the one
   UI-generated run** — the CLI path never writes the column. Dead schema or missing step;
   pick one and make it true.
5. **Spray loader skipped 11.8% of rows (11,165 of 94,239) with zero errors and zero reason
   codes** — spread is wide (0% to 45% per team). Unauditable as logged; minimum fix is a
   reason-code breakdown on the skip counter.
6. **Passkey login fails on a port mismatch** (unrelated to the run): client origin
   `http://baseball.localhost:8000` vs expected `:8001` — the traefik-vs-direct port split.
   Real login papercut; smallest possible fix chunk or a config note.

7. **CLEAR DEFECT, promote at next adjudication — a transient DNS failure publishes a report
   titled "Unknown" and calls it success.** One firing on the full run: `Could not fetch public
   team info ... ConnectError: Temporary failure in name resolution` → report generated with
   `team=Unknown`, status `ready`, served, and the driving script sees `OK`. Fail or retry;
   never publish "Unknown". (Also the run's only network fault: an in-container DNS blip.)
8. **`Cross-perspective dedup` collapses on score-match alone when start times DISAGREE by
   minutes** (2 firings, e.g. 19:20 vs 19:30 "treating as duplicate because per-team scores
   match (8-8)"). Same family as the same-listing window rules — check this branch's warrant
   against that spec's fitted-bound reasoning before the rebuild trusts it.

Also for the record: the half-pair defect fired 8 times in this run with exact 1:1 symptom
pairing (dedup score-disagree ↔ plays-derived disagree on identical game ids) — priority
confirmation for the already-stubbed fix, no new work here. And the app suggested
`bb data dedup-players` for one surviving pair — operator action, not a chunk.

## Progress log

- **2026-08-16** — Stubbed from the trainer's log sweep, mid-run. Final-tail re-sweep owed
  when the 71-team run completes.
