# Operator Bootstrap Guide

This guide walks you through getting the baseball-crawl system from zero to data in the database. It covers both credential capture paths, the bootstrap command, and common troubleshooting scenarios.

---

## Quick Start

Three steps to get data flowing:

**1. Capture credentials** -- Choose one path:

- **Proxy (iPhone)**: Start mitmproxy on your Mac, configure your iPhone to use it, open GameChanger on the phone. Credentials are written to `.env` automatically. See [Credential Capture: Proxy](#credential-capture-proxy) below.
- **Curl (browser)**: Copy a request from Chrome DevTools, save it to `secrets/gamechanger-curl.txt`, and run `python scripts/refresh_credentials.py` (or `bb creds import`). See [Credential Capture: Curl](#credential-capture-curl) below.

**2. Run the bootstrap command**:

```bash
python scripts/bootstrap.py
```

Also available as `bb data sync`.

This validates credentials, checks team configuration, crawls data from the GameChanger API, and loads it into the database.

**3. Check the dashboard**:

```bash
open http://localhost:8001/dashboard
```

---

## Credential Capture: Proxy

Use this path when capturing credentials from the GameChanger iOS app on an iPhone. Credentials are extracted automatically -- no manual copying required.

**1. Start mitmproxy on the Mac host** (not inside the devcontainer):

```bash
cd proxy
./start.sh
```

The script prints your Mac's LAN IP address and the mitmweb UI URL. Keep note of the LAN IP -- you will need it for the iPhone.

**2. Configure your iPhone to use the proxy**:

Follow the iPhone setup steps printed by `./start.sh`, or see the full instructions in [docs/admin/mitmproxy-guide.md](mitmproxy-guide.md#iphone-proxy-configuration). At minimum:

- Open **Settings > Wi-Fi**, tap **(i)** next to your network
- Set **Configure Proxy** to **Manual**
- Set **Server** to the Mac's LAN IP, **Port** to `8080`
- Install the mitmproxy CA certificate at `mitm.it` (one-time, per device)

**3. Open GameChanger on the iPhone** and navigate to any team or game page. The proxy's credential extractor detects GameChanger traffic and writes credentials to the project root `.env` automatically.

**4. Verify credentials were captured**:

Check that `.env` contains the key `GAMECHANGER_REFRESH_TOKEN_WEB` (do not display the value):

```bash
grep -q GAMECHANGER_REFRESH_TOKEN_WEB .env && echo "Key present" || echo "Key missing"
```

Or check the proxy logs for a "Credentials updated" message:

```bash
cd proxy && ./logs.sh
```

**5. When done**, turn off the iPhone proxy (**Settings > Wi-Fi > [network] > Configure Proxy > Off**) and stop mitmproxy:

```bash
cd proxy && ./stop.sh
```

For complete proxy setup, certificate management, browser capture, and troubleshooting, see [docs/admin/mitmproxy-guide.md](mitmproxy-guide.md).

---

## Credential Capture: Curl

Use this path when capturing credentials from a web browser (Chrome, Firefox, or Safari) via DevTools.

**1. Log in to GameChanger** at [web.gc.com](https://web.gc.com) in your browser.

**2. Open DevTools** (F12 or Cmd+Option+I on Mac).

**3. Go to the Network tab** and trigger any GameChanger API request (navigate to a team page or refresh the schedule).

**4. Copy a request as cURL**:

- Right-click any GameChanger API request in the Network tab
- Select **Copy > Copy as cURL** (Chrome/Edge) or **Copy as cURL** (Firefox)

**5. Save the curl command**:

Paste the copied command into `secrets/gamechanger-curl.txt`. The file should contain a single curl command.

**6. Extract credentials**:

```bash
python scripts/refresh_credentials.py
```

Also available as `bb creds import`.

This reads `secrets/gamechanger-curl.txt`, extracts the `gc-token` and `gc-device-id` headers, and writes them to `.env`.

---

## Bootstrap Command

`python scripts/bootstrap.py` (also available as `bb data sync`) runs four stages in order:

1. **Credential check** -- validates `.env` credentials against the API (`GET /me/user`)
2. **Team config check** -- verifies `config/teams.yaml` has at least one real team ID
3. **Crawl** -- fetches data from the GameChanger API
4. **Load** -- writes crawled data into the SQLite database

If either pre-flight check fails, the pipeline exits early with a clear message. Crawl failures are non-fatal -- any partial data that was fetched is still loaded.

### Flags

| Flag | Default | Description |
|------|---------|-------------|
| _(none)_ | -- | Full pipeline: validate + crawl + load |
| `--check-only` | off | Run credential and team config checks only. Skip crawl and load. Useful for verifying credentials before a scheduled run. |
| `--profile web` | `web` | Use web browser headers for API requests. Use this when credentials were captured from a browser via DevTools curl. |
| `--profile mobile` | -- | Use iOS mobile app headers for API requests. Use this when credentials were captured from the iPhone via the proxy. |
| `--dry-run` | off | Preview mode: no real API calls, no database writes. Passed through to both crawl and load stages. |

### Examples

```bash
# Validate only -- confirm credentials and team config before crawling
python scripts/bootstrap.py --check-only
# also: bb data sync --check-only

# Full pipeline with browser credentials (default)
python scripts/bootstrap.py
# also: bb data sync

# Full pipeline with credentials captured from iPhone
python scripts/bootstrap.py --profile mobile
# also: bb data sync --profile mobile

# Preview what would run without making any real calls or writes
python scripts/bootstrap.py --dry-run
# also: bb data sync --dry-run
```

### Reading the Output

The bootstrap script prints stage-by-stage status and a summary at the end:

```
Checking credentials...
  Credentials valid -- logged in as Jason Smith
Checking team configuration...
  3 team(s) configured: LSB Varsity, LSB JV, LSB Freshman
Crawling data...
Loading data...

--- Bootstrap summary ---
  credentials: valid
  teams: 3 team(s) configured: LSB Varsity, LSB JV, LSB Freshman
  crawl: success
  load: success
```

---

## Credential Lifecycle

### Token Architecture

GameChanger uses a three-tier credential system with different lifetimes:

| Credential | Lifetime | Notes |
|-----------|----------|-------|
| **Client ID + Client Key** | Permanent (until app redeploy) | Static secret from the app bundle. Stored in `.env`. Only changes when GC deploys a new app version. |
| **Refresh token** | 14 days (self-renewing) | Each programmatic refresh call returns a new refresh token -- effectively self-sustaining as long as you refresh before expiry. |
| **Access token** | ~60 minutes | Generated on demand via `POST /auth {"type":"refresh"}`. Not stored -- derived from the refresh token as needed. |

**Programmatic refresh is now available.** The project can generate a fresh access token from the refresh token at any time without browser interaction. The `gc-signature` signing algorithm was fully reverse-engineered on 2026-03-07. See `docs/api/auth.md` for the complete auth architecture.

### When to Refresh

- **Access tokens** expire in ~60 minutes. The bootstrap process and crawlers generate fresh access tokens automatically from the stored refresh token -- you do not need to manage this manually.
- **Refresh tokens** last 14 days. The refresh process returns a new refresh token each time it runs, so regular crawl runs keep the refresh token current automatically.
- **Manual re-capture** is only needed if the refresh token expires (e.g., no crawl has run for 14+ days) or if the client key changes due to a GC app deploy. Re-capture via proxy or curl paths described above.

The health check output is clear:

```
Credentials valid -- logged in as Jason Smith           # exit code 0, good to go
Credentials expired -- refresh via proxy capture        # exit code 1, recapture needed
  or scripts/refresh_credentials.py
Missing required credential(s): GAMECHANGER_REFRESH_TOKEN_WEB  # exit code 2, never captured
```

### What Happens When Credentials Expire Mid-Crawl

If credentials expire while a crawl is in progress, crawlers report a `CredentialExpiredError` and stop making API calls. Any data that was already fetched and written to disk is still loaded into the database in the load stage. The bootstrap summary will show `crawl: warning (errors)` and `load: success`.

After recapturing credentials, re-run the full bootstrap (`python scripts/bootstrap.py` or `bb data sync`) to fill in any data that was missed.

---

## Troubleshooting

### "Missing required credential(s)"

No credentials have been captured yet, or the `.env` file is missing required keys. Run one of the credential capture paths:

- Proxy path: [Credential Capture: Proxy](#credential-capture-proxy)
- Curl path: [Credential Capture: Curl](#credential-capture-curl)

### "Credentials expired"

The stored refresh token has passed its 14-day lifetime (or the access token has expired and programmatic refresh is failing). Recapture using either path above. The proxy path is faster (automated extraction); the curl path works without the proxy running.

### "No teams configured"

`config/teams.yaml` still contains placeholder team IDs (`REPLACE_WITH_*`). You need to add real GameChanger team IDs before crawling. Two options:

- Edit `config/teams.yaml` directly and replace placeholder IDs with your actual team UUIDs from GameChanger
- Use the admin UI at `/admin/teams` once it is available (E-042)

### "Crawl failed but load succeeded"

This is expected behavior when the crawl encounters errors partway through. The load stage runs regardless of crawl exit code, and any data fetched before the error was loaded successfully. The summary will show `crawl: warning (errors)`.

To get the missed data: recapture credentials if they expired, then re-run `python scripts/bootstrap.py`. The crawl is designed to be idempotent -- re-running it does not duplicate data.

### "Cannot reach GameChanger API"

A network error occurred when contacting the API. The check will report:

```
Network error reaching GameChanger API: ...
```

Check:
- Your internet connection is working
- `GAMECHANGER_BASE_URL` in `.env` is correct (typically `https://api.team-manager.gc.com`)
- The GameChanger API is not down (try opening [web.gc.com](https://web.gc.com) in a browser)

---

## Related Docs

- [docs/admin/mitmproxy-guide.md](mitmproxy-guide.md) -- Full proxy setup, iPhone and browser configuration, certificate management, and proxy troubleshooting
- [docs/admin/operations.md](operations.md) -- General operations: deployment, database backup, credential rotation, monitoring
- [docs/admin/getting-started.md](getting-started.md) -- Initial development environment setup from a fresh clone

---

*Last updated: 2026-03-07 | Story: E-055 (unified CLI), E-050-04*
