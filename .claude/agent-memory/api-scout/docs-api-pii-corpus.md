---
name: docs-api-pii-corpus
description: docs/api example JSON embeds real captured UUIDs + some real team/venue/person names corpus-wide; a denylist can't make it clean, only a systematic sweep can; app-identity client IDs are NOT PII
metadata:
  type: reference
---

The `docs/api/` corpus embeds **real captured GameChanger data verbatim** far beyond any single audited team: real full UUIDs (event / player / team / game_stream / collection IDs, neither `-REDACTED` nor all-zero) appear in ~30 endpoint files, plus scattered real team/venue/person names in `"name"`/`"title"`/`"city"` example values (opponent teams, venues, an opponent player name). `.claude/rules/api-docs.md` mandates placeholder redaction for ALL UUID fields and PII-safe example values, but most of the corpus predates/violates that rule.

**Implication:** an enumerated denylist (block known identifiers) can verify a *specific* team's scrub but can NOT certify "no real identity in docs/api" — the real-example tail is open-ended. A truthful whole-corpus cleanup needs a **systematic sweep** (every UUID → placeholder; every example `name`/`title`/`city` → api-docs taxonomy placeholder) plus a forward-enforcement rule (positive: example JSON must use taxonomy placeholders), not another denylist entry. Each deeper grep pass finds more — don't promise corpus-wide cleanliness from a scoped scrub.

**Critical exclusion:** the UUIDs documented in `auth.md`, `headers.md`, `post-auth.md` (web client `07cb985d-…`, mobile client `0f18f027-…`, and sibling app-identity IDs) are GameChanger **app-identity CLIENT IDs — documented API constants, NOT personal/team PII**. They are the SUBJECT of those docs and must be EXCLUDED from any PII UUID sweep. See [[client-id-rotation]].

Surfaced 2026-07-06 during E-254-07 (endpoint-doc PII scrub) planning: that story scrubs one identified youth team + the own-program + enumerated adjacent opponents + the two named minors (21-token uncommitted denylist at `secrets/pii-denylist.txt` / ~24 files); the broader UUID+name tail (~28 files) was recommended as a follow-up (positive taxonomy rule, not enumeration) rather than ballooning the story mid-Codex. Specific identifiers are deliberately NOT listed here — this memory is version-controlled, so it must not itself carry the PII being scrubbed.
