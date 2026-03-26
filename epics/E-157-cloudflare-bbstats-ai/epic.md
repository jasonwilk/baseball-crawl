# E-157: Cloudflare Production Deployment for bbstats.ai

## Status
`READY`

## Overview
Prepare the baseball-crawl coaching analytics platform for production deployment at **bbstats.ai** via Cloudflare Tunnel. This epic covers Docker Compose production hardening, environment configuration, deployment documentation, and context-layer updates -- producing a production-ready repo that an operator can deploy by following the runbook. Actual tunnel creation, DNS cutover, and go-live are operator actions documented in the runbook but not executed by stories.

## Background & Context
The application stack (FastAPI + Traefik + cloudflared) is already containerized and has been tested in local dev. The Cloudflare infrastructure is partially in place:
- **bbstats.ai** zone exists in Cloudflare with empty DNS records
- An Access application named "bbstats-ai" exists with two active blocking policies that **must be removed** before the tunnel goes live (see TN-3)
- A scoped RW API token is being created (teams:write, access:write, dns_records:edit, zone:read -- scoped to bbstats.ai zone and Jason's account)
- docker-compose.yml already has `cloudflared` service reading `TUNNEL_TOKEN` from env
- docker-compose.override.yml profiles cloudflared out for local dev
- The existing n8n-wilk-io deployment (tunnel -> Traefik -> app) is the reference pattern

**Key decisions (locked by user):**
- Domain: **bbstats.ai**. Tunnel name: **bbstats-ai** (dash convention for all CF resources)
- **No Cloudflare Access auth enforcement** -- the app handles authentication internally via E-023 magic links and passkeys. CF Access is present but not blocking requests.
- Least-privilege security lens throughout
- Full documentation required (ops runbook + context-layer for agents)

**Expert consultation:**
- **SE**: Auth code (`src/api/routes/auth.py`) is fully env-var-driven -- APP_URL, WEBAUTHN_RP_ID, WEBAUTHN_ORIGIN read from env with `baseball.localhost` defaults. No hardcoded production values in `src/`. No CF_ACCESS references in application code. The Traefik Host label (`baseball.localhost`) needs `bbstats.ai` added for production routing.
- **CA**: CLAUDE.md has exactly 2 stale lines (35, 54) referencing "Zero Trust Access for auth." No stale references in `.claude/rules/`, `.claude/skills/`, or `.claude/agents/`. E-157-03 is well-scoped.
- **DE**: WAL mode is already in place. No additional production-specific SQLite settings needed. No DB concerns for this epic.

## Goals
- Production-ready Docker Compose configuration that enables deployment at `https://bbstats.ai` (Traefik dashboard disabled, image pinned, host rule updated)
- `.env.example` updated with bbstats.ai production values and documentation
- Comprehensive deployment documentation updated for the bbstats.ai-specific setup, sufficient for an operator to deploy end-to-end
- Context layer (CLAUDE.md) updated to reflect the production domain and auth model

## Non-Goals
- Cloudflare Access policy enforcement (app handles auth internally; CF Access is present but passive)
- CF Email OTP as auth mechanism (captured as vision signal for future consideration)
- API subdomain routing (no `api.bbstats.ai` -- single domain serves both dashboard and API)
- CI/CD pipeline or automated deployments
- SSL certificate management (Cloudflare handles SSL termination)
- Monitoring, alerting, or observability beyond existing health checks
- CF Access service tokens for crawler M2M auth (not needed since Access is not blocking)
- Production data seeding or database migration beyond what startup already handles

## Success Criteria
- docker-compose.yml is production-safe (no dev-only features in base config) and passes YAML validation
- `.env.example` documents all bbstats.ai production values with clear inline guidance
- Deployment documentation is complete: an operator can follow it end-to-end to create the tunnel, configure DNS, remove Access policies, set env vars, and bring up the stack at `https://bbstats.ai`
- Context layer (CLAUDE.md, agent memory) accurately reflects the production domain and auth model with no stale references

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-157-01 | Production Docker Compose configuration | TODO | None | - |
| E-157-02 | Production deployment documentation update | TODO | E-157-01 | - |
| E-157-03 | Context-layer updates for bbstats.ai | TODO | E-157-01 | - |

## Dispatch Team
- software-engineer
- claude-architect

## Technical Notes

### TN-1: Cloudflare Resource Naming Convention
All Cloudflare resources use the **bbstats-ai** naming convention (domain with dash instead of dot):
- Tunnel name: `bbstats-ai`
- Access application: `bbstats-ai` (existing shell)
- API token: scoped to bbstats.ai zone only

### TN-2: Tunnel Configuration
The tunnel `bbstats-ai` routes traffic as:
```
Internet -> Cloudflare (SSL termination) -> Tunnel bbstats-ai -> traefik:80 -> FastAPI app :8000
```
Public hostname configuration in the tunnel:
| Hostname | Type | URL |
|----------|------|-----|
| bbstats.ai | HTTP | traefik:80 |

DNS: Cloudflare auto-creates a proxied CNAME record for `bbstats.ai` pointing to `<tunnel-uuid>.cfargotunnel.com` when the public hostname is configured via the dashboard.

### TN-3: Auth Model (No CF Access Blocking)
The application handles all authentication internally:
- **Magic links** (E-023): Email-based passwordless login via Mailgun
- **Passkeys** (E-023): WebAuthn/FIDO2 for returning users
- **Admin access**: `ADMIN_EMAIL` env var or `role='admin'` in database

Cloudflare Access application `bbstats-ai` exists with **two active blocking policies** (confirmed via MCP):
1. **"WARP Allow (jason@wilkinson.nu)"** — allow rule for jason@wilkinson.nu only
2. **"Google Auth Policy (jason@wilkinson.nu)"** — allow rule requiring jason@wilkinson.nu via Google Auth

**These policies MUST be removed before the tunnel goes live.** Once DNS points bbstats.ai to the tunnel, CF Access will enforce these policies and block all traffic except Jason's. Coaches cannot access the dashboard.

**Required action**: Remove both named policies from the `bbstats-ai` Access app (Zero Trust → Access → Applications → bbstats-ai → Policies). This preserves the Access app shell for future CF Email OTP adoption (vision signal) while allowing all traffic through to the app's internal auth.

Alternative options (not recommended):
- **Add a Bypass:Everyone policy** (explicitly passes all traffic through -- but leaves stale allow policies in place, confusing)
- **Delete the Access app** entirely (simplest, but must recreate if CF Access is later needed)

Once the two policies are removed and the Access app is policy-free:
- No `CF-Access-Client-Id` / `CF-Access-Client-Secret` headers needed
- No service tokens needed for crawler M2M access
- The app's `/health` endpoint is publicly accessible (no bypass policy needed)

### TN-4: Traefik Host Routing (Dual-Host)
The Traefik router rule must accept both hostnames:
- `baseball.localhost` -- local dev (existing)
- `bbstats.ai` -- production

Traefik supports OR conditions in host rules. The label in docker-compose.yml becomes a dual-host rule serving both environments from the same compose file.

### TN-5: Production Hardening in Docker Compose
Four changes to docker-compose.yml for production readiness:
1. **Traefik insecure API**: `--api.insecure=true` exposes the Traefik dashboard without auth. Must be removed from the base config and moved to the override for dev only.
2. **Traefik dashboard port**: `8180:8080` mapping exposes the dashboard on the host. Must be removed from the base config and moved to the override.
3. **Traefik app port**: `8000:80` mapping exposes Traefik to the host network, bypassing the tunnel. In production, all traffic arrives via tunnel → traefik:80 (Docker-internal). Must be moved to the override for dev only (least-privilege: no host port bindings in production except the app's direct `127.0.0.1:8001:8000` for local health checks).
4. **cloudflared image pinning**: Pin to a specific version tag instead of `latest` to prevent unexpected upstream changes in production.

The base docker-compose.yml should be production-safe. Dev-only features (Traefik dashboard, insecure API, Traefik host port) go in docker-compose.override.yml.

**Docker Compose `command` override semantics**: When the override file specifies a `command` for a service, Docker Compose **replaces** the entire command array -- it does NOT merge. The override must duplicate all base command flags plus any dev-only additions. For example, if the base traefik `command` has three flags and the override adds `--api.insecure=true`, the override must list all four flags (the three base flags + the insecure flag). Omitting the base flags silently drops them.

**Traefik image tag**: `traefik:v3` is a major-version floating tag (any v3.x release). This is accepted because Traefik follows semver within v3.x, making breaking changes unlikely. This is a different risk profile from `cloudflared:latest` (which floats across major versions). If Traefik v3 stability becomes a concern, pin to a specific minor version (e.g., `traefik:v3.3`).

### TN-6: Production .env Values
Required production values in `.env`:

| Variable | Production Value | Notes |
|----------|-----------------|-------|
| `APP_ENV` | `production` | Enables production logging, disables debug features |
| `APP_URL` | `https://bbstats.ai` | Used for magic link URLs |
| `WEBAUTHN_RP_ID` | `bbstats.ai` | Must match browser hostname |
| `WEBAUTHN_ORIGIN` | `https://bbstats.ai` | Must be HTTPS |
| `CLOUDFLARE_TUNNEL_TOKEN` | `<token>` | From tunnel creation |
| `MAILGUN_API_KEY` | `<key>` | Required for email delivery |
| `MAILGUN_DOMAIN` | `mg.bbstats.ai` (or existing domain) | Sending domain |
| `MAILGUN_FROM_EMAIL` | `noreply@mg.bbstats.ai` | From address |
| `ADMIN_EMAIL` | Jason's email | Bootstrap admin access |

Must NOT be set in production:
- `DEV_USER_EMAIL` (app fails to start if set with `APP_ENV=production`)

**Mailgun DNS prerequisite**: If using a new sending domain (e.g., `mg.bbstats.ai`), Mailgun requires DNS verification (SPF and DKIM TXT records on the sending subdomain) before emails will deliver. Without verification, magic link emails fail silently. If using an already-verified Mailgun domain, no additional DNS setup is needed.

No longer needed (CF Access not blocking):
- `CF_ACCESS_CLIENT_ID` / `CF_ACCESS_CLIENT_SECRET`

### TN-7: Scoped Cloudflare API Token
A least-privilege API token is being created with:
- **Permissions**: Account:Teams:Write, Account:Access:Write, Zone:DNS Records:Edit, Zone:Zone:Read
- **Zone scope**: bbstats.ai only
- **Account scope**: Jason@wilkinson.nu's Account (9c7859820fa98ff0b6e91401c7b9736b)

This token is stored in `.env` as `CLOUDFLARE_API_TOKEN` for programmatic Cloudflare API management (e.g., scripts, direct API calls). It is NOT used by the Cloudflare MCP server in `.mcp.json` -- the MCP uses OAuth (browser-based authentication). It is also NOT the tunnel token. The three credentials serve different purposes:
- `CLOUDFLARE_API_TOKEN`: Management token for programmatic CF API calls (stored in `.env`)
- `CLOUDFLARE_TUNNEL_TOKEN`: Runtime token that cloudflared uses to connect to the tunnel (stored in `.env`)
- Cloudflare MCP: OAuth-based, authenticates via browser popup (configured in `.mcp.json`, no `.env` variable)

## Open Questions
- What cloudflared version should be pinned? (SE to determine current stable version during implementation)

## History
- 2026-03-25: Created. Vision signal captured for CF Email OTP future auth option.
- 2026-03-26: Set to READY after 6 review passes (38 findings, 31 accepted, 7 dismissed).

### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 — CR spec audit | 8 | 6 | 2 |
| Internal iteration 1 — Holistic team | 15 | 11 | 4 |
| Codex iteration 1 | 6 | 5 | 1 |
| Codex iteration 2 | 5 | 5 | 0 |
| Internal iteration 2 — CR spec audit | 2 | 2 | 0 |
| Internal iteration 2 — Holistic team | 2 | 2 | 0 |
| **Total** | **38** | **31** | **7** |
