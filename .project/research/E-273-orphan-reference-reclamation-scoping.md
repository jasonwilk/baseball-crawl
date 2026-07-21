# Handoff Brief — Orphaned Reference Data After Report Deletion

**Date:** 2026-07-20
**Status:** Scoping complete. Planning NOT started — that is your job.
**Audience:** An LLM planning session with repo access. Assumes no prior conversation context.

---

## 0. How to use this document

This is a scoped problem statement, not a plan and not a design. It exists so you
can plan the fix without re-deriving the investigation.

Every claim is labeled:

- **[VERIFIED]** — confirmed against the live dev DB, app logs, or a literal file read during the investigation. Trust these.
- **[REPORTED]** — from a specialist agent's static code reading, not independently re-verified. Likely correct; spot-check before building on it.
- **[OPEN]** — unresolved. Your call to make.

Do not treat this brief as authoritative over the code. Where they disagree, the code wins.

---

## 1. TL;DR

The operator deleted 94 of 96 scouting reports through the admin UI. **Everything
the code was written to do, it did correctly** — zero errors, every cascade
succeeded, referential integrity intact.

But the database is now carrying **681 orphaned teams (of 737)** and **14,326
orphaned players (of 15,613 — 92%)**. None of it is reachable from any surviving
report, and no existing code path will ever reclaim it.

There are **three independent root causes**, not one. A fix that addresses only
the obvious one (the retention leak, visible in the logs) will fix the smallest
share of the problem and appear to succeed.

The operator's requirement:

> "If we have no use for data anymore, we should clean it up. We should not
> knowingly allow orphaned data in our database. The one exception *might be*
> public_id mapping. But it's so inexpensive to fetch it, that I'm still not
> sure it's worth knowingly leaving orphaned data."

---

## 2. What is NOT wrong (read this before framing the work)

This is a completeness gap in a correct system, not an incident. Framing it as a
reliability failure will produce an intervention far larger than warranted.

**[VERIFIED]** All of the following held after the 94 deletions:

- `PRAGMA foreign_key_check` — clean
- `PRAGMA integrity_check` — `ok`
- Zero dangling rows in `player_game_batting`, `player_game_pitching`, `plays`,
  `game_perspectives` pointing at deleted games
- All 64 surviving `games` rows belong to the 2 surviving reports
- No orphan HTML files on disk; no DB rows pointing at missing files
- Zero cascade failures in the logs (20 apparent "error" hits were false
  positives — `errors=0` inside INFO success lines)

**Game-level data cleaned up perfectly.** The leak is confined to the *reference*
tier: teams, players, rosters.

---

## 3. Why nothing ever alarmed

**[VERIFIED]** `PRAGMA foreign_key_check` is structurally incapable of detecting
this class of orphan. It verifies that every *reference* resolves to a live
target. It says nothing about *targets with zero referrers*.

Every orphaned team is a perfectly valid FK target. The DB will report "clean"
indefinitely while carrying 92% dead rows.

**Implication for your plan:** the fix needs its own invariant check. The built-in
integrity tooling will never regress-test this for you.

---

## 4. Measurements

**[VERIFIED]** Live dev DB, 2026-07-20, after the deletions:

| Metric | Value |
|---|---|
| `teams` total | 737 |
| Teams with a surviving report | 2 |
| Teams appearing in any game | 56 |
| **Teams with no report and no games** | **681** |
| `players` total | 15,613 |
| Players with no roster and no stats (naive count) | 9,427 |
| **Players transitively dead** | **14,326 (92%)** |
| `team_rosters` total | 6,096 |
| Roster rows belonging to surviving teams | 34 |
| Roster rows held by orphan teams | 4,899 |
| Teams carrying a `public_id` (total) | 48 |
| **Orphan** teams carrying a `public_id` | **35** |
| `opponent_links` rows | **0** |
| `membership_type='member'` teams | **0** (all 737 are `tracked`) |
| All teams with `is_active = 0` | **737 (100%)** — see §6.3 |
| Unreferenced `seasons` rows | 2 (legacy compound slugs) |

