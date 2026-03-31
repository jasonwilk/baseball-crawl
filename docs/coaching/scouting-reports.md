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

**Team Batting Summary** — The opponent's team-wide tendencies for the season:
- OBP (on-base percentage), strikeout rate, walk rate, SLG (slugging)

Every rate stat shows the number of games it's based on (e.g., "2.10 ERA (8 GP)"). A stat based on 3 games means less than one based on 15 — keep sample size in mind.

**Full Pitching and Batting Tables** — Complete per-player breakdowns below the summary cards.

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

- **Page 1**: Report header, game coverage indicator ("Through [date] ([N] games)"), context bar (last meeting result and batting tendencies), and the full pitching table
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

*Last updated: 2026-03-31 | Story references: E-163 (spray charts), E-153-03, E-153-04, E-159, E-183 (standalone reports), E-181-02 (game coverage indicator), E-181-03 (richer empty states, print page coverage indicator)*
