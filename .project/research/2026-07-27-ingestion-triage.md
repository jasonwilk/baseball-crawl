# Ingestion-bugs triage — cross-reference and sequencing (2026-07-27)

Provenance: produced by a Fable fork inheriting the navigator session's full context
(the operator-staged ingestion-bugs handoff, the four-agent live-vs-dev report audit,
the E-275/E-277 state). Written to disk 2026-07-27 after PM discovery for E-278 found
it cited but not durable — the load-bearing cross-findings below were independently
re-derived and confirmed by PM before this file existed; treat the two accounts as
mutually corroborating. The handoff itself (INGESTION-BUGS-HANDOFF.md, repo root) is
untracked and gitignored by design — this file cites it by section, never by
identifier.

## 1. Triage table (handoff items)

| Item | Defect | Severity | Live vs latent | Ordering constraints (handoff's own) |
|---|---|---|---|---|
| §2 | Boxscore opponent envelope discarded when both keys are slugs (shape-based own/opp inference) | High — 29/228 games missing a full team side, ~11 unknown players each, silent (errors=0, stage completed) | Live data gap, but no wrong number — absence, not corruption. §2.6 misattribution risk is latent-only (29/29 verified not occurring) | Fix before its backfill; backfill after §5 or exclude the 07-25 duplicate's degraded row |
| §3 | Game-ending run dropped when final play hits any of THREE skip paths | Moderate | Latent — 6 games short by exactly 1 run in plays-derived score; zero production consumers today; binds the north star | Decide persistence before planning its backfill (plain regeneration cannot touch the 6 — whole-game skip) |
| §4 | Score-only games (forfeits, quick-scored) indistinguishable from missing data across 8 render surfaces | Low-moderate, presentation only | Live display ambiguity, 1 game today | After §2 backfill (signatures overlap until then); label "score-only", never "forfeit" |
| §5 | Same-perspective duplicate game (GC double-lists upstream; byte-equality start-time tiebreaker; merge tool refuses shared-perspective pairs) | High — the only live wrong number in the handoff: one game double-counted in season aggregates | Live | FIRST — the §2 backfill would fully populate the duplicate and double-count the second team too |
| §6 | Plays team_players block fetched and never read; players stubbed "Unknown" | Moderate | Live (names missing), heals without re-ingest | Independent; parallelizable; mind the §6.4 asymmetric-key trap |

## 2. Cross-reference against the 2026-07-27 live-vs-dev audit

**(a) §5.1's detection key is blind to the date-split twin class — confirmed, and it
is a finding about the handoff itself.** The key groups on game_date + unordered team
pair. The audit's Jun-23 twin stores its two perspectives under different calendar
dates, so it can never land in one group. The handoff's "8 groups, 1 true duplicate"
is therefore a LOWER BOUND: at least one additional true duplicate (cross-perspective
class) exists in the dev DB that §5.1 structurally cannot see. The two dedup gaps are
complementary, not competing: §5's fix is a start-time tolerance in the
same-perspective load branch; the audit's gap is the natural-key (date+pair) collapse
across perspectives. Both need a time-window-based key and belong in one
dedup-hardening story set. Soft flag, not asserted: §5.2 lists the 07-21 pair with
116 plays on one row as a genuine doubleheader — 116 is far above the 47-77 per-game
norm the audit measured, and the confirmed double-load sat at 142; worth one query,
since the handoff's doubleheader adjudication did not check play-count anomalies.
[PM discovery for E-278 independently re-derived both findings from the primaries.]

**(b) §6/§2.5 and IDEA-196 are the same mechanism family, two ends.** Both run
through ensure_player_row's length-preference upsert: §2/§6 are the supply side
(Unknown stubs created by the plays loader, named only if the boxscore path succeeds
— 13/13 unknown pitchers in sampled games resolvable from the discarded team_players
block), IDEA-196 is the persistence side (an Unknown stub reachable via team_rosters
survives reclamation; equal-length misspellings are permanently sticky). Fixing §2+§6
dries up new stubs and auto-heals names ("Unknown" = length 0); IDEA-196's
sticky-misspelling remains a distinct upsert-policy decision the handoff does not
cover. The handoff correctly firewalls the 2,037 pre-existing orphan stubs to the
separate orphaned-reference-data handoff — do not merge those in.

**(c) Against the audit ideas (217-220): zero overlap, strong complements, one
connective insight.**
- Record-query perspective clause (IDEA-217): absent from the handoff — it even cites
  generator.py:396-422 in §4.2 without noticing the defect. Complementary
  defense-in-depth: the clause makes phantom rows invisible to the header; the
  handoff's fixes stop phantom rows existing. Both wanted.
- Mis-attribution phantom (IDEA-219): a defect class the handoff does not have. Its
  §5 root cause is upstream double-listing; this one is our own resolution logic.
  Complementary.
- Double-loaded plays (IDEA-220): not in the handoff — and the handoff explains the
  mechanism without noticing: the whole-game idempotency skip it quotes
  (plays_loader.py:143-152) keys on (game_id, perspective_team_id), so one real game
  crawled from two perspectives loads its plays twice BY DESIGN of that guard. These
  belong in the same dedup/identity epic.
- Display defects (IDEA-221): pure render-path bugs, no ingestion overlap; keep
  separate and small.

**(d) Contradictions: none material.** The handoff's "one confirmed duplicate" is
true only under its blind key (see a) — an undercount, not an error. Its §8 integrity
checks test different predicates than the audit's findings; no conflict.

## 3. Staleness check — the handoff's pin has NOT rotted

Spot-verified four load-bearing citations against main @ 9f8ff39: the shape-based key
split (game_loader.py:862-867, byte-matches the handoff's quote), the start-time
byte-equality tiebreaker + unreachable score fallback (~:1367-1372, drifted <=4
lines), the per-perspective whole-game skip (plays_loader.py:143-152, exact), all
three parser skip paths (plays_parser.py:267/290/301, exact). E-277 touched
reconcile_at_load.py/lifecycle.py only, so the handoff's game_loader/plays_* anchors
survived. Line citations usable as-is with ±5-line tolerance. [PM discovery
re-verified six anchors independently on 2026-07-27; all resolved exactly.]

## 4. Recommended sequencing (as of 2026-07-27; operator has since deferred the
prod backup and IDEA-208 to next season)

1. Prod backup (standing item) — precondition for any prod-side repair. [DEFERRED by
   operator 2026-07-27: end of season, DB resettable.]
2. IDEA-208 pitch-curve fix as its own small epic. [DEFERRED by operator to next
   season: not currently reporting to young arms.]
3. **Epic A — game identity & phantom decisions (MERGE)**: handoff §5
   (same-perspective tolerance + same-perspective merge support) + the UTC/date-split
   dedup-key gap (IDEA-218) + mis-attribution hardening (IDEA-219) + double-load
   resolution (IDEA-220) + the record-query perspective clause (IDEA-217) as story 1.
   Data repairs inside: the 07-25 dup, the Jun-23 twin, the Jun-27 phantom, the
   standing 6-Freshman-games merge, one prod-side query (which phantom does prod
   carry — merge vs delete). Five faces of one defect — "one real game, more than one
   row"; splitting them across epics builds second-path drift. [Became E-278.]
   > ⚠️ **ANNOTATION 2026-07-28 (E-278 closure). This item is EVIDENCE of what was
   > recommended before two later rulings, and is deliberately NOT rewritten. Two of its
   > clauses were superseded — do not act on them:**
   > - **"the record-query perspective clause (IDEA-217) as story 1" — DOMAIN-REJECTED.**
   >   baseball-coach ruled (E-278 TN-7, binding) that the record reflects games PLAYED,
   >   not games we have DATA for, and that the stat-row `EXISTS` gate must NOT be added to
   >   `_query_record`. Measured basis: 20 genuine completed-and-scored games across 12 of
   >   28 teams carry no stat rows from their own perspective and would have been silently
   >   deleted from those coaches' records. E-278-01 shipped the tie component instead.
   > - **"Data repairs inside: …" — VOID under the operator's ruling** (2026-07-27): *"We
   >   can reset all prod data. We don't have to repair anything historically. We only need
   >   to ensure we are accurate moving forward."* E-278 shipped forward prevention only and
   >   repaired nothing. Two entries on that list also dissolved on their own evidence: the
   >   **standing 6-Freshman-games merge is a FALSE POSITIVE** (genuine doubleheaders,
   >   identical perspectives, exactly 7200-second gaps, materially different scores —
   >   merging them would have been the destructive mistake), and the **prod-side phantom
   >   question was answered** (a B-class date-split twin with DISJOINT perspectives, which
   >   the existing merge primitive accepts once detection finds it).
   >
   > **What held:** the MERGE judgment itself. Five faces of one defect, one epic, no
   > second-path drift — E-278 delivered four stories against one `game_loader` seam.
4. **Epic B — envelope & identity fidelity (MERGE)**: §2 identity-based key
   classification (+ §2.6 ordering pin, §2.8 fixture decision) → §2 backfill via
   regeneration (after Epic A per §5.5) → §6 team_players flat lookup → §3
   parser-level final-score metadata with its persistence decision made in-epic → §4
   score-only labeling last.
5. Display-defects idea (IDEA-221) — ride late in Epic B or stay parked.
6. E-274 triage with coach and the E-275 promotion decision — discretionary,
   refine-first calls, neither blocks the above.

Out of scope: §8.1's decisions/save-rule gaps are vision-signal material, already
captured — no action.
