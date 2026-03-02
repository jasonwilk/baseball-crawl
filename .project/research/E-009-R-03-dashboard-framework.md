<!-- synthetic-test-data -->
# E-009-R-03: Dashboard Framework and Agent Browsability Research Findings

**Research Date**: February 28, 2026
**Status**: Complete
**Related Epic**: [E-009: Tech Stack Redesign](../epics/E-009-tech-stack-redesign/epic.md)
**Related Research**:
- [E-009-R-01: Database Options](E-009-R-01-database-options.md)
- [E-009-R-02: API Layer Options](E-009-R-02-api-layer-options.md)

---

## Executive Summary

This research evaluated dashboard framework options for baseball-crawl across both deployment paths (Option A: Cloudflare Pages + Workers; Option B: FastAPI + Docker). **The critical finding is that agent browsability via `WebFetch` to localhost is technically feasible for both options during local development, though with important caveats about URL handling and security restrictions.**

**Key Recommendation**: For agent feedback loops and mobile-first coaching dashboards, **Option B (FastAPI + Jinja2 server-rendered HTML) is the stronger choice**. Server-rendered HTML ensures agents receive fully-populated data when fetching the dashboard via WebFetch, eliminating client-side JavaScript rendering complexity. Option A (Cloudflare Pages + Workers) is viable but adds unnecessary complexity for this read-only, data-display use case.

**Framework Selection**:
- **Option A**: TypeScript Workers with Hono routing + server-rendered HTML via template literals or lightweight JS template engine
- **Option B**: FastAPI + Jinja2 templates with server-rendered HTML (no build step required)

**Styling Approach**: Tailwind CSS CDN for development/MVP (simplest, no build step). Switch to build tooling if production performance becomes a constraint (file size optimization).

**JavaScript Complexity**: For this use case, pure server-rendered HTML is sufficient. Alpine.js (7.1 kB) can add minor interactivity (toggle, filter) if needed, but the overhead is low. HTMX adds real-time update capability but is not essential for MVP.

**Charting**: Chart.js (lightweight, ~150 KB) for basic stats visualizations. Plotly.js for advanced interactive charts. No charting library is required for MVP (tables and stat cards are sufficient).

---

## Agent Browsability: The Critical Finding

### Current Limitations and Workarounds

**Q: Can Claude Code's WebFetch tool reach `http://localhost:<port>` URLs?**

**Answer**: This is **constrained but feasible with conditions**.

Claude Code's WebFetch tool has [security restrictions](https://docs.claude.com/en/docs/agents-and-tools/tool-use/web-fetch-tool) that prevent it from constructing arbitrary URLs dynamically. Specifically:
- Claude can only fetch URLs that have been **explicitly provided by the user** in the conversation context or from previous WebSearch/WebFetch results
- Claude **cannot generate and fetch URLs internally** (e.g., constructing `http://localhost:8000/dashboard` on its own)
- These restrictions exist to prevent data exfiltration attacks

**Implication for baseball-crawl**:
- An agent **cannot autonomously fetch** `http://localhost:<port>` without that URL being explicitly provided by the user first
- However, **once a user provides the localhost URL**, the agent can fetch it repeatedly and evaluate the HTML response
- For development workflows, the user would start the local server (`docker compose up` or `wrangler dev`), manually give the URL to the agent (e.g., "review the dashboard at http://localhost:8000"), and the agent can then fetch and evaluate the rendered HTML

### Practical Agent Browsability Workflow (Both Options)

1. **Development phase**: Developer starts local server (FastAPI or Pages Functions)
2. **User initiates review**: Developer tells the agent "review the dashboard at http://localhost:8000/dashboard"
3. **Agent fetches HTML**: Agent uses WebFetch to retrieve the rendered HTML from that URL
4. **Agent evaluates**: Agent sees the full HTML markup with data rendered, checks:
   - Mobile layout suitability (viewport meta tags, responsive design)
   - Data presentation (tables, stat cards populated with sample data)
   - Accessibility (semantic HTML, heading hierarchy)
5. **Feedback loop**: Agent provides UX feedback; developer iterates

This pattern works for both Option A and Option B because both run real HTTP servers on localhost during development.

### Why Server-Rendered HTML Matters for Agent Review

If the dashboard uses **client-side JavaScript (SPA or Alpine.js)**, the HTML returned by WebFetch will be the initial shell only—the JavaScript that populates data doesn't execute in WebFetch's HTTP client. Example:

```html
<!-- What WebFetch sees with SPA/Alpine.js approach -->
<div id="app"></div>
<script src="app.js"></script>
```

