# mitmproxy Proxy Guide

<!-- Last updated: 2026-03-07 | Source: E-055 (unified CLI), E-052 -->

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

Each `start.sh` invocation creates a timestamped session directory. All addon output lands in that session directory, not flat files in `proxy/data/`.

| Path | Contents |
|------|----------|
| Project root `.env` | Credentials (`GAMECHANGER_AUTH_TOKEN`, `GAMECHANGER_DEVICE_ID`) -- updated live |
| `proxy/data/sessions/<id>/header-report.json` | Header parity report for that session |
| `proxy/data/sessions/<id>/endpoint-log.jsonl` | Endpoint log for that session |
| `proxy/data/sessions/<id>/session.json` | Session metadata (started_at, stopped_at, endpoint_count, reviewed) |
| `proxy/data/current` | Symlink to the latest session directory -- always present after first start |
| `proxy/certs/` | mitmproxy CA certificate (persists across restarts) |

Both `proxy/data/` and `proxy/certs/` are gitignored (via `proxy/.gitignore`). The `.env` file is also gitignored at the project root.

## Session Management

Every `start.sh` / `stop.sh` cycle is a discrete session. Sessions accumulate in `proxy/data/sessions/` and the `current` symlink always points to the most recent one.

### Session lifecycle

- **`start.sh`**: creates a timestamped session directory, writes `session.json` with `status: "active"`, updates the `current` symlink, and starts the proxy container with `PROXY_SESSION_DIR` pointing to the new directory.
- **`stop.sh`**: stops the container, finalizes `session.json` (`stopped_at`, `endpoint_count`, `status: "closed"`), and prints a summary with next-steps guidance.

### Listing sessions

```bash
./scripts/proxy-review.sh list
# also: bb proxy review list
```

Prints a table of all sessions: ID, profile, status (the current session is marked with `*`), endpoint count, and reviewed status.

### Marking sessions reviewed

After reviewing a session's endpoint discoveries and feeding findings to api-scout, mark the session as reviewed:

```bash
./scripts/proxy-review.sh mark <session-id>   # mark one session
./scripts/proxy-review.sh mark --all           # mark all closed sessions
# also: bb proxy review mark <session-id>
# also: bb proxy review mark --all
```

### Operator workflow

1. `cd proxy && ./start.sh` -- start a capture session
2. Browse GameChanger on your iPhone or browser
3. `cd proxy && ./stop.sh` -- finalize the session (prints summary)
4. `./scripts/proxy-endpoints.sh --unreviewed` (or `bb proxy endpoints --unreviewed`) -- see new endpoint discoveries across all unreviewed sessions
5. Review findings; feed interesting ones to api-scout
6. `./scripts/proxy-review.sh mark <session-id>` (or `bb proxy review mark <session-id>`) -- mark the session reviewed

## Reading Reports

### Header Parity Report

```bash
./scripts/proxy-report.sh                  # current session (default)
./scripts/proxy-report.sh --session <id>   # specific session
./scripts/proxy-report.sh --all            # most recent closed session with a report
# also: bb proxy report [--session <id>] [--all]
```

Shows, for each traffic source (ios/web), which headers are missing, extra, or different compared to the project's `BROWSER_HEADERS` in `src/http/headers.py`.

Note: header reports are point-in-time snapshots, not aggregatable. `--all` returns the most recent closed session that has a report, not a merge of all sessions.

### Endpoint Discovery Log

```bash
./scripts/proxy-endpoints.sh                      # current session (default)
./scripts/proxy-endpoints.sh --session <id>       # specific session
./scripts/proxy-endpoints.sh --all                # aggregate across all sessions
./scripts/proxy-endpoints.sh --unreviewed         # aggregate across unreviewed sessions only
# also: bb proxy endpoints [--session <id>] [--all] [--unreviewed]
```

Shows a deduplicated table of every unique (method, path) seen, with hit count and most recent status code. Use `--unreviewed` as your default post-capture query to see only new discoveries.

## Refreshing Header Fingerprints

The `proxy-refresh-headers.py` script reads the latest mitmproxy capture report and rewrites `src/http/headers.py` to match the real headers seen in traffic. Run it after any mitmproxy capture session where you want to update the project's header fingerprints.

