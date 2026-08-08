# IDEA-002: Web Scraping Fallback Strategy

## Status
`CANDIDATE`

## Summary
When the GameChanger API cannot provide data we need, use browser automation or a managed scraping service as a fallback data access layer. This covers gaps where GameChanger exposes data in their web UI but not (yet) through a stable API endpoint.

## Why It Matters
The GameChanger API is undocumented and evolves without notice. There will be data we need -- specific game logs, roster history, opponent stats -- that is available in the GameChanger web interface but not surfaced by any API endpoint we can discover. Having a scraping strategy ready means a data gap does not have to block coaching workflows permanently.

## Rough Timing
When we hit our first real data gap during E-002 (Data Ingestion Pipeline) or E-003 (Data Model) work -- specifically when a crawl reveals that a stat or entity we need is not available via API. No urgency until that pain is felt.

Promotion trigger: api-scout or data-engineer identifies a concrete piece of data that is visible in the GameChanger web UI but unreachable via API.

## Dependencies & Blockers
- [ ] E-001-03 (API spec) must be substantially complete so we know what the API does NOT provide
- [ ] E-002 (Data Ingestion Pipeline) must be far enough along that we have encountered at least one real data gap
- [ ] Must evaluate whether GameChanger's Terms of Service permit scraping (legal/ethical review before building)

## Open Questions
- Does GameChanger's ToS prohibit automated browser access? (Check before building anything)
- Which specific data is missing from the API that would be worth the scraping complexity?
- Is "human in the loop" authentication a hard requirement, or can we automate it with stored session cookies?
- Which managed service is the right fit: self-hosted Playwright, or a cloud service (browserless.io, browserbase.com, scrapingbee.com)?
- How do we handle session expiration mid-scrape? Same credential rotation problem as the API, but harder.
- Can the Vercel agent-browser approach handle the auth flow, or is it too stateless?

## Notes
Candidate tools/services to evaluate when this becomes an epic:

- **browserless.io** -- https://www.browserless.io/ -- Managed Chrome/Playwright service. Good for headless automation without managing browser infra.
- **browserbase.com** -- https://www.browserbase.com/ -- Similar managed browser platform. Worth comparing pricing and reliability vs. browserless.
- **scrapingbee.com** -- https://www.scrapingbee.com/ -- Scraping-as-a-service with JS rendering. Handles proxies and detection avoidance automatically.
- **vercel-labs/agent-browser** -- https://github.com/vercel-labs/agent-browser -- Experimental agent-driven browser for AI workflows. Less battle-tested; worth watching.

Implementation constraints to carry forward when this is promoted:
- GameChanger login requires interactive authentication ("human in the loop") -- no simple headless login flow
- Must be strict about user agent strings and HTTP headers to avoid triggering bot detection
- Session cookie reuse strategy needed to minimize interactive login frequency
- All scraped data goes through the same raw -> processed pipeline as API data

Related: IDEA-001 (Local Cloudflare Dev Container) -- scraping jobs running locally or in a container may intersect with that workflow.

---
Created: 2026-02-28
Last reviewed: 2026-02-28
Review by: 2026-05-29