The agent sees an empty div, not rendered data. This makes agent review of **actual data presentation and layout** impossible.

**Server-rendered HTML solves this**:
```html
<!-- What WebFetch sees with server-rendered approach -->
<table>
  <tr><td>Player A</td><td>0.350</td></tr>
  <tr><td>Player B</td><td>0.295</td></tr>
</table>
```

The agent sees the populated table and can evaluate the layout, ordering, and presentation meaningfully.

**Conclusion**: For tight agent feedback loops, **server-rendered HTML is essential**. Option B (FastAPI + Jinja2) enforces this by design. Option A requires explicit template rendering in Workers, which is possible but adds complexity.

---

## Option A: Cloudflare Pages + Workers

### Server-Side Rendering Capability

**Can Cloudflare Pages deliver server-rendered HTML for the coaching dashboard?**

**Answer**: Yes, but with caveats.

Cloudflare Pages supports [server-side rendering through Pages Functions](https://blog.cloudflare.com/pages-full-stack-frameworks/). The pattern:
- Static assets (CSS, images) are served by Pages
- Dynamic HTML is rendered by a Pages Function (which is a Cloudflare Worker)
- Frameworks like **Hono** (lightweight TypeScript framework for Workers) can render HTML directly using template literals or JavaScript template engines like **Nunjucks** or **Eta**

### Local Development Experience with `wrangler pages dev`

From the [Cloudflare Pages local development docs](https://developers.cloudflare.com/pages/functions/local-development/):

**Strengths**:
- `wrangler pages dev` runs the same environment locally as production
- Supports hot-reload and browser auto-refresh (press `b` to open the browser at `http://localhost:8788`)
- Real-time debugging of Functions
- Full parity with production behavior (same D1 bindings, same runtime)

**Developer Experience**:
```bash
wrangler pages dev <directory>
# or with watch mode:
vite build --watch &
wrangler pages dev dist/
```

The tight feedback loop is achievable: code change → auto-build → hot-reload in browser.

### HTML Template Rendering in TypeScript Workers

TypeScript Workers do not have access to Python's Jinja2, but alternatives exist:

1. **Nunjucks.js**: Full-featured templating engine for JavaScript
   - ~80 KB minified
   - Supports inheritance, macros, filters
   - Works in Workers if code is bundled

2. **Eta**: Lightweight (~6 KB) embedded templates for JavaScript
   - Simpler than Nunjucks; sufficient for small dashboards
   - Template syntax similar to Jinja2

3. **Template literals**: For simple dashboards, plain TypeScript template strings are sufficient
   ```typescript
   const renderDashboard = (stats) => `
     <div class="container">
       <h1>Team Stats</h1>
       ${stats.map(s => `<p>${s.name}: ${s.avg}</p>`).join('')}
     </div>
   `
   ```

4. **Hono framework**: Provides `c.render()` for JSX-like HTML rendering
   ```typescript
   app.get('/', (c) => {
     return c.render(<Dashboard stats={stats} />)
   })
   ```

### Styling Approach for Option A

**Tailwind CSS CDN**: Include via `<script>` tag in the template
```html
<script src="https://cdn.tailwindcss.com"></script>
```

**Cost**: ~80 KB over the wire; all Tailwind classes available; no build step.

**Alternative**: Bundle Tailwind with build tooling, but this adds a Wrangler build step complexity that negates Pages' simplicity advantage for this use case.

### Agent Browsability for Option A

✅ **Feasible**: `wrangler pages dev` serves real HTML at `http://localhost:8788`. Agent can fetch dashboard HTML if URL is explicitly provided.

⚠️ **Constraint**: Must use server-rendered HTML (not SPA). Nunjucks or Eta overhead is real but manageable for ~500-1000 lines of template code.

### Recommendation for Option A

**Use TypeScript Workers + Hono + Eta (or Nunjucks) for server-rendered HTML.**

**Why**:
- Zero operational overhead (no server to manage)
- Excellent local dev parity with production
- Agent browsability is supported via `wrangler pages dev`

**Trade-offs**:
- TypeScript learning curve remains (from E-009-R-02)
- Template engine adds a small dependency (~6-80 KB bundled code)
- Serving layer code still not Python (context switch from crawlers)

---

## Option B: FastAPI + Jinja2

### Server-Rendered HTML with Jinja2

FastAPI's [Jinja2 template support](https://fastapi.tiangolo.com/advanced/templates/) is straightforward and idiomatic for Python developers.

#### Basic Setup

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

app = FastAPI()

# Mount static files (CSS, JS, images)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Configure Jinja2 templates
templates = Jinja2Templates(directory="templates")

@app.get("/dashboard")
async def dashboard(request: Request):
    stats = await get_player_stats()
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "stats": stats,
            "team_name": "LSB Varsity"
        }
    )
