# E-278-05: Rename the misleading derivation field; correct its docstrings

## Epic
[E-278: Game Identity — One Real Game, More Than One Row](epic.md)

## Status
`TODO`

## Description
After this story is complete, the field a game's calendar date is derived from is
named for the datum it actually carries, and the docstrings around it describe
where that datum comes from. A future agent diagnosing a wrong `game_date` will
be led to the code that produced it instead of past it.

## Context

`GameSummaryEntry` (`src/gamechanger/loaders/game_loader.py`) carries two
near-identical instant fields. `_derive_game_date` derives the calendar date from
`last_scoring_update`. On the public scouting path, `_build_games_index_from_data`
(`src/gamechanger/loaders/scouting_loader.py:813`) populates that field from
`start_ts` — the game's START instant — falling back to `end_ts` and then to the
empty string. Meanwhile a field literally named `start_time` sits beside it in
the same dataclass, populated from the same `start_ts`, and is **not** what the
date derives from.

`GameSummaryEntry`'s attribute documentation describes `last_scoring_update` only
as "ISO 8601 timestamp string", which does not disclose that on this path it
holds a start instant.

**This is not a cosmetic complaint — the misnaming has already cost diagnostic
time.** Planning-time investigation of the +1-day mechanism (epic TN-1) had to
establish by execution that `_derive_game_date`'s `[:10]` unparseable-instant
fallback never fired and that a *different* fallback, in a *different* function,
was responsible. IDEA-218 records the refuted hypothesis, and a fix aimed at it
would have been a no-op. A reader tracing "where does this wrong date come from"
naturally follows `start_time` and never reaches the field that actually feeds
the derivation.

This story is behavior-preserving. It ships last so it sweeps the state E-278-02
and E-278-04 leave behind rather than a state that has since moved.

## Acceptance Criteria

- [ ] **AC-1**: Given the field `_derive_game_date` derives from, when this story
      is complete, then its name names the datum it carries, and **no reference to
      the old name survives anywhere in `src/` or `tests/`**. The completion
      report **contains the per-site list with a verdict each**, and that list
      **includes both comment sites** (`scouting_loader.py` and
      `src/util/timezone.py`), which are prose rather than references and must be
      reworded rather than mechanically renamed. Per Technical Approach for why a
      grep count is not sufficient evidence for the verdicts.
- [ ] **AC-2**: Given the full test suite before and after the rename, when it
      runs, then no test's **expected value** changes — no expected date, dedup
      outcome, or row count moves. Only identifiers change. A behavioral
      difference means the rename was not behavior-preserving and this criterion
      is violated.
- [ ] **AC-3**: Given the two near-identical instant fields on
      `GameSummaryEntry`, when this story is complete, then their documentation
      states what each holds and how they differ on the public scouting path,
      including that both originate from `start_ts` there and how the derivation
      field's fallback chain differs.
- [ ] **AC-4**: Given `_derive_game_date`'s docstring, when this story is
      complete, then every behavioral claim in it describes the function as it
      exists after E-278-04 — specifically including the sentence describing when
      the raw-UTC-slice fallback fires, which E-278-04 may have changed. Per
      Technical Approach for the boundary against E-278-04's own docstring
      criterion.

## Technical Approach

The rename target is `GameSummaryEntry.last_scoring_update`. Choosing the new
name is yours; it should say that the field holds an instant the date is derived
from, and should not be confusable with the neighbouring `start_time`.

