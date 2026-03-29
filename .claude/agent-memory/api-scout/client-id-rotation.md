---
name: GC Client ID Rotation
description: GameChanger client IDs are not stable across deployments -- web IDs rotate on JS redeployments, mobile IDs rotate on iOS app updates
type: reference
---

## Client ID Rotation

GameChanger client IDs are **not permanent**. They rotate on two independent schedules:

### Web Client IDs/Keys
- Bundle-embedded in the GC JavaScript application
- Rotate whenever GC redeploys their web frontend (no advance notice)
- Both `GAMECHANGER_CLIENT_ID_WEB` and `GAMECHANGER_CLIENT_KEY_WEB` change together

### Mobile Client IDs
- Version-specific: each iOS app release ships a new client ID
- Rotate with iOS app updates (tied to Odyssey version string)
- `GAMECHANGER_CLIENT_KEY_MOBILE` is unknown (embedded in iOS binary, not extracted)

### Implication for Agents
- **Never assume client ID permanence.** A working client ID today may be invalid tomorrow.
- Current values live in `.env` -- specifically `GAMECHANGER_CLIENT_ID_WEB` and `GAMECHANGER_CLIENT_KEY_WEB`.
- `GAMECHANGER_CLIENT_KEY_MOBILE` is commented out / unknown in `.env`.
- When auth failures occur, client ID rotation is a possible root cause alongside token expiration.