**[VERIFIED]** Do **not** justify this work on disk space. The DB file is 303.3 MB
but **95.2% of pages are freelist**; live data is ~14.5 MB and orphan reference
data is ~3–4 MB. The 303 MB is recoverable by `VACUUM` entirely independently of
any orphan work. This is a correctness/hygiene problem, not a space problem.

### 4.1 Orphanhood is transitive — this is a design constraint, not trivia

**[VERIFIED]** The naive count (9,427) understates the problem. Once orphan teams'
roster rows are deleted, ~4,900 additional players become unreachable, bringing
the true dead set to 14,326.

**A single-pass "delete rows nothing references" sweep would leave ~4,900 players
behind and appear to have succeeded.** Reclamation must compute a transitive
closure from live roots (surviving `reports` rows) and iterate to a fixed point.

---

## 5. Root causes

### RC#1 — Order-dependent retention leak (the visible one)

**[VERIFIED]** `cascade_delete_team` (`src/reports/lifecycle.py:543`) deletes the
`teams` row only when no `games` row still FK-references it. No FK child has
`ON DELETE CASCADE`, so this guard is load-bearing — deleting the row while a
game referenced it would break a still-live report.

The decision is correct at that instant and **is never revisited**. When the
referencing games are deleted later in the sequence, the retained team becomes a
permanent orphan.

**Evidence [VERIFIED]:** app logs show **46 retentions vs 15 full deletes**. The
retention line is emitted at `lifecycle.py:588`, inside `cascade_delete_team` —
so all 46 came from that function, not from `cleanup_orphan_teams`. Sampled
retained teams (91, 45, 6, 23, 14, 2) all now have **0 games**.

No individual delete was wrong. **The bug exists only in the sequence.**

### RC#2 — Opponent stubs were never in scope (the largest share)

**[VERIFIED]** `_delete_report` (`src/api/routes/reports_admin.py:567`) reads one
`team_id` off the report row and cascades that team only. Every report also
creates stub team rows for each opponent on the schedule; nothing deletes those.

The only orphan sweep, `cleanup_orphan_teams` (`lifecycle.py:599`), has **exactly
one caller** — `src/reports/generator.py:2247` — during report *generation*,
scoped to `self.orphan_ids` (stubs that run created). It never runs on delete.

**Weight this higher than the log ratio suggests.** 681 orphans against 96 reports
means most were never in any cascade's scope. A planner optimizing for the 46
logged retentions fixes the smaller half.

### RC#3 — `players` is never deleted by any cleanup path

**[VERIFIED]** `DELETE FROM players` appears **exactly once in the entire
codebase**: `src/db/player_dedup.py:657`, the *merge* path.

`_delete_team_scoped_data` removes `team_rosters` (`lifecycle.py:514`) but never
the `players` those rows pointed at.

**This is independent of ordering.** The 14,326 orphan players would leak on a
perfectly-ordered delete. RC#1 and RC#2 are ordering/scope bugs; RC#3 is a missing
capability. **It needs its own fix — do not assume the team logic transfers.**

**[REPORTED]** `seasons` likewise has no deletion site.

---

## 6. Hard boundaries — read before designing any sweep

### 6.1 `membership_type='member'` teams are NEVER orphans

**[VERIFIED]** `teams` has `membership_type TEXT NOT NULL CHECK(... IN ('member','tracked'))`.
Member teams are load-bearing in at least four places:

- `src/api/auth.py:129` — `_get_permitted_teams`
- `src/api/routes/reports_admin.py:164` — morning-run team picker
- `src/db/teams.py:192-218` — `ensure_team_row` MATCH_ANCHOR
- `src/db/game_merge.py:692`

An LSB member team can legitimately have zero reports and zero games between
seasons. **A naive "no report + no games → delete" predicate destroys them.**

Worse, `_delete_team_scoped_data` deletes `opponent_links WHERE our_team_id IN (...)`
(**[REPORTED]** `lifecycle.py:530-533`). Those rows encode *operator decisions* —
hand-run `bb report map-opponent` resolutions and `no_presence` declarations. No
API call recreates them. A `public_id` is a lookup; an `opponent_links` row is a
judgment.

