# Post-Reset Onboarding Guide

This guide covers the end-to-end workflow for going from a fresh `bb db reset` to a working local environment with live scouting data.

---

## Step 1: Reset the Database

```bash
bb db reset
```

This drops and recreates the database and applies all migrations. The resulting database is empty (no teams, no players, no game data -- only the `programs` bootstrap row for Lincoln Standing Bear HS). The app needs to restart after a reset.

```bash
docker compose up -d --build app
```

Verify the app is healthy:

```bash
curl -s http://localhost:8001/health
```

Expected: `{"status": "ok", "db": "connected"}`.

---

## Step 2: Set Up Credentials

Credentials must be in `.env` before generating reports. Two parts: the client key and the API tokens.

### 2a. Extract or verify the client key

The client key (`GAMECHANGER_CLIENT_KEY_WEB`) is extracted from the GameChanger web app bundle. Run:

```bash
bb creds extract-key
```

This checks whether your `.env` already has the current key. If it reports "no update needed," skip to step 2b.

To apply an updated key:

```bash
bb creds extract-key --apply
```

### 2b. Import API credentials

If you don't have a refresh token yet (fresh reset with no `.env`), capture credentials from your browser:

1. Log in to [web.gc.com](https://web.gc.com) in Chrome.
2. Open DevTools → Network tab → trigger any request (navigate to a team page).
3. Right-click any `api.team-manager.gc.com` request → **Copy > Copy as cURL**.
4. Import:

```bash
bb creds import
```

### 2c. Refresh tokens

Once the client key and initial credentials are in `.env`, refresh to generate a fresh access token:

```bash
bb creds refresh --profile web
```

Verify everything:

```bash
bb creds check --profile web
```

All sections should show `[OK]`. If `[XX]` appears anywhere, see [docs/admin/credential-refresh.md](credential-refresh.md).

---

## Step 3: Generate a Report

With credentials in place, generate your first scouting report:

```bash
bb report generate <public_id>
```

Replace `<public_id>` with a GameChanger team's public URL slug (find it in the team's GameChanger URL, e.g., `https://web.gc.com/teams/a1GFM9Ku0BbF/schedule` → slug is `a1GFM9Ku0BbF`).

The command crawls the team's schedule and stats, renders a self-contained HTML report, and prints a shareable link. The report is accessible from `/admin/reports`.

Check the reports list:

```bash
bb report list
```

---

## Troubleshooting

### "Missing required credential(s)"

No credentials have been captured yet, or the `.env` file is missing required keys. Run one of the credential capture paths:

- Proxy path: see [Bootstrap Guide](bootstrap-guide.md#credential-capture-proxy)
- Curl path: see [Bootstrap Guide](bootstrap-guide.md#credential-capture-curl)

### Credential errors during report generation

Run `bb creds check --profile web` and follow the Decision Tree in [docs/admin/credential-refresh.md](credential-refresh.md).

### App won't start after reset

Check container logs: `docker compose logs app`. The most common cause is a migration error or a stale database file. Re-run `bb db reset` and rebuild.

---

## Related Docs

- [Bootstrap Guide](bootstrap-guide.md) -- Full credential capture paths (proxy, curl, mobile)
- [Credential Refresh](credential-refresh.md) -- Start here when auth fails
- [Operations](operations.md) -- Standalone reports reference, database backup, and monitoring
- [Getting Started](getting-started.md) -- First-time dev environment setup from a fresh clone

---

*Last updated: 2026-07-08 | Source: E-228 (empty reset, admin-sees-all), E-127-05 (original), E-239 (rewritten to reports-first: removed dashboard step, member-sync step), E-255-05 (Truth Sweep: corrected the post-reset health-check URL from :8000 to :8001)*
