# mitmproxy Proxy Guide

## What It Does

mitmproxy sits between your devices (iPhone, web browser) and GameChanger's servers. When you use GameChanger normally, mitmproxy passively captures:

- **Credentials** (`gc-token`, `gc-device-id`) -- written to the project root `.env` automatically
- **Headers** -- compared against the project's `BROWSER_HEADERS` to detect drift
- **API endpoints** -- every GameChanger URL hit is logged for API discovery

This replaces the manual "copy curl from DevTools" workflow. Open GameChanger on your phone or browser, and credentials flow into the project automatically.

## Architecture

mitmproxy runs directly on the Mac host in its own Docker container (under `proxy/`). It is completely separate from the project's Docker Compose stack (app, traefik, cloudflared) which runs inside the devcontainer.

This architecture means:
- iPhone reaches the proxy directly over LAN at `<mac-lan-ip>:8080` -- no VS Code port forwarding needed
- The mitmweb UI is at `http://localhost:8081` on the Mac
- The devcontainer can reach the proxy via `host.docker.internal:8080`

See `proxy/README.md` for the quick-start guide.

## Starting and Stopping

All proxy commands run from the `proxy/` directory on the Mac host (not inside the devcontainer):

```bash
cd proxy
./start.sh      # launch mitmproxy (detached); prints LAN IP and mitmweb URL
./status.sh     # check containers and port listeners
./logs.sh       # follow live log output
./stop.sh       # shut down mitmproxy
```

### Optional: set a mitmweb password

Copy `.env.example` to `.env` inside `proxy/` and set `MITMWEB_PASSWORD`:

```bash
cd proxy
cp .env.example .env
# Edit .env and set MITMWEB_PASSWORD=yourpassword
```

When `MITMWEB_PASSWORD` is unset or empty, mitmweb generates a token-based URL and prints it to the logs. Check `./logs.sh` for the URL.

## iPhone Proxy Configuration

### 1. Set the Proxy

1. Open **Settings > Wi-Fi**
2. Tap the **(i)** next to your connected network
3. Scroll to **Configure Proxy** > **Manual**
4. Set:
   - **Server**: Your Mac's LAN IP (printed by `./start.sh`, or see "Finding Your LAN IP" below)
   - **Port**: `8080`
5. Tap **Save**

### 2. Install the CA Certificate

1. Open **Safari** and visit **mitm.it**
2. Tap the Apple logo to download the profile
3. Go to **Settings > General > VPN & Device Management**
4. Tap the **mitmproxy** profile > **Install**
5. Go to **Settings > General > About > Certificate Trust Settings**
6. Toggle **mitmproxy** to enabled

The certificate is stored in `proxy/certs/` and persists across proxy restarts. You only need to install it once per iPhone. Deleting `proxy/certs/` invalidates all installed certs -- you would need to repeat these steps.

### 3. Verify

Open the GameChanger app. You should see requests appearing in the mitmweb UI at `http://localhost:8081` on the Mac.

### 4. When Done

Turn off the proxy on the iPhone:

1. **Settings > Wi-Fi > [network] > Configure Proxy > Off**

## Finding Your LAN IP

The `./start.sh` script prints your Mac's LAN IP. You can also find it manually:

- **macOS**: `ipconfig getifaddr en0` (Wi-Fi) or `ipconfig getifaddr en1` (Ethernet)
- **Windows**: `ipconfig` -- look for "IPv4 Address" under your active adapter
- **Linux**: `hostname -I | awk '{print $1}'`

## Web Browser Proxy Configuration

### Chrome (macOS)

Chrome uses the macOS system proxy:

1. Open **System Settings > Network > Wi-Fi > Details... > Proxies**
2. Enable **Web Proxy (HTTP)** -- set to `localhost`, port `8080`
3. Enable **Secure Web Proxy (HTTPS)** -- set to `localhost`, port `8080`
4. Click **OK** > **Apply**
5. Visit `mitm.it` in Chrome to install the CA certificate

### Chrome (Windows)

1. Open **Settings > Network & Internet > Proxy**
2. Under "Manual proxy setup", click **Set up**
3. Toggle on **Use a proxy server**
4. Set Address to `localhost`, Port to `8080`
5. Click **Save**
6. Visit `mitm.it` in Chrome to install the CA certificate

### Firefox

Firefox has its own proxy settings:

1. Open **Settings > General > Network Settings > Settings...**
2. Select **Manual proxy configuration**
3. Set HTTP Proxy to `localhost`, Port `8080`
4. Check **Also use this proxy for HTTPS**
5. Click **OK**
6. Visit `mitm.it` in Firefox to install the CA certificate

## Devcontainer Access

From inside the devcontainer, the host proxy is reachable via Docker's built-in DNS alias:

```bash
curl -sx http://host.docker.internal:8080 http://mitm.it
```

A non-empty HTML response confirms the devcontainer-to-host-proxy path is working. To route project HTTP requests through the proxy, set:

```
http_proxy=http://host.docker.internal:8080
https_proxy=http://host.docker.internal:8080
```

## Where Data Goes

| Path | Contents |
|------|----------|
| Project root `.env` | Credentials (`GAMECHANGER_AUTH_TOKEN`, `GAMECHANGER_DEVICE_ID`) -- updated live |
| `proxy/data/header-report.json` | Header parity report (latest snapshot per source) |
| `proxy/data/endpoint-log.jsonl` | Append-only log of every GameChanger API request |
| `proxy/certs/` | mitmproxy CA certificate (persists across restarts) |

Both `proxy/data/` and `proxy/certs/` are gitignored (via `proxy/.gitignore`). The `.env` file is also gitignored at the project root.

## Reading Reports

### Header Parity Report

```bash
./scripts/proxy-report.sh
```

Shows, for each traffic source (ios/web), which headers are missing, extra, or different compared to the project's `BROWSER_HEADERS` in `src/http/headers.py`.

### Endpoint Discovery Log

```bash
./scripts/proxy-endpoints.sh
```

Shows a deduplicated table of every unique (method, path) seen, with hit count and most recent status code.

## Troubleshooting

### Proxy unreachable from iPhone

- Verify your Mac and iPhone are on the same Wi-Fi network
- Check your Mac's LAN IP (printed by `./start.sh`, or see "Finding Your LAN IP" above)
- Confirm mitmproxy is running: `cd proxy && ./status.sh`
- Check that port 8080 is not blocked by macOS firewall (**System Settings > Network > Firewall**)
- Run `./status.sh` and confirm the container is `Up` and port 8080 has a listener

### Port 8080 already in use

```bash
cd proxy && ./status.sh   # shows what is listening on 8080
```

Stop the conflicting process or change the port in `proxy/docker-compose.yml`. Changing the port also requires reconfiguring the iPhone proxy settings.

### Certificate not trusted

- Make sure you completed **both** certificate steps: installing the profile (VPN & Device Management) AND enabling trust (Certificate Trust Settings)
- If you see SSL errors, the cert may have been regenerated. Remove the old profile from the iPhone and reinstall via `mitm.it`
- Deleting `proxy/certs/` invalidates all installed certs -- repeat the install steps

### No traffic captured

- Verify the iPhone/browser proxy is set to the correct IP and port 8080
- Check that the CA certificate is installed and trusted
- Open the mitmweb UI (URL printed by `./start.sh` or in `./logs.sh` output) to see if any traffic is flowing
- Only GameChanger domains are captured -- other traffic is passed through but not logged

### mitmproxy won't start

- Check for port conflicts: `lsof -i :8080` and `lsof -i :8081`
- Review logs: `cd proxy && ./logs.sh`
- Ensure Docker is running: `docker info`
