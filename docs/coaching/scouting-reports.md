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

**Full Pitching and Batting Tables** — Complete per-player breakdowns below the summary cards.

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

## Printing a Scouting Report

When full stats are loaded for an opponent, a **Print / Save as PDF** link appears at the top of their scouting page. Tap it to open a print-ready version of the report.

The print view is formatted for a standard landscape page:

- **Page 1**: Report header, context bar (last meeting result and batting tendencies), and the full pitching table
- **Page 2+**: Full batting table and batter tendencies charts

From the print view, use your browser's print command (**Ctrl+P** on Windows/Linux, **Cmd+P** on Mac) to print on paper or save as a PDF file. The page is self-contained — it works offline and prints cleanly without extra browser chrome.

**Tip**: Save a PDF the night before a game so you have it available in the dugout without needing a connection.

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

*Last updated: 2026-03-26 | Story references: E-153-03, E-153-04, E-159*
