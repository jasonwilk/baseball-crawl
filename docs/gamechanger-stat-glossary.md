# GameChanger Stat Glossary

Sources:
- GameChanger web UI stat definitions (original)
- GameChanger JS bundle (index.DQHXBrEi.js, extracted 2026-03-12)

This is the authoritative reference for all stat abbreviations used in GameChanger API responses and the GC UI.

Cross-reference: `docs/api/endpoints/get-teams-team_id-season-stats.md` (Schema: season-stats) maps these abbreviations to their JSON field names and types.

---

## Boxscore Column Groups

These are the stat groups displayed in the GameChanger boxscore view, extracted from the JS bundle.

| Group | Stats | Category |
|-------|-------|----------|
| BATTING | AB, R, H, RBI, BB, SO | offense |
| BATTING_EXTRA | 2B, 3B, HR, TB, HBP, SHF, SB, CS | offense |
| PITCHING | IP, H, R, ER, BB, SO | defense |
| PITCHING_EXTRA | WP, HBP, #P, TS, BF | defense |
| FIELDING_EXTRA | E | defense |

Note: `SHF` in BATTING_EXTRA is the API field name for sacrifice flies (UI label: `SF`). `TB` in PITCHING_EXTRA is total balls (not total bases -- pitching context).

---

## Batting (Standard)

| Abbrev | API Field | Definition |
|--------|-----------|-----------|
| GP | GP | Games played |
| PA | PA | Plate appearances |
| AB | AB | At bats |
| AVG | AVG | Batting average |
| OBP | OBP | On-base percentage |
| OPS | OPS | On-base percentage plus slugging percentage |
| SLG | SLG | Slugging percentage |
| H | H | Hits |
| 1B | 1B | Singles |
| 2B | 2B | Doubles |
| 3B | 3B | Triples |
| HR | HR | Home runs |
| RBI | RBI | Runs batted in |
| R | R | Runs scored |
| BB | BB | Base on balls (walks) |
| SO | SO | Strikeouts |
| K-L | SOL | Strikeouts looking |
| HBP | HBP | Hit by pitch |
| SAC | SHB | Sacrifice hits & bunts |
| SF | SHF | Sacrifice flies |
| ROE | ROE | Reached on error |
| FC | FC | Hit into fielder's choice |
| SB | SB | Stolen bases |
| SB% | SB% | Stolen base percentage |
| CS | CS | Caught stealing |
| PIK | PIK | Picked off |

## Batting (Advanced)

| Abbrev | API Field | Definition |
|--------|-----------|-----------|
| QAB | QAB | Quality at bats (any one of: 3 pitches after 2 strikes, 6+ pitch ABs, XBH, HHB, BB, SAC Bunt, SAC Fly) |
| QAB% | QAB% | Quality at bats per plate appearance |
| PA/BB | PA/BB | Plate appearances per walk |
| BB/K | BB/K | Walks per strikeout |
| C% | C% | Contact percentage/Contact rate: AB-K/AB |
| HHB | HARD | Hard hit balls: Total line drives and hard ground balls |
| HHB% | HARD% | % of batted balls that are line drives or hard ground balls |
| LD | LND | Line drives |
| LD% | LD% | Line drive percentage |
| FB | FLB | Fly balls |
| FB% | FB% | Fly ball percentage |
| GB | GB | Ground balls |
| GB% | GB% | Ground ball percentage |
| BABIP | BABIP | Batting average on balls in play |
| BA/RISP | BA/RISP | Batting average with runners in scoring position |
| LOB | LOB | Runners left on base |
| 2OUTRBI | 2OUTRBI | 2-out RBI |
| XBH | XBH | Extra-base hits |
| TB | TB | Total bases |
| PS | PS | Pitches seen |
| PS/PA | PS/PA | Pitches seen per plate appearance |
| 2S+3 | 2S+3 | Plate appearances in which batter sees 3+ pitches after 2 strikes |
| 2S+3% | 2S+3% | % of plate appearances in which batter sees 3+ pitches after 2 strikes |
| 6+ | 6+ | Plate appearances with 6+ pitches |
| 6+% | 6+% | % of plate appearances of 6+ pitches |
| AB/HR | AB/HR | At bats per home run |
| GIDP | GIDP | Hit into double play |
| GITP | GITP | Hit into triple play |
| CI | CI | Batter advances on catcher's interference |
| SB-ATT | SB-ATT | Stolen bases - Stealing attempts |

