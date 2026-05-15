# Coaching Dashboard

The coaching dashboard is live. Access it at `/dashboard/` — Jason will share the link and login with coaching staff.

---

## Dashboard Layout

The dashboard has three tabs at the bottom of the screen:

| Tab | What you see |
|-----|-------------|
| **Schedule** | Your team's full season schedule — upcoming and completed games |
| **Batting** | Your team's batting stats by player for the current season |
| **Pitching** | Your team's pitching stats by player for the current season |

The **Schedule** tab opens by default.

---

## Schedule View

The schedule shows every game for the active team and season in date order.

### Upcoming Games

Each upcoming game row shows:
- **Date** and how many days away it is
- **Opponent name** — tap to open the opponent scouting page
- **Home or Away** indicator
- **Scouted / Not Scouted badge** — green badge means we have stats loaded for this opponent; no badge means scouting data hasn't been pulled yet

The next game on the schedule is highlighted so it's easy to find at a glance.

### Completed Games

Each completed game row shows:
- **Date** and **opponent name**
- **Score** (tap to view the box score)
- **W or L** result
- **Home or Away** indicator

---

## Opponent Scouting Page

Tap any upcoming opponent's name to open their scouting page. The page opens with pitching information first, since "who's on the mound?" is the first question before any game.

### Game Coverage Indicator

Near the top of the page you'll see a line like:

> Through Mar 25 (8 games)

This tells you two things at once: how current the scouting data is (the most recent game date) and how many games the stats are based on. Eight games tells a much more reliable story than three — keep the game count in mind when weighing the numbers.

If no games have been loaded for this opponent yet, the coverage line won't appear. That means the system hasn't scouted this team yet — see the empty states section below.

### What You'll See

**Pitching** — Top three pitchers by innings pitched this season. For each pitcher:
- ERA, K/9 (strikeouts per 9 innings), BB/9 (walks per 9 innings)
- K/BB ratio — a higher number means they pound the zone; a lower number means they struggle with control
- Games pitched this season
- Handedness (L/R) when available
- **Rest** — how many days since this pitcher last appeared (e.g., "2d"). "Today" means they pitched in the most recent game. "—" means no outing data is available.
- **P (7d)** — total pitches thrown over the last 7 days, plus how many of those days included an appearance (e.g., "85/3d" = 85 pitches across 3 outings in the last 7 days). "—" means no recent outings. "?/2d" means the pitcher appeared but pitch counts weren't recorded in GameChanger.

**Team Batting Summary** — The opponent's team-wide tendencies for the season:
- OBP (on-base percentage), strikeout rate, walk rate, SLG (slugging)

Every rate stat shows the number of games it's based on (e.g., "2.10 ERA (8 GP)"). A stat based on 3 games means less than one based on 15 — keep sample size in mind.

**Full Pitching and Batting Tables** — Complete per-player breakdowns below the summary cards.

**Predicted Starter** — Who to expect on the mound. See the section below for details.

---

## Predicted Starter

The opponent scouting page includes a **Predicted Starter** section that answers the first question on any coach's mind: who is taking the ball next game?

The system analyzes this opponent's pitching history — rotation sequence, rest days, and recent workload — and makes its best call on who to expect on the mound.

### Confidence Tiers

The prediction comes in four forms depending on how much data is available and how clear the rotation pattern is:

| What you see | What it means |
|---|---|
| **Named starter, no qualifier** | Strong signal — rotation pattern is clear, rest lines up, this pitcher is the call |
| **Named starter with a caveat** | Rotation pick is clear, but a matchup alternative is plausible — review both candidates |
| **Multiple options shown equally** | No single clear pick — staff uses a committee or rotation is too irregular to call; use the rest table |
| **Rest table only, no prediction** | Fewer than 4 games in the system — not enough data to predict a starter |

When a starter is named, the reasoning line tells you why — for example: "Last pitched 5 days ago, leads rotation with 6 starts, averages 4.8 days rest between starts."

### Rest and Availability Table

