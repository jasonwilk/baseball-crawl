# E-004: Coaching Dashboard

## Status
`DRAFT`

## Overview
Build the coach-facing interface: server-rendered HTML views via FastAPI + Jinja2 on Docker that let coaches review player stats, prepare for opponents, and make lineup decisions -- without writing any SQL or running any scripts.

## Background & Context
The user (system operator) runs the crawl and load pipeline. Coaches interact exclusively with the published dashboard. The dashboard must be simple, fast, and mobile-friendly -- coaches look at this in the dugout on a phone, not on a desktop.

This epic is deliberately a DRAFT. It will not be fully specified until E-002 and E-003 are complete, because the available data and schema will shape what views are feasible. Key open questions (opponent split data accessibility, API field availability) need to be resolved first.

**Tech stack confirmed by E-009**: FastAPI + Jinja2 on Docker (replaces the original Cloudflare Workers/Pages plan). See CLAUDE.md for the full stack description.

**Do not start this epic until E-002-07 and E-003-04 are DONE.**

## Goals
- A FastAPI + Jinja2 serving layer that renders team, player, and game data from SQLite
- Server-rendered HTML views for: team roster + season stats, opponent scouting report, game log
- The dashboard is read-only -- coaches cannot modify data
- Mobile-friendly layout
- Player tracking across teams: a player's history is accessible regardless of which team they're currently on

## Non-Goals
- Authentication/login (out of scope for initial version; the URL is the access control)
- Data entry or editing
- Push notifications or real-time updates
- Advanced statistical analysis (e.g., WAR, BABIP)
- Automated lineup optimization

## Success Criteria
- A coach can load the team roster page and see current-season stats for all players in under 2 seconds on a mobile connection
- A coach can load an opponent scouting report that shows the opponent's key hitters and pitchers with their season stats
- A coach can see a player's game log for the last 5 games
- All views work correctly on a 375px-wide mobile screen

## Stories
To be written after E-002 and E-003 are complete. The story breakdown will cover:
- FastAPI route setup and SQLite queries
- Team roster and season stats endpoint + view
- Opponent scouting report endpoint + view
- Player profile page (career stats across teams/seasons)
- Game log view

## Technical Notes
- **Framework**: FastAPI + Jinja2 -- server-rendered HTML (not a client-side SPA)
- **CSS**: Tailwind CDN (no build step for MVP)
- **Data layer**: SQLite via the same database as the ingestion pipeline (`./data/app.db`)
- **Local dev**: `docker compose up` at `http://localhost:8000`
- **Agent browsability**: `curl http://localhost:8001/dashboard` via Bash tool (WebFetch does not work with localhost -- confirmed in E-009-06)
- **MVP scope**: Server-rendered HTML stat tables and cards; no client-side JS required
- **No build step**: Prefer zero-build-step frontend to keep the deployment simple

## Open Questions
- What specific analytical views do coaches want most? (Needs a conversation with the user before stories are written.)
- Should there be separate dashboards per team level (Varsity vs. JV) or a single dashboard with a team selector?
- What is the URL structure? Public URL? Password-protected?
- How often should the dashboard data be refreshed? (Driven by how often `scripts/crawl.py` is run.)

## History
- 2026-02-28: Created as DRAFT; blocked on E-002 and E-003 completion
