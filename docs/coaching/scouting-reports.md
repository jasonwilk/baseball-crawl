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

## Defensive Positioning Bundle

When scouting data is available for an upcoming opponent, the system automatically generates a **Defensive Positioning Bundle** -- a four-page printable report that turns the opposing lineup's spray-chart data into a concrete fielding plan based on where this specific opponent's batted balls actually land.

To access it, find the opponent's scouting page on the dashboard and look for the **Defensive Positioning** card. Tap it to open the bundle. Print it or save it as a PDF the night before the game.

### What's in the Bundle

The bundle prints as four pages in two orientations:

| Page | What it is | Orientation |
|------|-----------|-------------|
| **Page 1** | Coach call sheet -- in-game reference, one row per batter | Landscape |
| **Page 2** | Coach prep page -- pre-game analysis, full-field overlay of all six positions | Landscape |
| **Page 3** | Player cards: Left Field / Center Field / Right Field / Third Base | Portrait, cut to four 4.25"x5.5" cards |
| **Page 4** | Player cards: Shortstop / Second Base / compass key / opponent context | Portrait, cut to four 4.25"x5.5" cards |

Cut the two portrait sheets along the printed midlines to produce eight cards. Give the six fielder cards (LF, CF, RF, 3B, SS, 2B) to your fielders before the game. Keep the compass key and opponent context cards for yourself.

### The Positioning Idea: Team Default and Outliers

Every card starts from a **team default** position -- a star symbol (★) on each card's field diagram. This is where the data says that fielder should stand against this specific opponent's overall hit distribution, not the textbook "straight up" position. The star moves for every opponent you face.

Most batters in the lineup are not outliers -- they hit the ball in roughly the average direction for this opponent. Fielders play their star position for those batters.

**Outlier batters** are individuals who consistently hit the ball in a noticeably different direction than the team default. They appear as numbered pills (jersey numbers) placed on the field diagram where that batter's contact tends to land. A pill in the upper-left of the diagram means that batter tends to go deep to left; a pill near the bottom means they hit it in (toward the infield).

The field also shows a faint textbook reference dot (○) -- the standard practice position -- so you can see at a glance how much the star shifts from baseline.

### The Compass Zone System

To make in-game calls fast, each position on the field is divided into eight zones labeled **A through H**. The zones are arranged around the star like compass directions:

| Zone | Direction | Depth |
|------|-----------|-------|
| A | Left | In |
| B | Left | (middle) |
| C | Left | Deep |
| D | (center) | In |
| E | (center) | Deep |
| F | Right | In |
| G | Right | (middle) |
| H | Right | Deep |

When a batter's contact tends to land in a zone, the system places their jersey number pill in that zone. The fielder sees the pill position on the field diagram and knows exactly where to shift.

All eight letters appear on every card at their fixed positions. Letters with outlier batters appear at full ink; unused letters are faint placeholders. This means fielders learn the zone layout once from the compass key card and recognize it on every card all season -- the letters are always in the same place, only the pills change.

The **legend line** at the bottom of each card reads: `★ default · ○ textbook · A-H outliers`

### Reading the Call Sheet (Page 1)

The call sheet is the coach's in-game lookup table. One row per batter in the system, sorted alphabetically by name. Columns:

| Column | What it shows |
|--------|-------------|
| **#** | Jersey number (shown prominently for fast jersey-lookup) |
| **Name** | Batter's name |
| **LF, CF, RF, 3B, SS, 2B** | Zone letter (A--H) if this batter is an outlier at that position, or a center dot (·) if they play the team default there |
| **Note** | Plain-English reasoning for flagged batters (when AI analysis is enabled) |

A center dot (·) in every cell means "play your star position for this batter." A zone letter in a cell means "shift to zone X at that position."

**Example call**: You're coaching a game. Batter #14 comes up. You scan the call sheet -- the LF cell shows **C** and the other cells show dots. You tell your left fielder "fourteen -- Zone C." They move to the deep-left area of the field.

**Legend at the top of the sheet**: `A in-left · B left · C deep-left · D in · E deep · F in-right · G right · H deep-right · · = team default`

### Reading the Prep Page (Page 2)

The prep page is your pre-game analysis canvas. All six position stars appear on one large field diagram, with all outlier pills from all positions overlaid. Use it before the game to see the full picture of where this opponent hits the ball and whether multiple fielders are affected by the same batter.

