# Vision: LSB Baseball Analytics

## The One-Liner

Give Lincoln Standing Bear High School baseball coaches a competitive advantage that most high school programs don't have: data-driven scouting, lineup decisions, and player development -- powered by the same information every GameChanger user can already see, organized so it's actually useful.

## The Problem

High school baseball coaching decisions are made on gut feel, memory, and whatever a coach can scribble in a notebook between innings. The data exists -- every game scored on GameChanger produces box scores, pitch counts, spray charts, play-by-play logs -- but no one has time to open 120 box scores across four teams, copy the numbers into a spreadsheet, cross-reference opponents, and spot patterns.

The information is there. The labor to extract it is not.

## The Insight

We are not inventing new analytics. We are not building a proprietary model or reverse-engineering hidden data. We are automating what a diligent coach with unlimited time could do by hand: open every box score, record every stat, compare every matchup, and track every player's development across seasons and levels.

The competitive advantage is not the data -- it's having the data organized, current, and queryable when the coaching staff needs it.

## What This Looks Like When It's Working

**Before a game**, Coach Martinez pulls up tomorrow's opponent on the dashboard. She sees their typical lineup, who's been hot in the last five games, their probable starter's K/9 and walk rate, and how her hitters have fared against this team in prior meetings. She adjusts the batting order -- moving a patient hitter with a high walk rate to the top of the order against a wild pitcher, and slotting the power hitter into the 4-hole against a starter who gives up hard contact.

**During the season**, Coach Davis tracks his freshman pitchers' development. He can see that Jake's strikeout rate has climbed from 5.2 K/9 in his first five starts to 7.8 in his last five, while his walk rate has stayed steady. The numbers confirm what his eyes are telling him -- Jake is ready for tougher competition.

**Across seasons**, the coaching staff watches players progress from freshman ball through JV, varsity, and into legion summer ball. A player who struggled as a sophomore but showed steady improvement becomes a confident junior-year starter. The data tells the story of development that memory alone cannot track.

## The Layers

The system is built in layers, each one valuable on its own but more powerful together.

### Layer 1: Data Extraction
Automated crawling of GameChanger's API to pull team rosters, season stats, game schedules, box scores, and (eventually) pitch-by-pitch play data and spray charts. Raw data is stored faithfully before any transformation. Crawls are idempotent -- re-running never duplicates data.

### Layer 2: Structured Database
A queryable SQLite database that organizes the raw data into tables designed for coaching questions: batting splits, pitching matchups, game-by-game trends, opponent tendencies. The schema reflects the metrics that matter for decisions (OBP, K/9, BB/9, home/away splits, platoon splits), not just what the API happens to return.

### Layer 3: Coaching Dashboard
A server-rendered web application where coaches can pull up scouting reports, player stats, opponent analysis, and game prep information without touching a spreadsheet or asking Jason to run a query. Simple, fast, focused on the questions coaches actually ask.

### Layer 4: Longitudinal Intelligence
Player tracking across seasons, teams, and levels. Development arcs over time. Trend detection -- who's improving, who's regressing, who's streaking. The kind of institutional memory that a coaching staff accumulates over years, but structured so it doesn't walk out the door when an assistant coach moves on.

## Scope and Scale

This is a system for one high school program:

- **4 teams**: Freshman, JV, Varsity, Reserve (Legion later)
- **12-15 players per team**
- **~30 games per team per season**
- **1 operator** (Jason) who manages the system
- **A handful of coaches** who consume the dashboards

The scale is small by design. SQLite is the right database. Docker Compose on a home server is the right deployment. Cloudflare Tunnel is the right network layer. There is no need for cloud infrastructure, horizontal scaling, or microservices. The system should be simple enough that one person can operate it, maintain it, and explain it.

## What We Don't Do

- **We don't access hidden data.** Every piece of information comes from GameChanger's normal UI or API -- the same data any parent in the stands can see.
- **We don't build proprietary models.** The stats we track (OBP, K/9, BABIP, FIP) are well-established baseball metrics. We compute them; we don't invent them.
- **We don't over-engineer.** A script is better than a pipeline. A dict is better than a class. One file is better than a framework. Complexity is added only when a real problem demands it.
- **We don't design for scale we'll never need.** Four teams, 120 games a season, a few dozen players. The system should reflect that.

### Layer 5: Conversational Intelligence

An LLM-powered chat agent embedded in the dashboard. Not a generic baseball chatbot -- a context-aware analyst whose knowledge shifts based on where the coach is in the application.

- **On a game page**, the coach asks "What should I watch for against Lincoln East tomorrow?" or "Why did we struggle against their #3 pitcher last time?" The agent draws on matchup history, recent form, and pitching stats to answer.
- **On the schedule page**, the coach asks "Predict the next ten game outcomes" and gets projections grounded in the data the system has collected -- not hallucinated optimism.
- **On a player page**, the coach asks about tendencies: "What's his first-strike percentage?" or "Does he chase breaking balls away?" The agent reaches into pitch-by-pitch and play-by-play data to surface patterns the numbers reveal.
- **On a team page**, the coach asks "Who's the normal closer?" or "How does the lineup change against lefties?" The agent reads lineup history and usage patterns.

The context is the key. The same question gets a different answer depending on whether the coach is looking at a player, a game, a team, or a matchup. The agent is tuned for baseball coaching and strategy -- it picks up on nuances in the statistics that a coach might not have time to dig for manually.

**Audience**: Head coaches and assistants first. Players are a future possibility that would bring different expectations for language, depth, and permissions.

## The Horizon

The immediate goal is a working data pipeline and a coaching dashboard that coaches actually use for game prep. Beyond that, the system grows based on real needs:

- **Pitch-by-pitch analysis** -- when coaches want to study at-bat sequences, contact quality, and pitcher tendencies at a deeper level
- **Spray charts and defensive positioning** -- when coaches want to see where opponents hit the ball and adjust their defense accordingly
- **Automated scheduling** -- when manual crawl runs become tedious and data freshness matters daily during the season
- **Multi-season trend views** -- when enough data accumulates to tell meaningful development stories across years
- **Conversational intelligence** -- when the dashboard and data are rich enough to make an LLM analyst genuinely useful rather than a gimmick

Each of these arrives when the pain is real, not before.

## The Measure of Success

This system is working when a coach opens the dashboard before a game, finds what they need in under a minute, and makes a better decision because of it. Not a revolutionary decision -- maybe just moving a hitter up one spot in the order, or choosing the right reliever for a platoon matchup, or knowing that the opponent's cleanup hitter can't hit breaking balls on the road.

Small edges, consistently applied, across a 30-game season. That's the vision.
