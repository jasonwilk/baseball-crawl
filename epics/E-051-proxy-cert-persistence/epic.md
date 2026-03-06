# E-051: Fix mitmproxy CA Certificate Persistence

## Status
`READY`

## Overview
mitmproxy CA certificates do not survive container recreation. Each time the proxy container is stopped and restarted, new certificates are generated, forcing the operator to reinstall the CA cert on the iPhone. The volume mount exists but is ineffective due to a permissions mismatch between the host directory and the container's `mitmproxy` user.

## Background & Context
The proxy stack (`proxy/docker-compose.yml`) already has a bind mount from `./certs` to `/home/mitmproxy/.mitmproxy` -- the directory where mitmproxy stores its CA keypair. `start.sh` creates the `certs/` directory on the host before launching the container.

However, the directory is created with the host user's ownership. The official `mitmproxy/mitmproxy` Docker image runs as the `mitmproxy` user (UID 1000). When the container starts and mitmproxy tries to write its CA cert into `/home/mitmproxy/.mitmproxy`, it may lack write permission to the bind-mounted directory, causing mitmproxy to either regenerate certs to a different location or regenerate them each time the writable layer resets.

The fix is to ensure the entrypoint sets correct ownership/permissions on the cert directory before mitmproxy starts, so the generated CA keypair is written to the persistent bind mount and survives container recreation.

No expert consultation required -- this is a straightforward infrastructure bug fix within the existing proxy stack.

## Goals
- CA certificates persist across `./stop.sh` + `./start.sh` cycles (container recreation)
- iPhone cert trust survives proxy container restarts without reinstallation

## Non-Goals
- Changing the proxy architecture or addon system
- Adding cert rotation or expiry management
- Modifying the mitmproxy image itself (no custom Dockerfile)

## Success Criteria
- After `./stop.sh && ./start.sh`, the CA cert fingerprint in `proxy/certs/` is unchanged
- An iPhone with the cert previously installed can still proxy HTTPS traffic without reinstalling

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-051-01 | Fix cert directory permissions in proxy entrypoint | TODO | None | - |

## Dispatch Team
- software-engineer

## Technical Notes

### Root Cause
The `mitmproxy/mitmproxy` Docker image runs as the `mitmproxy` user. The bind mount target (`/home/mitmproxy/.mitmproxy`) must be writable by this user. When `start.sh` runs `mkdir -p certs` on the host, the directory is owned by the host user (likely UID 501 on macOS or UID 1000 in the devcontainer). If the container's `mitmproxy` user cannot write to it, certs are generated ephemerally and lost on container removal.

### Fix Approach
Add a permissions fix to `proxy/proxy-entrypoint.sh` that runs before `exec mitmweb`. The entrypoint should ensure `/home/mitmproxy/.mitmproxy` is writable by the mitmproxy user. Two approaches:

1. **chmod the directory** (simplest): `chmod 777 /home/mitmproxy/.mitmproxy` or `chmod a+rwx` -- works regardless of UID mapping. Acceptable since this is a local dev tool, not a production service.
2. **chown the directory** (cleaner): `chown mitmproxy:mitmproxy /home/mitmproxy/.mitmproxy` -- but requires running the entrypoint as root and then dropping privileges with `su-exec` or `gosu`, which the stock image may not have.

Option 1 is preferred for simplicity. The entrypoint already runs as the container user, so if it can't chmod, the alternative is to run the container with `user: root` in docker-compose.yml and have the entrypoint fix perms then exec as mitmproxy. Check which approach works with the stock image.

### Key Files
- `proxy/proxy-entrypoint.sh` -- entrypoint script, needs permissions fix
- `proxy/docker-compose.yml` -- may need `user: root` if the entrypoint can't chmod as the default user
- `proxy/start.sh` -- may need the `mkdir -p` to set group/other write bits

## Open Questions
None -- the diagnosis is clear and the fix is small.

## History
- 2026-03-06: Created. Bug reported by user: certs regenerate on every container restart, requiring iPhone CA reinstall.
