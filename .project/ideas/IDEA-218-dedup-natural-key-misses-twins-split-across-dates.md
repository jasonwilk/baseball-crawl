# IDEA-218: A cross-perspective twin whose two rows carry different `game_date` values can never be deduped

## Status
`RESOLVED` (2026-07-28, by E-278) — **the mechanism was established BY EXECUTION, and it was none of the three candidates below as written. Forward prevention shipped in E-278-04; the existing rows are resolved by the operator's data reset.** Annotated rather than rewritten: the reasoning below is a record of what was and was not known, and its central instinct was right.

> ## ✅ The mechanism, established by execution (E-278 TN-1)
>
> **One perspective's payload carries the timezone `US/Central`; the other carries `America/Chicago`. These name the same real zone — but `US/Central` is a legacy tzdata "backward" alias that DOES NOT RESOLVE in our runtime** (`python:*-slim` omits the backward links and `tzdata` was not a declared dependency). So `derive_local_date` raised `ZoneInfoNotFoundError`, logged a WARNING, and **fell through with the datetime still in UTC**, returning the UTC calendar date. For an evening game whose start instant has already crossed 00:00Z, that is the next day.
>
> **Two counterfactuals were EXECUTED, not reasoned:** repair only the alias and change nothing else → both perspectives yield the same date (**the alias failure is the necessary cause**); keep both aliases and equalize the instants → no split (**the 2.5-hour instant disagreement alone does not split**).
>
> **This capture's insistence on establishing the mechanism first was CORRECT and is the reason the fix landed on the right line.** Scoring the three candidates it named:
> - **Candidate 1** (different `last_scoring_update` instants) — **REFUTED by counterfactual.** The instants did disagree, by 2.5 hours, and that alone produces no split.
> - **Candidate 2** (different or absent `timezone` values) — **closest, but not for the stated reason.** It is not that "the same instant converts to different local dates"; it is that **one zone string fails to RESOLVE at all** and the conversion never happens.
> - **Candidate 3** (one perspective hit a fallback path) — **REFUTED AS WRITTEN, and this is the trap.** `derive_local_date` returned a date STRING, not `None`, so `_derive_game_date`'s `[:10]` unparseable-instant fallback **never fired**. A *different* fallback fired, in a *different* function. **A fix aimed at the `[:10]` fallback would have been a no-op.**
>
> ## ⛔ The stated REMEDY is false for this capture's own case
>
> *"The offline corrective already exists (`bb data merge-duplicate-games` …), so this is a gap in the live prevention path rather than a missing capability."* — **`plan_duplicate_game_merges` groups by `(season_id, game_date, unordered pair)`, so the offline tool CANNOT REACH a date-split twin either.** The date gate this capture correctly identifies in the live path applies to the offline path as well. There was no working corrective on either surface.
>
> ## What shipped
>
> **E-278-04**: `tzdata` declared as a runtime dependency (resolving the entire alias namespace rather than two observed instances), plus fail-closed degradation — an unresolvable zone now yields a sentinel rather than a plausible wrong date. **A SECOND, independent mechanism was found in the same investigation** and shifts dates the OPPOSITE way (−1 day): a full-day calendar event's `start_ts` is a DATE MARKER that was being localized as an instant. Both are fixed; a uniform date-shift repair would have corrupted one population while fixing the other.
>
> ⚠️ **Line citations below have ROTTED** — `game_loader.py:1183` and `:146-165` both moved substantially across E-278's four stories. Navigate by symbol.

## Summary

`GameLoader._find_duplicate_game` (`src/gamechanger/loaders/game_loader.py:1183`) finds candidates with `WHERE game_date = ? AND status = 'completed' AND game_id != ? AND (…team pair…)`. **Date equality is a hard gate on candidate selection** — confirmed by reading the query, not relayed. Doubleheader disambiguation by `start_time` and score totals happens *after* that gate, so it never sees a row the gate excluded.

One real game in the 2026 season is persisted as two `games` rows under the two perspectives' event ids, carrying **different `game_date` values**. The natural key (date + unordered team pair) therefore matches nothing, the twin is never collapsed, and both rows count toward the record header ([[IDEA-217]]).

## ⚠ The mechanism as relayed does not match the code — establish it first

The audit reported the cause as *"the two perspectives' start instants land on different UTC calendar dates."* **That phrasing is not what `game_loader` does**, and a fix designed against it would be aimed at the wrong line:

- `_derive_game_date` (`game_loader.py:146-165`) derives the date from **`summary.last_scoring_update`**, not from a start instant.
- It converts through the canonical venue-local seam `derive_local_date(instant, tz_name)` (`src/util/timezone.py:78`), using `summary.timezone` when present and falling back to the operating-timezone seam. **A raw UTC date slice is only the unparseable-instant fallback**, and `"1900-01-01"` is the absent-instant sentinel.

