---
paths:
  - ".devcontainer/**"
  - "Dockerfile"
  - "docker-compose*.yml"
  - "docker-compose*.yaml"
---

# Devcontainer Strategy

**Governing principle: Simple first. Complexity as needed.**

The devcontainer exists to give every contributor (human or agent) a reproducible development environment with zero manual setup. It should be the thinnest possible layer that achieves that goal.

## Base Image

Use Microsoft devcontainer images with Ubuntu as the base OS:

```
"image": "mcr.microsoft.com/devcontainers/base:ubuntu"
```

Do not pin to a specific Ubuntu version unless a real compatibility issue forces it. The `base:ubuntu` tag tracks the current LTS, which is what we want.

## Installing Dependencies

### Apt Packages

Use devcontainer features to install apt packages. The preferred feature is from rocker-org:

```json
"features": {
  "ghcr.io/rocker-org/devcontainer-features/apt-packages:1": {
    "packages": "jq,curl"
  }
}
```

Source: https://github.com/rocker-org/devcontainer-features/tree/main/src/apt-packages

An alternative from the devcontainers-extra community is also acceptable:

```json
"features": {
  "ghcr.io/devcontainers-extra/features/apt-packages:1": {
    "packages": "jq,curl"
  }
}
```

Source: https://github.com/devcontainers-extra/features/tree/main/src/apt-packages

Both accept a comma-separated `packages` string. Use one or the other, not both.

Do not shell out to `apt-get` in postCreateCommand unless a feature genuinely cannot handle the case.

### IMPORTANT: Features That Do NOT Exist

The official devcontainers/features registry (`ghcr.io/devcontainers/features/`) does NOT include an apt installer feature. There is no such thing as:

- `ghcr.io/devcontainers/features/apt:1` -- DOES NOT EXIST
- `ghcr.io/devcontainers/features/apt-packages:1` -- DOES NOT EXIST
- `ghcr.io/devcontainers/features/apt-get:1` -- DOES NOT EXIST

These have been hallucinated by AI in prior interactions. Do not use them. They will fail at container build time with a "feature not found" error. Always verify feature identifiers against the registry at https://containers.dev/features before adding them to devcontainer.json.

The only apt-related features that actually exist are from **rocker-org** and **devcontainers-extra** (listed above).

### Claude Code

Install Claude Code via `postCreateCommand` using the official installer script:

```
"postCreateCommand": "curl -fsSL https://claude.ai/install.sh | bash"
```

Do NOT install Claude Code via a devcontainer feature. The official installer is the supported path and ensures we get the latest version on each container build.

### Other Tools

Use devcontainer features (from the official registry or rocker-org) for standard tooling like GitHub CLI, Python, Node, etc. Only fall back to manual install scripts when no feature exists.

## Host Integration

### SSH / GitHub Access

Forward the host's SSH auth socket into the container so GitHub operations (clone, push, pull) work transparently using the host's SSH credentials:

```json
"remoteEnv": {
  "SSH_AUTH_SOCK": "${localEnv:SSH_AUTH_SOCK}"
}
```

This avoids copying private keys into the container. The host's SSH agent handles all authentication. Devcontainers automatically maps the socket path -- no explicit mount is needed.

### Mount ~/.claude

Mount the host user's `~/.claude` directory into the container so Claude Code picks up user-level settings, memory, and credentials:

```json
"mounts": [
  "source=${localEnv:HOME}/.claude,target=/home/vscode/.claude,type=bind"
]
```

Devcontainers handles UID/GID mapping and SSH socket forwarding automatically -- no special configuration needed beyond the `remoteEnv` entry above.

## Docker Compose Stack

The project runs a three-service stack via `docker-compose.yml`:

| Service | Purpose | Port |
|---------|---------|------|
| **app** | FastAPI application (Python, uvicorn) | `127.0.0.1:8001` (direct, loopback only), `localhost:8000` (via Traefik) |
| **traefik** | Reverse proxy, dashboard at `localhost:8180` | `localhost:8000` (app traffic), `localhost:8180` (dashboard) |
| **cloudflared** | Cloudflare Tunnel for production access | No host port (outbound only) |

The devcontainer and the compose stack are separate concerns:
- The **devcontainer** is the development environment (editor, CLI tools, Claude Code).
- The **compose stack** runs the application services. Agents interact with it via `docker compose` commands from the devcontainer shell.

See the "App Troubleshooting" section in CLAUDE.md for operational commands (health checks, logs, rebuild after changes).

## Maintenance

When editing `devcontainer.json`:
- Test the container builds cleanly: `devcontainer build --workspace-folder .`
- Verify Claude Code installs and launches correctly inside the container
- Verify SSH agent forwarding works for git operations
- Verify `~/.claude` mount provides expected settings and memory
