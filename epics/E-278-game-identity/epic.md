# E-278: Game Identity — One Real Game, More Than One Row

## Status
`READY` (2026-07-28)

## Overview

One real game can end up as more than one `games` row. Most of this is not a dedup defect
at all: **two independent date-derivation defects mis-date 11 rows today, in production,
and they shift in OPPOSITE directions** (TN-1 and TN-14). Only 2 are visible duplicates
now; the other 9 carry a wrong date already and become duplicates when their counterpart
perspective is scouted. **The live coach-facing harm — wrong game dates and a wrong
"Through [date]" freshness line — is larger than the dedup harm.** A third, unrelated route
(TN-5) duplicates a game at load. This epic fixes all three for FORWARD accuracy and
repairs nothing historical.

## Background & Context

The 2026-07-27 live-vs-dev report audit found the record header disagreeing with
GameChanger — **as observed on 2026-07-27: GC 25-15-0; live 25-16; dev 25-17.**

**⚠️ Those three figures are EVIDENCE, not a criterion. Do NOT update them, and do NOT test
against them.** They record what motivated this epic at a moment in time; rewriting them to
a current number would falsify that record. Two facts make the distinction load-bearing,
both established by as-epicA:

- **The GC figure MOVES WITH PLAY.** That profile reads **25-16-0 (41)** now. The cause was
  discriminated, not guessed: the record through 2026-07-26 was 25-14-0 (39), and **two**
  completed listings started on 2026-07-27, both losses. At audit time GC counted 39 + one
  = 25-15-0/40, exactly as recorded; it now counts both. **The audit figure was correct when
  taken and aged by one game in under 24 hours** — no lag, no defect. A later reader who
  re-checks it against a live GC number must not conclude the epic's premise evaporated.
- **This team is CLEAN on dedup** — 41 completed listings, RAW 25-16-0 == DEDUPED 25-16-0,
  zero collapsed groups. So its disagreement with our stored record is not explained by the
  double-listing mechanism, unlike the OQ-1 team. **But see TN-16: a clean record is not
  evidence that no game was double-scored** — this very team is the single-listing side of
  a game that WAS double-scored.

The two bad rows below are established on their own evidence, not on the GC delta. Two bad
rows explained it, with unrelated
causes. A separate operator-staged ingestion audit confirmed a third defect of the same
family. Planning-time investigation then established the mechanism behind the largest one
by execution, and it was not what any prior artifact predicted.

**Operator ruling (2026-07-27), which sets the epic's shape:** *"We can reset all prod
data. We don't have to repair anything historically. We only need to ensure we are
accurate moving forward."* Historical repair — dev and prod — is out.

Authorities, precedence order. Where a summary and one of these disagree, **the artifact
wins**:

1. as-epicA's IDEA-218 mechanism report (executed; relayed verbatim into the planning
   record). Establishes the alias cause, the counterfactuals, and the blast radius.
2. `INGESTION-BUGS-HANDOFF.md` §5 — repo root, **untracked and gitignored by design**.
   ⚠️ Produced ON THE LIVE SERVER: its row-level facts describe PRODUCTION, not this
   environment. §§2/3/4/6 are a follow-on epic.
3. `/workspaces/baseball-crawl/.project/research/2026-07-27-ingestion-triage.md`.
   **Its §4 item 3 is superseded twice over**: the record-query clause was
   domain-rejected (TN-7), and its "data repairs inside" list is void under the ruling.
4. `IDEA-217` / `IDEA-218` / `IDEA-219` / `IDEA-220` in `/workspaces/baseball-crawl/.project/ideas/`.

**Sequencing (handoff §5.5): this epic runs BEFORE the follow-on fidelity epic's §2
backfill**, which would otherwise fully populate a degraded duplicate row.

## Goals

- No new wrong `game_date` is derived — from a timezone string the runtime cannot resolve
  (mechanism 1, +1 day) **or from a full-day event's date marker localized as though it
  were an instant (mechanism 2, −1 day)**. **(Bullet CORRECTED 2026-07-27: it named only
  the alias mechanism, the same omission Success Criterion 1 carried. TN-14 establishes the
  two as co-equal and opposite in polarity, so a goal naming one of them understates the
  epic by half.)**
- A same-perspective duplicate from GameChanger's upstream double-listing is collapsed at
  load instead of persisted.
- The record header renders W-L-T and counts a completed scored game whether or not it
  carries stat rows.
- The derivation's misleading field name stops causing misdiagnosis.

## Non-Goals

- **Any historical data repair, dev or prod.** Operator ruling; existing bad rows are
  resolved by reset. ⚰ **This bullet carried a PRECONDITION — do not reset before
  IDEA-219's creating path is identified — which is DISCHARGED as of 2026-07-28.** The path
  is now identified from code and coverage statistics rather than from the row, so retaining
  the row buys nothing and the reset is unconditional again. See OQ-3.
- **Widening the dedup natural key.** as-epicA argues against it on evidence: the two
  perspectives disagreed by 2.5 hours on the start instant and still converged on the same
  local date once the zone resolved, so the derivation already tolerates the sloppiness we
  observe. A ±1-day window would paper over the real defect while loosening the merge
  criterion for tournament consecutive-day play, where a wrong merge is destructive.
- **A same-perspective collapse primitive** (cut — TN-6).
- Handoff §§2, 3, 4, 6; IDEA-196's upsert policy; IDEA-221's display defects; the 2,037
  orphan "Unknown" stubs.
- IDEA-220 — closed by investigation, no story (TN-8).

## Success Criteria

1. An unresolvable timezone alias no longer yields a silently-wrong calendar date.
2. A same-perspective pair with agreeing scores and a sub-second start delta is collapsed
   at load; genuine doubleheaders and consecutive-day games are not. **(CORRECTED
   2026-07-27 — this criterion previously required "agreeing scores AND PLAY COUNTS … at
   load", which TN-5's SPLIT retired and story 02's AC-8 forbids outright: play counts are
   0 and 0 at the load decision point, so consulting them reads as vacuous agreement. An
   epic closing correctly under TN-5 would have FAILED this criterion as written.)**
   Play-count corroboration belongs to the offline/audit surface, not to closure of this
   criterion.
3. The record header renders W-L-T and is guarded against the rejected coverage gate.
4. **A full-day calendar event is dated from its date marker, not localized as an instant**
   — so the −1-day mechanism produces no new mis-dated row, and a load carrying both
   mechanisms' shapes dates both correctly. **(ADDED 2026-07-27.** Criteria 1-3 covered the
   alias mechanism, the dedup fix and the record header, and **nothing covered mechanism 2
   at all** — an epic that dropped E-278-04's AC-2, AC-2b and AC-3 entirely would have
   satisfied every criterion as written, while leaving half the live date defect shipping.
   The Success Criteria are the closure gate, so a gap here is a gap in what closure
   checks.**)**
5. **The derivation's misleading field name no longer misdirects diagnosis**: the field the
   game date derives from is named for the datum it carries, and the rename is
   behavior-preserving. **(ADDED 2026-07-27 — E-278-05 had no Success Criterion, so the
   epic could have closed with that story silently dropped.)**
6. `python -m pytest tests/` reports 0 failed.

## Stories

| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-278-01 | Record header: count ties, pin games-played semantics | TODO | E-278-02 | - |
| E-278-02 | Same-perspective duplicate detection at load | TODO | E-278-04 | - |
| E-278-04 | Resolve timezone aliases; fail closed on an unresolvable zone | TODO | None | - |
| E-278-05 | Rename the misleading derivation field; correct its docstrings | TODO | E-278-01, E-278-02, E-278-04 | - |

Execution order is therefore **04 → 02 → 01 → 05**, and that order is FIXED — 01 and 05
both modify `tests/test_loaders/test_game_dedup.py`, so 05 runs after 01. **01 is NOT
independent** — that claim was wrong and is corrected below.

⚰ **A parenthetical here previously read "05 may equally run before 01; it depends on 02
and 04 only." That was FALSE and is retired.** It was written before the 05→01 edge
existed and survived the edge being added — licensing a dispatcher to put two stories on
one file with no ordering, which is the exact hazard that edge exists to prevent, on the
exact file it was about.

Story files: `E-278-01-record-header-ties.md`, `E-278-02-same-perspective-detection.md`,
`E-278-04-timezone-aliases-fail-closed.md`, `E-278-05-rename-derivation-field.md`.

**FOUR dependencies were ADDED during story authoring (2026-07-27); none is a
re-derivation of story shape.** (This header said "Two" while three bullets sat under it
and a fourth edge had no bullet at all — the count and the list drifted from the graph
they describe. Both corrected.)

- **05 depends on 04.** Both modify `src/gamechanger/loaders/game_loader.py` AND
  `src/gamechanger/loaders/scouting_loader.py`. 05 additionally pins a docstring sentence
  that 04 may rewrite, so 05 must run second or it sweeps a state that has since moved.
