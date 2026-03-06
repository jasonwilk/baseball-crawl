# Operational Boundary Catalog

Agents hallucinate about operational boundaries because they lack grounding in the physical topology of the system. This file catalogs known boundaries and the defenses in place.

## Hardening Pattern

Every boundary gets the same three-layer defense:
1. **CLAUDE.md section** -- ambient context, always loaded, describes what runs where
2. **Glob-triggered rule** -- `.claude/rules/`, fires when agents touch files near the boundary
3. **Architect memory entry** -- so the pattern is not reinvented each time

Not every boundary needs all three layers. Use judgment: if agents rarely touch the relevant files, a CLAUDE.md note may suffice. If agents frequently interact with boundary-adjacent files, the glob-triggered rule is essential.

## Known Boundaries

### 1. Mac Host vs. Devcontainer (Proxy)
- **What**: mitmproxy runs on the Mac host, not in the devcontainer. Agents cannot run proxy lifecycle commands.
- **Risk**: Agents see `proxy/` files and assume they can execute them.
- **Defenses**: CLAUDE.md "Proxy Boundary" section, `.claude/rules/proxy-boundary.md` (glob: `proxy/**`), architect memory.
- **Date hardened**: 2026-03-06

### 2. Devcontainer vs. Compose Stack
- **What**: The devcontainer is the dev environment; the compose stack (app, traefik, cloudflared) runs separately. Agents interact via `docker compose` commands, not by running app code directly.
- **Risk**: Low -- agents generally understand this. Documented in `.claude/rules/devcontainer.md` and CLAUDE.md "App Troubleshooting."
- **Defenses**: CLAUDE.md "App Troubleshooting" section, `.claude/rules/devcontainer.md` (glob: `.devcontainer/**`, `Dockerfile`, `docker-compose*.yml`).
- **Date hardened**: pre-existing (E-027)

### 3. Authenticated vs. Public API
- **What**: GameChanger has two API tiers with different auth requirements, different URL patterns, and different field names.
- **Risk**: Agents might send auth headers to public endpoints or omit them from authenticated ones, or assume URL patterns are consistent across tiers.
- **Defenses**: CLAUDE.md "GameChanger API" section (authenticated vs public bullets), `docs/gamechanger-api.md` (full spec), agent memory files for api-scout/software-engineer/data-engineer.
- **Date hardened**: 2026-03-04 (public-team-profile ingest)

### 4. Sensitive vs. Non-Sensitive Data (PII)
- **What**: Credentials, tokens, player PII must never appear in code, logs, or commits.
- **Risk**: Agents might log API responses containing tokens, or commit .env files.
- **Defenses**: Two-layer deterministic defense (git pre-commit hook + Claude Code PreToolUse hook), `.claude/rules/pii-safety.md` (glob: `src/safety/**`, `.githooks/**`, `.claude/hooks/pii-check.sh`), CLAUDE.md "Security Rules" section.
- **Date hardened**: E-006

### 5. Real vs. Hallucinated Identifiers
- **What**: AI agents hallucinate package names, feature identifiers, and API paths that do not exist.
- **Risk**: Builds fail silently or at runtime when hallucinated identifiers are used.
- **Defenses**: `.claude/rules/devcontainer.md` (documents real vs fake apt feature IDs), architect memory "Known Hallucination Traps" section.
- **Date hardened**: 2026-03-02

## When to Add a New Boundary

Assess during:
- **New infrastructure**: Any time a service, tool, or runtime is added that runs in a different environment than the devcontainer.
- **Ecosystem audits**: Periodic review of agent errors -- if multiple agents make the same wrong assumption, it is likely a missing boundary.
- **Epic completion**: If an epic introduced a new external dependency or changed where something runs.

Ask: "Could an agent reasonably hallucinate about what runs where, what is accessible, or what can call what?" If yes, harden it.
