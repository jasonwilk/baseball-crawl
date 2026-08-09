# Admin & Developer Documentation

This directory contains documentation for system operators and developers working on the baseball-crawl project.

## Contents

| Document | Description |
|----------|-------------|
| [Architecture](architecture.md) | System overview, components, data flow, directory structure, and tech stack. |
| [Getting Started](getting-started.md) | Prerequisites, setup, running the stack, seeding the database, and running tests. |
| [Post-Reset Guide](post-reset-guide.md) | End-to-end workflow from `bb db reset` to a working local environment with real GameChanger data. |
| [Credential Refresh](credential-refresh.md) | Step-by-step guide for fixing expired or broken GameChanger credentials. Start here when auth fails. |
| [Operations](operations.md) | Deployment, credential rotation, backups, troubleshooting, and monitoring. Includes admin UI reference: reports management and user roles. |
| [Production Deployment](production-deployment.md) | End-to-end runbook: bare Linux server to a running stack at `https://bbstats.ai` via Docker Compose and Cloudflare Tunnel. |
| [Cloudflare Access Setup](cloudflare-access-setup.md) | Cloudflare Tunnel creation, DNS, and Zero Trust Access configuration for the bbstats.ai deployment. |
| [Codex Guide](codex-guide.md) | Project-local Codex bootstrap, runtime-state split, trust model, and smoke checks. |
| [Terminal Guide](terminal-guide.md) | ZSH and tmux setup: what changed, ZSH for bash users, tmux key bindings, connecting from iTerm2, and operating modes. |

## Related Documentation

These documents live outside `docs/admin/` but are referenced throughout:

- [GameChanger API Spec](../api/README.md) -- Endpoint reference for the GameChanger API (maintained by api-scout). Per-endpoint files in `docs/api/endpoints/`.
- [HTTP Integration Guide](../http-integration-guide.md) -- How to use the shared HTTP session factory.
- [Database Backup & Restore](../database-restore.md) -- Backup and restore procedures for the SQLite database.
- [Safe Data Handling](../safe-data-handling.md) -- PII scanning and credential safety policies.

---

*Last updated: 2026-08-09 | Source: 2026-08-09-docs-retired-workflow-sweep (dropped the Agent Guide row -- the page documented the retired PM/epic/dispatch agent ecosystem and was deleted; the live process is `CLAUDE.md`), E-143 (original), E-239 (reports-first reframe), E-255-05 (Truth Sweep: added Production Deployment and Cloudflare Access Setup to Contents now that both runbooks live in docs/admin/, and removed the latter's stale Related Documentation entry)*
