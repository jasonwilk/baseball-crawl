# E-278-01: Record header — count ties, pin games-played semantics

## Epic
[E-278: Game Identity — One Real Game, More Than One Row](epic.md)

## Status
`DONE` (2026-07-28)

## Description
After this story is complete, a team's record header renders W-L-T and matches
GameChanger's display convention, including the trailing `-0` when a team has no
ties. The record continues to count games PLAYED rather than games we hold stat
data for, and a regression pin makes it impossible to quietly re-introduce the
stat-row coverage gate that domain review rejected.

## Context

The 2026-07-27 live-vs-dev report audit found the record header disagreeing with
GameChanger — **as observed on 2026-07-27: GC 25-15-0; live 25-16; dev 25-17. Those figures
are EVIDENCE, not a criterion: do not update them and do not test against them.** The GC
profile moves with play (it reads 25-16-0 now, because two more games completed), and per
epic TN-16 a GC profile record is a raw count of that team's own schedule listings. **No
criterion in this story targets matching GC's number, and none may be added.** Two bad
`games` rows explained
the numeric disagreement, and the rest of this epic stops those rows being
created. This story fixes the two things that remain wrong even with clean data:
a tie is counted as neither a win nor a loss, and the header omits the tie column
entirely.

`_query_record` (`src/reports/generator.py:396-422`) sums two `CASE` expressions
using strict `>` and `<`, so a game at equal scores falls through both arms and
contributes to neither total. It filters on `home_score IS NOT NULL AND
away_score IS NOT NULL` and nothing else — there is no stat-row `EXISTS` gate
today, which is the correct behavior per the ruling below.

**The rejected fix is the load-bearing context here.** An earlier triage
recommended adding a stat-row `EXISTS` gate to `_query_record` as
defense-in-depth against phantom rows. Domain review rejected it (epic TN-7): the
record reflects games PLAYED, not games we have DATA for, and a win or loss is
derivable from a final score alone. The rejection is now backed by measurement,
not argument — epic OQ-2 found **20 genuine completed-and-scored games across 12
of 28 subject teams** (per-team rates 2.4%-15.8%) that carry no stat rows from
their own team's perspective; 17 of the 20 are charted from the opposing
perspective. Had the gate shipped, those 20 real games would have silently
vanished from twelve coaches' records, while removing the two bad rows only
coincidentally. That is why AC-3 exists as a pin rather than as prose.

## Acceptance Criteria

- [ ] **AC-1**: Given a game that the record query counts at all — that is, one
      whose home and away scores are both non-null — when its two scores are
      equal, then it contributes exactly 1 to the team's tie count, 0 to wins,
      and 0 to losses, for either participating team in that season. **The
      wording is deliberate**: the query today has no completeness guard, so this
      criterion is scoped to the population the query actually reaches. Whether
      that population *should* be narrower is AC-6, not this criterion.
- [ ] **AC-2**: Given any team whose record renders on a **coach-facing report
      surface**, when the report is generated, then every such rendered record is
      three dash-separated integers — including when the tie count is 0, which
      renders a literal trailing `-0` rather than being suppressed. **Scope is
      deliberate**: this criterion previously said "no code path", a universal
      claim AC-4's method structurally could not verify. Operator-facing summary
      surfaces are a recorded non-goal — see Technical Approach.
- [ ] **AC-3** (regression pin): Given two databases identical except that one
      has zero rows in `player_game_batting` and `player_game_pitching`, when the
      record is queried for the same team and season in each, then the two
      records are equal in all three components. This holds for a team whose
      games are entirely stat-less.
- [ ] **AC-4**: Given the set of surfaces that render a record, when this story
      is complete, then the implementer has recorded a written verdict for each
      one — including "no change needed" where that is the answer. Per Technical
      Approach for the enumeration method; a surface with no recorded verdict
      fails this criterion.
- [ ] **AC-5**: Given any fixture, golden artifact, **or inline assertion** that
      encodes the record's shape, when the suite runs, then it encodes the
      three-component shape and passes. Nothing asserts the two-component shape.
      **"Assertion" is load-bearing**: the two known breakages are inline
      exact-dict assertions in a dedup test, which are neither a fixture nor a
      golden artifact, so the narrower wording reached neither them nor the Files
      list. Note that subscript-style access (as at
      `tests/test_report_generator.py:1537-1540`) survives the widening and needs
      no change — the exact-dict comparisons are the failing shape.
