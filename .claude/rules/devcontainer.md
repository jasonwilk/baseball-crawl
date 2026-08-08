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

## Browser-Test Infrastructure (Headless Chromium)

Some closure-gate tests render a report page in a real browser (Playwright + headless Chromium) to verify print/layout behavior a headless HTTP assertion cannot reach. Chromium is a browser binary, **not** a pip artifact, so the `playwright` Python package (in `requirements-dev.txt`) is necessary but not sufficient -- the binary is installed separately.

### Install

The post-create flow installs chromium **only** (not firefox/webkit, ~150MB one-time; worktrees share the container FS) immediately after the dev-lockfile install:

```
pip install -r requirements-dev.txt && playwright install --with-deps chromium
```

This lives inline in `.devcontainer/devcontainer.json`'s `postCreateCommand` chain (matching the existing inline post-create idiom), sequenced right after `pip install -r requirements-dev.txt`. A freshly built container therefore has the browser binary available. The post-create flow deliberately sets **no** run-enabling env marker (see fail-closed convention below).

### Boundary: dev / main-checkout only, NOT a CI gate

This browser test is a **dev / main-checkout** capability, not a CI gate. The boundary mirrors the runtime smoke's live-only boundary: just as `bb report generate` needs the dev-only host-mounted `./data/app.db` (absent from worktrees/CI), the browser test needs the chromium binary that only the devcontainer post-create flow installs.

- It is **authoritative at lifecycle step 4 VERIFY** -- the full `pytest tests/` run a chunk owes (in the main checkout, where the container's chromium is present) exercises it.
- It is **NOT wired into any CI workflow.** Do not add a CI job that installs chromium to run it; the full-suite run in the live devcontainer is the intended enforcement point.

### Fail-closed test convention + `SKIP_BROWSER_TESTS` opt-out

The browser test is **fail-closed**: on the scoped dev / main-checkout environment it always attempts to launch Chromium and hard-**FAILS** if the binary is absent. It never silently no-ops to green. This is deliberate -- a postCreate-set "browser available" marker would not reach the non-interactive closure pytest, so a marker-gated skip would pass vacuously (green-with-skipped-test) and defeat the test's purpose.

The **only** skip path is an explicit operator opt-**out** environment variable, the exact literal:

```
SKIP_BROWSER_TESTS
```

Set it (to any non-empty value) in a legitimately chromium-less contributor environment to skip the browser test. Absent that opt-out, a missing chromium binary is a hard failure, not a skip. (`SKIP_BROWSER_TESTS` is a cross-story pinned literal -- the browser test reads this exact token; do not rename it.)

### Install Footguns

**Footgun 1 -- the currently-running container is NOT updated (one-time operator step).** `postCreateCommand` only fires on a *future* container build; it does **not** install chromium into the container that is already running. To make the browser test pass in the live devcontainer without a rebuild, run this one-time operator step:

```
pip install -r requirements-dev.txt && playwright install --with-deps chromium
```

**This doc is the single source of truth for that operator step.** Other artifacts (e.g. the browser-test module) point *here* rather than restating the command -- do not create a second copy elsewhere.

**Footgun 2 -- a dependency reinstall gets the package but not the binary.** `pip install -r requirements-dev.txt` installs the playwright **package** but **not** the chromium **binary** -- the binary comes only from `playwright install --with-deps chromium` (the post-create flow, or the Footgun 1 operator step), never from a pip reinstall. If the browser test errors on a missing binary, run the Footgun 1 step.

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