- **02 depends on 04** (added after se-epicA's F4: the sequencing rule was asserted for
  04→05 and inconsistently NOT applied to 02↔04, though both list `game_loader.py`). They
  touch different functions so a textual conflict is unlikely, but under the staging-boundary
  protocol whichever runs second reviews against a moved file. **04 runs first for a semantic
  reason too**: it changes the derived `game_date`, which is the key `_find_duplicate_game`
  groups candidates by — so 02's dedup behavior is defined against corrected dates rather
  than dates this epic is about to move.

- **01 depends on 02** (added 2026-07-27; **01 was previously listed as independent and
  that was FALSE**). Both modify `tests/test_loaders/test_game_dedup.py`, which asserts
  **exact dict equality** on the record (`_query_record(...) == {"wins": 1, "losses": 0}` at
  `:1499` and its mirror at `:1508`). Adding a `ties` key breaks both, so they are MUST-FIX
  for story 01 under `.claude/rules/testing.md` ("Inverse direction"). 02 owns that file's
  dedup tests and runs first.
- **05 depends on 01** (added 2026-07-27, and the edge that had no bullet). Story 05 also
  modifies `tests/test_loaders/test_game_dedup.py` — it renames a field referenced there,
  while 01 rewrites that file's exact-dict `_query_record` assertions for the `ties` key.
  Three stories touch that one file (01, 02, 05), which is why it carries the most
  ordering constraints in the epic. 05 runs last.

**Line-number citations across all four stories are accurate as of 2026-07-27 and will
ROT** — 04 edits above every `game_loader.py` line 02 cites and moves the
`scouting_loader.py` site 05 cites. Navigate by symbol; treat numbers as hints to
re-confirm.

(E-278-03 was cut before instantiation — see History. The number is not reused.)

## Consultation Record

Per-domain verdicts, required explicitly by the PM quality checklist — a silent omission is
not a waiver, and this record was missing until 2026-07-27 even though every consultation
below actually happened. Narrating expert input in Technical Notes does not satisfy the
gate; these verdicts do.

| Domain (Consultation Triggers) | Verdict | Where the input is captured |
|---|---|---|
| Coaching data, statistics, scouting, reports | **CONSULTED** — baseball-coach | TN-7 (binding record-semantics ruling, read from `_query_record` directly); the both-sites `-0` ruling and the `recent_form` independence ruling in story 01's Notes; the pitching-workload safety framing behind story 02's AC-10; the AC-6 status-filter gap it raised |
| GameChanger API, data availability, auth | **CONSULTED** — api-scout | TN-14 (full-day mechanism, established by execution), OQ-4 (1064-event alias corpus and the ruling against a normalization map), the live-payload re-verification behind story 02's constraint 4 and Fixture specification, and the `docs/api/endpoints/get-public-teams-public_id-games.md` full-day section written for story 04's AC-2 |
| Database schema, SQL migrations, ETL | **CONSULTED** — data-engineer | TN-6 (UNIQUE-key collision analysis that CUT story 03), TN-13 (neutral row labels), OQ-5/OQ-6/OQ-7 adjudications, OQ-9's three-part answer, and `.claude/agent-memory/data-engineer/game_duplicate_class_taxonomy.md` |
| Python implementation, testing, code architecture | **CONSULTED** — software-engineer | OQ-8 (the fail-closed no-op, established by execution across six instant shapes), the caller-side constraint surface in story 04, TN-8's consumer audit closing IDEA-220, and the AC-8 anti-vacuity instant |
| Agent infrastructure, CLAUDE.md, rules, skills | **WAIVED** | No story's Files list touches `CLAUDE.md`, `.claude/rules/**`, `.claude/agents/**`, `.claude/skills/**`, or `.claude/hooks/**`. The closure-time context-layer assessment is a separate, unconditional gate and is NOT waived by this line |

## Operator Notes

**Both operator actions are RESOLVED as of 2026-07-28. Retained as a record of what was
asked and how each closed.**

1. ⚰ **"Do NOT reset before IDEA-219's creating path is identified" — DISCHARGED.** The
   Live-side trace identified the path from code plus identifier-coverage statistics, so it
   no longer depends on retaining the row (OQ-3, TN-17). **The reset is unconditional
   again.**
2. ⚰ **"Confirm the OQ-5 closure" — CONFIRMED DISMISSED by the operator.** The standing
   "six duplicate Freshman games" item is a FALSE POSITIVE: genuine doubleheaders with
   identical perspectives, exactly 7200-second start gaps, and materially different scores.
   Closed as a false positive rather than as "resolved by reset" — running a merge against
   them would have been the destructive mistake.

**Still live for the operator (not blockers, and not decisions this epic can make):**

- **The `tzdata` fix does not reach production at closure** — see below. Now doubly
  relevant: TN-17 confirms the gap inside the running prod container (16 `US/Central` rows,
  8 mis-dated, `tzdata` absent).
- **Prod's phantom is a B-class date-split twin whose perspectives are DISJOINT**, so the
  existing `bb data merge-duplicate-games` primitive would accept it once detection finds
  it. That is an operator repair option, not epic scope.

**The `tzdata` fix does NOT reach production when the epic closes. It reaches production
at the next image rebuild.** The gap is in the shipping image — `python:3.13-slim` omits
the tzdata `backward` links and the Dockerfile apt-installs only `curl` and `sqlite3` —
so declaring and installing the dependency fixes dev and CI immediately while production
keeps deriving UTC dates for aliased rows until the app image is rebuilt and redeployed.
Verified inside the running app container during planning. **So a green suite at closure is
not evidence that production is fixed**, and the epic should not be reported as closing the
live defect until the rebuild lands. Per `.claude/rules/app-troubleshooting.md`, that is
`docker compose up -d --build app` plus a health check; a requirements change is exactly the
trigger that rule names.

## Dispatch Team
- software-engineer

⚰ **A routing exception was granted here on 2026-07-27 and WITHDRAWN the same day. Do not
reinstate it.** It let this SE-only team edit comments in `migrations/001_initial_schema.sql`
(story 04's AC-9), reasoning that the edit was inert because `apply_migrations.py` tracks by
filename with no checksum. **data-engineer's standing ruling rejects exactly that
rationale** (`.claude/agent-memory/data-engineer/migration-immutability-basis.md`, E-277):
DE established the no-checksum fact first and ruled it insufficient, because there is no
mechanical boundary between an inert comment and one documenting DDL semantics — so
"comments may be edited when judged inert" moves the judgment to whoever is editing.
**AC-9 is removed, story 04 no longer touches `migrations/`, and no routing exception is
needed.** The false-provenance defect is filed as an idea. Migrations are DE's domain and a
PM scope call does not override a domain owner inside it.

(`data-engineer` was listed as a Dispatch Team member and is REMOVED 2026-07-27: all four stories carry
`Agent Hint: software-engineer`, and story 04's only DE-shaped file —
`migrations/001_initial_schema.sql` — is a comments-only edit that explicitly forbids DDL
change. DE's contribution to this epic was planning-phase measurement, which is not what
this section governs. Listing an agent no story routes to invites a spawn with nothing to
do.)

## Technical Notes

**Reading order note (2026-07-27).** These appear on disk as TN-1..TN-11, **TN-15, TN-12,
TN-14, TN-13** — insertion residue from notes added mid-planning. Every cross-reference in
this epic and its stories cites a TN by NUMBER, not by position, so nothing resolves
incorrectly; the numbers are the addresses. **Deliberately not physically reordered**:
moving four large blocks to fix a cosmetic ordering is precisely the mechanical edit most
likely to introduce a real defect in an epic whose dominant defect class is insertion
residue, and the ordering is the one property here that costs nothing to be wrong. Use
search, not scrolling.

### TN-1 — Gap B is a dependency defect, not a dedup defect (ESTABLISHED BY EXECUTION)

One perspective's public schedule payload carries the timezone `US/Central`; the other
carries `America/Chicago`. **These name the same zone.** `US/Central` is a legacy tzdata
"backward" alias that does not resolve in our runtime, so `derive_local_date`
(`src/util/timezone.py:78`) raises `ZoneInfoNotFoundError`, logs a WARNING, and **falls
through with the datetime still in UTC**, returning the UTC calendar date. For an evening
game whose start instant already crossed 00:00Z, that is the next day.

Counterfactuals were executed, not reasoned:

- Repair only the alias, change nothing else → both perspectives yield the same date.
  **The alias failure is the necessary cause.**
- Keep both aliases, equalize the instants → no split. **The 2.5-hour instant
  disagreement alone does not split.**

**IDEA-218's candidate 3 is REFUTED as written.** `derive_local_date(...)` returns a date
string, not `None`, so `_derive_game_date`'s `[:10]` unparseable-instant fallback never
fired. A *different* fallback fired, in a different function. **A fix aimed at the `[:10]`
fallback would be a no-op.** Correcting the idea file is a closure obligation (TN-9).

### TN-2 — Blast radius of the alias mechanism (⚠️ NOT the whole picture — see TN-14)

Of 926 rows with a non-null timezone, 24 carry an alias this runtime cannot resolve
(`US/Central` ×20, `US/Pacific` ×4). **9 of those 24 have a `game_date` one day later than
the true venue-local date** — all evening games starting 00:00-01:00Z, spanning 2026-05-28
to 2026-07-10. The other 15 are unaffected only because their afternoon instants share a
UTC and local date.

**Only 1 of the 9 is a manifest twin today. The other 8 are latent: each becomes a
duplicate the moment its counterpart perspective is scouted.**

Not a devcontainer artifact. Verified inside the running app container: `tzdata` is NOT
installed, both aliases fail there, and the wrong date reproduces. The Dockerfile is
`python:3.13-slim`, which omits the tzdata `backward` links, and apt-installs only `curl`
and `sqlite3`; there is no `tzdata` pin in requirements. **Production has the same gap.**

`timezone` is a **per-event** value, apparently whatever the event's creator entered — it
varies within a single team's own schedule (one five-game window carried `America/Denver`,
`US/Central` ×3, `America/Chicago`). Do not model it as a team property.

