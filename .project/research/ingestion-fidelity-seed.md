# Ingestion Fidelity — Epic B Seed Spec

**Status:** durable, committable, PII-clean replacement for the untracked repo-root
ingestion-bugs handoff (which carried live GameChanger identifiers by design and is
deleted). This file is the spec seed for the roadmap's "Epic B — envelope & identity
fidelity" slice. Companion record: `.project/research/2026-07-27-ingestion-triage.md`
(triage, cross-references, sequencing — carries deliberate tombstones; do not tidy it).

**PII discipline:** this file carries NO team names, public_ids, game/player UUIDs,
player names, or tokens. Every population named here is re-findable from the
regeneratable detection queries included inline. Where the handoff cited a specific
game or team as an example, a neutral label (TEAM-X, "the Jun-23 pair") plus the
re-finding query stands in.

**Anchor policy:** code is cited by file:line AND by symbol/phrase, because lines rot.
Anchors marked **[verified 2026-08-02]** were resolved against the main checkout on
that date. Anchors marked **[handoff pin]** were verified 2026-07-26 against the
handoff's baseline and have NOT been re-resolved — expect drift and re-anchor by
symbol. Concretely observed drift: the handoff's `_detect_team_keys` anchor (862–867)
now resolves to 1135–1144, and its "false comment" anchor (397–399) now resolves to
645–653 — a ~+250-line shift from E-278's `game_loader.py` work. Treat every
handoff-pin line number with that suspicion.

**Provenance:** findings were produced 2026-07-26/27 from the live dev database plus
live GameChanger API probes, then independently validated against a clean
`origin/main` checkout by a second agent, then re-derived and confirmed a third time
by PM discovery for E-278 (see the triage file §3). Claims that were tested and
REFUTED are in §7.4 so nobody re-chases them.

---

## 1. Defect 1 — opponent boxscore envelope silently discarded (all-slug key case)

**Severity: high.** 29 of 228 completed games (12.7%) in the dev DB are missing an
entire team's batting and pitching data. The data is present in the API right now;
this is a parse-side discard, not a data loss. It also causes ~11 unknown-named
players per affected game (§1.5).

### 1.1 Mechanism

`GameLoader._detect_team_keys` in `src/gamechanger/loaders/game_loader.py` (`def` at
:1121; defect at :1139–1140 **[verified 2026-08-02]**):

```python
keys = list(raw.keys())
uuid_keys = [k for k in keys if is_gc_uuid(k)]
slug_keys = [k for k in keys if not is_gc_uuid(k)]

own_key: str | None = slug_keys[0] if slug_keys else None
opp_key: str | None = uuid_keys[0] if uuid_keys else None
```

The boxscore endpoint returns a top-level dict with one envelope per team, keyed by a
team identifier. The loader infers identity from **key shape**: "our team is the
slug, the opponent is the UUID." That inference holds only when the opponent has no
public GameChanger presence. When the opponent DOES have one, GC keys their envelope
with a `public_id` slug too. Then `uuid_keys == []` → `opp_key = None`, and the
opponent's envelope is never read.

