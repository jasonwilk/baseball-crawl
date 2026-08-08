# IDEA-219: A third team's game was attributed to us because a free-text opponent string matched our name

## Status
`CANDIDATE` — **a phantom game row, disproven against GameChanger by impossible simultaneity. ⚰ The creating path was UNIDENTIFIED; it is now IDENTIFIED (2026-07-28) — see "The creating path" below. That was the important half, and it is answered.**

## The creating path (IDENTIFIED 2026-07-28)

**Two hops, both in the canonical team seam:**

1. **`_resolve_team_ids` branch 2 passes a free-text opponent NAME as the identifier.**
2. **`ensure_team_row` Step 3** (`src/db/teams.py:167-175`) matches on
   `WHERE name = ? COLLATE NOCASE AND season_year = ?` — a rung the module's own docstring
   calls **"weakest / heuristic."**

**Case-insensitive free-text name matching is the attachment mechanism: two distinct real
teams sharing a name within one season collapse onto whichever tracked row exists first.**

**Why this discharged the do-not-reset condition.** The evidence is **code plus
identifier-coverage statistics** — it does not depend on retaining the phantom row. Before
this, the row was the only known instance and had to be preserved; it no longer does.

**⚠️ Two caveats that bound the finding, both from its own author.**

- **The trace was read from the LOCAL CHECKOUT while the running prod image is ~8 days
  old.** **Confirm both hops in the ingesting build before treating the line references as
  exact.**
- **The prod census found ZERO confirmed instances among the 23 checkable teams — but only
  52 of 786 teams carry a `public_id`, leaving 142 of 192 games unverifiable. Zero-found is
  NOT absence**, and the coverage gap is the reason.

**Provenance:** relayed from a Live-side investigation whose full report lives on the prod
box (`/ephemeral/scratch/E278-PROD-INVESTIGATION.md`) and is unreachable from the dev
environment. Snapshot-dated 2026-07-28. There is no primary to check this against here.

**Why no story was added to E-278 (PM call, 2026-07-28).** The fix touches
`ensure_team_row`, a canonical seam with a wide blast radius, on the strength of zero
confirmed live instances — and E-278 was at its final gate. That combination is squarely the
operator's refine-before-build steer. **Promotion trigger is now sharper than "a second
phantom anywhere": the path is known, so the question is only whether to tighten the
name-only rung, and that is a scoping exercise rather than an investigation.**

## Summary

One `games` row in the 2026 season records a loss for our team in a game we did not play. It is a **third team's home game**: during that team's ingest, its free-text opponent string matched our team's name, and the row was linked to us.

**It is disproven rather than merely doubted.** Adjudicated against GameChanger's public data by api-scout: our team verifiably played a different game at the **identical instant**. Two games at one moment is impossible, so this is not a judgment call about which record is better — one of them cannot be ours.

The row has scores and no stat rows from our perspective, so it inflates the record header ([[IDEA-217]]) while appearing nowhere in the game logs or the footer count.

## Why It Matters

**The row is the small half; the creating path is the finding.** A phantom that exists can be deleted in a minute. A path that manufactures phantoms produces one per matching opponent string, forever, and nothing in the pipeline raises when it does — the row looks structurally identical to a real game.

It is also a **cross-team contamination**, which is a different and worse class than a duplicate. A twin ([[IDEA-218]]) is two records of one real game we did play. This is another program's game asserted as ours: a coach reading the header is being told about a loss that belongs to someone else, and any future surface that trusts `games` participation inherits it.

The suspected shape — a name-string match creating or resolving a team link — is one this codebase has already ruled on in a neighbouring place. The canonical team-creation cascade deliberately **refuses to attach `gc_uuid` or `public_id` on a name-only match**, on the stated grounds that a name-only identification is irreversible if wrong (`.claude/rules/architecture-subsystems.md`, Canonical Team Creation). If a free-text opponent string can nonetheless bind a game to a team by name, that caution is being enforced on one axis and not another.

## Rough Timing

**Two halves, and they are not the same urgency.**

- **The prod row**: promote whenever the operator wants the production header correct without waiting on the query fix. Note that [[IDEA-217]]'s header change makes the number right *without* deleting anything, so this is not blocking a correct report.
- **The creating path**: this is the one worth an epic's attention, and it should be identified before anyone concludes the incident is closed. **A single phantom is cleanup; a second phantom means an active creating path** — the same promotion trigger [[IDEA-196]] carries for its roster stub, and for the same reason.

## Dependencies & Blockers
- [ ] **Identify the creating path before designing any prevention.** Deleting the row without it fixes one instance of an unknown recurrence rate.

## Open Questions

- **Which code path bound a free-text opponent string to our team row?** Unidentified. The obvious candidate is the name+`season_year` match rung of the `ensure_team_row` dedup cascade, which exists precisely to resolve manually-typed opponents — but that is a hypothesis from reading the documented cascade, **not a diagnosis**, and it must be confirmed against the actual ingest path before anything is changed. A name-match rung that is correct for creating a *team* may still be wrong as the basis for attributing a *game*.
- **Does the third team's row carry a `progenitor_team_id`?** CLAUDE.md records its presence as meaning the coach linked the opponent via team lookup (a reliable signal) and its absence as meaning they typed the name by hand. That single field likely separates "our matching was too loose" from "the source data was ambiguous and we had nothing better to go on" — different problems, different fixes.
- **Which of the two phantoms does production carry?** Live shows 25-16 against dev's 25-17, so production has exactly one of this row and the [[IDEA-218]] twin. **The audit handoff does not record which**, and it decides whether a prod cleanup is a merge or a delete. One query.
- **Is impossible simultaneity reusable as a detector?** It is what settled this case, and it is mechanical: two `games` rows for one team at the same instant, or with overlapping windows, cannot both be real. Whether that is worth building as a standing check or is a one-off diagnostic technique is open — but it is a genuinely strong signal, and it needs no external adjudication.
- **How many more are there?** Nobody has swept. The same set-difference query that surfaced these two would surface others in the season.

## Notes

Found in the four-agent live-vs-dev report evaluation on 2026-07-26/27, by taking the set difference between `_query_record`'s predicate and `_query_freshness`'s and adjudicating each surviving row against GameChanger.

**⛔ Deletion is a destructive act on production data and is not authorized by this capture.** Establishing what created the row comes first — deleting the evidence before diagnosing the path is the sequence to avoid, since the row is currently the only known instance of whatever produced it.

Filed apart from [[IDEA-218]] deliberately. Both are phantom rows found in the same measurement and both inflate the same header, but a cross-team mis-attribution and a dedup-key gap share nothing beyond the symptom. Bundling them would let a carrier epic fix the tractable one and close the ticket.

Related: [[IDEA-217]] (the header that surfaced it), [[IDEA-218]] (the other phantom), [[IDEA-196]] (a production data residue on the same report, with the same "one is cleanup, two is an active path" trigger), [[IDEA-088]], [[IDEA-043]].

---
Created: 2026-07-27
Last reviewed: 2026-07-27
Review by: 2026-10-25
