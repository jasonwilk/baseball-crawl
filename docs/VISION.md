# Vision: Baseball Analytics Platform

## The One-Liner

Give baseball coaches a competitive advantage that most programs don't have: data-driven opponent scouting, delivered as a fresh report the morning of the game -- powered by the same information every GameChanger user can already see, organized so it's actually useful. Lincoln Standing Bear High School is the first program. It won't be the last: the report tool serves any coach with a team on GameChanger, one season at a time.

## The Problem

High school baseball coaching decisions are made on gut feel, memory, and whatever a coach can scribble in a notebook between innings. The data exists -- every game scored on GameChanger produces box scores, pitch counts, spray charts, play-by-play logs -- but no one has time to open an opponent's 30 box scores, copy the numbers into a spreadsheet, and spot the patterns before Friday's game.

The information is there. The labor to extract it is not.

## The Insight

We are not inventing new analytics. We are not building a proprietary model or reverse-engineering hidden data. We are automating what a diligent coach with unlimited time could do by hand: open every one of an opponent's box scores, record every stat, and compile a scouting picture -- for this season, this opponent, this game.

The competitive advantage is not the data -- it's having the data organized, current, and delivered when the coaching staff needs it: the morning of the game, in a report they can read on the bench.

## What This Looks Like When It's Working

**The morning of a game**, Coach Martinez opens a link in her inbox: a fresh scouting report on tonight's opponent, generated automatically a few hours earlier. She sees their probable starter's K/9 and walk rate, their recent form, which hitters have been hot, and where they tend to put the ball in play. She adjusts the batting order -- moving a patient hitter with a high walk rate to the top against a wild pitcher, and slotting the power hitter into the 4-hole against a starter who gives up hard contact.

**On the bench**, the report is a clean, self-contained page -- no login, no app to learn, just a shared link that opens on any phone. Everything the staff needs to prep for this opponent is on one screen, and it was current as of that morning's data.

**Across a season**, the coaching staff builds a rhythm: every game gets its report, every report sharpens the next decision. Small edges -- the right reliever for a platoon matchup, one hitter moved up a spot, knowing the opponent's cleanup hitter can't handle breaking balls -- add up over thirty games.

Each report is one team's *current* body of work, generated fresh. The system does the season's worth of manual box-score labor so the coach can spend the morning coaching.

## The Layers

The system is built in layers, each one valuable on its own but more powerful together.

### Layer 1: Data Extraction
Automated crawling of GameChanger's API to pull an opponent's rosters, game schedules, box scores, pitch-by-pitch play data, and spray charts. Raw data is fetched fresh at generation time; play templates are persisted as a repair source. Crawls are idempotent -- re-running never duplicates data.

### Layer 2: Structured Database
A queryable SQLite database that organizes the raw data into tables designed for coaching questions: batting lines, pitching matchups, game-by-game rows, opponent tendencies. The schema reflects the metrics that matter for decisions (OBP, K/9, BB/9, first-pitch-strike %, QAB), and it stores every stat GameChanger tracks -- populated by direct API pull or compiled from play-by-play -- so a stat is never missing when a coach wants it. The scope is one team, one season at a time.

### Layer 3: Scouting Reports
The sole coaching surface. `bb report generate <gc_url>` (or the admin action) runs an in-memory pipeline that crawls an opponent, loads and reconciles the data, and renders a frozen, self-contained HTML report served publicly at a shareable link -- no login for viewers, no app to learn. Reports degrade gracefully: a missing spray chart or partial play data never fails the report, and the report tells the coach how complete it is (games covered, plays data, spray availability). The forward feature is **morning-of-game scheduled delivery**: a cron-invoked run that generates each LSB team's next-opponent report before dawn and emails coaches the link.

The serving surface is evolving from an admin panel into a **collection of tools**. Scouting reports are the first tool; a GC stats aggregator and a report deep-dive are on the horizon (see The Horizon). The auth model has two axes: logging in gates **discoverability** (logged-in users see the tool list in nav) and **privileged actions** (generate, delete, manage) -- but not **basic access**: a report link opens for anyone who has it, logged in or not. Tools are a coach's workspace, not an access wall.

## Scope and Scale

The report tool serves any coach with a team on GameChanger. Lincoln Standing Bear High School (Freshman, JV, Varsity, Reserve) is the first user and the proving ground, but the reach extends to Legion summer ball, USSSA youth, and travel programs -- any team scored on GameChanger, addressed by its `public_id`. A 9U USSSA coach gets a scouting report the same way a varsity coach does.

**The reach is single-season, any-team -- not multi-season.** "Serves any program" means the tool works for any team's *current* season, one report at a time. It does **not** mean tracking a player or team across seasons, blending programs, or building longitudinal history -- those remain explicit non-goals (see below). Multi-program breadth and multi-season depth are different things: we pursue the breadth and deliberately decline the depth.

**What this means concretely:**

- **Teams**: Lincoln HS (Freshman, JV, Varsity, Reserve) is the operator's own program; any GameChanger team can be scouted by `public_id`.
- **Per report**: one opponent, one season, ~30 games, 12-15 players.
- **Each season is its own context.** There is no cross-season rollup and no roster carry-over tracking. A report is a snapshot of one team's season.
- **Operator**: Jason runs the system and generates reports; coaches consume the shared links.
- **Growth model**: Add coverage by generating more reports, not by deploying new infrastructure.

