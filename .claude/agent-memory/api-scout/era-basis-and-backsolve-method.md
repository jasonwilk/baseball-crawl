---
name: era-basis-and-backsolve-method
description: GC ERA/rate-stat basis field (settings.scorekeeping.bats.innings_per_game) + the reusable back-solve method for reverse-engineering how GC computes any rate stat
metadata:
  type: reference
---

# GC ERA basis field + rate-stat back-solve method

Discovered 2026-07-14 via live empirical investigation against owned+opponent teams (motivated E-264 "League-Aware ERA Basis Fix").

## Endpoint-schema fact: the game-length basis field

- **Field:** `settings.scorekeeping.bats.innings_per_game` on `GET /teams/{gc_uuid}`
  (Accept `application/vnd.gc.com.team+json; version=0.10.0` — same pin as `TEAM_DETAIL_ACCEPT` in `src/gamechanger/opponent_ladder.py`).
- **Type:** integer. Observed 6 and 7 only.
- **Per-team-season constant**, NOT age/level-derived. Two 12U teams differed (6 vs 7); an 8U/9U/10U were 7; travel-ball seen at BOTH 6 and 7. Never infer from `age_group`/`classification`.
- **Opponent-capable:** returned for non-owned teams given the `gc_uuid` (3/3 tracked opponents returned it). BUT `GET /teams/{gc_uuid}` can RAISE 403 (ForbiddenError/CredentialExpiredError) for some teams — wrap the fetch, treat as unreadable.
- **NOT on the public profile:** `GET /public/teams/{public_id}` has no `settings` object. Resolve `public_id`→`gc_uuid` via the search bridge, then hit the authenticated endpoint. (Contrast: `season-stats` is 403 for opponents; team-metadata is not.)
- **`bats` = GC's baseball-sport subkey** (softball would differ). Fine here — baseball-only.
- **Fallback when unreadable = 7** (modal, correct for HS/Legion/13U+/most youth). Never 9 for youth/HS; never an age table.

## How GC uses it (all verified full-precision, zero scatter)

- `ERA = innings_per_game × ER / IP`
- `K/G = innings_per_game × SO / IP`  (our docs mislabeled this "per 9 innings" — it's per game-length)
- These two are the ONLY game-length-dependent pitching rates. Everything else is game-length-independent:
  `BB/INN = BB/IP` (per single inning), `WHIP = (BB+H)/IP`, `K/BF = SO/BF`, `K/BB = SO/BB`, `BAA = H/AB`.
- GC exposes **no** `K/9` or `BB/9` keys at all.

## IP format gotcha (API vs UI)

The API returns IP as **true fractional innings** (e.g. `51.6667` = 51⅔, `53.3333` = 53⅓), NOT the "51.2" display format shown in the GC UI. Compute `outs = round(IP×3)`, or work directly in innings. Do not treat the fraction as tenths. (This bit me on the first pass — the buggy tenths conversion still rounded to the right integer but wasn't exact.)

## REUSABLE METHOD: back-solving "how does GC compute X"

When GC returns both a computed rate stat and its raw inputs, recover the hidden multiplier/basis by algebra:

1. For a rate `R = k × numerator / denominator`, solve `k = R × denominator / numerator` using season TOTALS per pitcher AND the team aggregate (large samples kill rounding noise).
2. Use the **API's full-precision** value (GC returns e.g. `6.113207547169812`, not the 2-decimal UI value) — so `k` resolves to an exact integer with zero scatter. If it scatters, your input conversion (e.g. IP→outs) is wrong, not GC.
3. Cross-check across teams that SHOULD differ (here: teams known to play 6- vs 7-inning games) to prove the basis is a real per-entity variable, not a global constant.
4. Confirm the recovered basis against any candidate explicit field (here `innings_per_game`) — walk the full response key tree (recursively) and regex for `inning|regulation|length|scheduled|game_type|format` to find where GC stores it.
5. Check whether the field is per-GAME or per-entity: if the season aggregate collapses to a single `k` with no blending, it's a flat per-entity constant (here: per-team-season), and there's no per-game field.

This method generalizes to any "what denominator/weight does GC use for stat Y" question.
