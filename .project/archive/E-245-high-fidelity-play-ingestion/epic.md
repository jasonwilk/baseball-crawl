# E-245: High-Fidelity Play Ingestion

## Status
`COMPLETED`
<!-- Lifecycle: DRAFT → READY → ACTIVE → COMPLETED (or BLOCKED / ABANDONED) -->

## Overview
Close the largest measured gap between our plays-derived box scores and GameChanger's
official scorebook. The plays parser silently drops every pitch that carries a trailing
type/velocity annotation (e.g. `"Strike 1 looking (75 MPH Curveball)"`), collapsing
`pitch_count` / `is_first_pitch_strike` to zero for any team whose scorekeeper charts pitch
type — which is exactly what produced the impossible FPS 3.4% / P-PA 0.2 on a real Legion
report. This epic recovers those pitches (and, while the parser is open, captures the pitch
type and velocity into new columns), makes the report's pitch-detail rate stats honest by
gating them on charted plate appearances, and fixes a separate self-game data-quality bug
that corrupts team rollups for 23 games. It is a deliberate step along the north star,
"Always Get Closer to Byte-Identical Play Ingestion" (`docs/VISION.md`).

## Background & Context
A coach flagged physically-impossible pitching stats on the Empire Netting & Fence Sr. Legion
report. A full discovery effort (api-scout, data-engineer, software-engineer) traced it three
ways — live API, DB, code — and measured the season-wide gap. Durable findings:

- **Root cause**: `PlaysParser._classify_template` (`src/gamechanger/parsers/plays_parser.py`)
  exact-matches the bare pitch vocabulary. The live API emits a base result plus an OPTIONAL
  trailing parenthetical carrying speed and/or type. Any annotated pitch fails the exact match,
  is classified `event_type='other'`, and never increments `plays.pitch_count` /
  `is_first_pitch_strike`. Long-standing since E-195 (the parser was built against an API spec
  that normalized the suffix away) — not a recent regression.
- **The gap is COVERAGE, not fidelity.** DE's baseline (`.project/research/E-245-plays-boxscore-reconciliation-baseline.md`)
  shows outcome-derived stats already reconcile 98.4–100% once no-plays units are excluded —
  the parser is faithful where it has data. The season gap decomposes into three independent
  axes; this epic addresses the two that are clean bugs.
- **Two scary hypotheses came back CLEAN** (api-scout): the reconcile engine's outcome-vocab
  sets cover all 21 live `name_template` outcomes (no silent SO/AB/H drift), and incomplete-PA
  BF undercount is zero. No work needed on either; a forward-note is recorded in Technical Notes.
- **Grammar is fully ground-truthed**: see `docs/api/endpoints/get-game-stream-processing-event_id-plays.md`
  ("Pitch event grammar"). Velocity (MPH) is real and capturable; an earlier "structurally
  absent" claim was refuted by a controlled test team.

Scope was locked by the user (2026-06-29): three functional changes + a migration. Productizing
a reconciliation scoreboard and deciding the perspective/coverage policy (axis 2) are explicitly
deferred. Using the newly-stored pitch type/velocity in reports is captured as IDEA-086.

## Goals
- Recover the ~5,841 dropped pitch events across 29 affected games so `pitch_count` /
  `is_first_pitch_strike` reflect reality, and make all future reports parse annotated pitches.
- Capture per-pitch `pitch_type` and `pitch_speed_mph` into new `play_events` columns whenever
  present (storage only; analysis is IDEA-086).
- Make the report's pitch-detail rate stats (FPS%, P-PA, P-BF) honest by computing them over
  charted plate appearances only, and make the "N of M games" coverage badge mean pitch-charted
  games.
- Eliminate the 23 self-games (`home_team_id == away_team_id`) so team-level rollups and pitcher
  attribution stop being corrupted.

## Non-Goals
- **Reconciliation scoreboard productization** — deferred. DE's manual repro query
  (`scratchpad/recon.sql`) remains the check for now. The north-star enforcement gate lands when
  the scoreboard exists (a future epic).
- **Perspective / coverage policy (axis 2)** — a measurement-policy decision, not a bug. Out of
  scope.
- **Using pitch type / velocity in reports or analysis** — captured as IDEA-086. This epic STORES
  the data; it does not surface or analyze it.
- **Outcome-vocab and incomplete-PA work** — both audited clean this session; no changes. See the
  forward-note in Technical Notes (TN-8).
- No structured-events (`/game-streams/{id}/events`) rearchitecture — api-scout confirmed it is
  more work than fixing the plays parser; held as last resort.
- **Cause-4 multi-pitcher-boundary attribution drift** (the +23 BF game `e283438c`, which is
  `home != away` — NOT a self-game) is a distinct axis. Out of scope here; flag to PM as an idea
  candidate.

