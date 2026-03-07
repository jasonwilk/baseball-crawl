# IDEA-014: Mobile vs. Web API Documentation Split

## Status
`CANDIDATE`

## Summary
The API endpoint docs (`docs/api/endpoints/`) may need a more pronounced split between mobile and web profile behavior. The current YAML frontmatter has `profiles.web` and `profiles.mobile` status fields, but the documentation body does not strongly differentiate when endpoints behave differently across profiles (different headers, different response shapes, endpoints that only work on one profile).

## Why It Matters
As we discover more endpoints with profile-divergent behavior, the current format risks under-documenting critical differences. Coaches and operators rely on correct crawl configuration per profile. If an endpoint returns different data on mobile vs. web (or fails on one), that distinction needs to be front-and-center in the doc -- not buried in a YAML field. Accurate per-profile docs also inform crawl strategy (which profile to use for which data).

## Rough Timing
After more proxy session ingestion surfaces concrete examples of profile-divergent behavior. The trigger is: we have 3+ endpoints where the doc body needs to describe meaningfully different behavior per profile, and the current format feels inadequate.

## Dependencies & Blockers
- [ ] More proxy session data ingested (E-072 planning underway) to surface real examples of divergent behavior
- [ ] IDEA-011 investigation (HTTP 500 endpoints that work on mobile but fail on web) would provide concrete cases

## Open Questions
- What does "more pronounced" look like? Separate sections per profile in the doc body? Entirely separate files per profile? A tabbed/columnar format?
- Is the YAML frontmatter `profiles` field sufficient for machine-readable status, with the body handling the narrative? Or does the frontmatter itself need richer structure?
- How many endpoints actually diverge in practice? This might be a small-N problem that does not justify a format overhaul.

## Notes
- Related to E-072 (proxy session ingestion work, currently being planned).
- Related to IDEA-011 (HTTP 500 endpoints that succeed on mobile but fail on web).
- The current per-endpoint format was established in E-062. Any format changes would need to update the validation script (`scripts/validate_api_docs.py`) and the `.claude/rules/api-docs.md` loading discipline.
- The `ingest-endpoint` skill would also need updating if the doc format changes.

---
Created: 2026-03-07
Last reviewed: 2026-03-07
Review by: 2026-06-05
