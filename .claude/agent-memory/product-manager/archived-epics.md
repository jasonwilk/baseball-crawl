# Archived Epics -- Key Milestones

Canonical source for the full archive: `ls /.project/archive/`

This file preserves only key milestones and architectural decision points from the project's history.

## Foundation (E-001 — E-030)
- **E-001**: GameChanger API Foundation — credential parser, API client, endpoint docs
- **E-002**: Data Ingestion Pipeline — 13 stories, 615 tests. Crawlers + loaders for all core data
- **E-003**: Data Model and Storage Schema — core schema, coaching_assignments, seed data
- **E-006**: PII Safety System — pre-commit hook + Claude Code hook for credential scanning
- **E-013**: Agent Buildout — data-engineer and software-engineer from stubs to full operational manuals

## Infrastructure (E-042 — E-100)
- **E-042**: Admin Interface and Team Management — URL-based onboarding, admin CRUD, opponent discovery
- **E-077**: Programmatic Auth Module — gc-signature HMAC, token refresh, client integration
- **E-088**: bb CLI Unification — Typer-based CLI replacing standalone scripts
- **E-096**: Production Deployment — Docker Compose on home Linux server with Cloudflare Tunnel
- **E-097**: Opponent Scouting Data Pipeline — bb data scout, scouting crawler and loader
- **E-100**: Team Model Overhaul — fresh-start schema rewrite. Programs, INTEGER PK, membership_type, TeamRef

## Process Evolution (E-112 — E-149)
- **E-112**: Context Layer Optimization — CLAUDE.md 508→152 lines, 4 new scoped rules, zero info loss
- **E-136/E-137**: Atomic Epic Commits + Worktree Isolation — single commit per epic, git worktree dispatch
- **E-140**: Planning Skill — formalized plan→spec review→triage→refine→READY workflow
- **E-149**: Review Methodology Retro — 6 new CR bug pattern checklist items from E-147/E-148 gaps

## Data Enrichment (E-155 — E-212)
- **E-155**: Combine Duplicate Teams — atomic merge across 16 FK cols in 13 tables
- **E-158**: Spray Chart Pipeline — full pipeline + dashboard integration, matplotlib rendering
- **E-173**: Fix Opponent Scouting E2E — resolution write-through, auto-scout, unified resolve page
- **E-195**: Plays Data Ingestion — FPS% and QAB from play-by-play, 2-table schema, parser/loader split
- **E-196**: Pitching Availability — migration 014, game ordering convention, shared workload query
- **E-197**: Derive season_id from Team Context — canonical utility, decoupled filesystem vs DB
- **E-198**: Reconciliation Engine — plays-vs-boxscore detection + BF-boundary correction
- **E-199**: Plays-Derived Stats in Reports — FPS%, QAB%, P/BF, P/PA on both scouting surfaces
- **E-204**: Starter vs. Relief Tracking — appearance_order, GS/GR display, backfill CLI
- **E-212**: Predicted Starter — first LLM integration, two-tier enrichment pattern, both surfaces
- **E-214**: Fix Predicted Starter Rest Day Anchoring — `reference_date` threading, `FEATURE_PREDICTED_STARTER` flag
- **E-215**: Fix Player-Level Duplicates — `ensure_player_row()` canonical upsert, prefix-matching detection, atomic merge, two-hook post-load dedup sweep in scouting pipeline
