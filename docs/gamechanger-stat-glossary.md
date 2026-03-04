# GameChanger Stat Glossary

Source: GameChanger web UI stat definitions. This is the authoritative reference for all stat abbreviations used in the season-stats API response.

Cross-reference: `docs/gamechanger-api.md` (Schema: season-stats) maps these abbreviations to their JSON field names and types.

---

## Batting (Standard)

| Abbrev | Definition |
|--------|-----------|
| GP | Games played |
| PA | Plate appearances |
| AB | At bats |
| AVG | Batting average |
| OBP | On-base percentage |
| OPS | On-base percentage plus slugging percentage |
| SLG | Slugging percentage |
| H | Hits |
| 1B | Singles |
| 2B | Doubles |
| 3B | Triples |
| HR | Home runs |
| RBI | Runs batted in |
| R | Runs scored |
| BB | Base on balls (walks) |
| SO | Strikeouts |
| K-L | Strikeouts looking |
| HBP | Hit by pitch |
| SAC | Sacrifice hits & bunts |
| SF | Sacrifice flies |
| ROE | Reached on error |
| FC | Hit into fielder's choice |
| SB | Stolen bases |
| SB% | Stolen base percentage |
| CS | Caught stealing |
| PIK | Picked off |

## Batting (Advanced)

| Abbrev | Definition |
|--------|-----------|
| QAB | Quality at bats (any one of: 3 pitches after 2 strikes, 6+ pitch ABs, XBH, HHB, BB, SAC Bunt, SAC Fly) |
| QAB% | Quality at bats per plate appearance |
| PA/BB | Plate appearances per walk |
| BB/K | Walks per strikeout |
| C% | Contact percentage/Contact rate: AB-K/AB |
| HHB | Hard hit balls: Total line drives and hard ground balls |
| LD% | Line drive percentage |
| FB% | Fly ball percentage |
| GB% | Ground ball percentage |
| BABIP | Batting average on balls in play |
| BA/RISP | Batting average with runners in scoring position |
| LOB | Runners left on base |
| 2OUTRBI | 2-out RBI |
| XBH | Extra-base hits |
| TB | Total bases |
| PS | Pitches seen |
| PS/PA | Pitches seen per plate appearance |
| 2S+3 | Plate appearances in which batter sees 3+ pitches after 2 strikes |
| 2S+3% | % of plate appearances in which batter sees 3+ pitches after 2 strikes |
| 6+ | Plate appearances with 6+ pitches |
| 6+% | % of plate appearances of 6+ pitches |
| AB/HR | At bats per home run |
| GIDP | Hit into double play |
| GITP | Hit into triple play |
| CI | Batter advances on catcher's interference |

## Pitching (Standard)

| Abbrev | Definition |
|--------|-----------|
| IP | Innings pitched |
| GP | Games pitched |
| GS | Games started |
| BF | Total batters faced |
| #P | Total pitches |
| TS | Total strikes thrown |
| W | Wins |
| L | Losses |
| SV | Saves |
| SVO | Save opportunities |
| BS | Blown saves |
| SV% | Save percentage |
| H | Hits allowed |
| R | Runs allowed |
| ER | Earned runs allowed |
| BB | Base on balls (walks) |
| SO | Strikeouts |
| K-L | Strikeouts looking |
| HBP | Hit batters |
| ERA | Earned run average |
| WHIP | Walks plus hits per innings pitched |
| LOB | Runners left on base |
| BK | Balks |
| PIK | Runners picked off |
| CS | Runners caught stealing |
| SB | Stolen bases allowed |
| SB% | Stolen bases allowed percentage |
| WP | Wild pitches |
| BAA | Opponent batting average |
| MPHFB | Fastball average velocity |
| MPHCT | Cutter average velocity |
| MPHCB | Curveball average velocity |
| MPHSL | Slider average velocity |
| MPHCH | Changeup average velocity |
| MPHOS | Offspeed average velocity |

## Pitching (Advanced)

