# E-033: Project Hygiene -- Align Docs and Tests with Current Reality

## Status
`COMPLETED`

## Overview
Fix documentation and test files that have drifted from the implemented stack. After the E-009 tech stack decision (FastAPI + SQLite + Docker + Cloudflare Tunnel), several canonical documents still describe the old Cloudflare D1 / Workers / TypeScript plan, active story files use machine-specific absolute paths that break in different workspaces, and the FastAPI test harness has a lifecycle problem that causes tests to hang. This epic brings everything into alignment with current reality.

## Background & Context

### What prompted this epic
A project review identified four categories of drift:

1. **CLAUDE.md describes the wrong stack.** The Tech Stack, Deployment Target, Architecture, and Security Rules sections still reference Cloudflare D1, Workers, TypeScript, and "Cloudflare secrets for production." The E-009 decision (2026-02-28) chose FastAPI + Jinja2 + SQLite + Docker Compose + Cloudflare Tunnel. Agents loading CLAUDE.md get the wrong mental model of the project.

2. **The current migration has a misleading comment.** `migrations/001_initial_schema.sql` says "Schema designed per E-003" but E-003-01 (the schema rewrite) is still TODO. The file contains the pre-E-003 schema. The comment should describe what the file IS, not what it will become.

3. **FastAPI tests may hang.** `tests/test_api_health.py` and `tests/test_dashboard.py` create `TestClient(app)` without using the context manager protocol. This can leave the ASGI lifespan running and cause tests to hang instead of completing promptly.

4. **72 files contain hardcoded `/Users/jason/Documents/code/baseball-crawl/` paths.** Many are archived (acceptable), but active story files (E-023-01 through E-023-05, E-009-08) and context-layer files (agent definitions, skills, architect memory) contain these non-portable paths. Implementing agents running in `/workspaces/baseball-crawl/` will reference files at paths that do not exist in their environment.

### Expert consultation
No expert consultation required. The PM performed the full file analysis (grep for stale references, file-by-file review of all affected documents). All changes are mechanical text replacements guided by the user's design preference: "CLAUDE.md and shipped code comments should describe current implemented reality, not future planned state." Context-layer stories route to claude-architect for implementation, who will see full context at dispatch time.

### Relationship to E-009-08
E-009-08 ("CLAUDE.md and E-004 Update") exists in E-009 and covers overlapping scope. This epic deliberately avoids duplicating E-009-08's work. The scope split:

- **E-033 handles NOW** (no blockers): CLAUDE.md Tech Stack, Deployment Target, Architecture, Security Rules sections. Context-layer files (agent defs, skills, memory). Active story hardcoded paths. Test harness. Migration comment.
- **E-009-08 handles LATER** (blocked on E-009-07 production runbook): CLAUDE.md Commands section (references the runbook). E-004 epic update. E-002 history entry. E-009 epic closure.

The two epics do not modify the same files except CLAUDE.md -- and they touch different sections. E-033 stories must not modify the Commands section of CLAUDE.md.

### Design principle applied
Per the user's stated preference:
- **CLAUDE.md and code comments** describe current implemented reality
- **Epics and stories** describe future work until that work is done
- **Archived files** are frozen historical records and are not modified

## Goals
- CLAUDE.md accurately describes the implemented stack (FastAPI + SQLite + Docker + Cloudflare Tunnel)
- All active story files and context-layer files use workspace-relative paths, not machine-specific absolute paths
- FastAPI test files complete reliably without hanging
- The existing migration comment accurately describes what the file contains

