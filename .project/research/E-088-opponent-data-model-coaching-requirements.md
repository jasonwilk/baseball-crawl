# E-088: Opponent Data Model -- Coaching Requirements
**Date**: 2026-03-09
**Author**: baseball-coach agent
**Question answered**: What does the opponent data model need to support real pre-game scouting decisions? How should link states, unlinked opponents, multi-season continuity, and crawl priority be handled from a coaching perspective?

---

## 1. What Opponent Data Matters Most for Pre-Game Scouting

Ranked from highest to lowest coaching value, with priority labels.

### Tier 1 -- The Three Things a Coach Needs Before Every Game
See section 3 (Minimum Viable Profile) for details. These are always required.

### Tier 2 -- MUST HAVE for Game Prep
1. **Season batting stats for the opposing lineup** (OBP, K%, BB%, AVG at minimum): The core of pre-game scouting. Tells your pitching staff which hitters are dangerous, who will chase, and who will work counts. *Sample size caveat: present with PA count. An opponent with 8 games played may have small-sample stats; flag accordingly.*
2. **Pitching rotation and recent outings**: Who is their ace? Who pitched last game (cannot pitch today)? What are the projected starters' K/BB ratios and pitch count histories? This is the single most actionable pre-game decision input -- who do we expect to face?
3. **Recent game results (last 3-5 games)**: Win/loss, run totals, and margins. Are they on a hot streak? Did they just get mercy-ruled twice? A team that lost 14-0 yesterday may have emotional and physical factors in play. *This is why the public games endpoint is so valuable -- recent form, zero auth cost.*

### Tier 3 -- SHOULD HAVE for Full Scouting
4. **Roster and lineup tendencies**: Who bats leadoff vs. cleanup? Does the coach change the order against lefties? Knowing their lineup construction tells you who to pitch around and who to challenge.
5. **Win/loss record with competition context**: A 12-2 record matters more if their opponents were competitive. A 12-2 record against all recreational teams tells a different story. Competition level must accompany the record.
6. **Head-to-head history**: If we have played this team before, what happened? Not just wins/losses but margin, which pitchers faced each other, who got hot. This has outsized value in conference schedules where you face the same team 4+ times per season.

### Tier 4 -- NICE TO HAVE for Deep Scouting
7. **Per-player recent form (last 3 games)**: Who is hot right now? This requires per-game player stats and is worth having when available, but not a blocker for basic scouting.
8. **Baserunning tendencies**: Stolen base frequency, caught stealing rate. Tells your catcher and pitcher whether they need to hold runners.
9. **Inning-by-inning scoring patterns**: Do they come out swinging in the first inning? Do they mount late-inning comebacks? Informs bullpen management and in-game strategy.

### What to De-Prioritize
- **Fielding metrics**: Error rates are interesting but rarely actionable in a single game plan. Nice to know if their shortstop has 12 errors, but it does not change your offensive approach.
- **BABIP and batted ball type splits**: These require large samples and involve too much luck variance to be reliable at the high school level. Track them later.
- **Home/away splits for the opponent**: Useful at the MLB level; at high school the sample sizes (10-15 games per side at most) are too thin to act on.

---

## 2. Presenting Unlinked Opponents to Coaches

Unlinked opponents -- the 14% with no `progenitor_team_id` -- are not useless. They just require a different presentation.

### What We Have for Unlinked Opponents
When we played an unlinked opponent, our scorekeeper recorded:
- Our team's performance in that game (our box score)
- The final score
- The game date, location, and result
- Possibly some opponent player names from the box score (if the scorekeeper entered them)

This is our-side-of-the-story data. It tells coaches how WE performed against this opponent, not how the opponent performs generally.

### How to Present Unlinked Opponents -- MUST HAVE
Display a clear, prominent data quality indicator at the top of every opponent profile. Not a tiny footnote -- a visible status badge:

- **"Full scouting data"**: Linked, real GC team data available. Season stats, roster, recent games.
- **"Partial scouting data -- our games only"**: Unlinked. We have what our scorekeeper recorded from games we played. No opponent season stats.
- **"No data"**: We have never played this team and they are not linked. Placeholder only.

### The Coaching Mental Model for Unlinked Opponents
A coach looking at an unlinked opponent should see:
1. The badge: "Partial scouting data -- our games only"
2. A brief explanation: "This team isn't in GameChanger's database. The stats below are from games we played against them -- our scorekeeper's records only."
3. Our game results against them (if any): Score, date, our pitchers, our hitters' lines
4. A prompt to the operator (Jason): "Want to link this team? Search by name or paste their GameChanger URL."

This is not embarrassing -- it is honest. A coach would rather see "we don't have full data on this team" than see stale or misleading partial stats presented as if they were complete.