**Current exposure is LATENT, not active [VERIFIED]:** there are 0 member teams
and 0 `opponent_links` rows in the DB today. The investigation's own orphan
queries did *not* filter on `membership_type` — they were safe only by accident.
Your predicate must scope to `membership_type='tracked'`.

**[REPORTED]** `ensure_team_row` inserts report/scouting teams as `'tracked'` with
`is_active=0` hardcoded (`src/db/teams.py:236`), so `tracked` is a clean
discriminator.

### 6.2 Do not touch rows for surviving games

Reclamation must not touch data for games that survive.

**[VERIFIED] The reconciliation baseline is ALREADY stale — do not read a diff as
caused by your sweep.** `.project/baselines/reconciliation-scoreboard.json` was
snapshotted at `db_game_count = 561`; the DB now has **64**. The deletions
invalidated it before any orphan work began.

Correct sequence: **re-snapshot the baseline first**, then run the sweep, then
expect an **exact no-diff**. A pure reference-data sweep touches no stat rows, so
any movement means the sweep overreached. That makes it an excellent post-sweep
assertion — but only after the re-snapshot, and it is a safety check, **not** a
design driver.

### 6.3 `is_active` is a dead guard — do not predicate anything on it

**[VERIFIED]** `ensure_team_row_with_provenance` hardcodes `is_active` to 0 on
every INSERT (`src/db/teams.py:236`), despite the column's `DEFAULT 1`
(`migrations/001_initial_schema.sql:71`). **All 737 teams are `is_active = 0`,
including both surviving report teams.**

Consequence: Guard 1 of `is_team_eligible_for_cleanup` (`lifecycle.py:681-685`)
has **never rejected anything**. Only Guard 2 (other `reports` rows) protects a
team.

Any sweep guard predicated on `is_active = 1` protects **zero rows**. The
member-team boundary (§6.1) must key on `membership_type = 'member'` directly.

### 6.4 Cross-team player identity is an explicit permanent Non-Goal

This is a **gift** — use it. There is no "this player might matter to another
team" case to reason about. A player unreachable from surviving stats is
unreachable, full stop.

---

## 7. Structural constraints on the fix

### 7.1 There is NO batch boundary to hook

**[VERIFIED]** There is no bulk-delete feature. `reports_admin.py:712` exposes one
route — `POST /reports/{report_id}/delete`, one report per HTTP request. The
94 deletions were 94 separate sequential requests (~2s apart in the logs).

**[REPORTED]** It is worse than N transactions — it is **2N**. `_delete_report`
opens two connections with a commit between: conn1 (`:583-616`) does the report
row + file + eligibility, then `cascade_delete_team` commits internally on conn2
(`lifecycle.py:586` or `:595`).

**"Re-evaluate at end of batch" has nothing to attach to.** The viable shapes are:
a per-request terminal pass, a periodic pass, or an operator command.

**A per-request pass would have fixed RC#1 here** — retention-freeing is
monotonic, so the sweep at request k+1 sees the games deleted at request k. Cost
is O(N) sweeps over a trivially small table; it invents no new batch concept.

### 7.2 The retention branches are the WRONG call sites

**[REPORTED]** Both `cascade_delete_team:585` and `cleanup_orphan_teams:649` know
they retained something, but neither can act — the blocking `games` row belongs to
a *different* team's data that a *later* request deletes. Hooked there, it fires
too early every time. **The seam must be terminal.**

### 7.3 `ON DELETE CASCADE` is NOT the fix — verdict, with reasons

**[REPORTED, high confidence]** Adding cascades is the obvious idea and it is wrong
on three counts:

1. **It cannot reach the biggest leak.** `players` has **no FK to `teams`** at all
   (columns: `player_id, first_name, last_name, bats, throws, created_at`). 14,326
   of ~19,900 orphan rows are unreachable by any cascade rooted at `teams`.
   Cascade fixes the roster leak and nothing else.