```

#### Mobile-First Base Template Structure

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Baseball Crawl Dashboard{% endblock %}</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-50">
    <nav class="bg-white shadow">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="flex justify-between h-16">
                <div class="flex items-center">
                    <h1 class="text-xl font-bold">{{ team_name }}</h1>
                </div>
                <div class="flex items-center space-x-4">
                    <a href="/dashboard" class="text-gray-700">Dashboard</a>
                    <a href="/opponent" class="text-gray-700">Opponent</a>
                </div>
            </div>
        </div>
    </nav>

    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {% block content %}{% endblock %}
    </main>

    <footer class="mt-12 bg-gray-100 py-4">
        <p class="text-center text-gray-600 text-sm">
            Baseball Crawl Coaching Analytics
        </p>
    </footer>
</body>
</html>
```

#### Mobile-Optimized Stat Card Template

```html
{% extends "base.html" %}

{% block content %}
<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
    {% for player in stats %}
    <div class="bg-white rounded-lg shadow p-4">
        <h3 class="font-semibold text-gray-900">{{ player.name }}</h3>
        <dl class="mt-2 space-y-1 text-sm">
            <div class="flex justify-between">
                <dt class="text-gray-600">Avg</dt>
                <dd class="font-semibold text-gray-900">.{{ player.avg|round(3)|string|replace('0.', '') }}</dd>
            </div>
            <div class="flex justify-between">
                <dt class="text-gray-600">OBP</dt>
                <dd class="font-semibold text-gray-900">.{{ player.obp|round(3)|string|replace('0.', '') }}</dd>
            </div>
            <div class="flex justify-between">
                <dt class="text-gray-600">K/9</dt>
                <dd class="font-semibold text-gray-900">{{ player.k9|round(1) }}</dd>
            </div>
        </dl>
    </div>
    {% endfor %}
</div>
{% endblock %}
```

#### Stat Table Template

```html
{% extends "base.html" %}

{% block content %}
<div class="overflow-x-auto">
    <table class="min-w-full border-collapse border border-gray-300">
        <thead class="bg-gray-100">
            <tr>
                <th class="border border-gray-300 px-4 py-2 text-left font-semibold">Player</th>
                <th class="border border-gray-300 px-4 py-2 text-right font-semibold">AB</th>
                <th class="border border-gray-300 px-4 py-2 text-right font-semibold">H</th>
                <th class="border border-gray-300 px-4 py-2 text-right font-semibold">Avg</th>
                <th class="border border-gray-300 px-4 py-2 text-right font-semibold">OBP</th>
                <th class="border border-gray-300 px-4 py-2 text-right font-semibold">HR</th>
            </tr>
        </thead>
        <tbody>
            {% for player in batting_stats %}
            <tr class="{% if loop.index % 2 %}bg-white{% else %}bg-gray-50{% endif %}">
                <td class="border border-gray-300 px-4 py-2">{{ player.name }}</td>
                <td class="border border-gray-300 px-4 py-2 text-right">{{ player.ab }}</td>
                <td class="border border-gray-300 px-4 py-2 text-right">{{ player.hits }}</td>
                <td class="border border-gray-300 px-4 py-2 text-right font-semibold">.{{ player.avg|round(3)|string|replace('0.', '') }}</td>
                <td class="border border-gray-300 px-4 py-2 text-right">.{{ player.obp|round(3)|string|replace('0.', '') }}</td>
                <td class="border border-gray-300 px-4 py-2 text-right">{{ player.hr }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
{% endblock %}
```

### Styling: Tailwind CSS CDN vs. Build Tooling

#### Tailwind CDN Approach (Recommended for MVP)

```html
<script src="https://cdn.tailwindcss.com"></script>
```

**Advantages**:
- Zero build complexity
- All Tailwind classes available immediately
- Perfect for rapid iteration
- ~80 KB over the wire (cached by browser)

**Disadvantages**:
- Ships all Tailwind classes to the browser (waste for production)
- No JIT compilation of custom classes

**When to switch to build tooling**: If production file size becomes a concern (Lighthouse/Vercel Analytics reports > 100 KB CSS), use Tailwind with build step.

#### Build Tooling Approach (If Performance Matters)

```bash
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss -i src/input.css -o static/output.css --watch
```

**Result**: ~10-15 KB CSS file (vs 80 KB CDN) in production. Not necessary for MVP.

