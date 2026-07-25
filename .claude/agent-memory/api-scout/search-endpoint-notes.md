---
name: POST /search query parsing behavior
description: Empirical findings on how GC's POST /search handles punctuation and Unicode, from probes on 2026-04-16 and 2026-04-17
type: reference
---

# POST /search Query-Parser Behavior

## Hit Shape — NO `age_group` / `competition_level` (CONFIRMED 2026-07-25)

Verified across **150 hits** from 6 queries: every hit is `{type, result}` with

```
result.{id, public_id, name, sport, season.{name, year}, location.{city, state, country}, avatar_url, type}
```

`age_group` and `competition_level` are **absent** — not null-valued, genuinely not in the
payload. So the `public_id`→`gc_uuid` bridge **cannot** supply the level field; the public
team profile is the only cheap source (see [[public-team-age-group-level-field]]). Note the
season object here IS nested (`result.season.name` / `.year`), which is a **different shape**
from the public team profile's flat `team_season.season` string — do not conflate them
(see [[public-team-profile-season-shape]]).

This also undercuts the *inferred* schema in the `/search/opponent-import` doc, which
speculates those fields exist there (see [[search-opponent-import-regression]]).

## Diacritic Folding (CONFIRMED 2026-04-17)

GC's search backend folds diacritics to ASCII at query time. A query containing accented Latin letters returns hits on the first attempt; no client-side normalization is required for accented-letter names to match indexed teams.

Evidence (2026-04-17 probe, 27 queries total):
- `Kéarney A's 10U` (U+00E9) → 1 hit, matched indexed "Kearney A's 10U"
- `Kearñey A's 10U` (U+00F1) → 1 hit, same team
- `Rivérside Varsitybaseball Acme` → 1 hit, matched "Riverside Varsitybaseball Acme"
- `Piñata` → 23 hits; `Pinata` → 24 hits (near-identical result sets)

**Implication**: a normalization fallback in caller code that strips accents (`[^A-Za-z0-9 ]+`) is lossy without being necessary. The narrower `[^\w ]+` regex (Unicode-aware `\w`) preserves accented letters, matches GC's own folding on the retry path, and avoids introducing false positives where accent-stripped tokens collide with a different indexed team name.

## Non-Latin Scripts (PARTIAL 2026-04-17)

CJK ideograms appear to be ignored as tokens by GC's parser:
- `野球` alone → 25 hits, total_count=10000 (likely unfiltered match)
- `Morris 野球 Baseball` → 1 hit (baseball team — GC tokenized around the CJK, matched on Latin tokens)
- `Morri野 Baseball` (CJK glued to Latin token) → 1 hit (GC tokenized around the CJK as if it were whitespace)

Cyrillic / Arabic probes returned 0 hits, but the queries weren't validated against known-indexed teams, so cannot conclude the 0 is char-caused vs. no-match.

## Punctuation Failure Claims — NEEDS RE-VERIFICATION

The 2026-04-16 probe claimed 4 ASCII characters kill queries: `/`, `'` (U+0027), `%`, `#`. The 2026-04-17 refined probe did NOT reproduce the straight-apostrophe failure:
- `"Kearney A's 10U"` (U+0027) → 1 hit, same team as curly-apos form
- `"Varsity'Baseball"` → 1 hit

Possibilities: (a) GC's query parser was updated between 2026-04-16 and 2026-04-17; (b) the original failure was context-specific (depended on surrounding tokens); (c) the straight-apos failure requires a specific query shape that wasn't reproduced. The defensive punctuation-fallback approach in the client remains sound (zero cost when names work on first attempt) but the canonical "straight apos always returns 0" claim is not currently reproducible. Flag for re-probe next time a full punctuation sweep is warranted.

## Regex Narrowing Recommendation

When writing normalization fallbacks for POST /search:
- **Prefer**: `re.sub(r"[^\w ]+", " ", name, flags=re.UNICODE)` — strips punctuation, preserves Unicode letters (accented Latin, CJK, Cyrillic, etc.)
- **Avoid**: `re.sub(r"[^A-Za-z0-9 ]+", " ", name)` — strips accents AND CJK, lossy for operator-typed input, can produce false-positive matches by collision (e.g., `Müller` → `Miller`)

Both handle the known punctuation failures identically; the narrow form just doesn't damage what GC would have parsed correctly on its own.