**On enumerating the sites (AC-1).** A grep gives you candidates, not a witness —
`.claude/rules/tool-output-integrity.md` (Prohibition 3) requires a literal read
of each line before ruling on it, and the same file records that an unexpected
match count is a cross-check trigger rather than a finding, in either direction.
At planning time the old name appeared at 8 sites in `src/` — `game_loader.py` (5),
`scouting_loader.py` (2), `src/util/timezone.py` (1) — and 22 across 7 test files.
Treat those as a starting count you must re-derive, not a target to hit: E-278-02
and E-278-04 land first and may move them. **TWO of the `src/` hits are *comments*
rather than references** — the explanatory comment at `scouting_loader.py:767` and
the `UTC_ISO_FORMAT` wire-format comment in `src/util/timezone.py`, which contrasts
GameChanger's wire format with ours and names the field in passing. A sweep that
mechanically renames every match will damage both. (An earlier draft of this
paragraph said "one" and omitted the `timezone.py` site entirely, which is also why
that file is now in the Files list.)

**Boundary against E-278-04, so neither story assumes the other did it.**
E-278-04's docstring criterion covers claims about how the derivation
**degrades** — the unresolvable-zone and full-day behavior, and the
`scouting_loader.py:767-772` comment. This story's AC-3 and AC-4 cover claims
about what the **fields hold and where they come from**, plus
`_derive_game_date`'s own docstring. Where the two touch the same docstring, this
story runs after E-278-04 and owns the final state.

Per `.claude/rules/tool-output-integrity.md` ("Prose you AUTHOR is a claim too"),
resolve every symbol and path the docstrings cite against the repo rather than
carrying them forward on trust.

**⚠️ Every line number in this story is accurate as of planning (2026-07-27) and
will ROT before it runs.** E-278-04 edits `_derive_game_date` and
`GameSummaryEntry` — above the `game_loader.py` sites cited here — and also edits
`_build_games_index_from_data`, which moves the `scouting_loader.py:813`
population site and the `:767-772` comment. Navigate by SYMBOL: the
`last_scoring_update=` assignment inside `_build_games_index_from_data`, and the
`GameSummaryEntry` attribute block. Per
`.claude/rules/tool-output-integrity.md` ("cite a stable anchor, not a line
range") — and note that this story runs LAST, so its citations have had the most
time to move.

## Dependencies
- **Blocked by**: E-278-01, E-278-02, E-278-04. **E-278-01** shares
  `tests/test_loaders/test_game_dedup.py` with this story (01 rewrites its
  exact-dict `_query_record` assertions for the `ties` key; this story renames a
  field referenced in the same file), so the two need explicit ordering and this
  story runs after 01. **This story runs LAST in the epic** — execution order is
  04 → 02 → 01 → 05. **E-278-02 and E-278-04** both modify
  `src/gamechanger/loaders/game_loader.py`; E-278-04 additionally modifies
  `src/gamechanger/loaders/scouting_loader.py` **and `src/util/timezone.py`** —
  **three** shared files with 04, not two — and may change the very docstring
  sentence AC-4 pins. (The third was named in the Files list below before this
  sentence caught up with it.)
- **Blocks**: None

## Files to Create or Modify
- `src/gamechanger/loaders/game_loader.py` — the field, `_derive_game_date`, and
  the `GameSummaryEntry` attribute documentation
- `src/gamechanger/loaders/scouting_loader.py` — the population site at `:813`
  and the surrounding comment at `:767-772`
- `src/util/timezone.py` — **a THIRD file, without which AC-1 is unsatisfiable.**
  The `UTC_ISO_FORMAT` wire-format comment (around `:131-132`) names
  `last_scoring_update` while contrasting GameChanger's wire format with ours. AC-1
  requires no surviving reference in `src/`, and the 8 sites span three files, not
  two: `game_loader.py` (5), `scouting_loader.py` (2), `src/util/timezone.py` (1).
- `tests/test_loaders/test_game_loader.py`
- `tests/test_game_start_time.py`
- `tests/test_loaders/test_game_dedup.py`
- `tests/test_loaders/test_self_game_fix.py`
- `tests/test_scouting_loader.py`
- `tests/test_uuid_contamination.py`
- `tests/test_report_plays.py`

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes

Correcting IDEA-218's refuted candidate 3 is an epic **closure** obligation
(epic TN-9), not part of this story. Do not edit the idea file here.
