# IDEA-096: Systematic docs/api PII sweep (blanket UUID + positive placeholder rule)

## Status
`CANDIDATE`

## Summary
E-254-07 scrubs the 24 endpoint/flow docs that carry the AUDITED identified team's identity (the identified opponent team + the operator's own program + BOTH real minors — names AND player UUIDs, pulled forward), verified by a 22-token denylist byte-gate. During that review, api-scout found the denylist can't guarantee "no real identity anywhere in `docs/api/`" — there's a broader real-PII tail OUTSIDE E-254-07's scope, ~28 distinct files in two classes: **Class A** — real full UUIDs (event / game_stream / player / team / opponent / collection / series / avatar IDs, ~23 files) EXCLUDING the two minor PLAYER UUIDs (now handled in E-254-07) but INCLUDING the deferred opponent-TEAM UUID; **Class B** — real ADULT team/venue/tournament names (~11 files). This idea is the systematic sweep to close the whole tail.

## Why It Matters
The audit + E-254-07 removed the specific flagged identity, but example JSON across the wider API-doc set still commits real UUIDs and real names. A blocklist (denylist) is inherently incomplete — it only catches what it enumerates. The durable fix is a POSITIVE rule ("all example JSON in `docs/api/` must use the api-docs.md placeholder taxonomy; real UUIDs → all-zero/redacted") enforced going forward, plus a one-time blanket sweep of the existing docs. A likely-minor player name in the tail makes closing it more than cosmetic.

## Rough Timing
Promote after E-254 closes (don't balloon a mid-review story). A natural next PII-hardening slice. Escalate sooner if the possible-minor name is deemed high-priority to remove immediately (could be pulled into a small targeted fix).

## Dependencies & Blockers
- [ ] E-254-07 complete (establishes the harness + taxonomy pattern this reuses).
- [ ] api-scout produces the complete file+identifier inventory (offered) — the full list of tail files, real UUIDs, and residual names.

## Open Questions
- Blanket UUID sweep mechanics: a regex that redacts all real-looking UUIDs to all-zero, with an EXCLUSION allowlist for GameChanger app-identity CLIENT IDs (documented API constants in `auth.md` / `headers.md` / `post-auth.md` — the web/mobile client UUIDs — which are the SUBJECT of those docs and MUST stay).
- Enforcement: a positive example-JSON-placeholder rule (context-layer) + a re-runnable check (relates to the E-254 Open-Questions "denylist as re-runnable check" item), rather than an ever-growing denylist.
- Should the likely-minor player name be pulled into E-254-07 as a targeted add now, or wait for this systematic sweep? (PM/user call.)

## Notes
Surfaced by api-scout during the E-254 Codex-review triage while confirming the P1-07 org/event token coverage. E-254-07's Description was narrowed to its audited/enumerated scope so it does not over-claim; this idea holds the remainder. Related: the E-254 Open-Questions context-layer follow-ups (taxonomy bare-prefix clarification + denylist-as-re-runnable-check).

**Concrete Class-B instance found during E-254-07 dispatch (2026-07-07)**: a THIRD person name (a likely own-roster minor's name — the exact identifier is withheld here per Decision #2) was found in `docs/api/endpoints/patch-players-player_id.md`, OUTSIDE the 22-token E-254-07 denylist. api-scout scrubbed it to a placeholder for hygiene during the scrub (gate-neutral, since it's not a denylist token), but flagged that it (and likely more own-roster/opponent names) belongs in THIS systematic tail and/or the real denylist. This is a concrete confirmation that the tail contains at least one more likely-minor name beyond the two E-254-07 pulled forward — reinforcing that the systematic sweep is more than cosmetic. When this idea is promoted, api-scout's full inventory (held outside git, per Decision #2) should enumerate all such residual names.

---
Created: 2026-07-06
Last reviewed: 2026-07-07
Review by: 2026-10-04