### TN-3 — The degradation is fail-OPEN, and that is the deeper defect

Returning the UTC date on an unresolvable zone produces a **plausible wrong answer with
only a WARNING** — the shape `.claude/rules/python-style.md` warns against, where a
missing safety signal must default to REFUSE rather than proceed. Returning `None` routes
the caller into its existing explicit fallback instead of quietly emitting a date wrong by
a day.

**⚠️ CORRECTED 2026-07-27 during story authoring — the sentence immediately above is
FALSE at the one call site that produced the 9 mis-dated rows.** It holds at
`morning_run.py:224` (falls back to the stored `game_date`) and at
`backfill_game_dates.py:87-91` (counts the skip and leaves the row untouched). It fails at
`_derive_game_date` (`game_loader.py:159-164`), whose existing fallback is
`summary.last_scoring_update[:10]` — the UTC date prefix, **byte-identical to the wrong
string the fail-open path emits today**. So a change that only makes `derive_local_date`
return `None` is a **no-op exactly where this defect lives**, and an acceptance criterion
phrased as "returns `None` on an unresolvable zone" would be satisfied by that no-op while
the 9 rows stay wrong. E-278-04's AC-4a is therefore written as a property about the
resulting DATE, not about a return value. Recorded as **OQ-8**, sent to se-epicA for
confirmation. This does not weaken the fail-closed DIRECTION, which stands (OQ-4: "keep the
fail-closed change anyway") — but note precisely what it does to TN-14's fix-surface item 2:
**item 2's direction survives and its original MECHANISM wording does not**, which is why
that item has been rewritten as a property of the resulting date. Do not read this block as
endorsing item 2's superseded phrasing. It means the caller's fallback
is part of the change, not a beneficiary of it.

Installing `tzdata` fixes the observed 24 rows. **Failing closed fixes the class**, since
the next unresolvable string will not be one we predicted. Both belong in E-278-04.
Dependency changes follow `.claude/rules/dependency-management.md`.

**⚠️ A REFUTED position was briefly in this note — do not restore it.** de-epicA argued
that `America/Chicago` (879 rows) and `US/Central` (20 rows) are tzdata aliases for one
offset and therefore "convert identically", concluding the timezone difference is
non-causal. **That is false in our runtime**, and it is checkable in one command:
`ZoneInfo('US/Central')` raises `ZoneInfoNotFoundError` — in the devcontainer and in the
running app container alike. **The two strings are semantically identical and
operationally not.** The conversion never happens; the code degrades to the raw UTC date.
DE reasoned from what the aliases *mean*; as-epicA ran the code on the real payloads.
as-epicA's report wins, and DE has been sent the reproduction.

se-epicA's related correction ("compare resolved offsets, not strings") is right in spirit
and **incomplete for the same reason: you cannot compute an offset for a zone that does not
resolve.** The criterion an AC needs is two-stage — **does the zone RESOLVE in our runtime,
and only then, what offset does it yield at that instant.** Stage one is where the live
defect lives.

Cross-zone rows do genuinely exist, so that concern is not vacuous: `America/Denver` ×16,
`America/New_York` ×6, `US/Pacific` ×4, `America/Phoenix` ×1, NULL ×2. **`America/Phoenix`
does not observe DST**, so its offset relative to Denver changes by season — the one row
where a fixed-offset assumption breaks.

**⚠️ DO NOT carry the "an afternoon start is nowhere near midnight" reassurance into this
branch.** That argument is about **zone-versus-zone** gaps — roughly one hour between
adjacent US zones — and it is sound only there. **The alias branch compares local against
UTC, a 5-6 hour gap for Central, so every game starting at or after roughly 19:00 CDT lands
on the next UTC day.** Evening games are most of a baseball schedule, which is exactly why
**9 of the 24 rows are wrong rather than 1.** se-epicA flagged this against its own earlier
reasoning; misapplying it would make the defect look rare when it is routine.

### TN-4 — A second consumer shares the defect

`src/db/backfill_game_dates.py` also calls `derive_local_date`, so a backfill run today
would re-derive the same wrong dates. It is wired to an operator command
(`src/cli/data.py:570`) and derives from `start_time` only, **skipping NULL `start_time`
rows** — so it can move one twin's date and not the other's. E-278-04 must verify its
behavior against the file rather than assuming the shared fix covers it — AC-5a makes the
recorded verdict checkable by requiring it to name the code path that decides the answer.

### TN-5 — Gap A: detection, and the trigger is NOT the clock

GameChanger's own schedule lists one game twice, 0.96 s apart, under two distinct event ids
(handoff §5.4). Both rows share a perspective, so the byte-equality tiebreaker at
`game_loader.py:1367-1372` classifies them as a doubleheader. **Any fix must tolerate GC
double-listing a game**, and must NOT loosen the schedule-count guard — GC genuinely
reports 2, so no count-based rule can discriminate.

⚰ **RETIRED FOR THE LOAD PATH 2026-07-27 — do not restore; see the SPLIT block below.**
This note opened: *"The discriminator is agreement of scores AND play counts; the
sub-second time delta is a NARROWING condition, never the trigger."* Play counts are 0 and
0 at the load decision point, so that discriminator cannot be evaluated there.

**It survives unchanged on the OFFLINE/audit surface**, where the measurement was taken and
where plays genuinely exist: measured by de-epicA in dev, identical scores plus a
play-count ratio ≥ 0.85 selects exactly one pair across all 37 same-date groups, **zero
false positives**. This uses the season's data to EXCLUDE rather than to authorize a merge,
and a wrong merge is the destructive direction. **The narrowing-not-trigger half also
survives on both surfaces** — the sub-second delta never becomes the trigger; score
agreement is.

**Separation evidence, labeled by locality — the two databases differ and neither overrides
the other:**

| Population | Doubleheader gap | Near-zero deltas |
|---|---|---|
| PROD (handoff §5.4) | 150-180 min | the duplicate alone, at 0.96 s |
| DEV (de-epicA, measured) | **floor 90 min** | **four**: 0.96 s plus three same-date twins at exactly 0.00 s |

Do NOT write "150 minutes" or "four orders of magnitude" into a criterion. The dev floor is
90 minutes and the separation is 3.75 orders. **"The duplicate is the only thing near zero"
is false in dev — CORPUS-WIDE.**

**⚠️ SPLIT (2026-07-27, on se-epicA's execution-ordering finding): TN-5's discriminator and
TN-5's prohibition CANNOT BOTH be honoured at the load decision point, so they now govern
different surfaces.** `_find_duplicate_game` runs inside `load_team`
(`generator.py:1912`); plays load ~340 pipeline lines later (`generator.py:2253`). So at
first load both candidates have **0 plays**, and a naive corroborator reads `0 == 0` as
AGREEMENT — vacuously true for every pair, leaving scores as the sole discriminator, which
two genuine doubleheaders can share. **That is a destructive merge.** On re-scout the ratio
is `0/58`, which never clears 0.85, so the duplicate persists forever. Both directions fail.

- **OFFLINE / audit surfaces**: scores + play-count ratio ≥ 0.85 — validated across 37
  same-date groups, zero false positives. Sound, and it STAYS.
- **LOAD-TIME rule**: score agreement is the TRIGGER, sub-second delta NARROWS, scoped to
  the same-perspective branch. **Play counts MUST NOT be consulted at load** (story 02
  AC-8).

Whether score-plus-delta alone is SUFFICIENT is genuinely unsettled and is forced to an
explicit recorded verdict by story 02 AC-9 rather than decided here. **Knock-on flagged, not
absorbed:** TN-6 cut the collapse primitive because story 02 "stops it at load," which
assumed a load-time rule was straightforwardly available; if AC-9's verdict is that no
adequate corroborator exists, TN-6's reasoning needs re-examining rather than assuming.

**⚠️ SCOPE CORRECTION (2026-07-27, de-epicA, on re-measurement): the sentence above is
correct about the corpus and OVER-BROAD as a constraint on the branch it governs.** All
three 0.00-second pairs carry **disjoint** perspectives, and `_find_duplicate_game` resolves
cross-perspective candidates in an earlier branch — so they can never reach the
same-perspective tiebreaker at `:1362-1372` and cannot be false positives for a rule scoped
there. Exactly one near-zero pair shares a perspective, and it is PAIR-ALPHA. DE's
restatement, which is the form to carry: *"the duplicate is not the only thing near zero
corpus-wide — but it is the only same-perspective thing near zero, and the same-perspective
branch is the only place a near-zero rule would run."* DE notes it wrote the original
without scoping it to that branch. **Score agreement remains the trigger; a sub-second delta
is usable as the narrowing condition inside the same-perspective branch.** (The three
cross-perspective pairs also disagree on score, which is why the cross-perspective branch
does not already collapse them — a separate Class B/C question, not story 02's.)

### TN-6 — Why the same-perspective collapse primitive is NOT here

`merge_duplicate_game` refuses shared-perspective pairs, and the refusal is **structural,
not stylistic**. `perspective_team_id` sits inside the UNIQUE key on every game-child table
(`player_game_batting`, `player_game_pitching`, `plays`, `spray_charts`,
`game_perspectives`). Re-pointing a child row is safe only when the perspectives are
disjoint; when shared, both key columns become equal and **every child re-point collides** —
58 guaranteed `plays` collisions on the known pair alone. Loosening the refusal does not
produce a working merge; it produces one that aborts partway.

Collapsing a same-perspective twin is therefore a **different operation**, requiring a
per-child-table conflict policy that exists nowhere in the codebase. Under the operator
ruling it would be built for rows that reset will delete, against a defect E-278-02 stops
at load. Cut, and parked as an idea with this finding as its promotion rationale.

### TN-7 — Coach ruling on record semantics (BINDING)

baseball-coach, after reading `src/reports/generator.py:396-422` directly:

> **The record reflects games PLAYED, not games we have DATA for. Do NOT add the stat-row
> `EXISTS` gate to `_query_record`.**

A stat-row gate is right for things rendering a player stat line — there is no OBP with no
plate appearances. A win or loss is derivable from a final score alone. The gate would drop
the two bad rows only *coincidentally*, still miss a future duplicate carrying boxscore
lines, and newly drop genuinely-played, honestly-unscored games — real for the
any-`public_id` scope.

**Ties**: match GameChanger's **DISPLAY FORMAT** exactly — always show the trailing `-0`,
never conditionally suppress it. **⚠️ This is a ruling about FORMAT, not about matching
GC's NUMBER, and TN-16 makes the distinction load-bearing**: GC's record is a raw listing
count, so its number is not a target. The format ruling stands entirely. Coach's reason,
which is now partly superseded as stated: the whole defect was our number disagreeing with
theirs, so
adopting their display convention removes one more place a reader must reconcile. Currently
a tie falls through both strict `>` and `<` arms and counts as neither.

### TN-8 — IDEA-220 is CLOSED by investigation. No story.

se-epicA enumerated every `plays` / `play_events` reader in `src/` (11 files by SQL grep,
cross-checked against 27 by name, all extras hand-cleared). **Every coach-facing
plays-derived stat is perspective-filtered**: the five report-section queries in
`generator.py` (FPS%, P-BF, QAB%, P-PA, team aggregates), `pitcher_outings.py:313`, and the
reconciliation engine's chosen-perspective filter. `recon_scoreboard.py`'s aggregates carry
no WHERE filter but `GROUP BY game_id, perspective_team_id, pitcher_id`, so each perspective
is its own unit — structurally immune.

One operator-only counter (`recon_scoreboard.py:388`, `dropped_pitch_events`) counts a
two-perspective game's stranded events twice. **Corrected characterization (se-epicA, and
the correction matters): this is NOT an omitted `WHERE`.** `play_events` **has no
`perspective_team_id` column at all**, so it cannot be filtered without joining through
`plays` — calling it "unfiltered" implies a one-line fix that does not exist.

se-epicA's settled position after de-epicA's repair-surface argument: **the count is right
and the docstring wording is what should change** — each stranded row is separately
repairable by `reload_game_plays`, so counting both perspectives' rows is correct for a
repair-surface measure, while the docstring describes it pitch-level. It never reaches a
coach. Idea-sized wording fix, not a defect.

**Also refuted and not carried**: an earlier `team_rosters` fan-out hazard. de-epicA
confirmed `PRIMARY KEY (team_id, player_id, season_id)`, so the join cannot fan out.

IDEA-220's own promotion criterion — "promote only if the check finds an unscoped consumer" —
is **not met**. Its warning against deleting either perspective's rows stands.

Carry into any reconciliation work: **the engine reconciles a two-perspective game under ONE
perspective only**, so the other perspective's plays are never corrected.

### TN-9 — Closure obligations (artifact corrections)

1. **IDEA-218**: its stated remedy is false for its own case — `plan_duplicate_game_merges`
   groups by `(season_id, game_date, unordered pair)`, so the offline tool cannot reach a
   date-split twin. Its candidate 3 is refuted (TN-1). Its mechanism framing is superseded.
2. **IDEA-217**: the MEASUREMENT (the clause yields a record matching GC's on current data
   — **note per TN-16 that "GC-correct" is the wrong frame**, since GC's number is a raw
   listing count; the measurement stands as an observation, not as a correctness claim)
   stays as recorded evidence; the ARGUMENT gets a superseded-by-coach-ruling annotation
   with date and reasoning pointer.
3. **Triage file §4 item 3**: annotate, do not rewrite — it is evidence of what was
   recommended before the ruling.
4. **IDEA-220**: record that the consumer check is DONE and its result, so it is not re-run.
5. **⚠️ RE-ATTRIBUTED 2026-07-27 — this item previously read "as-epicA's report cites
   '(migration 014)' … do not propagate it," which blamed the relay for a claim the REPO
   generates.** No migration 013 or 014 exists (the set tops out at `012`) and both columns
   come from `001_initial_schema.sql` — that much was right. But
   `migrations/001_initial_schema.sql` itself carries the false attribution in **four
   places**: lines 135-136 in the header comment and lines 147-148 inline in the `games`
   DDL, where they surface in `.schema games` output. as-epicA read it there and relayed it
   accurately. Verified independently by PM and by se-epicA. **"Do not propagate it" was
   therefore incomplete guidance while the source comment stands** — the next reader
   re-derives the identical claim from the canonical schema file with no reason to doubt it.
   **Disposition: FOLDED INTO E-278-04 as AC-9** (comments only, no DDL, no new migration);
   `apply_migrations.py` tracks by filename with no checksum, so a comment edit cannot
   invalidate or re-run an applied migration. Do not discount as-epicA's report generally on
   the strength of the original wording.

### TN-10 — Identifier hygiene

Dev, prod, and the handoff carry real team names, `public_id` slugs, and GC UUIDs. Writing
any under `epics/**` or `.project/**` trips the pre-commit doc-PII byte-gate and blocks the
planning commit. **Refer to rows by date and role only, as this file does.** Never truncate
or prefix a real name to disguise it.

### TN-11 — Fixture locality (CORRECTED 2026-07-27 — Gap A DOES have a live fixture)

**⚠️ This note previously said Gap A has no fixture here. That was WRONG. Do not restore
it.** de-epicA queried dev and both PAIR-ALPHA rows are present: same date, same single
perspective, start times 0.96 s apart, identical scores, 58 plays each.

The evidence that it is a real dev query rather than the handoff echoed back: DE swept dev
*before* reading the handoff's figures, and the `created_at` values it measured **differ
from the handoff's** (one second apart in dev; identical in the handoff). An echo would
have reproduced the handoff's values exactly. The one-second `created_at` gap is itself the
signature — two loads of one game inside a single run.

**So E-278-02's fixture is not invented — it is built from real observed values.**
⚰ **This line previously read "Build against the live dev rows," which is now SUPERSEDED as
an instruction (2026-07-27).** Two reasons: the stored rows are LOSSY — `games` has no
`end_ts` column, so they cannot express the two-hour end-instant divergence the story turns
on — and a dispatch worktree can query neither the live DB nor the live API, so "build
against live rows" named a source no implementer can reach. **The authoritative source is
the payload-value table transcribed in story 02's Technical Approach ("Fixture
specification"), which is repo-durable.** The dev rows remain corroboration for the
existence claim, which is what this TN is actually about.

The locality caution still binds for everything else: the handoff was produced on the live
server, so its other row-level facts are production-side, and prod-side questions become
packaged queries the operator runs live-side, never dispatched work. **A dev query coming
back empty on a handoff row is locality, not refutation — but here the query came back
positive.**

⚠️ The two row ids are GC UUIDs. **They are denylist material and must never be written
into `epics/**` or `.project/**`** (TN-10). Refer to the pair as PAIR-ALPHA.

### TN-15 — Reconciling the three expert accounts (resolve, do not average)

Three agents converged, with residual disagreements that are NOT contradictions once the
questions are separated. Recorded so nobody "splits the difference".

**The alias failure: three-way agreement, and de-epicA has withdrawn its own counter-claim.**
DE executed it and confirmed: `America/Chicago`, `America/Denver`, `America/New_York` and
`America/Phoenix` all RESOLVE; **`US/Central` and `US/Pacific` both raise
`ZoneInfoNotFoundError`.** `tzdata` is not installed, `available_timezones()` returns 498,
and `/usr/share/zoneinfo/US/Central` is absent. DE's earlier "they convert identically"
claim is withdrawn in its own words as *"the same class of error — I trusted a name instead
of running it."* **Production exposure IS confirmed** — as-epicA verified inside the running
app container. DE could not (docker is barred) and correctly labelled its own prod claim
unconfirmed; as-epicA's check settles it.

**PAIR-ECHO: as-epicA and de-epicA are answering DIFFERENT questions.**
⚰ **CORRECTED 2026-07-27 — this note previously read "and both are right", and described
the ECHO rows as re-deriving *"correctly"* from their own stored values. de-epicA has
withdrawn both, in its own words: they re-derive *"self-consistently, not correctly"*, and
"it is not a disagreement." Do not restore either.** One of the two ECHO rows holds a
**wrong date** — the true calendar date is 2026-05-31 and we stored 2026-05-30 — so ECHO is
one-correct-row-and-one-defective-row, not two valid derivations. And the two perspectives
are not disagreeing: they are using two different encodings of "no known start time", one
an all-day calendar event and one midnight local, so the 300-minute gap is the zone offset
**by construction** rather than a genuine payload disagreement.

What survives is the useful half: DE measured whether the code is **self-consistent** —
both rows re-derive to what is stored, which proves the pipeline is deterministic and
proves nothing about whether the answer is right.
as-epicA measured whether the *input* is being interpreted correctly — the upstream payload
carries `is_full_day: true`, so that `start_ts` is a **date marker that should never have
been localized at all** (TN-14). **DE's "still API-only, unresolved" conclusion is
superseded**: as-epicA's addendum answers it. Self-consistent code operating on a
misinterpreted input is exactly the defect.

**PAIR-FOXTROT is one game — as-epicA proved what DE could only indicate.** DE asked that
the epic not say "confirmed", rating it *"high confidence, two corroborating signals, one
contrary"* (identical scores and identical 68/68 play counts, against a 150-minute delta
inside the doubleheader band). That caution was right on DE's evidence. **as-epicA has
stronger evidence DE lacked**: complementary home/away with mirrored scores fetched from
both live schedules. One game, settled.

**`start_time` classification, which `perspective-provenance.md` currently omits.** Measured
across all five disjoint-perspective pairs: three are byte-identical (0.0 min), FOXTROT is
150 min, ECHO is 300 min. The honest classification is **"usually stable across
perspectives, but not guaranteed — observed disagreements up to 300 minutes."** Note the
cross-perspective branch's own comment cites "~30-minute offsets"; both observed
disagreements exceed that considerably.

**An instrument can share the defect it would measure.** DE declined to run
`backfill_game_dates(dry_run=True)` as a survey, because it re-derives through the same
`derive_local_date` that carries the UTC-fallback bug — against the 24 unresolvable-zone
rows it would reproduce the wrong answer and **report agreement.** DE resolved the aliases
by hand instead. Any story tempted to use that command as a measuring device inherits this
trap.

**The 24 rows, and why only 9 are wrong**: all 24 stored a UTC-slice date; the other 15 are
afternoon games where the UTC slice coincidentally equals the local date. Wrong dates fall
on 2026-05-28, 06-03, 06-04, 06-12, 06-17, 06-18, 06-24, 07-07, 07-10.

**Fixing the derivation would have prevented PAIR-FOXTROT entirely** — with a correct date
the pair becomes same-date with exactly matching scores, which the existing cross-perspective
branch already collapses. One cheap fix at the derivation; one twin never created. That is
the strongest argument for E-278-04 leading this epic.

### TN-12 — A dedup-audit query is easy to get half-right

as-epicA's first adjacent-date self-join MISSED the confirmed pair, because it ordered the
join by `game_id` rather than by date and so checked only one direction. The corrected sweep
found it. **A query of this shape returns a confident, plausible, incomplete answer** — any
story writing one owes a check in both directions.

### TN-14 — A SECOND, independent mechanism, shifting the OPPOSITE way

TN-1/TN-2 describe one mechanism. **There are two, and they move dates in opposite
directions.** Established by as-epicA on PAIR-ECHO after de-epicA supplied it.

One perspective's payload for PAIR-ECHO is an **all-day calendar event**: `start_ts` at
midnight UTC, a 24-hour `end_ts`, `timezone: null`, and **`is_full_day: true`**. That
`start_ts` is a **date marker, not an instant.** We localize it as though it were an
instant, which shifts it *back* into the previous day. The other perspective encodes the
same "no known start time" as midnight *local*, which localizes correctly. Both denote one
calendar date; we store two.

**The codebase already documents this exact failure and never generalized it.**
`scouting_loader.py:767-772` explains at length that a UTC-midnight value "would shift back
a day (America/Chicago -> 1899-12-31)" — reasoning applied to the *synthetic* `1900-01-01`
sentinel and never extended to *real* full-day events, which have the identical shape.
`is_full_day` is present in the payload and read by **nothing**: a grep for
`is_full_day|full_day` across `src/` returns only the authenticated `schedule.py`, on a
differently-named key.

**Revised totals — 11 mis-dated rows, two mechanisms, opposite polarity:**

| Mechanism | Direction | Rows | Population |
|---|---|---|---|
| Unresolved alias (TN-1) | **+1 day** | 9 | 2026-05-28 to 2026-07-10 |
| Full-day date marker | **−1 day** | 2 | both NULL-timezone rows in the corpus |

**⚠️ 4 MORE are already queued.** as-epicA measured the live corpus: **6 full-day events,
all 6 mis-dated.** Two are the stored rows; **the other four are not yet completed and each
becomes a mis-dated row the moment it completes and loads.** So the forward count is 11
today plus 4 inbound.

**Both classes reproduce by two independent methods.** as-epicA derived 9 and 2 from the
live payloads, and independently derived the same 9 and 2 from the stored rows by a
different route. de-epicA reproduced the corpus cross-checks on its own connection. Exact
agreement across independent paths is the evidence the mechanism model is right.

**Key the fix on `is_full_day`, not on a null timezone.** They correlate perfectly both ways
in this corpus (6/6 each direction), but that is n=6 with n=2 stored. **`is_full_day` is the
causal signal; null-timezone is a convenient way to FIND these rows, not a rule to build on.**
Both experts state this independently.

**Also confirmed at n=1064: 0 events have an absent or empty `start_ts`**, and 0 stored rows
carry the `1900-01-01` sentinel. So the `end_ts` fallback is a real but **unexercised** code
path — do not build a story around it, and do not assume it is dead either.

**The opposite polarity is load-bearing: a uniform date-shift repair would corrupt one
population while fixing the other.** Any repair must key off the mechanism, never the
symptom.

Only 2 of the 11 are manifest twins today; the other 9 carry a wrong date **now** and
become twins when the counterpart perspective is scouted. **So the coach-facing harm —
wrong game dates and a wrong "Through [date]" freshness line — is live, and larger than
the dedup harm.**

**E-278-04's fix surface is therefore three things, none of them the dedup key:**

1. **tzdata dependency** — install `tzdata`, or normalize aliases to canonical names at ingest.
2. **Fail-closed degradation** — an unresolvable zone must not yield a stored date equal to
   the bare UTC slice of the instant. **(CORRECTED 2026-07-27 — this item previously read
   "return `None` … so callers reach their existing explicit fallback, instead of emitting a
   plausible wrong date behind a WARNING." That mechanism is REFUTED twice over, by TN-3's
   correction block and by OQ-8's ANSWERED entry: at `_derive_game_date` the existing
   fallback IS `[:10]`, identical to the fail-open output BY CONSTRUCTION, so a
   `None`-returning change alone is a no-op there. The DIRECTION stands; the stated
   mechanism does not.)** Expressed as a property of the resulting date — see E-278-04
   AC-4a.
3. **Honour `is_full_day`** — a full-day event's date marker is taken as a raw date slice,
   never localized.

as-epicA's recommendation against widening the dedup key to ±1 day **stands and is
strengthened**: two distinct upstream defects produce these splits, and a looser key would
mask both while genuinely loosening merges for consecutive-day tournament games.

Read-only reproductions (no credentials, no network): `replay.py` and `replay_echo.py` in
`/tmp/claude-1000/-workspaces-baseball-crawl/4aca143d-2d11-40ae-ae02-d8924803b063/scratchpad/apiscout-e278/`.
⚠️ Scratchpad, not durable — re-derive rather than cite if they are gone.

### TN-16 — GameChanger's own record is NOT ground truth (ESTABLISHED BY EXECUTION)

**A GC profile record is a RAW COUNT of that team's OWN schedule listings, not of games
played — and the inflation is PER-TEAM, never global.** Each profile is internally
consistent with its own schedule; **only the side carrying two listings inflates.** Do not
read this note as "GC double-counts." Measured by as-epicA against four live payloads on a
team with a known double-listing:

- profile `team_season.record` = `{win: 30, loss: 12, tie: 0}` — **42 decisions**
- RAW count of every completed schedule listing = **30-12-0, 42 — exactly the profile**
- DEDUPED (same date + opponent + final score collapsed) = **28-12-0, 40**
- exactly two collapsed groups, both wins

It reconciles only if **both** listings of each double-scored game count. **So on a team
with a double-listing, matching GC means reproducing GC's error, and our deduplicated
record is the MORE correct number.**

**Binding consequence: "matches the GC profile record" MUST NOT be an acceptance target
anywhere in this epic.** No AC currently states one — verified by reading all four stories'
criteria, not inferred — and none may be added.

**What survives untouched: the coach's DISPLAY ruling (TN-7).** Adopting GC's three-part
`W-L-T` format is a decision about FORMAT, and nothing here touches it. What is weakened is
only the *rationale sentence* that framed the defect as "our number disagreeing with
theirs" — see the correction in TN-7.

**Same-game evidence, and the cleanest signal is not the timestamps.** The second pair's
start instants are **30 ms** apart, final score 3-2 on both, **inning-by-inning line scores
identical across all 8 innings**, same opponent, same home/away — and `end_ts` diverges
again (1-hour vs 3-hour spans), the same signature as PAIR-ALPHA. The decisive detail is a
judgment-stat divergence that is *internally consistent*: **team hits 9→10 while opponent
errors 2→1.** One batted ball was scored an error by one scorekeeper and a hit by the
other. Two independent scorebooks of one game: runs are unambiguous so they agree, judgment
calls are not so they differ by exactly one play.

**⚠️ SCOPE — do not over-read this, stated at as-epicA's insistence.** The arithmetic was
run on **one team (30-12-0)**. The epic's Background cites a **different** team (GC
25-15-0), which has **not** been checked for a double-listing. **The principle transfers;
the specific explanation does not, yet.** What changes now is framing only: "disagrees with
GC" is no longer automatically our defect. Confirming the Background team needs its
`public_id` routed to as-epicA by the operator — it is an identifier and cannot live here
(TN-10).