---

## Pitching (Standard)

| Abbrev | API Field | Definition |
|--------|-----------|-----------|
| IP | outs | Innings pitched (API stores as out count; divide by 3 for display) |
| GP | GP:P | Games pitched |
| GS | GS | Games started |
| BF | BF | Total batters faced |
| #P | #P | Total pitches |
| TS | TS | Total strikes thrown |
| TB | TB | Total balls |
| W | W | Wins |
| L | L | Losses |
| SV | SV | Saves |
| SVO | SVO | Save opportunities |
| BS | BS | Blown saves |
| SV% | SV% | Save percentage |
| H | H | Hits allowed |
| R | R | Runs allowed |
| ER | ER | Earned runs allowed |
| BB | BB | Base on balls (walks) |
| SO | SO | Strikeouts |
| K-L | SOL | Strikeouts looking |
| HBP | HBP | Hit batters |
| ERA | ERA | Earned run average |
| WHIP | WHIP | Walks plus hits per innings pitched |
| LOB | LOB | Runners left on base |
| BK | BK | Balks |
| PIK | PIK | Runners picked off |
| CS | CS | Runners caught stealing |
| SB | SB | Stolen bases allowed |
| SB% | SB% | Stolen bases allowed percentage |
| WP | WP | Wild pitches |
| HR | HR | Home runs allowed |
| BAA | BAA | Opponent batting average |

## Pitching (Advanced)

| Abbrev | API Field | Definition |
|--------|-----------|-----------|
| P/IP | P/IP | Pitches per inning |
| P/BF | P/BF | Pitches per batter faced |
| K/BF | K/BF | Strikeouts per batter faced |
| K/BB | K/BB | Strikeouts per walk |
| FIP | FIP | Fielding Independent Pitching |
| S% | S% | Strike percentage |
| FPS% | FPS% | First pitch strike percentage |
| FPSO% | FPSO% | % of FPS at-bats that result in an out |
| FPSW% | FPSW% | % of FPS at-bats that result in a walk |
| FPSH% | FPSH% | % of FPS at-bats that result in a hit |
| BB/INN | BB/INN | Walks per inning |
| 0BBINN | 0BBINN | Zero-walk innings |
| BBS | BBS | Walks that score |
| LOBB | LOBB | Leadoff walk (1st batter of inning) |
| LOBBS | LOBBS | Leadoff walk that scored (1st batter of inning) |
| LOO | LOO | Leadoff out (1st batter of inning) |
| 1ST2OUT | 1ST2OUT | Innings with 1st 2 batters out |
| 123INN | 123INN | 1-2-3 Innings |
| <13 | <13 | Innings of 13 pitches or fewer |
| <3 | <3 | Batters on or out in three pitches or less |
| <3% | <3% | % of batters on or out in three pitches or less |
| LBFP# | LBFPN | Pitch count number of first pitch to last batter faced |
| SM | SM | Opposing batter swings-and-misses |
| SM% | SM% | % of total pitches that are swings and misses |
| SW | SW | Total pitches batters swung at |
| GO | GO | Ground outs |
| AO | AO | Air outs (fly outs) |
| GO/AO | GO/AO | Ratio of ground outs to air outs |
| WHB | WEAK | Number of batted balls weakly hit (fly balls and ground balls) |
| WEAK% | WEAK% | % of batted balls weakly hit (fly balls and ground balls) |
| HHB | HARD | Number of batted balls that are line drives or hard ground balls |
| HHB% | HHB% | % of batted balls that are line drives or hard ground balls |
| LD | LND | Line drives (pitching context) |
| LD% | LD% | Line drive percentage |
| FB | FB | Fly balls (pitching context) |
| FB% | FB% | Fly ball percentage |
| GB | GB | Ground balls (pitching context) |
| GB% | GB% | % of all batted balls hit on the ground |
| BABIP | BABIP | Opponent batting average on balls in play |
| BA/RISP | BA/RISP | Opponent batting average with runners in scoring position |

---

## Fielding

