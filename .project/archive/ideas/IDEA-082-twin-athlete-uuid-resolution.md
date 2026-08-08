# IDEA-082: GameChanger Active/Removed Athlete-UUID "Twin" Resolution

## Status
`CANDIDATE`

## Summary
Some opponent scouting reports are corrupted because one human is split across two
GameChanger athlete UUIDs -- an `active` (current-roster) record and a `removed`
(old) record -- so our per-UUID stat aggregation fragments their season into two
partial lines. Detect and merge these same-team "twins" deterministically (no LLM),
gating the merge on GameChanger's per-player `active`/`removed` status, and present
the human as a single canonical player.

## Why It Matters
GameChanger re-rosters teams mid-season. When a player's UUID is reissued, their
stats persist under the old (`removed`) UUID while new games accrue under the
`active` UUID. Our aggregation keys on UUID, so the report shows the same human
twice with split stats. Concrete case: team "Elkhorn North Equitable Bank Reserve"
(public_id `PkMl2UWGdrgG`) -- Pierson Kaufman appears as a 7-PA `#7 Kaufman`
(active) AND a phantom 34-PA + 13.2-IP `Kaufmann` (removed); his real ~41-PA /
13.2-IP line is shredded across two records and the report looks like a mess. A
read-only blast-radius scan estimates ~66-81 same-team twin candidates across
~10-11 of 125 tracked teams (~8%). Fixing this makes any affected opponent report
trustworthy instead of confusing.

## Rough Timing
After the user re-validates the blast-radius on a cleaner database (see Blockers).
Promote when an affected opponent is a real scouting target and the corrupted report
is felt as friction, or when the user prioritizes report-integrity work. No urgency
while the suite is green and unaffected teams report correctly.

## Dependencies & Blockers
- [ ] **Re-validate blast-radius on a clean database.** The current dev DB has
      accumulated state; the user wants the ~66-81-twin estimate re-confirmed against
      more/cleaner data before committing to an epic.
- [ ] **data-engineer ratifies the detection-source decision (X vs. Y)** -- see
      Open Questions. This is the central design choice and gates real story-writing.

## Open Questions
- **X vs. Y (the central design decision, for DE to ratify):**
  - **X (recommended):** Re-base twin detection on the per-player STAT tables (the
    authoritative same-team player set, carrying provenance) instead of
    `team_rosters`. Robust; decouples detection from roster ingestion; makes all
    ~81 twins detectable.
  - **Y:** Guarantee every stat-bearing player gets a `team_rosters` stub so the
    existing roster-JOIN detection works. Patches the symptom; keeps the current
    matcher but adds an ingestion obligation.
- Bucket-(a)-style cleanup aside: should `players.status` be a new persisted column
  fetched from `/players/{uuid}` (the proposed merge gate), or fetched on demand?
- Canonical-record policy confirmation: keep the ACTIVE record (roster name + jersey)
  and fold the removed twin's stats into it -- does this hold for every twin shape?

## Notes

### Proposed solution shape (deterministic, NO LLM)
- Re-base twin detection on the stat tables (the dominant fix -- makes all ~81 twins
  detectable; X above).
- Gate merges on GC `status` (`active`/`removed`); persist `players.status` (new
  column) from `GET /players/{uuid}`.
- Name matching is name-PRIMARY but shallow: exact, then <=1-edit last name. Status +
  temporal disjointness are CORROBORATION, not the primary key (temporal-alone
  false-positives on sparse-sample siblings).
- Canonical = the ACTIVE record (roster name + jersey); fold the removed twin's stats
  in.
- Run a single dedup sweep AFTER all stages (boxscore + plays + spray), not before.
- Blast-radius evidence supports deterministic-only: 66/66 real twins are shallow
  string variants; an LLM would risk false-merging the 38 sibling pairs. Explicitly
  NO Haiku (reserve any LLM only as a future operator-review suggester if a genuine
  nickname case ever appears).

### Empirically established (api-scout probe, 2026-06-21)
Source: all 46 Elkhorn games + roster + per-player records.
Memory: `.claude/agent-memory/api-scout/roster-vs-boxscore-identity.md`.
- Every boxscore carries a CONSTANT 25-UUID team-identity table; 14 are
  `status:"active"` (= the public roster) and 11 are `status:"removed"` (old records
  whose stats persist but are filtered from the roster). There is a cutover
  (~2026-05-06 for Elkhorn).
