# API Scout -- Agent Memory

## Credential Lifecycle

**Three-token architecture confirmed 2026-03-07. Programmatic refresh CONFIRMED WORKING.**

**gc-signature CRACKED 2026-03-07.** Algorithm: `{nonce}.{hmac}` where nonce=Base64(32 random bytes) and hmac=HMAC-SHA256(clientKey, timestamp|nonce_bytes|sorted_body_values[|prevSig_bytes]). Full details: `data/raw/gc-signature-algorithm.md`, `docs/api/auth.md`.

**Three token types:**
- **CLIENT token** (exp-iat = 600s = 10 min): `type:"client"`, `sid`, `cid`, `iat`, `exp`. Anonymous session token.
- **ACCESS token** (~61 min web / ~12 hours mobile): `type:"user"`, `cid`, `email`, `userId`, `rtkn`, `iat`, `exp`. Sent as gc-token in all standard API calls.
- **REFRESH token** (14 days, self-renewing): `id` (uuid:uuid), `cid`, `uid`, `email`, `iat`, `exp`. No `type` field, different `kid`. Sent as gc-token in POST /auth refresh calls.

**.env variables:** `GAMECHANGER_REFRESH_TOKEN_WEB`, `GAMECHANGER_CLIENT_ID_WEB`, `GAMECHANGER_CLIENT_KEY_WEB` (SECRET), `GAMECHANGER_DEVICE_ID`, `GAMECHANGER_USER_EMAIL`, `GAMECHANGER_USER_PASSWORD`.

**Mobile profile:** Mobile client IDs are version-specific and rotate with app updates. `0f18f027-...` = Odyssey/2026.8.0 (iOS 26.3.0), `23e37466-2878-43f4-a9f8-5f1751b7efcf` = Odyssey/2026.9.0 (iOS 26.3.1, current as of 2026-03-12). Web client ID: `07cb985d-...`. Mobile client key UNKNOWN (iOS binary). Programmatic mobile refresh NOT POSSIBLE.

**Token validity check**: `GET /me/user` returns 200 OK (valid) or 401 (expired).

**REFRESH TOKEN STATUS**: Last known expired 2026-03-09. Session 2026-03-11_032625 captured new web session data -- credentials must have been refreshed between 2026-03-09 and 2026-03-11.

Credentials are NEVER logged, committed, or displayed. Redact to `{AUTH_TOKEN}` in all docs.

## API Spec Location

Single source of truth: `docs/api/` -- index at `docs/api/README.md`, per-endpoint files in `docs/api/endpoints/` (120 endpoint files + web-routes reference = 121 total as of 2026-03-12).

## Exploration Status

As of 2026-03-12. See `docs/api/README.md` for full endpoint index.

## Topic File Index

- [exploration-findings.md](exploration-findings.md) -- Detailed session findings: 2026-03-09 (opponent import flow, game creation, mobile search, progenitor_team_id full access confirmed), 2026-03-11 (E-094 constraints confirmed, gc-user-action values, athlete profile hierarchy, 10 new endpoints), 2026-03-12 (follow-gating confirmed, unfollow 2-step sequence, notification settings, iOS app version). Also: iOS app identity, opponent ID hierarchy (root vs progenitor vs public_id), HTTP 500/404/403 patterns.
- [operational-notes.md](operational-notes.md) -- High-priority unexplored areas (POST /search schema, LSB HS credentials, import-summary), boxscore critical facts (game_stream.id, asymmetric keys, groups), JWT decode tips (exp-iat thresholds), security rules and PII hotspots.
- [mobile-auth-notes.md](mobile-auth-notes.md) -- Mobile authentication specifics and credential capture workflow.
- [client-id-rotation.md](client-id-rotation.md) -- GC client IDs rotate on web redeployments and iOS app updates; never assume permanence
- [search-endpoint-notes.md](search-endpoint-notes.md) -- POST /search folds diacritics server-side; narrow-regex recommendation; 2026-04-16 punct-failure claim didn't fully reproduce 2026-04-17
