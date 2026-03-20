# Credential Refresh Guide

When GameChanger API calls start failing, this guide walks you through getting everything working again. Start at the top and follow the path that matches your situation.

## Quick Diagnosis

Run this first to see what's broken:

```bash
bb creds check --profile web
```

Look at the status indicators:

| Indicator | Meaning |
|-----------|---------|
| `[OK]` | Working |
| `[!!]` | Warning (expiring soon) |
| `[XX]` | Failed / expired |
| `[--]` | Not configured |

## Decision Tree

```
bb creds check shows [XX] on...
│
├── Client Key Validation ──────► Path A: Client Key Rotation
│
├── Refresh Token ──────────────► Path B: Token Refresh (programmatic)
│   (and Client Key is [OK])       Usually automatic -- try this first
│
├── API Health (GET /me/user) ──► Path B first, then Path C if B fails
│
└── Multiple sections [XX] ─────► Path A, then Path B
```

If you're not sure what's wrong, start with **Path A** -- it's safe to run even if the key hasn't changed, and it rules out the most confusing failure mode.

---

## Path A: Client Key Rotation

The HMAC signing key comes from the GameChanger JavaScript bundle. When GC redeploys their web app, the key changes and all auth fails. This is the most common "everything is broken" scenario.

**No authentication required** -- the key is extracted from a public webpage.

### Steps

**1. Check if the key has changed (dry run):**

```bash
bb creds extract-key
```

This fetches the current key from `https://web.gc.com` and compares it to your `.env`. If it says "no update needed," the key is current -- skip to Path B.

**2. Apply the updated key:**

```bash
bb creds extract-key --apply
```

This writes the new `GAMECHANGER_CLIENT_ID_WEB` and `GAMECHANGER_CLIENT_KEY_WEB` to `.env`.

**3. Refresh tokens with the new key:**

```bash
bb creds refresh --profile web
```

**4. Verify everything works:**

```bash
bb creds check --profile web
```

All sections should show `[OK]`. Done.

---

## Path B: Token Refresh (Programmatic)

The normal day-to-day flow. Requires a valid client key. No browser interaction needed.

If the refresh token is still valid (within 14 days), it refreshes normally. If the refresh token is expired, the command automatically falls back to the full login flow using `GAMECHANGER_USER_EMAIL` and `GAMECHANGER_USER_PASSWORD` from `.env`.

### Steps

**1. Refresh the tokens:**

```bash
bb creds refresh --profile web
```

This calls `POST /auth {type:"refresh"}` using the stored refresh token and client key. If the refresh token is expired and email + password are in `.env`, it automatically performs the full login flow instead. On success, it writes a new access token and a new refresh token to `.env`.

**2. Verify:**

```bash
bb creds check --profile web
```

If this fails with a signature error, the client key may be stale -- go to **Path A**.

---

## Path C: Full Re-Capture (Browser)

Use this only when Path B fails **and** login fallback also fails (e.g., email/password not in `.env`, or password changed). This should be rare.

### Steps

**Recommended: re-run the setup wizard:**

```bash
bb creds setup web
```

This performs the full login flow interactively, regenerates a device ID, and writes all credentials to `.env`. Faster than the manual curl process below.

**Alternative: manual curl import** (if `bb creds setup web` is unavailable):

**1. Make sure the client key is current:**

```bash
bb creds extract-key --apply
```

**2. Log in to GameChanger** at [web.gc.com](https://web.gc.com) in Chrome.

**3. Open DevTools** (F12 or Cmd+Option+I).

**4. Go to the Network tab** and navigate to any team page to trigger API requests.

**5. Copy a request as cURL:**

- Right-click any `api.team-manager.gc.com` request in the Network tab
- Select **Copy > Copy as cURL**

**6. Import the credentials:**

Save the curl command to `secrets/gamechanger-curl.txt`, then:

```bash
bb creds import
```

Or pass it inline:

```bash
bb creds import --curl 'curl ...'
```

**7. Verify:**

```bash
bb creds check --profile web
```

---

## Path D: Mobile Profile

Mobile credentials are captured via mitmproxy on the Mac host -- not from the devcontainer. The mobile access token lasts ~12 hours. Programmatic refresh is not available for mobile (the iOS client key has not been extracted).

### Steps

**1. Start the proxy on the Mac host** (not in the devcontainer):

```bash
cd proxy && ./start.sh
```

**2. Configure iPhone proxy** to point to your Mac's IP on port 8080.

**3. Open GameChanger on the iPhone** -- the proxy addon captures credentials to `.env` automatically.

**4. Stop the proxy and disable iPhone proxy:**

```bash
cd proxy && ./stop.sh
```

**5. Validate and verify:**

```bash
bb creds capture --profile mobile
bb creds check --profile mobile
```

See [mitmproxy-guide.md](mitmproxy-guide.md) for the full proxy setup and iPhone configuration.

---

## After Refreshing Credentials

If the app container is running, restart it to pick up the new `.env` values:

```bash
docker compose restart app
```

To run a full data pipeline after refreshing:

```bash
bb data sync
```

---

## What Each Credential Is

| Variable | What It Is | Lifetime | How to Get It |
|----------|-----------|----------|---------------|
| `CLIENT_KEY_WEB` | HMAC signing key from GC JS bundle | Months (until GC redeploys) | `bb creds extract-key --apply` |
| `CLIENT_ID_WEB` | App identifier from same bundle | Same as client key | Same command |
| `REFRESH_TOKEN_WEB` | JWT for obtaining access tokens | 14 days (self-renewing) | `bb creds refresh`; optional when `GAMECHANGER_USER_EMAIL` + `GAMECHANGER_USER_PASSWORD` are set (login fallback handles renewal) |
| `ACCESS_TOKEN_WEB` | JWT for API calls | ~60 minutes | Generated automatically |
| `DEVICE_ID_WEB` | Stable hex device fingerprint | Permanent | Auto-generated by `bb creds setup web` (one-time) |
| `USER_EMAIL` | Account email | Permanent | Manual (one-time) |
| `USER_PASSWORD` | Account password | Until changed | Manual (one-time) |

The access token is generated on demand by `TokenManager` -- you almost never need to manage it manually.

## Login Fallback

When the refresh token expires and `GAMECHANGER_USER_EMAIL` + `GAMECHANGER_USER_PASSWORD` are set in `.env`, the system automatically performs the full login flow (client-auth, user-auth, password) to obtain new tokens. This means **Path C is rarely needed** as long as email and password are in `.env`.

The login fallback triggers on the `get_access_token()` path only -- `force_refresh()` does not attempt login.

---

## Troubleshooting

### "Everything was working yesterday, now nothing works"

Most likely a client key rotation. Run `bb creds extract-key` to check. See Path A.

### "Signature rejected" errors

The `gc-signature` HMAC is computed with a stale client key. This looks identical to an expired refresh token (both return HTTP 401). Run `bb creds extract-key` to check before concluding the refresh token is bad.

### "Credentials expired" but the refresh token isn't 14 days old

This is the stale-key false alarm. `bb creds check` will show the refresh token within its validity window, but refresh calls still fail. The client key is the problem. See Path A.

### Mobile token expired

Recapture via proxy. Mobile tokens can't be refreshed programmatically. See Path D.

---

*See also: [Bootstrap Guide](bootstrap-guide.md) | [Operations](operations.md) | [Auth Architecture](../api/auth.md) | [mitmproxy Guide](mitmproxy-guide.md)*
