# E-278-04: Resolve timezone aliases; fail closed on an unresolvable zone; honour full-day events

## Epic
[E-278: Game Identity — One Real Game, More Than One Row](epic.md)

## Status
`DONE` (2026-07-28)

## Description
After this story is complete, a game's stored `game_date` is its venue-local
calendar date regardless of which spelling of a timezone GameChanger's payload
happens to carry, and an all-day calendar event is dated from its date marker
rather than localized as though it were an instant. An unresolvable timezone
string no longer produces a plausible wrong date behind a log WARNING.

## Context

This is the largest live defect in the epic and it is a **date** defect, not a
dedup defect. Eleven rows are mis-dated in production today, by **two independent
mechanisms that shift dates in OPPOSITE directions** (epic TN-1, TN-2, TN-14),
and the forward count is 11 today plus **4 inbound** — upcoming events that
become mis-dated rows the moment they complete and load.
Only 2 are visible duplicates now; the other 9 carry a wrong date already and
become duplicates the moment their counterpart perspective is scouted. The
coach-facing harm — wrong game dates and a wrong "Through [date]" freshness line
— is live and larger than the dedup harm.

**Mechanism 1, +1 day, 9 rows.** One perspective's payload carries the timezone
`US/Central`; the other carries `America/Chicago`. These name the same zone, but
`US/Central` is a legacy tzdata "backward" alias that does not resolve in our
runtime, so `derive_local_date` (`src/util/timezone.py:78`) raises
`ZoneInfoNotFoundError`, logs a WARNING, and **falls through with the datetime
still in UTC**, returning the UTC calendar date. For an evening game whose start
instant already crossed 00:00Z, that is the next day. Of 926 rows with a non-null
timezone, 24 carry an unresolvable alias (`US/Central` x20, `US/Pacific` x4) and
9 of those are mis-dated; the other 15 escape only because their afternoon
instants share a UTC and local date.

**Two alias counts appear in this epic and they measure different populations —
do not reconcile them into one figure.** The 24 above are STORED `games` rows.
Epic OQ-4's separate measurement — `US/Central` x25 and `US/Pacific` x4, **29 of
1064 schedule events, 2.7%** — covers the reachable EVENT corpus across 28
`public_id`s, which includes upcoming events that have no stored row yet. Every
event carries the `timezone` key, so an absent value is always an explicit null.
That corpus is a superset of the stored games and **not** a sample of
GameChanger at large.

Two counterfactuals were **executed**, not reasoned: repairing only the alias and
changing nothing else makes both perspectives yield the same date (so the alias
failure is the necessary cause), and keeping both aliases while equalizing the
instants produces no split (so the 2.5-hour instant disagreement alone does not
split).

**Mechanism 2, −1 day, 2 rows.** One perspective encodes a game as an all-day
calendar event: `start_ts` at midnight UTC, a 24-hour `end_ts`, `timezone: null`,
and `is_full_day: true`. That `start_ts` is a **date marker, not an instant**. We
localize it as though it were an instant, which shifts it *back* into the
previous day. The other perspective encodes the same "no known start time" as
midnight *local*, which localizes correctly. Both denote one calendar date; we
store two.

**Key the fix on `is_full_day`, not on a null timezone.** The two correlate
perfectly in this corpus, 6/6 in each direction — but that is n=6, with only n=2
stored. `is_full_day` is the **causal** signal; a null timezone is a convenient
way to FIND these rows, not a rule to build on. Both experts state this
independently, and AC-2b exists to keep an implementation from quietly keying on
the proxy.

**The codebase already documents this exact failure and never generalized it.**
`scouting_loader.py:767-772` explains at length that a UTC-midnight value "would
shift back a day (America/Chicago -> 1899-12-31)" — reasoning applied to the
*synthetic* `1900-01-01` sentinel and never extended to *real* full-day events,
which have the identical shape. `is_full_day` is documented in our own API spec
(`docs/api/endpoints/get-public-teams-public_id-games.md`, the field table) on
the very payload `_build_games_index_from_data` reads, and is read by nothing:
the only `full_day` reader in `src/` is the authenticated
`src/gamechanger/crawlers/schedule.py`, on a differently-named key.