| Abbrev | API Field | Definition |
|--------|-----------|-----------|
| GP | GP:F | Games played (fielding) |
| TC | TC | Total Chances |
| A | A | Assists |
| PO | PO | Putouts |
| FPCT | FPCT | Fielding Percentage |
| E | E | Errors |
| DP | DP | Double Plays |
| TP | TP | Triple Plays |
| WHB | WEAK | Weakly hit balls (fly balls and ground balls) |
| HHB | HARD | Hard hit balls (line drives or hard ground balls) |
| LD | LND | Line drives (fielding context) |

---

## Catcher

| Abbrev | API Field | Definition |
|--------|-----------|-----------|
| GP | GP:C | Games played as catcher |
| INN | outs:C | Innings played as catcher (API stores as out count) |
| PB | PB:C | Passed balls allowed |
| SB | SB:C | Stolen bases allowed |
| SB-ATT | SB-ATT | Stolen bases - Stealing attempts |
| CS | CS:C | Runners caught stealing |
| CS% | CS:C% | Runners caught stealing percentage |
| PIK | PIK:C | Runners picked off |
| CI | CI:C | Batter advances on catcher's interference |

---

## Positional Innings

The API stores positional innings as out counts (field prefix `outs-`). Divide by 3 for display.

| Abbrev | API Field | Definition |
|--------|-----------|-----------|
| P | IP | Innings played at pitcher |
| C | IC:C | Innings played at catcher |
| 1B | outs-1B | Innings played at first base |
| 2B | outs-2B | Innings played at second base (context: positional innings) |
| 3B | outs-3B | Innings played at third base |
| SS | outs-SS | Innings played at shortstop |
| LF | outs-LF | Innings played at left field |
| CF | outs-CF | Innings played at center field |
| RF | outs-RF | Innings played at right field |
| SF | outs-SF | Innings played at short field (softball; uncommon in baseball) |
| Total | IP:F | Total innings played |

---

## Pitch Type Breakdown (Baseball)

Each pitch type has a count, strikes, strike%, swing%, and swing-and-miss% stat. Baseball pitch types:

| Abbrev | Definition |
|--------|-----------|
| #P | Total pitches |
| FB | Number of pitches thrown as Fastballs |
| FBS | Number of Fastballs thrown for strikes |
| FBS% | Percentage of Fastballs thrown for strikes |
| FBSW% | Percentage of Fastballs swung at |
| FBSM% | Percentage of Fastballs swung at and missed |
| MPHFB | Fastball average velocity |
| CT | Number of pitches thrown as Cutters |
| CTS | Number of Cutters thrown for strikes |
| CTS% | Percentage of Cutters thrown for strikes |
| CTSW% | Percentage of Cutters swung at |
| CTSM% | Percentage of Cutters swung at and missed |
| MPHCT | Cutter average velocity |
| CB | Number of pitches thrown as Curveballs |
| CBS | Number of Curveballs thrown for strikes |
| CBS% | Percentage of Curveballs thrown for strikes |
| CBSW% | Percentage of Curveballs swung at |
| CBSM% | Percentage of Curveballs swung at and missed |
| MPHCB | Curveball average velocity |
| SL | Number of pitches thrown as Sliders |
| SLS | Number of Sliders thrown for strikes |
| SLS% | Percentage of Sliders thrown for strikes |
| SLSW% | Percentage of Sliders swung at |
| SLSM% | Percentage of Sliders swung at and missed |
| MPHSL | Slider average velocity |
| CH | Number of pitches thrown as Changeups |
| CHS | Number of Changeups thrown for strikes |
| CHS% | Percentage of Changeups thrown for strikes |
| CHSW% | Percentage of Changeups swung at |
| CHSM% | Percentage of Changeups swung at and missed |
| MPHCH | Changeup average velocity |
| OS | Number of pitches thrown as Offspeeds |
| OSS | Number of Offspeeds thrown for strikes |
| OSS% | Percentage of Offspeeds thrown for strikes |
| OSSW% | Percentage of Offspeeds swung at |
| OSSM% | Percentage of Offspeeds swung at and missed |
| MPHOS | Offspeed average velocity |

## Pitch Type Breakdown (Softball)

Softball-specific pitch types not used in baseball:

