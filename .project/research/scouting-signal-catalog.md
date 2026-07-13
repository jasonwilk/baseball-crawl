# Scouting Signal Catalog

- **Status**: DRAFT (claude-architect structure + baseball-coach content, 2026-07-13). Discovery input for the **E-263** epic (extend reports with Deep Scout + catching-stats section). NOT committed scope until the epic selects entries.
- **Purpose**: The durable, growable inventory of opponent-intelligence SIGNALS computable from data already in the dev DB (`plays`, `play_events.raw_template`, `spray_charts`, `player_game_batting`/`pitching`, `games`) — no new crawling. Replaces the reactive "operator eyeballs it in the data" loop with a standing reference.
- **Ownership**: content columns (Name, Detects, Floor + grey, Exploit/action, Ethics tier) = **baseball-coach**; structure columns (ID, Category, Data source, Computation, Matchup dependency, Depends on, Fact-sheet key, Validation status, Provenance) = **claude-architect**.
- **Provenance / rationale**: `deep-scout-design-2026-07-12.md` is the design-session RECORD (why these signals matter, live-validation logs §8x). This catalog is the STRUCTURED successor to that doc's §4 idea inventory — it is the lookup surface; the design doc stays the narrative/citation surface.
- **Feeds**: the Deep Scout fact-sheet spec (design doc §6). Each entry's `Fact-sheet key` is the bridge — the epic builds catalog entries, not a re-derived list.

---

## How to use this file

- **Add a signal** when it has been computed against real data at least once. Copy the Entry Template, assign the next `SIG-NNN`, and add an Index row.
- **This is reference DATA, not a behavioral rule.** It deliberately does NOT live in `.claude/rules/` or `.claude/skills/` — it drives no agent behavior on its own; it is the spec input the epic consumes. (The Discovery Pass METHOD below is likewise documented, not codified — see that section.)

## Global doctrine (applies to every entry; not repeated per-signal)

- Rate stats need **20 PA** (batting) / **15 IP** (pitching); directional/alignment needs **15 BIP**; steal-light greys below **5 attempts**.
- Genuinely sparse events (backpicks, bunt-defense chances, GDP opportunities) show **raw counts only, never a rate**, at any n.
- Floors/grey states are enforced UPSTREAM in the fact sheet (`status: ok|thin|no_data`), never by prose hedging.
- Charted-only signals (pitch-level: FPS%, two-strike chase) always **badge the real denominator** (games charted vs total).
- **Ethics default**: coach-facing = full names/full data; player-safe = team-tendency/number only, never a named opposing kid next to a weakness. Per-entry Ethics tier notes only the deltas from this default.

## Entry field schema

| Field | Owner | Meaning |
|---|---|---|
| **ID** | CA | Stable `SIG-NNN`; never reused. |
| **Name** | coach | Human-readable signal name. |
| **Category** | CA | A–J bucket from design-doc §4 (navigable + mapped to the brainstorm). |
| **Detects** | coach | The real-world tendency/fact surfaced. |
| **Data source** | CA | Exact table/column or `raw_template` parse form — the buildability proof. |
| **Computation** | CA | One-line metric definition. |
| **Floor + grey** | coach | Entry-specific floor delta beyond the global doctrine. |
| **Exploit / action** | coach | The coaching directive. |
| **Matchup dependency** | CA | `pure-opponent` \| `pairing` (needs `--vs`/`--date`, §5). |
| **Depends on** | CA | Other `SIG-NNN` this must be JOINED to (cross-signal dependency). |
| **Ethics tier** | coach | Delta from the global ethics default. |
| **Fact-sheet key** | CA | The `{value, n, status}` key in the §6 contract. All PROPOSED except `probable_starter`. |
| **Validation status** | CA | `validated-live` (cite §8x game) \| `computed` (run once, outcome not graded) \| `hypothesis` \| `blocked`. |
| **Provenance** | CA | Design-doc section + date. |

### Entry Template

```
### SIG-NNN — <name>
- **Category**: <A–J> | **Matchup**: pure-opponent|pairing | **Depends on**: SIG-NNN|none | **Validation**: … | **Fact-sheet key**: `<key>`
- **Detects**: <coach>
- **Data source**: <table.column / raw_template form>
- **Computation**: <one-line metric>
- **Floor + grey**: <coach>
- **Exploit / action**: <coach>
- **Ethics tier**: <coach>
- **Provenance**: design-doc §N, YYYY-MM-DD
```

---

## Index