The sidebar on the prep page shows the same jersey × zone grid as the call sheet but with a different sort: outlier batters come first (alphabetical within the group), then non-outlier batters below a divider. This groups the players who need attention at the top when you're doing pre-game prep -- unlike the call sheet, which keeps alphabetical order for fast in-game lookup.

### Reading the Player Cards (Pages 3 and 4)

Each fielder carries their own card. The card for their position shows:

- **Header**: opponent name, position name, and data coverage ("Through Mon Day (N games)")
- **Field diagram**: the star (★) for this position, a faint textbook dot (○), the 8 compass zone letters, and numbered pills for any outlier batters
- **Sidebar**: a compact table listing each outlier batter's jersey number and zone letter for this position
- **Legend**: `★ default · ○ textbook · A-H outliers`

If there are no outlier batters for this position, the sidebar reads "No outliers this opponent" and the fielder plays the star position for all batters.

**How to hand out cards**: give the LF card to the left fielder, the SS card to the shortstop, and so on. Before the game, each fielder finds their star position on their own field diagram and notes which jersey numbers have pills -- those are the batters they need to shift for. When you make a call, the fielder checks their pill, sees what zone it's in, and moves there.

### Data Coverage and Confidence

Each artifact shows a coverage line -- "Through Mon Day (N games)" -- which tells you how many of this opponent's games the positioning is based on. The system uses three confidence levels based on total balls in play for this opponent:

| Coverage | What you see | What it means |
|----------|-------------|--------------|
| **Full** (50+ balls in play) | Star at full opacity, small BIP count label, density background visible | Strong positioning signal -- use with confidence |
| **Thin** (15-49 balls in play) | Star with a thin-data badge, outliers shown normally | Early-season data -- useful lean but some noise |
| **Zero** (fewer than 15 balls in play) | "Not enough spray data -- play your standard alignment" message instead of a diagram | Cannot generate a reliable recommendation yet |

The coverage shown on the bundle is locked at the moment Jason generates the report. If you open the bundle a day later, the "Through" date still reflects the data that was in the system when it was printed -- the coverage line does not update automatically. Ask Jason to regenerate the bundle if you want the latest data before an important game.

### The Compass Key Card (Page 4, Slot 3)

The third card on the second print sheet is a compass key -- a blank field diagram showing all eight zones labeled with A through H and the in/deep/left/right axes annotated. Keep this card yourself or post it in the dugout. Fielders can use it to learn the zone vocabulary during the first few games; after a few uses the layout becomes automatic.

### The Opponent Context Card (Page 4, Slot 4)

The fourth card on the second print sheet shows this opponent's team-level numbers:

- Opponent name and coverage cue
- Win-loss record
- Runs per game (offensive output) and runs allowed per game (pitching/defense)
- Total balls in play in our scouting data and the confidence tier (Full / Thin / Zero)

This card gives you the quick team-context frame before you look at individual batters.

### Freshness and the "Through" Date

The dashboard card shows a line like **Through May 10 (8 games)** near the positioning link. This tells you how current the data behind the bundle is. The system regenerates the bundle automatically each time a scouting sync runs, so the date advances as new games are scouted.

If the auto-generate step fails after a sync (uncommon), the dashboard shows the prior bundle until the next successful sync. Ask Jason if the date looks significantly stale before an important game.

### What the Bundle Does Not Cover

- **Pitcher, catcher, and first base** are not included. Their positioning is situation-driven, not spray-chart-driven. The bundle covers SS, 2B, 3B, LF, CF, and RF only.
- **Batter handedness** is not shown on the cards. The system does not have handedness data from the scouting source it uses for opponents. The zone letters are expressed as absolute field direction -- Zone B means "toward left field" regardless of whether the batter hits left or right. The spray data itself captures the actual direction of each batter's contact, so the call is still meaningful without knowing handedness explicitly.

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

*Last updated: 2026-05-18 | Source: E-229 (defensive positioning bundle -- compass zones, 4-page bundle, call sheet, prep page, player cards, compass key, opponent context card, coverage tiers), E-228 (positioning bundle architecture, freshness cue), E-163 (spray charts), E-153-03, E-153-04, E-159, E-183 (standalone reports), E-181-02 (game coverage indicator), E-181-03 (richer empty states, print page coverage indicator), E-196 (Rest and P (7d) pitching columns), E-212 (predicted starter section)*