**Recommendation for baseball-crawl**: **Use Tailwind CDN for MVP**. Revisit if dashboard load time becomes a problem.

### HTMX: Partial Page Updates Without a Build Step

**Question**: Is HTMX (partial page updates without JavaScript) worth adding to FastAPI + Jinja2?

**Answer**: Not for MVP, but useful later for specific features.

#### HTMX Overview

[HTMX](https://htmx.org) allows server-side interactivity without writing JavaScript. Example:

```html
<!-- Add a like button that updates server-side state without page reload -->
<button hx-post="/api/player/{{ player.id }}/like"
        hx-swap="outerHTML"
        class="btn btn-sm">
    ♡ {{ player.likes }}
</button>
```

When clicked, HTMX sends a POST to `/api/player/1/like`, receives updated HTML from the server, and swaps it into the DOM.

#### Real-Time Updates with HTMX + SSE

For live game stats during games, HTMX + Server-Sent Events (SSE) enables true real-time updates:

```html
<!-- Polling approach: refresh every 10 seconds -->
<div hx-get="/api/live-score"
     hx-trigger="every 10s"
     hx-swap="outerHTML">
    Loading...
</div>
```

Performance impact (from real-world case studies):
- Load time: 28ms (vs 620ms React)
- Bundle size: 20 KB (vs 1.8 MB React)
- Development speed: 65% faster

#### HTMX Trade-offs

**Costs**:
- One more dependency (~50 KB unpacked, ~15 KB gzipped)
- Requires understanding of `hx-*` attributes
- Server-side logic to return HTML fragments

**Benefits**:
- No build step
- Extremely fast page interactions
- Progressive enhancement (works without JavaScript if needed)
- Server-rendered HTML maintained (agent browsability preserved)

**Recommendation for baseball-crawl**:
- **MVP**: No HTMX. Static page refreshes are sufficient (coaches refresh browser to see updated game scores).
- **Later** (E-004 or beyond): Add HTMX if live-game stats updates become a coaching requirement.

### Agent Browsability for Option B

✅ **Excellent**: Docker Compose serves FastAPI at `http://localhost:8000`. Jinja2 templates ensure fully-rendered HTML with data populated. Agent can fetch and evaluate real content.

✅ **Python-native**: No language context switch. Same Python language and patterns as crawlers.

### Recommendation for Option B

**Use FastAPI + Jinja2 templates + Tailwind CSS CDN + Docker Compose.**

**Why**:
- Server-rendered HTML ensures agent can review actual data presentation
- Zero build complexity (Tailwind CDN)
- Same Docker Compose pattern as production (local/prod parity)
- Python end-to-end (no TypeScript learning)
- HTMX is an optional enhancement if real-time updates later matter

**Trade-offs**:
- Requires managing one Linux server (operational overhead vs. Option A)
- FastAPI + SQLite concurrency pattern adds modest complexity (documented in E-009-R-02)

---

## Framework Complexity Assessment: Server-Rendered HTML vs. SPA

### When is Server-Rendered HTML Sufficient?

**Yes, for baseball-crawl MVP:**
- Read-only data display (coaches don't edit)
- Tables and stat cards (no complex interactions)
- Mobile-responsive layout (CSS handles this)
- Page refresh is acceptable for data updates
- No real-time WebSocket updates required for MVP

### When Would an SPA Become Necessary?

**Later, if**:
- Real-time live-game stat updates become essential
- Coaches need complex filtering/sorting on client side
- Dashboard requires offline capability
- Coaching staff demands instantaneous data refresh

### Agent Browsability Verdict

**Server-rendered HTML is essential for agent feedback loops.** An SPA would return empty divs to WebFetch, making visual design review impossible.

---

## Charting and Visualization Library Recommendations

### For Basic Stats Dashboards (MVP)

**No charting library required initially.** Tables and stat cards are sufficient:
- Batting average, OBP, strikeout rates (text numbers)
- Game logs (tables)
- Opponent tendencies (tables)

### When Charts Become Useful

**Add charts if coaches ask for:**
- Trend lines (average by game across a season)
- Spray charts (hit locations on a field diagram)
- Distribution histograms (strikeout rates across pitchers)
- Heatmaps (pitcher performance by batter handedness)

### Library Comparison

| Library | Size | Use Case | Notes |
|---------|------|----------|-------|
| **Chart.js** | ~150 KB | Line, bar, pie charts | Lightweight; ideal for simple trends |
| **Plotly.js** | ~600 KB | Complex interactive charts | Overkill for MVP; good for advanced analytics |
| **Nivo** | ~200 KB (React) | Data visualization dashboards | Requires React; powerful but adds framework overhead |
| **Apex Charts** | ~200 KB | Sports dashboards | Good interactive charts; not lightweight |
| **No library** | 0 KB | Tables and lists | Perfect for MVP; add later if needed |

### Recommendation

**MVP**: No charting library. Use semantic HTML tables.

**When to add charts**:
- Coach feedback indicates need for trend visualization
- Game-by-game performance comparisons become frequent
- **Chart.js recommendation**: Lightweight, no build step, pairs well with server-rendered HTML

**Chart.js + FastAPI Example**:
```html
<!-- In Jinja2 template -->
<canvas id="avg-trend"></canvas>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script>
    const ctx = document.getElementById('avg-trend').getContext('2d');
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: {{ game_dates|tojson }},
            datasets: [{
                label: 'Batting Average',
                data: {{ batting_avgs|tojson }},
                borderColor: '#3b82f6',
                fill: false
            }]
        }
    });
</script>
```

---

## JavaScript Complexity: Server-Rendered HTML + Alpine.js

### Do We Need Client-Side JavaScript?

**For MVP**: No.

**For interactivity**, Alpine.js (7.1 kB) is a lightweight alternative:

```html
<!-- Example: Toggle filter dropdown without page reload -->
<div x-data="{ open: false }">
    <button @click="open = !open" class="btn">Filter by Team</button>
    <div x-show="open" class="dropdown">
        <a href="?team=varsity">Varsity</a>
        <a href="?team=jv">JV</a>
    </div>
</div>
```

### Alpine.js Trade-offs

**Advantages**:
- Tiny footprint (7.1 kB gzipped)
- No build step
- Progressive enhancement (works with server-rendered HTML)

**Disadvantages**:
- Still adds JavaScript to the mix (agent browsability still requires server-rendered HTML to work)
- Limited to simple interactions (showing/hiding, basic state)

### Recommendation

**MVP**: Use pure server-rendered HTML, no JavaScript. Page navigation and browser refresh are acceptable patterns.

**If coaches want filter/sort interactivity**: Add Alpine.js later (minimal overhead). Keep server-rendered HTML as the foundation.

---

## CSS Recommendation: Tailwind CDN vs. Bootstrap CDN vs. Hand-Written

### Tailwind CSS CDN (Recommended)

```html
<script src="https://cdn.tailwindcss.com"></script>
```

**Advantages**:
- Utility-first approach; rapid iteration
- ~80 KB over the wire
- No build step required
- Pair well with Jinja2 macros

**Example utility classes for mobile-first**:
```html
<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
    <!-- Single column on mobile, 2 on tablet, 3 on desktop -->
</div>
```

### Bootstrap CDN

```html
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
```

**Advantages**:
- Well-known utility classes
- Extensive component library
- Larger ecosystem of templates

**Disadvantages**:
- Heavier (~250 KB CSS + 120 KB JS)
- Less "utility-first" mindset; more class combinations
- Older design language (less modern look without customization)

### Hand-Written Minimal CSS

```html
<style>
    body { font-family: sans-serif; margin: 0; }
    .container { max-width: 1200px; margin: 0 auto; padding: 1rem; }
    .stat-card { background: #f3f4f6; border-radius: 0.5rem; padding: 1rem; }
    @media (max-width: 768px) { .stat-card { padding: 0.5rem; } }
</style>
```

**Advantages**:
- Minimal overhead
- Full control
- Extremely fast

**Disadvantages**:
- Tedious for complex layouts
- No responsive grid system built-in
- Hard to maintain consistency across pages

### Recommendation

**Use Tailwind CSS CDN for MVP**, switch to build tooling only if production performance requires it (unlikely for a coaching dashboard).

**Why Tailwind wins**:
- Rapid iteration (add classes directly in Jinja2 templates)
- Mobile-first mindset built-in
- Beautiful default styling
- Utility-first scales better than hand-written or Bootstrap component classes

---

## Styling for Mobile-First Coaching Dashboard

### Viewport Meta Tag (Essential)

```html
<meta name="viewport" content="width=device-width, initial-scale=1.0">
```

### Mobile-First Responsive Grid

```html
<!-- Tailwind: single column on mobile, responsive above -->
<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
    {% for player in stats %}
    <div class="bg-white rounded shadow p-4">
        <!-- Player stat card -->
    </div>
    {% endfor %}
</div>
```

### Table Optimization for Mobile

```html
<!-- Tailwind: horizontal scroll on mobile, normal on desktop -->
<div class="overflow-x-auto">
    <table class="min-w-full text-sm">
        <!-- Table rows -->
    </table>
</div>
```

### Touch-Friendly Buttons and Links

```html
<!-- Minimum 44px height for touch targets (mobile accessibility) -->
<a href="/player/{{ player.id }}"
   class="inline-block px-4 py-3 bg-blue-500 text-white rounded">
    View Profile
</a>
```

---

## Open Questions: Claude Code WebFetch + Localhost

### Critical Question: Localhost URL Security Model

**Status**: Confirmed feasible with caveats.

**Verification Needed** (for E-009-06 Agent Browsability Verification):
1. Test: User explicitly provides `http://localhost:8000` in prompt → Agent successfully fetches and describes rendered HTML
2. Test: Agent cannot autonomously construct localhost URLs (security model confirmed)
3. Test: Agent can evaluate CSS classes, semantic HTML, data population in returned content
4. Test: Mobile viewport rendering is visible in returned HTML (responsive design is evaluable)

### Localhost Testing Protocol (Recommended for E-009-06)

```
1. Start FastAPI locally: docker compose up
2. Provide URL to agent: "Review the dashboard at http://localhost:8000/dashboard"
3. Agent uses WebFetch with prompt: "Does this dashboard look mobile-friendly? Are stats populated correctly?"
4. Verify: Agent's response references:
   - Actual HTML structure (table rows, stat cards)
   - Tailwind classes (responsive grid, mobile adjustments)
   - Data values (player names, averages)
   - Suggestions for layout improvements
```

If agent successfully describes rendered content, agent browsability is validated for tight development loops.

### Fallback if Localhost Fails

If WebFetch cannot reach localhost URLs (security restrictions are stricter than documented), fallback approaches:

1. **Staging deploy on Cloudflare Pages or Docker host** (temporary URL provided to agent)
2. **Agent browsability via `mcp__ide__executeCode`** (execute Python screenshot tools, but this requires Playwright/headless browser)
3. **HTML snapshots** (developer saves dashboard HTML as artifact and shares with agent)

---

## Recommendation Summary by Option

### Option A: Cloudflare Pages + Workers

**Technology Stack**:
- TypeScript Workers + Hono framework
- Eta template engine (6 KB) for server-rendered HTML
- Tailwind CSS CDN (~80 KB)
- Pages Functions for routing
- `wrangler pages dev` for local development at `http://localhost:8788`

**Strengths**:
- Zero operational overhead
- Excellent local/prod parity
- Real-time feedback loops via hot-reload
- Agent browsability: feasible via `wrangler pages dev`

**Trade-offs**:
- TypeScript learning curve (~2-4 weeks)
- Template engine adds dependency
- Serving layer code not Python

**When to choose**: If zero-ops cloud simplicity is paramount and team accepts TypeScript.

### Option B: FastAPI + Docker (Recommended)

**Technology Stack**:
- FastAPI framework
- Jinja2 templates for server-rendered HTML
- Tailwind CSS CDN (~80 KB)
- SQLite + WAL mode (from E-009-R-01)
- Docker Compose for local dev and production
- `docker compose up` for local development at `http://localhost:8000`

**Strengths**:
- Python end-to-end (no language context switch)
- Simple Docker Compose (same locally and in production)
- Excellent agent browsability (server-rendered HTML guaranteed)
- Jinja2 is native Python, zero friction for templates
- HTMX is optional enhancement for later real-time features

**Trade-offs**:
- Requires managing one Linux VPS (~$4-10/month)
- Operational overhead vs. Option A (but proven pattern via n8n-wilk-io)

**When to choose**: If developer velocity, Python homogeneity, and tight agent feedback loops matter more than zero-ops overhead.

---

## Framework and Styling Decision Matrix

| Aspect | Option A | Option B |
|--------|----------|----------|
| **HTML Rendering** | TypeScript Workers + Eta/Nunjucks | FastAPI + Jinja2 |
| **CSS Framework** | Tailwind CDN | Tailwind CDN |
| **Charting (MVP)** | None (tables only) | None (tables only) |
| **JavaScript (MVP)** | None required | None required |
| **Real-time Updates (MVP)** | Page refresh | Page refresh |
| **Optional Later: Interactivity** | Alpine.js (7 KB) | Alpine.js (7 KB) + HTMX (15 KB) |
| **Optional Later: Charts** | Chart.js (150 KB) | Chart.js (150 KB) |
| **Local Dev Server** | `wrangler pages dev` @ localhost:8788 | `docker compose up` @ localhost:8000 |
| **Agent Browsability** | ✅ Feasible (server-rendered HTML) | ✅ Excellent (server-rendered HTML native) |

---

## Testing Recommendations

### Option A Testing Checklist

- [ ] `wrangler pages dev` serves dashboard HTML with sample data at localhost:8788
- [ ] Tailwind CDN loads and styles are applied (inspect DevTools)
- [ ] Mobile viewport meta tag renders correctly on mobile browser
- [ ] Eta template rendering compiles without errors
- [ ] Agent can fetch `http://localhost:8788/dashboard` and describe rendered data (E-009-06)
- [ ] Hot-reload works: edit template, save, browser updates automatically

### Option B Testing Checklist

- [ ] `docker compose up` brings FastAPI online at localhost:8000
- [ ] Jinja2 templates render with database data populated
- [ ] Tailwind CDN loads and styles applied
- [ ] Mobile viewport renders correctly on phone browser
- [ ] Agent can fetch `http://localhost:8000/dashboard` and describe rendered data (E-009-06)
- [ ] FastAPI logs show successful template rendering
- [ ] SQLite WAL mode is enabled (`PRAGMA journal_mode=WAL`)
- [ ] Migrations apply cleanly on fresh container startup

---

## CSS and Design Patterns for Coaching Dashboard

### Essential Mobile-First Patterns

**1. Responsive Grid**:
```html
<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
    <!-- Auto-stacks on mobile, 2-col on tablet, 3-col on desktop -->
</div>
```

**2. Readable Table on Mobile**:
```html
<div class="overflow-x-auto">
    <table class="text-sm whitespace-nowrap">
        <!-- Horizontal scroll on mobile -->
    </table>
</div>
```

**3. Touch-Friendly Navigation**:
```html
<nav class="flex gap-2">
    <a href="/dashboard" class="px-4 py-3 rounded hover:bg-blue-100">Dashboard</a>
    <a href="/opponent" class="px-4 py-3 rounded hover:bg-blue-100">Opponent</a>
</nav>
```

**4. Stat Cards (Mobile Optimized)**:
```html
<div class="bg-white rounded shadow p-4 sm:p-6">
    <h3 class="text-lg sm:text-xl font-semibold">{{ player.name }}</h3>
    <dl class="mt-3 space-y-2 text-sm">
        <div class="flex justify-between">
            <dt class="text-gray-600">Average</dt>
            <dd class="font-semibold">.{{ player.avg|round(3)|string|replace('0.', '') }}</dd>
        </div>
    </dl>
</div>
```

---

## Sources and References

### Cloudflare Pages and Workers Documentation
- [Cloudflare Pages: Server-side render full stack applications with Pages Functions](https://blog.cloudflare.com/pages-full-stack-frameworks/)
- [Cloudflare Pages Functions: Local development](https://developers.cloudflare.com/pages/functions/local-development/)
- [Cloudflare Pages: Functions overview](https://developers.cloudflare.com/pages/functions/)
- [Hono: Lightweight web framework for Cloudflare Pages](https://hono.dev/docs/getting-started/cloudflare-pages)
- [Cloudflare: Your frontend, backend, and database — now in one Cloudflare Worker](https://blog.cloudflare.com/full-stack-development-on-cloudflare-workers/)

### Claude Code and WebFetch Tool
- [Claude API: Web fetch tool](https://docs.claude.com/en/docs/agents-and-tools/tool-use/web-fetch-tool)
- [Claude Platform Docs: Web fetch tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-fetch-tool)

### FastAPI and Jinja2 Templates
- [FastAPI: Advanced Templates documentation](https://fastapi.tiangolo.com/advanced/templates/)
- [Real Python: How to Serve a Website With FastAPI Using HTML and Jinja2](https://realpython.com/fastapi-jinja2-template/)
- [TestDriven.io: Tips and Tricks - FastAPI - Templates with Jinja2](https://testdriven.io/tips/235fc106-8ad2-4d64-a7ae-8610a1b2d221/)
- [Medium: FastAPI as a Hypermedia Driven Application w/ HTMX & Jinja2Templates](https://medium.com/@strasbourgwebsolutions/fastapi-as-a-hypermedia-driven-application-w-htmx-jinja2templates-644c3bfa51d1)

### HTMX and Real-Time Dashboards
- [Medium: Building Real-Time Dashboards with FastAPI and HTMX](https://medium.com/codex/building-real-time-dashboards-with-fastapi-and-htmx-01ea458673cb)
- [GitHub: fastapi-htmx-tailwind-example](https://github.com/volfpeter/fastapi-htmx-tailwind-example)
- [Johal.in: HTMX FastAPI Patterns: Hypermedia-Driven Single Page Applications 2025](https://johal.in/htmx-fastapi-patterns-hypermedia-driven-single-page-applications-2025/)
- [Medium: Building Real-Time Dashboards with FastAPI, HTMX & Plotly Python](https://medium.com/codex/building-real-time-dashboards-with-fastapi-htmx-plotly-python-the-pure-python-charts-edition-2c29e77da953)

### CSS and Styling
- [Tailwind CSS: Play CDN](https://tailwindcss.com/docs/installation/play-cdn)
- [Tailwind CSS: Optimizing for Production](https://v3.tailwindcss.com/docs/optimizing-for-production/)
- [Tailkits: Tailwind CSS v4 CDN: The Fastest Setup Guide](https://tailkits.com/blog/tailwind-css-v4-cdn-setup/)
- [Bootstrap: The world's most popular mobile-first framework](https://getbootstrap.com/docs/5.3/getting-started/introduction/)
- [Medium: Utilizing Bootstrap for "Mobile First" Development](https://medium.com/swlh/utilizing-bootstrap-for-mobile-first-development-f85c8b65118a)

### JavaScript Charting Libraries
- [StackShare: Plotly.js vs Chart.js comparison](https://stackshare.io/stackups/js-chart-vs-plotly-js)
- [Luzmo: JavaScript Chart Libraries In 2026: Best Picks + Alternatives](https://www.luzmo.com/blog/javascript-chart-libraries)
- [Metabase: Comparing the most popular open-source charting libraries](https://www.metabase.com/blog/best-open-source-chart-library)
- [GitHub: Plotly.js repository](https://github.com/plotly/plotly.js)

### Lightweight JavaScript Framework
- [Alpine.js: Official site](https://alpinejs.dev/)
- [GitHub: TailwindCSS-Alpine.js-Template](https://github.com/VojislavD/TailwindCSS-Alpine.js-Template)
- [Medium: Alpine.js: The Minimalist JavaScript Framework for Modern Web Development](https://medium.com/@zulfikarditya/alpine-js-the-minimalist-javascript-framework-for-modern-web-development-839382997988)
- [Medium: How to Build Interactive Python Dashboards with Tailwind, FastAPI, and Alpine.js](https://medium.com/@hexshift/how-to-build-interactive-python-dashboards-with-tailwind-fastapi-and-alpine-js-2fce46918323)

### Server-Rendered HTML vs. SPA
- [dotCMS: SPAs and Server Side Rendering: A Must, or a Maybe?](https://www.dotcms.com/blog/spas-and-server-side-rendering-a-must-or-a-maybe)
- [Hygraph: What is the difference between SPAs, SSR, and SSGs?](https://hygraph.com/blog/difference-spa-ssg-ssr)
- [DEV Community: SSR vs SPA Showdown: Choosing the Right Rendering Approach](https://dev.to/santhanam87/ssr-vs-spa-showdown-choosing-the-right-rendering-approach-for-your-web-app-4439)
- [DebugBear: The Ultimate Guide To Server-Side Rendering (SSR)](https://www.debugbear.com/blog/server-side-rendering)

### HTML Semantics
- [W3Schools: HTML Semantic Elements](https://www.w3schools.com/html/html5_semantic_elements.asp)
- [web.dev: Semantic HTML](https://web.dev/learn/html/semantic-html)
- [Austin Gil: How to Build HTML Forms Right: Semantics](https://austingil.com/how-to-build-html-forms-right-semantics/)

---

## Author Notes

This research confirms that **server-rendered HTML is the right choice for agent-browsable coaching dashboards**. Both Option A (Cloudflare Pages + Workers) and Option B (FastAPI + Docker) can deliver this, but Option B is the stronger recommendation for baseball-crawl because:

1. **Agent browsability** is native to server-rendered HTML (no SPA, no client-side rendering complications)
2. **Python homogeneity** eliminates language context switching
3. **Tight feedback loops** via `docker compose up` match the fast iteration needed for dashboard development
4. **Proven pattern** (n8n-wilk-io reference) reduces execution risk

Option A remains viable if zero operational overhead is the decisive factor. The TypeScript learning curve is real but not a blocker for a small serving layer.

The key insight for agent browsability: **explicitly provide the localhost URL to the agent**, and WebFetch can then evaluate rendered HTML. This enables tight feedback loops for coaching dashboard iteration.

For E-009-01 (Technology Decision Record), this research should inform the final choice. The decision is driven by team preference (operations vs. developer experience) rather than technical capability constraints—both options are production-ready and support agent browsability.
