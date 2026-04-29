# IDEA-084: crawl_jobs.games_crawled Column Cleanup

## Status
`CANDIDATE`

## Summary
Either define semantics and start writing the `crawl_jobs.games_crawled` column, or drop the column in a future migration. Today the column exists in `migrations/001_initial_schema.sql` but no code path writes to it -- verified during E-229 iter-1 review.

## Why It Matters
Schema fields with no writers create maintenance debt: future engineers reading the schema assume the column carries information, write queries against it, get NULLs back, and then have to chase whether the NULLs are "real zero" or "never populated." The `games_crawled` Python attribute that everyone references in `trigger.py` / `cli/data.py` / `crawlers/scouting.py` is a dataclass field on `ScoutingCrawlerResult` / `ScoutingSprayChartResult`, completely separate from the SQL column -- this name collision compounds the confusion.

## Rough Timing
Promote when: (a) someone tries to use `crawl_jobs.games_crawled` and discovers the gap, OR (b) the next migration that touches `crawl_jobs` (good moment to either fill in or drop the column).

## Dependencies & Blockers
- [ ] Decide whether to populate or drop -- a quick design conversation
- [ ] If populate: `run_scouting_sync` is the natural writer; needs an UPDATE of the row before terminal status
- [ ] If drop: standard migration

## Open Questions
- If we populate it, what does it count -- `games_crawled` from `ScoutingCrawlResult` (boxscores fetched) or some other definition?
- Is there UI surface (admin dashboard, sync history page) that should display the value if we keep it?

## Notes
Surfaced during E-229 iter-1 review (DE follow-up Q2). Earlier DE assertion that the column "already exists" was verified narrowly (the column exists in the SQL schema) but DE corrected: NO code path writes to it. Filed at E-229 closure per Closure Tasks section.

---
Created: 2026-04-29
Last reviewed: 2026-04-29
Review by: 2026-07-28
