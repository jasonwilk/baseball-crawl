# E-103: Baseball Coach Agent Refinement

## Status
`READY`

## Overview
Refine the baseball-coach agent definition to embody the real coaching perspective that emerged from the 2026-03-13 vision session with Jason (head coach). The current agent reads as a generic baseball analytics expert; it should think like a Lincoln coach sitting in the dugout -- team-first, rate-stat-driven, flag-oriented, and aware of the HS-to-Legion seasonal flow.

## Background & Context
During a vision curation session on 2026-03-13, Jason articulated how coaches actually think about their work. Key insights that the current baseball-coach agent definition does not reflect:

1. **One coach, one team, one season at a time.** The primary frame is team-first, not program-first. A coach focuses on their team for this season.
2. **Seasons are sequential, not parallel.** HS ends, then Legion starts. Rosters carry over ~80%. In Lincoln, Legion teams closely align to HS teams (LSB Reserve maps to sophomore-level Legion team).
3. **Historical stats decay with recency.** Early in Legion, HS data fills the picture. As Legion games accumulate, current-season data takes over. Recency-weighted, not hard-walled.
4. **Own-team improvement first, opponents second.** "Give the coach any and all insights into what their team is doing and how to improve their own play. Then, secondarily, give them insights into the opponents."
5. **Rate stats are mandatory.** K/9, BB/9, OBP, K%, ERA, SB%. Counting stats alone are unusable for coaching decisions.
6. **Proactive flags are non-negotiable.** Short rest, high pitch count, hot/cold streaks, high walk rate. Coaches should not have to calculate these.
7. **Printable one-pager for bench use.** PDF, B&W, plain English. This is how coaches consume data on game day.
8. **Multi-program is real but simple.** USSSA (youth) coaches will use the platform too. A 9U coach has one team through a season -- same mental model.
9. **Three named coach personas.** The platform serves three distinct types: USSSA youth coaches (9U-14U, age-grouped travel ball), high school coaches (varsity/JV/freshman/reserve, spring season), and Legion coaches (post-HS summer, same-region players). Each has one team through a season. The mental model is identical across all three.
10. **Cross-season player and opponent intersection.** The same kid may appear as a USSSA player in fall, an HS player in spring, and a Legion player in summer. An opponent pitcher from HS reappears on a different Legion team three weeks later. The coach agent must understand this reality — player and opponent identity transcends the team context for any given season.
11. **Fresh-start philosophy.** Each season is a fresh start. Same kid, new team, new opportunities. Past data is context, not conclusion. The system focuses on THIS team, THIS season. Prior seasons are available when asked, never leading. This is a coaching principle, not just a display preference.
12. **Relevance decay framework and pull-based history.** Historical data relevance degrades by age and competitive-tier gap: same season = act on it; prior season same level = moderate-high, use with small-sample caveats; 2 seasons ago = context only, flag the age; 3+ seasons ago = curiosity, not evidence; different competitive tier (e.g., 12U rec → HS varsity) = flag prominently with age/level context. Display default: current season only. Prior data surfaces as a quiet indicator ("prior data available"), tap to expand. For opponents, "Familiar Faces" ("you have prior data on 3 of these hitters") is a sidebar note, not a featured section — slightly more visible for opponents than own-team, because coaches know their own players daily but may not recognize opponent names.

The current agent definition has good bones (statistics knowledge, sample size awareness, anti-patterns) but lacks the coaching persona, the Lincoln-specific context, and the emphasis on proactive data delivery over passive query.

No expert consultation required -- the input came directly from the head coach during a vision session. This is a direct translation of user requirements into agent refinement.

## Goals
- The baseball-coach agent embodies a team-first, season-at-a-time coaching perspective
- Own-team improvement is explicitly prioritized over opponent scouting in the agent's framing
- Lincoln-specific knowledge (HS-to-Legion transitions, roster overlap, seasonal flow) is embedded
- Rate stats and proactive flags are emphasized as core requirements, not afterthoughts
- The agent understands how coaches consume data (quick lookups, printable one-pagers, game-day context)

## Non-Goals
- Changing the agent's technical boundaries (still does not write code, SQL, or make technology choices)
- Adding new tool access or model changes
- Modifying other agent definitions
- Implementing any dashboard or reporting features (this is agent persona refinement only)

## Success Criteria
- The refined agent definition, when read by a new user, communicates that this agent thinks like a high school baseball coach focused on their team this season -- not a sabermetrics analyst
- All twelve coaching insights from the vision session and E-100 review session are reflected in the agent definition
- Existing strengths (sample size awareness, anti-patterns, inter-agent coordination, output standards) are preserved
- The agent definition remains concise and scannable (not bloated with prose)

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-103-01 | Refine baseball-coach agent definition with coaching persona | TODO | None | claude-architect |

## Dispatch Team
- claude-architect

## Technical Notes
- **Single file change**: `.claude/agents/baseball-coach.md`. This is a context-layer file, routed to claude-architect.
- **Preserve, don't replace**: The current definition has good structural bones. The refinement should reshape the framing, add Lincoln-specific context, and shift emphasis -- not rewrite from scratch.
- **Coaching concepts to embed** (from Background & Context, insights 1–12): team-first frame, sequential seasons, recency-weighted history, own-team-first priority, rate stats mandatory, proactive flags non-negotiable, printable one-pager, multi-program simplicity, no separate front doors, three named coach personas (USSSA/HS/Legion), cross-season player/opponent intersection, fresh-start philosophy + relevance decay + pull-based history (Familiar Faces).
- **Context-layer only**: No Python code, no tests. Definition of Done does not require test passage (context-layer story).

## Open Questions
None.

## History
- 2026-03-13: Created. Input from vision session with Jason (head coach). No expert consultation required -- direct user requirements.
- 2026-03-13: Four additional coaching concepts added from E-100 domain review session (baseball-coach agent as reviewer): three named coach personas (USSSA/HS/Legion), cross-season player/opponent intersection, fresh-start philosophy, relevance decay framework + pull-based history + Familiar Faces pattern. Background & Context expanded to 12 insights.
