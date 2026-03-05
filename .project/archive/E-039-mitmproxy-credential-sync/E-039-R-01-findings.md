# E-039-R-01: mitmproxy Addon Ecosystem -- Research Findings

**Date**: 2026-03-05
**Status**: Complete
**Researcher**: product-manager (based on mitmproxy documentation and ecosystem knowledge)

---

## 1. Existing Addons

### Credential/Header Extraction Addons
No published mitmproxy addons specifically target "credential extraction from headers to .env files." The use case is too project-specific. However, several related projects exist:

- **mitmproxy built-in export**: mitmproxy can export flows as curl commands, HAR files, or raw data. This is UI-driven, not addon-driven, and does not write to `.env`.
- **mitmproxy-har-dump** (built-in example addon): Dumps all traffic to HAR format. Too broad -- captures everything, not just credentials. Not useful as-is.
- **mitmproxy scripting examples** (in mitmproxy repo under `examples/addons/`): Include simple request/response loggers, header modifiers, and filter examples. Good reference for addon structure but none match our use case.

### API Logging/Discovery Addons
- **mitmproxy's built-in `mitmdump` with `-w`**: Writes all flows to a binary file. Can be replayed/analyzed later. Not JSONL, not filtered.
- No published addon specifically produces a deduplicated API endpoint log in JSONL format.

### Recommendation
**Build all addons from scratch.** The use cases are too specific (GameChanger domain filtering, `.env` integration, source detection) for any existing addon to cover even 50%. The mitmproxy addon API is simple enough that custom addons are straightforward.

## 2. Addon API Surface

### Key Hooks for Our Use Cases

| Hook | When Fired | Use Case |
|------|-----------|----------|
| `request(flow: http.HTTPFlow)` | When a client request is received (before forwarding to server) | Header capture, credential extraction (headers available), domain filtering |
| `response(flow: http.HTTPFlow)` | When server response is received (before forwarding to client) | Endpoint logging (need status code), credential extraction (alternative) |
| `configure(updated: set[str])` | When addon options change or on startup | One-time initialization |
| `load(loader: Loader)` | When the addon is first loaded | Register options, initialize state |

### Flow Object API
```python
from mitmproxy import http

def request(self, flow: http.HTTPFlow):
    # Request attributes
    flow.request.host        # "api.gc.com"
    flow.request.port        # 443
    flow.request.method      # "GET"
    flow.request.path        # "/teams/123/stats"
    flow.request.url         # Full URL
    flow.request.query       # MultiDictView of query params
    flow.request.headers     # Headers (case-insensitive dict-like)
    flow.request.headers["gc-token"]  # Access specific header
    flow.request.headers.get("gc-token", "")  # Safe access

def response(self, flow: http.HTTPFlow):
    # Response attributes
    flow.response.status_code  # 200
    flow.response.headers      # Response headers
```

### Flow Metadata (Addon-to-Addon Communication)
```python
# Set metadata in one addon
flow.metadata["gc_source"] = "ios"

# Read metadata in another addon
source = flow.metadata.get("gc_source", "unknown")
```
This is the recommended pattern for addon-to-addon communication. Metadata is per-flow and available to all addons processing that flow.

### Built-in Filtering
mitmproxy supports flow filters via command-line (`--set flow_filter=...`) but for our use case, programmatic filtering in the addon (via `gc_filter.is_gamechanger_domain()`) is more flexible and testable.

### Logging
```python
from mitmproxy import ctx

ctx.log.info("Message")   # Standard log
ctx.log.warn("Warning")
ctx.log.error("Error")
```

## 3. Docker Image Environment

### Python Version
The `mitmproxy/mitmproxy` Docker image (latest/11.x) ships with **Python 3.12+** (the image is Alpine-based and bundles the Python version mitmproxy was built with). mitmproxy 11.x requires Python 3.12+.

### Pre-installed Packages
The image includes mitmproxy and all its dependencies:
- `mitmproxy` (core library)
- `cryptography` (for TLS/cert handling)
- `certifi`
- `h2` (HTTP/2)
- `hyperframe`
- Standard library modules (`json`, `pathlib`, `logging`, `urllib.parse`, etc.)