2. **The cross-perspective model makes team-rooted cascade semantically wrong.**
   Every stat table carries *two* team FKs (`team_id`, `perspective_team_id`),
   plus `plays.batting_team_id` as a third. A cascade fires on the wrong one. This
   is exactly the F-H1 hazard `_delete_team_anchor_and_orphan_data` exists to
   prevent (docstring at `lifecycle.py:406-421`): team Y's pitcher FPS%/P-BF come
   from plays where `batting_team_id = X` under `perspective_team_id = Y`, so
   deleting X must not destroy them. `_live_report_perspective_ids`
   (`lifecycle.py:363-381`) implements a **conditional** spare. **CASCADE is
   unconditional and cannot express that.** Adding it would silently reopen the
   bug E-253-01 closed — permanently, since whole-game plays idempotency means the
   hole is never re-fetched.
3. **The manual ordering is deliberate, not accreted.** The `games` DELETE is
   guarded by `NOT EXISTS (SELECT 1 FROM game_perspectives ...)`
   (`lifecycle.py:352-360`). A `teams`→`games` cascade would delete a shared game
   the instant one participant is removed, destroying the other participant's data.

**One narrow cascade is endorsed as simplification only:**
`play_events.play_id → plays.id ON DELETE CASCADE`. Genuinely single-parent
ownership, and `lifecycle.py` hand-writes the same "delete `play_events` before
`plays`" subquery three times (`:311`, `:426`, `:474`). **It is not a fix for this
problem and must not be sold as one.** **[OPEN]** Grep first to confirm no caller
relies on deleting `plays` while keeping events.

### 7.4 Recommended seam

**[REPORTED]** `src/reports/lifecycle.py`. It already owns both cascade families
and both shared helpers, and is deliberately **client-free** (no httpx, no jinja2,
no generator import) so the admin route can import it without dragging in the
generation stack. Importable from admin route, CLI, generator, and morning-run
without inverting layering.

Suggested shape: `reclaim_orphan_reference_data(conn) -> ReclaimResult`, called at
the end of `_delete_report` (after conn2 commits) and at the end of
`_cleanup_orphans` (`generator.py:2236`). Wiring it into `cleanup_expired_reports`
additionally gives it a no-operator-action trigger, mirroring how
`reap_stale_generating_reports` was wired (`lifecycle.py:230-235`).

**Three orphan classes with different predicates — one query does NOT cover all three:**

1. **teams** — no `reports` row, no `games` FK, no other live FK, `membership_type='tracked'`
2. **players** — no `team_rosters` row AND no stat rows in `player_game_batting` / `player_game_pitching` / `plays` (batter AND pitcher) / `spray_charts`
3. **iterate to a fixed point** — deleting a team frees roster rows, which frees players

---

## 8. Concurrency — a real, unhandled race

**[REPORTED]** Not a locking problem. `get_connection` (`src/api/db.py:42`) sets
`busy_timeout=30000` + WAL, and the generator keeps short-lived connections, so a
sweep will not deadlock. The race is **logical**:

```
generator.py:1579   self._ensure_team_row()               ← teams row COMMITTED
generator.py:1582   self._create_report_and_run_record()  ← reports row created
```

Between those two lines, the report's own team has no `reports` row and no `games`
row — **indistinguishable from an orphan**, and `is_active=0` makes it look inert.
Wider exposure: opponent stubs are game-less until `GameLoader` writes their games
rows, and post-run stubs sit orphaned until `_cleanup_orphans` at `:2236`.

**No guard exists in this direction.** `_compute_orphans` (`:2225-2234`) is the
TN-4 per-run created-set, which protects a generation from *another generation* —
the inverse.

**This is not hypothetical:** during the investigation the operator deleted reports
while a generation was in flight (it completed mid-deletion at 12:36:40) **[VERIFIED]**.

**[OPEN]** Levers, none endorsed: gate on
`NOT EXISTS (SELECT 1 FROM reports WHERE status='generating')`; a minimum-age
predicate on the team row; or capture-then-re-verify. Note the `generating` gate
has a hole — the window above is *before* the reports row exists.

