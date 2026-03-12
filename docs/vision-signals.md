# Vision Signals

Raw parking lot for vision signals -- statements about what this project will become. Any agent appends here when they notice a signal in conversation. Format: date, one or two sentences, optional source context.

## Signals

- **2026-03-07**: Jason envisions an LLM-powered chat agent built into the dashboard where coaches can ask questions about matchups and get strategy insights. *(conversation during vision discussion)*
- **2026-03-09**: Codex treated as an agent LLM you drive, not a separate tool. Full repo access assumed (CLAUDE.md, agent defs, rules, everything). Two modes (spec review, code review) x two paths (headless dispatch, prompt generation). The mental model is: Claude dispatches to Codex the way it dispatches to any implementing agent. *(E-080 redesign discussion)*
- **2026-03-09**: Fuzzy opponent resolution using a light LLM (Haiku): compare rosters (mostly same players, jersey numbers), cross-reference shared game scores, and confirm "these are the same team" when the automated progenitor_team_id chain is unavailable. Useful for hand-created opponents with no GC link. *(opponent data model discussion)*
- **2026-03-11**: The `/search/opponent-import` endpoint could unlock opponent UUID resolution without the 403 barrier on the reverse bridge. Combined with the athlete-profile cluster (`/athlete-profile/{id}/career-stats`), this opens a path to full opponent data parity and cross-team longitudinal player tracking. Connects to IDEA-009 and IDEA-019. *(E-094 refinement team review)*
- **2026-03-12**: The complete opponent scouting chain has been verified end-to-end: public_id -> reverse bridge -> season stats + boxscores in 4 API calls per opponent. The core scouting value proposition is now technically achievable -- a coach can get full season stats for every player on an upcoming opponent. This is the inflection point where the project moves from "data collection" to "competitive intelligence." *(E-097 discovery -- live walkthrough of Lincoln Southwest Varsity data)*
