# Admin & Developer Documentation

This directory contains documentation for system operators and developers working on the baseball-crawl project.

## Contents

| Document | Description |
|----------|-------------|
| [Architecture](architecture.md) | System overview, components, data flow, directory structure, and tech stack. |
| [Getting Started](getting-started.md) | Prerequisites, setup, running the stack, seeding the database, and running tests. |
| [Credential Refresh](credential-refresh.md) | Step-by-step guide for fixing expired or broken GameChanger credentials. Start here when auth fails. |
| [Operations](operations.md) | Deployment, credential rotation, backups, troubleshooting, and monitoring. |
| [Agent Guide](agent-guide.md) | The AI agent ecosystem: what it is, how to work with it, and how to request work. |
| [Codex Guide](codex-guide.md) | Project-local Codex bootstrap, runtime-state split, trust model, and smoke checks. |
| [Terminal Guide](terminal-guide.md) | ZSH and tmux setup: what changed, ZSH for bash users, tmux key bindings, connecting from iTerm2, and operating modes. |

## Related Documentation

These documents live outside `docs/admin/` but are referenced throughout:

- [GameChanger API Spec](../api/README.md) -- Endpoint reference for the GameChanger API (maintained by api-scout). Per-endpoint files in `docs/api/endpoints/`.
- [HTTP Integration Guide](../http-integration-guide.md) -- How to use the shared HTTP session factory.
- [Cloudflare Access Setup](../cloudflare-access-setup.md) -- One-time Cloudflare Tunnel and Zero Trust configuration.
- [Database Backup & Restore](../database-restore.md) -- Backup and restore procedures for the SQLite database.
- [Safe Data Handling](../safe-data-handling.md) -- PII scanning and credential safety policies.

---

*Last updated: 2026-03-09 | Story: E-081-04*
