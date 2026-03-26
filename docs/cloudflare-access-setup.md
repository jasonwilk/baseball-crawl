# Cloudflare Configuration for bbstats.ai

This guide covers the Cloudflare configuration for the bbstats.ai deployment.
The tunnel routes all traffic through Cloudflare's network (SSL termination, CDN) to
the Docker Compose stack on the production server. Authentication is handled entirely by
the application (magic links and passkeys) -- Cloudflare Access is present as an
infrastructure shell but is **not enforcing access control**.

Follow these steps when deploying or re-deploying to a new server.

## Prerequisites

- A Cloudflare account with `bbstats.ai` DNS managed by Cloudflare.
- The baseball-crawl `docker-compose.yml` deployed on the target server.
- `cloudflared` CLI installed locally, or access to the Cloudflare dashboard.

---

## 1. Auth Model for bbstats.ai

The application handles all authentication internally:

- **Magic links**: Email-based passwordless login via Mailgun
- **Passkeys**: WebAuthn/FIDO2 for returning users
- **Admin access**: `ADMIN_EMAIL` env var or `role='admin'` in the database

Cloudflare Access application `bbstats-ai` exists but functions as a **passive shell**:
it routes traffic to the tunnel without enforcing any access policy. This means:

- All traffic passes through to the app's own login flow
- No Cloudflare login page or redirect -- users see the app login directly
- CF Access can be activated in the future by adding Email OTP policies without any
  infrastructure changes (the app shell is preserved for this)

### Active policies that must be removed before go-live

The `bbstats-ai` Access application currently has two blocking policies from initial
setup. **These must be removed before the tunnel goes live** (see Section 2 below):

1. **"WARP Allow (<operator-email>)"** -- allows only <operator-email> via WARP
2. **"Google Auth Policy (<operator-email>)"** -- allows only <operator-email> via Google Auth

While either policy is active, Cloudflare Access enforces it: all traffic that does not
match the rule receives a 403 error. Coaches attempting to reach the dashboard will be
blocked.

---

## 2. Pre-Go-Live: Remove Blocking Access Policies (Required)

> **This step is mandatory before pointing DNS to the tunnel.** Skipping it means all
> non-Jason traffic will be blocked by Cloudflare Access -- coaches cannot reach the
> dashboard.

