# IDEA-171: `age_group` forms matching no pattern are read as no signal at all

## Status
`PROMOTED` — to **E-274** (`/workspaces/baseball-crawl/epics/E-274-age-group-level-signal/epic.md`), 2026-07-25.

**Two things this file got wrong that the epic corrects — read these before citing it:**
1. **The recommended fix is rejected.** This file says "any fix must normalize separators BEFORE matching." Normalizing `_`→space turns `middle_12U` into `middle 12U`, which DOES match `\b(\d+)U\b` and would route a middle-school team to the Pitch Smart 15-18 curve — a curve calibrated for the oldest band, which UNDER-rests a middle-school arm. The epic uses a known-value allowlist instead (E-274 TN-5).
2. **"Closed enum" is not supported.** api-scout attempted to certify the 7-value school family and could not — what exists is GC's display-mapper `switch` plus the creation picker, GC's own mapper carries a `default:` branch, and the picker offers only 3 of the 7. Treat the set as OPEN.

The "Evidence gap to close cheaply first" below is **CLOSED, POSITIVE** (25 non-managed opponent public profiles, unauthenticated; `high_junior_varsity` ×19, `high_varsity` ×6, plus `high_freshman` confirmed separately; zero auth-vs-public mismatches). The field is populated on 91/91 teams swept, and for LSB's HS schedule the school family is the only family that appears.

## Summary
`detect_league_level` recognizes exactly two `age_group` shapes — a single `\d+U` bracket and the free-text range form (`"13-18"`). Any third shape is not merely unmapped, it is **unread**: it falls through to name-keyword matching, and a team whose name carries no level word reaches `unknown` and gets its Most Likely Arms card suppressed. api-scout observed a live third form, `"high_freshman"`, which matches neither pattern.

## DIAGNOSIS UPGRADED 2026-07-25 — this is bigger and better-understood than as first written
This entry originally framed `high_freshman` as "a third `age_group` shape we do not parse." That undersold it. The operator pointed the team at GC team configs and api-scout verified against GameChanger's own web-bundle enum: **`age_group` is not an age-bracket field at all — it is a polymorphic three-family LEVEL field.**

- **school**: `high_varsity`, `high_junior_varsity`, `high_freshman`, `elementary`, `middle_12U`, `middle_13O`, `college`
- **travel**: `NNU` (e.g. `16U`) — the only family E-272's bracket ladder reads
- **recreational**: `"Between N - M"`

It is already on `GET /public/teams/{public_id}` (the response `_fetch_public_team_info` parses), populated on all 18 opponent profiles swept, and it **discriminates varsity / JV / freshman live**.

So this is not a parser gap around an odd string. It is a **structured, populated level signal that `detect_league_level` ignores** because its `age_group` handling tests only two of the three families. That reframes the idea from "handle one more form" to "read a level field we already receive" — and makes it the seed of a follow-up epic (suggested **E-274**) rather than a small fix.

**Two constraints any implementation must respect:**
1. **GameChanger has no "reserve" level.** The HS enum has three values, so LSB's four classifications do not map 1:1 — the two `high_freshman` teams on our own program are almost certainly Freshman + Reserve collapsed. Harmless for rest rules (both → `nsaa_subvarsity`), but **the level field cannot fully replace inference**, and a design premised on 1:1 mapping is wrong from the start.
2. **The value is self-reported by the opposing coach**, so it can be wrong or stale. It is a strong signal, not an authority — which is also why it weakens E-263-02c's premise (operator pick as PRIMARY mechanism) without eliminating the pick as a CORRECTION path.

**Evidence gap to close cheaply first:** api-scout has observed `high_varsity` / `high_junior_varsity` only on our OWN teams via `/me/teams`, never yet on an opponent's public profile. One public call settles whether the school family populates for opponents as reliably as it does for us — worth doing BEFORE any design depends on it.

**Status stays CANDIDATE, not closed.** The diagnosis is upgraded; the fix is still real work, and the trap below still applies to any implementation.

## Why It Matters
This is real coaching exposure, not a theoretical gap. An LSB-adjacent freshman opponent tagged `high_freshman` carries a perfectly good level signal — "freshman" is literally in the field — and the engine discards it, suppressing a card it had the information to populate. The signal is present and legible to a human; only the matcher cannot see it.

Worth being precise about the severity direction: the outcome is SUPPRESSION, not a wrong rest table. That is the safe failure — no coach is handed an incorrect rest number. But a suppressed card on an opponent we could have scouted is a silent loss of the feature's value, and it looks identical to "we have no data" rather than "we could not parse a field."

## THE TRAP — the obvious fix does not work
Anyone picking this up will reach for the existing `\bfreshman\b` pattern in `_LEVEL_WORD_PATTERNS` and assume it already covers the word. It does not, and the reason is easy to miss:

```
'high_freshman'   \bfreshman\b matches: False
'high freshman'   \bfreshman\b matches: True
'high-freshman'   \bfreshman\b matches: True
```

`_` is a **word character**, so there is no word boundary between `high_` and `freshman`. Space and hyphen both produce a boundary; underscore does not.

**Any fix must normalize separators BEFORE matching.** Otherwise the level-word patterns silently keep missing the very form the fix was written for — the failure mode preserved through its own fix, passing review because the pattern "obviously" contains the word. Verified by SE; recorded here so the next implementer does not lose a round to it.

## Rough Timing
Promote when either:
- A real opponent's card is observed suppressing on an unmatched `age_group` form (the concrete trigger — `high_freshman` is already live in the wild, so this may not be far off), or
- Someone is next working in `detect_league_level` for another reason and can fold in separator normalization cheaply.

Not urgent: the failure is safe-direction (suppression), and the population of affected teams is currently unquantified.

## Dependencies & Blockers
- [ ] None. E-272 shipped the ladder this would extend.

## Open Questions
- **How many distinct `age_group` forms exist?** api-scout has seen three (`\d+U`, the range form, `high_freshman`) on n=18. A wider sweep would size the problem before anyone builds a matcher — and might reveal `high_sophomore`, `high_jv`, or similar siblings, which would suggest a `high_<level>` family rather than a one-off.
- Is separator normalization enough, or does the `high_` prefix itself need handling? `high_freshman` presumably means "high school freshman" — the prefix is meaningful, not noise.
- Should an unmatched-but-non-empty `age_group` log a WARNING? It is a signal we received and could not read, which is exactly the observability gap [[IDEA-168]] raises for the season field. Same shape, different field.
- Does this interact with the bracket ladder's precedence? A `high_freshman` team is sub-varsity-aged, so if it ever became readable it would take the level-word path and be season-disambiguated — which is the correct outcome and needs no new precedence rule.

## Notes
Surfaced by api-scout's live probe during E-272 Phase 4 (n=18), and confirmed by SE as **pre-existing, NOT an E-272 regression** — SE ran `high_freshman` through a faithful reconstruction of both the pre-E-272 path and the shipped one and got identical results in all four cases. E-272 added the bracket ladder ahead of the name keywords without changing how an unmatched `age_group` falls through.

Kept as an idea rather than widened into E-272 scope: it is a new detection signal, not an epic AC, and SE explicitly recommended the ledger over scope-widening. Related: [[IDEA-168]] (the same "signal received, not acted on, no warning" shape, for the season field).

---
Created: 2026-07-25
Last reviewed: 2026-07-25
Review by: 2026-10-23