## Non-Goals
- Updating the CLAUDE.md Commands section (that depends on the production runbook from E-009-07; stays in E-009-08)
- Updating E-004's Technical Notes (stays in E-009-08)
- Updating E-002's History (stays in E-009-08)
- Rewriting the migration schema itself (that's E-003-01)
- Updating `src/api/db.py` query patterns (that will change when E-003-01 rewrites the schema)
- Fixing archived files or completed research artifacts (they are frozen historical records)
- Adding new tests or new features

## Success Criteria
- A grep for "Cloudflare D1" or "Cloudflare Workers" in CLAUDE.md returns zero results
- A grep for "Cloudflare secrets" in CLAUDE.md returns zero results
- A grep for `/Users/jason/Documents/code/baseball-crawl` in all active epic story files (under `/epics/`) returns zero results
- A grep for `/Users/jason/Documents/code/baseball-crawl` in all `.claude/` context-layer files returns zero results
- `pytest tests/test_api_health.py tests/test_dashboard.py` completes within 30 seconds (no hanging)
- The `001_initial_schema.sql` header comment no longer claims the schema was "designed per E-003"

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-033-01 | Update CLAUDE.md stack description to match implemented reality | DONE | None | claude-architect |
| E-033-02 | Fix hardcoded paths in context-layer files | DONE | None | claude-architect |
| E-033-03 | Fix hardcoded paths in active epic story files | DONE | None | general-dev |
| E-033-04 | Fix FastAPI test harness lifecycle and migration comment | DONE | None | general-dev |

## Technical Notes

### CLAUDE.md sections requiring changes (E-033-01)
The following sections have stale references. The corrections are based on the E-009 decision record at `/.project/decisions/E-009-decision.md` and the implemented stack (E-009-02 through E-009-06, all DONE).

**Deployment Target (line 33):**
Current: `- **Cloudflare**: D1 (SQLite database), Workers (API/ETL), Pages (dashboards when ready), KV/R2 (caching/raw storage as needed)`
Replace with: Stack summary matching implemented reality (FastAPI + SQLite + Docker Compose + Cloudflare Tunnel/Access on home Linux server).

**Tech Stack (lines 46-49):**
Current: Cloudflare D1, Cloudflare Workers, TypeScript/JavaScript for Workers and Pages
Replace with: FastAPI + Jinja2 (Python), SQLite (host-mounted, WAL mode), Docker Compose, Cloudflare Tunnel + Zero Trust Access

**Architecture (line 139):**
Current: `Credential management: environment variables for local dev, Cloudflare secrets for production`
Replace with: `Credential management: environment variables via .env files (local and production)`

**Security Rules (line 144):**
Current: `Use Cloudflare secrets/environment variables for production`
Replace with: `Use environment variables via .env files for production (Docker Compose reads .env automatically)`

**Scope of E-033-01:** ONLY the sections listed above. Do NOT touch the Commands section, App Troubleshooting section, or any other section. Those are either already correct or owned by E-009-08.

### Context-layer files with hardcoded paths (E-033-02)
Files in `.claude/` that contain `/Users/jason/Documents/code/baseball-crawl/`:

1. `.claude/agents/claude-architect.md`
2. `.claude/agents/general-dev.md`
3. `.claude/agents/api-scout.md`
4. `.claude/agents/data-engineer.md`
5. `.claude/agent-memory/claude-architect/MEMORY.md`
6. `.claude/agent-memory/claude-architect/agent-blueprints.md` (also has stale D1 references)
7. `.claude/skills/filesystem-context/SKILL.md`
8. `.claude/skills/context-fundamentals/SKILL.md`

**Replacement pattern:** All paths should use workspace-relative paths (e.g., `/epics/E-NNN-slug/E-NNN-SS.md` or `epics/E-NNN-slug/E-NNN-SS.md`). Do NOT use a different absolute path like `/workspaces/baseball-crawl/` -- that is equally non-portable. Use project-root-relative paths.

**Additional fix in `agent-blueprints.md`:** Lines 65 and 77 reference "Cloudflare D1" -- update to "SQLite" per the E-009 decision.

### Active story files with hardcoded paths (E-033-03)
Files in `/epics/` that contain `/Users/jason/Documents/code/baseball-crawl/`:

1. `epics/E-023-auth-permissions/E-023-01.md` (2 occurrences -- Technical Approach reference files)
2. `epics/E-023-auth-permissions/E-023-02.md` (2+ occurrences)
3. `epics/E-023-auth-permissions/E-023-03.md` (occurrences in reference files)
4. `epics/E-023-auth-permissions/E-023-04.md` (4 occurrences -- Technical Approach reference files)
5. `epics/E-023-auth-permissions/E-023-05.md` (5 occurrences)
6. `epics/E-009-tech-stack-redesign/E-009-08.md` (6 occurrences -- Files to Create or Modify)
7. `epics/E-009-tech-stack-redesign/E-009-01.md` (1 occurrence -- Notes section)

Also in `.project/decisions/E-009-decision.md` (4 occurrences in Research Artifacts section) -- this is a finalized decision record. Include it in scope since it's still actively referenced by agents.

**Replacement pattern:** Same as E-033-02. Use project-root-relative paths.

**Files NOT in scope:** Research spikes (E-009-R-01 through R-07) are DONE artifacts. Archived files are frozen. These are left as-is.

### Test harness fix (E-033-04)
**Problem:** `TestClient(app)` starts the ASGI lifespan. Without the context manager (`with TestClient(app) as client:`), the lifespan may not shut down cleanly, causing tests to hang.

**Fix pattern:**
```python
# Before (problematic):
client = TestClient(app)
response = client.get("/health")

# After (correct):
with TestClient(app) as client:
    response = client.get("/health")
```

Files to fix:
- `tests/test_api_health.py` -- 4 test methods create TestClient inline
- `tests/test_dashboard.py` -- `seeded_client` fixture and `test_health_endpoint_unaffected` method

Additionally: add a pytest timeout to `pyproject.toml` or `pytest.ini` so test hangs fail fast instead of hanging indefinitely. A 30-second per-test timeout is reasonable.

**Migration comment fix (also E-033-04):** In `migrations/001_initial_schema.sql`, change the header comment from "Schema designed per E-003 (Data Model) spec" to "Initial schema (pre-E-003 rewrite). E-003-01 will rewrite this file." This is a one-line comment change -- bundled into this story because it touches the same "current vs. future state" concern and is too small for its own story.

### Parallel execution safety
- E-033-01 and E-033-02 both route to claude-architect. E-033-01 modifies `CLAUDE.md`. E-033-02 modifies `.claude/agents/*.md`, `.claude/agent-memory/claude-architect/*`, `.claude/skills/**`. No file overlap -- safe to run in parallel.
- E-033-03 modifies files in `epics/` and `.project/decisions/`. No overlap with E-033-01 or E-033-02.
- E-033-04 modifies `tests/test_api_health.py`, `tests/test_dashboard.py`, `migrations/001_initial_schema.sql`, and optionally `pyproject.toml`. No overlap with any other story.
- All four stories can run in parallel.

## Open Questions
None.

## History
- 2026-03-03: Created as READY. All four findings verified by file analysis. Stories written with specific file lists and testable ACs. No expert consultation needed -- changes are mechanical. Scope deliberately avoids overlap with E-009-08.
- 2026-03-03: Dispatched all 4 stories in parallel. E-033-01 and E-033-02 to claude-architect (context-layer files). E-033-03 and E-033-04 to general-purpose (epic/story files, tests, migration). No file conflicts -- full parallel execution.
- 2026-03-03: All 4 stories completed and verified. E-033-01: CLAUDE.md Deployment Target, Tech Stack, Architecture, Security Rules sections corrected (grep returns 0 for stale Cloudflare D1/Workers/secrets references). E-033-02: 8 context-layer files fixed (hardcoded paths removed, D1->SQLite in agent-blueprints.md). E-033-03: 7 active story files + 1 decision record fixed (hardcoded paths removed). E-033-04: TestClient context managers in 2 test files, pytest-timeout added, migration comment corrected, all 16 tests pass in 0.44s. Epic marked COMPLETED. Documentation assessment: no documentation impact (changes were mechanical corrections to existing docs/config, no new features, endpoints, schema changes, or architecture changes).