The scale stays small even as more teams are scouted. SQLite is the right database. Docker Compose on a home server is the right deployment. Cloudflare Tunnel is the right network layer. There is no need for cloud infrastructure, horizontal scaling, or microservices. The system should be simple enough that one person can operate it, maintain it, and explain it.

## What We Don't Do

- **We don't access hidden data.** Every piece of information comes from GameChanger's normal UI or API -- the same data any parent in the stands can see.
- **We don't build proprietary models.** The stats we track (OBP, K/9, BABIP, FIP) are well-established baseball metrics. We compute them; we don't invent them.
- **We don't over-engineer.** A script is better than a pipeline. A dict is better than a class. One file is better than a framework. Complexity is added only when a real problem demands it.
- **We don't design for scale we'll never need.** A handful of reports a week, a few dozen players per report. The system should reflect that.

### Explicit Non-Goals

These were built once, removed (E-239), and must not be rebuilt. The multi-program *reach* above does not license any of them:

- **Cross-team player identity.** No athlete-profile population, no tracking one player across programs, no cross-program blending of a player's record. Per-team identity is sufficient for a scouting report.
- **Cross-season / multi-season / longitudinal anything.** No multi-season rollups, no season-over-season comparison, no longitudinal player or team tracking, no recency-tapering across seasons. This applies all the way down to the machinery: cross-season `season_id` partitioning and season-selection logic are not part of the report core. A report needs a season only as a within-report game filter -- year-only / current scope is the correct, complete window, never a "degraded" one. (The one legitimate home for multi-season logic is the offline GC stats aggregator tool -- see The Horizon -- which is explicitly separate from the report core.) **Operator carve-out:** pointing the tool at *whichever season the operator wants* is a desired action, not cross-season machinery. Year-filtered team search, season disambiguation when a `public_id` spans multiple seasons, and generating a report on any season's `public_id` are all fine -- the report that comes out is still a single-season snapshot. What is barred is rollup, tracking, or blending *across* seasons *within one artifact*. "Let me scout last year's version of this team" (a separate single-season report) is fine; "track this team across seasons" (one artifact spanning years) is not.
- **Member-team season-management product.** No dashboard browsing, roster/season stat pages, or schedule UI. The schedule *data* need (for morning-of-game delivery) is met by the authenticated schedule endpoint, public games as fallback.
- **Tracked/followed-opponent management as a product surface.** Reports are generated on demand or on schedule for whoever is next; no standing opponent-registry UI.
- **Multi-user team-scoped permissions.** One operator generates; coaches consume public links.
- **Distributed job infrastructure** (Redis/Celery) and in-process schedulers. Host cron invoking a CLI is the ceiling until reality demands more.

## The Horizon

The immediate product is the report and its morning-of-game delivery. Beyond that, the system grows based on real needs:

- **Coach email as a summary, not just a link** -- the key numbers (top two pitchers, OBP, steal rate) in the email body for a quick pre-game glance without clicking through.
- **A tools hub** -- the serving surface as a collection of coach-facing tools rather than an admin panel, with the two-axis auth model above.
- **GC stats aggregator** -- an offline tool that ingests CSVs exported from multiple GameChanger seasons and combines them, including merging two teams with mostly the same roster into one stat set. This is deliberately multi-season and lives *outside* the single-season report core -- the one place multi-season logic belongs.
- **Report deep-dive** -- take a generated scouting report and have an LLM conversation about it (mechanism TBD). A narrow, report-grounded analyst, not a general chatbot.
- **Pitch-type / pitch-selection surfacing** -- GameChanger includes pitch type when a scorekeeper charts it; we persist it now (it's free) and surface pitch mix and sequencing in reports once it proves prevalent enough among scouted opponents.
- **Pitch-by-pitch depth and defensive positioning** -- deeper at-bat-sequence and spray/positioning analysis, when coaches want to study contact quality and adjust their defense.

Each of these arrives when the pain is real, not before.

## North Star: Always Get Closer to Byte-Identical Play Ingestion

Plays-derived box scores should reconcile against GameChanger's official box scores across an entire season **as closely as mathematically possible** -- and every change to play ingestion should move that gap closer, never further.

This is a standing commitment to continuous fidelity, not a one-time threshold. We do not declare victory at some target number and stop. The measure is a plays-to-boxscore reconciliation scoreboard that diffs derived stats against the official box scores, per stat, over the full season; the discipline is that the gap trends toward zero and never regresses. "Always try to get closer."

We are honest about the limit. Quick-scored games, abandoned at-bats, and ordinary scorekeeper noise mean some residual is irreducible -- a perfect zero is not on the table, and pretending otherwise would be a fake 100%. The north star is the *direction and the discipline*, not a promised endpoint. When we extract a stat from play-by-play and call it the same stat GameChanger reports, the burden is on us to prove it reconciles -- and to keep proving it as the parser, the data sources, and the season evolve.

## The Measure of Success

This system is working when a coach opens the report link before a game, finds what they need in under a minute, and makes a better decision because of it. Not a revolutionary decision -- maybe just moving a hitter up one spot in the order, or choosing the right reliever for a platoon matchup, or knowing that the opponent's cleanup hitter can't hit breaking balls on the road.

Small edges, consistently applied, across a 30-game season. That's the vision.
