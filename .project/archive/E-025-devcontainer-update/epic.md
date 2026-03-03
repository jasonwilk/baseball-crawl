# E-025: Devcontainer Update -- Align with Python/Docker Stack

## Status
`COMPLETED`

## Overview
The `.devcontainer/devcontainer.json` was created before the E-009 tech stack decision and does not
reflect the current stack. It has no Python runtime and no Docker access for running
`docker compose up`. This epic updates the devcontainer to match the production stack: Python 3.12,
Docker-in-Docker, and the correct tooling for both human developers and AI coding assistants working
in Codespaces or VS Code Remote Containers.

## Background & Context

### What Exists Today
The current devcontainer installs:
- Base image: `mcr.microsoft.com/devcontainers/base:ubuntu`
- Node.js (present for OpenAI Codex CLI -- `@openai/codex` is an npm package that requires Node.js)
- `git`, `curl`, `jq` via apt
- Claude Code CLI (`curl` install) and OpenAI Codex CLI (`npm i -g @openai/codex`) via `postCreateCommand`
- VS Code extensions: Python, Claude Code, ChatGPT, CSV viewer
- Bind mount of `~/.claude` for CLI config
- SSH agent forwarding

What it is missing:
- Python 3.12 runtime (tests, linting, and local scripts require Python)
- Docker access (needed for `docker compose up` -- the primary dev command)
- Python dependencies installation (`pip install -r requirements.txt`)

### Node.js and OpenAI Codex -- Clarification (2026-03-03)
Node.js is NOT unused -- it is required by the OpenAI Codex CLI (`@openai/codex`), which is an npm
package. The user confirmed Node.js was added specifically for Codex support and should be kept as
long as Codex needs it. Since Codex CLI has no Python-based alternative, Node.js must remain in the
devcontainer to support it. The epic scope is updated accordingly: **add Python 3.12 and
Docker-in-Docker alongside the existing Node.js**, rather than replacing Node.js.

### Why Docker-in-Docker (Not Socket Forwarding)
Two approaches exist for running Docker inside a devcontainer:

**Docker-in-Docker** (`docker-in-docker` devcontainer feature): Runs a separate Docker daemon inside
the container. Containers created by `docker compose up` are children of this inner daemon.
- Volume paths in `docker-compose.yml` resolve relative to the devcontainer filesystem (correct)
- Clean isolation from the host Docker daemon
- Recommended by the devcontainers spec for most use cases
- No file permission issues with the Docker socket on macOS

**Docker socket forwarding** (bind-mount `/var/run/docker.sock`): Shares the host Docker daemon.
Containers are siblings, not children.
- Volume paths in `docker-compose.yml` resolve relative to the host filesystem (breaks when
  the workspace is inside the devcontainer at `/workspaces/baseball-crawl` but the host path
  is `/Users/jason/Documents/code/baseball-crawl`)
- Socket permission issues on macOS are a common pain point
- Faster startup (no inner daemon) but more fragile

**Decision: Docker-in-Docker.** It is the correct choice for this project because `docker-compose.yml`
uses relative volume mounts (`./data:/app/data`, `./migrations:/app/migrations`) that must resolve
inside the devcontainer workspace, not on the macOS host.

### Expert Consultation
No expert consultation required. The devcontainer is development environment configuration, not
agent infrastructure or domain logic. The Docker-in-Docker vs socket forwarding decision follows
directly from how the project's `docker-compose.yml` uses relative volume paths. The Python feature
selection is determined by the project's requirements.txt and Python 3.12 Dockerfile base image.

### Relationship to E-009
E-009 open question #10 identified this devcontainer drift. This epic is the follow-on that resolves
it. E-009 remains ACTIVE (stories 07 and 08 still TODO) but this epic is independent -- it does not
block or depend on E-009's remaining stories.

## Goals

- The devcontainer provides Python 3.12 for running tests, linters, and scripts without Docker
- The devcontainer provides Docker-in-Docker for running `docker compose up`
- Node.js is retained for OpenAI Codex CLI support
- `postCreateCommand` installs Python dependencies from `requirements.txt` (in addition to existing
  Claude Code and Codex CLI installs)
- A developer (human or AI) can clone the repo, open in Codespaces or Remote Containers, and have a
  fully working environment within minutes

## Non-Goals

- Modifying the `docker-compose.yml` or `Dockerfile` (those are correct as-is)
- Adding CI/CD integration or GitHub Actions configuration
- Creating a separate production devcontainer profile
- Changing how Claude Code sessions work on the host machine (they already work; this is about
  Codespaces/Remote Containers)
