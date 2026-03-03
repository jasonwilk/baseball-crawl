# Understanding the Stats

This guide explains the statistics the LSB analytics system tracks. Each stat includes what it measures, how it is calculated, and what the numbers mean in practice. If you understand baseball but have not spent much time with advanced stats, this is for you.

---

## Batting Statistics

### OBP -- On-Base Percentage

**What it measures:** How often a batter reaches base, for any reason.

**The formula:** (Hits + Walks + Hit-by-Pitch) divided by (At-Bats + Walks + Hit-by-Pitch + Sacrifice Flies)

**What the numbers mean:**
- .400 or above is excellent at the high school level
- .350 means the batter reaches base about 1 in 3 plate appearances
- .300 is roughly average for a solid high school hitter
- Below .280 is a sign the batter is struggling to get on base

**Why it matters:** OBP is the single most important offensive stat. Getting on base creates scoring opportunities. A player who walks a lot but does not hit for power is still valuable because he is on base. When setting a lineup, your best OBP guys belong at the top.

**Example:** Marcus Rivera has a .380 OBP through 60 plate appearances. That means he is reaching base nearly 4 out of every 10 times he comes to the plate -- a strong option for the top of the order.

---

### SLG -- Slugging Percentage

**What it measures:** A batter's power, weighted by how far he gets on each hit.

**The formula:** Total bases divided by At-Bats. A single = 1 base, double = 2, triple = 3, home run = 4.

**What the numbers mean:**
- .500 or above is strong power for high school
- .400 is solid
- Below .300 suggests the batter is mostly hitting singles or not hitting much at all

**Why it matters:** SLG tells you who is driving the ball. A player with a high SLG hits for extra bases, which means runs score faster. Your middle-of-the-order hitters (3-4-5 spots) should be your best sluggers.

**Example:** Devon Jackson has a .475 SLG. He is hitting a lot of doubles and the occasional home run -- a good fit for the 3 or 4 hole.

---

### K% -- Strikeout Rate

**What it measures:** How often a batter strikes out, as a percentage of plate appearances.

**The formula:** Strikeouts divided by Plate Appearances, expressed as a percentage.

**What the numbers mean:**
- Below 15% is very good contact ability
- 15-20% is about average for high school
- Above 25% means the batter is striking out too much

**Why it matters:** A batter who strikes out a lot puts nothing in play -- no chance for an error, no advancing a runner, no productive out. High K% batters become a bigger problem in late-game situations when you need contact.

**Example:** Tyler Whitehawk has a 28% K% -- he strikes out about once every four plate appearances. Consider him for situations where a strikeout is less costly, and work with him on pitch recognition in practice.

---

### BB% -- Walk Rate

**What it measures:** How often a batter draws a walk, as a percentage of plate appearances.

**The formula:** Walks divided by Plate Appearances, expressed as a percentage.

**What the numbers mean:**
- Above 12% is excellent discipline
- 8-12% is solid
- Below 5% means the hitter is swinging at too many pitches outside the zone

**Why it matters:** Walks put runners on base without risking an out. A high walk rate signals a patient hitter who sees pitches well. These batters tend to raise pitch counts on opposing pitchers, which helps your whole lineup later in the game.

**Example:** Marcus Rivera has a 14% BB% -- he draws a walk about 1 in 7 plate appearances. That patience is another reason he works well at the top of the lineup.

---

### BABIP -- Batting Average on Balls in Play

**What it measures:** How often a batter gets a hit when he puts the ball in play (excludes home runs, strikeouts, and walks).

**The formula:** (Hits minus Home Runs) divided by (At-Bats minus Strikeouts minus Home Runs plus Sacrifice Flies)

**What the numbers mean:**
- The league average is typically around .300
- Well above .350 may mean the batter is getting lucky -- expect some regression
- Well below .250 may mean the batter is getting unlucky -- he might improve without changing anything

**Why it matters:** BABIP helps you figure out whether a hot or cold streak is real. A batter with a very high BABIP may be due for a slump even though his overall numbers look great right now. A batter with a very low BABIP might be hitting the ball hard and just getting unlucky.

**Important caveat:** BABIP is the stat most affected by small sample sizes. Do not read too much into it until a batter has at least 50-60 plate appearances. Even then, treat it as a clue, not a verdict.

**Example:** Sam Easley is hitting .190 but his BABIP is .180 -- well below what you would expect. He might be hitting the ball hard right at defenders. Watch his at-bats before benching him; his numbers may bounce back on their own.

---

## Pitching Statistics

### K/9 -- Strikeouts per Nine Innings

**What it measures:** How many batters a pitcher strikes out, scaled to a nine-inning game.

**The formula:** (Strikeouts divided by Innings Pitched) multiplied by 9.

**What the numbers mean:**
- Above 9.0 is a dominant strikeout pitcher at the high school level
- 6.0-9.0 is solid
- Below 5.0 means the pitcher is relying on his defense, not missing bats

**Why it matters:** Strikeouts are the most reliable way to get outs because the defense is not involved. A high-K pitcher controls his own results. When you need a big out in a tough spot, you want the guy who can miss bats.

**Example:** Jake Morningstar has a K/9 of 8.5 through 28 innings. He is striking out close to a batter per inning -- a strong option when you need strikeouts.

---

### BB/9 -- Walks per Nine Innings

**What it measures:** How many batters a pitcher walks, scaled to a nine-inning game.

**The formula:** (Walks divided by Innings Pitched) multiplied by 9.

**What the numbers mean:**
- Below 2.5 is excellent command
- 2.5-4.0 is average for high school
- Above 5.0 is a control problem -- free baserunners add up fast