**Third independent strengthening of story 02:** this is the **second** confirmed
double-listing, on a second team, both still live in GC's schedule today.

**THE DOUBLE-LISTING IS PERSPECTIVE-ASYMMETRIC, and this is the most useful thing in this
note.** as-epicA checked the OPPONENT side of the OQ-1 double-scored game — identified by
identity (team-name hash matching the opponent-name hash in the details payload, scores
complementary), not by the matching timestamp:

| Perspective | listings of that ONE game |
|---|---|
| the Legion team | **2** (a `.000Z` 1-hour-end and a `.030Z` 3-hour-end; both 3-2, home) |
| the opponent | **1** (the `.030Z` 3-hour-end only; 2-3, away) |

Three consequences, and the second is a trap:

1. **The inflation is a per-team property** — see the scoping at the top of this note.
2. **⚠️ A CLEAN GC RECORD IS NOT EVIDENCE THAT NO DOUBLE-SCORING OCCURRED.** The opponent's
   record reconciles exactly (RAW 25-16-0 == DEDUPED 25-16-0, zero collapsed groups)
   **precisely because it received one listing of a game that WAS double-scored.** Any
   future check reading a clean record as "this game was not double-scored" is exactly
   backwards. Carry this into story 02's detection rationale.
3. **The defect's visibility depends on which team you scout** — two rows from one side, one
   from the other. That is story 02's same-perspective shape, and it independently confirms
   the design decision that **prevention must sit at LOAD** rather than relying on the
   opponent's schedule to disambiguate.