### End-to-End Workflow

1. **Capture traffic** using mitmproxy (iPhone or browser -- see sections above). The `header_capture` addon writes `header-report.json` into the active session directory automatically as requests flow through.

2. **Preview the diff** (dry-run, no files changed):

   ```bash
   python scripts/proxy-refresh-headers.py
   # also: bb proxy refresh-headers
   ```

   This reads the header report and prints a unified diff showing exactly what would change in `src/http/headers.py`. No files are written.

3. **Apply the update:**

   ```bash
   python scripts/proxy-refresh-headers.py --apply
   # also: bb proxy refresh-headers --apply
   ```

   This writes the updated `src/http/headers.py` and prints a summary of which dicts were updated (`BROWSER_HEADERS`, `MOBILE_HEADERS`, or both).

4. **Review and commit:**

   ```bash
   git diff src/http/headers.py
   git add src/http/headers.py
   git commit -m "chore: refresh header fingerprints from mitmproxy capture YYYY-MM-DD"
   ```

### Source-to-Dict Mapping

| Captured from | Updates |
|---------------|---------|
| Web browser traffic (`web` source) | `BROWSER_HEADERS` |
| iOS app traffic (`ios` source) | `MOBILE_HEADERS` |
| Unknown source | Ignored |

If the capture contains only one source (e.g., you only captured iOS traffic), only the corresponding dict is updated. The other dict is preserved from the existing `headers.py`.

### Headers Excluded from Auto-Update

The script never writes these header categories to `headers.py`, even if they appear in the capture:

| Category | Headers | Reason |
|----------|---------|--------|
| **Credential headers** | `gc-token`, `gc-device-id`, `gc-signature`, `gc-app-name`, `cookie` | Auth secrets -- injected by `GameChangerClient`, never in session defaults |
| **Per-request headers** | `content-type`, `accept`, `gc-user-action-id`, `gc-user-action`, `x-pagination` | Vary per API call -- set by the caller, not the session |
| **Connection-level headers** | `host`, `connection`, `content-length`, `transfer-encoding`, `te`, `trailer`, `upgrade`, `proxy-authorization`, `proxy-authenticate` | Managed by the HTTP library, not fingerprint-relevant |

### Report Path

The script tries `proxy/data/current/header-report.json` first (session-aware path, written by E-052 session management). If that file does not exist, it falls back to `proxy/data/header-report.json` (flat path written directly by the `header_capture` addon).

### Error: No capture data found

If you see:

```
No capture data found. Run mitmproxy and capture GameChanger traffic first.
```

Neither report path exists. Run mitmproxy and navigate GameChanger on your iPhone or browser to generate traffic. The report is written automatically after the first request.

## Mobile Credential Capture

This section explains how to capture mobile app credentials from the iOS GameChanger (Odyssey) app for use with the `mobile` header profile in `src/http/session.py`.

### Why Mobile Credentials?

Some GameChanger API endpoints behave differently with web browser headers vs. mobile app headers. The `create_session(profile="mobile")` function in `src/http/session.py` sends iOS Odyssey headers, but you also need credentials extracted from mobile app traffic. The `gc-token` JWT format is the same for both web and mobile, but the `gc-device-id` may differ.

### End-to-End Workflow

1. **Start mitmproxy on the Mac host:**

   ```bash
   cd proxy
   ./start.sh
   ```

   The script prints the Mac's LAN IP address and the mitmweb UI URL.

