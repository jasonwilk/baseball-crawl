# IDEA-192: Proxy-Session Endpoint Normalization and Data-First Capture

## Status
`CANDIDATE`

## Summary
Two reusable design fragments salvaged from E-072 (Proxy Session Ingestion Skill) when it was abandoned on 2026-07-26: (1) a concrete ruleset for normalizing captured proxy paths into the parameter-templated form used by `docs/api/endpoints/` filenames, and (2) the **data-first** insight -- the richer proxy endpoint-log format already carries `response_body`, so most endpoints need no curl recapture at all. The abandoned epic was a whole workflow skill; these two pieces are the parts worth keeping, and either can be applied by hand without the skill existing.

## Why It Matters
The normalization ruleset is the genuinely hard part of comparing a proxy session against our endpoint docs, and it was worked out in detail across four E-072 refinement passes (CA, SE, UXD, and three Codex rounds). Re-deriving it later would repeat that cost for no reason. The data-first insight matters more: whoever built the current session-ingest mental model assumed every undocumented endpoint needed a fresh authenticated curl, which is what made the workflow expensive, time-sensitive (the `gc-signature` expires within minutes), and credential-adjacent. If the response body is already sitting in the log, most of that apparatus is unnecessary.

**The normalization ruleset** (from E-072 Technical Notes, "Endpoint comparison logic"):
- UUID segments matching the 8-4-4-4-12 hex pattern become their placeholder names (`{team_id}`, `{game_stream_id}`, etc.).
- Short alphanumeric slugs under `/public/teams/` or `/teams/public/` become `{public_id}`.
- Multi-parameter paths must normalize **all** parameter positions, not just the first.
- Fallback: if a normalized path with named placeholders matches no existing doc filename, use `{id}` generically for all UUID-shaped segments and mark the candidate "placeholder names uncertain -- requires human review."
- Normalize **then** deduplicate before comparing -- a session with 50+ raw `/teams/{id}/opponent/{id}` paths collapses to one template.
- Exclude docs carrying `status: NOT_API` in frontmatter (`web-routes-not-api.md`) from the comparison set.
- `bb proxy endpoints` output is **raw and unnormalized** (literal UUIDs). It is not the normalized set and must not be treated as one -- read `endpoint-log.jsonl` directly and normalize in-agent.

**The data-first insight**: proxy sessions from 2026-03-12 onward use a richer endpoint-log format carrying `query_params`, `request_headers`, `response_headers`, `request_body`, and `response_body`. E-072's refinement measured `response_body` as populated for roughly 45% of entries (empty for OPTIONS, 304s, and auth errors). Detect the format by checking for a `response_body` key in the first JSONL entry. When picking among entries matching one normalized template, prefer the largest non-empty 2xx `response_body` by byte length, ties broken by earliest timestamp. **Security constraint that travels with this**: save only `response_body`. Never save or display `request_headers` -- they carry live `gc-token` values.

## Rough Timing
Someday. There is no pull today: this sat unpulled for roughly 4.5 months, which is why E-072 was abandoned rather than kept. Promote (or just apply the rules by hand) when a real proxy session needs processing and the manual comparison is actually painful.

## Dependencies & Blockers
- [ ] None technically -- the proxy addons (`proxy/addons/*.py`), the `bb proxy` CLI (`src/cli/proxy.py`), and the `ingest-endpoint` skill all still exist and work.
- [ ] The real blocker is demand: new-endpoint discovery volume has not justified automation.

## Open Questions
- Is the ~45% `response_body` population figure still accurate? It was measured during E-072's 2026-03-13 refinement against sessions from that period, and nobody has re-measured since. Treat it as a period observation, not a current fact.
- Does this belong as a skill at all, or as a short procedure inside the existing `ingest-endpoint` skill? E-072 assumed a whole new skill; that assumption is what carried the context-ratchet cost that helped kill it (trigger 7 gates `.claude/skills/**` line growth against a committed baseline, and a large new SKILL.md would need an operator-signed exception on top of an already-stale baseline).

## Notes
Source: extracted from E-072 at abandonment, 2026-07-26, on the operator's ruling. The full abandoned spec -- including the Phase 3 presentation format, the priority rubric, and the web-vs-mobile capture asymmetry -- is preserved in the archived epic at `/.project/archive/E-072-proxy-session-ingestion/` if more detail is ever wanted.

**This idea supersedes E-072 as the unblock pointer for [[IDEA-014]]** (Mobile vs. Web API Documentation Split), which listed "more proxy session data ingested (E-072 planning underway)" as a precondition. E-072 will never deliver that; if IDEA-014 is ever promoted, the session-processing capability it wants is described here instead.

One capture-asymmetry fact worth remembering independently of the rest, because it is a security policy rather than an implementation gap: **web-profile access tokens are obtained programmatically by `TokenManager` and never persisted to `.env`**, so generating a curl template for a web session would require displaying a live `gc-token`. Batch curl capture is therefore viable only for the mobile profile, which does persist `GAMECHANGER_ACCESS_TOKEN_MOBILE`. Do not "fix" this later by relaxing it.

---
Created: 2026-07-26
Last reviewed: 2026-07-26
Review by: 2026-10-24
