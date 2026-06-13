---
name: e235-trust-block-review
description: E-235 trust block design consultation and holistic review outcomes — signal set, severity tiers, operator/coach split, and defect found in AC-2
metadata:
  type: project
---

## E-235 Trust Block Design (2026-06-13)

Epic E-235 (Report run records + trust signals + quality gates, ROADMAP slice B). Coach was consulted during planning and performed the holistic review of story 07 (footer trust block) and story 03 (quality gates).

### Signal Set (frozen, coach-authoritative per TN-7)

Footer line: `Through {date} (N of M games) · Pitch detail for {K} games · spray {available/unavailable} · Generated: {date}`

- "Through {date}" = last completed game date (freshness)
- "Generated: {date}" = report build date (separate from freshness — matters for scheduled delivery)
- "Pitch detail" = bench-readable rename of "plays data" (jargon avoided)
- "loaded" jargon dropped; bare numbers or "found" preferred
- M = games PLAYED to date, NOT total scheduled

### Three Severity Tiers

| Tier | Condition | Action |
|---|---|---|
| quiet | coverage ≥ 80% AND no degraded-confidence flag | Plain text, no alarm |
| flagged | coverage 50–79% OR any operator integrity flag set | Show generic degraded-confidence line |
| loud | coverage < 50% | Prominent warning |

**Critical clarification (found as defect in AC-2 during review):** The degraded-confidence warning line appears in ALL THREE severity states whenever `degraded_confidence` is true. Coverage severity (quiet/flagged/loud) and data-reliability warning are INDEPENDENT signals — both show when both conditions apply. The original AC-2 only attached "→ show the degraded-confidence line" to the "flagged" tier, omitting the loud case. PM fixed this before READY.

### Operator/Coach Flag Split

- `season_fallback` and `identity_match_method = 'name_only'` → **admin run record ONLY**
- Coach footer: generic degraded-confidence line ONLY when either flag is true: `⚠️ Data accuracy may be limited. Contact your operator to verify before the game.`
- Rule: if a coach can't act on it from the bench, it belongs in the admin record, not the footer

### No-Games Outcome

Explicit named message (never a silent empty report):
> `No completed games found for {Team Name} this season. If this looks wrong, verify the team URL and try again.`

Admin run record distinguishes: `games_expected == 0` (early season, no games played) vs `games_expected > 0 AND games_loaded == 0` (games played, none loaded).

### K=0 Edge Case (advisory, noted during review)

"Pitch detail for 0 games" is awkward coaching language. Preferred: "No pitch-detail data" when K=0. Left to implementer judgment.

### Defect Found in Review

AC-2 in story 07 defined "→ show the degraded-confidence line" only under the "flagged" tier. The "loud" tier definition was silent on whether the warning line also shows when `degraded_confidence` is true. Fixed by PM before READY (added clarifying sentence to TN-7 and AC-2).

**Why:** Coverage severity and data reliability are independent coaching signals. A <50% coverage report with a name-only match needs BOTH the loud indicator AND the warning line.