There is an all-UUID fallback (matching keys against the owned team's `gc_uuid`), but
it is gated on `own_key is None` (:1144 **[verified 2026-08-02]**, comment "If all
keys are UUIDs"). In the all-slug case `own_key` is set, so it never fires.

### 1.2 Why it is silent

- The only record of the detection outcome is a `logger.debug` ("Boxscore key
  detection: own_key=…") — invisible at normal log level.
- The caller's error path requires **both** keys `None`; never triggers here.
- The opponent read is `opp_data = raw.get(opp_key) if opp_key else None`, and the
  downstream skip site is a bare `if opp_data:` — falls through, no error, no counter.
- Nothing increments `LoadResult.errors`. The E-236 stage classifier is deliberately
  **error-driven, not coverage-driven** (correctly — for a scouted opponent, an
  unscored box score is the modal case), so `errors == 0` → stage `completed`. An
  observed run over 33 games reported `boxscores_fetched=33, load_errors=0,
  load_status=completed` while dropping 7 opponent envelopes.
- `completed_games_with_data` does not catch it: it counts games with data from the
  scouted team's own perspective, and our own side always loaded fine.
- `_resolve_team_ids` uses `opp_identifier = summary.opponent_id or opp_key`, so the
  games row still gets a correct, distinct opponent and a final score — the game
  looks complete while carrying half the data.

### 1.3 `is_gc_uuid` is correct — do not change it

`src/gamechanger/url_parser.py` **[handoff pin]** — full-string-anchored
(`.match()` + `$`), `re.IGNORECASE`. A 12-char slug returns `False`; a canonical UUID
returns `True`. The predicate is right; the inference built on top of it is wrong.
Its exact anchoring is load-bearing for this classification, and commit `c64878c`
(E-247) collapsed three copies into it behind an explicit byte-identical behavior
gate. Changing the regex would break unrelated call sites.

### 1.4 Detection query and evidence

The authoritative blast-radius query (dev DB; expect **29** before the fix, **0**
after backfill):

```sql
WITH sides AS (
  SELECT g.game_id,
    (SELECT COUNT(*) FROM player_game_batting b WHERE b.game_id=g.game_id AND b.team_id=g.home_team_id)
   +(SELECT COUNT(*) FROM player_game_pitching p WHERE p.game_id=g.game_id AND p.team_id=g.home_team_id) h,
    (SELECT COUNT(*) FROM player_game_batting b WHERE b.game_id=g.game_id AND b.team_id=g.away_team_id)
   +(SELECT COUNT(*) FROM player_game_pitching p WHERE p.game_id=g.game_id AND p.team_id=g.away_team_id) a
  FROM games g WHERE g.status='completed')
SELECT COUNT(*) FROM sides WHERE (h>0) <> (a>0);
```

Live-API evidence (identifiers withheld; the query above re-finds the population):
in two affected games probed directly, the opponent envelope was present in the API
keyed by a `public_id` slug, fully populated (lineups of 9 and 12, pitching rows
present) — and unloaded. Two control games against the *same opponents* whose
envelopes happened to be UUID-keyed loaded fine. Four further affected games sampled
from other scouted teams were all `slug+slug` with both envelopes fully populated
(10–16 stat rows per envelope). The affected population spans **5 scouted teams**
(11, 7, 6, 4, and 1 affected games respectively).

### 1.5 Downstream symptom — unknown player names (same bug, no separate fix)

All 29 affected games carry 9–15 unknown-named players each (avg 11.1 ≈ an opponent
lineup plus pitchers). Root cause is the same discard:

- The plays parser does **not** consume `team_players` at all (see §3).
- `src/gamechanger/loaders/plays_loader.py:207,209` **[verified 2026-08-02]** create
  stubs via `ensure_player_row(db, id, "Unknown", "Unknown")`.
- Names are upgraded **only** by the boxscore load's `players` array. Discard the
  opponent envelope and the opponent roster is never named.

Fixing this defect and regenerating heals the names: `ensure_player_row` uses
length-based name preference (longer wins, "Unknown" treated as length 0), so the
upgrade is automatic. §3 is the second, independent fix for names specifically.

### 1.6 Latent ordering risk — fix at the same time (not yet observed)

`own_key = slug_keys[0]` selects by **JSON insertion order**, not identity. In an
all-slug boxscore, if GC ever serializes the opponent first, the opponent's stats
load **as our team's** — silent misattribution, strictly worse than absence. Tested
and NOT occurring: in all 29 games the loaded side's pitching R equals the opposing
team's final score (29/29 consistent). That is an empirical ordering regularity, not
a contract — the code offers no guarantee. `self._team_ref.public_id` is available at
this site and never consulted. Narrower form of the same hole: even in `slug+UUID`
boxscores the slug is never verified against `public_id`. The fix below closes both;
add a test pinning opponent-first ordering.

### 1.7 Required fix

Make classification **identity-based, not shape-based**:

1. Prefer exact match of a key against `self._team_ref.public_id` (case-sensitive as
   GC emits it) → that is `own_key`; the other key is `opp_key`, regardless of shape.
2. Keep the existing `gc_uuid` match for the all-UUID case.
3. Retain shape-based inference only as a last-resort fallback when neither
   identifier is available, and log a **WARNING** (not debug) when falling back.
4. When exactly two keys exist and one is identified, the other **is** the opponent —
   never leave `opp_key` None in a 2-key payload.
5. If a 2-key payload yields no `opp_key`, that is an **error condition**: increment
   `LoadResult.errors` (or a dedicated counter) so the stage classifier can surface
   it. A dropped envelope must never again be indistinguishable from an unscored
   opponent.
6. Fix the false prose (§1.8).

### 1.8 False prose to correct with the fix (TWO sites)

Both claim the absent opponent stat block is "truthful"; both are **false in the
all-slug case**, where the block was present and discarded:

- The comment block ending "the opponent then simply has no per-player stat rows
  (truthful)" — `game_loader.py:645–653` **[verified 2026-08-02]** (the handoff cited
  397–399; drifted).
- The `_resolve_team_ids` docstring, item 2: "these opponents never used GC
  scorekeeping … The opponent row gets no per-player stat rows -- truthful, not
  fabricated" — `game_loader.py:~779–784` **[verified 2026-08-02]**.

### 1.9 Tests

Existing **[names verified 2026-08-02; lines current then]**:

- `tests/test_loaders/test_game_loader.py:839`
  `test_detect_team_keys_uuid_only_gc_uuid_none`
- `tests/test_loaders/test_game_loader.py:906`
  `test_detect_team_keys_classification_byte_identical` — the E-247 hard gate.
- `tests/test_player_line_reconcile.py:1085`
  `test_absent_opponent_block_leaves_an_observable_uncovered_residual` — should
  still pass after the fix.

**No all-slug case exists, and no test pins the buggy behavior** — the fix is free to
change it.

⚠️ **Fixture decision (make it consciously):** the byte-identical gate's 3rd
parametrize case classifies the dashed-but-non-canonical key `team-uuid-jv-001` as
*own*, while the fixture's `TeamRef.public_id` is a different committed sentinel slug
(`_OWN_TEAM_SLUG`, and `_make_loader` — both fixture values already in git, not PII).
An identity-based fix **must consciously define** the
single-slug-that-doesn't-match-`public_id` fallback or this case changes behavior.
Decide deliberately; don't just re-baseline it.

Add: all-slug 2-key payload → correct own/opp split by `public_id`; opponent-first
ordering → still correct (pins §1.6); 2-key payload with no identifiable own key →
error surfaced.

### 1.10 Backfill — two paths; the spec must present both

**There is no idempotency guard on the boxscore stat path.** Per-player upserts are
`ON CONFLICT(game_id, player_id, perspective_team_id) DO UPDATE` (batting and
pitching) and the games row is `ON CONFLICT(game_id) DO UPDATE` **[handoff pin —
cite by conflict clause]**. Missing opponent rows simply INSERT on re-run.

**Path A — regeneration backfill (dev):** fix the classifier, then regenerate a
report per affected scouted `public_id` (5 teams). The normal crawl re-fetches
boxscores and loads the opponent side; the player-name upgrade rides along. No new
CLI is required. Confirm the §1.4 query returns 0. A targeted pass over the 29 games
has precedent (`bb data fix-self-games`, `src/cli/data.py` **[handoff pin]**), but
note the standing guidance against one-off CLI commands for one-time operations.

**Path B — the reset may moot backfill (prod).** Operator ruling, verbatim
(2026-07-27): *"We can reset all prod data. We don't have to repair anything
historically. We only need to ensure we are accurate moving forward."* The standing
prod-healing sequence is rebuild → reset → re-scout, which — run with a fixed
classifier — repopulates everything from the API and leaves nothing to backfill.
The spec should present both paths and let the epic decide which the dev DB gets.

⚠️ **`bb report generate` is DESTRUCTIVE** — reconcile-at-load can hard-delete
`games` and their entire child surface, and orphan reclamation can delete unreachable
`teams`/`players`/`team_rosters`. Never treat regeneration as read-only or purely
additive. E-276's health gate protects retires (deletes), not inserts — adding rows
won't trip it.

---

## 2. Defect 2 — game-ending run dropped when the final play hits a skip path

**Severity: moderate — latent fidelity gap, NOT a live stat error.** 6 games DB-wide
have a plays-derived final score short by exactly one run.

**Impact, stated precisely:** there are effectively **no production consumers** of
the plays running score. The only `src/` reader is the reconciliation engine, which
SELECTs `home_score`/`away_score` but never references them; its `game_runs` signal
uses `games.home_score`/`away_score` as **both** boxscore and plays value, so its
delta is always 0 — a data-availability placeholder. `recon_scoreboard.py` reads no
score columns. Every report surface uses `games.*` scores, which come from the
schedule summary and are **correct** for all 6 games **[handoff pin for all anchors
in this paragraph]**. So W/L, run differentials, and reports are unaffected today.
Fix it because it binds the byte-identical-ingestion north star, not because a
number is currently wrong.

### 2.1 Mechanism — THREE skip paths, not one

`src/gamechanger/parsers/plays_parser.py`, in the `parse_game` loop — all three fire
before the running score is read **[verified 2026-08-02]**:

| Path | `continue` at | Condition |
|---|---|---|
| (a) abandoned PA | :269 | `if not final_details` (comment "AC-9: Skip abandoned PAs") |
| (b) non-PA marker | :297 | `outcome in _NON_PA_OUTCOMES` (`"Runner Out"`, `"Inning Ended"`; frozenset at :83) |
| (c) batter unextractable | :308 | `batter_id is None` |

When a game ends on a walk-off or the instant a run rule is satisfied, GC emits a
**final** play with `name_template` = `"${uuid} at bat"`, **empty `final_details`**,
`did_score_change: true`, and the **updated post-run score**. Path (a) skips it —
correct for stats — but that play carries the only copy of the final score, and being
last, no later row carries it forward.

⚠️ **Generalize the fix.** A game ending on a "Runner Out" with
`did_score_change: true` (path b) — e.g. a walk-off where the trailing runner is
thrown out — strands the final run the same way, as does path (c). Seed from the last
**raw** play regardless of which skip path fired. Fixing only path (a) leaves two
open holes.

### 2.2 Evidence and detection query

Live payloads for two affected games showed exactly the shape above: a final raw play
with empty `final_details`, `did_score_change: true`, and a score one run past the
last emitted play; boxscore finals confirmed the extra run (one was an 8-run-rule
ending). The signature is clean and bounded: **225 games reconcile exactly, 6 short
by exactly 1, none by more** (the 6: one each on 2026-05-26, 05-29, 06-01, 06-10,
06-27, 07-21). Re-find them:

```sql
WITH last AS (SELECT pl.game_id, pl.home_score fhs, pl.away_score fas FROM plays pl
  WHERE pl.play_order=(SELECT MAX(play_order) FROM plays p2 WHERE p2.game_id=pl.game_id))
SELECT g.game_id, g.game_date, g.home_score||'-'||g.away_score box, l.fhs||'-'||l.fas plays_end
FROM games g JOIN last l ON l.game_id=g.game_id
WHERE g.home_score<>l.fhs OR g.away_score<>l.fas;
```

### 2.3 Two tempting fixes are WRONG — documented so they stay unbuilt

**❌ Do NOT remove the skip / emit a sentinel plays row.** `BF` and `AB` in the
reconciliation scoreboard are **row-count-derived** (`src/reports/recon_scoreboard.py`,
comment "a NULL outcome counts as an AB" **[handoff pin]**), and report QAB% / P-PA
denominators are `COUNT(*)` over `plays` (`generator.py`, `COUNT(*) AS total_pa`
**[handoff pin]**). A sentinel row silently corrupts all of these. (`plays.batter_id`
is NOT NULL per `migrations/001_initial_schema.sql`, though the UUID is recoverable
from the `"${uuid} at bat"` template — the stat corruption is the real blocker, not
the FK.)

**❌ Do NOT mutate the last emitted play's score.** It misattributes the run to the
prior PA, garbles that row's `did_score_change`, and in an edge case puts the run in
the **wrong half-inning** — a placed runner scoring on a wild pitch during the first
(abandoned) PA of a half means the last *emitted* play belongs to the previous half.

**✅ Recommended: parser-level game metadata.** Have `PlaysParser.parse_game` (`def`
at plays_parser.py:231 **[verified 2026-08-02]**; currently returns
`list[ParsedPlay]`) also return a final score seeded from the **last play in raw
payload order, regardless of skip path or `final_details`** — e.g. a
`ParsedGamePlays` wrapper carrying `plays + final_home_score/final_away_score`. Sole
caller to update: `plays_loader.py:156` **[verified 2026-08-02]** (plus tests).

### 2.4 Persistence decision — make it IN the spec, before planning any backfill

- **No DB change is required.** There is no plays-final column and
  `games.home_score` is already correct; the recovered value serves the fidelity
  metric and diagnostics. If persisted, use a **game-level column** — never new
  `plays` rows. The dropped play's `did_score_change` is lost either way. The recon
  scoreboard gates no runs stat, so there is no ratchet implication.
- **Plain regeneration cannot repair the 6 games.** Whole-game idempotency at
  `plays_loader.py:143–152` **[verified 2026-08-02]** (`SELECT 1 FROM plays WHERE
  game_id = ? AND perspective_team_id = ? LIMIT 1` → `LoadResult(skipped=1)`) means a
  fixed parser plus regeneration still skips them.
- **The plays-reload path cannot repair them either.** `reload_game_plays`
  (`src/gamechanger/loaders/plays_reload.py` **[handoff pin]**) only UPDATEs existing
  rows and never invokes `PlaysParser.parse_game`; the dropped play was never
  persisted, so there is no row to update. Raw play JSON is persisted nowhere
  (in-memory crawl-to-load).
- Therefore: **if the value is not persisted, there is nothing to backfill** and the
  6 games need no re-ingest. If it is persisted, they need a targeted
  delete-and-reload or a deliberate skip bypass.

### 2.5 Tests

Existing, in `tests/test_plays_parser.py` **[names verified 2026-08-02]**:
`TestAbandonedPAs::test_empty_final_details_skipped` (:194 — the fixture already uses
the exact walk-off shape `outcome = "${uuid} at bat"`, so it is the natural place to
extend), `TestAbandonedPAs::test_only_abandoned_plays_returns_empty` (:208), plus
`test_game_with_abandoned_pa_excluded_from_count` and
`test_correct_play_count_excludes_abandoned` **[handoff pin]**. None in
`tests/test_plays_loader.py`.

Add: a payload whose final entry is skipped (**each** of the three paths) with a
changed score must produce **no extra plays row** AND a correct plays-derived final
score.

---

## 3. Defect 3 — plays `team_players` is fetched and thrown away

**Severity: moderate. Independent of §1.** Every opponent player identity we need is
already in a payload we request on every game, and nothing reads it.

### 3.1 Mechanism

The plays response has three top-level keys: `plays`, `sport`, **`team_players`**.
`team_players` is keyed by team; each entry carries `id`/`first_name`/`last_name`/
`number` for **both** teams — 46–54 named entries per game in sampled games.
`PlaysParser` never consumes it (the identifier appears exactly once in the module,
in a docstring **[handoff pin]**). Meanwhile `plays_loader.py:207,209` **[verified
2026-08-02]** create every player referenced by a play as an
`ensure_player_row(…, "Unknown", "Unknown")` stub. Names are written **only** by the
boxscore load path; whenever that path is absent, unscored, or mis-keyed (§1), the
players stay `Unknown Unknown` forever — even though the correct names arrived in
the same crawl.

### 3.2 The fix, and the §6.4 asymmetric-key trap

Build a **flat `id -> name` lookup across ALL `team_players` keys** and use it to
name the stubs. ⚠️ The two keys are **not** the same shape — the same slug-vs-UUID
asymmetry behind §1 applies here. Never select a key by shape, or this fix reproduces
§1's bug in a new place.

Evidence: across the 7 affected games of one scouted team, **13 of 13** unknown-named
pitchers resolved from `team_players` alone.

Why fix this even after §1: it is defence in depth for identity against any future
boxscore failure, and it heals names **without a re-ingest** of stat rows
(`ensure_player_row`'s length preference upgrades "Unknown" automatically).
`team_players` cannot supply **stat rows** — §1 is still required for those. Do both.

### 3.3 Kill the doc note that describes absent behavior

The context layer already describes this flat lookup **as though it exists**:
`.claude/rules/architecture-subsystems.md:50` **[verified 2026-08-02]** — "**
team_players asymmetric keys**: own team uses `public_id` slug, opponent uses UUID --
build a flat lookup dict across both." (The handoff attributed this to CLAUDE.md; the
sentence actually lives in that rules file.) The parser does not consume
`team_players` at all. Either implement the lookup (preferred) or correct the note
when this story lands; do not leave documentation describing absent behavior. A
context-layer edit routes to claude-architect per `.claude/rules/agent-routing.md`.

---

## 4. Presentation gap — score-only games are indistinguishable from missing data

**This is not an ingestion defect.** The loader behaves correctly; it is a display
problem that cost a live API probe and an operator round-trip to diagnose.

Operator-confirmed: one 2026-06-11 game (7-0) was a **manually scored forfeit**. The
API returned both team envelopes with full rosters attached, all four lineup/pitching
groups present but with **zero `stats` rows**, `team_stats` totals carrying the runs
(`R:7` with `AB:0`), and **0 plays**. DB result: games row + 7-0 score, zero stat
rows, zero errors, status `completed`. `classify_stage_status`
(`src/reports/run_status.py` **[handoff pin]**) is explicitly error-driven and its
guardrail forbids passing coverage as `loaded`/`expected`;
`.claude/rules/architecture-subsystems.md` documents this exact shape as correctly
classifying `completed`. **Not a defect.**

### 4.1 Build a "score-only game" label, NOT a "forfeit detector"

`team_stats` is **discarded** — never read anywhere in `src/` (the JSON key appears
only in the boxscore endpoint doc under `docs/api/endpoints/`). So an offline
detector can only use the derived signature: `status='completed'` + both scores NOT
NULL + zero `player_game_batting`/`player_game_pitching` rows + zero plays.

**That signature does not uniquely identify a forfeit.** It is byte-for-byte the
modal "scored-but-empty / quick-scored" shape. The only differentiator in the live
evidence was `team_stats` (`R:7` with `AB:0`), and it is **unverified** whether
ordinary quick-scored games differ there. Therefore: classify and label as
**"score-only game — no box score in GameChanger"**, which is true for forfeits AND
quick-scored games. Only claim "forfeit" if crawl-time `team_stats` capture is proven
discriminating via API comparison, or the operator annotates the game.

Detection query (current DB-wide count: exactly **1**):

```sql
SELECT g.game_id, g.game_date, g.home_score||'-'||g.away_score FROM games g
WHERE g.status='completed'
  AND (SELECT COUNT(*) FROM plays p WHERE p.game_id=g.game_id)=0
  AND (SELECT COUNT(*) FROM player_game_batting b WHERE b.game_id=g.game_id)=0
  AND (SELECT COUNT(*) FROM player_game_pitching p WHERE p.game_id=g.game_id)=0;
```

### 4.2 Surfaces that currently render such a game misleadingly

All anchors **[handoff pin]** — re-resolve by symbol/role at spec time:

| Surface | Where (by role) | Problem |
|---|---|---|
| **Coverage footer (sharpest)** | M (schedule-derived) and N (data-bearing) counts in `generator.py`; rendered in `scouting_report.html` | The game inflates M but is deliberately excluded from N — "Through {date} (N of M games)" reads permanently as missing data. |
| `coverage_pct` severity | `renderer.py` severity thresholds | Depressed n/m can flip severity quiet → flagged/loud on a game nobody played. |
| Recent Form chips | `_query_recent_games` in `generator.py` → report template | Renders "W 7-0 vs X" indistinguishable from a played game. |
| Runs scored/allowed averages | `generator.py` | A 7-0 skews per-game averages. |
| W/L record | record query in `generator.py` | Defensible for a forfeit, but unmarked. |
| No-games page copy | `renderer.py` | A team whose only completed game is score-only gets M=1/N=0 → "box score data isn't available yet". |
| Header freshness | report template | Excluded from the freshness date, so the report can read staler than the schedule. |
| Admin list | `admin/reports.html` | Shows N. |

**Not affected:** pitcher outings (needs outings rows), plays-derived stats,
query-time season aggregates (all zero-row). Also: exclude score-only games from
**denominators** of derived per-game work, and a decisions surface must treat a
forfeit as a valid **no-decision** (no winning/losing pitcher), not an unresolved
game.

⚠️ **Sequence AFTER the §1 backfill**: until then, the zero-stat-rows signature
overlaps the §1 symptom. After the backfill it is clean.

---

## 5. Ordering constraints

1. **The duplicate-game work (handoff §5) ran FIRST, deliberately — it became E-278
   and is done.** Rationale preserved: the §1 backfill would have fully populated the
   degraded row of the then-live same-perspective duplicate pair, converting a
   half-populated duplicate into a fully-populated one and double-counting the
   second team as well. E-278 shipped **forward prevention only** (start-time
   tolerance in dedup, no historical repairs — see the operator ruling in §7.1).
2. **Within Epic B:** §1 classifier fix (+ ordering pin + fixture decision) → §1
   backfill (confirm the §1.4 query returns 0) → §3 `team_players` consumption
   (independent; parallelizable; mind the asymmetric-key trap) → §2 parser fix (with
   its persistence decision made in-spec FIRST) → §4 score-only labeling LAST.
3. **Prod:** the standing healing sequence is rebuild → reset → re-scout **before any
   prod regeneration**. A reset run on a fixed classifier moots the prod backfill
   entirely (§1.10 Path B).

---

## 6. Absorb-candidate ideas (future spec author triages; one line each)

- **IDEA-219** — free-text opponent name match can attribute a third team's game; the
  creating path is the "Step 3: name + season_year + tracked match" block in
  `ensure_team_row` (`src/db/teams.py:167–175` **[verified 2026-08-02]**); no fix
  shipped yet.
- **IDEA-196** — sticky-misspelling upsert / roster-reachable Unknown-stub residue;
  firewalled from this work but mechanically adjacent (same `ensure_player_row`
  length-preference seam as §1.5/§3).
- **IDEA-221** — report display-formatting defects, including an illegal `5.3 IP`
  render; pure render-path, no ingestion overlap; keep small.
- **IDEA-146 / 147 / 151 / 152** — freshness cluster (staleness-aware plays/spray
  refresh; re-derive `batting_team_id` on orientation change; opponent-link
  resolve-once permanence; accumulate-only hygiene).
- **IDEA-135** — `shf` column mislabeled (is sacrifice flies) in the data dictionary.
- **Pointer:** the classifier sub-chain is NOT this epic — it lives in DRAFT epics
  E-274 / E-275 with floating ideas 176 / 179 / 182 / 184 / 201 / 207 / 209 / 210.

---

## 7. Consciously excluded, with reasons

### 7.1 Historical repair — excluded by operator ruling

Verbatim (2026-07-27): *"We can reset all prod data. We don't have to repair anything
historically. We only need to ensure we are accurate moving forward."* Epic B ships
forward correctness; data repair appears only where it is a side effect of
regeneration (§1.10) or explicitly decided (§2.4).

### 7.2 IDEA-208 (8U–14U pitch-curve suppression)

Deferred by the operator to next season (2026-07-27): not currently reporting to
young arms. Recorded in the idea file's Status as of 2026-08-02.

### 7.3 The 2,037 orphan `Unknown` player rows — POINTER OF RECORD

Of 2,396 `first_name='Unknown'` players, 2,037 have NO batting, pitching, or plays
rows at all. That is the pre-existing orphaned-reference-data issue (operator
principle: "no knowingly-orphaned data") — **distinct** from §1/§3, which concern
players that DO appear in plays but were never named. Do not conflate them.

⚠️ **The handoff cited a scoping home for these at
`.project/research/orphaned-reference-data-handoff.md`. That file NEVER EXISTED.**
The nearest actual record is
`.project/research/E-273-orphan-reference-reclamation-scoping.md`, and **this seed is
now their pointer of record.** Note: roster-reachable stubs survive E-273's
reachability predicate **by design**; IDEA-196 explains that persistence side.

### 7.4 Ruled out during the investigation — do NOT re-chase

Each was tested and found clean (identifiers withheld; verdicts carried):

- **Same bug class elsewhere in `src/`: none.** `is_gc_uuid` outside `url_parser`
  appears only at the §1 defect site and in `crawlers/opponents.py` (format-validates
  a search-result id, not an own/opp split — safe). The §1 site was the only
  tree-wide positional-`[0]`-on-filtered-keys hit.
- **Plays parser does not share the slug/UUID assumption.** `batting_team_id` derives
  from half-inning + games-row home/away; its `uuids[0]` reads are from **template
  strings** per the documented API contract, not envelope shape-guessing.
- **Spray loader safe** — attribution is identity-based via roster lookup;
  unresolvable players are counted and logged.
- **Scouting loader safe** — no key-shape logic.
- **Reconcile-at-load inherits §1 and fails safe** — returns None for the absent
  block; uncovered rows preserved, WARNING logged. Same root cause, not a distinct
  bug.
- **`play_order` gaps are by design for MID-game skips.** Scores are
  absolute/cumulative (documented in the plays endpoint doc and the parser), so a run
  on a skipped mid-game play appears in the next emitted play's score. The one real
  loss case is when the skipped play is the game's LAST — that is §2, all three skip
  paths. No `src/` consumer assumes contiguous `play_order`.
- **Silent own/opp misattribution is not occurring** (29/29 check, §1.6) — latent
  only, still worth hardening.
- **The ~22 non-affected games with unknown players are mostly benign** — sampled
  games showed GC's own `team_players` simply lacks names for 1–2 players; density
  1–12 (avg 3.6) vs 9–15 (avg 11.1) in affected games. Only 2 of 22 were sampled —
  the high-end outliers deserve a look someday, low priority, not the §1 bug.
- **Other integrity classes clean:** plays with NULL `pitcher_id`: 0; games with
  plays but no boxscore rows: 0; self-games: 0.
- **§8.1-class gaps are vision-signal material, not defects, already captured:**
  `player_game_pitching.decision` is 100% NULL (GC never populates W/L/SV — must be
  derived from play-by-play); `plays` carries no baserunner state (save rule's
  on-deck clause uncomputable → derived saves understated, not wrong); no
  inherited-runner tracking (losing-pitcher approximation misattributes). Do not
  expand scope into these without the operator asking.
- **A soft flag from triage, unresolved:** one 07-21 "genuine doubleheader" row
  carries 116 plays — far above the 47–77 per-game norm — and the doubleheader
  adjudication did not check play-count anomalies. Worth one query if dedup work
  reopens (E-278's lane, not Epic B's).

### 7.5 Not carried from the handoff (deliberately)

- The enumerated 29-game affected list, the 6-game §2 id list, all example game/team
  identifiers, opponent `public_id` slugs, and the one real team name — PII;
  regenerated on demand by the §1.4 / §2.2 / §4.1 queries.
- The handoff's §1 operational preamble (worktree-guard mechanics, story-gate,
  pytest-piping, DB backup, API probe snippet) — already canonical in
  `.claude/rules/` and `docs/`; a spec seed should not fork copies of it. One
  reminder kept: **back up the dev DB (`python3 scripts/backup_db.py`) before any
  mutating pass.**
- The handoff §5 duplicate-game analysis in full — implemented and closed as E-278;
  the triage file and E-278's archived epic are the records.

---

## 8. Instrument caveat — verify the yardstick before trusting the backfill verdict

The prescribed before/after measurement for the §1 backfill is
`bb report reconcile-scoreboard`. **That instrument is currently compromised per
IDEA-195:** the ratchet gate was retired 2026-07-26 (diagnostic-only now), but
~180 lines of the retired gate machinery still live in
`src/reports/recon_scoreboard.py` — `default_baseline_path`, `load_baseline`,
`evaluate_gate`, `write_baseline`, `GateResult` all present at :492 onward
**[verified 2026-08-02]**. Verify or fix the instrument (IDEA-195's deletion) before
trusting its verdict on the backfill; at minimum, confirm which code path the CLI
actually runs. Restoring opponent rows should only improve the gated stats. Do not
`--update-baseline` without operator review — the JSON diff is the human review
point.

And once more, because it is the least obvious thing in this repo: **report
generation and deletion are DESTRUCTIVE** (reconcile-at-load hard-deletes; orphan
reclamation hard-deletes). Every backfill-by-regeneration step in this seed inherits
that. Snapshot first.