**[REPORTED]** `docs/ROADMAP.md:82` already documents a related
`cleanup_orphan_teams()` concurrency race, and `:296` schedules a run-scoped fix
before Epic E. Same function, same reachability question, approached from the
creation side. Consider whether the per-run `created_team_ids` attribution
mechanism (TN-4) is the right model to reuse — it already solved "which teams are
mine to delete" across a process boundary.

---

## 9. Test surface

**[REPORTED]** Existing coverage:

- `tests/test_report_generator.py` — 25 refs; `cleanup_orphan_teams` / `cascade_delete_team` ~`:2658-3900`; `cleanup_expired_reports` `:4618-4960`
- `tests/test_admin_reports.py` — route-level: `test_delete_removes_row:303`, `test_ac1_clean_cascade_of_report_only_team:457`, `test_ac6_empty_team_row_cascade:514`, `test_ac1_delete_report_cascades_run_record:592`, `test_ac4_eligible_team_cascade_with_run_row_no_integrity_error:621`, `test_team_delete_cascade_removes_scheduled_runs:698`
- `tests/test_report_negative_paths.py:260` — patches `cleanup_orphan_teams`
- `tests/test_cli_report.py:243-284` — `bb report cleanup` (file sweep only)

**No batch-delete test exists.** Every fixture is single-report or single-cascade.
Nothing sets up two reports where deleting A retains a team that deleting B then
frees. Nothing asserts global post-delete state. Nothing covers the players leak.
Zero concurrency coverage.

### Blocker to plan around

**[REPORTED]** `test_cascade_delete_team_preserves_games_row_when_other_perspective_remains:3267`
and `test_cascade_delete_team_drops_games_row_when_last_perspective:3313` **pin the
current retention behavior as correct**.

- If your fix changes `cascade_delete_team` semantics → these are stale-by-contract and must move in the same change.
- If your fix is an **additive** terminal pass → they stay green. A real point in that design's favor.

---

## 10. Product framing and position

Framing recommended by PM, endorsed:

> The schema has an ownership model that exists only implicitly, and deletion is
> implemented as per-report imperative cascades that structurally cannot enforce it.

Reports are the root set; teams/players/rosters are transitively-owned reference
data. Nothing in the code says so. `cascade_delete_team` answers "what does *this*
team own?" — a local question. "Is this team still needed?" is a global
reachability question no local cascade can answer.

**Do not frame this as "fix the retention leak."** That yields a patch that fixes
RC#1 and leaves RC#2 and RC#3 intact.

### 10.1 The prevention-vs-cleanup tension — settled

`CLAUDE.md` states "Prevention over cleanup," and the operator has previously
pushed back on `bb data` repair commands. **A terminal reclamation pass does not
violate that principle.**

The principle targets *repair tools for messes better insert-time logic would have
prevented*. That rests on an assumption which is **false here**: orphanhood is not
a property of a row at insert time or at any single delete. It is a property of
the graph *after the last referencing delete commits*. You cannot prevent it at
insert time, because at insert time the data is needed.

The operative distinction is **structural-invariant vs operator-repair-surface**:

- A `bb data reclaim-orphans` command the operator must remember to run is the
  anti-pattern — and leaves the invariant violated between runs.
- The same logic as the closing act of deletion is not cleanup; **it is the
  deletion completing.** Nobody calls a garbage collector a repair tool.

**Recommendation:** one function, invoked automatically at the end of every
deletion path, **no operator-facing command**. The 681 existing orphans get
reclaimed by the next deletion, or by a one-shot invocation — but do not ship a
permanent CLI surface for a one-time condition.

**[OPEN]** If you conclude a standalone entry point is unavoidable for the initial
681, that is defensible — but argue for it, don't assume it, and don't let it
become the ongoing mechanism.

### 10.2 `public_id` — recommendation: delete it

The operator's instinct is right and their own cost analysis is the reason. A
`public_id` is recoverable from one `POST /search` via
`resolve_gc_uuid_by_public_id`. A mapping cache decoupled from `teams` would add a
table, a lifecycle, a staleness question, and a consistency invariant — to avoid
an API call the report pipeline already makes. Over-engineering under simple-first.

