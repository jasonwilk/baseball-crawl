# E-088: Opponent Data Model and Resolution

## Status
`READY`

## Overview
Bridge local opponent entries to real GameChanger teams so coaches can access full scouting data for upcoming opponents. This epic creates the `opponent_links` table, an automated resolution crawler that chains authenticated API calls to resolve ~86% of opponents automatically, an admin UI for manually linking the remaining ~14%, and context-layer documentation for migration conventions and the opponent resolution API flow.

## Background & Context
When LSB teams play games, GameChanger creates local opponent entries with a `root_team_id`. Some of these opponents have a `progenitor_team_id` linking to the canonical GC team, but the connection is not stored in our database. Without this bridge, the coaching dashboard cannot show opponent season stats, pitcher rotations, or recent form -- the three things coaches need most for pre-game scouting.

The resolution chain was mapped during API exploration (2026-03-09): opponents list -> progenitor_team_id -> team detail -> public_id. The `GET /teams/{progenitor_team_id}/public-team-profile-id` endpoint returns 403 for opponent UUIDs, so the resolution must go through `GET /teams/{progenitor_team_id}` which returns `public_id` directly in team metadata.

Expert consultations completed: baseball-coach (coaching requirements, `.project/research/E-088-opponent-data-model-coaching-requirements.md`), data-engineer (schema design), software-engineer (implementation patterns), api-scout (endpoint risk assessment), ux-designer (admin page design), claude-architect (context-layer scope).

## Goals
- Store the resolution state of every opponent (linked/auto, linked/manual, unlinked) in a queryable bridge table
- Automatically resolve ~86% of opponents via the progenitor_team_id -> team detail -> public_id chain
- Give the operator a manual URL-paste flow to link the remaining ~14%
- Document migration conventions and the opponent resolution API flow in the context layer

