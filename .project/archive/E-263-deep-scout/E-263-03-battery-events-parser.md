# E-263-03: Battery-events parser (`raw_template` → UUID-keyed CS/backpick/pickoff)

## Epic
[E-263: Deep Scout v1 — Opponent-Intelligence Report Sections](epic.md)

## Status
`TODO`

## Description
After this story is complete, a pure-function parser turns the baserunner-event strings stored in `play_events.raw_template` into typed, UUID-keyed battery events (caught-stealing, catcher backpick, pitcher pickoff, snap-play pickoff, pickoff-attempt, wild pitch, passed ball) that the Running Game & Battery section (E-263-05) rolls up. No new crawling and no schema change — it parses text already in the DB.

## Context
Per Technical Notes TN-3, the actor (catcher/pitcher/runner) UUID lives ONLY inside the `raw_template` string (e.g. `caught stealing 2nd, catcher ${uuid}`, `picked off at 1st, catcher ${uuid} to ${fielder}` = BACKPICK, `picked off at 1st, pitcher ${uuid}`, `Pickoff attempt at {base}`, `wild pitch`, `passed ball`). The existing `plays_parser.py` already classifies these as `event_type='baserunner'` but does NOT extract the actor UUID or sub-type. DE confirmed `raw_template` embeds `${uuid}` tokens (36-hex `_UUID_PATTERN`), not names, so the parse is a clean UUID extraction with no name-resolution step. This mirrors the existing `plays_parser.py` pure-parser separation (parser is DB-free and unit-testable; the loader/query layer does DB work). This story is the parser only; E-263-05 consumes it.

## Acceptance Criteria
- [ ] **AC-1**: A new pure-function module `src/gamechanger/parsers/battery_events.py` parses a `raw_template` string into a typed battery-event result carrying the event sub-type (caught_stealing / **stolen_base** / catcher_backpick / pitcher_pickoff / snap_pickoff / pickoff_attempt / wild_pitch / passed_ball, per the design-doc §8d parse forms) and the actor `${uuid}` token(s), keyed by UUID never by name (per Technical Notes TN-3). The **`stolen_base`** sub-type (a successful steal, the "steals" keyword already classified in `plays_parser.py`) carries the RUNNER's UUID and names NO catcher (a clean steal names nobody, design-doc §2) — it is required so the CS% denominator (`CS/(CS+SB)`) is formable from ONE plays-derived source (E-263-05 AC-2), never mixing plays events with boxscore SB.
- [ ] **AC-2**: A catcher backpick (`picked off at {base}, catcher ${uuid} to ${fielder}`) is distinguished from a pitcher pickoff (`picked off at {base}, pitcher ${uuid}`) and from a snap-play pickoff (`picked off at {base}, {infielder}`), each attributing the out to the correct named actor UUID.
- [ ] **AC-3**: A pickoff-ATTEMPT (`Pickoff attempt at {base}` — a throw-over, no out) is parsed distinctly from a completed pickoff (an out), and wild pitch / passed ball are parsed as battery-leak events.
- [ ] **AC-4**: The parser is pure (no DB, no HTTP) and fully unit-tested against representative `raw_template` strings for every parse form in AC-1, including a string with no battery event (returns an empty/none result) and a malformed string (does not raise).
- [ ] **AC-5**: The parser does not re-implement or duplicate the existing baserunner classification in `plays_parser.py`; it extracts the actor/sub-type from the stored template. (It may share the `_UUID_PATTERN` shape but must not diverge from it.)
- [ ] **AC-6** (variant-robustness — the E-245 footgun): the parser matches via SUBSTRING/KEYWORD anchors, NOT a full-string exact match, so a template carrying an appended annotation, an alternate base ordinal, or a trailing clause still classifies rather than silently vanishing. It is unit-tested against OBSERVED live template variants (not only the canonical forms) — an exact-match parser over `raw_template` silently dropped annotated pitch templates in E-245 and undercounted the stats; the catching card must not repeat that. (api-scout-F2.)
- [ ] **AC-7** (missing-actor case): a battery event whose template carries NO actor `${uuid}` (a scorekeeper can record e.g. "caught stealing" with no catcher clause) is handled EXPLICITLY — the parser flags it as actor-unknown so the downstream rollup (E-263-05) can count it in the team-level tally but EXCLUDE it from per-player attribution. It MUST NOT be dropped, and MUST NOT borrow the previous event's actor identity (an ethics-sensitive mis-attribution against the named-catcher steal light, Technical Notes TN-8).

## Technical Approach
Read the parse forms in `.project/research/deep-scout-design-2026-07-12.md` §8d and the existing `src/gamechanger/parsers/plays_parser.py` (`_UUID_PATTERN`, the `caught stealing`/`picked off`/`Pickoff attempt` keyword classification at ~lines 86-99, and the `_PITCHER_EXPLICIT_PATTERN` regex approach it already uses). Build a new pure function over the stored template string, returning a dataclass. Unit-test without any DB fixture. Do NOT persist into new columns — parse-at-read is the v1 posture (DE: parse-at-load into typed columns is an optional future optimization, not required at HS scale).

## Dependencies
- **Blocked by**: None (pure parser over already-stored data)
- **Blocks**: E-263-05

## Files to Create or Modify
- `src/gamechanger/parsers/battery_events.py` (new — pure-function parser)
- `tests/test_battery_events_parser.py` (new — unit tests for every parse form)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-263-05**: the typed, UUID-keyed battery-event parser the Running Game & Battery rollup consumes (CS%, backpick raw counts, pitcher pickoffs, WP+PB leak rate).

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing (pure unit tests, no DB)
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Keep this a pure parser separate from the query/rollup layer, mirroring the `plays_parser.py`/`plays_loader.py` separation — it enables unit testing without DB fixtures and keeps the rollup (E-263-05) focused on the perspective-scoped SQL.