Small corroboration, labeled as such by its author: the listing that survives on the
opponent's side is the `.030Z` / 3-hour variant — the one earlier guessed to be the fuller
scorebook. **Suggestive only; Q2 stays unresolved** and as-epicA again declined to label
the listings on it.

**Unresolved and reported as such:** which listing is tournament-scored vs team-scored
**cannot be determined from these payloads** — the recap carries no structured scorekeeper,
author, or stream-owner field. The 3-hour span hints at the fuller book, but that is
inference and as-epicA declined to label the listings on it.

### TN-17 — PRODUCTION-side findings (RELAYED; source unreachable from here)

**⚠️ PROVENANCE, stated because it bounds every figure below.** These are operator-pasted
outputs from a Live-side investigation whose full report lives on the prod box
(`/ephemeral/scratch/E278-PROD-INVESTIGATION.md`) and is **not reachable from this
environment**. This note is therefore a **relay with no primary to check it against**,
snapshot-dated **2026-07-28**. Treat its figures as evidence-of-a-moment, not as constants,
and do not promote any of them into a criterion.

**1. Prod's phantom is a B-CLASS date-split twin, NOT a mis-attribution.** Its two
perspectives carry `America/Chicago` and `US/Central`, same score, same 68 plays, one day
apart; removing it moves 25-16 to 25-15. **Its perspectives are DISJOINT, so the existing
merge primitive accepts it — only DETECTION failed.** That is clean corroboration for
E-278-04's centrality and for the story-order argument (04 first, because it moves the
`game_date` that dedup groups on).