## Non-Goals
- Search-based opponent association (search endpoint response body unknown -- HIGH risk; deferred until captured via ingest-endpoint)
- Opponent stat crawling (IDEA-019)
- Public endpoint data ingestion (IDEA-020)
- Fuzzy/LLM-based opponent matching (IDEA-018)
- Multi-season stat storage (coach's team-entity/team-season split is forward-compatible but not implemented here)
- Full database migration process definition (partially addressed by migrations rule; remainder is IDEA-021)

## Success Criteria
- `opponent_links` table exists with correct schema, indexes, and constraints
- Running the automated resolver populates opponent_links for all teams with progenitor_team_id data
- Admin opponents page displays all three link states with coach-friendly labels
- Operator can manually link an unlinked opponent via URL paste with confirmation
- Context-layer files document migration conventions and the resolution API flow

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-088-01 | opponent_links Migration and Seed Data | TODO | None | - |
| E-088-02 | Automated Opponent Resolution Crawler | TODO | E-088-01 | - |
| E-088-03 | Admin Opponents Page with Manual URL-Paste Linking | TODO | E-088-01 | - |
| E-088-04 | Context-Layer Updates (Migration Rule + Flow Doc + API Docs) | TODO | None | - |

## Dispatch Team
- data-engineer (story 01)
- software-engineer (stories 02, 03)
- claude-architect (story 04)

## Technical Notes

### 1. Schema: opponent_links Table (DE Design)

```sql
CREATE TABLE IF NOT EXISTS opponent_links (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    our_team_id         TEXT    NOT NULL REFERENCES teams(team_id),
    root_team_id        TEXT    NOT NULL,  -- intentionally NOT a FK to teams; this is GC's local opponent registry key, not a canonical team UUID
    opponent_name       TEXT    NOT NULL,
    resolved_team_id    TEXT    REFERENCES teams(team_id),
    public_id           TEXT,
    resolution_method   TEXT CHECK (resolution_method IN ('auto', 'manual') OR resolution_method IS NULL),
    resolved_at         TEXT,
    is_hidden           INTEGER NOT NULL DEFAULT 0,
    created_at          TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT    NOT NULL DEFAULT (datetime('now')),  -- no trigger; callers must set updated_at = datetime('now') on every UPDATE
    UNIQUE(our_team_id, root_team_id)
);

CREATE INDEX IF NOT EXISTS idx_opponent_links_resolved
    ON opponent_links(resolved_team_id)
    WHERE resolved_team_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_opponent_links_public_id
    ON opponent_links(public_id)
    WHERE public_id IS NOT NULL;
```

### 2. API Resolution Chain

The resolution chain uses authenticated endpoints only:

1. `GET /teams/{team_id}/opponents` -- returns opponent list with `progenitor_team_id` (nullable)
2. `GET /teams/{progenitor_team_id}` -- returns team metadata including `public_id`
3. Public endpoints (future use): `GET /public/teams/{public_id}` for opponent self-reported data

**WARNING**: `GET /teams/{progenitor_team_id}/public-team-profile-id` returns **403 for opponent UUIDs**. Do NOT use this endpoint for resolution. Use `GET /teams/{progenitor_team_id}` directly.

Endpoint documentation:
- `/workspaces/baseball-crawl/docs/api/endpoints/get-teams-team_id-opponents.md`
- `/workspaces/baseball-crawl/docs/api/endpoints/get-teams-team_id.md`

### 3. Resolution Statistics

- ~86% of opponents have a non-null `progenitor_team_id` and can be auto-resolved
- ~14% have null `progenitor_team_id` and require manual linking (URL paste)
- These percentages are based on observed data from LSB teams; other programs may vary

### 4. Crawl Timing

- ~60 opponents with progenitor_team_id across all LSB teams
- Sequential requests at ~1.5s spacing (project forbids parallel requests to same endpoint)
- Total estimated time: ~90 seconds for full resolution pass
- Resolution is idempotent -- safe to re-run

### 5. Manual Resolution Protection Pattern

Upsert must use COALESCE on `resolution_method` to prevent auto-resolution from overwriting manual links:

```sql
INSERT INTO opponent_links (our_team_id, root_team_id, opponent_name, resolved_team_id, public_id, resolution_method, resolved_at)
VALUES (?, ?, ?, ?, ?, 'auto', datetime('now'))
ON CONFLICT(our_team_id, root_team_id) DO UPDATE SET
    opponent_name = excluded.opponent_name,
    resolved_team_id = CASE
        WHEN opponent_links.resolution_method = 'manual' THEN opponent_links.resolved_team_id
        ELSE excluded.resolved_team_id
    END,
    public_id = CASE
        WHEN opponent_links.resolution_method = 'manual' THEN opponent_links.public_id
        ELSE excluded.public_id
    END,
    resolution_method = COALESCE(opponent_links.resolution_method, excluded.resolution_method),
    resolved_at = CASE
        WHEN opponent_links.resolution_method = 'manual' THEN opponent_links.resolved_at
        ELSE excluded.resolved_at
    END,
    updated_at = datetime('now');
```

### 6. FK Satisfaction Pattern

`resolved_team_id` references `teams(team_id)`. Before inserting a resolved opponent_link, ensure the team row exists using the `_ensure_team_row()` pattern from `GameLoader` (inserts a stub row if the team_id is not already in the teams table).

Reference: `src/gamechanger/loaders/game_loader.py` -- `_ensure_team_row()` method.

### 7. Coach-Friendly Label Language

Per baseball-coach consultation, use coaching language not technical terms:

| Resolution State | Badge Color | Badge Text | Meaning |
|-----------------|-------------|------------|---------|
| Auto-resolved | Green | "Full stats" + gray "auto" micro-label | Linked via progenitor_team_id chain |
| Manually linked | Blue | "Full stats" + gray "manual" micro-label | Operator linked via URL paste |
| Unlinked | Yellow | "Scoresheet only" | No GC team link; only our game data available |

Yellow communicates a data limitation, not an error. Never expose raw API IDs (UUIDs, progenitor_team_id) in the UI.

### 8. Three ID Types

| ID | Source | Purpose |
|----|--------|---------|
| `root_team_id` | Our scorekeeper's opponent entry | Local identifier from GC's opponent registry; unique per our-team + opponent pair. Intentionally NOT a FK to teams -- it references GC's local opponent entries, not canonical team UUIDs |
| `progenitor_team_id` | GC opponent metadata | Canonical GC team UUID; nullable (~14% missing) |
| `public_id` | GC team metadata response | Public slug for unauthenticated endpoints (e.g., `lincoln-eagles-ne`) |

### 9. Coaching Requirements Reference

The full coaching requirements analysis is at: `/.project/research/E-088-opponent-data-model-coaching-requirements.md`

Key coaching priorities for opponent data (from baseball-coach):
1. Who is pitching today (K/BB ratio, IP, last pitch count)
2. Record and recent form (last 3-5 games with scores)
3. Top 2-3 hitters by OBP (with PA counts and K%)

These priorities inform future work (IDEA-019, IDEA-020) but are not directly implemented in this epic. This epic creates the resolution infrastructure that makes that future work possible.

### 10. Admin UI Design (UXD)

**Page structure**: New `/admin/opponents` page with sub-nav tab (Users | Teams | Opponents). Teams page "Tracked Opponents" section simplified to summary count + "Manage connections" link.

**Templates**: Two templates -- `opponents.html` (listing with filter pills) and `opponent_connect.html` (combined connect flow with multi-state rendering).

**Routes**:
- `GET /admin/opponents` (listing with `?filter=` for pills and `?team_id=` for scoping)
- `GET /admin/opponents/{id}/connect` (URL-paste form)
- `GET /admin/opponents/{id}/connect/confirm` (confirmation display)
- `POST /admin/opponents/{id}/connect` (save the link)
- `POST /admin/opponents/{id}/disconnect` (clear link, allow re-linking)

**Connect flow**: URL-paste only for this epic. The template design accommodates future search results rendering when the search endpoint schema is captured.

**Manual link UUID limitation**: The URL-paste flow extracts a `public_id` slug. The reverse bridge endpoint (`GET /teams/public/{public_id}/id`) returns 403 for opponent teams, so no UUID is available. Manual links set `public_id` only; `resolved_team_id` remains NULL. This is acceptable -- `public_id` is sufficient for all public endpoint data access (IDEA-020).

**Disconnect restriction**: Disconnect is only allowed for manually-linked opponents. Auto-resolved opponents cannot be disconnected because the next resolver run would immediately re-create the link.

**Post-connect redirect**: Successful `POST /admin/opponents/{id}/connect` redirects to `GET /admin/opponents?team_id={our_team_id}`.

**Confirm page error handling**: If the public API call on the confirm page fails (network error, 404, timeout), show an error message with a "try again" link rather than silently failing.

### 11. Discovered Stubs vs. opponent_links Duality

The `discover_team_opponents()` function in admin routes creates placeholder `teams` rows with `source='discovered'` from public schedule data (matched by name). The `OpponentResolver` (E-088-02) creates `opponent_links` rows from the authenticated opponents endpoint (keyed by `root_team_id`). These are parallel structures serving different purposes: discovery creates team stubs for display, while resolution creates bridge rows for scouting data access. They are not reconciled in this epic.

### 12. Wrong Auto-Link Limitation (MVP)

Auto-resolved links cannot be manually overridden in this epic. `POST /admin/opponents/{id}/disconnect` returns 400 for auto-resolved opponents because the next resolver run would immediately re-create the link. If an auto-link is wrong, corrective action requires a direct SQL fix or a future "override" feature. This is a known MVP limitation.

## Open Questions
- None remaining. All questions resolved during expert consultation.

## History
- 2026-03-09: Created. Expert consultations with baseball-coach, data-engineer, software-engineer, api-scout, ux-designer, and claude-architect completed during formation. Schema divergence (bridge table vs. columns on teams) resolved in favor of bridge table. Search-based manual association deferred due to unknown search endpoint response schema.
- 2026-03-10: DE spec review triaged by full team (PM, SE, DE, CA, DW). 17 refinements accepted across all 4 stories and epic Technical Notes: removed redundant index, added CHECK constraint on resolution_method, added root_team_id non-FK comment, added updated_at caller-obligation comment, added TN-11 (discovered stubs duality) and TN-12 (wrong auto-link MVP limitation), clarified {id} parameter as opponent_links.id, added field-mapping note and is_hidden handling to E-088-02, added --dry-run flag to CLI, added duplicate public_id and own-team URL guards to E-088-03, added multi-team seed row requirement, added datetime format note and CLAUDE.md update to E-088-04. 3 rejected (seed_dev.sql exists, slot 002 gap archaeology, parse_team_url regex). 1 deferred (public_id divergence).