**But the operator has the asset misidentified.** The expensive-to-recreate data is
not `public_id` — it is `opponent_links` (§6.1). The good news: that middle
position **already exists and is already built**. `opponent_links` is a separate
table keyed on `root_team_id`, decoupled from the `teams` lifecycle by design.
Treat it as **outside the reachability graph entirely**.

**[REPORTED] DE's independent cost analysis agrees — drop them.** The number at
stake is **35**, not 48 (§4). Findings:

- Re-resolution is `public_id → gc_uuid` via `resolve_gc_uuid_by_public_id` →
  `search_teams_by_name`: one or more `POST /search` calls, 25 hits/page. Bounded,
  cheap, already in the hot path of every report run.
- **The hazard is real but not the expected one.** Per
  `.claude/rules/gc-uuid-bridge.md`, a zero-hit search is *ambiguous* —
  punctuation/Unicode-apostrophe quirk (recoverable) vs. genuinely unindexed
  (never recoverable). So the risk is not a *wrong* team; it is silently getting
  *nothing*, degrading a future report (no spray charts, which need `gc_uuid`).
- **Why it mostly doesn't bite these rows:** re-needing the mapping requires
  generating a *new* report for that opponent, and that flow starts from a
  `public_id` the operator supplies via GC team URL. `ensure_team_row` matches *on*
  the supplied value (`src/db/teams.py:147-165`) rather than reading the stale row
  to find it. The cached row saves at most one search call. The unindexed failure
  mode applies to teams reached by *name search*, which is not how these were
  acquired.

**Retention is not free — this should settle it.** A stale `teams` row is a live
`MATCH_ANCHOR` target (`teams.py:126-165`) and **will** be reused, carrying stale
`name` / `season_year` / `innings_per_game` into backfill logic.
`innings_per_game` is load-bearing provenance: per `.claude/rules/data-model.md`,
NULL means "never fetched → ERA on the assumed 7-inning fallback, and the report
flags '(assumed)'." A resurrected row carrying a stale integer would **suppress
the "(assumed)" disclosure on a fresh report** — a silent correctness cost paid to
save one API call.

**[OPEN]** DE did not trace every report-generation entry point to confirm none
does a reverse lookup keyed on a stored team row. Worth one SE confirmation before
locking this in.

---

## 11. Scope

**In:**
- Reachability-based reclamation of teams, players, `team_rosters` (and any other unreachable reference tier)
- Wiring it into the deletion path so the invariant holds after every delete
- One-time reclamation of the existing 681 / 14,326 as an *invocation* of the same pass
- An assertable post-condition

**Out:**
- **Expiry / `cleanup_expired_reports`** — expiry unlinks the HTML and nulls `report_path` but deliberately keeps the `reports` row. The report is still a live root; nothing becomes unreachable. Explicitly out.
- **Morning-run** — creates only; inherits the invariant free if it later deletes.
- **Admin UI surfaces** beyond what the Post-Cascade Probe rule forces (§12). Do not build an orphan-count dashboard — dashboards were deleted in E-239.
- **`is_team_eligible_for_cleanup` guards** — those govern *authorization* to delete. This work is about *completeness*. Different question.
- **Auth-table expiry** — **[REPORTED]** `sessions` (11 rows) and `magic_link_tokens` have **no expiry reaper**; they are deleted only on logout/consume (`src/api/routes/auth.py:514,524,571`). `webauthn_challenges` *does* have a TTL. This is a genuine instance of the operator's "no knowingly orphaned data" standard, but it is a **different mechanism and a different epic**. Named here only so it is not mistaken for completeness of this one.

### 11.1 Vehicle for the one-time reclamation

**[REPORTED]** DE's concrete recommendation, consistent with §10.1: ship the
one-shot as a **migration or a documented SQL script — not a `bb data` command**.
The DELETEs are plain `NOT EXISTS` sweeps and are fully expressible in SQL. This
matches the operator's explicit prior pushback on one-off CLI commands, and avoids
leaving a permanent operator-facing surface for a one-time condition.

---