**Why it matters:** Walks are free baserunners. A pitcher with a high BB/9 is putting runners on base without the other team having to earn it. In high school, walks often lead to runs because baserunning mistakes and passed balls turn one walk into a rally.

**Example:** Chris Runningelk has a BB/9 of 5.8 through 22 innings. That means he is walking more than a batter every two innings. He may need shorter outings or work on throwing strikes before he can handle longer starts.

---

### K/BB Ratio -- Strikeout-to-Walk Ratio

**What it measures:** The balance between a pitcher's ability to miss bats and his ability to throw strikes.

**The formula:** Strikeouts divided by Walks.

**What the numbers mean:**
- Above 3.0 is excellent -- the pitcher strikes out three batters for every one he walks
- 2.0-3.0 is solid
- Below 1.5 is a concern -- the pitcher does not have enough strikeout ability to make up for his walks

**Why it matters:** K/BB is one of the best single numbers for evaluating a pitcher overall. It tells you whether the pitcher is in control. A guy with a 1.0 K/BB is walking as many as he strikes out -- that is a recipe for high pitch counts and short outings.

**Example:** Jake Morningstar has a K/BB of 3.2. For every batter he walks, he strikes out more than three. That is a pitcher you can trust in pressure situations.

---

### FIP -- Fielding Independent Pitching

**What it measures:** What a pitcher's earned run average "should" be based only on the things he controls: strikeouts, walks, hit batters, and home runs.

**The formula:** ((13 x Home Runs) + (3 x Walks) - (2 x Strikeouts)) divided by Innings Pitched, plus a league constant (usually around 3.10).

**What the numbers mean:**
- Below 3.00 is elite
- 3.00-4.00 is solid
- Above 5.00 suggests the pitcher is getting hit hard or walking too many

**Why it matters:** Sometimes a pitcher has a low earned run average because his defense is making great plays behind him. Sometimes a pitcher has a high earned run average because his defense is letting him down. FIP strips out the defense and tells you how well the pitcher himself is actually performing.

**Important caveat:** FIP only works well with a reasonable number of innings. With fewer than 15 innings pitched, the numbers can swing wildly based on one bad outing.

**Example:** A pitcher with a 2.80 earned run average but a 4.10 FIP may be getting bailed out by strong defense. If the defense behind him changes (like when JV players sub in), expect worse results.

---

## When to Trust the Numbers -- Sample Size Warnings

High school baseball has short seasons and small rosters. A 30-game season means a batter might only get 80-100 plate appearances all year. When you split those numbers by situation -- home vs. away, lefty vs. righty -- the sample gets even smaller.

Here is when to trust the stats and when to take them with a grain of salt:

### Batting Stats

| Plate Appearances | How Reliable? |
|---|---|
| Fewer than 20 PA | **Do not rely on these numbers.** One hot or cold week can make the stats look wildly different than reality. Use the eye test instead. |
| 20-50 PA | **Emerging picture.** You can start to see tendencies, but expect the numbers to move. Use them alongside what you see in practice and games. |
| 50-80 PA | **Reasonably trustworthy.** The stats are starting to stabilize. Good enough for lineup decisions and scouting reports. |
| 80+ PA | **Solid.** This is a meaningful sample for high school. Trust these numbers for decisions. |

### Pitching Stats

| Innings Pitched | How Reliable? |
|---|---|
| Fewer than 15 IP | **Do not rely on these numbers.** One bad start can wreck or inflate every stat. Watch the pitcher; do not let the numbers override what you see. |
| 15-30 IP | **Emerging picture.** You can see patterns forming, but the numbers can still shift significantly. |
| 30-50 IP | **Reasonably trustworthy.** Enough innings for the stats to reflect real ability. Suitable for scouting reports and matchup planning. |
| 50+ IP | **Solid.** Unusual to see at the high school level except for a team's ace. Very reliable. |

### Splits (Home/Away, Left/Right)

Splits cut your already-small sample in half -- or worse. A batter with 80 plate appearances on the season might only have 15-20 at-bats against left-handers. That is not enough to draw conclusions.

**Rule of thumb:** Do not make lineup decisions based on a split unless the player has at least 20 plate appearances in that split. If the sample is smaller, note the tendency but do not overreact.

---

## What Are Splits?

Splits break down a player's stats by specific situations. The two most useful splits for game prep are:

### Home/Away Splits

**What they show:** How a player performs at home versus on the road.

**Why they matter:** Some players hit better at home (comfort, familiarity, crowd support). Some pitchers are sharper on the road. If you are playing an away game and your opponent's best hitter has much worse numbers on the road, that is useful to know.

**When to use them:** Primarily for scouting opponents. If you notice an opposing batter has a .420 OBP at home but .280 on the road (with enough plate appearances to trust), you know he may be less dangerous when you host him.

### Left/Right Splits (Platoon Splits)

**What they show:** How a batter performs against left-handed pitchers versus right-handed pitchers, or how a pitcher performs against left-handed batters versus right-handed batters.

**Why they matter:** Most hitters have an advantage against opposite-handed pitchers (a right-handed batter facing a lefty). If your opponent has a dangerous left-handed hitter, knowing whether you have a lefty or righty who neutralizes him matters for your pitching decisions.

**When to use them:** For pitching matchups and lineup construction. If the opposing team stacks left-handed hitters, you might want your right-handed pitcher on the mound. If a specific opposing batter struggles against lefties, that changes your bullpen strategy.

**Sample size reminder:** Splits cut the data in half. A batter with 80 plate appearances on the season may only have 25 against lefties. The numbers are useful as a guide, but do not treat a 25 plate-appearance split like gospel.

---

*Last updated: 2026-03-03 | Story reference: E-028-04*