## Success Criteria
The headline is the **pitch-detail fidelity fix**: FPS% and P/PA now reflect actual pitch-charted
data rather than a denominator inflated by un-charted PAs (and, on affected teams, by pitches the
parser silently dropped). Tier-1 outcome stats are boxscore-sourced and already reconcile 98.4–100%
(baseline) — they were never broken, so "no Tier-1 regression" is a guardrail here, not the
headline (TN-7). Figures are anchored on DE's measured baseline
(`.project/research/E-245-plays-boxscore-reconciliation-baseline.md`). Live-DB recovery figures are
OPERATOR-verified after the epic merges and the reload runs (the reload cannot execute inside an
epic worktree — see TN-9); fixture/unit verification happens during dispatch.

- [ ] The plays parser classifies annotated pitches (type and/or velocity) as `event_type='pitch'`
      with the correct `pitch_result`, verified against fixtures covering all three annotation
      forms plus the bare form (TN-2).
- [ ] After the one-time reload, `pitch_count > 0` is present on the previously-dropped events;
      team-133 (Empire Netting & Fence Sr. Legion) team FPS% recovers from **3.4% to ~64%** and
      P-PA rises from **~0.2 to ~2.7** (the measured charted-PA values in the baseline;
      operator-verified). The general league range (~38–42% FPS, ~3.5–4.0 P/PA) is context only —
      verify against the measured team-133 numbers.
- [ ] `play_events.pitch_type` and `play_events.pitch_speed_mph` are populated for annotated
      pitches and NULL for bare pitches.
- [ ] FPS% / P-PA / P-BF are computed over charted PAs only (`pitch_count > 0`); QAB% keeps its
      all-PA denominator (TN-5). The coverage badge and inline per-stat counts reflect pitch-charted
      games per TN-5's copy, never suppressing a zero-charted team.
- [ ] No Tier-1 outcome stat regresses (guardrail): per-stat exact% for BF, SO, BB, H, HBP, IP
      (pitching) and PA, AB, H, BB, SO, HBP (batting) does not drop relative to the baseline (TN-7).
      `#P`/`pitch_count` is excluded — it is the recovered headline metric, expected to IMPROVE (TN-7).
- [ ] Self-games drop from 23 to 0 (axis-3 counter); no completed game has
      `home_team_id == away_team_id`, the 23 opponents resolve to distinct (by-name or sentinel)
      teams, and the collapsed `batting_team_id` rollups for those games are corrected
      (operator-verified after the re-ingest of the 5 affected teams — see TN-6).
- [ ] Full test suite green at closure.

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-245-01 | Add `pitch_type` + `pitch_speed_mph` columns to `play_events` (migration 007) | DONE | None | data-engineer |
| E-245-02 | Recover annotated pitches, capture type/velocity, reload affected games | DONE | E-245-01 | software-engineer |
| E-245-03 | Data-bearing pitch-detail denominator + honest pitch-charted coverage badge | DONE | None | software-engineer |
| E-245-04 | Fix self-game (`home == away`) opponent-resolution corruption | DONE | E-245-02 (reuses its reload to re-derive `batting_team_id`) | data-engineer |
| E-245-05 | Update `key-metrics.md` FPS% definition for the data-bearing denominator | DONE | E-245-03 | claude-architect |

## Dispatch Team
- data-engineer
- software-engineer
- claude-architect

## Technical Notes

**TN-1 — Grounding artifacts (load as deferred context).**
- Measured baseline + success-metric design: `.project/research/E-245-plays-boxscore-reconciliation-baseline.md`
- Ground-truthed pitch grammar, parsing rules, vocabulary: `docs/api/endpoints/get-game-stream-processing-event_id-plays.md` (sections "Pitch event grammar" and "Parsing rules")
- DE companion finding on the parser gap: `.claude/agent-memory/data-engineer/pitch_type_annotation_parser_gap.md`
- Perspective invariant for any stat write: `.claude/rules/perspective-provenance.md`

**TN-2 — Pitch grammar & parsing contract.** A pitch template is a base result plus an optional
single trailing parenthetical: `<base> [ " (" <annotation> ")" ]`, where the annotation is
`<speed> " MPH " <type>` | `<speed> " MPH"` | `<type>`. The authoritative grammar, the closed
6-value type vocabulary (`Fastball|Curveball|Slider|Changeup|Cutter|Unclear`, where `Unclear`
means "type unknown"), the strip-then-match rule for recovering `pitch_count`, and the inner
sub-parse for speed/type are all documented in the endpoint doc cited in TN-1. The parser must
apply the strip-and-match per event (bare and annotated pitches interleave within one game) and
must gate the strip so it only fires when the post-strip base is a known pitch template — never
strip parentheticals off mid-AB / non-pitch templates. `pitch_result` semantics are preserved
(the existing six values). The implementer applies the documented grammar; the regexes in the
doc are the contract, not a code mandate.

