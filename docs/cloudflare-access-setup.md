# Cloudflare Tunnel + Zero Trust Access Setup

This guide covers the one-time Cloudflare configuration required to put the
baseball-crawl stack behind a Cloudflare Tunnel with Zero Trust Access policies.
Follow these steps when deploying to a new VPS or domain.

## Prerequisites

- A Cloudflare account with a domain whose DNS is managed by Cloudflare.
- The baseball-crawl `docker-compose.yml` deployed on the target VPS (E-009-02).
- `cloudflared` CLI installed locally or access to the Cloudflare dashboard.

---

## 1. Create the Tunnel

You have two options: dashboard or CLI. The dashboard is easier for a one-time
setup. The CLI is useful if you want to script it later.

### Option A: Cloudflare Dashboard (recommended)

1. Go to [Cloudflare Zero Trust](https://one.dash.cloudflare.com/) ->
   **Networks** -> **Tunnels**.
2. Click **Create a Tunnel**.
3. Choose **Cloudflared** as the connector type.
4. Name the tunnel (e.g., `baseball-crawl-prod`).
5. On the next screen, Cloudflare shows a Docker run command containing
   `--token <TOKEN>`. Copy that token value.
6. Set `CLOUDFLARE_TUNNEL_TOKEN=<TOKEN>` in your `.env` on the VPS.

### Option B: cloudflared CLI

```bash
cloudflared tunnel login          # Opens browser for Cloudflare auth
cloudflared tunnel create baseball-crawl-prod
# Outputs a tunnel UUID and creates ~/.cloudflared/<UUID>.json
```

When using the CLI, generate a tunnel token with:

```bash
cloudflared tunnel token baseball-crawl-prod
```

Copy that token into `CLOUDFLARE_TUNNEL_TOKEN` in `.env`.

---

## 2. Configure Tunnel Ingress (Public Hostnames)

In the Cloudflare dashboard, open your tunnel -> **Configure** ->
**Public Hostnames**. Add two entries:

| Subdomain              | Domain        | Type | URL                |
|------------------------|---------------|------|--------------------|
| `baseball`             | `<your-domain>` | HTTP | `traefik:80`       |
| `api.baseball`         | `<your-domain>` | HTTP | `traefik:80`       |

Traefik uses the `Host` header to route internally between the dashboard
(`baseball.<domain>`) and the API (`api.baseball.<domain>`).

If you used the CLI instead:

```yaml
# ~/.cloudflared/config.yml  (on the VPS, not needed when using dashboard config)
tunnel: <TUNNEL-UUID>
credentials-file: /root/.cloudflared/<TUNNEL-UUID>.json

ingress:
  - hostname: baseball.<your-domain>
    service: http://traefik:80
  - hostname: api.baseball.<your-domain>
    service: http://traefik:80
  - service: http_status:404
```

---

## 3. DNS Records

If you configured ingress in the dashboard (Option A / Public Hostnames tab),
Cloudflare creates the CNAME records automatically.

If you configured ingress via config file (Option B), create the CNAMEs manually:

1. Go to **DNS** -> **Records** for your domain.
2. Add two CNAME records (proxied, orange cloud):
   - `baseball` -> `<TUNNEL-UUID>.cfargotunnel.com`
   - `api.baseball` -> `<TUNNEL-UUID>.cfargotunnel.com`

SSL termination is handled by Cloudflare automatically. No certificates are
managed in the Docker Compose stack.

---

## 4. Create the Zero Trust Access Application (Dashboard)

Access applications define *who* can reach which hostname.

### 4.1 Dashboard application (`baseball.<domain>`)

1. Go to **Zero Trust** -> **Access** -> **Applications**.
2. Click **Add an Application** -> **Self-hosted**.
3. **Application name**: `baseball-crawl dashboard`
4. **Application domain**: `baseball.<your-domain>`
5. Click **Next** -> **Add a Policy**.
6. Policy name: `Coaching staff`
7. Action: **Allow**
8. Add an Include rule:
   - **Selector**: `Emails ending in` -> `<your-email-domain>` (e.g. `lsb.edu`)
   - OR add a second Include rule: **Selector**: `WARP` -> `Device Enrolled`
9. Save the policy and the application.

This allows coaching staff who have WARP installed *or* who complete email OTP
to reach the dashboard.

### 4.2 API application (`api.baseball.<domain>`)

1. **Add an Application** -> **Self-hosted**.
2. **Application name**: `baseball-crawl API`
3. **Application domain**: `api.baseball.<your-domain>`
4. Click **Next** -> **Add a Policy**.
5. Policy name: `Crawler service token`
6. Action: **Allow**
7. Add an Include rule:
   - **Selector**: `Service Token` -> (select the token created in step 5 below)
8. Save the policy and the application.

This locks the API to service token auth only; no human browser sessions are
allowed.

### 4.3 Optional: Public bypass for shared scouting reports

If a specific path (e.g., `/scouting/game-day`) should be shareable without
login:

1. Open the dashboard application.
2. Click **Add a Policy**.
3. Policy name: `Public game-day page`
4. Action: **Bypass**
5. Add an Include rule: **Selector**: `Everyone`
6. Add a path rule: **Application path**: `/scouting/game-day*`

Cloudflare evaluates policies top to bottom; place the bypass policy above the
`Coaching staff` policy so public paths are matched first.

---

## 5. Create a Service Token (Crawler -> API Auth)

Service tokens let Python crawlers call the production API without a human
login flow.

1. Go to **Zero Trust** -> **Access** -> **Service Tokens**.
2. Click **Create Service Token**.
3. Name: `baseball-crawl-crawler`
4. Set an expiry appropriate for your rotation policy (e.g., 1 year).
5. Cloudflare shows the **Client ID** and **Client Secret** once. Copy both now.
6. Add them to `.env` on the VPS:
   ```
   CF_ACCESS_CLIENT_ID=<client-id>
   CF_ACCESS_CLIENT_SECRET=<client-secret>
   ```
7. Assign the token to the API Access application (see step 4.2 above).

---

## 6. Crawler Auth Pattern

Any Python script that calls the production API must include these headers on
every request:

```python
headers = {
    "CF-Access-Client-Id": os.environ["CF_ACCESS_CLIENT_ID"],
    "CF-Access-Client-Secret": os.environ["CF_ACCESS_CLIENT_SECRET"],
}
```

These headers are checked by Cloudflare Access *before* the request reaches the
FastAPI app. Store the values in environment variables; never hardcode them.

The canonical header set for all HTTP requests is defined in
`src/http_client.py`. The CF-Access headers should be injected at the session
level when the `APP_ENV=production` environment variable is set, so local dev
runs do not need the service token at all.

---

## 7. Start the Stack and Verify

On the VPS, with `CLOUDFLARE_TUNNEL_TOKEN` set in `.env`:

```bash
docker compose up -d
docker compose logs cloudflared --follow
```

Expected log output once the tunnel connects:

```
INF Connection registered connIndex=0 ...
INF Connection registered connIndex=1 ...
INF Registered tunnel connection ...
```

In the Cloudflare dashboard (**Networks** -> **Tunnels**), the tunnel status
should change from **Inactive** to **Healthy** within 30 seconds.

### End-to-end connectivity test

```bash
# Health check through the tunnel (no auth required on /health)
curl -v https://baseball.<your-domain>/health

# API endpoint with service token
curl -v \
  -H "CF-Access-Client-Id: $CF_ACCESS_CLIENT_ID" \
  -H "CF-Access-Client-Secret: $CF_ACCESS_CLIENT_SECRET" \
  https://api.baseball.<your-domain>/health
```

Both should return `{"status": "ok"}` with HTTP 200.

### Dashboard access test

1. Open `https://baseball.<your-domain>` in a browser.
2. Cloudflare redirects to the Access login page.
3. Authenticate via WARP or email OTP using your coaching-staff email.
4. The dashboard should load.

---

## 8. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `cloudflared` container exits immediately | Invalid or missing `CLOUDFLARE_TUNNEL_TOKEN` | Re-copy the token from the dashboard |
| Tunnel shows "Degraded" in dashboard | `app` health check failing; `cloudflared` cannot reach Traefik | Check `docker compose ps`, verify `app` is healthy |
| 1020 Access Denied on API calls | Service token not attached to the API Access application | See step 4.2 |
| 1020 Access Denied on dashboard | Your email is not in the allowed domain, or WARP not enrolled | Check the coaching-staff policy in step 4.1 |
| CNAME not resolving | DNS record not yet propagated, or Cloudflare proxy disabled | Check DNS tab; orange-cloud (proxied) must be on |

---

## Notes

- **SSL**: Cloudflare handles SSL termination. The Docker Compose stack has no
  TLS certificates and no cert renewal concern.
- **Local dev**: The `cloudflared` service is not needed locally. Access the
  app directly at `http://localhost:8000`. Use `docker-compose.override.yml` to
  remove the `cloudflared` service for local dev (covered in the production
  runbook, E-009-07).
- **Image pinning**: `cloudflare/cloudflared:latest` is used here for
  simplicity. Pin to a specific version tag (e.g., `cloudflare/cloudflared:2025.4.0`)
  in production to avoid unexpected behavior from upstream updates.
- **Token rotation**: Cloudflare Access service tokens expire. Set a calendar
  reminder to rotate `CF_ACCESS_CLIENT_ID` and `CF_ACCESS_CLIENT_SECRET` before
  expiry. The tunnel token does not expire unless revoked.