| ID | Name | Cat | Matchup | Depends on | Validation |
|---|---|---|---|---|---|
| SIG-001 | NSAA eligibility + probable-starter rank | A | pairing (date) | — | validated-live |
| SIG-002 | Battery-control card (CS + backpick + pickoff) | D | pure-opponent | — | validated-live |
| SIG-003 | Steal light / battery run-control (opp SB%, WP+PB) | D | pairing | — | validated-live |
| SIG-004 | Per-arm innings-weighted control (BB/7, SO/7, strike%, H/7) | B | pure-opponent | SIG-001 | validated-live |
| SIG-005 | Loss-forensics blueprint | G | pure-opponent | SIG-001 | validated-live |
| SIG-006 | First-pitch-strike% per pitcher | B | pure-opponent | SIG-001 | computed |
| SIG-007 | Defensive-alignment directive (GB% + side) | C | pure-opponent | — | validated-live |
| SIG-008 | Defensive error-map by position → bunt targets | E | pure-opponent | — | computed |
| SIG-009 | Times-through-order fade | A | pure-opponent | SIG-001 | computed |
| SIG-010 | Running-game concentration (top-2 SB share) | D | pure-opponent | — | validated-live |
| SIG-011 | Leg-hit / speed-inflation ledger | C | pure-opponent | — | validated-live |
| SIG-012 | Slasher overlay | C | pure-opponent | SIG-007, SIG-010, SIG-011 | computed |
| SIG-013 | Lineup-slot reach-base shape | C | pure-opponent | — | computed |
| SIG-014 | GDP-prone hitters | C | pure-opponent | — | hypothesis |
| SIG-015 | Baserunning-aggression cost / TOOTBLAN | D | pure-opponent | — | computed |
| SIG-016 | First-inning wobble per starter | B | pure-opponent | SIG-001 | computed |
| SIG-017 | Bunt-defense report card | E | pure-opponent | — | hypothesis |
| SIG-018 | Rally-starter / leadoff-slot OBP | C | pure-opponent | SIG-013 | computed |
| SIG-019 | Two-strike chase rate (their hitters) | C | pure-opponent | — | hypothesis |
| SIG-020 | Opposing-coach substitution pattern | coach-tendency (§3 SHOULD #7) | pure-opponent | — | hypothesis |
| SIG-021 | Backup-catcher exploit window | D | pure-opponent | SIG-002 | hypothesis |
| SIG-022 | Frozen-hitter (called-K3 share) | C | pure-opponent | — | computed |
| SIG-023 | First-pitch approach per hitter (+P/PA) | C | pure-opponent | — | computed |
| SIG-024 | Chaos-arm ledger (HBP+balk+WP/arm) | B | pure-opponent | — | computed |
| SIG-025 | Defensive-wobble window (errors by inning) | E | pure-opponent | — | computed |
| SIG-026 | Turn-two threat (infield DP conversion) | E | pure-opponent | — | computed |
| SIG-027 | Small-ball index (coach bunt usage) | coach-tendency (§3 SHOULD #7) | pure-opponent | — | computed |
| SIG-028 | Late-game fade / front-runner | F (CONTEXT tier) | pure-opponent | — | computed |

*Fact-sheet keys are PROPOSED (snake_case) except `probable_starter`, which is fixed in design-doc §6. SE/DE confirm final keys during the epic.*
*SIG-022..028 are the accepted Fable-scout discovery batch (2026-07-13). Content cells are first-pass (lead spec); Coach-catalog refines the coaching-value wording.*

---

## Entries

### SIG-001 — NSAA eligibility + probable-starter rank
- **Category**: A | **Matchup**: pairing (game date) | **Depends on**: none | **Validation**: validated-live (§8, 2026-07-12) | **Fact-sheet key**: `probable_starter`
- **Detects**: which opposing arms are legally eligible on our game date under rest rules, and which is most likely to start, ranked.
- **Data source**: `player_game_pitching` (pitch counts + game dates per arm) + NSAA rest-rules engine (already built for our own staff) + `games` for the schedule/date axis.
- **Computation**: deterministic rest-rule eligibility per `player_id`; probable-starter rank = rest × start-history × recent cadence, innings-weighted.
- **Floor + grey**: eligibility = deterministic, zero sample caveat. Rank is a lean below 3 starts of history; equally-rested arms → "committee," never a false-precision single pick.
- **Exploit / action**: condition the WHOLE game plan (approach, bullpen matchup, who's unavailable) on the specific arm expected, not a staff average.
- **Ethics tier**: coach-facing (strategic rest/pitch-count data on a named opponent; no player-safe form needed).
- **Provenance**: design-doc §3 MUST #1, §8 (predicted both workhorses unavailable + rested arm started).

### SIG-002 — Battery-control card (catcher CS + BACKPICKS + pitcher pickoffs)
- **Category**: D | **Matchup**: pure-opponent (our-runners overlay is a pairing extension) | **Depends on**: none | **Validation**: validated-live (§8d, 2026-07-13) | **Fact-sheet key**: `battery_control`
- **Detects**: catcher throwout arm, strong backpicking catchers, holding pitchers, battery leaks.
- **Data source**: `play_events.raw_template` parse forms — `caught stealing {base}, catcher ${C}`; `picked off at {base}, catcher ${C} to {fielder}` (BACKPICK); `picked off at {base}, pitcher ${P}`; `Pickoff attempt at {base}`; `wild pitch`/`passed ball`.
- **Computation**: roll up strictly by `player_id` (NEVER by name — §8d attribution rule); pickoff-attempt/gm + base split, CS%, backpick putouts/catcher (raw count), pitcher pickoffs/arm, WP+PB leak rate. **Dropped-third-strike allowed line** (folded in from the Fable-scout batch, 2026-07-13): `plays.outcome='Dropped 3rd Strike'` by defensive team — ~22% of K3 leave the batter safe, so a leaky catcher gives a free base on strikeouts (kept a battery-card LINE, not a standalone SIG).
- **Floor + grey**: backpicks sparse — flag "STRONG BACKPICK ARM" at 2+ but ALWAYS show raw count; pickoff-attempt frequency needs ≥5 games to read as a trend.
- **Exploit / action**: DUAL-USE, the standout new play call. Defense — vs aggressive-hold/backpick battery, shorten secondary lead, get back hard. Offense — corners loaded, bait the backpick to first, runner at third breaks home (catcher-tendency analog of a balk-steal). Dropped-third-strike line: against a leaky catcher, every strikeout in the dirt with first base open (or 2 outs) is a running play — our batter busts it out of the box on ANY uncaught third strike, and an existing runner stays alert for the extra 90 on the same pitch (ex: Opponent A 8 D3K allowed).
- **Ethics tier**: coach-facing names catcher/pitcher; player-safe form = "their catcher throws behind runners — get back hard, tighten your lead."
- **Provenance**: design-doc §8d (Opponent C P15 backpick parsed + attributed).

### SIG-003 — Steal light / battery run-control
- **Category**: D | **Matchup**: pairing (OUR runners × their battery) | **Depends on**: none | **Validation**: validated-live (§8, 2026-07-12) | **Fact-sheet key**: `steal_light`
- **Detects**: opponent's overall SB success rate and WP+PB rate against a given battery. Distinct from SIG-002 — this is the raw success-rate signal, not the tendency-detection card.
- **Data source**: `player_game_batting` (SB/CS per game, keyed by `player_id`) + `play_events.raw_template` (WP/PB events).
- **Computation**: team SB / (SB+CS) vs the battery; WP+PB per game. Roll up strictly by `player_id`/UUID, NEVER by name (§8d attribution rule) — a name-keyed rollup silently merges distinct players across teams.
- **Floor + grey**: grey below 5 steal attempts; always show raw count alongside rate ("3-for-5 caught," never a bare %).
- **Exploit / action**: sets tonight's running-game aggression level (green/red) for OUR runners; a high WP+PB rate independently flags a battery worth bunt-and-run pressure even without a steal attempt.
- **Ethics tier**: coach-facing ONLY in named form — the sharpest ethics risk in the catalog (screenshot-able targeting of a named 15–16yo catcher's arm). Player-safe form: team tendency only, never name the catcher.
- **Provenance**: design-doc §3 SHOULD #4, §8 (green call → ran 3-for-4).

### SIG-004 — Per-arm innings-weighted control (BB/7, SO/7, strike%, H/7)
- **Category**: B | **Matchup**: pure-opponent (starter selection via SIG-001 is the pairing) | **Depends on**: SIG-001 | **Validation**: validated-live (§8, 2026-07-12) | **Fact-sheet key**: `arm_control`
- **Detects**: a specific pitcher's own command profile, innings-weighted so a staff aggregate isn't dominated by a low-inning wild reliever.
- **Data source**: `player_game_pitching` (BB, SO, IP, H per arm); strike% from `plays` pitch reconstruction (or boxscore TS/#P).
- **Computation**: innings-weighted BB/7, SO/7, H/7, strike% per `player_id`, JOINED to SIG-001's probable starter.
- **Floor + grey**: 15 IP for a trustworthy rate; below 6 IP, raw line only, no rate framing.
- **Exploit / action**: the two-branch approach that was the exact 2026-07-12 miss — "if he's wild (his norm), work counts/take walks; if he locates, he doesn't miss bats, put it in play and run." Joining this to SIG-001 is the single highest-value synthesis fix in the catalog.
- **Ethics tier**: coach-facing full names; player-safe = instruction only ("work the count"), never naming the pitcher.
- **Provenance**: design-doc §6 principle 5, §8 (P2's own line was the fix).

### SIG-005 — Loss-forensics blueprint (conditioned on probable starter)
- **Category**: G | **Matchup**: pure-opponent | **Depends on**: SIG-001 | **Validation**: validated-live (§8, 2026-07-12 — deterministic loss-counting held; the synthesis miss was NOT joining it to SIG-001) | **Fact-sheet key**: `loss_blueprint`
- **Detects**: the recurring thread(s) across a majority of the opponent's losses — who scored first, walks drawn, steals taken, when the losing pitcher was pulled — joined to the starter facing us.
- **Data source**: `games` (final scores → opponent losses) + `play_events.raw_template` (first-run, BB, SB, pitching-change sequence). "Scored first" is sharpened by the cheap line-score ingestion unlock (§7); today it is reconstructable from plays.
- **Computation**: per-loss counting across the loss set; surface the modal thread; condition on SIG-001's probable starter, not a season aggregate.
- **Floor + grey**: game-level counting across n≥5 losses is robust; below 5, use raw counts ("3 of their 4 losses"), never a percentage.
- **Exploit / action**: the core of the locker-room script — "3 things teams that beat them did," sharpened by the actual arm we face.
- **Ethics tier**: coach-facing raw; strips cleanly to player-facing instruction voice with no names.
- **Provenance**: design-doc §3 MUST #2, §8.

### SIG-006 — First-pitch-strike% per pitcher
- **Category**: B | **Matchup**: pure-opponent | **Depends on**: SIG-001 | **Validation**: computed | **Fact-sheet key**: `fps_by_arm`
- **Detects**: whether a pitcher is a "challenger" (pounds the zone early) or a "nibbler," per arm.
- **Data source**: `plays.is_first_pitch_strike` (per-PA first-pitch-strike flag; the FPS% partial index at `migrations/001` excludes HBP/IBB from the denominator so first-pitches ≈ qualifying PAs), keyed by `pitcher_id`. (Note: the per-pitch `is_first_pitch` column lives on `play_events`, not `plays`; FPS% per arm needs only the per-PA `plays` flag.)
- **Computation**: FPS% = first-pitch strikes / first pitches per arm; badge the charted-games denominator.
- **Floor + grey**: charted-games subset — badge charted vs total; treat <15 IP as thin.
- **Exploit / action**: cleanest per-batter ambush/patience cue — ≥60% FPS = "swing at strike one"; <48% = "take the first pitch, make him find it."
- **Ethics tier**: coach-facing names the pitcher; among the SAFEST to hand players directly ("expect strike one") — pure approach cue, not a weakness callout.
- **Provenance**: design-doc §4-B, §3 doctrine (FPS%/pitch data = charted subset).

### SIG-007 — Defensive-alignment directive (GB% + spray side)
- **Category**: C | **Matchup**: pure-opponent (sharpens with OUR personnel → pairing extension) | **Depends on**: none | **Validation**: validated-live (§8b-ii, 2026-07-13) | **Fact-sheet key**: `alignment`
- **Detects**: a hitter's ground-ball rate and pull/oppo side, turned into a positioning instruction rather than a description.
- **Data source**: `spray_charts` (`fielder_position`, `x`/`y`, `play_result`, `play_type` for GB/FB) per `batter` — buildable today, no `final_details` needed (design-doc §3 SHOULD #5 correction).
- **Computation**: GB% + pull/oppo side per hitter → directive: "shade 3B/SS, guard the 5-6 gap" / "infield in" (≥50% GB) / "OF deep" (≥45% FB).
- **Floor + grey**: 15 BIP directional floor; below it, raw spray counts only, flagged "insufficient sample for a directive."
- **Exploit / action**: reads straight onto the lineup card — changes where all 9 fielders stand before the at-bat.
- **Ethics tier**: the ONE signal where naming an opposing hitter is allowed on a PLAYER-FACING card — number-only, alignment purpose, no weakness language (§5).
- **Provenance**: design-doc §3 SHOULD #5, §8b-ii (P1/P5/P4/P7 read PULL+GB-left).

### SIG-008 — Defensive error-map by position → bunt/pressure targets
- **Category**: E | **Matchup**: pure-opponent | **Depends on**: none | **Validation**: computed (attribution-corrected — see caveat) | **Fact-sheet key**: `error_map`
- **Detects**: which defensive positions leak errors, as a rate (errors / chances), not a raw count.
- **Data source**: `spray_charts.error` + `fielder_position` (batted-ball error attribution) and/or `play_events.raw_template` error events. **ATTRIBUTION CAVEAT**: a defensive-error-map query was caught counting the WRONG team — the `team_id`/perspective filter MUST be verified before any error-map fact ships (see Discovery Pass gate).
- **Computation**: errors / fielding chances per position, filtered to the scouted team's defensive innings.
- **Floor + grey**: below ~10 season chances at a position, no directive.
- **Exploit / action**: "errors cluster at SS/3B, run at the left side" — a Tuesday-practice decision (drill bunt-for-a-hit) and a Friday in-game call.
- **Ethics tier**: coach-facing names positions/players; player-safe fully safe as-is ("their left side is shaky, we're bunting there") — positional, not an individual callout.
- **Provenance**: design-doc §4-E; team-lead attribution incident 2026-07-13.

### SIG-009 — Times-through-order fade
- **Category**: A | **Matchup**: pure-opponent | **Depends on**: SIG-001 | **Validation**: computed (not graded — one tier below validated-live) | **Fact-sheet key**: `tto_fade`
- **Detects**: whether a starter's reach-rate/hittability climbs the 2nd/3rd time a lineup sees him.
- **Data source**: `play_events.raw_template` (PA sequence → batter-vs-pitcher time-through index) + `player_game_pitching`.
- **Computation**: bucket PA by 1st/2nd/3rd time through; **reach-BASE rate (ROE-inclusive)** per bucket per `pitcher_id` — the discovery-run ONBASE set counts reached-on-error and dropped-3rd-strike as on-base, so it is BROADER than textbook OBP (BB+HBP+H) and must NOT be reconciled against a real OBP.
- **Floor + grey**: <15 PA in a within-game bucket = grey; need 3+ games of 3rd-time data before calling it a pattern.
- **Exploit / action**: tells the coach WHEN a starter gets hittable (late-game patience/aggression) and informs pinch-hit timing. Capped value — many HS/Legion starters don't survive a 3rd cycle under pitch limits.
- **Ethics tier**: coach-facing only (fatigue intel); no player translation beyond generic "stay ready off the bench."
- **Provenance**: design-doc §4-A; computed live — .488 reach-base rate 3rd time through, n=41 BF (P14, Opponent B team 192, discovery run 2026-07-13; counter-example P12 did NOT fade, 3rd-time .235 n=17). Computed from real data but NOT graded against a game outcome — hence `computed`, not `validated-live`.

### SIG-010 — Running-game concentration (top-2 SB share + gap)
- **Category**: D | **Matchup**: pure-opponent | **Depends on**: none | **Validation**: validated-live (§8c, 2026-07-13) | **Fact-sheet key**: `run_concentration`
- **Detects**: whether SB attempts are concentrated in 1–2 runners or spread across the roster.
- **Data source**: `player_game_batting` (SB per `player_id`, aggregated). **Key strictly by `player_id`** — §8c saw a garbled 58/6 count vs the true 121/15.
- **Computation**: top-2 SB share of team total + the #2→#3 gap.
- **Floor + grey**: needs ≥10 season team SB before "concentration" means anything.
- **Exploit / action**: concentrated (top-2 ≳65%, clear gap) → key on/neutralize 2 NAMED runners (hold close, slide-step, pitch-out); distributed (≲45%, no gap) → team-wide battery discipline instead. Tells the coach WHERE to spend hold-play effort.
- **Ethics tier**: coach-facing named; player-safe stays team-level ("they run a lot, stay alert").
- **Provenance**: design-doc §8c (Opponent A distributed 121/15/27%).

### SIG-011 — Leg-hit / speed-inflation ledger
- **Category**: C | **Matchup**: pure-opponent | **Depends on**: none | **Validation**: validated-live (§8b-i, 2026-07-13) | **Fact-sheet key**: `leg_hit_ledger`
- **Detects**: the share of a hitter's singles that were legged-out infield hits (vs clean OF hits) — de-inflates his batting line.
- **Data source**: `spray_charts` (a `play_result='single'` with an infield `fielder_position` P/C/1B/2B/3B/SS = infield hit; LF/CF/RF = clean) + `player_game_batting` (SB, AVG).
- **Computation**: infield-single% per hitter; flag SPEED-INFLATED when a high-SB hitter's infield-single share is high. Caveat: an IF-fielded single ≈ infield hit (sound, not perfect); bunt singles to C/P count.
- **Floor + grey**: small infield-single denominators shown raw ("50%, n=2" = a lean); ~15-BIP bar before flagging SPEED-INFLATED.
- **Exploit / action**: recalibrates the alignment (a legger demands infield-in + quick release) AND our pitcher's confidence — a ".333" may be a .250 bat with wheels; don't overreact by pitching around him.
- **Ethics tier**: coach-facing named; player-safe generic ("infield-hit guys, play in, quick release") — never call out an opposing kid's inflated AVG to players.
- **Provenance**: design-doc §8b-i (P8 .333, 42% legged).

### SIG-012 — Slasher overlay
- **Category**: C | **Matchup**: pure-opponent | **Depends on**: SIG-007, SIG-010, SIG-011 | **Validation**: computed | **Fact-sheet key**: `slasher`
- **Detects**: the intersection of the SB leaderboard, leg-hit ledger, and alignment card — a runner who is ALSO a compound offensive threat via legged-out grounders.
- **Data source**: derived — cross of SIG-010 (SB leaders), SIG-011 (infield-single%), SIG-007 (pull-GB-left).
- **Computation**: intersection flag: primary base-stealer AND heavy-GB-left AND high-infield-hit.
- **Floor + grey**: needs BOTH parent floors cleared (5+ SB attempts AND 15+ BIP) — never flag off a thin read on either axis.
- **Exploit / action**: compound call — infield in AND shaded left AND tighten the hold — for the one player who turns a routine 5-6 grounder into a legged single into a stolen base into a run. Worth flagging explicitly since a coach won't compute the intersection in the dugout.
- **Ethics tier**: coach-facing named.
- **Provenance**: design-doc §8c ("slasher" overlay; P4 analog on Opponent A).

### SIG-013 — Lineup-slot reach-base shape
- **Category**: C | **Matchup**: pure-opponent | **Depends on**: none | **Validation**: computed | **Fact-sheet key**: `lineup_slot_obp`
- **Detects**: where the batting order relaxes (a "breather" slot) or doesn't, by on-base rate per lineup position.
- **Data source**: `play_events.raw_template` (PA sequence → batting-order reconstruction; `batting_order` is NULL in scouting-loaded boxscores, §8) + on-base outcomes.
- **Computation**: OBP per reconstructed lineup slot, recency-weighted (last 5–7 games).
- **Floor + grey**: full-season PA per slot AND HS lineups aren't stable — weight the last 5–7 games, flag any slot <20 PA as thin, say explicitly when the lineup is too unstable for a reliable 9-slot shape.
- **Exploit / action**: "no breather, stay locked all 9" vs "7-8-9 is where you can pitch to contact" — informs our pitcher's effort allocation.
- **Ethics tier**: coach-facing.
- **Provenance**: design-doc §4-C, §8 (lineup-spine reconstruction nailed exactly; secondary lesson on recency).

### SIG-014 — GDP-prone hitters
- **Category**: C | **Matchup**: pure-opponent | **Depends on**: none | **Validation**: hypothesis | **Fact-sheet key**: `gdp_hitters`
- **Detects**: hitters who ground into double plays at an elevated rate in runner-on/<2-out situations.
- **Data source**: `play_events.raw_template` (double-play events, batter named) + base-state reconstruction from the baserunner-event sequence.
- **Computation**: GDP / GDP-opportunity (runner-on, <2-out) per `player_id` — the DENOMINATOR is opportunities, not total PA.
- **Floor + grey**: <10 GDP opportunities = no_data (usually small in a 30-game season); raw counts only.
- **Exploit / action**: turn-two candidates — infield plays for the DP with a runner on and this hitter up; tells OUR pitcher to pound the zone and induce the grounder.
- **Ethics tier**: coach-facing; rarely worth pushing to players (defensive call, not a batter instruction).
- **Provenance**: design-doc §4-C.

### SIG-015 — Baserunning-aggression cost / TOOTBLAN
- **Category**: D | **Matchup**: pure-opponent (vs-us extension is pairing) | **Depends on**: none | **Validation**: computed | **Fact-sheet key**: `baserunning_cost`
- **Detects**: whether an aggressive running team's outs-per-attempt make them a liability to press or a weapon not to be tested. Frequently a genuine NULL.
- **Data source**: `play_events.raw_template` (caught-stealing, picked-off, out-on-bases events) + `player_game_batting` (SB attempts).
- **Computation**: baserunning outs per attempt; classify press-worthy vs leave-alone.
- **Floor + grey**: needs ≥15–20 SB attempts before the rate means anything; below that raw counts only, no efficient/inefficient label.
- **Exploit / action**: keeps the memo from inventing a press play — e.g. 154 SB at 95%, 11 outs = "don't bother, control the free 90s instead" is itself the correct verdict.
- **Ethics tier**: coach-facing.
- **Provenance**: design-doc §4-D (TOOTBLAN ledger).

### SIG-016 — First-inning wobble per starter
- **Category**: B | **Matchup**: pure-opponent | **Depends on**: SIG-001 | **Validation**: computed | **Fact-sheet key**: `first_inning_wobble`
- **Detects**: whether a specific starter is measurably shakier in the 1st inning (runs/BB/hits) before settling.
- **Data source**: `play_events.raw_template` (inning=1 outcomes per `pitcher_id`) across his starts + `games`.
- **Computation**: 1st-inning runs/BB/hits allowed per start, averaged across starts.
- **Floor + grey**: needs 4–5+ starts by that pitcher before it's a pattern vs a one-off.
- **Exploit / action**: sets the OPENING LINE of the locker-room script and the top-of-order approach — "make him work in the 1st," including a bunt-and-run early against a wobbly arm.
- **Ethics tier**: coach-facing named.
- **Provenance**: design-doc §4-B, §8 (self-scout mirror: our starter's 1st-inning walk/HBP wobble).

### SIG-017 — Bunt-defense report card
- **Category**: E | **Matchup**: pure-opponent | **Depends on**: none | **Validation**: hypothesis | **Fact-sheet key**: `bunt_defense`
- **Detects**: whether the opponent's infield fields bunts cleanly or leaks errors specifically on bunt plays (a bunt-specific slice of SIG-008).
- **Data source**: `play_events.raw_template` (bunt play events + error/out outcome).
- **Computation**: errors / bunt attempts against them; raw counts.
- **Floor + grey**: single-digit season sample typical — raw counts only, never a rate.
- **Exploit / action**: "2 errors on 5 bunt attempts, drop one down" vs "they field bunts clean, don't waste an out" — informs practice plan and in-game call.
- **Ethics tier**: coach-facing; player-safe safe as-is ("we're bunting more this week").
- **Provenance**: design-doc §4-E.

### SIG-018 — Rally-starter / leadoff-slot OBP
- **Category**: C | **Matchup**: pure-opponent | **Depends on**: SIG-013 | **Validation**: computed | **Fact-sheet key**: `leadoff_obp`
- **Detects**: the actual on-base rate of whoever hits leadoff/#2 specifically, not the team overall.
- **Data source**: `play_events.raw_template` (lineup-slot reconstruction, shared with SIG-013) + on-base outcomes.
- **Computation**: OBP for the leadoff/#2 slot, recency-weighted.
- **Floor + grey**: 20 PA in the slot specifically, weighted to recent games (whole-season order modes mislead — §8).
- **Exploit / action**: a high-OBP leadoff hitter means our pitcher bears down early (leadoff walks score disproportionately); a weak leadoff spot = an easy get-ahead out.
- **Ethics tier**: coach-facing named.
- **Provenance**: design-doc §4-C (rally starters / leadoff OBP).

### SIG-019 — Two-strike chase rate (their hitters)
- **Category**: C | **Matchup**: pure-opponent | **Depends on**: none | **Validation**: hypothesis | **Fact-sheet key**: `two_strike_chase`
- **Detects**: whether a hitter expands the zone / chases once down two strikes, vs shortens up and puts it in play.
- **Data source**: `plays` / `play_events.raw_template` pitch sequences (count reconstructable per §2), keyed by `batter`.
- **Computation**: chase (swing at out-of-zone) rate on two-strike pitches per hitter; badge the charted-games subset.
- **Floor + grey**: pitch-level — <20 two-strike pitches seen = no_data; always badge charted subset.
- **Exploit / action**: pitch-calling intel for OUR arm — "two strikes, go up and away, he chases" vs a contact hitter (defend contact).
- **Ethics tier**: coach-facing only — pitch-calling intel has no batter-facing use.
- **Provenance**: design-doc §4-C (two-strike contact/chase profile).

### SIG-020 — Opposing-coach substitution pattern
- **Category**: coach-tendency (no §4 letter; design-doc §3 SHOULD #7) | **Matchup**: pure-opponent (bullpen-timing is an our-pen pairing extension) | **Depends on**: none | **Validation**: hypothesis | **Fact-sheet key**: `coach_subs`
- **Detects**: that specific opposing coach's pinch-hit and defensive-sub tendencies — timing, score-state, handedness.
- **Data source**: `play_events.raw_template` (substitution events) + game state (inning/score from `games` + plays).
- **Computation**: sub frequency/timing by score-state across that coach's games.
- **Floor + grey**: needs 5+ games of that specific opposing coach; HS/Legion benches (12–15 roster) are structurally small regardless.
- **Exploit / action**: tells our bullpen when to expect a pinch-hitter; flags a thin bench (starters playing through fatigue — exploitable late).
- **Ethics tier**: coach-facing only — about the OTHER coach's decisions, not a player, so the player-safe gate doesn't apply; not actionable for a player script.
- **Provenance**: design-doc §3 SHOULD #7 (coach-tendency scouting).

### SIG-021 — Backup-catcher exploit window
- **Category**: D | **Matchup**: pure-opponent | **Depends on**: SIG-002 | **Validation**: hypothesis | **Fact-sheet key**: `backup_catcher`
- **Detects**: whether the opponent's primary (strong-arm) catcher is sitting — rest, DH, injury — opening a window against a weaker backup.
- **Data source**: lineup / `player_game_*` catcher-position rows per game (who caught) cross-referenced with SIG-002's per-catcher CS/backpick.
- **Computation**: identify the primary catcher (innings/CS share); flag when a game's catcher is the backup. The backup's own CS sample is near-certain no_data.
- **Floor + grey**: backup's CS sample near-certain no_data (0–3 attempts all season) — the signal is situational awareness, not a computed rate.
- **Exploit / action**: mid-game adjustment more than pregame — "watch who's catching; if the backup enters, default aggressive" (who catches tonight isn't always knowable pregame).
- **Ethics tier**: coach-facing.
- **Provenance**: design-doc §4-D (backup-catcher exploit window).

---

## Fable-scout discovery batch (2026-07-13, accepted)

All entries below are `computed` — validated against the live DB with cross-checks by Fable-scout, but NOT graded against a game outcome (one tier below validated-live). Shared provenance: **Fable-scout discovery run 2026-07-13; computed with a `MIN(perspective_team_id)` dedup CTE, keyed by `player_id`/UUID.** Content cells are first-pass (lead spec); Coach-catalog refines coaching wording.

### SIG-022 — Frozen-hitter (called-strike-three share)
- **Category**: C | **Matchup**: pure-opponent | **Depends on**: none (batter-side complement to SIG-019) | **Validation**: computed | **Fact-sheet key**: `frozen_hitter`
- **Detects**: how often a hitter takes strike three LOOKING vs swinging — a "frozen" hitter who watches the putaway pitch. Needs no zone data (the complement SIG-019 does).
- **Data source**: `plays.outcome IN ('Strikeout','Dropped 3rd Strike')` + terminal `play_events.raw_template` `'Strike 3 looking'` vs `'... swinging'`, keyed by `batter` (`player_id`).
- **Computation**: called-K share = looking-K / total-K per hitter.
- **Floor + grey**: ≥8 K before a %; below that show raw counts.
- **Exploit / action**: OUR-pitcher putaway call. Against a frozen hitter (high looking-share), don't nibble on the 0-2/1-2 pitch — come right after him with a well-located strike, he's shown he won't offer. Against a hacker (low looking-share), a strike in the zone just gets put in play — you have to compete off the plate to get him to chase.
- **Ethics tier**: coach pitch-calling only (no batter-facing use).
- **Provenance**: Fable-scout run 2026-07-13; ex Opponent A P6 8/12 looking vs P2 3/9.

### SIG-023 — First-pitch approach per hitter (+P/PA)
- **Category**: C | **Matchup**: pure-opponent | **Depends on**: none (batter mirror of SIG-006) | **Validation**: computed | **Fact-sheet key**: `first_pitch_approach`
- **Detects**: whether a hitter swings at or takes the first pitch, plus pitches-per-PA (patience).
- **Data source**: `play_events.is_first_pitch` + `play_events.pitch_result` (swing set) for first-pitch-swing%; `plays.pitch_count` for P/PA. Keyed by `batter`.
- **Computation**: first-pitch-swing% + mean pitches/PA per hitter.
- **Floor + grey**: ≥30 first pitches; badge the charted-games denominator.
- **Exploit / action**: per-hitter first-pitch plan for OUR arm. Against an auto-taker (low first-pitch-swing%), get ahead with a get-me-over strike one — he's giving it to you. Against a first-pitch ambusher (high first-pitch-swing%), work the edges or off-speed early; grooving one is exactly what he's sitting on.
- **Ethics tier**: coach-facing names the hitter for pitch-calling; player-safe form for OUR pitcher stays generic ("get ahead early against automatic takers, work off the plate against hackers") without naming the batter.
- **Provenance**: Fable-scout run 2026-07-13; ex Opponent A P3 12% vs P7 43% first-pitch-swing.

### SIG-024 — Chaos-arm ledger (HBP + balk + WP per arm)
- **Category**: B | **Matchup**: pure-opponent | **Depends on**: none (distinct axis from SIG-004's walk/strike command) | **Validation**: computed | **Fact-sheet key**: `chaos_arm`
- **Detects**: pitchers who leak free bases via hit-batsmen, balks, and wild pitches — orthogonal to the walk/strike axis.
- **Data source**: `player_game_pitching.hbp` + `.wp`; balks from `play_events.raw_template` `'Balk by pitcher ${...}'` (⚠ the UUID starts at substr offset **19, NOT 18** — Fable's fixed off-by-one; a per-arm-per-game `player_game_pitching.bk` column also exists as a fallback). Keyed by `pitcher_id`.
- **Computation**: HBP per IP + balk count (raw) + WP per arm.
- **Floor + grey**: HBP needs ≥10 IP for a rate; balks raw at any n.
- **Exploit / action**: two distinct plays off one signal. Against a high-HBP arm, our hitters can crowd the plate and take the free base rather than bailing out. Against a balk-prone arm, load the corners and put pressure on him (secondary leads, a delayed steal look) — a pitcher with a track record of balking is more likely to balk again under pressure, and that's a free run.
- **Ethics tier**: coach-facing names the arm; player-safe form stays generic instruction to our hitters ("crowd the plate, take your base" / "get a good secondary lead, he balks under pressure") without naming the pitcher.
- **Provenance**: Fable-scout run 2026-07-13; ex Opponent A P13 9 HBP/11.3 IP + 3 balks.

### SIG-025 — Defensive-wobble window (errors by inning bucket)
- **Category**: E | **Matchup**: pure-opponent | **Depends on**: none (temporal companion to SIG-008) | **Validation**: computed | **Fact-sheet key**: `defensive_wobble`
- **Detects**: WHEN a defense leaks errors — early vs late innings. Team-SPECIFIC (a universal late-fatigue hypothesis was tested and REJECTED — see discovery log).
- **Data source**: `plays.outcome='Error'` bucketed by inning, defensive team resolved via the `games` join. Keyed by team.
- **Computation**: ROE share per inning bucket (early/late) per defensive team.
- **Floor + grey**: ≥10 ROE AND ≥20 defensive innings per bucket; show raw counts.
- **Exploit / action**: save our pressure plays (bunt-for-a-hit, steal attempts, hit-and-run) for the opponent's leaky inning window. If they're error-prone early, push the running game and small ball in innings 1-3; if they fade late, hold the pressure package for the 5th-7th, when their defense is more likely to crack.
- **Ethics tier**: player-safe (team-level).
- **Provenance**: Fable-scout run 2026-07-13; ex Opponent C 34% early vs 16% late; Opponent B inverse.

### SIG-026 — Turn-two threat (infield DP conversion)
- **Category**: E | **Matchup**: pure-opponent | **Depends on**: none (defensive mirror of SIG-014) | **Validation**: computed | **Fact-sheet key**: `turn_two`
- **Detects**: how often an infield turns the double play.
- **Data source**: `plays.outcome='Double Play'`, defensive team via the `games` join; denominator = defensive games (a true DP-opportunity denominator is a v2 refinement).
- **Computation**: DP per defensive game per team.
- **Floor + grey**: raw + per-def-game; label reliable at ≥25 defensive games.
- **Exploit / action**: sets our hit-and-run / avoid-the-DP rule for the day. Against a strong turn-two infield, put the runner in motion more often with a GDP-prone hitter up (a moving runner can't be doubled off first as easily) or send him on contact; against a weak turn-two infield, the DP risk on a routine grounder is lower, so play it straight.
- **Ethics tier**: player-safe.
- **Provenance**: Fable-scout run 2026-07-13; ex Opponent C 0.45/gm vs Opponent A 0.19.

### SIG-027 — Small-ball index (coach bunt usage)
- **Category**: coach-tendency (no §4 letter; design-doc §3 SHOULD #7) | **Matchup**: pure-opponent | **Depends on**: none | **Validation**: computed | **Fact-sheet key**: `small_ball`
- **Detects**: their coach's offensive bunt frequency — how much small-ball he plays.
- **Data source**: `plays.outcome='Sacrifice Bunt'` + `spray_charts.play_type='bunt'`. ⚠ Do NOT use `player_game_batting.shf` — that column is sac FLIES, not bunts. Keyed by team.
- **Computation**: sac-bunt + bunt-attempt count per team vs a peer baseline.
- **Floor + grey**: raw; label a small-ball team at ~≥2× the peer rate.
- **Exploit / action**: a practice-plan allocation call, not an in-game one — only spend Tuesday's limited practice time drilling bunt defense against an opponent whose coach actually plays small ball (flagged at ~2x the peer bunt rate). Against a non-bunting coach, that practice time is better spent elsewhere.
- **Ethics tier**: coach/defensive-prep; player-safe ("expect bunts, corners ready").
- **Provenance**: Fable-scout run 2026-07-13; ex Opponent C 15 sac bunts vs ~4 peers.

### SIG-028 — Late-game fade / front-runner  **(CONTEXT TIER — not a decision-driver)**
- **Category**: F (game flow — CONTEXT tier, matches design-doc §3 DEMOTED) | **Matchup**: pure-opponent | **Depends on**: none | **Validation**: computed (context) | **Fact-sheet key**: `game_flow`
- **Detects**: a team's run-timing curve + record when trailing after 4 + one-run-game record — a game-flow PROFILE, not a decision input.
- **Data source**: per-inning run distribution from `plays` (runs by inning, off/def via the `games` join) + `games` (final margin for one-run record + trail-after-4 state). Keyed by team.
- **Computation**: run-timing curve per inning; W-L when trailing after 4; one-run-game record.
- **Floor + grey / CONFOUNDS (record inline)**: late-inning cells are thin; "trails after 4 → loses" carries a team-QUALITY confound (descriptive, NOT causal); the 6th-inning scoring bump is LEAGUE-WIDE — read a team's curve AGAINST the league curve, never in isolation.
- **Exploit / action**: context, not a call. Fine to mention in the locker-room script so nobody panics if the opponent jumps out early ("they're front-runners — teams that hang around beat them late"), but it is descriptive, not causal: a team with a bad record when trailing after 4 may just be a worse team overall. Do NOT let this number change a specific bunt/steal/pitching-change decision on its own.
- **Ethics tier**: player-safe (team-level).
- **Provenance**: Fable-scout run 2026-07-13; ex Opponent C 1W–8L trailing after 4, dies after the 4th.

---

## Discovery Pass — standing method step

**The systemic fix.** Until now every signal above was surfaced by the operator spotting it by eye — reactive tooling. The discovery pass institutionalizes the eyeball as a repeatable METHOD that runs alongside the fixed fact-sheet.

**Documented as a METHOD, not codified as a skill/rule (yet).** Per Simple First, a `.claude/skills/discovery-pass` before the Deep Scout epic defines an actual agent-run workflow is speculative infra. It graduates to a skill only when the epic makes it an automated pass. For now it is an operator+agent practice that LEANS ON existing rules rather than restating them (`.claude/rules/tool-output-integrity.md` for cross-check; §8d attribution rule for UUID-not-name).

### The two passes

1. **Fixed pass (design-doc §6, exists)** — compute the known catalog signals into the fact sheet. Deterministic, always run.
2. **Discovery pass (new)** — after the fixed pass, an open-ended hypothesis sweep:
   - **Form hypotheses** from a rotating checklist: "is any stat concentrated in 1–2 players?" · "any split by inning / count / order slot?" · "any outlier vs league or vs our self-scout?" · "any tendency that only appears in losses?"
   - **Test many, cheaply.** Keep only survivors that clear the global-doctrine floor.
   - **Report survivors AND honest nulls** — "tested X, nothing there." Nulls are information: they stop the same ground being re-hunted and are recorded so the next session doesn't repeat them.
   - **VERIFY ATTRIBUTION before reporting — the hard gate.** No survivor reaches the memo until: (a) its query is attribution-checked — correct `team_id`/perspective filter, keyed by `player_id`/UUID not name (the SIG-008 wrong-team error-map; the SIG-010 §8c garbled 58/6 vs true 121/15); and (b) any surprising aggregate is cross-checked via an independent query per `tool-output-integrity.md`. A scout memo built on a mis-attributed or garbled count is worse than none.
   - **Promotion loop** — a survivor that recurs across opponents and validates gets PROMOTED into this catalog as a new `SIG-NNN` (`hypothesis` → `computed` → `validated-live`). **This is how the catalog grows.** The discovery pass is the standing generator; the catalog is its durable output.

### Integration with the fixed fact-sheet (§6) and prompt (Prompt A)

- **Fact-sheet contract gains a `discovery` block** beside the fixed sections: `{hypotheses_tested: N, survivors: [{value, n, status}...], nulls: [...]}` — same `{value, n, status}` contract as every other fact.
- **Attribution-verification is a fact-sheet PRECONDITION**, not a synthesis concern: a survivor cannot enter the fact sheet until attribution-checked + cross-checked. "Verify before reporting" is mechanical, upstream of the LLM.
- **The synthesis prompt treats survivors as leads under the SAME doctrine** (cite n inline, thin → "lean," ban always/never) but **flags them `unvalidated lead`** vs a catalog-validated signal — a fresh discovery finding carries more epistemic humility than an entry that cleared the recurrence bar.

### Discovery-run log — honest nulls & caveats (2026-07-13, Fable-scout)

Recorded as part of the method's null discipline (a rejected hypothesis is a result — it stops the same ground being re-hunted):
- **OF-arm / extra-bases-taken — NOT cheap-buildable.** Reconstructing outfield-arm suppression from relay chains needs data not cheaply available; rejected for v1, not promoted.
- **Universal late-inning defensive fatigue — TESTED and REJECTED.** The hypothesis that all defenses leak more errors late did NOT hold; the effect is team-SPECIFIC — which is exactly what SIG-025 (defensive-wobble window) captures instead.
- **League-curve caveat on SIG-028.** The 6th-inning scoring bump is league-wide, so a team's run-timing curve must be read AGAINST the league curve — recorded as a live confound on the signal, not a standalone rejection.

---

## Connection to the E-263 / Deep Scout epic (for PM)

- **Sharpens scope, does not expand the MUST tier.** The catalog turns design-doc §7's prose scope into a signal-by-signal build list — the epic points at `SIG-NNN` entries. The `Depends on` column names the joins that must exist (every pitcher signal joins SIG-001; SIG-012 joins three) — these are the exact synthesis fixes the 2026-07-12 live validation surfaced.
- **Discovery pass is a NEW capability §7 lacked.** Recommend v1 = fixed catalog signals + the discovery-pass METHOD as a documented operator practice; the AUTOMATED (agent-run) discovery pass is a v2 candidate. Keeps v1 shippable.
- **PM should capture ONE idea** ("Scouting Signal Catalog + discovery pass — inputs to Deep Scout v1", pointing here + at the design doc) so it is tracked in the ledger and reviewed on epic completion. No existing idea covers this (IDEA-022/037/084/108 are scouting-adjacent but distinct).
- **Home graduation**: this catalog stays in `.project/research/` while pre-epic. When Deep Scout v1 ships, promote it to `docs/` (product reference) — not before (Simple First; `docs/` implies committed stability).
