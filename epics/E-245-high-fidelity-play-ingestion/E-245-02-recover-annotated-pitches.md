# E-245-02: Recover annotated pitches, capture type/velocity, reload affected games

## Epic
[E-245: High-Fidelity Play Ingestion](epic.md)

## Status
`TODO`

## Description
After this story is complete, the plays parser will correctly classify pitches that carry a
trailing type/velocity annotation (instead of dropping them), so `pitch_count` and
`is_first_pitch_strike` reflect reality for every team — including those whose scorekeepers chart
pitch type. The parser will also capture each pitch's `pitch_type` and `pitch_speed_mph` into the
columns added in E-245-01. A one-time, operator-runnable reload mechanism re-derives the affected
already-loaded games so the fix applies to historical data, not just future reports.

## Context
This is the highest-value fix in the epic. `PlaysParser._classify_template`
(`src/gamechanger/parsers/plays_parser.py`) exact-matches the bare pitch vocabulary and drops any
annotated pitch as `event_type='other'`, which is what produced the impossible FPS 3.4% on the
Empire Netting & Fence Sr. Legion report. ~5,841 pitch events across 29 games are stranded (~5,328
on team 133 alone). The authoritative grammar and parsing rules are in the endpoint doc (epic
TN-1/TN-2); the reload requirement (already-loaded games will not self-heal) is in epic TN-3.

Forward-path vs reload-path is the distinction to hold (TN-3a): on the FORWARD parse path (new
reports), the derived flags (`pitch_count`, `is_first_pitch_strike`, `is_qab`) recompute
automatically once annotated pitches classify as `event_type='pitch'`, because the parser has
`final_details` in memory — no separate change beyond the classification fix (AC-1). On the RELOAD
path (already-loaded games), `final_details` is NOT available, so the parent flags are NOT automatic:
`pitch_count` and `is_first_pitch`/`is_first_pitch_strike` re-derive from the recovered pitch events
(AC-4/AC-5), and `is_qab` recomputes via the TN-3a OR-merge (AC-6) — never a from-scratch
`_compute_qab`. E-245-04 (self-game fix) reuses this story's reload entry point, which must also
re-derive `batting_team_id` from the current games-row home/away (AC-9, TN-3b); see Handoff Context.

## Acceptance Criteria
- [ ] **AC-1**: Given a pitch template carrying any annotation form — `(<type>)`, `(<speed> MPH <type>)`,
      or `(<speed> MPH)` — when the parser classifies it, then it is `event_type='pitch'` with the
      correct `pitch_result`, per the grammar in epic TN-2. Bare pitches continue to classify
      correctly. Verified with fixtures covering all three annotation forms plus the bare form,
      interleaved within one game.
- [ ] **AC-2**: Given an annotated pitch, when it is parsed and loaded, then `play_events.pitch_type`
      holds the parsed type (or NULL if absent) and `play_events.pitch_speed_mph` holds the parsed
      integer speed (or NULL if absent); a bare pitch leaves both NULL (epic TN-4).
- [ ] **AC-3**: Given the strip-and-match rule, when a NON-pitch (mid-AB / substitution /
      baserunner) template contains parentheses, then it is NOT misclassified as a pitch — the
      strip is gated on the post-strip base being a known pitch template (epic TN-2).
- [ ] **AC-4**: Given an already-loaded game whose pitches were dropped, when the reload mechanism
      runs, then the affected `play_events` rows are re-derived (dropped pitches reclassified,
      type/speed populated) and the parent `plays.pitch_count` is recomputed, with no API re-fetch
      required (epic TN-3). Boxscore-derived `player_game_*` and season-aggregate rows are left
      untouched.
- [ ] **AC-5**: Given a reloaded game, when `play_events.is_first_pitch` and
      `plays.is_first_pitch_strike` are re-derived, then they reflect the recovered annotated pitch
      as the true first pitch (they are NOT trusted from stored values, which are wrong on affected
      games — epic TN-3a).
- [ ] **AC-6**: Given the reload recomputes `plays.is_qab`, when it runs, then it uses the OR-merge
      in epic TN-3a (`stored_is_qab OR check_2s_plus_3 OR pitch_count >= 6`) and NEVER a from-scratch
      `_compute_qab`. Verified specifically: an HHB-only QAB (a hard-hit ball with `pitch_count = 0`
      pre-reload) SURVIVES the reparse — its `is_qab` stays true (no false-negative regression from
      the unavailable `final_details`).
