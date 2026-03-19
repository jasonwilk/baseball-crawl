# Post-Reset Onboarding Guide

This guide covers the end-to-end workflow for going from a fresh `bb db reset` to a working local environment with real GameChanger data.

---

## Step 1: Reset the Database

```bash
bb db reset
```

This drops and recreates the database, applies all migrations, and seeds placeholder data. The app needs to restart after a reset.

```bash
docker compose up -d --build app
```

Verify the app is healthy:

```bash
curl -s http://localhost:8000/health
```

Expected: `{"status": "ok", "db": "connected"}`.

---

## Step 2: Set Up Credentials

Credentials must be in `.env` before crawling. Two parts: the client key and the API tokens.

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

`bb creds extract-key` handles multiple `EDEN_AUTH_CLIENT_KEY` candidates automatically, selecting the correct one by matching against `GAMECHANGER_CLIENT_ID_WEB`.

### 2b. Import API credentials

If you don't have a refresh token yet (fresh reset with no `.env`), capture credentials from your browser:

1. Log in to [web.gc.com](https://web.gc.com) in Chrome.
2. Open DevTools → Network tab → trigger any request (navigate to a team page).
3. Right-click any `api.team-manager.gc.com` request → **Copy > Copy as cURL**.
4. Import:

```bash
bb creds import
```

`bb creds import` accepts curl commands, raw JSON token payloads, and bare JWT strings -- paste any of these into `secrets/gamechanger-curl.txt` before running, or pass inline:

```bash
bb creds import --curl 'curl ...'
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

## Step 3: Add Teams via Admin UI

The admin UI at `/admin/teams` is the primary path for adding real teams to the database.

**1. Open the teams page:**

Navigate to `http://localhost:8000/admin/teams`. The Admin link is in the top navigation bar.

**2. Click Add Team** and paste a GameChanger team URL:

```
https://web.gc.com/teams/XXXXXX/schedule
```

The URL parser also accepts any URL containing `/teams/{id}` or a bare public ID slug.

**3. Review the confirm page:**

The system resolves the team name, public ID, and GameChanger UUID automatically. On the confirm page:

- Set **Membership** to **Member** for your own teams (LSB Varsity, JV, Freshman, Reserve), or **Tracked** for opponents.
- Optionally assign a **Program** (e.g., Lincoln Standing Bear HS) and **Division** (e.g., varsity, jv).

**4. Click Add Team** to save.

Repeat for each member team.

---

## Step 4: Verify Dev User Access

The dev user is automatically assigned to all member teams on the first request to the dashboard -- no manual SQL required.

To verify:

1. Navigate to `http://localhost:8000/` (or any team dashboard page).
2. The first request triggers auto-assignment. The dashboard should display batting stats for your team. (If you have multiple member teams, a team selector will also appear.)

If member teams don't appear, check that they were added with **Membership: Member** (not Tracked) in step 3. You can correct this via the Edit link on the teams list.

---

## Step 5: Run the Initial Crawl

With teams in the database, pull real data:

```bash
bb data crawl --source db
bb data load --source db
```

`--source db` reads active member teams directly from the database (the teams you added in step 3).

Check the results:

```bash
bb status
```

Alternatively, the full pipeline in one command:

```bash
bb data sync
```

---

## Troubleshooting

### "No teams configured" / empty crawl

Make sure teams were added via the admin UI with **Membership: Member** and that the app has been restarted after the reset (`docker compose up -d --build app`).

### Dev user still not seeing teams after step 4

Confirm member teams show `membership_type = member` in the admin list at `/admin/teams`. If they show as Tracked, edit each team and change the membership radio to Member.

### Credential errors during crawl

Run `bb creds check --profile web` and follow the Decision Tree in [docs/admin/credential-refresh.md](credential-refresh.md).

### App won't start after reset

Check container logs: `docker compose logs app`. The most common cause is a migration error or a stale database file. Re-run `bb db reset` and rebuild.

---

## Related Docs

- [Bootstrap Guide](bootstrap-guide.md) -- Full credential capture paths (proxy, curl, mobile)
- [Credential Refresh](credential-refresh.md) -- Start here when auth fails
- [Operations](operations.md) -- Team management, database backup, and monitoring
- [Getting Started](getting-started.md) -- First-time dev environment setup from a fresh clone

---

*Last updated: 2026-03-19 | Story: E-127-05*