| Abbrev | Definition |
|--------|-----------|
| RB | Number of pitches thrown as Riseballs |
| RBS | Number of Riseballs thrown for strikes |
| RBS% | Percentage of Riseballs thrown for strikes |
| RBSW% | Percentage of Riseballs swung at |
| RBSM% | Percentage of Riseballs swung at and missed |
| MPHRB | Riseball average velocity |
| DB | Number of pitches thrown as Dropballs |
| DBS | Number of Dropballs thrown for strikes |
| DBS% | Percentage of Dropballs thrown for strikes |
| DBSW% | Percentage of Dropballs swung at |
| DBSM% | Percentage of Dropballs swung at and missed |
| MPHDB | Dropball average velocity |
| SC | Number of pitches thrown as Screwballs |
| SCS | Number of Screwballs thrown for strikes |
| SCS% | Percentage of Screwballs thrown for strikes |
| SCSW% | Percentage of Screwballs swung at |
| SCSM% | Percentage of Screwballs swung at and missed |
| MPHSC | Screwball average velocity |
| DC | Number of pitches thrown as Drop Curves |
| DCS | Number of Drop Curves thrown for strikes |
| DCS% | Percentage of Drop Curves thrown for strikes |
| DCSW% | Percentage of Drop Curves swung at |
| DCSM% | Percentage of Drop Curves swung at and missed |
| MPHDC | Drop Curve average velocity |
| KB | Number of pitches thrown as Knuckleballs |
| KBS | Number of Knuckleballs thrown for strikes |
| KBS% | Percentage of Knuckleballs thrown for strikes |
| KBSW% | Percentage of Knuckleballs swung at |
| KBSM% | Percentage of Knuckleballs swung at and missed |
| MPHKB | Knuckleball average velocity |
| KC | Number of pitches thrown as Knuckle Curves |
| KCS | Number of Knuckle Curves thrown for strikes |
| KCS% | Percentage of Knuckle Curves thrown for strikes |
| KCSW% | Percentage of Knuckle Curves swung at |
| KCSM% | Percentage of Knuckle Curves swung at and missed |
| MPHKC | Knuckle Curve average velocity |

---

## Play Event Types

These event type strings appear in the `plays` endpoint response and drive play-by-play reconstruction.

| Event Type | Description |
|------------|-------------|
| `single` | Single |
| `double` | Double |
| `triple` | Triple |
| `home_run` | Home run |
| `strikeout` | Strikeout (swinging) |
| `dropped_third_strike` | Dropped third strike -- batter reaches base |
| `dropped_third_strike_batter_out` | Dropped third strike -- batter thrown out |
| `walk` | Base on balls (walk) |
| `hit_by_pitch` | Hit by pitch |
| `sacrifice_bunt` | Sacrifice bunt |
| `sacrifice_bunt_error` | Sacrifice bunt attempt resulting in error |
| `sacrifice_fly` | Sacrifice fly |
| `sacrifice_fly_error` | Sacrifice fly attempt resulting in error |
| `fielders_choice` | Fielder's choice |
| `fielders_choice_double_play` | Fielder's choice resulting in double play |
| `double_play` | Double play |
| `error` | Reached on error |
| `fielding_error` | Fielding error (alternate form) |
| `reached_on_error` | Reached on error (alternate form) |
| `foul_tip_out` | Foul tip caught for out (third strike) |
| `infield_fly` | Infield fly rule |
| `out_on_appeal` | Out on appeal |
| `other_out` | Other out (not further classified) |
| `stole_base` | Stolen base (alternate form) |
| `steal` | Stolen base attempt |
| `caught_stealing` | Caught stealing |
| `picked_off` | Picked off |
| `passed_ball` | Passed ball (baserunner advance) |
| `wild_pitch` | Wild pitch (baserunner advance) |
| `other_advance` | Other baserunner advance |
| `catcher_interference` | Catcher interference |
| `offensive_interference` | Offensive interference |
| `illegal_pitch` | Illegal pitch |

---

## API Field Name Mapping

The GameChanger API uses different field names than the UI in a number of cases. This table is the canonical mapping, sourced from the JS bundle (2026-03-12).

### Batting

| UI Label | API Field | Notes |
|----------|-----------|-------|
| K-L (Strikeouts looking) | `SOL` | UI uses K-L; API uses SOL |
| SAC (Sacrifice hits/bunts) | `SHB` | API splits sacrifice bunts into SHB |
| SF (Sacrifice flies) | `SHF` | API uses SHF; note: SHF also appears in the BATTING_EXTRA boxscore group |
| HHB (Hard hit balls) | `HARD` | API uses HARD for count |
| HHB% | `HARD%` | API uses HARD% for percentage |
| LD (Line drives) | `LND` | API uses LND |
| FB (Fly balls) | `FLB` | API uses FLB in batting context |

