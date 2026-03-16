---
paths:
  - "docker-compose.yml"
  - "Dockerfile"
  - "requirements.txt"
  - "migrations/**"
---

# App Troubleshooting

All commands run from `/workspaces/baseball-crawl`. App is at `http://localhost:8001` inside the devcontainer.

## Stack Management

```bash
docker compose up -d           # start the stack (detached)
docker compose down            # stop and remove containers
docker compose restart app     # restart app service only
docker compose ps              # show running containers and ports
```

## Health Check

```bash
curl -s http://localhost:8001/health   # direct (expect 200 OK)
curl -s -H "Host: baseball.localhost" http://localhost:8000/health  # via Traefik
```

## Logs

```bash
docker compose logs app            # full log history
docker compose logs -f app         # follow live logs (Ctrl-C to exit)
docker compose logs --tail=50 app  # last 50 lines
docker compose logs app 2>&1 | grep -A 10 "ERROR\|Traceback"  # errors and tracebacks only
```

## Rebuild After Changes

After changing source code or migrations, rebuild and restart the app container so changes take effect:

```bash
docker compose up -d --build app   # rebuild image and restart app
```

## When the App Is Unreachable

1. `docker info` -- error means Docker daemon is down.
2. `docker compose ps` -- `app` must show `Up`.
3. `docker compose logs app` -- check for startup errors or port conflicts.
4. `lsof -i :8001` -- if occupied, stop the conflicting process.
5. `docker compose restart app` -- then re-curl.

## When to Check App Health

After any change to files in `src/`, `migrations/`, `Dockerfile`, `docker-compose.yml`, or `requirements.txt`, rebuild and verify the health check passes before marking work as done.