- Multi-architecture support (arm64/amd64) -- Docker-in-Docker handles this transparently

## Success Criteria

1. `devcontainer.json` uses Python 3.12, Docker-in-Docker, and Node.js features
2. `python --version` inside the devcontainer reports Python 3.12.x
3. `docker compose up` succeeds inside the devcontainer and the app responds at `localhost:8000`
4. `pytest` runs successfully inside the devcontainer (with Python deps installed)
5. Existing bind mounts (`.claude` config, SSH agent) continue to work
6. `postCreateCommand` installs Python deps, Claude Code CLI, and Codex CLI without manual intervention
7. `node --version` reports a working Node.js runtime (for Codex CLI)

## Stories

| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-025-01 | Update devcontainer.json for Python/Docker stack | DONE | None | general-dev |
| E-025-02 | Verify devcontainer builds and runs the full stack | DONE | E-025-01 | general-dev |

## Technical Notes

### Target devcontainer.json Shape

The updated devcontainer should use these devcontainer features:
- `ghcr.io/devcontainers/features/python:1` with `version: "3.12"` -- provides Python runtime (NEW)
- `ghcr.io/devcontainers/features/docker-in-docker:2` -- provides Docker daemon + Docker Compose (NEW)
- `ghcr.io/devcontainers/features/node:1` -- Node.js runtime for OpenAI Codex CLI (KEEP)
- `ghcr.io/rocker-org/devcontainer-features/apt-packages:1` with `packages: "git,curl,jq"` (KEEP)

Base image: Keep `mcr.microsoft.com/devcontainers/base:ubuntu` (the Python feature adds Python
on top of this).

### postCreateCommand Update

Current: `curl -fsSL https://claude.ai/install.sh | bash && npm i -g @openai/codex`

Updated: `curl -fsSL https://claude.ai/install.sh | bash && npm i -g @openai/codex && pip install -r requirements.txt`

The existing Claude Code CLI install and Codex CLI install are kept. Python dependencies are added
via `pip install -r requirements.txt` so that `pytest` and imports work outside Docker.

### Port Forwarding

The devcontainer should forward port 8000 (FastAPI app via Traefik) and optionally 8080 (Traefik
dashboard). Add to `forwardPorts`: `[8000, 8080]`.

Note: With Docker-in-Docker, ports exposed by `docker compose up` are exposed inside the devcontainer.
The devcontainer's `forwardPorts` then maps them to the host. This two-hop forwarding is handled
automatically by VS Code / Codespaces.

### Existing Mounts and Config to Preserve

These must remain unchanged:
- `source=${localEnv:HOME}/.claude,target=/home/vscode/.claude,type=bind` -- Claude CLI config
- `sshAgent: "local"` -- SSH agent forwarding for git operations
- `remoteUser: "vscode"` -- standard devcontainer user
- `remoteEnv.PATH` extension for `/home/vscode/.local/bin` -- needed for pip-installed binaries

### VS Code Extensions

Keep: `ms-python.python`, `Anthropic.claude-code`, `openai.chatgpt`, `ReprEng.csv`
Add: `ms-python.debugpy` (Python debugger, commonly paired with ms-python.python)

### File Reference

- Current devcontainer: `/Users/jason/Documents/code/baseball-crawl/.devcontainer/devcontainer.json`
- Docker Compose: `/Users/jason/Documents/code/baseball-crawl/docker-compose.yml`
- Dockerfile: `/Users/jason/Documents/code/baseball-crawl/Dockerfile`
- Requirements: `/Users/jason/Documents/code/baseball-crawl/requirements.txt`

## Open Questions

None. The architecture is straightforward and all decisions are resolved in Technical Notes.

## History
- 2026-03-03: Created as READY. Follows from E-009 open question #10 (devcontainer configuration
  drift). No expert consultation required -- development environment configuration with clear
  inputs from the existing stack. Docker-in-Docker selected over socket forwarding due to relative
  volume path resolution requirements.
- 2026-03-03: Clarified Node.js dependency. User confirmed Node.js was added for OpenAI Codex CLI
  support. Since `@openai/codex` is an npm package requiring Node.js and has no Python alternative,
  Node.js must be retained. Epic scope changed from "replace Node.js with Python" to "add Python
  and Docker-in-Docker alongside existing Node.js." Updated Goals, Success Criteria, Technical Notes,
  and both story files.
