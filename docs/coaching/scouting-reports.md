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

### What You'll See

**Pitching** — Top three pitchers by innings pitched this season. For each pitcher:
- ERA, K/9 (strikeouts per 9 innings), BB/9 (walks per 9 innings)
- K/BB ratio — a higher number means they pound the zone; a lower number means they struggle with control
- Games pitched this season
- Handedness (L/R) when available

**Team Batting Summary** — The opponent's team-wide tendencies for the season:
- OBP (on-base percentage), strikeout rate, walk rate, SLG (slugging)

Every rate stat shows the number of games it's based on (e.g., "2.10 ERA (8 GP)"). A stat based on 3 games means less than one based on 15 — keep sample size in mind.

**Team Spray Chart** — After the batting summary card, a field diagram shows where this opponent's entire lineup tends to put the ball when they make contact. Green dots are hits; red dots are outs. This chart covers only games where our teams played them — you'll see a label telling you exactly how many balls in play the chart is based on.

**Full Pitching and Batting Tables** — Complete per-player breakdowns below the summary cards. Players with enough individual spray data show a **"View spray →"** link next to their name. Tap it to open that player's personal spray chart in a new tab — useful for positioning your outfield against a specific hitter before the game.

A note above the batting table tells you the minimum: only players with 10 or more balls in play show a spray link.

---

## Three Scouting States

Not every opponent will have full data. The page handles three situations:

| State | What you see | What it means |
|-------|-------------|--------------|
| **Full stats** | All sections populated | We've run a scouting sync and have season stats loaded |
| **Linked, not scouted** | Yellow notice: "This team is linked but stats haven't been loaded yet" | The opponent is in the system but the sync hasn't run yet — ask Jason to trigger a scouting sync |
| **Not linked** | Yellow notice: "Stats not available. This opponent hasn't been linked to a GameChanger team yet." | The opponent hasn't been connected to GameChanger yet — Jason handles this in the admin panel |

If you tap an upcoming opponent and see a yellow notice, ask Jason to pull the data before game day.

---

## Spray Charts

Spray charts show where a player puts the ball when they make contact — a visual map of a hitter's tendencies on a baseball diamond.

### How to Read a Spray Chart

Each dot on the field represents one ball in play:
- **Green dot** — the batter got a hit on that play
- **Red dot** — the batter was out on that play

Home run zones appear as numbered circles along the outfield arc: left field, center field, and right field.

The more dots cluster in a spot, the more consistently this hitter goes to that area. A hitter who pulls everything will have most dots on the left side of the field (for a right-handed batter). A hitter who sprays it around will have dots spread across the whole field.

### Where You'll Find Spray Charts

**Player profile page** — Each player's profile page includes a "Spray Chart" card showing their season ball-in-play distribution. The heading tells you how many balls in play the chart is based on (e.g., "Based on 34 balls in play").

**Opponent scouting page** — The opponent scouting page shows two types of spray data:
1. A **Team Spray Chart** card showing where the opponent's entire lineup collectively puts the ball against our teams.
2. **"View spray →" links** in the batting table for individual opponent players with enough data.

### What the Messages Mean

Not every player will have a chart. When there's not enough data, you'll see one of these messages instead:

| Message | What it means |
|---------|--------------|
| "Based on N balls in play" | Enough data — the chart is shown. |
| "Small sample — N balls in play" | Some data exists (5-9 for a player, 10-19 for a team), but not enough to draw reliable conclusions. No chart shown. |
| "Not enough data yet — N balls in play recorded" | Very few balls in play on file. |
| "Charts will appear after the next sync" | No spray data has been crawled yet. Ask Jason to run a sync. |

**Why are the thresholds different for players vs. teams?**

Individual player charts need at least 10 balls in play before they're displayed. Team aggregate charts need at least 20. A single full game against an opponent typically produces 20-30 team balls in play, so the team chart fills in faster. Per-player charts take more games against the same opponent to reach 10 BIP for each hitter.

### "Against Our Teams" — What That Means

Spray data on the opponent scouting page comes only from games where our teams actually faced that opponent. It does not include games the opponent played against other schools.

This is important context: if we've only played an opponent once, the spray chart reflects one game. The "Based on N balls in play" label always tells you exactly how much data is behind the chart.

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

*Last updated: 2026-03-26 | Story references: E-158 (spray charts), E-153-03, E-153-04*