**2. B-class blast radius confirmed INSIDE the running prod container.** `US/Central` and
`US/Eastern` both raise `ZoneInfoNotFoundError`, `tzdata` absent, Python 3.13.14. **16
`US/Central` rows, 8 mis-dated — and the 8/8 split is mechanism-exact**: only 00:00-01:00Z
starts roll past UTC midnight. ⚠️ **These are PROD figures and are a DIFFERENT POPULATION
from TN-2's dev figures (24 alias rows, 9 mis-dated) and OQ-4's corpus figures (29 of 1064
events). Do not reconcile the three into one number** — the same discipline TN-2 already
carries.

**3. Two detector facts for story 02 and any future D-class detection.**
   - **A FORFEIT is a FALSE POSITIVE** for any detector shaped as "the counterparty's
     schedule lacks this game" — identical signature, entirely benign cause.
   - GC itself lists two games 75 minutes apart against a literal `"Triple Crown
     Tournament"` opponent string. **Upstream data entry, not our defect** — do not build
     detection that treats it as one.

**4. Prod's DB shrank mid-session, 228 → 192 completed games** — report-deletion cascade,
normal operation (report generation is destructive on two axes). **Consequence: the
ingestion handoff's counts are now stale snapshots on BOTH sides.** Verified in response:
**no acceptance criterion in any of the four stories pins a handoff count** — the ACs turn
on payload values and properties, never on a row census.

**5. RESOLVED 2026-07-28 — and it was NOT a conflict. Recorded with a correction to my own
reasoning.**

⚰ **This item previously concluded that a midnight-UTC row being `is_full_day: false`
"means the null-timezone proxy over-counts." That inference is MINE and it is FALSE.** I
conflated two different signatures. **A 7:00pm US Central start IS midnight UTC** — such a
row being `is_full_day: false` is completely unremarkable and says nothing about the
null-timezone proxy. as-epicA measured the discrimination over the 928-row dev corpus:

| Proxy for "full-day event" | rows selected | actual full-day rows |
|---|---|---|
| starts at midnight UTC | **50** | 2 |
| null `timezone` | **2** | 2 |

**Midnight-UTC over-counts by 25x; null-timezone matched the measured population exactly.**
So the counterexample impeaches a proxy the C-class count did not use. **The durable lesson,
now documented in the endpoint doc so the next reader is stopped by it: never size the
full-day population by midnight-UTC.**

**The column decision stands — no `is_full_day` column — on a stronger reason than the
original.** as-epicA accepted my fix-versus-measurement distinction as sound and then
defeated the measurement case on its own terms: **a column added now is NULL for exactly the
rows anyone wants to count.** Sizing the *existing* population would require backfilling it
from the API — and once you have re-fetched, you already have the answer and the column is
redundant. It can only ever describe rows ingested *after* it exists, which is precisely the
population nobody is trying to size. (Supporting: as-epicA has already sized the live
full-day population at **6 of 1064 events across 28 teams** by API read — no migration, one
pass, available on request.)

**Where Live is RIGHT, recorded as agreement rather than as a defeated proposal:**
`is_full_day` is the causal signal and the proxies are lossy. That is exactly what AC-2b
requires, and the quantified version above is sharper than the 6/6 correlation we had.