| Abbrev | Definition |
|--------|-----------|
| IP | Innings pitched |
| BF | Total batters faced |
| P/IP | Pitches per inning |
| P/BF | Pitches per batter faced |
| <3% | % of batters on or out in three pitches or less |
| LOO | Leadoff out (1st batter of inning) |
| 1ST2OUT | Innings with 1st 2 batters out |
| 123INN | 1-2-3 Innings |
| <13 | Innings of 13 pitches or fewer |
| FIP | Fielding Independent Pitching |
| S% | Strike percentage |
| FPS% | First pitch strike percentage |
| FPSO% | % of FPS at-bats that result in an out |
| FPSW% | % of FPS at-bats that result in a walk |
| FPSH% | % of FPS at-bats that result in a hit |
| BB/INN | Walks per inning |
| 0BBINN | Zero-walk innings |
| BBS | Walks that score |
| LOBB | Leadoff walk (1st batter of inning) |
| LOBBS | Leadoff walk that scored (1st batter of inning) |
| SM% | % of total pitches that are swings and misses |
| K/BF | Strikeouts per batter faced |
| K/BB | Strikeouts per walk |
| WEAK% | % of batted balls weakly hit (fly balls and ground balls) |
| HHB% | % of batted balls that are line drives or hard ground balls |
| GO/AO | Ratio of ground outs to air outs |
| HR | Home runs allowed |
| LD% | Line drive percentage |
| FB% | Fly ball percentage |
| GB% | % of all batted balls hit on the ground |
| BABIP | Opponent batting average on balls in play |
| BA/RISP | Opponent batting average with runners in scoring position |

## Pitch Type Breakdown

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

## Fielding

| Abbrev | Definition |
|--------|-----------|
| TC | Total Chances |
| A | Assists |
| PO | Putouts |
| FPCT | Fielding Percentage |
| E | Errors |
| DP | Double Plays |
| TP | Triple Plays |

## Catcher

| Abbrev | Definition |
|--------|-----------|
| INN | Innings played as catcher |
| PB | Passed balls allowed |
| SB | Stolen bases allowed |
| SB-ATT | Stolen bases - Stealing attempts |
| CS | Runners caught stealing |
| CS% | Runners caught stealing percentage |
| PIK | Runners picked off |
| CI | Batter advances on catcher's interference |

## Positional Innings

| Abbrev | Definition |
|--------|-----------|
| P | Innings played at pitcher |
| C | Innings played at catcher |
| 1B | Innings played at first base |
| 2B | Innings played at second base |
| 3B | Innings played at third base |
| SS | Innings played at shortstop |
| LF | Innings played at left field |
| CF | Innings played at center field |
| RF | Innings played at right field |
| SF | Innings played at short field |
| Total | Total innings played |

---

## API Field Name Mapping

The season-stats API uses slightly different field names than the UI glossary in some cases:

| UI Glossary | API Field | Notes |
|-------------|-----------|-------|
| K-L (Strikeouts looking) | `SOL` | API abbreviation differs |
| HHB (Hard hit balls) | `HARD` | API uses HARD for count |
| HHB% | `HARD%` | API uses HARD% for percentage |
| SAC (Sacrifice hits) | `SHB` | API splits into SHB (sac bunts) |
| SF (Sacrifice flies) | `SHF` | API uses SHF |
| INN (Catcher innings) | `IC:C` | API uses IP-style prefix |
| PB (Passed balls) | `PB:C` | API appends :C for catcher context |
| SB-ATT (Steal attempts) | `SBATT:C` | API uses SBATT:C |
| CS% (Catcher) | `CS:C%` | API appends :C for catcher context |
| LOO | `LOO` | Leadoff out (1st batter of inning) |
| LOBB (pitching) | `LOBB` | Leadoff walk (1st batter of inning) |
| BBS | `BBS` | Walks that score |
| LOBBS | `LOBBS` | Leadoff walk that scored |
| <13 | `<13` | Innings of 13 pitches or fewer |
| 1ST2OUT | `1ST2OUT` | Innings with 1st 2 batters out |

## Notes

- The API response includes pitch-type abbreviation fields (`CH%`, `CB%`, `DB%`, `SL%`, `KC%`, `FB%`, `OS%`, `SC%`, `RB%`, `CT%`, `KB%`, `DC%`) all set to `0` in the observed sample. These likely correspond to the pitch-type breakdown stats but require pitch-type tagging to be enabled in GameChanger for non-zero values.
- `OSMPH`, `OS#MPH` in the API response likely correspond to offspeed velocity fields (`MPHOS`).
- `IP:SF` appears in the API but "SF" (short field) positional innings are uncommon -- only used in certain league configurations.
- `TP:P` = triple plays turned as pitcher (observed as 0 in all samples).