**The opposite polarity is load-bearing.** A uniform date-shift repair would
corrupt one population while fixing the other. Any correction must key off the
mechanism, never the symptom.

**Not a devcontainer artifact.** Verified inside the running app container:
`tzdata` is not installed, both aliases fail there, and the wrong date
reproduces. The Dockerfile is `python:3.13-slim`, which omits the tzdata
`backward` links, and apt-installs only `curl` and `sqlite3`; there is no
`tzdata` pin in requirements. Production has the same gap.

**`timezone` is a per-event value**, apparently whatever the event's creator
entered — it varies within a single team's own schedule (one five-game window
carried `America/Denver`, `US/Central` x3, `America/Chicago`). Do not model it as
a team property.

## Acceptance Criteria

- [ ] **AC-1**: Given two otherwise byte-identical game payloads that differ only
      in that one carries a legacy alias (`US/Central`, `US/Pacific`) and the
      other its canonical IANA name, and whose start instant is an evening game
      that has already crossed 00:00Z, when each is loaded, then both store the
      **same** `game_date`, and that date is the venue-local one — not the UTC
      one.
- [ ] **AC-2**: Given a payload carrying `is_full_day: true` and a midnight-UTC
      `start_ts`, when it is loaded, then the stored `game_date` is the calendar
      date named by that marker and NOT the previous day.
- [ ] **AC-2b**: Given two payloads that differ only in `timezone` — one null,
      one a resolvable IANA name — and both carrying `is_full_day: true`, when
      each is loaded, then both take the full-day path and store the same date.
      Given a payload with a null `timezone` and `is_full_day: false`, when it is
      loaded, then it does **not** take the full-day path. The full-day behavior
      keys on `is_full_day`, never on a null timezone — per Technical Approach.
- [ ] **AC-3**: Given a single load containing both an AC-1 row and an AC-2 row,
      when it completes, then both rows hold their correct venue-local dates
      simultaneously. Neither mechanism's correction moves the other's
      population.
- [ ] **AC-4a** (the date property — must not be conditional on logging): Given a
      timezone string this runtime cannot resolve and that is not one of the
      aliases AC-1 covers, when a game with an evening instant is loaded, then the
      stored `game_date` **differs from the bare UTC date slice** of that instant.
- [ ] **AC-4b** (the degradation is observable): Given the same load, when it
      completes, then the degradation is recorded in a way an operator can detect
      **without reading logs** — in the stored row, the load result, or another
      durable signal. A log WARNING alone does NOT satisfy this: that is exactly
      what today's fail-open path already emits, so a log-only criterion would be
      satisfied by the defect under repair.
- [ ] **AC-4c** (no silent zone substitution — the fail-closed direction, RULED):
      Given a timezone string that is **present but unresolvable**, when the game
      is loaded, then the system does not silently substitute a different zone
      (the operating-timezone default included) and present the result as a
      venue-local date. Per Technical Approach; substituting an unverified zone
      satisfies AC-4a while remaining fail-OPEN, which is the deeper defect TN-3
      names, not the fix for it.