- 3 humans (Horn, Krapp, Kaufman) exist as BOTH an active and a removed UUID; the
  twins never appear in the same game (temporally disjoint). The other 8 removed
  records are genuinely former players (no active twin) and MUST be kept (real
  contributors, e.g. 19 IP).
- GC exposes NO same-human unification field: `person_id == own id` on every record
  (our docs were wrong; api-scout corrected
  `docs/api/endpoints/get-players-player_id.md` and
  `get-teams-public-public_id-players.md`); `/athlete-profile/{id}` is 403 for
  non-owned teams; `gc_athlete_profile_id` is never populated.
- `GET /players/{uuid}.status` (`active`|`removed`) IS reachable for tracked
  opponents and is a deterministic merge gate -- it is NOT present in the boxscore
  `players[]` array (only via the per-player record).

### Blast-radius (read-only scan, 125 tracked teams / 1,545 players-with-stats)
- ~66-81 same-team twin candidates across ~10-11 teams (~8% of tracked teams).
- Distribution: 64 EXACT same-name/different-UUID, ~2 last-name-variant
  (Kaufman/Kaufmann), ~1 first-name typo, ZERO genuine nickname-of-same-person.
- Separately: 38 same-surname/different-first SIBLING pairs (Will/Seth Bluvas,
  Traeton/Rylan Johnson...) that must NOT be merged, and 331 `Unknown`-first cameo
  pairs (separate data-quality issue, out of scope).

### Root cause (two read-only diagnostic agents, 2026-06-27 -- both converged)
1. **DOMINANT/structural:** detection is roster-dependent.
   `find_duplicate_players` (`src/db/player_dedup.py:104-136`) INNER-JOINs
   `team_rosters` to itself, so it only pairs UUIDs both present in `team_rosters`.
   60 of 81 twins (74%) are missed because boxscore-only tracked opponents have ZERO
   `team_rosters` rows -- on 8 of 11 affected teams EVERY twin is undetectable.
   `ensure_player_row` (plays/spray stubs) writes only `players`, never
   `team_rosters`, so those twins are invisible even to the manual
   `bb data dedup-players` CLI.
2. **Secondary:** exact last-name equality (`COLLATE NOCASE`) has no fuzzy/prefix
   tolerance, so Kaufman/Kaufmann slips through even when both ARE rostered.
3. **Tertiary:** ordering -- the in-pipeline sweep (Hook 1,
   `scouting_loader.py:142-157`) runs BEFORE the plays/spray stages
   (`generator.py:1772,1775`) create new stubs; no post-stage sweep.
- **RULED OUT:** team/perspective provenance is FINE (both twins carry the same
  `team_id` + `perspective_team_id` -- do NOT touch the perspective machinery);
  season_id mismatch is ruled out (`team_rosters`/`games` are cleanly year-only
  post-E-241).
- **Cautions:** the current matcher already surfaces 88 "Unknown Unknown"/initial-stub
  junk pairs (broadening detection needs a name-quality/status gate); Hook 1 swallows
  dedup exceptions silently.

### Non-goals
Don't touch perspective provenance; don't drop removed-only players; don't merge
siblings; don't touch the 331 Unknown-first cameos; no LLM.

### References
- `src/db/player_dedup.py:104-136` (roster-JOIN detection)
- `src/reports/scouting_loader.py:142-157` (Hook 1 in-pipeline sweep)
- `src/reports/generator.py:1772,1775` (plays/spray stage stub creation)
- `.claude/agent-memory/api-scout/roster-vs-boxscore-identity.md`
- `docs/api/endpoints/get-players-player_id.md`,
  `get-teams-public-public_id-players.md` (api-scout corrections)
- `.claude/rules/data-model.md` -- "plays pipeline dedup gap" + "merge-every-run
  cycle" notes
- Related ideas: IDEA-043 (fuzzy duplicate TEAM detection), IDEA-046 (resolver
  duplicate gc_uuid).

---
Created: 2026-06-27
Last reviewed: 2026-06-27
Review by: 2026-09-25 (90 days from created)
