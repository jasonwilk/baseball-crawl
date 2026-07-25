# IDEA-181: TBD / tournament schedule placeholders are being stored as opponent `teams` rows

## Status
`CANDIDATE`

## Summary

Schedule placeholders — not teams — are landing in the `teams` table as opponents. Found while probing `resolve156.json` during E-274 planning (2026-07-25): of the 156 entries examined, **20 fall into a `NON_TEAM` bucket** that is not a classification failure at all. Observed values:

```
TBD May 16, 2026
South Tournament
TBD- 05/30/26, 3:00 PM
TBD- 06/14/26, 4:00 PM
```

These are a coach's placeholder text for an unscheduled slot or a bracket-to-be-assigned, typed into GameChanger's manual opponent-entry flow. They arrive on the schedule exactly like a real free-text opponent name and nothing downstream distinguishes them, so they become rows.

**This is an INGESTION concern and is independent of the classifier work.** `detect_league_level` returning `unknown` for `TBD May 16, 2026` is the correct answer — the input is not a team. E-274 neither creates nor fixes this, and no `age_group` / league-detection change touches it.

Cited from the E-274 session handoff — `/workspaces/baseball-crawl/.project/research/2026-07-25-session-handoff.md`, the `CORRECTION (2026-07-25, next session)` note in the artifact-inventory section.

## Why It Matters

Two consequences, and they are separable:

**1. It inflates any denominator drawn from "teams that fail to classify."** The suppressed-card figure quoted during E-274 planning was *46 of 156*. The buckets account for 64 + 46 + 26 = **136**; the missing 20 are the `NON_TEAM` bucket. **The honest figure is 46 of 136 (34%), not 46 of 156 (29%)** — the rate is *worse* than reported, because the denominator was padded with rows that were never eligible to classify. Any future measurement over "unclassified opponents" inherits the same padding unless it excludes these first. This is the same population-vs-number failure family E-274 logged five instances of; the number was right and the noun was wrong.

**2. Orphan-reclamation and dedup passes are carrying rows that can never resolve.** A `TBD- 05/30/26, 3:00 PM` team has no `public_id`, no roster, no games it can ever be a real participant in, and no path to resolution — but it is a `teams` row, so `reclaim_orphan_reference_data`, `cleanup_orphan_teams`, and `search_teams_by_name` all have to reason about it, and `bb report map-opponent`'s unresolved-opponent surface can present it to the operator as something to map. It is permanent, un-actionable inventory in the reference tier.

Severity is low and the direction is safe — nobody gets a wrong rest number or a wrong stat from a placeholder row, and the card correctly suppresses. What makes it worth recording is that it is **silent and monotonic**: every season adds more, none ever resolve, and the only symptom is a slowly-degrading denominator in measurements nobody suspects.

## Rough Timing

No pain felt yet. Natural triggers:
- Someone next measuring opponent classification coverage (the denominator bug bites immediately and invisibly).
- Someone working the unresolved-opponent operator surface, where these show up as noise in a list meant to be actionable.
- Any deliberate pass over `teams`-row hygiene.

Not urgent enough to displace anything. **Scope deliberately not decided here** — captured, not designed, per the routing instruction.

## Dependencies & Blockers
- [ ] None hard.

## Open Questions

- **Where is the right seam — reject at ingestion, or classify-and-mark?** Refusing to create the row is cleaner but throws away the fact that the schedule slot exists; a `is_placeholder` marker keeps the slot and lets every reader filter. The two imply very different blast radii.
- **Is a predicate even safely writable?** `TBD`-prefixed and `Tournament`-suffixed are the observed shapes, but this is free text a coach types — `Tournament` in particular is a legitimate token in real team names, and a bias-to-refuse predicate that keeps a real team is right where one that drops it is not. Needs the observed corpus enumerated before anyone writes a regex.
- **How many exist in the live DB right now, and what do they participate in?** The 20 came from one probe artifact, not from a `teams` query. If any placeholder row has games or stats attached, that is a different and worse finding than inert inventory.
- **Do these interact with the cross-perspective game dedup?** Two schedules could each carry their own `TBD` text for the same real slot. Unknown whether that has produced anything.
- **Are they already being swept?** E-273's `reclaim_orphan_reference_data` hard-deletes unreachable `teams`, and a placeholder with no games and no report may already qualify as an orphan — in which case the population is self-limiting and only the denominator half of this idea survives. **Check this first; it could shrink the idea to a measurement note.**

## Notes

Found by the main session while probing `resolve156.json` during E-274 planning; routed to PM for capture with an explicit "do not scope a fix." The probe artifacts carrying the raw values are the **untracked** `/workspaces/baseball-crawl/.project/research/E-274-probe/` (`resolve156.json`, `probe_results.json`) — the values quoted above are placeholder strings, not identifiers, so they are safe to record here verbatim, but the surrounding real team names are not and are deliberately not committed.

Related: [[IDEA-156]] (completed-games-with-data `team_id` predicate — same "which rows are real participants" question at the games grain), [[IDEA-171]] (promoted to E-274, the classifier work this is independent of), [[IDEA-157]] (dedup fork refusal — adjacent `teams`-row hygiene).

---
Created: 2026-07-25
Last reviewed: 2026-07-25
Review by: 2026-10-23
