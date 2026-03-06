# IDEA-012: Crawl Orchestration and Scheduling System

## Status
`CANDIDATE`

## Summary
A system for scheduling, monitoring, and managing recurring crawl runs -- including credential rotation awareness, run history tracking, error alerting, and automated crawl/load cycles on a schedule.

## Why It Matters
After E-050 (bootstrap), the operator can run a full crawl-and-load cycle with one command. But this is still manual -- the operator must remember to run it, check for errors, and refresh credentials before they expire. For a system tracking 4 Lincoln teams + opponents across a 30-game season, manual triggering becomes tedious. A scheduling system would keep data fresh automatically and alert the operator only when intervention is needed (expired credentials, API errors, etc.).

## Rough Timing
After E-050 (bootstrap) is complete and the operator has run several manual crawl cycles. The pain of manual triggering will become clear during the first few weeks of the season when games happen every 2-3 days and data needs refreshing after each game.

**Promotion trigger**: The operator has run the bootstrap manually 5+ times and finds it tedious, OR the season starts and data freshness becomes a daily concern.

## Dependencies & Blockers
- [ ] E-050 (credential bootstrap) must be complete -- provides the pipeline to schedule
- [ ] E-042 (admin team management) should be complete -- DB-driven team config is the expected source
- [ ] Need to decide: cron-based scheduling (simple, external to app) vs. in-app scheduler (more complex, self-contained)
- [ ] Need to decide: alerting mechanism (email via Mailgun? Dashboard notification? Log-only?)

## Open Questions
- Should scheduling be cron (external) or in-app (e.g., APScheduler)?
- What is the right crawl frequency? After every game? Daily? Twice daily?
- Should the system auto-detect when a game was played and trigger a crawl?
- How should credential expiry warnings work? 3 days before expiry? 1 day?
- Should crawl history be stored in the database (for admin UI display) or just in log files?
- Does the system need to handle partial failures gracefully (e.g., one crawler fails, others succeed)?
- Should there be a "health" page in the admin UI showing last crawl time, credential expiry, and error counts?

## Notes
- `scripts/crawl.py` already handles partial failures (logs error, continues to next crawler, writes manifest with error counts)
- `scripts/load.py` similarly handles partial failures
- The simplest v1 might just be a cron job calling `python scripts/bootstrap.py` with a wrapper that emails on failure
- Credential expiry can be predicted from the JWT `exp` claim without making an API call
- Related ideas: IDEA-008 (plays/line scores crawling) and IDEA-009 (per-player game stats) would add more crawlers to the orchestration pipeline

---
Created: 2026-03-06
Last reviewed: 2026-03-06
Review by: 2026-06-06