### SHOULD HAVE: Head-to-Head Data is Still Valuable for Unlinked Opponents
Even without season stats, knowing how OUR team performed against THIS opponent has real value. If we've played them 3 times and won all three with our ace, or lost all three and their pitcher struck out 8 of our batters, that's actionable intel. The data model should store our games against unlinked opponents and present that head-to-head history clearly.

---

## 3. Minimum Viable Opponent Profile -- The Three Things

If we can only show coaches three things, make them:

**1. Who Pitches for Them Today (MUST HAVE)**
Specifically: the likely starting pitcher's name, their season K/BB ratio, and their pitch count from their last outing (to determine rest and availability). If we don't know who starts, show the top 2-3 pitchers by innings pitched with their basic lines.

*Sample size caveat: Always show innings pitched alongside any rate stat. "K/BB: 2.8 in 12 IP (small sample)" is far more useful than "K/BB: 2.8."*

*Why this is #1*: The entire offensive game plan changes based on the starting pitcher. Against a high-K arm, you want contact hitters in the order and you accept more strikeouts from your power guys. Against a high-BB pitcher, you want OBP guys at the top to draw walks and create baserunners for your RBI guys. You cannot set the lineup without knowing who's on the mound.

**2. Their Win/Loss Record with Recent Form (MUST HAVE)**
Specifically: overall record, competition level, and results from their last 3-5 games with scores.

*Why this is #2*: It sets expectations. Walking into a game against a 14-1 team requires a different mental approach than facing a 3-12 team. Recent form tells you whether they're peaking or slumping. A team that just lost three in a row by 10+ runs may have depth issues. A team that just won five straight is playing with confidence.

**3. Their Top 2-3 Hitters by OBP (MUST HAVE)**
Specifically: the batters with the highest OBP, their typical lineup slot, and their K% (do they put the ball in play or swing and miss?).

*Sample size caveat: Show PA count. "OBP .450 in 35 PA" vs. "OBP .450 in 8 PA" are completely different signals.*

*Why this is #3*: Your pitcher needs to know who in the opposing lineup will be the hardest outs. The #3 and #4 hitters are usually the most dangerous, but a leadoff guy with a .480 OBP is a special problem -- he's going to be on base all day. This single piece of information changes how your pitcher attacks the bottom of the lineup (knowing the dangerous guys will be coming up again in the 3rd) and how your manager might pitch around certain batters.

---

## 4. Manual Association Workflow -- The Coach's Mental Model

This addresses how Jason (the operator) should be able to manually link an unlinked opponent to a real GC team.

### How an Operator Thinks About This
Jason is not thinking about `progenitor_team_id` values. He is thinking: "We're playing Lincoln Eagles next week and I need scouting data. How do I connect them to their real GameChanger page?"

He will try the most natural thing first: **search by name**. "Lincoln Eagles." If there are 4 teams with similar names in the database, he needs enough context to pick the right one (city/state, competition level, a couple of their recent opponents he recognizes).

