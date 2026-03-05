# proxy/ -- Host-Based mitmproxy

Runs mitmproxy directly on the Mac host to capture GameChanger API traffic from an iPhone. Because it runs on the host (not inside Docker), the iPhone can reach it over LAN without any port-forwarding gymnastics.

## What it does

- Intercepts HTTPS traffic from an iPhone configured to use the proxy
- Logs and decodes API calls made by the GameChanger app
- Addons write captured credentials and endpoint data to the project root `.env` and `proxy/data/`
- The mitmweb UI lets you inspect captured traffic at `http://localhost:8081`

## Quick start

```bash
cd proxy
./start.sh      # launch (detached)
./status.sh     # check containers and port listeners
./logs.sh       # follow live log output
./stop.sh       # shut down
```

### Optional: set a mitmweb password

Copy `.env.example` to `.env` and set `MITMWEB_PASSWORD`:

```bash
cp .env.example .env
# Edit .env and set MITMWEB_PASSWORD=yourpassword
```

When `MITMWEB_PASSWORD` is unset or empty, mitmweb generates a token-based URL and prints it to the logs. Check `./logs.sh` for the URL.

## iPhone setup

Before capturing traffic, configure the iPhone to route through the proxy and trust the mitmproxy CA certificate.

### 1. Configure proxy

1. Start the proxy: `./start.sh` (note the LAN IP printed to the terminal)
2. On iPhone: **Settings > Wi-Fi > [your network] > Configure Proxy > Manual**
3. Server: `<LAN IP from start.sh>`  Port: `8080`

### 2. Install CA certificate

1. With the proxy running and the iPhone pointed at it, open **Safari** on the iPhone
2. Navigate to `http://mitm.it`
3. Tap the mitmproxy certificate and follow the prompts to install it
4. **Settings > General > VPN & Device Management > mitmproxy > Install**
5. **Settings > General > About > Certificate Trust Settings > toggle mitmproxy on**

The certificate is stored in `proxy/certs/` and persists across proxy restarts. You only need to install it once per iPhone.

## Devcontainer access

From inside the devcontainer, reach the host proxy via Docker's built-in DNS alias:

```
http_proxy=http://host.docker.internal:8080
```

Example:

```bash
curl -sx http://host.docker.internal:8080 http://mitm.it
```

A non-empty HTML response confirms the devcontainer-to-host-proxy path is working.

## Data and credentials

| Path | Contents |
|------|----------|
| `proxy/certs/` | mitmproxy CA certificate (persists across restarts) |
| `proxy/data/` | Addon output: captured endpoint logs, header reports |
| Project root `.env` | Credentials written by the credential-extractor addon |

Both `proxy/certs/` and `proxy/data/` are gitignored. `.env` is also gitignored at the project root.

## Python version note

The `mitmproxy/mitmproxy` Docker image ships Python 3.14. The project devcontainer runs Python 3.13. Addons execute under 3.14 at runtime inside the mitmproxy container. This is low risk because all addon code uses stdlib only -- no third-party packages that might have version-specific behavior.

## Troubleshooting

### Port 8080 already in use

```bash
./status.sh   # shows what is listening on 8080
```

Stop the conflicting process or change the port in `docker-compose.yml`. Note that changing the port also requires reconfiguring the iPhone proxy settings.

### iPhone can't connect to proxy

- Confirm the iPhone and Mac are on the same Wi-Fi network
- Run `./start.sh` and verify the LAN IP printed is reachable from the iPhone
- Try `ping <LAN IP>` from the iPhone (Settings > General > VPN... won't help; use a ping app)
- Check macOS firewall: **System Settings > Network > Firewall** -- ensure Docker is allowed or the firewall is off for testing
- Run `./status.sh` and confirm the container is `Up` and port 8080 has a listener

### Certificate not trusted / HTTPS sites fail

- Ensure you completed all four steps in the iPhone setup above, including the trust toggle
- The trust toggle is in **Settings > General > About > Certificate Trust Settings** (scroll to bottom)
- If you regenerated certs (deleted `proxy/certs/`), repeat the certificate install steps -- the old cert is now invalid
- Confirm mitmproxy is running: `./status.sh`