- [ ] **AC-6** (verification item, may or may not change code): Given the schema
      and the game loader, when this story is complete, then the implementer has
      established and recorded whether a game that is **not** genuinely concluded
      — suspended, postponed with partial play, weather- or curfew-stopped — can
      carry non-NULL `home_score` and `away_score` in this database. If it can,
      the record query needs a `status = 'completed'` guard it does not currently
      have, and this story adds it. If it cannot, the verdict is recorded and no
      code changes. Per Technical Approach; this is a domain-flagged gap, not a
      style preference.

## Technical Approach

The query change is in `_query_record`. Note that its current return contract
(`{"wins": ..., "losses": ...}`, or `None` when both sums are NULL) is consumed
downstream and documented in `render_report`'s docstring — widening it is a
production contract change, so per `.claude/rules/testing.md` ("Inverse
direction"), every fixture and assertion encoding the old shape must move in the
same change rather than being left as follow-up. That is what AC-5 exists to
catch.

**For AC-4, enumerate by SYMBOL SWEEP across `src/` and `src/api/templates/` — not
from the template and renderer.** That narrower method was the original wording and
it is structurally unable to reach the exceptions, which is what made AC-2's
universal claim uncheckable: a verdict list produced that way looks exhaustive and
omits members. Sweep the record-accessor shapes (the `wins`/`losses` attribute,
subscript, and `record_wins`/`record_losses` field forms) and record a verdict per
hit, "no change needed" included.

The sweep will surface at least three sites beyond the two report-render ones
(`scouting_report.html:618`, the header, and `:629`, the summary line). Expected
verdicts, which you should confirm rather than copy:

- **`src/reports/morning_run.py` (`_resolved_record`, ~`:272`) and
  `src/cli/report.py` (~`:676`)** — operator-facing summary lines that render a
  two-part record. **Recorded NON-GOAL for this story.** Their tie is dropped
  upstream at the API-parse boundary: `TeamProfile` declares only
  `record_wins`/`record_losses` and reads only `record.get("win")`/`("loss")`
  (`src/gamechanger/team_resolver.py:48-49`, `:135-136`), while the public spec
  documents `record: {win, loss, tie}`. Fixing that is a parse-layer change on an
  operator surface — out of scope here, and worth an idea rather than silent
  scope growth.
- **`src/reports/generator.py:2457`** builds a two-part `team_record` string for
  Tier-2 enrichment. **Verdict: no change needed — the value is unused.**
  `src/reports/llm_analysis.py:176-178` and `:221-222` document it as *"accepted for
  call-site compatibility but intentionally unused"*; the validated prompt variant
  drops the records section, so the string is built and discarded. code-reviewer
  initially flagged this as coach-facing and **retracted it** after following the
  parameter to its consumer. Do not "fix" it.

The tie predicate is equal non-null scores on a completed game. Do NOT reach for
a stat-row, perspective, or coverage condition anywhere in this query — see the
Context section and epic TN-7 for why, and note that AC-3 will go red if one is
added.

**On AC-6, which baseball-coach raised after reading `_query_record` directly.**
Equal score at genuine completion is the correct definition of a tie — that part
is not in question. The gap is that `_query_record`'s `WHERE` clause filters on
`season_id`, the team, and `home_score IS NOT NULL AND away_score IS NOT NULL`,
and **nothing else** — there is no `status = 'completed'` condition, which makes
it an exception to the convention in `.claude/rules/data-model.md` that every
game query in `src/` filters on `'completed'`. Verified against the current file.

> ⚠️ **ANNOTATED AT CLOSURE, 2026-07-28 (PM). The paragraph above is preserved as a
> record of what was believed at planning time — but "Verified against the current
> file" did NOT hold for the half of the claim that mattered, and that phrase is
> exactly the sentence a later reader trusts most, so it is marked rather than left
> to pass.**
>
> **What WAS verified and still holds:** `_query_record`'s `WHERE` clause carries no
> `status` condition.
>
> **What was NOT verified and is FALSE:** that this makes it *an exception to a
> convention the other queries follow.* `.claude/rules/data-model.md`'s census was
> wrong. `_query_recent_games`, `_query_runs_avg` and `_query_freshness` **all gate
> on scored-ness with no status filter**, and `generator.py` carries **zero**
> `status = 'completed'` predicates (there are nine in `src/`, none in that file).
> Established by claude-architect refusing a relayed instruction and checking, and
> verified independently by code-reviewer.
>
> **This does not weaken AC-6 — it puts it on better ground.** `_query_record` is
> not a lone deviant needing justification; it is **consistent with all three of its
> siblings**, because that whole query family uses scored-ness as its completeness
> predicate. The verdict moves from *"knowingly breaking a documented convention"*
> to *"the convention's census was wrong and this query conforms to its family."*
>
> **Why this is annotated rather than preserved silently, since the paragraph is
> otherwise evidence:** a planning-time BELIEF is evidence and is preserved. *"Verified
> against the current file"* is a different kind of claim — it asserts a check was
> performed, which **discharges a duty the reader would otherwise have.** It suppresses
> re-verification, so it is criterion-shaped and gets corrected. The belief stays; the
> false assurance is marked.
>
> The epic's own record of this class applies to its author here: a **correct
> conclusion stopped the premise underneath it being checked.** code-reviewer made the
> same error on the same sentence from the other direction — reporting the rule as
> *newly* falsified by this story, when those three siblings had violated it all
> along — and diagnosed it in the same words.
Whether that matters depends on a fact about the loader that neither PM nor coach
has established: can a score land on a game whose `status` is not terminal?
Weather and curfew stoppages are the realistic case at this level, and pool-play
time-limit ties are a real, intentional tie type at youth and travel level — so
do not treat "a tie" as inherently suspicious; the question is only whether an
*unfinished* game can present as one.

Note the blast radius before deciding: a missing `status` guard would affect the
existing win and loss counts **identically**, not just the new tie branch. So if
it is a real gap it is a pre-existing one this story would be extending rather
than introducing — which is an argument for fixing it here, not for deferring it.

**se-epicA has already answered part of this, which narrows the hunt.** On the
live scouting path two facts bound it: `_build_games_index_from_data` skips any
event whose `game_status != "completed"`, and `_upsert_game`'s INSERT
**hardcodes** `status` to `'completed'`. So no code path on the reports pipeline
writes a scored row with a non-terminal status. That does **not** close AC-6 —
GameChanger's own `completed` may cover a weather-shortened game, which is
genuinely concluded and therefore fine — but it reduces the open question to
"is there another live `games` writer?", and SE read only the scouting path.
**as-epicA answered the other half from the payload side — but rest the reasoning
on the LOADER'S GATE, not on the absence of a non-final status.** Across **1064
live schedule events** it observed four `game_status` values: `completed` (1034),
absent-or-null (27), **`live` (2)**, and `new` (1). No suspended, postponed, or
forfeit status appeared.

**The `live` value is why the framing matters.** The endpoint doc previously
asserted, from a 633-record probe, that no `live` status had ever been observed;
the wider sweep observed it twice, and api-scout has retired that claim in the doc
with a dated tombstone. **A `live` game is by definition not concluded, and it
demonstrably exists in this payload** — so "no non-final status exists" is not a
safe premise and must not be used as one. The status set is **OPEN**, and it has
now grown once under a wider corpus; gate on `== "completed"` rather than
enumerating not-completed values.

What actually protects the public path is therefore structural rather than
empirical: `_build_games_index_from_data` skips any event whose `game_status !=
"completed"`, so a non-completed event never becomes a `games` row regardless of
which status values GameChanger invents next. That inference holds without any
claim about the enum's contents. It still says nothing about the authenticated
path.

**code-reviewer then closed the remaining question: there is no other live `games`
writer.** A sweep of `src/`, `scripts/`, and `migrations/` finds exactly **one**
`INSERT INTO games` — in **`GameLoader._upsert_game`**
(`src/gamechanger/loaders/game_loader.py`, at `:1843` as of 2026-07-28), the one
that hardcodes `'completed'`. ⚠️ **This citation read `:1569` at planning time and
had rotted by 274 lines** once E-278-04 and E-278-02 both inserted above it —
navigate by the symbol, and expect `:1843` to move again when E-278-05 edits this
module. **The claim itself was re-verified on 2026-07-28 and still holds: exactly
one `INSERT INTO games` in `src/`, and the only two `UPDATE games` statements
(`game_merge.py`, `backfill_game_dates.py`) touch `game_stream_id` and `game_date`
respectively, neither writing `status`.** Note the DDL default is `status TEXT NOT NULL DEFAULT
'scheduled'`, so a non-terminal scored row is **representable in the schema but
unreachable through any current writer**.

**So AC-6 can be satisfied by a recorded verdict with no code change**, on the
strength of those three independent checks. Confirm the sweep rather than taking
it on trust — that is what the criterion asks for. Adding the `status =
'completed'` guard anyway, as defence in depth against a future second writer, is
a legitimate verdict too; what is not legitimate is leaving it unexamined. A
weather-shortened game *is* genuinely concluded and is fine either way. Either answer is acceptable; what AC-6 forbids is leaving it unexamined, so
that the gap between AC-1's English and the query's actual guard is a recorded
decision rather than a silence.

Domain rulings incorporated from baseball-coach are recorded in the Notes section
below; where this story and those rulings disagree, raise it rather than
resolving it silently.

## Dependencies
- **Blocked by**: E-278-02. Both stories modify
  `tests/test_loaders/test_game_dedup.py`. That file asserts **exact dict
  equality** on the record — `_query_record(db, team_a_id, season_id) == {"wins":
  1, "losses": 0}` at `:1499` and the mirror at `:1508` — so adding a `ties` key
  breaks both, making them MUST-FIX for this story per
  `.claude/rules/testing.md` ("Inverse direction"). E-278-02 owns that file's
  dedup tests, so it runs first and this story then updates the record
  assertions against its final state. **This story is NOT independent**, which
  the Stories table previously implied.
- **Blocks**: E-278-05, which also modifies
  `tests/test_loaders/test_game_dedup.py` and therefore runs after this story.

## Files to Create or Modify
- `src/reports/generator.py` — `_query_record` and the assembly of the `record`
  dict it feeds
- `src/api/templates/reports/scouting_report.html` — record render sites
- `src/reports/renderer.py` — the `record` shape documented in `render_report`'s
  docstring
- `tests/test_report_generator.py` — record query behavior, including AC-3's pin
- `tests/test_report_renderer.py` and/or `tests/test_report_rendering.py` —
  rendered record shape
- `tests/fixtures/golden/report_stats.json` — **confirmed** to encode the
  two-component record shape (a `record` object carrying only `wins` and
  `losses`, near line 1021). This is AC-5's known target, not a conditional one.
- `tests/test_report_golden.py` — if the golden comparison needs to move with it
- `tests/test_loaders/test_game_dedup.py` — **MUST-FIX, verified.** Two exact-dict
  assertions on `_query_record` (`:1499`, `:1508`) break the moment a `ties` key
  is added. Shared with E-278-02, which is why this story is now blocked by it.

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes

Domain ruling (epic TN-7, baseball-coach, binding): ties match GameChanger's
**DISPLAY FORMAT** exactly — always show the trailing `-0`, never conditionally
suppress it. **The ruling is about FORMAT and stands entirely; it is not a
ruling to match GC's NUMBER**, which epic TN-16 establishes is a raw count of
schedule listings rather than of games played. The coach's stated reason is
partly superseded on that point: it was that the whole defect was our number
disagreeing with theirs, so
adopting their display convention removes one more place a reader must reconcile.

**Coach ruling on AC-2's scope (2026-07-27): BOTH sites, same three-part format,
no exceptions.** The reason is not cosmetic symmetry — it is the principle this
epic exists to protect, `.claude/rules/data-model.md`'s "one honest count and one
honest date everywhere." A header reading `25-15-0` beside a summary line reading
`25-15 record` would **manufacture a new visible on-page inconsistency of the
identical shape as the one that started this work** — two numbers on the same
report that disagree, now by a tie-count omission instead of a phantom-row
inflation. Do not reintroduce the disease this epic is curing.

**Coach ruling on the two tie surfaces: independent, do not fold together.**
`recent_form` and the season record answer different questions (per-game trend
versus season total) and neither should be derived from the other. But
`recent_form` already treating `"T"` as a first-class outcome sharpens why this
gap matters: the fix introduces no new concept to the codebase, it closes a place
where the season-aggregate query had not caught up with what the per-game view
already does correctly. And it raises the cost of leaving it broken — a coach who
sees a `"T"` in the last-five strip and a two-part record above it, with no tie
anywhere in the total, is looking at a contradiction on the same page. That is
worse than an invisible bug, because it is a visible one nobody explained.

Epic OQ-1 is open: the operator may override the coach ruling in favor of the
triage file's perspective clause. That would change this story's scope. Planning
proceeds on the coach ruling per decision routing.