### Pitching

| UI Label | API Field | Notes |
|----------|-----------|-------|
| IP (Innings pitched) | `outs` | API stores as total outs; divide by 3 for innings display |
| K-L (Strikeouts looking) | `SOL` | Same as batting |
| LBFP# (Last batter first pitch count) | `LBFPN` | API uses LBFPN |
| WHB (Weakly hit balls) | `WEAK` | API uses WEAK for count |
| HHB (Hard hit balls) | `HARD` | API uses HARD |
| LD (Line drives) | `LND` | API uses LND |
| FB (Fly balls) -- pitching context | `FB` | No alias needed; API uses FB in pitching context |

### Fielding

| UI Label | API Field | Notes |
|----------|-----------|-------|
| WHB (Weakly hit balls) | `WEAK` | API uses WEAK |
| HHB (Hard hit balls) | `HARD` | API uses HARD |
| LD (Line drives) | `LND` | API uses LND |
| PIK (Picked off, catcher) | `PIK:C` | Catcher context appends :C |
| CI (Catcher interference) | `CI:C` | Catcher context appends :C |
| CS (Caught stealing, catcher) | `CS:C` | Catcher context appends :C |
| SB (Stolen bases, catcher) | `SB:C` | Catcher context appends :C |
| PB (Passed balls) | `PB:C` | Catcher context appends :C |
| INN (Catcher innings) | `outs:C` | API stores as out count; catcher context |
| IP (Pitcher positional innings) | `outs` | Same field as innings pitched |
| 1B positional innings | `outs-1B` | Pattern: `outs-{position}` for all positions |
| 2B positional innings | `outs-2B` | |
| 3B positional innings | `outs-3B` | |
| SS positional innings | `outs-SS` | |
| LF positional innings | `outs-LF` | |
| CF positional innings | `outs-CF` | |
| RF positional innings | `outs-RF` | |
| SF positional innings | `outs-SF` | Short field (softball) |
| Total innings played | `IP:F` | |

---

## Notes

- The API response includes pitch-type percentage fields (`CH%`, `CB%`, `DB%`, `SL%`, `KC%`, `FB%`, `OS%`, `SC%`, `RB%`, `CT%`, `KB%`, `DC%`) typically set to `0` unless pitch-type tagging is enabled in GameChanger.
- `OSMPH`, `OS#MPH` in some API responses likely correspond to offspeed velocity fields (`MPHOS`).
- `IP:SF` appears in the API for short field positional innings. Uncommon in baseball; used in some softball league configurations.
- `TP:P` = triple plays turned as pitcher (observed as 0 in all samples).
- The `SB-ATT` field represents steal attempt totals. In the catcher stats section, the API uses `SBATT:C`.
- `TB` has two distinct meanings depending on context: "Total Bases" in batting stats, and "Total Balls" in pitching stats (PITCHING_EXTRA boxscore group).
- Velocity stats for baseball: MPHFB, MPHCT, MPHCB, MPHSL, MPHCH, MPHOS. Short UI labels: "FB Velo", "CT Velo", "CB Velo", "SL Velo", "CH Velo", "OS Velo".
- Velocity stats for softball: MPHRB, MPHDB, MPHSC, MPHDC, MPHKB, MPHKC. Short UI labels: "RB Velo", "DB Velo", "SC Velo", "DC Velo", "KB Velo", "KC Velo".
- Editable batting stats (26+): GP, AB, 1B, 2B, 3B, HR, RBI, R, BB, SO, K-L, HBP, SAC, SF, ROE, FC, SB, CS, PIK, QAB, HHB, LD, FB, GB, LOB, 2OUTRBI, PS, 2S+3, 6+, GIDP, CI
- Editable pitching stats (35+): GP:P, IP, GS, BF, #P, TB, TS, H, R, ER, BB, SO, K-L, HBP, LOB, BK, PIK, CS, SB, WP, W, L, SV, BS, LBFP#, <3, LOO, 1ST2OUT, 123INN, <13, 0BBINN, BBS, LOBB, LOBBS, SM, SW, WHB, HHB, GO, AO, LD, FB, GB
- Editable fielding stats (6): GP:F, A, PO, E, DP, TP
- Editable catching stats (7): GP:C, INN, PB, SB, CS, PIK, CI
