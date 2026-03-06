# IDEA-011: Investigate HTTP 500 Endpoint Failures

## Status
`CANDIDATE`

## Summary
Three GameChanger API endpoints return HTTP 500 with web browser headers but succeeded during iOS proxy capture. The root cause is unknown. This idea covers systematically investigating why they fail and how to make them work.

## Why It Matters
These three endpoints could unlock high-value coaching data:
- `GET /me/related-organizations` -- organization discovery for multi-team management
- `GET /organizations/{org_id}/teams` -- all teams in an org in a single call
- `GET /organizations/{org_id}/opponent-players` -- bulk opponent roster at org level

The server errors reference undefined pagination properties (`page_starts_at`, `page_size`), but we do not know whether the fix is mobile-specific headers, different pagination query parameters, a different `gc-app-version` value, or something else entirely. We only know that:
1. Web browser headers (Chrome 145 profile) produced HTTP 500
2. iOS Odyssey app headers (captured via mitmproxy proxy) produced HTTP 200

## Rough Timing
After E-049 completes (dual-header system and full endpoint documentation are prerequisites). The mobile credential capture workflow from E-049-06 enables the experimentation this idea requires.

Promote when:
- A coaching use case needs org-level data (standings, team lists, opponent rosters at org scope)
- Mobile credentials are available for controlled testing
- The dual-header system (E-049-05) is in place for easy profile switching

## Dependencies & Blockers
- [ ] E-049 complete (dual-header system, endpoint docs, mobile credential capture workflow)
- [ ] Mobile credentials captured via mitmproxy (at least one valid iOS token)

## Open Questions
- Is the failure caused by missing headers (e.g., `gc-app-version`, `x-gc-features`, `x-gc-application-state`)?
- Is it caused by missing query parameters (e.g., `page_starts_at`, `page_size` as URL params rather than headers)?
- Do these endpoints work with web headers plus just the `gc-app-version` header added? (minimal delta test)
- Are there other endpoints that fail similarly but were not in our bulk collection?
- Does the iOS proxy capture show specific query parameters on these endpoints that the web collection missed?

## Notes
- The error messages (`Cannot read properties of undefined (reading 'page_starts_at')` and `'page_size'`) are JavaScript server-side errors, suggesting the API server expects these values to be present somewhere in the request and crashes when they are not.
- Extracted from E-049-04 (ABANDONED) per user feedback (2026-03-06): the "mobile-only" label was a hypothesis, not a fact. This idea captures the investigation work without presupposing the answer.
- The proxy capture data at `proxy/data/endpoint-log.jsonl` may contain request details (query params, headers) for the iOS requests that succeeded -- this should be the first place to look.
- Raw error payloads: `data/raw/bulk-20260305-234522/me-related-organizations.json`, `org-teams.json`, `org-opponent-players.json`

---
Created: 2026-03-06
Last reviewed: 2026-03-06
Review by: 2026-06-04