2. **Configure the iOS device to use the proxy:**

   - Open **Settings > Wi-Fi** > tap **(i)** on your connected network
   - Scroll to **Configure Proxy > Manual**
   - Set **Server** to your Mac's LAN IP, **Port** to `8080`
   - Tap **Save**

   (Full details in the [iPhone Proxy Configuration](#iphone-proxy-configuration) section above.)

3. **Install the mitmproxy CA certificate on the device:**

   - Open **Safari** and navigate to **mitm.it**
   - Tap the Apple logo to download the profile
   - Go to **Settings > General > VPN & Device Management** > install the mitmproxy profile
   - Go to **Settings > General > About > Certificate Trust Settings** > toggle mitmproxy to **enabled**

   (You only need to do this once per device, unless `proxy/certs/` is deleted.)

4. **Open the GameChanger app and sign in:**

   Open the GameChanger app on the iPhone. Navigate to any team or game page to generate API traffic. The `credential_extractor` addon (`proxy/addons/credential_extractor.py`) automatically detects `gc-token` and `gc-device-id` headers in the proxied requests and writes them to the project root `.env` file.

5. **Verify credentials were captured:**

   Check the proxy logs for a "Credentials updated" message:

   ```bash
   cd proxy
   ./logs.sh
   ```

   Confirm the `.env` file was updated with `GAMECHANGER_AUTH_TOKEN` and `GAMECHANGER_DEVICE_ID`.

### Headers to Extract

The credential extractor addon captures these headers automatically:

| Header | .env Variable | Notes |
|--------|--------------|-------|
| `gc-token` | `GAMECHANGER_AUTH_TOKEN` | JWT auth token. Same format as web token. 14-day lifetime. |
| `gc-device-id` | `GAMECHANGER_DEVICE_ID` | 32-char hex device identifier. May differ from the web device ID. |
| `gc-app-name` | `GAMECHANGER_APP_NAME` | Not observed in iOS traffic (web-specific: `web`). |
| `gc-signature` | `GAMECHANGER_SIGNATURE` | Only on POST /auth requests. |

Optionally note the mobile-specific `gc-app-version` value (`2026.7.0.0` vs web's `0.0.0`). This value is not extracted to `.env` by the addon -- it is hardcoded in `MOBILE_HEADERS` in `src/http/headers.py`.

### Storing Mobile Credentials

The credential extractor writes to the same `.env` variables regardless of traffic source (web or mobile). This means:

- If you capture **mobile credentials after web credentials**, the `.env` file is overwritten with the mobile values
- The `gc-token` is interchangeable (same JWT, same server) -- either web or mobile token works for API calls
- The `gc-device-id` **may differ** between web and mobile. Whether the server ties the device ID to the request profile is **unverified** -- test when both credential sets are available
- If you need to maintain separate credential sets, manually copy the mobile values before switching back to web capture

### Web vs Mobile Credential Capture

| Aspect | Web Browser | Mobile (iOS) |
|--------|------------|--------------|
| **Source** | Chrome DevTools (copy as curl) or mitmproxy browser capture | mitmproxy iOS capture |
| **Auth token** | `gc-token` JWT | `gc-token` JWT (same format) |
| **Device ID** | `gc-device-id` (32-char hex) | `gc-device-id` (32-char hex, may differ) |
| **Token lifetime** | 14 days (from JWT `exp - iat`) | 14 days (same JWT format) |
| **App version** | `gc-app-version: 0.0.0` (POST /auth only) | `gc-app-version: 2026.7.0.0` (on all requests) |
| **Setup required** | Browser proxy or DevTools | iPhone proxy + CA cert |
| **Extraction** | Manual (curl) or automatic (mitmproxy) | Automatic (mitmproxy credential_extractor addon) |

### Security Considerations

**Warning: Remove the mitmproxy CA certificate after capture.**

Installing the mitmproxy CA certificate on your iOS device enables man-in-the-middle interception of **all** HTTPS traffic on that device -- not just GameChanger. While the proxy is running and the certificate is trusted:

- All HTTPS connections from the device are decryptable by mitmproxy
- Banking apps, messaging apps, and all other network traffic could be intercepted
- Any other machine on the same network running the same mitmproxy instance could see this traffic

**After you have captured the credentials you need:**

1. Stop the proxy: `cd proxy && ./stop.sh`
2. Turn off the iPhone proxy: **Settings > Wi-Fi > [network] > Configure Proxy > Off**
3. Remove the CA certificate trust: **Settings > General > About > Certificate Trust Settings** > toggle mitmproxy to **disabled**
4. Optionally remove the profile entirely: **Settings > General > VPN & Device Management** > mitmproxy > **Remove Profile**

The documented workflow used iOS 26.x (based on the 2026-03-05 capture). Certificate trust settings paths may differ on older iOS versions.

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