## 12. Secondary finding — operator blindness

**[REPORTED]** `_delete_report` returns `None` and swallows cascade failure at
`:627-632` with a `logger.warning`; the route (`:719-723`) flashes
`"Report deleted."` unconditionally. **Full delete, partial retention, and cascade
exception are indistinguishable to the operator.** The 46 retentions were
structurally invisible.

`.claude/rules/admin-ui.md` contains a **"Post-Cascade Probe for Retention UI"**
convention written for exactly this helper. It is **not implemented**.

**[OPEN]** Whether this rides along or is deferred is a scoping call.

---

## 12.5 Sweep hazards — checklist before writing any DELETE

**[REPORTED]** from DE, in addition to §6:

1. **`is_active` protects nothing** (§6.3). All 737 rows are 0.
2. **Never reason about a team's data via `team_id` alone.** Three team FKs exist
   (`team_id`, `perspective_team_id`, `plays.batting_team_id`); a `team_id`-only
   check will call a live-report-referenced team unreachable.
3. **Stat-row destruction is permanent** — whole-game plays idempotency
   (`lifecycle.py:373-376`) means a hole is never re-fetched. Touch only
   unreferenced *reference* rows.
4. **Concurrent generation is the sharpest race** (§8). `created_team_ids` is
   in-memory only, so nothing on disk marks a stub as in-flight. Note the
   stale-generating reaper (`lifecycle.py:107`, `STALE_GENERATING_SECONDS = 3600`)
   can hold a `generating` flag for an hour after a crash — so gating on
   "no generating report" can stall a sweep for an hour.
5. **`MATCH_ANCHOR` resurrection is expected, not a regression.** Orphan counts
   growing between sweeps is normal. "Prevent re-creation" must **not** enter scope.
6. **Leave `sqlite_sequence` alone** — AUTOINCREMENT high-water marks
   (`teams`=777, `plays`=106583). Resetting risks id reuse.
7. **`VACUUM` is a separate explicit decision** — rewrites the file, needs ~2x
   free space, takes an exclusive lock. Never implicit inside a delete path.
8. **Deleting unreferenced `seasons` rows is safe** — `ensure_season_row`
   recreates on demand and `derive_season_id_for_team` derives independently.
   All four FK parents (`games`, `team_rosters`, `plays`, `scouting_runs`) were
   checked. Note the 2 unreferenced rows are legacy compound slugs
   (`2025-spring-hs`, `2026-spring-hs`) stranded by E-241's year-only format
   change — a **different mechanism** from delete leakage.

## 13. Success criteria (AC seeds)

**The invariant, as a query.** After any deletion path completes, this returns zero:

> `tracked` teams with no `reports` row referencing them and no `games` row
> referencing them

Equivalents for players (no stat rows, no roster rows) and `team_rosters` (no
surviving team). Write the exact SQL; the shape is what is specified here. Note
the `membership_type='tracked'` scoping (§6.1).

**The test that would have caught this** — highest-value AC in the whole change,
and it **must be a batch test**, because none of the root causes reproduce on a
single delete:

> Generate ≥3 reports sharing at least one opponent stub, where at least one team
> is retained by a cross-perspective `games` FK. Delete all reports. Assert the
> invariant query returns zero — not "assert the delete succeeded."

Order-dependence is the bug. A single-report delete test proves nothing. State
this explicitly or the easy test gets written.

**Observable done:** the operator runs the invariant query against the live dev DB
and gets zero, having deleted nothing manually. `foreign_key_check` and
`integrity_check` still clean. Reconciliation scoreboard unmoved.

**Non-criterion:** do **not** accept "681 orphans removed" as done. That is the
symptom. If the invariant holds, the count is a consequence; if it doesn't, the
count comes back.

---

## 14. Open questions for you

