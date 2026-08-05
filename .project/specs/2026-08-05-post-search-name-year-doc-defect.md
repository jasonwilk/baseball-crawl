# `post-search.md` says `result.name` "typically includes year" — the repo's own capture says 0/15

**Date:** 2026-08-05 · **Status:** **STUB — needs a probe, not an edit.**
**Source:** found while writing `2026-08-05-rung-c-search-resolve-recoverable.md`, where this
doc line was used as a load-bearing rationale and turned out to be contradicted by the repo's
own captured data. Nothing was changed either way.

## The claim

`docs/api/endpoints/post-search.md` (the `Field Reference` table):

> \| `hits[].result.name` \| string \| Team display name (typically includes year, e.g., "Team Name 2026"). \|

## The contradicting evidence

From `proxy/data/sessions/2026-03-11_032625/endpoint-log.jsonl` — the only real captured
`POST /search` response bodies in the repo (2 responses, 15 team hits) — **0 of 15 names
contain a 4-digit year**:

```
Northampton Nighthawks Navy 12U      Nighthawks Navy AAA 14U
Northampton Nighthawks Navy 10U      Northampton Nighthawks 11U Navy
Northampton Nighthawks 9U Navy       EYO Navy Nighthawks
Northampton Nighthawks 8U Navy       Nighthawks (Navy) 13U(AAA)
AAA Navy Nighthawks                  Gatorball Navy Nighthawks AA Division
```

(Regex `(19|20)\d{2}`, with a positive control proving it fires on `"Example Team 2026"`.)

⚠ **Why this is a STUB and not a fix.** Those 15 hits are **one query family** — a single
youth-travel club, captured 2026-03-11. That is strong evidence against "typically", but it
is not a census: HS and Legion teams may well be named differently, and the doc's claim may
have come from a real observation on a different population that simply was not captured
here. **Correcting a factual API-behavior doc on one query family would be trading one
unverified claim for another** — and `.claude/rules/api-docs.md` holds the factual record to
a live-verification bar.

## What a resolution needs

- A real `POST /search` probe across **several team-name families** — at minimum one HS
  program, one Legion team, and one youth/travel club — counting how many returned
  `result.name` values carry a year.
- Then one of: correct the line to what was measured, scope it ("names for
  *[population]* commonly include the year"), or drop the parenthetical if no pattern holds.
- Whatever lands, record the sample size and date, per the accuracy standard in
  `.claude/rules/api-docs.md`.

## Why it matters (beyond tidiness)

This line was cited as the reason to reject the documented **exact-name-match** auto-accept
criterion for opponent-resolution rung (c). The rejection still stands — canonical names
diverge from our free-text schedule names in word order and punctuation, which is visible in
the very list above (`Nighthawks Navy 10U` vs `Nighthawks 9U Navy`) — but it now rests on
that observation rather than on this doc line. **Anyone re-opening the name-match question
should not lean on this sentence until it has been re-measured.**
See `2026-08-04-rung-c-auto-accept-criteria-drift.md`.

## Out of scope

- Editing `post-search.md` from this stub alone.
- Re-opening the name-match criterion (a separate decision).

## Progress log

- **2026-08-05** — Stubbed. Measured 0/15 against the committed capture with a positive
  control; deliberately did NOT edit the endpoint doc, because a single query family is not
  the basis on which to rewrite a factual API record.