**TN-3 — Reload requirement (already-loaded games will NOT self-heal).** Plays use whole-game
idempotency (`SELECT 1 FROM plays WHERE game_id = ? AND perspective_team_id = ?`), so a plain
report regen skips already-loaded games and the parser fix alone does not repair history. The
affected games' existing rows must be re-derived. The full annotated `at_plate_details` text is
retained verbatim in `play_events.raw_template`, so recovery does NOT require an API re-fetch — a
re-parse of stored `raw_template` can reclassify the dropped pitches and populate the new
type/speed columns. The parent `plays.pitch_count` and `is_first_pitch_strike` are derived from
the events and must be recomputed for affected plays. Boxscore-derived `player_game_*` and season
aggregates are NOT touched by this bug and must not be rewritten. **The reload mechanism is MANDATED
(not an implementer's choice): an IN-PLACE re-derivation whose SOURCE is `play_events.raw_template`,
which NEVER invokes `parse_game`.** A clear-and-re-ingest path is explicitly forbidden here: deleting
`play_events` would destroy `raw_template` (the ONLY DB copy of the annotated pitch text — there is no
raw JSON on disk under in-memory crawl-to-load), forcing an API re-fetch and breaking the offline
property (AC-4); and `parse_game` cannot run on reload anyway because it needs `final_details`, which
is not persisted (TN-3a). So the reload re-reads each affected game's stored `play_events` rows,
reclassifies the dropped pitches, populates the new type/speed columns, and recomputes the parent
flags in place. The one-time historical pass follows the existing `bb data backfill-appearance-order`
precedent (an operator-runnable maintenance command). E-245-04 reuses this same reusable per-game
entry point for the POST-correction plays re-derivation of the self-games (TN-6), so the reload MUST
expose a per-game core that also re-derives `batting_team_id` from the current games-row home/away
(TN-3b). The forward parser fix makes new reports correct automatically.

**TN-3b — Reload re-derives `batting_team_id` from the fresh games row (SE+DE; required for E-245-04
reuse).** `batting_team_id` is a parse-time `plays` column derived from `half` + the game's home/away
team ids — it is NOT a pitch flag. The reusable per-game reload entry point MUST re-read home/away
FRESH from the (current) `games` row and re-run the `half`→team derivation when it rebuilds the
plays. For E-245-02's own affected games this is a no-op (their home/away is already correct), but it
is exactly the mechanism by which E-245-04 fixes the self-games: after E-245-04 corrects a game's
home/away to `home != away`, calling this entry point re-derives the correct `batting_team_id` per
half. Without this, E-245-04 cannot reuse the reload.

**TN-3a — Reload-path `is_qab` OR-merge (REQUIRED to keep the reload offline; SE).** `final_details`
(the outcome narration) is NOT persisted anywhere — it exists only transiently in the parser, no DB
column, the loader never writes it. It is needed for exactly one thing in a from-scratch parent-flag
recompute: QAB condition 4 (hard-hit ball — `_check_hhb` scans `final_details`). So a naive "re-run
`_compute_qab` from DB rows" on reload would silently drop HHB-only QABs — a real `is_qab`
regression. The reload MUST therefore recompute `is_qab` as an exclusion-guarded OR-MERGE, never from scratch:
it FIRST returns `is_qab = 0` for any outcome in the forward path's `_QAB_EXCLUDED_OUTCOMES`
(Intentional Walk / Dropped 3rd Strike / Catcher's Interference), and ONLY otherwise computes
`new_is_qab = stored_is_qab OR check_2s_plus_3(recovered_pitch_events) OR (recovered_pitch_count >= 6)`.
The exclusion-first guard is mandatory: without it, an excluded outcome whose recovered count reaches a
pitch-count condition (e.g. a Dropped-3rd-Strike PA with 6+ recovered pitches) would flip from the
correct `is_qab = 0` to `1`, corrupting even pitch-count-unaffected games — the forward `_compute_qab`
excludes those outcomes BEFORE any pitch-count condition, and the reload must match. With the guard in
place this is provably sound and monotonic: the pitch-drop bug only ever produces FALSE-NEGATIVE QABs,
and only on the two pitch-count-dependent conditions (2S+3, 6+ pitches); conditions 3–7 (XBH / HHB /
walk / sac) do not depend on `pitch_count` and are already baked into stored `is_qab`, and the bug
never ADDS pitches (no false positive to discard). Both the exclusion check (reads only `outcome`) and
the OR-merge never read `final_details`, so the offline property holds. HHB is NOT in the excluded set,
so HHB-only QABs still survive. A from-scratch `_compute_qab` is explicitly NOT used on the reload path (it
would require `final_details` and thus a re-fetch). This applies to the RELOAD path only — the
forward parser path has `final_details` in memory and computes QAB normally. Likewise,
`play_events.is_first_pitch` is currently WRONG on affected games (the annotated true-first pitch was
logged as 'other', so the flag landed on a later bare pitch); the reload MUST RE-DERIVE it, not trust
the stored value. Both are fully reconstructible offline.

**TN-4 — New columns.** `play_events` gains two NULLABLE columns: `pitch_type TEXT` (one of the
6-value vocabulary, or NULL when absent/unknown) and `pitch_speed_mph INTEGER` (or NULL). Both are
captured per-event whenever present, independently — a speed-only pitch sets `pitch_speed_mph` and
leaves `pitch_type` NULL; a type-only pitch does the reverse; a bare pitch leaves both NULL. No
CHECK constraint is required on `pitch_type` (the vocabulary may grow if GC adds a type). Migration
is an additive `ALTER TABLE ADD COLUMN` (see `.claude/rules/migrations.md`; next number is 007 —
confirm via `ls migrations/*.sql`).

**TN-5 — Denominator & badge policy.** The pitch-detail rate stats in `src/reports/generator.py`
(`_query_plays_pitching_stats`, `_query_plays_batting_stats`, `_query_plays_team_stats`) currently
compute FPS% / P-PA / P-BF as `SUM(...) / COUNT(*)` over ALL plays, so un-charted PAs dilute the
rate. Restrict these denominators to charted PAs (`pitch_count > 0`). The `plays_game_count` /
"N of M games" coverage badge must likewise count pitch-CHARTED games (games with at least one
charted PA from this team's perspective), consistent with the data-bearing-coverage principle in
`.claude/rules/data-model.md`.

**Relation to `key-metrics.md` (M2 — context-layer reconciliation, see TN-10).** `key-metrics.md`
currently defines FPS% as "FPS / BF with NO query-time exclusions — ALL PAs (HBP, IBB, and every
other outcome) in the denominator," and claims this "matches GameChanger." This epic's gate does NOT
contradict that intent: it is an UN-CHARTED-PA exclusion (`pitch_count == 0`), NOT an OUTCOME
exclusion. Outcome-based exclusions (HBP/IBB/etc.) remain absent — every charted PA outcome still
counts. The "matches GameChanger" claim HOLDS: GC's own FPS% is computed over pitch-charted PAs (the
reason team-133's true FPS% is ~64%, not a denominator that includes un-charted PAs). The
`key-metrics.md` wording must be updated by claude-architect to add the charted-PA qualifier (TN-10).

**QAB Denominator Policy (RESOLVED, baseball-coach).** QAB% **KEEPS its all-PA denominator — do
NOT gate it on `pitch_count > 0`.** Every plate appearance is a QAB *opportunity* regardless of
whether pitches were charted, so gating the denominator would shrink the sample for no benefit. The
`pitch_count > 0` gate therefore applies to **FPS% / P-PA / P-BF ONLY**. **Caveat (S4, ties to
TN-3a):** the all-PA DENOMINATOR is correct, but `is_qab` is NOT fully outcome-derived — 2 of its 6
conditions (2S+3, 6+ pitches) ARE pitch-count-dependent. Those affect the QAB NUMERATOR (the
`is_qab` flag), which the reload recovers via the TN-3a OR-merge — they do not change the all-PA
denominator decision. Forward caveat: if a future GameChanger QAB variant adds a NEW "6+ pitch AB"
*denominator* component, THAT would need charted-PA gating — current GC QAB does not, so all-PA is
correct now.

**Two distinct coverage counts.** Because FPS%/P-PA are charted-gated but QAB% is not, the report
surfaces TWO honest counts: (a) **pitch-charted games** (games with ≥1 charted PA, perspective-
scoped) — drives FPS%/P-PA and the badge; (b) **games-with-plays** (any plays rows) — drives QAB%.
Label QAB% with its own count; do not conflate it with the pitch-charted coverage.

**Coach-facing copy (RESOLVED, baseball-coach).**
- Coverage badge: `"Pitch-charted: N of M games"` (N = pitch-charted games, M = games to date).
- Inline per pitch-detail stat (FPS%/P-PA/P-BF): the charted-game count rides the same line, e.g.
  `"FPS% 64% (4 charted games)"`. Sparse cases (1–3 games) use the SAME format — the count itself
  is the warning (`"(1 charted game)"`).
- Inline QAB% (S2): QAB% rides its OWN games-with-plays count, e.g. `"QAB% 40% (12 games)"` — the
  wording difference ("games" vs "charted games") carries the distinction; no asterisk, no footnote.
- Zero pitch-charted games — TWO cases (M3):
  - (a) **zero charted AND zero games-with-plays** (no plays at all): render the section with the
    full note `"No pitch-by-pitch data available for this team"`.
  - (b) **zero charted BUT some games-with-plays** (plays exist, none pitch-charted): QAB% still
    renders with its games-with-plays count; FPS%/P-PA/P-BF show the NARROWED note
    `"Pitch-charting not available — FPS% and P/PA cannot be computed"`. Do NOT claim "no data" — the
    team has plays data, just no pitch charting.
  - NEVER suppress in either case (per `.claude/rules/display-philosophy.md` "never suppress, always
    contextualize"). A 2-of-15 team's FPS% from those 2 games is still useful; the count tells the
    coach how much weight to give it.

Story E-245-03 references this section.

**TN-6 — Self-game axis (DE-owned, root cause CONFIRMED).** 23 games (3.9%) have
`home_team_id == away_team_id`. Confirmed mechanism (DE, empirical): the scouting path hardcodes
`opponent_id=""` (`src/gamechanger/loaders/scouting_loader.py:393/426`); these 23 opponents never
used GC scorekeeping, so the boxscore carries only the scouted team's key → `opp_key=None` →
`opp_team_id_result=None` → `game_loader.py:580-584` sets `opp_team_id = own_team_id` (its
"placeholder, not used" comment is WRONG — it IS used) → `_resolve_home_away` returns `(own, own)`.
Verified on self-game `ca04a524` (only team-133 players; 0 of 23 self-games have a second batting
team — not a name collision). Downstream, the plays parser then derives `batting_team_id` from
`half`, so both halves collapse onto one team id → team-rollup outliers + pitcher over-attribution
(DE measured self-game over-attribution up to **+32 BF**, e.g. real self-game `1415cb04`).

**Fix (two parts, `game_loader.py`):** (1) when the boxscore lacks the opponent stat block, resolve
the opponent team by NAME (`opponent_team.name` is available but currently only reached when
`opp_identifier` is truthy) so a distinct `opp_team_id` is produced (the opponent simply has no
per-player stat rows — truthful, not fabricated); (2) a home≠away INVARIANT GUARD in
`_resolve_home_away`/`_upsert_game` that NEVER emits `home_team_id == away_team_id` — falling back to
an "Unknown Opponent" sentinel stub rather than `own_team_id` when truly unresolvable. Delete the
misleading comment.

**Existing-data correction — boxscore re-ingest (API re-fetch) + IN-PLACE plays fix (NO clear).**
The 23 games' opponent identity is UNRECOVERABLE from the DB (both home/away name the scouted team;
the opponent name was discarded at ingest), so correcting the `games` row requires re-fetching the
boxscore for the 5 affected teams and re-running the FIXED loader (which now resolves the opponent by
name) — an API re-fetch, explicitly UNLIKE Story 02's offline reparse. **But `plays`/`play_events`
are NOT cleared and NOT re-fetched.** The `batting_team_id` corruption is fixed IN PLACE: once the
`games` row is corrected to `home != away`, E-245-02's in-place per-game reload entry point re-reads
the games row and re-derives `batting_team_id` per `half` (TN-3b). Clearing `play_events` is
forbidden here for the same reason as TN-3/M1 — it would destroy `raw_template` (the only copy of the
pitch text), and 04 does not re-fetch plays. Sequence: fixed loader merges → re-fetch + re-run the
boxscore game-load for the 23 games (corrects the `games` row home/away + creates the opponent by
name) → call E-245-02's in-place reload to re-derive `batting_team_id`. There is NO "clear tool" — 02
owns a concrete IN-PLACE reload entry point, not a clear+reload tool. Per the Cleanup-Detection Mirror
Invariant (`.claude/rules/data-model.md`), the corrective rewrite respects perspective scoping.
**Success gate: the axis-3 self-game counter goes 23 → 0.** (The +23 BF outlier `e283438c` is NOT a
self-game —
home=220, away=100 — it is a distinct cause-4 multi-pitcher-boundary issue, out of scope; see
Non-Goals.)

**TN-7 — Success-metric frame.** Success is "the season reconciles closer than today," not merely
"ACs pass." The HEADLINE is the pitch-detail fidelity fix (baseball-coach): FPS% and P/PA now
reflect actual pitch-charted data instead of an inflated denominator — DE's measurement showed
Tier-1 outcome stats already reconcile 98.4–100% (boxscore-sourced, never broken), so there is no
Tier-1 fix to headline. Frame success with the concrete before/after on the measured team-133
baseline (FPS 3.4% → ~64%, P-PA → ~2.7). QAB% improving is a secondary win, not the headline. The
GUARDRAIL bar (must hold, but is not the story): no Tier-1 outcome stat's exact% regresses against
the baseline, and the two addressed axis counters (dropped-pitch-events, self-games) go to zero.
DE's `scratchpad/recon.sql` is the manual check until a scoreboard is productized. **Guardrail set
(boxscore-sourced OUTCOME stats that must not regress):** pitching BF, SO, BB, H, HBP, IP; batting
PA, AB, H, BB, SO, HBP — kept in sync with the Success Criteria guardrail bullet (S3). **`#P` /
`pitch_count` is NOT in the guardrail set:** it is the recovered headline metric — its exact% is
EXPECTED TO IMPROVE (the parser bug collapsed it toward ~0 on affected teams), not held flat.

**TN-8 — Forward-note (outcome vocab).** The reconcile engine's hardcoded outcome sets were
audited clean against all 21 live `name_template` outcomes this session (no silent drift). No work
needed now. Re-run that audit if GameChanger ever adds a NEW hit string or a NEW PA-not-AB string
(outside `_AB_EXCLUSIONS`).

**TN-9 — Worktree constraint.** Reloads and corrective data passes touch the live DB and CANNOT
run inside an epic worktree (no `.env`/`data/`, no `bb`/docker per `.claude/rules/worktree-isolation.md`);
the E-245-04 self-game correction additionally needs GC credentials for its `games.json` re-fetch
(TN-6). During dispatch, implementers verify parser/loader/query/migration behavior via fixtures and
unit tests; the live-DB recovery figures in Success Criteria are OPERATOR-verified after merge.

**TN-10 — Context-layer impact (M2; handled by story E-245-05, claude-architect).** Story E-245-03
changes the effective FPS%/P-PA/P-BF denominator (charted-PA gate), which makes
`.claude/rules/key-metrics.md`'s current FPS% wording ("FPS / BF with NO query-time exclusions — ALL
PAs") stale. `key-metrics.md` is a context-layer file PM does NOT edit — the wording update (add the
charted-PA qualifier while preserving the "no OUTCOME exclusion" and "matches GameChanger" points per
TN-5) is **story E-245-05**, owned by claude-architect and blocked-by E-245-03 so it documents the
shipped semantics. Landing it as a dispatch story (rather than deferring to the closure context-layer
assessment) keeps the rule from going stale mid-epic. The closure context-layer assessment
(`.claude/rules/context-layer-assessment.md`) still verifies it before archive.

## Open Questions
None. All consultations are resolved and incorporated: SE on parser/reload + the `is_qab` OR-merge
(TN-3, TN-3a), DE on the migration and the empirically-confirmed self-game root cause + re-ingest
mechanism (TN-4, TN-6), baseball-coach on QAB denominator + copy + the success headline (TN-5, TN-7).

## History
- 2026-06-29: Created (DRAFT). Discovery complete (full plays→boxscore reconciliation baseline);
  scope locked by user.
- 2026-06-29: Incorporated SE/DE/baseball-coach consultation. Resolved QAB denominator (keep
  all-PA), coverage-badge + inline copy, success-metric headline (pitch-detail fidelity, not Tier-1
  parity), reload-path `is_qab` OR-merge + `is_first_pitch` re-derivation (TN-3a), and the
  empirically-confirmed self-game root cause (`opponent_id=""` → `opp_team_id = own_team_id` at
  `game_loader.py:580-584`) with its re-ingest (API re-fetch) correction. Scoped OUT the +23 BF
  `e283438c` (cause-4 multi-pitcher-boundary, not a self-game). All open questions closed.
- 2026-06-29: Incorporated internal review iteration 1 (CR + SE/DE/coach holistic). Accepted 11
  findings: mandated in-place reparse-from-`raw_template` (TN-3, no clear-and-re-ingest for the
  offline reload); added reload `batting_team_id` re-derivation (TN-3b, story 02 AC-9, story 04 AC-3);
  split the zero-charted copy into no-plays vs some-plays cases (TN-5, story 03 AC-6/AC-7); QAB%
  display format + rationale caveat (TN-5 S2/S4); reconciled the Tier-1 guardrail set and excluded
  `#P` as the recovered headline (TN-7, Success Criteria); pinned the self-game site and real +32 BF
  magnitude (`1415cb04`); flagged the `key-metrics.md` FPS% wording for claude-architect (TN-10).
  Dismissed the stale half of the CR/SE timing-race finding (story 02 OR-merge ACs were already
  present). Consistency sweep clean; AC numbering verified.
- 2026-06-29: M2 routing resolved (final) — added story E-245-05 (claude-architect, blocked-by
  E-245-03) to reconcile `.claude/rules/key-metrics.md`'s FPS% wording during dispatch. Epic has 5
  stories; Dispatch Team = data-engineer + software-engineer + claude-architect. (TN-10 also remains
  a closure-assessment backstop.)
- 2026-06-29: Incorporated Codex spec-review iteration 1 (3 of 4 findings). P1: resolved the
  02↔04 "clear tool" contradiction — E-245-02 concretely owns a non-optional IN-PLACE per-game reload
  entry point; E-245-04 reuses it to re-derive `batting_team_id` in place after its boxscore re-ingest
  (NO `play_events` clear — clearing would destroy `raw_template`); reconciled TN-6, story 02 Files,
  story 04 Context/AC/Technical Approach. P2-testability: split story 04 AC-3 (fixture, dispatch) from
  AC-5 (live 23→0, operator post-merge). P3: updated story 03 Description prose to match TN-5 (QAB
  numerator caveat + two zero-charted notes). P2-consultation (E-245-05 had no claude-architect input)
  ACCEPTED — CA validation in flight via the main session; to be recorded here + folded into E-245-05
  ACs when relayed. Consistency sweep clean.
- 2026-06-29: claude-architect consulted on E-245-05 (closes Codex P2-consultation). CA APPROVED the
  charted-PA gate as the correct context-layer call (it makes "matches GameChanger" MORE accurate),
  confirmed via grep that ONLY `key-metrics.md`'s FPS% bullet is stale (QAB entry, data-model.md, and
  the api-scout glossary need no edit — single-file scope correct), and proposed the exact replacement
  FPS% wording now folded into E-245-05's Technical Approach (implemented verbatim at dispatch) and
  ACs. All Codex iteration-1 findings now resolved.