- [ ] **AC-5a**: Given `src/db/backfill_game_dates.py`, which shares
      `derive_local_date`, when this story is complete, then the implementer has
      recorded a written verdict on its behavior under this change — "no change
      needed" included — and that verdict **names the specific code path that
      determines the answer** (its tier structure and the `tz_name = timezone or
      operating_tz_name` fallback), so the verdict is checkable against the file
      rather than taken on trust. A test demonstrates that a backfill run over a
      corpus containing an **alias** row (AC-1's shape) does not move it to a
      wrong date.
- [ ] **AC-5b**: Given that a stored full-day row is **indistinguishable** from a
      timed row in the `games` schema — no full-day marker is persisted, so the
      backfill sees only a midnight-UTC `start_time` and a NULL `timezone` — when
      this story is complete, then the implementer has recorded an explicit
      verdict on what the backfill should do with such a row: leave it untouched
      under a conservative don't-re-derive-what-cannot-be-verified guard, or
      document the limitation and accept it. **Adding a full-day column to
      `games` is NOT an option here** (see Technical Approach). Either verdict
      passes; silence fails.
- [ ] **AC-6**: Given the runtime the application actually ships, when this story
      is complete, then `tzdata` is a declared dependency following
      `/workspaces/baseball-crawl/.claude/rules/dependency-management.md`, and
      AC-1 holds without any alias-to-canonical-name mapping table existing in
      `src/`. A normalization map is NOT an acceptable substitute — see Technical
      Approach for why this is settled rather than open. **Declaring is not
      installing**: a `requirements.in`/`.txt` edit alone does not make `tzdata`
      importable in a shared-venv worktree, and AC-1 cannot pass without it, so
      the implementer also installs it into the working environment and reports
      that alongside the requirements change. Measured in this checkout at
      planning time: `tzdata` NOT installed, `available_timezones()` = 498,
      `US/Central` and `US/Pacific` both raising.
- [ ] **AC-7**: Given the prose across the repository that describes how the
      date derivation degrades, when this story is complete, then the implementer
      report **contains a list of those sites, each with a verdict** ("no change
      needed" included), that list **contains every site Technical Approach names
      as a floor**, and every claim left standing in the code describes the
      behavior the code now has. **A list identical to the floor FAILS** — the
      floor is known incomplete, so a superset is the passing condition. The list
      is the artifact under review; how it was produced is the implementer's
      business, but Technical Approach explains why copying the floor will not
      produce a passing one.

- [ ] **AC-8** (anti-vacuity guard on AC-1 and AC-4a): Given the instants used to
      exercise AC-1 and AC-4a, when those tests run, then each instant is one
      whose venue-local date and UTC date **differ**. An afternoon instant has
      local date == UTC date and therefore passes under every candidate fix
      including doing nothing — a test built on one certifies nothing. Per
      Technical Approach for a worked discriminating instant.
⚰ **AC-9 REMOVED 2026-07-27 — do not reinstate without a data-engineer ruling.**
It required correcting the four false "migration 014" comments in
`migrations/001_initial_schema.sql`. **`migrations/**` is data-engineer's domain,
and DE has a standing ruling that closes this exact case** — see Technical
Approach. The defect is real and is now tracked as an idea; this story no longer
touches `migrations/`.

## Technical Approach

Epic TN-14 names three fix surfaces, and none of them is the dedup key: the
tzdata dependency, fail-closed degradation, and honouring `is_full_day`. (TN-14
states the first as "install `tzdata`, or normalize aliases at ingest"; epic OQ-4
has since settled that either/or in favour of the dependency — see AC-6 below.) Treat them as one story because the polarity
interaction in AC-3 is only observable when all three are in play.

**A caution on AC-4a, because the epic's TN-3 states the fail-closed rationale in
a form that does not hold at the site that produced the defect.** TN-3 says
returning `None` on an unresolvable zone "routes the caller into its existing
explicit fallback instead of quietly emitting a date wrong by a day." That is
true at `morning_run.py:224` (falls back to the stored `game_date`) and at
`backfill_game_dates.py:87-91` (counts the skip and leaves the row untouched). It
appears **false** at `_derive_game_date` (`game_loader.py:159-164`), whose
existing fallback is `summary.last_scoring_update[:10]` — the UTC date prefix,
which is the same wrong string the fail-open path produces today. So a change
that only makes `derive_local_date` return `None` may be a no-op exactly where
the 9 mis-dated rows came from. This is why AC-4a is written as a property about
the resulting date rather than about a return value: a criterion phrased as
"returns `None` on an unresolvable zone" would be satisfiable by that no-op.
**se-epicA has since CONFIRMED this by execution, and it is stronger than
coincidence — the two are identical by construction.** When
`astimezone(ZoneInfo(tz_name))` raises, `dt` keeps whatever tzinfo it was
*parsed* with, and `.date()` on an aware datetime returns the date in its own
tzinfo — the written wall-clock date, which is exactly what `[:10]` slices off
the front of the string. SE executed six instant shapes (UTC-suffixed,
offset-suffixed, space-separated, bare date) and all six agreed. So the two paths
coincide for **any** ISO-8601 string whose first ten characters are the date, not
merely for our data, and there is nothing between the `None` and the slice — the
`or` is the whole path. Fail-closed alone therefore leaves all 9 evening-game rows
mis-dated.

**AC-8 exists because of the other way this goes vacuous.** SE's discriminating
instant is `2026-06-20T02:00:00.000Z` — venue-local `2026-06-19`, UTC
`2026-06-20`. An afternoon instant such as `18:00Z` (13:00 CDT) has local date ==
UTC date and passes under every candidate fix including doing nothing.

**Why AC-4 is split into 4a and 4b.** It previously read as one compound
predicate — "not the bare UTC slice *accompanied only by a log WARNING*" — which
forbids the conjunction and is therefore satisfiable by keeping the wrong date
and upgrading the log to ERROR. The date property must not be conditional on the
logging, so it is now its own criterion. Note also that **once AC-6 installs
`tzdata`, AC-4a's precondition is reachable only through a synthetic invalid zone
string**: there is no real unresolvable alias left to test with, and an
implementer hunting for one will conclude the branch is untestable. Construct the
invalid zone deliberately.

**On AC-5b, and why "just add a column" is closed off.** `games` carries no
full-day marker, and the backfill derives solely from stored `start_time` and
stored `timezone` (`tz_name = timezone or operating_tz_name`). A stored full-day
row is therefore a midnight-UTC `start_time` with a NULL `timezone` — exactly the
shape the backfill would re-localize back a day, re-applying mechanism 2. It
genuinely cannot tell the row apart. Persisting the flag is ruled out below on
scope grounds, so the choice is between a conservative repair-path guard and a
documented limitation. **AC-2b does not forbid the conservative guard**: AC-2b
governs the *load* path's causal rule, where keying on a null timezone would
substitute a proxy for the real signal that is available there. A
don't-re-derive-what-I-cannot-verify rule on the *repair* path is a different
thing — the flag is genuinely absent there, and refusing to touch an unverifiable
row is the fail-closed direction. Decide it explicitly; the two criteria only
look in tension if that distinction is left implicit.

**The constraint surface for a caller-side change** (SE, read directly). None of
these forbids one; together they say what a fix must carry:

1. **`-> str` and `NOT NULL` are both real.** `_derive_game_date` is annotated
   `-> str` and `games.game_date` is `TEXT NOT NULL`
   (`migrations/001_initial_schema.sql:140`). Returning `None` from the *caller*
   is not available without changing the column contract and all three call
   sites: `game_loader.py:415`, `scouting_loader.py:852`, and `:862`.
2. **The derived date is a KEY in three places at once, not a display field.** It
   feeds the schedule-count lookup, then `_find_duplicate_game`, then
   `_upsert_game`; in `scouting_loader` it builds the schedule-count keys and the
   ambiguous-date set. **Any change to the returned string re-groups dedup
   candidates and schedule counts simultaneously.** That is probably desirable
   here — the defect *is* wrong grouping — but make it intentional rather than a
   side effect.
3. **An in-band unknown sentinel already exists and carries a hazard.** The
   absent-instant path returns `"1900-01-01"`, and because `_find_duplicate_game`
   gates on `game_date = ?`, every sentinel-dated game with the same team pair
   becomes a dedup candidate for every other. Bounded but real, and it lands on
   repeat-opponent and doubleheader cases. A second in-band sentinel meaning
   "unresolvable zone" would inherit that behavior. Flagged as a shape, not an
   argument against.
4. **A cleaner instant is already in hand at the same site.** `summary.start_time`
   (= `game.get("start_ts")`) is available and is what `backfill_game_dates`
   re-derives from.

**PM RULING on AC-4c (2026-07-27): the fail-closed DIRECTION binds, and the
operating-timezone fallback is not an acceptable degradation for a
present-but-unresolvable zone.** The loophole is real and worth naming, because it
is the most natural thing an implementer would reach for: falling back to the
operating timezone produces a date that differs from the UTC slice (satisfying
AC-4a) and could be logged (satisfying a weak reading of AC-4b), while silently
substituting a zone nobody verified. That is a plausible wrong answer presented as
a venue-local date — the exact shape `.claude/rules/python-style.md` means by "a
missing safety signal defaults to REFUSE, not to proceed," and the shape TN-3
identifies as the deeper defect beneath the alias bug.

**Note the distinction this ruling does NOT disturb.** `_derive_game_date` already
uses the operating tz when the payload carries **no** timezone at all
(`summary.timezone or get_operating_timezone().key`). That is a different case: no
signal was given, and the documented default applies. AC-4c governs the case where
a zone **was** given and we could not resolve it — there, substituting a different
zone discards information the payload actually supplied.

What "distinguishable" may mean in AC-4b is deliberately open: a venue-local
default zone, a refusal, or a recorded signal on the row are all candidates, and
the constraint surface (`_derive_game_date`'s `-> str` return, its `1900-01-01`
sentinel path, its role in the dedup natural key, and `ScoutingLoader`'s
schedule-count precompute which must key on the byte-identical date string) is
the implementer's to weigh.

`.claude/rules/canonical-seams.md` names `derive_local_date` a canonical seam, so
enumerate its consumers from the symbol and check each one rather than reading
only your own diff — the four known callers are `game_loader._derive_game_date`,
`backfill_game_dates`, `morning_run.py:224`, and `generator.py:2378`. All four
were independently confirmed real by as-epicA.

**On AC-7, and why it forbids working from this list.** The story originally
named three prose sites; as-epicA swept and found at least five. The two that a
three-site list misses are exactly the ones a fix would falsify:

1. **`src/reports/generator.py:2374-2376`** asserts `derive_local_date` *"returns
   None **only** for an absent or unparseable instant; the fallback is
   venue-local 'today', never a UTC slice."* If AC-4 makes an unresolvable zone
   also return `None`, that "only" is false. The call site itself stays correct —
   its tz comes from `get_operating_timezone().key`, always resolvable — so the
   code is fine and **the prose is what rots**, which is why a code-only sweep
   misses it.
2. **`src/db/backfill_game_dates.py:88-91`**, both the comment *"start_time
   present but unparseable -- cannot correct; do not touch"* **and the
   `skipped_unparseable` summary-key NAME**, which would then be counting
   unresolvable-zone skips under a name asserting otherwise. A key name is a
   claim; sweep identifiers, not only sentences.

This is `.claude/rules/python-style.md`'s bound that a contract sweep covers every
tree that DESCRIBES the contract, not only the module graph. Treat the five as a
floor to exceed, not a target to hit.

### Why AC-9 was REMOVED (PM reversal, 2026-07-27)

**I granted a routing exception to let an SE story edit an applied migration's
comments, and I was wrong. Reversed on the domain owner's standing ruling.**
data-engineer's `migration-immutability-basis.md` (E-277, established by
execution) addresses this exact case and **rejects my rationale by name.** I
argued the edit was safe because `apply_migrations.py` tracks by filename with no
checksum. DE established that same fact first — and ruled that it is **not**
sufficient grounds, because the append-only rule should be argued from a
different premise: **there is no mechanical boundary between an inert comment and
a comment documenting DDL semantics** (a CHECK vocabulary, a DEFAULT, an FK's
`ON DELETE` choice). Once "comments may be edited when judged inert" becomes
precedent, the judgment call moves to whoever is editing, and the convention is
the only thing holding the line. DE's prescription: *"Correct stale prose where
readers actually look, and let the applied migration stand as a record of what
was applied."*

Two things worth carrying. **Mechanical unenforceability is not permission** — I
treated "nothing will catch this" as evidence it was safe, which is the same
shape as reading a missing guard as a green light. And **decision routing is not
advisory**: migrations are DE's domain, DE had already ruled, and a PM scope call
does not override a domain owner inside their own domain. The defect is real and
is filed as an idea rather than dropped.

**Superseded reasoning, retained so the reversal is legible:**
`migrations/001_initial_schema.sql` attributes both columns to "migration 014" in
four places — lines 135 and 136 in the header comment, and lines 147 and 148
inline in the `games` DDL, which means they surface in `.schema games` output. No
migration 013 or 014 exists; the set tops out at `012`, and both columns come
from `001_initial_schema.sql` itself. This was originally logged as a citation
error in an expert report, but as-epicA traced it and **the repo generates it**:
the report relayed what the live schema said. Correcting the report alone fixes
one instance and leaves the generator running, so the next agent to open the
canonical schema file or run `.schema games` makes the identical error with no
reason to doubt it. It is folded in here because this story already touches both
columns and the fix is four comments; PM's call, logged so it can be challenged.
Verified against the file at planning time. **Do not touch the DDL** — an applied
migration's structure is frozen; only the comments are wrong.

se-epicA raised the right question about whether editing an applied migration is
safe at all, given the migration-immutability convention. **Checked:
`apply_migrations.py` tracks applied migrations by FILENAME only** — it reads
`SELECT filename FROM _migrations` and inserts `(filename)`, with no checksum or
content hash anywhere in the module. So a comment edit cannot invalidate an
already-applied migration or trigger a re-run, and the DDL never re-executes.
That is what makes AC-9 safe; it would not be safe if the tracker hashed content.

**AC-2's fixture comes from a specific named section, not from the endpoint doc
generally.** Build it from **"Full-Day Events (`is_full_day: true`) — `start_ts`
is a DATE MARKER, not an instant"** in
`/workspaces/baseball-crawl/docs/api/endpoints/get-public-teams-public_id-games.md`.
That section was written for this story (api-scout, 2026-07-27, live-verified) and
carries the four-part shape, the date-marker semantics in prose with a worked
`2026-05-31 → 2026-05-30` example, the correct read (`start_ts[:10]`, no
conversion), and **a full sample record** — which matters because the whole defect
is that a full-day event looks like an ordinary timed one, and a field-table line
cannot show that.

**Do NOT build this fixture from the authenticated schedule doc.** It documents
the same concept in a **different shape** (`full_day` plus `{"date": ...}`
objects) that `_build_games_index_from_data` never receives; the section above
carries a warning to the same effect. Before that section existed, the endpoint
doc had only a one-line field entry with both samples carrying `false`, which is
why this instruction is now specific.

⚰ **A second, CONFLICTING source instruction stood here and is retired
(2026-07-27).** It named the authoritative spec for AC-2's fixture as **both** the
public-games doc **and** the authenticated schedule doc — directly contradicting
the block above, which says to build from the public doc's named section and
explicitly NOT from the authenticated one. The block above is correct and is the
single rule: `_build_games_index_from_data` never receives the authenticated
shape. Build the fixture from the spec rather than from the implementation, per
`.claude/rules/testing.md` (Test-Validates-Spec) — but from **one** spec.

**On AC-6, which epic OQ-4 settled — and settled in the opposite direction from
what it was asked to enable.** as-epicA measured the whole reachable corpus and
ruled against scoping this story to a normalization map: a `{US/Central →
America/Chicago, US/Pacific → America/Los_Angeles}` table "would look
evidence-based while being a denylist that fails open" the first time GameChanger
emits `US/Eastern`, `US/Mountain`, `US/Arizona`, `Canada/Eastern`, or any of the
several dozen other tzdata backward links. Nothing bounds what GC can send — the
field is per-event, appears to be whatever the creator typed, and already varies
three ways inside one team's schedule. **An enum observed closed is not an enum
proven closed.** Installing `tzdata` resolves the entire alias namespace
including aliases never seen, which removes the class rather than two instances.

**Keep the fail-closed change anyway.** With `tzdata` present the unresolvable
branch becomes nearly unreachable — which is precisely why it should fail loudly
when something reaches it. Do not let AC-6 talk you out of AC-4. se-epicA puts
the same caution from the other side: **installing `tzdata` alone masks rather
than fixes.** It resolves the two aliases we happen to store today and leaves the
degradation path exactly as it is, so the next unresolvable string — the class
fail-closed exists to protect against — still silently becomes a UTC date. The
two changes cover different things and neither substitutes for the other.

**Do NOT add an `is_full_day` column to `games`.** DE confirmed the flag is not
persisted (`games` carries `game_id, season_id, game_date, home_team_id,
away_team_id, home_score, away_score, status, game_stream_id, start_time,
timezone, created_at`) and noted that a stored-row detector would therefore have
to infer the shape. as-epicA's scope ruling: that points *away* from a change
here. At ingest the flag is right there in the payload dict —
`_build_games_index_from_data` already reads five other keys off it, so honouring
it is a sixth lookup at the same site, with no migration. A stored-row detector
is only needed for **historical repair**, which the operator's ruling puts out of
scope; once ingest honours the flag, no new mis-dated rows are created and there
is nothing forward for a detector to find. If a later epic takes up historical
repair, persisting the flag becomes a real question then, on evidence.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-278-05 (which renames a field in the same two loader modules) and
  **E-278-02** (which also modifies `game_loader.py`, and whose dedup grouping key
  is the `game_date` this story corrects). This story runs FIRST in the epic.

## Files to Create or Modify
- `src/util/timezone.py` — `derive_local_date` degradation behavior
- `src/gamechanger/loaders/game_loader.py` — `_derive_game_date`, and
  `GameSummaryEntry` if the full-day flag must be carried
- `src/gamechanger/loaders/scouting_loader.py` —
  `_build_games_index_from_data` (reads the payload; does not currently read
  `is_full_day`), and the `:767-772` comment per AC-7
- `src/db/backfill_game_dates.py` — verified by reading per AC-5a/AC-5b; may not
  change. Note its `skipped_unparseable` summary-key NAME is itself in AC-7's
  sweep scope.
- `src/cli/data.py` — **ADDED BY PM AT AC VERIFICATION, 2026-07-28; it was NOT in
  the story's original Files list.** Recorded here because this list is the input
  to the epic's file-conflict sequencing, not to retro-fit the contract. The
  `backfill-game-dates` command surfaces the backfill's summary dict to the
  operator, so the two new skip classes (AC-5a's `skipped_unresolvable_timezone`,
  AC-5b's `skipped_ambiguous_full_day`) are unreported without an edit here and
  `games_processed` stops reconciling against the reported categories. Its command
  docstring is also a claim in AC-7's sweep scope. **Checked for conflicts: no
  other E-278 story touches this file** (the epic's only other reference is TN-4's
  citation), so it introduces no new ordering constraint on 02, 01 or 05.
- `requirements.in` — the `tzdata` dependency (AC-6)
- `requirements.txt` — **REGENERATED, never hand-edited.** Its header says
  *"GENERATED by pip-compile — do not edit it directly"* and it is built with
  `--generate-hashes`, so a hand edit breaks the hash lockfile. Regenerate via
  `pip-compile requirements.in -o requirements.txt --strip-extras
  --generate-hashes`.
- `requirements-dev.txt` — **REGENERATED. A PLANNING OMISSION, added by PM
  2026-07-28 after code-reviewer caught it; it was missing from this list when the
  story was dispatched.** `requirements-dev.in:5` is `-r requirements.in`, so the
  dev lockfile is a GENERATED SUPERSET of the runtime one and a new runtime pin
  does not appear in it until it is recompiled. Two things depend on that:
  `.github/workflows/ci.yml` recompiles **both** lockfiles and runs
  `git diff --exit-code -- requirements.txt requirements-dev.txt`, so drift fails
  CI; and the devcontainer installs from the dev lockfile, so a rebuilt
  devcontainer silently loses the package and AC-1 reverts to red.
  ⚠️ **The lesson generalizes past this story: the authority for which dependency
  artifacts exist is `.claude/rules/dependency-management.md`'s File Layout, NOT
  this Files list.** AC-6 binds to that rule. Both the implementer and PM verified
  the three artifacts named here and neither derived the set from the rule, which
  is how a four-artifact change shipped as three.
- `pyproject.toml` — its `dependencies = [...]` list carries the comment
  *"Runtime dependencies -- keep in sync with requirements.in"*, so declaring
  `tzdata` in only the requirements files leaves the two out of sync. Verified at
  planning time; follow `.claude/rules/dependency-management.md`.
- ⚰ `migrations/001_initial_schema.sql` — **REMOVED from this story's scope**
  with AC-9 (see Technical Approach). This story touches no file under
  `migrations/`.
- `tests/test_util_timezone.py`
- `tests/test_loaders/test_game_loader.py`
- `tests/test_scouting_loader.py`
- `tests/test_game_start_time.py`
- `tests/test_backfill_game_dates.py`
- `tests/test_morning_run.py` — **MUST-FIX, not optional cleanup.**
  `test_derive_local_date_unknown_tz_falls_back_to_utc_date` (lines 141-143) asserts
  `derive_local_date("2026-06-20T12:00:00.000Z", "Not/AZone") == "2026-06-20"` —
  **precisely the fail-open contract AC-4a reverses.** It is the only test importer
  of the seam that was missing from this list. Per `.claude/rules/testing.md`
  ("Inverse direction"), a stale test encoding a deliberately-changed production
  contract moves in the same change. Note its instant is an *afternoon* one, so it
  is also an AC-8 case: rewriting it needs an evening instant to discriminate.

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-278-05**: the final set of references to
  `GameSummaryEntry.last_scoring_update` and to the derivation's docstrings.
  E-278-05 renames that field and corrects those docstrings, so it must sweep the
  state this story leaves behind rather than the state that preceded it.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes

Read-only reproductions of both mechanisms existed at planning time as
`replay.py` and `replay_echo.py` under a session scratchpad path recorded in epic
TN-14. **Scratchpad, not durable** — if they are gone, re-derive rather than cite
them.

Historical repair is an explicit epic non-goal under the operator's ruling: the
11 mis-dated rows are resolved by reset, not by this story. This story changes
forward derivation only.

Measured at n=1064: **0 events carry an absent or empty `start_ts`**, and 0
stored rows carry the `1900-01-01` sentinel. So `_build_games_index_from_data`'s
`end_ts` fallback and `_derive_game_date`'s sentinel path are real but
**unexercised** code. Do not build any part of this story around them — and do
not assume they are dead either.

Both mis-dating classes reproduce by two independent methods: as-epicA derived
the 9 and the 2 from the live payloads and again from the stored rows by a
different route, and de-epicA reproduced the corpus cross-checks on its own
connection. Exact agreement across independent paths is the evidence the
mechanism model is right.