**One narrow question remains open with Live, and it is a single field:** did its
counterexample row carry a **null** timezone or a real one? If real, the null-timezone proxy
is untouched. If null, that is a genuine first counterexample to the 6/6 correlation and
as-epicA wants to see it. **E-278-04's scope is unchanged either way.**

### TN-13 — Neutral row labels (use these; never an identifier)

de-epicA supplied invented labels so rows can be discussed in planning artifacts without
tripping the doc-PII gate (TN-10). Dates and roles only — no names, `public_id`s, or UUIDs.

| Label | Date(s) | Class | Reachable by existing tooling? |
|---|---|---|---|
| PAIR-ALPHA | 2026-07-25 | same-perspective, sub-second delta, identical scores + plays | **No** — refused, shared perspective |
| PAIR-BRAVO | 2026-06-23 | cross-perspective, scores differ by 1 | **Yes** — offline predicate accepts today |
| PAIR-CHARLIE | 2026-06-10 | cross-perspective, scores differ by 1 | **Yes** |
| PAIR-DELTA | 2026-05-26 | cross-perspective, scores differ by **2** (outside `_SCORE_TOLERANCE_RUNS = 1`) | No — grouped, then refused |
| PAIR-ECHO | 2026-05-30 / 05-31 | **date-split**, disjoint, identical scores + plays | No — never grouped |
| PAIR-FOXTROT | 2026-06-23 / 06-24 | **date-split**, disjoint, identical scores + plays | No — never grouped |
| PAIR-GOLF | 2026-07-21 | genuine doubleheader (adjudicated — OQ-6) | n/a |
| FRESH-1..6 | 6 dates, Mar–May 2026 | genuine doubleheaders (adjudicated — OQ-5) | n/a |

**Forward scope is bounded by this table**: the offline predicate already handles the
same-date disjoint case correctly (BRAVO, CHARLIE), so forward work builds for
**PAIR-ALPHA's shape (same-perspective) and the date-split shape (ECHO, FOXTROT)** — not
for the case that already works. PAIR-DELTA raises a separate forward question: whether
`_SCORE_TOLERANCE_RUNS` should widen from 1 to 2. de-epicA leans against widening the
constant and toward letting a stronger corroborator carry it; that is a design call for
E-278-02, not a settled decision.

## Open Questions

- **OQ-1**: The triage file argues the record perspective clause is complementary
  defense-in-depth. The coach ruling rejects it, pricing a false-negative cost the triage did
  not. Planning on the coach ruling per decision routing; **an operator override would change
  E-278-01's scope.**
