# IDEA-129: Write-Only Raw API Response Archive

## Status
`CANDIDATE`

## Summary
Add a write-only archive of raw GameChanger API responses (append-only, keyed by endpoint + fetch time), so a debugging or replay session can inspect exactly what the API returned. Today the scouting/reports pipeline uses an in-memory crawl-to-load path that stores no raw payloads — once a report is generated, the raw JSON that produced it is gone.

## Why It Matters
The in-memory pipeline is deliberately simple (no disk intermediary — see CLAUDE.md "in-memory crawl-to-load"), but it leaves nothing to inspect after the fact. When a report looks wrong, there is no captured payload to diff against the parser output, and no way to replay a fetch offline. A cheap write-only raw archive would give:
- A debugging trail: "what did the API actually send for this game?"
- Replay capability: re-run the loader against a stored payload without re-fetching (and without live credentials).
- A regression fixture source: real payloads become test fixtures.

Note this is in tension with CLAUDE.md's Architecture note "Store raw API responses before transforming (raw -> processed pipeline)" — which the in-memory pipeline does NOT currently honor (that staleness is itself IDEA-flagged for the housekeeping epic). This idea is the "make the raw-archive claim true, on purpose, write-only" direction.

## Rough Timing
Someday / when a real debugging pain surfaces (a report that is wrong and cannot be diagnosed from the DB alone). No urgency — the pipeline works. Promote if raw-payload diffing becomes a recurring need, or if we want real-payload test fixtures.

## Dependencies & Blockers
- [ ] Decide storage shape: append-only JSONL vs. per-fetch files under `./data/raw/`, retention policy, and PII posture (raw payloads carry real names/UUIDs — must stay gitignored and honor the redaction discipline).
- [ ] Confirm it stays WRITE-ONLY (archive, not a cache the loader reads on the hot path) so it does not reintroduce a disk intermediary into the pipeline.

## Open Questions
- Where does the write hook live — inside the GC client, or at the loader boundary?
- Retention: bounded ring (last N fetches) vs. unbounded until manually pruned?
- Does this supersede or reconcile the stale CLAUDE.md "store raw before transforming" claim, rather than leaving both?

## Notes
Source: PLATFORM-AUDIT-2026-07-04 residual #10 (the in-memory-pipeline REVISIT left this residual). Related: the housekeeping-epic context-layer item that fixes the false "Store raw API responses before transforming" line in CLAUDE.md — this idea is the forward direction that line describes.

---
Created: 2026-07-12
Last reviewed: 2026-07-12
Review by: 2026-10-10