- 2026-06-29: Set **READY** (user-approved; path was straight to READY, no Codex iteration 2). Quality
  checklist passed.
- 2026-06-29: Dispatch — E-245-01 DONE (migration 007; AC PASS + reviewer APPROVED). E-245-02 in
  review.
- 2026-06-29: Dispatch review-iteration finding (code-reviewer, E-245-02, MUST FIX). The reload's
  `is_qab` OR-merge as originally specified (`stored_is_qab OR check_2s_plus_3 OR pitch_count >= 6`)
  omitted the forward path's outcome exclusions: an outcome in `_QAB_EXCLUDED_OUTCOMES` (Intentional
  Walk / Dropped 3rd Strike / Catcher's Interference) whose recovered count reaches a pitch-count
  condition would flip from the correct `is_qab = 0` to `1`, corrupting even pitch-count-unaffected
  games. Amended AC-6 (story 02) and TN-3a to mandate an exclusion-FIRST guard (reusing the forward
  path's `_QAB_EXCLUDED_OUTCOMES`, no from-scratch `_compute_qab`, offline property preserved — the
  exclusion check reads only `outcome`). HHB-only-QAB survival is unchanged (HHB is not in the excluded
  set). SE owns the one-line code guard; this is the AC/TN reconciliation. Consistency sweep: the OR-
  merge formula appeared in AC-6 and TN-3a (both updated); the QAB Denominator Policy and story-02
  Technical Approach reference the OR-merge by name only (no formula) and remain accurate.