### Recommended Workflow Priority -- MUST HAVE: Search by Name First
The primary manual association flow should be:
1. Operator sees an unlinked opponent with the "Partial data" badge
2. An action button: "Link to GameChanger team"
3. A search field: "Search by team name"
4. Results show: team name, city/state, competition level, win/loss record, and 2-3 opponent names from their recent schedule (so Jason can confirm it's the right team -- "yeah, I recognize Lincoln Academy and Burlington Heights as teams they'd play")
5. Operator selects the match, confirming the link

### SHOULD HAVE: URL Paste as a Power-User Path
Some operators (Jason is technically savvy) will know they can get the team's GameChanger URL directly. Support paste: "Or paste a GameChanger team URL." This is faster for someone who already has the URL open in a browser tab.

### NICE TO HAVE: Browse Recent Shared Opponents
"Teams that played both you and this opponent" -- if both teams played the same third team, that's a strong signal they are in the same competition tier and likely the same region. This is a helpful disambiguation when there are multiple "Lincoln Eagles" in the search results.

### What the Operator Should NOT Have to Do
- Manually enter `progenitor_team_id` UUIDs. Never expose raw API IDs in the UI.
- Browse a full database of all GC teams. The search result list should be scoped to plausible matches (same state, similar competition level).
- Re-confirm the link every season. Once linked, the association should persist across seasons unless the operator breaks it.

---

## 5. Multi-Season Continuity -- Same Program, Different Roster

This is a genuine data modeling tension that needs to be resolved at the schema level.

### The Core Problem
"Lincoln Eagles 14U" in 2025 has completely different players than "Lincoln Eagles 14U" in 2026. But:
- The coaching staff may be the same (or mostly the same)
- The coaching tendencies and game strategies persist even when the roster turns over
- For scouting purposes, a coach facing Lincoln Eagles wants to know about both "what this PROGRAM does" and "what this SPECIFIC TEAM does right now"

### Recommendation: Same Team Entity, Separate Season Stats -- MUST HAVE
The team entity (the program -- "Lincoln Eagles 14U") should persist across seasons. What changes per season is the roster, the stats, and the record. The data model should distinguish:

- **Team entity**: Name, city/state, competition level, GC team UUID. This persists.
- **Team season**: Linked to the team entity + a season year. Contains the win/loss record, season stats, roster for that year.
- **Head-to-head history**: Stored as games between teams, linked via team entity + season. This lets a coach see "we've played Lincoln Eagles 4 times across 2 seasons."

### What Coaches Actually Want
- "What is Lincoln Eagles doing THIS season?" -- current season stats, current roster, recent games
- "What have we seen from Lincoln Eagles historically?" -- head-to-head games, our performance vs. them over time
- "Who is their ace this year vs. last year?" -- same program, roster comparison across seasons

The data model must support both "current season view" (default) and "multi-season historical view" (available for programs we've faced repeatedly). The scouting report defaults to current season but surfaces historical context if available.

### SHOULD HAVE: Competition Level Context When Comparing Seasons
A team that was "club_travel" in 2024 and "high_school_varsity" in 2025 is not directly comparable. The data model should store `competition_level` per season (not just per team entity) so coaches see: "Lincoln Eagles, 2024 Club Travel, 2025 HS Varsity -- these seasons are at different competition levels."

### NICE TO HAVE: Cross-Season Coaching Staff Continuity Signal
If the same coaching staff persists across seasons, their tendencies carry over even with a new roster. The public endpoint returns coach names. If the same names appear for a team across multiple seasons, that's a useful signal: "This program runs the same system year over year." Worth tracking but not blocking for the initial data model.

---

## 6. Crawl Priority Ordering

When we start pulling opponent data (IDEA-019, after E-088), the order matters. Here is the coaching priority ranking.

### Priority 1 -- MUST HAVE: Upcoming Opponents on the Schedule
The most time-sensitive scouting need. An opponent we play tomorrow needs data today. An opponent we play in 6 weeks can wait.

Sort the crawl queue by: **games on the schedule in ascending date order**, filtering to opponents with confirmed (linked) resolutions. Crawl each opponent's data in reverse proximity order -- the next scheduled opponent gets crawled first.

This also means the crawl should be incremental, not batch-once. As new games appear on the schedule, the queue should automatically reprioritize.

### Priority 2 -- MUST HAVE: Recently Played Opponents (retroactive scouting)
After the season starts and we have played games, coaches want to review how opponents we already faced compare to what the data predicted. More importantly, some opponents we face multiple times in a season -- a rematch is a scouting opportunity.

Crawl recently played opponents immediately after games complete. This builds the head-to-head history and validates the pre-game scouting reports against what actually happened.

### Priority 3 -- SHOULD HAVE: Fully Resolved Opponents We Have Not Yet Crawled
All opponents with `progenitor_team_id` that have not been crawled yet. This is the background fill pass -- no urgency, just completeness. Should run on a slow crawler (generous rate limiting, not time-sensitive).

### Priority 4 -- NICE TO HAVE: Unresolved (Unlinked) Opponents
Once Jason manually links them (via the search/URL workflow in item 4 above), move them into the resolution queue. No point crawling before the link exists.

### Practical Crawl Frequency
- **Pre-game (T-48 hours)**: Re-crawl the upcoming opponent's data. Player-stats and season stats can change day-to-day during the season. Stale data is worse than no data if a key pitcher just had a 120-pitch outing and is unavailable.
- **Post-game**: Crawl opponent's updated stats after the game. Captures any stat updates from the most recent game.
- **Weekly background**: Re-crawl all opponents who have recent games, to keep season stats current.

---

## Summary Table

| Question | Answer | Priority |
|----------|--------|----------|
| Most important scouting data | Pitching rotation + recent form + top hitters | MUST HAVE |
| Unlinked opponent presentation | Visible "partial data" badge + head-to-head history | MUST HAVE |
| MVP opponent profile (3 things) | Likely pitcher today, record + recent form, top 2-3 hitters by OBP | MUST HAVE |
| Manual association UX | Search by name first; URL paste as power-user option | MUST HAVE |
| Multi-season continuity | Same team entity, separate season stats per year | MUST HAVE |
| Crawl priority | Upcoming schedule first, recently played second, batch fill third | MUST HAVE |

All items above assume sample size caveats are presented inline with every stat. No stat is shown without its denominator (PA, IP). This is non-negotiable for coaching trust in the data.
