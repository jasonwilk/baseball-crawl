---
paths:
  - "proxy/**"
---

# Proxy Boundary -- Host vs. Container

The `proxy/` directory contains mitmproxy configuration and scripts that run on the **Mac host machine**, NOT inside the devcontainer. This is a hard architectural boundary.

## What You MUST NOT Do

- Do NOT run `proxy/start.sh`, `proxy/stop.sh`, `proxy/status.sh`, or `proxy/logs.sh` -- these execute Docker commands on the Mac host, which is unreachable from the devcontainer.
- Do NOT run `docker compose` commands against `proxy/docker-compose.yml` -- this is a separate compose stack managed on the Mac host.
- Do NOT attempt to start, stop, restart, or health-check the mitmproxy container.

If proxy management is needed, **tell the user** to run the command on the Mac host.

## What You CAN Do

- **Read** files in `proxy/` (inspect configs, review scripts, edit addon code).
- **Read** proxy output data in `proxy/data/` (header reports, endpoint logs) -- this directory is a mounted volume accessible from both environments.
- **Run** `./scripts/proxy-report.sh` and `./scripts/proxy-endpoints.sh` from the devcontainer -- these read `proxy/data/` files, they do not interact with the proxy process.

## Key Files

| File | Purpose | Runs on |
|------|---------|---------|
| `proxy/start.sh`, `stop.sh`, `status.sh`, `logs.sh` | Proxy lifecycle management | Mac host only |
| `proxy/docker-compose.yml` | Proxy container definition | Mac host only |
| `proxy/addons/` | mitmproxy addon scripts (Python) | Mac host (inside proxy container) |
| `proxy/certs/` | TLS certificates for HTTPS interception | Mac host |
| `proxy/data/` | Captured data (header reports, endpoint logs) | Both (mounted volume) |

## Editing Proxy Files

You can freely edit files in `proxy/` (addons, configs, scripts). Changes will take effect the next time the user restarts the proxy on the Mac host. If your edits require a proxy restart, tell the user: "Run `cd proxy && ./stop.sh && ./start.sh` on the Mac host to pick up these changes."
