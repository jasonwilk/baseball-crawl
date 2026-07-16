# Reading the Outings Breakdown

The **Outings Breakdown** section of a scouting report shows each opposing pitcher's outing-by-outing history for the season -- not just his season totals, but how he did in every appearance he's made. It answers a question the season stat line alone can't: "was he sharp *last time out*, or is his season line propped up by one big game weeks ago?"

---

## How the Section Is Organized

Each pitcher gets his own collapsible entry. Tap or click a pitcher's name to expand his outing log.

At the top of each pitcher's entry is a **season summary line** -- his full-season numbers. Below that is a **game-by-game table**, one row per appearance, in chronological order (oldest first).

A small dot next to a pitcher's name means at least one of his outings this season was strong enough to be highlighted green (see below) -- a quick way to spot which arms on the staff have a "watch out for this guy" outing in their recent history without opening every entry.

---

## The Season Summary Line

The season line gives you the same context you'd expect (innings pitched, games/starts, ERA, WHIP, first-pitch strike rate), plus four rate stats built specifically for this section:

- **K/BF** -- strikeouts per batter faced. How often he simply misses bats.
- **BB/INN** -- walks per inning. How often he gives away a free baserunner.
- **K/BB** -- strikeouts per walk. The single best "is this guy in control" number.
- **H/BF** -- hits allowed per batter faced. How often he gets hit when the ball's in play.

**Why these four instead of the K/9 and ERA/WHIP you already see elsewhere on the report?** Because K/BF and H/BF split apart two things WHIP lumps together. WHIP treats a walk and a hit the same -- both are "a runner on base." But a pitcher who gives up a lot of hits and a pitcher who gives up a lot of walks are different problems that call for different game plans: attack a hit-hard arm early before he finds the zone; be patient against a walk-prone one and make him throw strikes. Looking at H/BF next to BB/INN tells you which one you're facing. K/BF and K/BB round out the picture by telling you whether he can miss bats at all.

**Small-sample flags on the season line:**
- If the pitcher has thrown fewer than 15 innings this season, his innings figure is flagged -- treat the whole rate line as an early read, not a settled scouting book.
- If K/BB shows a walk count next to it (e.g., "3.0 K/BB · 4 BB"), that's a reminder the ratio is built on very few walks and can swing with one more free pass.
- A pitcher who hasn't walked anyone yet shows a **"0 BB"** badge instead of a K/BB number. That's not missing data -- it's the system telling you a zero-walk performance *is* the notable fact. Read it as a strength (elite command), not a gap.

---

## The Game-by-Game Table

Each row is one outing: `Date | Opp | IP | BF | H | HR | BB | K | R | FPS% | ERA`.

These are raw counts for that single appearance -- not rates. A single outing is too small a sample to turn into a percentage that means anything (a 1-inning relief stint with 1 walk would show a nonsense 100% "walk rate" if it were converted). Read them as what actually happened that day: how many innings, how many men on, how many runs.

The **ERA** column on each row is that outing's ERA on the same game-length basis used elsewhere in the report -- the league's actual game length (usually 7 innings for high school, occasionally shorter for some youth divisions) -- so you can compare one outing's ERA to another's, or to his season ERA, apples to apples.

---

## Reading the Green Highlighting

Some rows are shaded green. A green row means: **this was a strong outing -- respect it, don't get cute against this arm if he's on the mound again.**

A row turns green if the pitcher did any ONE of the following in that outing:

- **Threw strikes** -- didn't walk a single batter across a real workload (at least 3 innings).
- **Got ahead early** -- threw a first-pitch strike at least 65% of the time, across enough charted at-bats to trust it.
- **Missed bats** -- struck out at least two-thirds of the batters he faced, across a real workload.
- **Shut the door** -- didn't allow a run, across a longer outing (at least 4 innings).

Only one of these needs to be true for a row to go green -- it's a "was this arm dealing" flag, not a combined score.

**Rows without color are not a red flag.** There's no red or "exploit this" highlighting in this section -- only green. An outing that's too short or too small a sample to judge one way or the other is simply shown plain, with no color. Plain does not mean weak; it means there wasn't enough in that outing to call it a standout performance either way.

---

## What's Computed From Play-by-Play vs. the Official Box Score

Most of the table -- IP, BF, H, BB, K, R -- comes straight from GameChanger's official box score, the same numbers you'd see if you opened the game yourself.

Two columns are different: **FPS%** and **HR** (home runs allowed) are computed from the pitch-by-pitch play data we collect, not from GameChanger's official boxscore totals. The report notes this above the section.

**What that means in practice:** these two numbers are a very reliable directional read -- roughly 90-95% accurate at the pitcher level, typically within a batter or two per outing -- but they're not guaranteed to match an official box score number exactly, because occasionally a play gets attributed to the wrong pitcher in a multi-pitcher game. Use FPS% and HR the way you'd use any good scouting note: trust the pattern (this guy consistently gets ahead in counts; this guy has given up a couple of homers this year), but don't treat a single outing's FPS% or HR count as gospel if it looks surprising.

---

*Last updated: 2026-07-16 | Source: E-265 (Pitcher Outings Breakdown), E-265-04 (this how-to)*