1. **[OPEN]** Does RC#3 (players never deleted) get folded into the same pass, or is it a separate change? It has a different root and a different predicate.
2. **[OPEN]** Fold in the `docs/ROADMAP.md:82` concurrency race, or keep separate? At minimum, do not make it worse.
3. **[OPEN]** Additive terminal pass vs modifying `cascade_delete_team` semantics — §9 shows two tests pin current behavior; additive keeps them green.
4. **[OPEN]** How to reclaim the existing 681 without shipping a permanent CLI surface.
5. **[OPEN]** Concurrency guard shape (§8), given the pre-`reports`-row window.
6. **[OPEN]** Confirm no report-generation entry point does a reverse lookup keyed on a stored team row (DE's one untraced assumption behind the `public_id` recommendation).
7. **[OPEN]** Enumerate every FK to `teams(id)` (**[REPORTED]** ~18 sites in `migrations/001_initial_schema.sql`) rather than trusting any list in this brief — especially `opponent_links.resolved_team_id` and `user_team_access` as reclamation-blocking pins.

---

## 15. Verification queries

Baseline before/after. **Note the `membership_type` filter — omitting it is the
§6.1 landmine.**

```sql
-- Orphan tracked teams (the headline invariant; target: 0)
SELECT COUNT(*) FROM teams t
WHERE t.membership_type = 'tracked'
  AND NOT EXISTS (SELECT 1 FROM reports r WHERE r.team_id = t.id)
  AND NOT EXISTS (SELECT 1 FROM games g
                  WHERE g.home_team_id = t.id OR g.away_team_id = t.id);

-- Transitively dead players (target: 0). Demonstrates the fixed-point need.
WITH live AS (
  SELECT team_id AS id FROM reports
  UNION SELECT home_team_id FROM games
  UNION SELECT away_team_id FROM games
),
orphan_team AS (SELECT id FROM teams WHERE id NOT IN (SELECT id FROM live))
SELECT COUNT(*) FROM players p
WHERE NOT EXISTS (SELECT 1 FROM player_game_batting b WHERE b.player_id = p.player_id)
  AND NOT EXISTS (SELECT 1 FROM player_game_pitching g WHERE g.player_id = p.player_id)
  AND NOT EXISTS (SELECT 1 FROM spray_charts s
                  WHERE s.player_id = p.player_id OR s.pitcher_id = p.player_id)
  AND NOT EXISTS (SELECT 1 FROM team_rosters r
                  WHERE r.team_id NOT IN (SELECT id FROM orphan_team)
                    AND r.player_id = p.player_id);

-- Roster rows held by orphan teams
SELECT COUNT(*) FROM team_rosters
WHERE team_id NOT IN (
  SELECT team_id FROM reports
  UNION SELECT home_team_id FROM games
  UNION SELECT away_team_id FROM games
);

-- Guard: must stay clean
PRAGMA foreign_key_check;
PRAGMA integrity_check;
```

**Values at time of writing [VERIFIED]:** 681 / 14,326 / 4,899 / clean / ok.

---

## 16. Provenance

- **product-manager** — §10 framing, prevention-vs-cleanup position, §6.1 `opponent_links` boundary, §11 scope, §13 criteria
- **software-engineer** — §7 seam and call-site analysis, §8 concurrency race, §9 test surface, §12 blindness, RC#3 discovery
- **data-engineer** — §4 inventory and the "verified NOT leaking" list, §6.3 dead `is_active` guard, §7.3 `ON DELETE CASCADE` verdict, §10.2 `public_id` cost analysis, §12.5 hazards, stale-baseline catch (§6.2), DB-size framing (§4). Independently reproduced the 14,326 transitive figure by a different decomposition (1,197 roster-reachable ∪ 653 stat-reachable = 1,287 live; 15,613 − 1,287 = 14,326).
- **Main session** — all **[VERIFIED]** measurements, log analysis, transitive-closure finding, `foreign_key_check` blindness, no-bulk-delete finding, RC#3 confirmation, retention-log attribution.

### Suggested vision signal

The operator's philosophy statement is a durable data-lifecycle principle not
currently in `docs/VISION.md` in any form:

> "We should not knowingly allow orphaned data in our database."

**Captured** — appended to `docs/vision-signals.md` dated 2026-07-20, per
`.claude/rules/vision-signals.md`. It will surface at the next "curate the
vision" pass. No action needed from you.