1. Go to [Cloudflare Zero Trust](https://one.dash.cloudflare.com/) -> **Access** ->
   **Applications**.
2. Find the **bbstats-ai** application and click **Configure** (or **Edit**).
3. Go to the **Policies** tab.
4. Delete the **"WARP Allow (<operator-email>)"** policy.
5. Delete the **"Google Auth Policy (<operator-email>)"** policy.
6. Save the application.

**Preserve the Access application itself** -- leaving the app shell (with no policies)
allows future activation of CF Email OTP for coaching staff without any infrastructure
changes. Only the blocking policies are removed.

After removal, the `bbstats-ai` Access app has zero policies. All traffic passes through
to the app's internal authentication.

---

## 3. Create the Tunnel

### Option A: Cloudflare Dashboard (recommended)

1. Go to [Cloudflare Zero Trust](https://one.dash.cloudflare.com/) ->
   **Networks** -> **Tunnels**.
2. Click **Create a Tunnel**.
3. Choose **Cloudflared** as the connector type.
4. Name the tunnel **`bbstats-ai`**.
5. On the next screen, Cloudflare shows a Docker run command containing
   `--token <TOKEN>`. Copy that token value.
6. Set `CLOUDFLARE_TUNNEL_TOKEN=<TOKEN>` in your `.env` on the server.

### Option B: cloudflared CLI

```bash
cloudflared tunnel login          # Opens browser for Cloudflare auth
cloudflared tunnel create bbstats-ai
# Outputs a tunnel UUID and creates ~/.cloudflared/<UUID>.json
```

Generate a tunnel token with:

```bash
cloudflared tunnel token bbstats-ai
```

Copy that token into `CLOUDFLARE_TUNNEL_TOKEN` in `.env`.

---

## 4. Configure Tunnel Ingress (Public Hostnames)

In the Cloudflare dashboard, open the **bbstats-ai** tunnel -> **Configure** ->
**Public Hostnames**. Add one entry:

| Subdomain | Domain | Type | URL |
|-----------|--------|------|-----|
| *(leave blank)* | `bbstats.ai` | HTTP | `traefik:80` |

Leave the Subdomain field blank to configure the apex domain `bbstats.ai`. Cloudflare
creates the DNS CNAME record automatically.

If you used the CLI instead:

```yaml
# ~/.cloudflared/config.yml  (not needed when using dashboard config)
tunnel: <TUNNEL-UUID>
credentials-file: /root/.cloudflared/<TUNNEL-UUID>.json

ingress:
  - hostname: bbstats.ai
    service: http://traefik:80
  - service: http_status:404
```

---

## 5. DNS Records

If you configured ingress in the dashboard (Public Hostnames tab), Cloudflare creates
the CNAME record automatically.

If you configured ingress via config file (Option B), create the CNAME manually:

1. Go to **DNS** -> **Records** for `bbstats.ai`.
2. Add one CNAME record (proxied, orange cloud):
   - `bbstats.ai` -> `<TUNNEL-UUID>.cfargotunnel.com`

SSL termination is handled by Cloudflare automatically. No certificates are managed in
the Docker Compose stack.

---

## 6. Scoped API Token (Management Credential)

A least-privilege API token enables programmatic Cloudflare management (DNS record
updates, Access configuration changes). This is distinct from the tunnel token and is
optional -- only needed if you are scripting Cloudflare API calls.

### Permissions

| Scope | Permission | Access Level |
|-------|-----------|--------------|
| Account: Teams | Write | Jason's account only |
| Account: Access | Write | Jason's account only |
| Zone: DNS Records | Edit | bbstats.ai zone only |
| Zone: Zone | Read | bbstats.ai zone only |

**Zone scope**: bbstats.ai only -- no access to other zones in the account.

### Creating the token

1. Go to [Cloudflare dashboard](https://dash.cloudflare.com/) -> **My Profile** ->
   **API Tokens**.
2. Click **Create Token** -> **Create Custom Token**.
3. Name: `bbstats-ai-management` (or similar).
4. Set permissions per the table above.
5. Set **Zone Resources** to `Include > Specific zone > bbstats.ai`.
6. Set **Account Resources** to `Include > Specific account > Jason's account`.
7. Click **Continue to Summary** -> **Create Token**.
8. Copy the token immediately (shown only once).

### Environment variable

Add to `.env` on the server:

```
CLOUDFLARE_API_TOKEN=<token>
```

### Three credentials -- distinct purposes

| Credential | Variable | Used by | Purpose |
|------------|----------|---------|---------|
| Scoped API token | `CLOUDFLARE_API_TOKEN` | Scripts, CLI | Programmatic CF management (DNS, Access config) |
| Tunnel token | `CLOUDFLARE_TUNNEL_TOKEN` | cloudflared container | Tunnel runtime connection to Cloudflare network |
| Cloudflare MCP | *(OAuth, no env var)* | Claude Code | Interactive CF management via browser popup |

Do not substitute one for another -- they authenticate differently and have different scopes.

### Token rotation

The API token does not auto-expire, but rotate it:
- When team members change
- If you suspect compromise
- Annually as a hygiene practice

To rotate: create a new token in the Cloudflare dashboard, update `CLOUDFLARE_API_TOKEN`
in `.env`, and delete the old token.

---

## 7. CF Access Application Reference (Not Active for bbstats.ai)

> **Reference only.** The following sections document how CF Access applications and
> policies work. They are **not active for the bbstats.ai deployment** -- the Access
> app shell has no enforcing policies (see Section 2). Retained here for reference in
> case CF Access is later enabled (e.g., adding Email OTP for coaching staff).

### 7.1 Adding a coaching staff policy

To activate CF Access for the dashboard at a later date:

1. Go to **Zero Trust** -> **Access** -> **Applications**.
2. Open the **bbstats-ai** application and click **Add a Policy**.
3. Policy name: `Coaching staff`
4. Action: **Allow**
5. Add an Include rule:
   - **Selector**: `Emails ending in` -> your email domain (e.g., `lsb.edu`)
   - OR **Selector**: `Email` -> specific addresses
6. Save the policy.

This would redirect all unauthenticated traffic to Cloudflare's email OTP login flow.

### 7.2 API subdomain (not applicable for bbstats.ai)

bbstats.ai uses a single domain with no `api.baseball` subdomain. A separate API
Access application is not needed. If you later add a separate API subdomain, create a
Self-hosted application for the new hostname and add a Service Token policy.

### 7.3 Optional: Public bypass for shared scouting reports

If a specific path (e.g., `/scouting/game-day`) should be shareable without login if
CF Access is later enabled:

1. Open the Access application and click **Add a Policy**.
2. Action: **Bypass**, Include rule: **Everyone**, path: `/scouting/game-day*`.

Cloudflare evaluates policies top to bottom; place bypass policies above allow policies.

---

## 8. Service Token Reference (Not Active for bbstats.ai)

> **Reference only.** Service tokens are **not required for the current bbstats.ai
> deployment** -- CF Access is not blocking traffic. Documented here for reference in
> case an API Access application with service token auth is added later.

Service tokens let Python crawlers call the production API without a human login flow,
when an API Access application with a Service Token policy is active.

1. Go to **Zero Trust** -> **Access** -> **Service Tokens**.
2. Click **Create Service Token**.
3. Name: `baseball-crawl-crawler`
4. Set an expiry appropriate for your rotation policy (e.g., 1 year).
5. Copy the **Client ID** and **Client Secret** (shown once).
6. Add them to `.env` on the server:
   ```
   CF_ACCESS_CLIENT_ID=<client-id>
   CF_ACCESS_CLIENT_SECRET=<client-secret>
   ```
7. Assign the token to an API Access application (see section 7.2).

---

## 9. Crawler Auth Pattern (Reference -- Not Active with No-Blocking Model)

> **Reference only.** These headers are **not needed for the current bbstats.ai
> deployment** (CF Access is not enforcing policies). Preserved here for reference in
> case CF Access is later enabled on an API path.

Any Python script that calls the production API when CF Access is active must include
these headers on every request:

```python
headers = {
    "CF-Access-Client-Id": os.environ["CF_ACCESS_CLIENT_ID"],
    "CF-Access-Client-Secret": os.environ["CF_ACCESS_CLIENT_SECRET"],
}
```

These headers are checked by Cloudflare Access *before* the request reaches the
FastAPI app. Store the values in environment variables; never hardcode them.

The canonical header set for all HTTP requests is defined in `src/http/headers.py` (BROWSER_HEADERS and MOBILE_HEADERS profiles) and `src/http/session.py` (session factory).
CF-Access headers would need to be injected at the session level when `APP_ENV=production` is
set, so local dev runs do not need the service token.

---

## 10. Start the Stack and Verify

On the server, with `CLOUDFLARE_TUNNEL_TOKEN` set in `.env`:

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

In the Cloudflare dashboard (**Networks** -> **Tunnels**), the tunnel status should
change from **Inactive** to **Healthy** within 30 seconds.

### End-to-end connectivity test

```bash
# Health endpoint -- no authentication required
curl -v https://bbstats.ai/health
```

Expected: HTTP 200 with `{"status": "ok", "db": "connected"}`.

### Dashboard access test

1. Open `https://bbstats.ai` in a browser.
2. The app login page loads directly (no CF Access redirect).
3. Log in via magic link (email) or passkey.
4. The dashboard should load.

---

## 11. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `cloudflared` container exits immediately | Invalid or missing `CLOUDFLARE_TUNNEL_TOKEN` | Re-copy the token from the dashboard |
| Tunnel shows "Degraded" in dashboard | `app` health check failing; `cloudflared` cannot reach Traefik | Check `docker compose ps`, verify `app` is healthy |
| 403 Access Denied for all users | CF Access blocking policy still active | Complete Section 2: remove both policies from `bbstats-ai` Access app |
| 1020 Access Denied | Unexpected CF Access policy active | Check Zero Trust -> Access -> Applications -> bbstats-ai for active policies |
| CNAME not resolving | DNS record not yet propagated, or Cloudflare proxy disabled | Check DNS tab; orange-cloud (proxied) must be enabled |

---

## Notes

- **SSL**: Cloudflare handles SSL termination. The Docker Compose stack has no TLS
  certificates and no cert renewal concern.
- **Local dev**: The `cloudflared` service is not needed locally. Access the app
  directly at `http://localhost:8001`. Use `docker-compose.override.yml` to omit
  `cloudflared` for local dev (covered in the production runbook).
- **Image pinning**: cloudflared is pinned to `cloudflare/cloudflared:2024.12.2` in
  `docker-compose.yml`. Update the pin when upgrading.
- **Token rotation**: The scoped API token (`CLOUDFLARE_API_TOKEN`) does not expire
  but should be rotated annually or after personnel changes. The tunnel token
  (`CLOUDFLARE_TUNNEL_TOKEN`) does not expire unless revoked.

---

*Last updated: 2026-03-26 | Story: E-157-02*