- **OQ-2 — ANSWERED, and it validates the coach ruling with data.** Measured by de-epicA:
  **20 genuine cases across 12 of 28 subject teams**, per-team rates **2.4%–15.8%** of a
  team's own completed games. 17 of the 20 have plays recorded from the *opposing*
  perspective — the game was played and charted by somebody, just not by this team.
  **Had the `EXISTS` gate shipped, twenty real games with real final scores would have
  silently vanished from twelve coaches' records** while removing the two bad rows only
  coincidentally. Coach predicted LSB near-zero and other programs not; the spread across
  twelve teams is exactly that. Two methodology notes worth keeping: the obvious narrow
  framing (restricted to games carrying a `game_perspectives` row) returns **1 and is
  wrong**, because that row is written *after* stat data loads and so systematically
  excludes the population being counted; and 10 of the raw 30 were duplicate artifacts —
  an uncollapsed twin necessarily produces two such entries, since each row holds one
  side's stats. **Consequence: coach's additive coverage signal has real material to
  describe (2-16% of a team's own games), not a null set.** Whether it earns a story is
  now a product call, not a measurement question.
- **OQ-3 — DISCHARGED 2026-07-28. The creating path is IDENTIFIED, and the reset
  precondition is lifted.** Per the Live-side trace (relayed — see TN-17 provenance):
  `_resolve_team_ids` branch 2 passes a **free-text opponent name** as the identifier, and
  `ensure_team_row` Step 3 (`src/db/teams.py:167-175`) matches `WHERE name = ? COLLATE
  NOCASE AND season_year = ?` — a rung the module's own docstring calls **"weakest /
  heuristic."** Case-insensitive free-text name matching is the attachment mechanism: **two
  distinct real teams sharing a name within one season collapse onto whichever tracked row
  exists first.** The evidence is code plus identifier-coverage statistics, so **it does not
  depend on retaining the row** — which is what lifts the do-not-reset condition.
  **⚠️ Caveats that bound it.** The trace was read from the local checkout while the running
  prod image is ~8 days old, so **confirm both hops in the ingesting build before treating
  the line references as exact.** And the prod census found **zero** confirmed instances
  among the 23 checkable teams — but only **52 of 786** teams carry a `public_id`, leaving
  **142 of 192** games unverifiable. **Zero-found is not absence.**
  **NO STORY ADDED — PM call, refine before building.** The fix would touch
  `ensure_team_row`, a canonical seam with a wide blast radius, on the strength of zero
  confirmed live instances; that deserves its own scoping rather than a late addition to an
  epic at its final gate, and it is squarely the operator's standing steer. The creating
  path and its caveats are recorded in IDEA-219 so the next session starts from the answer
  rather than re-deriving it.
- **OQ-4 — ANSWERED, and the answer is the OPPOSITE of what it was asked to enable.**
  as-epicA measured the whole reachable corpus: 28 `public_id`s, 28 fetched OK, **1064
  schedule events**, carrying **6 distinct timezone strings plus null**. Two fail to resolve
  — `US/Central` (25) and `US/Pacific` (4) — **29 of 1064 events, 2.7%.** Every event carries
  the key, so absence is always an explicit null.

  **Do NOT scope E-278-04 to a normalization map.** A `{US/Central → America/Chicago,
  US/Pacific → America/Los_Angeles}` map would look evidence-based while being **a denylist
  that fails open** the first time GameChanger emits `US/Eastern`, `US/Mountain`,
  `US/Arizona`, `Canada/Eastern`, or any of the several dozen other tzdata backward links.
  Nothing bounds what GC can send: the field is per-event, appears to be whatever the
  creator typed, and already varies three ways inside one team's schedule. **An enum
  observed closed is not an enum proven closed** — as-epicA cites being bitten by exactly
  this on `age_group` and `ngb`, where a "closed" set kept growing as the corpus widened.

  **Install `tzdata`.** One dependency resolves the entire alias namespace, including
  aliases never seen, and removes the class rather than two instances. A normalization map
  is at best belt-and-braces, never the primary fix. **Keep the fail-closed change anyway** —
  with `tzdata` present the branch becomes nearly unreachable, which is exactly why it
  should fail loudly when reached.

  **Corpus bound, stated plainly:** 28 is every team for which we hold a `public_id` (475
  teams exist; the other 447 are opponent stubs, unreachable). It is a **superset of the
  stored games** — it includes upcoming events — but **not a sample of GameChanger at
  large.**
- **OQ-5 — ANSWERED, and the standing item is a FALSE POSITIVE.** de-epicA adjudicated all
  six pairs (FRESH-1..6): **identical — not disjoint — perspectives on both rows, start
  gaps of exactly 7200 seconds, and materially different scores on every pair.** Different
  scores mean different games. The standing item describes them as a "cross-perspective
  class"; **there is no cross-perspective anything here — they are genuine doubleheaders.**
  Close it as a false positive rather than as "resolved by reset". **Running the merge
  command against them would have been the destructive mistake**; the existing planner
  groups them by date and then correctly refuses on the disjointness gate, so the guard
  held. Confirm the closure with the operator at READY.
- **OQ-6 — ANSWERED. The 116-plays soft flag is a false positive.** All 116 plays on that
  row (PAIR-GOLF) carry a *single* `perspective_team_id` with contiguous `play_order`. The
  triage file's alarm compared 116 against the double-load's 142, but **142 is a
  two-perspective total (71+71) and 116 is a single-perspective count — different
  measures.** Single-perspective distribution across 884 games: min 31, median 59, p95 74,
  max 116. That row *is* the max: a real outlier, not a defect. Related: **42 games carry
  plays under more than one perspective**, so the 142-row game is one of 42, not an anomaly
  — which further supports TN-8's closure of IDEA-220.
- **OQ-7 — ANSWERED. PAIR-ALPHA IS in this database.** de-epicA supplied both row ids from a
  live dev query; `created_at` differs from the handoff's, so it is a real query and not an
  echo. **TN-11 was wrong and has been corrected: the duplicate is real and present, so
  E-278-02's fixture encodes real observed values rather than invented ones.** ⚰ The
  original wording here — *"E-278-02 builds against live dev rows, not synthetic
  fixtures"* — is superseded as an instruction; see TN-11. The fixture's authoritative
  source is the payload-value table in story 02's Technical Approach, because the stored
  rows lack `end_ts` and no dispatch worktree can reach either live source.
- **OQ-8 — ANSWERED by execution, and the answer is stronger than the question.** se-epicA
  confirmed the two paths are **identical by construction**, not merely on our data: when
  `astimezone` raises, `dt` keeps the tzinfo it was PARSED with, and `.date()` on an aware
  datetime returns the written wall-clock date — exactly what `[:10]` slices off the string.
  Six instant shapes executed, all six agreed. So fail-closed alone is a no-op at
  `_derive_game_date` and leaves all 9 evening-game rows mis-dated. **Two consequences now
  in E-278-04**: AC-4a asserts a property of the resulting date (a return-value criterion
  would go green on the no-op), and new **AC-8** requires the test instant to be an EVENING
  one — an afternoon instant has local date == UTC date and passes under every candidate fix
  including doing nothing. SE also supplied the caller-side constraint surface (the `-> str`
  signature, `game_date TEXT NOT NULL`, the date's role as a KEY in three places, and the
  existing `1900-01-01` in-band sentinel's dedup-candidate hazard), all recorded in the
  story. Original question retained below for the record.
- **OQ-8 (original text, now answered).** Does
  fail-closed degradation actually change anything at `_derive_game_date`? Its existing
  fallback is `summary.last_scoring_update[:10]`, which appears byte-identical to the
  fail-open output, making a `None`-returning change a no-op at the one site that produced
  the 9 mis-dated rows. See the correction block in TN-3. Sent to se-epicA. **E-278-04 is
  written so this does not block it** — AC-4a asserts a property of the resulting date, so it
  cannot be satisfied by the no-op whichever way the answer lands. If the reading is wrong,
  the story's Technical Approach says to correct it rather than design around it.
- **OQ-9 — ANSWERED by de-epicA, and (b) WIDENS the design space.**
  **(a) Confirmed: the play-count corroborator is NOT available at the prevention point.**
  DE's 37-group measurement came from `SELECT COUNT(*) FROM plays` on stored rows —
  validation that the discriminator separates, not a prescription for where it runs. Both
  PAIR-ALPHA rows were created one second apart in a single run and the plays stage runs
  after the boxscore load, so neither row has plays when the dedup decision is made. Nuance:
  the corroborator IS available on a re-generation; it is unavailable on the first load,
  which is exactly the load that creates the duplicate.
  **(b) All three 0.00-second pairs are CROSS-perspective, so TN-5's prohibition is correct
  corpus-wide and OVER-BROAD as a constraint on the same-perspective branch.** All three
  carry disjoint perspectives (and all three also disagree on score, which is why the
  cross-perspective branch does not already collapse them). Exactly one near-zero pair shares
  a perspective: PAIR-ALPHA. DE's own restatement: *"the duplicate is not the only thing near
  zero corpus-wide — but it is the only same-perspective thing near zero, and the
  same-perspective branch is the only place a near-zero rule would run."* So score agreement
  remains the trigger and a sub-second delta is usable as the narrowing condition there.
  **(c) A constraint DE volunteered, which rules out the obvious substitute:** the first
  row's stat rows ARE committed and readable when the second row's check runs, but the two
  rows carry materially different content — 18 batting rows vs 10, 4 pitching vs 1 — despite
  identical scores and 58 plays each. **A naive "identical player line sets" test would not
  fire on this pair.** DE declined to recommend a predicate on n=1 and the story does the
  same. Original question retained below.
- **OQ-9 (original text, now answered).** Two
  questions bounding E-278-02's design space, both sent to de-epicA:
  **(a) Can the play-count corroborator be evaluated where prevention has to happen?**
  TN-6 cut the collapse primitive because E-278-02 "stops it at load", so the second row
  must be prevented in `_find_duplicate_game` — which runs during the boxscore load, while
  plays load later via the report generator's plays stage. Both listings arrive in the same
  crawl, so neither row has `plays` rows at the decision point. If so, "agreement of scores
  AND play counts" is a sound OFFLINE discriminator that cannot be evaluated at the
  decision point, and the story needs a corroborator available in the payload.
  **(b) Are the three dev 0.00-second same-date pairs same-perspective or
  cross-perspective?** `_find_duplicate_game` resolves cross-perspective candidates in an
  earlier branch, before the same-perspective tiebreaker at `:1362-1372` is reached. If
  those three are cross-perspective they are not false positives for a rule scoped to that
  branch, and the sub-second delta may be usable as a trigger there. If they are
  same-perspective, TN-5's prohibition stands exactly as written. **Until answered, the
  story writes to the prohibition as stated** — the conservative direction, since a wrong
  merge is the destructive one.

**Blocking status of open questions (2026-07-27): none of the questions above blocks a
story's acceptance criteria.** This line owns that claim and carries its own date. It
previously lived inside OQ-7's answer, where it was silently falsified the moment OQ-8 and
OQ-9 were added below it — a global claim parked inside one question's answer goes stale
without anyone editing it. Re-date this line when the set of open questions changes.

## History
- 2026-07-27: Created (DRAFT). Six code anchors verified against current main; two
  cross-findings independently re-derived before the triage file existed.
- **2026-07-28: READY.** Review scorecard below.

### Review scorecard

Counts are reconstructed from the per-pass triage summaries. **"Findings" counts what each
pass raised against the spec**; the disposition columns are mine.

| Pass | Findings | ACCEPT | In part | Already fixed | Dismissed |
|---|---|---|---|---|---|
| Internal 1 — baseball-coach holistic | 3 | 3 | — | — | 0 |
| Internal 1 — software-engineer holistic | 8 | 8 | — | — | 0 |
| Internal 1 — api-scout holistic (5 + a 6th with its doc patch) | 6 | 6 | — | — | 0 |
| Internal 1 — code-reviewer spec audit (re-adjudicated) | 10 | 9 | — | 1 | 0 |
| Internal 2 — code-reviewer fresh-context | 15 | 13 | 2 | — | 0 |
| Internal 2 — code-reviewer targeted round 2 | 2 | 2 | — | — | 0 |
| Codex iteration 1 | 4 | 4 | — | — | 0 |
| Codex iteration 2 | 3 | 3 | — | — | 0 |
| **Total** | **51** | **48** | **2** | **1** | **0** |

**Honest labelling notes, because the table flatters the process if read alone:**

- **The first code-reviewer audit ran twice.** Its round-1 report (6 MUST / 5 SHOULD) was
  rendered against text that moved underneath it, so only the **re-adjudicated** report is
  counted. It also **self-retracted one round-1 finding** after following a parameter to its
  consumer; that retraction is excluded from the counts and was honoured as a recorded
  "no change needed" verdict rather than a fix.
- **The two in-part dispositions are both cr2's**, and it withdrew or conceded both after
  seeing the reasoning: S8 (physically reorder the Technical Notes — declined in favour of a
  reading-order note, since TN references are numeric addresses) and S4 (split AC-9 out —
  declined at the time, then **overtaken**: AC-9 was removed entirely on a data-engineer
  ruling, which is the outcome cr2 wanted for a reason neither of us had).
- **Zero dismissals is not a boast.** Every finding was correct on the merits. The reason is
  visible in the epic: a large share were **defects introduced by my own incorporation of an
  earlier finding** — a correction landing while its predecessor stayed. That pattern
  recurred often enough to produce the three-leg sweep now recorded in this epic's process
  history, and reviewers caught several instances the sweep's earlier two-leg form could not
  reach.
- **The Live-side (production) work is NOT counted as a review pass** and is listed
  separately below, because it produced **evidence**, not findings against the spec. It is
  the reason OQ-1 and OQ-3 closed.

### Evidence rounds (not review passes)

- **api-scout OQ-4** — 28 `public_id`s, 1064 schedule events; killed the alias
  normalization-map approach in favour of the `tzdata` dependency.
- **api-scout OQ-1 (two probes)** — established that a GC profile record is a **raw count of
  that team's own schedule listings** (TN-16), and that the double-listing is
  **perspective-asymmetric**, so a clean GC record is not evidence that no double-scoring
  occurred.
- **data-engineer OQ-5 / OQ-6 / OQ-7 / OQ-9** — adjudicated the standing six-Freshman item
  as a false positive, confirmed PAIR-ALPHA is present in dev, and established that the
  play-count corroborator is unavailable at the prevention point.
- **software-engineer OQ-8** — proved by execution that fail-closed alone is a **no-op** at
  the site that produced the nine mis-dated rows.
- **Live-side production investigation (relayed, unreachable source)** — discharged OQ-3 by
  identifying IDEA-219's creating path from code plus coverage statistics; confirmed the
  B-class gap inside the running container (TN-17).

- 2026-07-27: Reshaped after the operator's forward-accuracy-only ruling and as-epicA's
  executed mechanism report. **E-278-03 (same-perspective collapse primitive) CUT before
  instantiation** on de-epicA's UNIQUE-key collision finding (TN-6); number not reused. Gap B
  reframed from a dedup-key problem to a tzdata dependency + fail-open degradation problem.
  IDEA-220 closed without a story on se-epicA's consumer audit (TN-8).