### What is NOT Pre-installed
- `python-dotenv` is NOT in the image
- `requests` / `httpx` are NOT in the image (not needed -- we use mitmproxy's flow objects)

### Custom Dockerfile Needed?
**No.** Our addons do not need `python-dotenv`. The `merge_env_file()` function in `src/gamechanger/credential_parser.py` uses only standard library (`pathlib`). Since the project root is mounted at `/app`, addons can import it directly. No additional pip packages are required.

The only reason to create a custom Dockerfile would be if we needed to install additional Python packages. Since we do not, we can use the stock `mitmproxy/mitmproxy` image directly.

### sys.path Configuration
For addons to `import src.gamechanger.credential_parser`, the project root (`/app`) must be on `sys.path`. Two approaches:
1. **Environment variable**: Set `PYTHONPATH=/app` in the Docker Compose service definition.
2. **In-addon sys.path manipulation**: `sys.path.insert(0, "/app")` at the top of each addon.

**Recommendation**: Use `PYTHONPATH=/app` in docker-compose.yml (cleaner, one place).

## 4. Configuration Options

### Addon Loading
Addons are loaded via the `--scripts` flag (can be specified multiple times) or via `--set scripts=...`:

```bash
# Multiple addons
mitmweb --scripts /app/mitmproxy/addons/credential_extractor.py \
        --scripts /app/mitmproxy/addons/header_capture.py \
        --scripts /app/mitmproxy/addons/endpoint_logger.py
```

Alternatively, a single "loader" script can instantiate and return multiple addon classes:

```python
# addons/loader.py
from credential_extractor import CredentialExtractor
from header_capture import HeaderCapture
from endpoint_logger import EndpointLogger

addons = [
    CredentialExtractor(),
    HeaderCapture(),
    EndpointLogger(),
]
```

Then load with `--scripts /app/mitmproxy/addons/loader.py`. The `addons` list at module level is the convention mitmproxy uses to discover addon instances.

**Recommendation**: Use a single loader script. Simpler Docker Compose command, and the addons can share imports (like `gc_filter`).

### Multiple Addons Running Concurrently
Yes, fully supported. Each addon receives every flow event. Addons run in the order they are loaded. Flow metadata is the recommended communication mechanism between addons (see Section 2).

### Configuration File
mitmproxy supports `~/.mitmproxy/config.yaml` for persistent configuration. In Docker, this would be at `/home/mitmproxy/.mitmproxy/config.yaml`. However, for our use case, command-line flags in docker-compose.yml are simpler and more transparent.

## 5. mitmweb vs. mitmdump vs. mitmproxy

| Variant | UI | Headless | Scripts Support | Best For |
|---------|-----|---------|-----------------|----------|
| `mitmproxy` | Terminal (curses) | No | Yes | Interactive terminal use |
| `mitmweb` | Web UI (port 8081) | Background-capable | Yes | **Our use case** |
| `mitmdump` | None | Yes | Yes | CI/automation, no UI needed |

### Recommendation: **mitmweb**

- Provides the web UI on port 8081 for inspecting traffic visually
- Fully supports `--scripts` for addon loading
- Can run as a background Docker service
- The web UI is valuable for debugging proxy issues and inspecting captured traffic

**Docker entrypoint**: The `mitmproxy/mitmproxy` image defaults to running `mitmproxy` (terminal UI). Override with:
```yaml
entrypoint: ["mitmweb"]
command: ["--web-host", "0.0.0.0", "--scripts", "/app/mitmproxy/addons/loader.py"]
```

The `--web-host 0.0.0.0` flag is required so the web UI is accessible from outside the container (default is `127.0.0.1`).

## 6. Certificate Persistence

### How It Works
On first startup, mitmproxy generates a CA certificate and private key at `~/.mitmproxy/` (inside the container: `/home/mitmproxy/.mitmproxy/`). Files generated:
- `mitmproxy-ca.pem` (CA certificate)
- `mitmproxy-ca-cert.cer` (CA cert in DER format, for iOS/Android import)
- `mitmproxy-ca-cert.p12` (PKCS12 format)
- `mitmproxy-ca.p12` (CA key + cert)
- `mitmproxy-dhparam.pem` (DH parameters)

### Persistence Strategy
**Named Docker volume** mounted at `/home/mitmproxy/.mitmproxy`:
```yaml
volumes:
  - mitmproxy-certs:/home/mitmproxy/.mitmproxy
```

This persists the CA cert across container restarts and rebuilds. The iPhone only needs to trust the cert once (as long as the volume is not deleted).

### Verification
After restart, compare the CA cert fingerprint:
```bash
docker compose exec mitmproxy openssl x509 -in /home/mitmproxy/.mitmproxy/mitmproxy-ca.pem -fingerprint -noout
```

## 7. iOS Proxy Configuration

### Setup Steps (iOS 17+)
1. **Configure proxy**: Settings > Wi-Fi > [network] > Configure Proxy > Manual
   - Server: LAN IP of the Docker host (e.g., `192.168.1.x`)
   - Port: `8080`
2. **Install CA cert**: Open Safari, navigate to `mitm.it`. Tap the Apple icon to download the profile.
3. **Install profile**: Settings > General > VPN & Device Management > mitmproxy > Install
4. **Trust CA cert**: Settings > General > About > Certificate Trust Settings > Enable full trust for mitmproxy

### Known Gotchas (iOS 17+)
- **Step 4 is mandatory and separate from Step 3.** Installing the profile (Step 3) is not enough -- you must also enable full trust (Step 4). This is a common source of "certificate not trusted" errors.
- **`mitm.it` only works when traffic is actively flowing through the proxy.** If the proxy is not running or the device is not configured to use it, `mitm.it` shows an error page.
- **iOS may cache proxy settings.** If switching between proxy on/off, sometimes toggling Wi-Fi off/on helps.
- **Certificate expiration**: mitmproxy CA certs are valid for ~10 years by default. Not a concern for our use case.

### The `mitm.it` Page
Still works reliably on iOS 17+. It detects the device type and offers the appropriate certificate format. The page is served by mitmproxy itself (not an external service), so it requires traffic to flow through the proxy.

## Recommendations Summary

### (a) Existing Addons to Reuse vs. Build
**Build all four addons from scratch.** No existing addon covers our specific needs (GameChanger domain filtering, `.env` credential writing, header parity reports, JSONL endpoint logging). The mitmproxy addon API is simple enough that custom addons are straightforward (each is ~50-100 lines).

### (b) mitmproxy Variant
**Use `mitmweb`** for the Docker service. It provides the web UI for traffic inspection while fully supporting script loading.

### (c) Custom Docker Image
**Not needed.** The stock `mitmproxy/mitmproxy` image has everything we need. Set `PYTHONPATH=/app` in the compose service environment to enable project module imports. No additional pip packages required.

### (d) Design Changes to Epic Technical Notes

1. **Add a loader script**: Instead of loading each addon separately via `--scripts`, create `mitmproxy/addons/loader.py` that exports an `addons` list. This simplifies the Docker Compose command to a single `--scripts` flag. Add this to the File Layout in Technical Notes.

2. **PYTHONPATH configuration**: Add `PYTHONPATH=/app` to the mitmproxy service's `environment` section in docker-compose.yml. This is cleaner than per-addon `sys.path` manipulation.

3. **mitmweb entrypoint**: The Docker Compose service should use `entrypoint: ["mitmweb"]` with `command: ["--web-host", "0.0.0.0", "--scripts", "/app/mitmproxy/addons/loader.py"]`. The `--web-host 0.0.0.0` flag is essential for external access to the web UI.

4. **gc_filter.py does not need mitmproxy flow metadata**: The epic Technical Notes mention "sets a flow metadata key" -- but `gc_filter.py` is a pure utility module. The individual addons call `gc_filter.detect_source(user_agent_string)` and can optionally set flow metadata themselves. This is consistent with the current Technical Notes ("pure Python, no mitmproxy imports").

5. **No changes needed to**: port strategy (8080/8081), volume mount approach, certificate persistence via named volume, `.env` integration via `merge_env_file()`, or the overall addon architecture.

## Open Questions Resolved

| Question | Resolution |
|----------|-----------|
| Reuse existing addons? | No -- build all from scratch |
| JSONL vs. summary for endpoint logger? | JSONL (append-only) as planned, with downstream dedup |
| Additional Python packages needed? | No -- `merge_env_file()` uses only stdlib |
| mitmweb with --scripts? | Yes, fully supported |
| Certificate persistence approach? | Named volume at `/home/mitmproxy/.mitmproxy` |
