# E-103-01: Refine baseball-coach agent definition with coaching persona

## Epic
[E-103: Baseball Coach Agent Refinement](epic.md)

## Status
`DONE`

## Description
After this story is complete, the baseball-coach agent definition will embody the real coaching perspective articulated by head coach Jason during the 2026-03-13 vision session. The agent will think team-first, prioritize own-team improvement over opponent scouting, speak in terms of rate stats and proactive flags, and understand the Lincoln-specific seasonal flow from HS to Legion. Six additional coaching concepts from the E-100 domain review session are also embedded: three named coach personas (USSSA/HS/Legion), cross-season player/opponent intersection, fresh-start philosophy, relevance decay framework, pull-based historical data, and the Familiar Faces opponent scouting pattern.

## Context
The baseball-coach agent definition at `.claude/agents/baseball-coach.md` currently reads as a generic baseball analytics expert. A vision session with Jason (head coach) on 2026-03-13 revealed nine specific insights about how coaches actually think. This story reshapes the agent definition to reflect that real coaching perspective while preserving the existing structural strengths (statistics knowledge, sample size awareness, anti-patterns, inter-agent coordination).

## Acceptance Criteria
- [ ] **AC-1**: The Identity section frames the agent as a coach focused on one team, one season at a time -- not as a program-level analytics expert. The team-first mental model is the primary frame.
- [ ] **AC-2**: The agent definition explicitly prioritizes own-team improvement insights over opponent scouting. Own-team analysis is the primary responsibility; opponent scouting is secondary and clearly labeled as such.
- [ ] **AC-3**: Lincoln-specific knowledge is embedded: HS-to-Legion seasonal transitions, ~80% roster carryover, LSB Reserve to sophomore-level Legion alignment, and the sequential (not parallel) nature of seasons. Cross-season player and opponent intersection is addressed: the same player may appear on USSSA, HS, and Legion teams across consecutive seasons; the same opponent pitcher from HS may reappear on a Legion opponent weeks later.
- [ ] **AC-4**: Rate stats (K/9, BB/9, OBP, K%, ERA, SB%) are emphasized as the mandatory baseline for coaching decisions. The definition explicitly states that counting stats alone are insufficient and must be accompanied by rate equivalents.
- [ ] **AC-5**: Proactive flags are defined as a core requirement, not an afterthought. The agent knows that coaches need to be told about short rest, high pitch count, hot/cold streaks, and high walk rates without having to ask or calculate.
- [ ] **AC-6**: The agent's tone for surfacing insights is "bubble up, never push." Safety flags (rest days, pitch counts) can push — they're compliance. Performance insights (streaks, splits, matchup patterns) bubble up quietly: "I noticed Thompson is 8-for-12 against lefties this month." Never prescriptive — the system observes, the coach decides. The goal is to get the coach into a flow state with the data, not make them feel managed or chaotic.
- [ ] **AC-7**: The agent understands how coaches consume data on game day: quick lookups during the game, a printable B&W one-pager for the bench, and plain English over jargon-heavy tables.
- [ ] **AC-8**: Historical stat decay and the fresh-start philosophy are addressed. Each season is a fresh start — prior data is context, not conclusion, and the system leads with THIS season's data. The agent carries the relevance decay framework: same season = act on it; prior season same competitive level = moderate-high; 2 seasons ago = context only, flag the age; 3+ seasons ago = curiosity not evidence; different competitive tier (e.g., 12U rec → HS varsity) = flag with age and level. Early in a new season (e.g., Legion opening week after HS spring), prior-season data fills the gap as a floor estimate; current-season data takes over as games accumulate.
- [ ] **AC-9**: The three coach personas are named explicitly: USSSA youth coaches (9U-14U travel ball), high school coaches (varsity/JV/freshman/reserve), and Legion coaches (post-HS summer). The agent understands each persona's context and speaks to them appropriately. The mental model is identical across all three: one coach, one team, one season. No separate UX framing per program type.
- [ ] **AC-10**: Existing strengths are preserved: sample size awareness and thresholds, anti-patterns (no code, no tech choices, always flag sample size, always prioritize), inter-agent coordination section, output standards, stat abbreviation reference, skill references, and memory section all remain intact (content may be refined but not removed).
- [ ] **AC-11**: The agent definition remains concise -- no section exceeds 30 lines, and the total file length does not increase by more than 60 lines over the current version (143 lines), given the additional coaching concepts from the E-100 review session.
- [ ] **AC-12**: Pull-based historical data and the Familiar Faces pattern are reflected in how the agent frames recommendations. Default is current season only; prior data surfaces as a quiet indicator ("prior data available"), available on demand. For opponent scouting, "Familiar Faces" appears as a sidebar note ("you have prior data on 3 of these hitters"), not a featured section. Slightly more prominent for opponents than own-team, because coaches see their own players daily but may not recognize opponent names.

## Technical Approach
The file to modify is `.claude/agents/baseball-coach.md`. This is a context-layer refinement -- reshaping existing sections and adding targeted new content, not a rewrite. The epic Technical Notes contain the nine coaching insights that must be embedded. The current file (143 lines) has good structure; the refinement should work within that structure, adjusting framing and emphasis rather than adding large new sections.

Key areas to reshape:
- **Identity section**: Shift from "baseball analytics domain expert" to a coach-first persona
- **Your Context section**: Add Lincoln-specific seasonal knowledge
- **Core Responsibilities**: Reorder to lead with own-team improvement; add proactive flags and rate stats emphasis
- **Key Baseball Analytics Knowledge**: Strengthen rate stat emphasis; add proactive flags subsection
- **What Coaches Actually Use**: Refine to reflect the game-day consumption patterns (one-pager, quick lookups)
- **Output Standards**: Add bench-ready, printable format awareness
- **Historical data philosophy**: Add fresh-start principle, relevance decay framework, and pull-based history (Familiar Faces pattern) — likely a new subsection under Key Baseball Analytics Knowledge or What Coaches Actually Use

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `.claude/agents/baseball-coach.md` -- refine agent definition

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Agent definition YAML frontmatter unchanged (name, description, model, color, memory, tools)
- [ ] No regressions: all existing inter-agent coordination contracts preserved

## Notes
- The nine coaching insights are enumerated in the epic's Background & Context section and Technical Notes. Use those as the source of truth for what to embed.
- The `description` field in the YAML frontmatter may be updated if the refined identity warrants a better one-line summary, but the structural fields (model, color, memory, tools) must not change.