Below the prediction (or alone when there isn't enough data) is a compact table showing the top arms on this staff — starters first, then key relievers:

| Column | What it shows |
|---|---|
| **Name** | Pitcher name; **GS** badge shows starts this season |
| **Last Outing** | How many days ago this pitcher last appeared (any role) |
| **Last Outing #P** | Pitch count in their most recent outing |
| **7d Workload** | Total pitches thrown across all appearances in the last 7 days |

A pitcher who threw 85+ pitches with fewer than 4 days rest is unlikely to start — the system factors this in when ranking candidates. A pitcher flagged "availability unknown" hasn't appeared in 10+ days and may be injured or unavailable.

### Bullpen Order

Below the rest table you'll see the likely bullpen order: which relievers have most often been the first out of the pen after the starter exits. This helps you anticipate who you'll face if the starter is pulled early.

### A Prediction, Not a Guarantee

The system predicts based on rotation pattern, rest, and workload. The opposing coach may make a matchup decision that overrides the rotation — that happens. Treat the prediction as the most likely scenario, not a certainty. A note at the bottom of the section always states what the prediction is based on.

---

## Three Scouting States

Not every opponent will have full data. The page handles three situations:

| State | What you see | What it means |
|-------|-------------|--------------|
| **Full stats** | Stats, coverage indicator, and spray charts all populated | Scouting data has been loaded for this opponent |
| **Linked, not scouted yet** | "No scouting data yet. Stats will appear after the next update." | The opponent is in the system but the scouting pull hasn't run yet — this often resolves on its own within minutes; if it doesn't, ask Jason |
| **Not linked** | "This opponent isn't linked to GameChanger yet." | The opponent hasn't been connected to GameChanger — Jason handles this in the admin panel |

If you open an opponent page and see one of these messages instead of stats, it is not a broken page — it is the system telling you exactly what the situation is. When in doubt, ask Jason to check on it before game day.

---

## Printing a Scouting Report

When full stats are loaded for an opponent, a **Print / Save as PDF** link appears at the top of their scouting page. Tap it to open a print-ready version of the report.

The print view is formatted for a standard landscape page:

- **Page 1**: Report header, game coverage indicator ("Through [date] ([N] games)"), context bar (last meeting result and batting tendencies), and the full pitching table. The **Rest** column in the print view shows the actual date of last outing (e.g., "Mar 28") rather than days elapsed — so the printed report is accurate even if it's read a few days later.
- **Page 2+**: Full batting table and batter tendencies charts

From the print view, use your browser's print command (**Ctrl+P** on Windows/Linux, **Cmd+P** on Mac) to print on paper or save as a PDF file. The page is self-contained — it works offline and prints cleanly without extra browser chrome.

**Tip**: Save a PDF the night before a game so you have it available in the dugout without needing a connection.

---

## Spray Charts

Spray charts show where each batter hits the ball — ground balls, line drives, and fly balls plotted on a baseball field diagram. They're useful for defensive positioning: if a batter consistently pulls the ball or hits to the opposite field, the chart will show it clearly.

### Where Spray Charts Appear

Spray charts show up in three places:

**Player profile page** — Each player on your roster or a scouted opponent has a profile page. If we have ball-in-play data for that player, their spray chart appears inline on the page. The subtitle under the chart reads "Based on N balls in play" — that's how many batted balls went into the chart.

**Opponent detail page** — The opponent scouting page now includes a **Team Spray Chart** card showing the aggregate spray pattern for the entire opposing lineup. It gives you a quick read on the team's overall hit direction tendencies before diving into individual matchups.

The batting table on the opponent page also has a **View spray** link for each individual batter who has spray data. Tap the link to open that batter's spray chart.

**Opponent print page** — When you print a scouting report (or save it as a PDF), each batter's spray chart is included on the page. "Spray chart coming soon" placeholders no longer appear — if data exists, the chart prints; if not, the row shows "No spray chart data available."

### What "Based on N balls in play" Means

The subtitle under every chart tells you the sample size. A chart based on 3 balls in play is just three data points — don't over-weight it. A chart based on 20+ balls tells a more reliable story. Use spray charts as one input alongside your own scouting, not as a definitive answer.

### "No Spray Chart Data Available"

This message means the system doesn't have any batted-ball data for this player yet. It can happen because:

- The opponent's scorekeeper didn't record spray data in GameChanger (some scorekeepers track this, some don't)
- The player hasn't appeared at bat in any game we've scouted yet
- A scouting sync hasn't been run for this opponent — ask Jason to pull the latest data

If you see this message for a player you expect to face, let Jason know so he can check whether a sync is needed.

---

## Standalone Reports

The dashboard is the main tool for scouting scheduled opponents, but sometimes you need to share scouting information with someone who doesn't have dashboard access -- or scout a team that isn't on your schedule yet.

For those cases, Jason can generate a **standalone report**: a shareable link that opens a frozen scouting snapshot anyone can view, no login required.

See the full guide: [Standalone Reports](standalone-reports.md)

---

## Defensive Positioning Cards

When scouting data is available for an upcoming opponent, the system automatically generates **Defensive Positioning Cards** -- two printable artifacts that turn the opposing lineup's spray-chart tendencies into a concrete fielding plan.

- A **landscape call sheet**: one row per batter the system has data on, listing the call for each fielding position at a glance.
- Six **portrait player cards**: one card per covered position (Left Field, Center Field, Right Field, Third Base, Shortstop, Second Base). Each card is written for the player who stands at that position -- not the coach.

To access them, find the opponent's scouting page on the dashboard and look for the **Defensive Positioning** card. Tap it to open the full scouting report, which includes the call sheet and player cards alongside the regular pitching and batting sections. Print the report or save it as a PDF the night before the game.

### Reading the Call Sheet

The call sheet is organized as a table -- one row per batter -- sorted so the batters who need a positioning adjustment come first, then the rest in jersey-number order.

**Columns**:

| Column | What it shows |
|--------|-------------|
| **#** | Jersey number |
| **Name** | Batter's name |
| **CALL** | The single verbal call for this batter (see call words below) |
| **LF, CF, RF, 3B, SS, 2B** | Each position's specific call in compact form |
| **Confidence** | How much data underlies this call: BIP count, HR count, and a "thin" tag if under 10 balls in play |
| **Note** | Plain-English rationale for the call (when the LLM layer is enabled) |

**The CALL column** is what the coach yells during the game. There are 8 possible calls:

| Call word | What it means |
|-----------|-------------|
| **STRAIGHT UP** | No adjustment needed -- play your standard position |
| **SHADE LEFT** | Shift moderately toward left field |
| **SHADE LEFT SHALLOW** | Shift toward left field and move in slightly |
| **SHADE LEFT DEEP** | Shift toward left field and play deeper |
| **SHADE RIGHT** | Shift moderately toward right field |
| **SHADE RIGHT SHALLOW** | Shift toward right field and move in slightly |
| **SHADE RIGHT DEEP** | Shift toward right field and play deeper |
| **MIXED** | Each position gets a different call -- see the per-position columns |

**The per-position columns** (LF, CF, RF, 3B, SS, 2B) use compact symbols:

| Symbol | Meaning |
|--------|---------|
| `·` | Straight up (no adjustment) |
| `L` | Shade left |
| `L Sh` | Shade left shallow |
| `L Dp` | Shade left deep |
| `R` | Shade right |
| `R Sh` | Shade right shallow |
| `R Dp` | Shade right deep |

For most batters, the CALL column and all the per-position cells agree. The per-position columns matter most on **MIXED rows** (see below).

**The Confidence column** is intentional -- sample size matters. A batter with 8 balls in play is labeled **(8 BIP | thin)**. Treat thin-data calls as a gentle lean, not a strong signal. A batter with 25+ balls in play gives you a much more reliable picture.

### Reading the Player Cards

Each player card is written for one fielder at one position. The cards are portrait-orientation and print 6 to a sheet (one per covered position).

**Layout**:
- The top line says **STRAIGHT UP** -- the default for most batters. Most of the lineup gets no adjustment.
- Below that is a short **exceptions list** keyed by jersey number: jersey + name + the call word. For example:
  - `#23 Martinez — SHADE LEFT`
  - `#7 Okonkwo — SHADE RIGHT DEEP`
- At most 6 exception batters are listed per card. If more than 6 batters need an adjustment at this position, the top 6 by balls-in-play are shown, with a "+N more" note at the bottom.

**How to use them**: hand the SS card to the shortstop before the game. During the game, when the coach calls out a name or number, the fielder finds it in the list and moves to that call. If a name isn't on the exceptions list, the default is STRAIGHT UP.

### MIXED Rows

A batter is **MIXED** when the system's recommendation differs by position. For example, the short-stop might shade left for this batter while left field stays straight up. In that case:

- The CALL column shows **MIXED**.
- The per-position cells (LF, CF, RF, 3B, SS, 2B) each show their individual call.
- The player card for each position shows the position-specific call (e.g., the SS card shows `#23 SHADE LEFT DEEP`).

When the coach calls a MIXED batter's name, each fielder looks at their own card, not the call sheet. The coach may also call the jersey number instead of the name -- the player card shows both.

### Freshness and the "Through" Date

The dashboard link shows a line like **Through May 10** near the positioning card. This is the date the displayed report was generated -- not when the most recent scout run happened.

If a scout run completes successfully, a new report bundle is generated automatically and the date updates. If the auto-generate step fails (uncommon), the dashboard keeps showing the prior report until the next successful scout produces a new one. Ask Jason if the date seems significantly out of date before an important game.

### What the Cards Do Not Cover

- **Pitcher, catcher, and first base** are not included. Their positioning is driven by the game situation and their defensive role, not by an opposing batter's spray chart. v1 covers SS, 2B, 3B, LF, CF, RF only.
- **Batter handedness** is not shown. The calls are expressed as absolute field direction (LEFT/RIGHT) rather than pull/opposite because handedness information isn't available through the data source the system uses for scouting. The calls are still actionable -- "SHADE LEFT" means move toward left field regardless of whether the batter bats left or right.

---

## Reading Rate Stats

A quick reference for stats shown throughout the dashboard:

| Stat | Full Name | What to look for |
|------|-----------|-----------------|
| **OBP** | On-Base Percentage | How often they reach base. .350+ is strong at the high school level. |
| **ERA** | Earned Run Average | Runs allowed per 9 innings (pitching). Lower is better. |
| **K/9** | Strikeouts per 9 innings | Strikeout rate. Higher = more swing-and-miss stuff. |
| **BB/9** | Walks per 9 innings | Walk rate. Lower = better command. |
| **K/BB** | Strikeout-to-walk ratio | Combined control metric. "--" means zero walks (can't divide). |
| **SLG** | Slugging Percentage | Power hitting. .400+ signals a lineup with pop. |
| **GP** | Games Played | Sample size for all rate stats. |

---

*Last updated: 2026-05-15 | Story references: E-228 (defensive positioning cards section), E-163 (spray charts), E-153-03, E-153-04, E-159, E-183 (standalone reports), E-181-02 (game coverage indicator), E-181-03 (richer empty states, print page coverage indicator), E-196 (Rest and P (7d) pitching columns), E-212 (predicted starter section)*