- 2026-06-29: **Dispatch complete — all 5 stories DONE.** Shipped: (01) migration 007 adds nullable
  `play_events.pitch_type` + `pitch_speed_mph`; (02) the plays parser now classifies annotated pitches
  (type/velocity) instead of dropping them, captures type/speed, and a mandated in-place
  reparse-from-`raw_template` reload (`reload_game_plays`, no clear / no API / no `parse_game`) repairs
  already-loaded games, including the AC-6/TN-3a exclusion-first `is_qab` OR-merge (per-story CR MUST
  FIX — see the prior entry) and `is_first_pitch`/`batting_team_id` re-derivation; (03) FPS%/P-PA/P-BF
  denominators restricted to charted PAs (`pitch_count > 0`) with QAB% kept all-PA, plus the
  "Pitch-charted: N of M games" badge, inline charted-game counts, and the two never-suppress
  zero-charted notes; (04) `game_loader.py` now always resolves a distinct opponent (by name → "Unknown
  Opponent" sentinel) with a home≠away invariant guard, and `bb data fix-self-games` corrects the 23
  existing self-games (boxscore re-ingest + in-place `reload_game_plays` re-derivation, no plays clear);
  (05) `key-metrics.md` FPS% wording reconciled to the charted-PA denominator. Per-story review found:
  E-245-02 QAB OR-merge exclusions (MUST FIX, fixed); E-245-03 golden `_meta` attribution (SHOULD FIX,
  fixed); E-245-04 CLI test coverage (MUST FIX, fixed) + a shared-sentinel/`_find_duplicate_game`
  natural-key collision edge (SHOULD FIX, awareness-only, AC-2-sanctioned → captured as **IDEA-088**,
  not a blocker). E-245-05 was context-layer-only (code-reviewer skipped; PM verified ACs solo).
- 2026-06-29: **Phase 4 ("and review").** 4a CR holistic integration review over the full epic diff:
  clean (0 findings). 4b Codex code review: 2 findings on `bb data fix-self-games`, both ACCEPTED and
  remediated (P1 MUST FIX — shared-connection transaction isolation: the per-team `except` did not
  `rollback()`, so a mid-run partial write could be silently committed by a later team or the final
  rederive; fixed with a one-line `conn.rollback()` in the CLI except, in-scope, no AC/`load_team`
  semantics change. P2 MUST FIX — error-path test now asserts post-failure rollback). Both live within
  the command surface E-245-04 owns, so no AC amendment.
- 2026-06-29: **Documentation assessment (PM, per `.claude/rules/documentation.md`): IMPACT EXISTS —
  docs-writer dispatch required before archive.** Triggers fired: #1 (new feature/commands ship), #4
  (schema change — migration 007), #5 (epic changes how coaches read the report). Affected files +
  required updates: (a) `docs/admin/operations.md` — add the two new operator maintenance commands
  `bb data reload-annotated-pitches` and `bb data fix-self-games` to the `bb data` command catalog
  (alongside the existing reconcile / dedup-players / backfill-appearance-order entries), each with
  dry-run/execute semantics and the one-time-historical-pass framing; (b)
  `docs/coaching/standalone-reports.md` — describe the new "Pitch-charted: N of M games" coverage badge,
  the inline per-stat "(N charted games)" counts, and the two zero-charted notes (no-plays vs
  plays-but-uncharted), refining the existing exec-summary coverage sentence (line ~31); (c)
  `docs/coaching/understanding-stats.md` — sharpen the FPS%/P-PA/P-BF "important note" wording so it
  reflects the charted-PA denominator (the rate is computed over pitch-charted PAs and matches
  GameChanger; "—" still means no pitch data). Migration 007's columns are storage-only / not surfaced
  (future surfacing is IDEA-086), so trigger #4 needs no operator/coach schema-doc change beyond the
  command additions; the schema reference home is `.claude/rules/data-model.md` (context-layer,
  handled below). Not yet dispatched — main session to route docs-writer before archival.
- 2026-06-29: **Context-layer assessment (six-trigger, per `.claude/rules/context-layer-assessment.md`).**
  T1 (new convention/pattern/constraint): **YES** — data-bearing charted-PA denominator gate; the
  `home_team_id != away_team_id` games invariant; the in-place offline reload-from-`raw_template` repair
  pattern (no clear-and-re-ingest for plays). T2 (architectural decision, ongoing): **YES** —
  `reload_game_plays` as the canonical reusable per-game in-place re-derivation entry point; storing
  per-pitch type/velocity. T3 (footgun/failure mode/boundary): **YES** — shared-connection
  partial-commit-on-failure in multi-item CLI loops (must `rollback()` in the per-item `except`);
  already-loaded plays do NOT self-heal (reload required); the self-game root cause (`opponent_id=""` →
  `opp_team_id = own_team_id`). T4 (agent behavior/routing/coordination): **NO**. T5 (domain knowledge
  for future agents): **YES** — FPS%/P-PA/P-BF computed over charted PAs matches GameChanger; QAB
  exclusion-outcome semantics; pitch grammar (already in the endpoint doc). T6 (new CLI command/
  workflow): **YES** — `bb data reload-annotated-pitches` and `bb data fix-self-games` (CLAUDE.md
  Commands section). E-245-05 already pre-handled one context-layer item (`key-metrics.md` FPS% wording,
  per TN-10) as a dispatch story; the remaining firing triggers are codified by claude-architect
  (dispatched in parallel) before archival.

### Review Scorecard

**Planning (spec review):**
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal review iter 1 — CR spec audit + SE/DE/coach holistic (consolidated, deduped) | 12 | 12* | 0* |
| Codex spec review iter 1 | 4 | 4 | 0 |
| **Spec subtotal** | **16** | **16** | **0** |

**Dispatch (per-story CR + Phase 4 reviews):**
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Per-story CR — E-245-01 | 0 | 0 | 0 |
| Per-story CR — E-245-02 (QAB OR-merge exclusions, MUST FIX) | 1 | 1 | 0 |
| Per-story CR — E-245-03 (golden `_meta` attribution, SHOULD FIX) | 1 | 1 | 0 |
| Per-story CR — E-245-04 (CLI test coverage MUST FIX; + 1 SHOULD FIX → IDEA-088) | 2 | 1** | 0 |
| Per-story CR — E-245-05 | — | — | — *(context-layer-only; CR skipped, PM verified solo)* |
| CR integration review (4a, full-epic diff) | 0 | 0 | 0 |
| Codex code review (4b — shared-connection rollback P1 + test-assert P2) | 2 | 2 | 0 |
| **Dispatch subtotal** | **6** | **5** | **0** |

\* The internal-review row's 12 deduped items were 11 straight ACCEPTs (B1, B2, B3, M1, M2, M3,
S1–S5) plus **X1**, a CR-vs-SE read-timing split: the "Context prose" half was ACCEPTED and fixed,
while the stale "is_qab OR-merge / is_first_pitch ACs are missing" half was DISMISSED as a false
positive (those ACs were already present — a message-crossing timing artifact, not a substantive
finding). Counted as accepted; **no substantive finding was dismissed** in either pass.

\*\* E-245-04's second finding (the shared "Unknown Opponent" sentinel + `_find_duplicate_game`
natural-key collision edge) was a code-reviewer awareness-only SHOULD FIX, NOT a within-AC defect
(AC-2 sanctions the shared stub) — DEFERRED to **IDEA-088** rather than dismissed; the real 23
self-games all resolve by name, so the edge is unreached today. Across all passes, **no substantive
finding was dismissed** (16 spec + 6 dispatch findings; 21 accepted, 1 deferred to an idea, 0
dismissed).
