# mitmproxy Proxy Guide

## What It Does

mitmproxy sits between your devices (iPhone, web browser) and GameChanger's servers. When you use GameChanger normally, mitmproxy passively captures:

- **Credentials** (`gc-token`, `gc-device-id`) -- written to `.env` automatically
- **Headers** -- compared against the project's `BROWSER_HEADERS` to detect drift
- **API endpoints** -- every GameChanger URL hit is logged for API discovery

This replaces the manual "copy curl from DevTools" workflow. Open GameChanger on your phone or browser, and credentials flow into the project automatically.

## Starting and Stopping

Start the proxy (app stack starts too if not already running):

```bash
./scripts/proxy.sh start
```

This prints the proxy address, mitmweb UI URL, and iPhone setup reminder.

Stop only mitmproxy (app stack keeps running):

```bash
./scripts/proxy.sh stop
```

Check mitmproxy status:

```bash
./scripts/proxy.sh status
```

## iPhone Proxy Configuration

### 1. Set the Proxy

1. Open **Settings > Wi-Fi**
2. Tap the **(i)** next to your connected network
3. Scroll to **Configure Proxy** > **Manual**
4. Set:
   - **Server**: Your computer's LAN IP (see "Finding Your LAN IP" below)
   - **Port**: `8080`
5. Tap **Save**

### 2. Install the CA Certificate

1. Open **Safari** and visit **mitm.it**
2. Tap the Apple logo to download the profile
3. Go to **Settings > General > VPN & Device Management**
4. Tap the **mitmproxy** profile > **Install**
5. Go to **Settings > General > About > Certificate Trust Settings**
6. Toggle **mitmproxy** to enabled

The certificate only needs to be installed once. It persists until you remove it or delete the `mitmproxy-certs` Docker volume.

### 3. Verify

Open the GameChanger app. You should see requests appearing in the mitmweb UI at `http://localhost:8081`.

### 4. When Done

Turn off the proxy on the iPhone:

1. **Settings > Wi-Fi > [network] > Configure Proxy > Off**

## Finding Your LAN IP

Since the devcontainer has its own network, `hostname -I` inside it returns the container IP -- not your host's LAN IP. Find your real IP on the **host machine**:

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

## Where Data Goes

| File | Contents |
|------|----------|
| `.env` | Credentials (`GAMECHANGER_AUTH_TOKEN`, `GAMECHANGER_DEVICE_ID`) -- updated live |
| `data/mitmproxy/header-report.json` | Header parity report (latest snapshot per source) |
| `data/mitmproxy/endpoint-log.jsonl` | Append-only log of every GameChanger API request |

The `data/mitmproxy/` directory is git-ignored (under the `data/` rule). The `.env` file is also git-ignored.

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

- Verify your computer and iPhone are on the same Wi-Fi network
- Check your host LAN IP (see "Finding Your LAN IP" above) -- not the container IP from `hostname -I`
- Confirm mitmproxy is running: `./scripts/proxy.sh status`
- Check that port 8080 is not blocked by a firewall
- Check for devcontainer port-forwarding conflicts (see "Traefik dashboard appears instead of mitm.it" below)

### Traefik dashboard appears instead of mitm.it

If you configure your iPhone proxy to `<host-ip>:8080` and visit `mitm.it` in Safari but see the Traefik dashboard instead of the mitmproxy certificate installer, VS Code's devcontainer port forwarding is conflicting with Docker's port mapping.

**Symptoms**: Visiting `http://mitm.it` shows the Traefik dashboard page. Running `lsof -i :8080` on the host shows two processes (e.g., OrbStack and VS Code) both listening on port 8080.

**Cause**: The `devcontainer.json` `forwardPorts` array included port 8080, so VS Code created its own forwarding tunnel on the host. This races with Docker Compose's `0.0.0.0:8080:8080` binding for the mitmproxy container. The iPhone connects to whichever listener wins the bind -- often VS Code's tunnel, which routes to Traefik instead of mitmproxy.

**Fix**:
1. Open `.devcontainer/devcontainer.json`
2. Remove `8080` and `8081` from the `forwardPorts` array (keep `8000` and `8180`)
3. Rebuild the devcontainer (VS Code: "Rebuild Container")
4. Verify with `lsof -i :8080` on the host -- only one process should be listening

This has already been fixed in the project. If it recurs after a devcontainer config change, check `forwardPorts` first.

### Certificate not trusted

- Make sure you completed **both** certificate steps: installing the profile (VPN & Device Management) AND enabling trust (Certificate Trust Settings)
- If you see SSL errors, the cert may have been regenerated. Remove the old profile from the iPhone and reinstall via `mitm.it`
- Deleting the `mitmproxy-certs` Docker volume invalidates all installed certs

### No traffic captured

- Verify the iPhone/browser proxy is set to the correct IP and port 8080
- Check that the CA certificate is installed and trusted
- Open `http://localhost:8081` (mitmweb UI) to see if any traffic is flowing
- Only GameChanger domains are captured -- other traffic is passed through but not logged

### mitmproxy won't start

- Check for port conflicts: `lsof -i :8080` and `lsof -i :8081`
- Review logs: `docker compose logs mitmproxy`
- Ensure Docker is running: `docker info`
