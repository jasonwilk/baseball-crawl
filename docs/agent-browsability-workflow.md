# Agent Browsability Workflow

**Reference doc for**: E-004 (Coaching Dashboard epic)
**Created**: 2026-03-02
**Verification source**: E-009-06 research note at `.project/research/E-009-agent-browsability-verification.md`

---

## Purpose

This document defines the standard workflow for using the baseball-coach agent to review
dashboard changes during development. It replaces any guesswork about which HTTP
mechanism works for agents fetching localhost URLs.

**Key finding from E-009-06**: The `WebFetch` tool does NOT accept `localhost` URLs
(returns "Invalid URL"). The `Bash` tool with `curl` is the confirmed working fallback
and is the recommended mechanism going forward.

---

## Standard Workflow

### Step 1: Start the Stack

```bash
cd /path/to/baseball-crawl
docker compose up -d
```

Wait for the app to be healthy (about 15-20 seconds):

```bash
docker compose ps
# Confirm: baseball-crawl-app-1 status shows (healthy)
```

Verify connectivity:

```bash
curl -s -H "Host: baseball.localhost" http://localhost:8000/health
# Expected: {"status":"ok","db":"connected"}
```

If the database has no data, seed it:

```bash
# Run from the project root (not inside the container -- scripts/ is host-only)
DATABASE_PATH=./data/app.db python3 scripts/seed_dev.py
```

**Note on the Host header**: Traefik routes requests by hostname. All curl commands must
include `-H "Host: baseball.localhost"` or you will receive a 404 from Traefik's catch-all
handler. The app container responds on port 8000 internally; traffic reaches it through
Traefik on host port 8000.

---

### Step 2: Fetch the Dashboard HTML

Use `curl` in the Bash tool to retrieve the rendered HTML:

```bash
curl -s -H "Host: baseball.localhost" http://localhost:8000/dashboard
```

This returns the full server-rendered HTML including any Jinja2-templated stat tables.
Tailwind CDN styling is applied client-side, so the HTML you see is unstyled structurally --
but all content (player names, stats, table structure) is present in the server-rendered
response.

---

### Step 3: Invoke the Baseball-Coach Agent for UX Feedback

Pass the HTML output from Step 2 into a baseball-coach invocation. The standard prompt:

```
Please review the following HTML from the LSB [Team] dashboard and provide UX feedback:

1. Can you see the stat table content? Is the layout useful for game prep?
   (Quote one specific player row from the table.)
2. Is the mobile layout adequate for dugout use at a 375px viewport?
   (Consider: header stickiness, font size, scroll behavior, tap target size.)
3. What is one specific improvement you recommend for the next dashboard iteration?
   Label your recommendation as MUST HAVE, SHOULD HAVE, or NICE TO HAVE.

[PASTE HTML HERE]
```

The baseball-coach agent reads the raw HTML and provides structured feedback based on
its domain knowledge of high school baseball coaching needs.

---

### Step 4: Review Feedback and Iterate

After receiving baseball-coach feedback:

1. **Capture the feedback** in the relevant story's notes or a research artifact.
2. **Classify each recommendation** (MUST HAVE / SHOULD HAVE / NICE TO HAVE) if the
   baseball-coach did not already label it.
3. **Open a story or add to backlog** for any MUST HAVE items that are not already covered
   by the current epic's acceptance criteria.
4. **Make changes** to the template or route handler as appropriate.
5. **Repeat**: Re-fetch the updated dashboard and re-invoke baseball-coach for the
   changed section.

---

## URL Reference

| Route | Description | curl command |
|-------|-------------|--------------|
| `/health` | Health check | `curl -s -H "Host: baseball.localhost" http://localhost:8000/health` |
| `/dashboard` | Batting stats dashboard | `curl -s -H "Host: baseball.localhost" http://localhost:8000/dashboard` |
| Traefik dashboard | Routing debug UI | Open `http://localhost:8180` in browser (no Host header needed) |

---

## Why Not WebFetch?

`WebFetch` is the intuitive choice for agents to retrieve web content, but it refuses
`localhost` URLs entirely. This was confirmed in E-009-06:

- Attempted: `WebFetch("http://localhost:8000/dashboard", ...)`
- Result: `Invalid URL` error -- tool refuses localhost addresses

This is expected behavior: WebFetch is designed for public URLs, not local development
servers. The Bash `curl` approach is equally capable for our purposes and has no such
restriction.

**For production dashboards** (after Cloudflare Tunnel is configured in E-009-04), the
baseball-coach agent will be able to use WebFetch against the public Cloudflare Access URL
without any workaround. The curl fallback is only needed in local development.

---

## Teardown

When done with dashboard review:

```bash
docker compose down
```

The SQLite database persists in `./data/app.db` (host-mounted volume). Data is not lost
on container stop. Use `docker compose down -v` only if you want to reset volumes.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `404 page not found` from curl | Missing `Host` header | Add `-H "Host: baseball.localhost"` to your curl command |
| `{"status":"ok","db":"connected"}` but table shows "No stats available" | Database not seeded | Run `DATABASE_PATH=./data/app.db python3 scripts/seed_dev.py` |
| App container not healthy | Startup still in progress | Wait 15-20 seconds, retry `docker compose ps` |
| Cloudflared service restarting | No `CLOUDFLARE_TUNNEL_TOKEN` in `.env` | Expected in local dev; ignore for dashboard review |
