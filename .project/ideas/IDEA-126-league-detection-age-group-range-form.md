# IDEA-126: `detect_league_level` Misses GC's Free-Text `age_group` Range Form

## Status
`CANDIDATE`

## Summary
`src/reports/starter_prediction.py::detect_league_level` only recognizes the `\d+U` bracket form (e.g. `"14U"`) in its Priority-2 `age_group` branch. GameChanger also returns a free-text range form -- `age_group="Between 13 - 18"` -- which slips through to `"unknown"`, suppressing the "Most Likely Arms" projection and the Tier-2 AI "Scouting Analysis" for summer HS-age travel opponents that have no NGB. The API is giving us a valid HS-age level signal; the detector just doesn't read that format. This is a `starter_prediction.py` detection fix, not an API gap.

## Why It Matters
Discovered during a live-vs-dev report comparison for a summer HS-age travel opponent (real team name and public_id redacted here as PII). The report showed NO "Most Likely Arms" projection and NO Tier-2 AI "Scouting Analysis."

Root cause traced (with api-scout):
- `detect_league_level` resolves this team to `"unknown"` -> `get_rules_for_league` returns `None` -> `confidence="suppress"`, `suppress_reason="unsupported_level"` -> the generator then skips Tier-2 LLM enrichment entirely (`generator.py:~1343`).
- api-scout confirmed via a live `GET /public/teams/{public_id}` call for the opponent: `ngb="[]"` (empty), and `age_group="Between 13 - 18"` -- a real HS-age level signal.
- Because the only age branch matches the `\d+U` bracket form, the free-text "Between N - M" range slips through to `unknown` and suppresses, instead of routing to the intended `youth_travel` -> `PITCH_SMART_15_18` labeled-estimate path (built in E-243-02, `is_estimate=True`, banner-labeled).

Net effect: this class of opponent (summer season, HS-age, no NGB) gets a suppressed card today when it should get a directional Pitch Smart estimate.

## Proposed Direction
- Extend `detect_league_level` Priority-2 `age_group` handling to recognize the `"Between N - M"` range form (map an HS-age upper bound -> `youth_travel`), alongside the existing `\d+U` match.
- **Caveat 1 (band ambiguity):** `"Between 13 - 18"` spans three Pitch Smart bands (13-14 / 15-16 / 17-18); the engine only carries the 15-18 curve. Mapping a 13-18 bracket to the 15-18 (most permissive) curve is a reasonable directional estimate but over-permits genuine 13-14 arms -- acceptable for a *labeled estimate*, worth a code comment.
- **Caveat 2 (companion doc note):** `docs/api/endpoints/get-public-teams-public_id.md` documents `age_group` only via the `14U` example; the free-text `"Between 13 - 18"` range form is a real observed value and should be added to that field's description.

## Rough Timing
Unblocked, low-effort. Promote "when we prioritize the projection surface for travel opponents."

## Dependencies & Blockers
None. The estimate path this routes into already exists (E-243-02).

- [x] `youth_travel` -> `PITCH_SMART_15_18` labeled-estimate path exists (E-243-02)
- [x] Live-confirmed `age_group` range form observed (api-scout, on the redacted opponent)

## Open Questions
- Should the range parser generalize to any `"Between N - M"` (map the upper bound to the closest supported band), or narrowly match the observed HS-age range? Simple-first argues for a narrow upper-bound-to-band mapping with a comment.
- Are there other free-text `age_group` forms in the wild beyond `\d+U` and `"Between N - M"` that would still fall through to `unknown`?

## Notes
- Related: **IDEA-066** (League/Level Detection for Pitch Rules, PROMOTED -> E-218) established the detection machinery; this is a format-coverage gap in that machinery. E-243-02 built the `youth_travel` estimate path this fix routes into.
- **Unrelated background (context only, NOT in scope):** the same live comparison surfaced that the LIVE production DB shows an inflated record (31-4 vs GameChanger's official 26-4) from duplicate/phantom games that the current dev code (E-253: E-245 self-game fix + dedup) already corrects. The user chose idea-capture only and did NOT ask to act on that here. Mentioned as related background, not part of this idea's scope.

---
Created: 2026-07-12
Last reviewed: 2026-07-12
Review by: 2026-10-10 (suggest 90 days from created)