So there are at least three candidate explanations and nobody has separated them: the two perspectives report **different `last_scoring_update` instants** (each scorebook last touched at a different moment) for a game that ended near local midnight; the two perspectives report **different or absent `timezone` values**, so the same instant converts to different local dates; or one perspective hit a fallback path. **These imply different fixes.** Establish which before touching anything — this is the first step, ahead of any remedy.

Note that `_derive_game_date` is documented as the SINGLE derivation shared with `ScoutingLoader`'s schedule-count precompute, and its docstring already warns that the two must key on an identical date string or the tolerant same-game signal silently key-misses. That warning is about a different divergence than this one, but it is the same brittleness and the same function.

## Why It Matters

`.claude/rules/canonical-seams.md` states the project's position plainly: **prevention over cleanup** — `_find_duplicate_game` exists precisely so cross-perspective twins are collapsed before insertion rather than repaired afterwards. A twin that slips the natural key defeats that design silently: nothing errors, nothing warns, and the duplicate is simply persisted.

The blast radius is wider than the record header this was found through. A twin is two `games` rows for one real game, each with its own child surface, so anything counting or summing over games that does not perspective-scope can double-count it. E-259's query-time season aggregates are protected by the `perspective_team_id` filter, which is why this did not show up as doubled batting lines — but that filter is a per-query discipline, not a structural guarantee, and the standing invariant in `.claude/rules/perspective-provenance.md` exists because omitting it is easy.

The offline corrective already exists (`bb data merge-duplicate-games` over the canonical `merge_duplicate_game` seam, E-261), so this is a gap in the *live* prevention path rather than a missing capability.

## Rough Timing

**Promote when the mechanism is established, or fold into the next epic touching `game_loader`'s dedup path.** The investigation is small and should probably just be run: pull the two rows' `game_date`, `start_time`, and the summary fields they were derived from, and compare.

Not urgent as a coach-facing matter once [[IDEA-217]] lands — the header stops counting it. It stays worth fixing because it is a **prevention-path** defect that will recur on any game with the same shape, and each recurrence leaves a permanent duplicate.

## Dependencies & Blockers
- [ ] **Establish the actual mechanism** (above). Everything else waits on it.

## Open Questions

- **Which of the three candidate causes is it?** See above. Unseparated.
- **Should the natural key tolerate an adjacent date at all?** A ±1-day window would catch this class but is a real loosening — it puts genuine consecutive-day games against the same opponent (common in tournament play) into the same candidate pool, where they would then rest entirely on the `start_time` and score-total tiebreakers. **Widening a dedup key is a merge risk, and a wrong merge is destructive**, so this needs weighing against fixing the derivation instead. Fixing the derivation is the narrower change if the derivation is what is wrong.
- **How many other twins are already persisted with this shape?** One was found because it landed in a record-header discrepancy. Nothing has swept for the general case, and a query for same-team-pair rows on adjacent dates with disjoint perspectives would answer it. That number decides whether this is one repair or a cleanup pass.
- ✅ **ANSWERED, and "possibly the whole finding" was closer to right than the question knew.** *Original text preserved:* **Is `last_scoring_update` the right basis for a calendar date at all?** It is the instant a scorekeeper last touched the book, which for a game finishing late, or edited the next morning, is not the date the game was played. Raised, not answered — and possibly the whole finding.
  > **The field was misNAMED rather than misCHOSEN.** On the public scouting path it was never populated from a last-scoring instant at all — `_build_games_index_from_data` fills it from `start_ts`, falling back to `end_ts`. So the value was usually right and the name described a different datum, which is precisely what made this question unanswerable from the name alone. **E-278-05 renamed it to `date_source_instant`** and documented how it differs from the adjacent `start_time` (the fallback chain: this field falls back to `end_ts` then `""`, while `start_time` takes `start_ts` alone). The underlying date defect was real but had a different cause — see the mechanism block at the top.

## Notes

Found in the four-agent live-vs-dev report evaluation on 2026-07-26/27, by adjudicating the record-header set difference against GameChanger. Both rows of the pair are real data about a real game; neither is junk.

**⛔ Cleanup is a separate, destructive act and is not authorized by this capture.** The correct tool is the canonical `merge_duplicate_game` seam (via `bb data merge-duplicate-games`), never a hand-deletion of one row — the seam re-points all six `games` FK children and deletes the losing row last, and it refuses fail-closed when the two rows share any `perspective_team_id`. Read `.claude/rules/canonical-seams.md` before touching either row.

Deliberately filed apart from [[IDEA-219]]: both are phantom rows found in the same set difference, but that one is a cross-team mis-attribution at ingest with an entirely different cause and remedy. Same symptom, unrelated diseases.

Related: [[IDEA-217]] (the header that surfaced it — fixable independently), [[IDEA-219]] (the other phantom row), [[IDEA-220]] (a double-load found in the same pass, possibly the same game — check before assuming), [[IDEA-124]].

---
Created: 2026-07-27
Last reviewed: 2026-07-27
Review by: 2026-10-25