- [ ] **AC-7**: Given the reload mechanism is run twice, when it completes, then it is idempotent
      (re-running does not double-count or corrupt counts).
- [ ] **AC-8**: Every `play_events` / `plays` write continues to carry `perspective_team_id` on the
      parent `plays` row per `.claude/rules/perspective-provenance.md` (no regression).
- [ ] **AC-9**: Given the reusable per-game reload entry point, when it rebuilds a game's plays, then
      it re-reads home/away FRESH from the current `games` row and re-derives `batting_team_id` per
      `half` (a no-op when `home != away`; the exact mechanism E-245-04 relies on after it corrects a
      self-game's home/away) — per epic TN-3b.

## Technical Approach
Apply the documented grammar (epic TN-2): strip a trailing `(...)` group gated on the base being a
known pitch template, then sub-parse the inner annotation into optional speed and type. Flow the
two new fields through the parser's per-event dataclass and the loader INSERT into the new columns.
For the reload (epic TN-3), the full annotated text is retained in `play_events.raw_template`, so a
re-parse of stored rows can recover everything without re-fetching from the API; the parent
`plays` flags derive from the events and must be recomputed. Two reload-path subtleties are
mandatory (epic TN-3a): recompute `is_qab` via the OR-merge (NOT a from-scratch `_compute_qab`,
because `final_details` is not persisted), and RE-DERIVE `is_first_pitch` / `is_first_pitch_strike`
rather than trusting the stored (wrong) values. The reload mechanism is MANDATED (epic TN-3), not an
implementer's choice: an in-place re-derivation whose SOURCE is `play_events.raw_template`, which
NEVER invokes `parse_game`. Clear-and-re-ingest is forbidden here — deleting `play_events` would
destroy `raw_template` (the only DB copy) and force an API re-fetch, breaking AC-4. Follow the
`bb data backfill-appearance-order` precedent for the one-time operator command. Do not run the
reload in the worktree (epic TN-9) — verify via fixtures/unit tests; live-DB recovery is
operator-verified.

## Dependencies
- **Blocked by**: E-245-01
- **Blocks**: E-245-04 (E-245-04 reuses this story's reload to re-derive `batting_team_id`; also a shared `src/cli/data.py` surface)

## Handoff Context
- **Produces for E-245-04**: a reusable per-game reload entry point that, for a given
  `(game_id, perspective_team_id)`, re-derives a game's `play_events` + parent `plays` flags IN PLACE
  from `play_events.raw_template` (TN-3 mandate) — including re-reading home/away FRESH from the
  current `games` row and re-deriving `batting_team_id` per `half` (AC-9, TN-3b). E-245-04 calls this
  AFTER it corrects a self-game's home/away, so the re-derivation yields the correct `batting_team_id`.
  Design the per-game core as a callable function, not only a batch CLI command, so E-245-04 reuses
  it for the post-correction plays re-derivation.

## Files to Create or Modify
- `src/gamechanger/parsers/plays_parser.py` (classification + annotation sub-parse; per-event dataclass fields)
- `src/gamechanger/loaders/plays_loader.py` (write the two new columns)
- A reusable per-game IN-PLACE reload entry point — a callable function in `src/` (e.g. alongside the plays loader) exposed via a `bb data` subcommand in `src/cli/data.py`. This is CONCRETE and REQUIRED (not optional): it is the artifact E-245-04 reuses (TN-3b). Contract: for a `(game_id, perspective_team_id)`, re-derive `play_events` + parent `plays` flags IN PLACE from stored `raw_template` — reclassify dropped pitches, populate type/speed, recompute `pitch_count`/`is_first_pitch`/`is_first_pitch_strike`, recompute `is_qab` via the TN-3a OR-merge, and re-read home/away from the current `games` row to re-derive `batting_team_id`. No DELETE, no API.
- `src/cli/data.py` (the `bb data` subcommand wrapping the entry point above)
- `tests/test_plays_parser.py` (annotation-form fixtures, gating, bare/annotated interleave)
- Reload-mechanism tests under `tests/` (idempotency, parent-flag recompute, no-refetch, `is_qab` OR-merge incl. HHB-only-QAB survival, `is_first_pitch` re-derivation)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
- [ ] Test scope discovery run for every modified module (per `.claude/rules/testing.md`)

## Notes
The reload is one-time historical repair; the forward parser fix makes new reports correct
automatically. See epic TN-3 for the no-refetch rationale and the FK ordering note.
