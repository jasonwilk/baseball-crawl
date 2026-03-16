---
paths:
  - "proxy/**"
  - "src/http/**"
  - "src/gamechanger/client*"
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

---

## Bright Data (IP Anonymization)

Bright Data is a residential proxy service used by `GameChangerClient` to anonymize outbound API requests. It runs inside the devcontainer as part of the normal HTTP session -- no host boundary issues.

**Environment variables** (all in `.env`, git-ignored):
- `PROXY_ENABLED` -- set to `true` to route GameChanger API requests through Bright Data; any other value or absent means disabled
- `PROXY_URL_WEB` -- Bright Data proxy URL for the web profile
- `PROXY_URL_MOBILE` -- Bright Data proxy URL for the mobile profile
- `PROXY_URL_*` values contain embedded credentials (username:password in the URL) and are treated as secrets -- same handling as tokens (never log, commit, or display)

**SSL behavior**: When a Bright Data proxy is configured, SSL verification is automatically disabled (`verify=False` on `httpx.Client`). This is required because Bright Data uses a self-signed certificate in the CONNECT tunnel. Do not treat `verify=False` as a general pattern -- it is specific to the Bright Data proxy path.

**Sticky sessions**: When the proxy is enabled, each `GameChangerClient` instance automatically uses a sticky session -- all requests from that client route through the same Bright Data peer IP for the duration of the session. This happens transparently: `GameChangerClient.__init__` generates a session ID (`secrets.token_hex(8)`) and injects it into the proxy URL username via `_inject_session_id()` in `src/http/session.py`. No caller configuration is needed. The sticky peer has a 5-minute idle timeout on Bright Data's side; since crawl requests are spaced seconds apart, no keep-alive mechanism is necessary. If a sticky peer becomes unavailable (502), Bright Data auto-assigns a new peer on the next request using the same session ID -- the existing retry logic handles this. Note: `bb proxy check` does NOT use sticky sessions; it tests raw proxy connectivity with a rotating IP, which is the correct behavior for a diagnostic command.

**Diagnostics**: Run `bb proxy check` to verify proxy connectivity and confirm IP anonymization is working.
