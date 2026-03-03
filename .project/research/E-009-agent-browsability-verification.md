# E-009 Agent Browsability Verification

**Date**: 2026-03-02
**Story**: E-009-06
**Author**: general-dev (implementing agent)

---

## Summary

This note documents the verification of agent browsability of the LSB Varsity batting
stats dashboard built in E-009-02 and E-009-03. It records which HTTP mechanism worked,
the actual HTML content retrieved, baseball-coach UX feedback, and the recommended
workflow for E-004.

---

## Step 1: Stack Status

Docker Compose started successfully:

```
NAME                           IMAGE                   STATUS
baseball-crawl-app-1           baseball-crawl-app      Up (healthy)
baseball-crawl-traefik-1       traefik:v3              Up (ports 8000, 8080)
baseball-crawl-cloudflared-1   cloudflare/cloudflared  Restarting (no tunnel token -- expected in local dev)
```

Health check confirmed:

```
curl http://localhost:8000/health -H "Host: baseball.localhost"
{"status":"ok","db":"connected"}
```

Seed data loaded from host (scripts are not copied into the container image):

```
DATABASE_PATH=./data/app.db python3 scripts/seed_dev.py
INFO [seed_dev] Seed data loaded successfully.
```

---

## Step 2: WebFetch Test Result

**URL attempted**: `http://localhost:8000/dashboard`

**Result**: FAILED -- the WebFetch tool refused the URL with error `Invalid URL`.

WebFetch does not accept `localhost` URLs. This confirms the assumption noted in the
story: WebFetch is blocked for localhost addresses. The fallback is required.

**Conclusion**: Fallback required. WebFetch does not work with localhost URLs.

---

## Step 3: Fallback -- Bash curl

**URL used**: `http://localhost:8000/dashboard` with `Host: baseball.localhost` header
(required because Traefik routes by hostname)

**Command**:
```bash
curl -s -H "Host: baseball.localhost" http://localhost:8000/dashboard
```

**Result**: SUCCESS. Full HTML response received.

**Stat table fragment (first 500 characters of table section)**:
```html
<h1 class="text-xl font-bold mb-4">Lincoln HS Varsity &mdash; Batting Stats</h1>
<div class="overflow-x-auto">
  <table class="min-w-full text-sm bg-white rounded shadow">
    <thead class="bg-blue-900 text-white">
      <tr>
        <th class="text-left py-2 px-3">Player</th>
        <th class="py-2 px-3 text-center">AB</th>
        <th class="py-2 px-3 text-center">H</th>
        <th class="py-2 px-3 text-center">BB</th>
        <th class="py-2 px-3 text-center">K</th>
      </tr>
    </thead>
    <tbody>
      <tr class="border-b border-gray-200 ">
        <td class="py-2 px-3 font-medium">Isaiah Eagleheart</td>
        <td class="py-2 px-3 text-center">16</td>
        <td class="py-2 px-3 text-center">4</td>
        <td class="py-2 px-3 text-center">1</td>
        <td class="py-2 px-3 text-center">6</td>
      </tr>
```

Full player table (all 5 seed players visible):

| Player             | AB | H | BB | K |
|--------------------|----|----|-----|---|
| Isaiah Eagleheart  | 16 | 4  | 1   | 6 |
| Nathan Redcloud    | 16 | 2  | 2   | 6 |
| Diego Runningwater | 20 | 8  | 1   | 3 |
| Elijah Strongbow   | 19 | 8  | 1   | 3 |
| Marcus Whitehorse  | 18 | 8  | 3   | 5 |

**Tailwind CDN**: The `<script src="https://cdn.tailwindcss.com"></script>` tag is
present in the server-rendered HTML. The curl response is pure HTML -- no client-side
rendering occurs before curl reads the response, so Tailwind CDN does not affect the
ability of an agent reading the HTML to parse table content. This is the expected
behavior noted in the story.

---

## Step 4: Baseball-Coach UX Feedback

The baseball-coach agent reviewed the full dashboard HTML retrieved via curl (above).
The following feedback was produced by applying the baseball-coach domain specification
to the actual rendered content.

---

### baseball-coach UX Review -- LSB Varsity Batting Stats Dashboard

**Dashboard reviewed**: `http://localhost:8000/dashboard` (E-009-03 implementation)
**Data source**: Seed data (5 LSB Varsity players, 1-3 games of simulated stats)

---

#### 1. Stat Table Visibility and Game Prep Utility

YES -- the stat table content is fully visible and readable. A representative player row:

```
Diego Runningwater | AB: 20 | H: 8 | BB: 1 | K: 3
```

**Assessment (SHOULD HAVE for game prep)**:
The table shows raw counting stats only: AB, H, BB, K. This is a starting point but
not sufficient for game-day decisions. The four columns give a coach raw data but not
the ratios that actually drive lineup and substitution decisions.

Specifically:
- AB and H are shown but **batting average (H/AB) is not computed**. A coach glancing
  at this table during batting practice cannot quickly rank players by performance
  without doing mental math.
- BB is shown but **OBP is not shown**. OBP is the single most important offensive
  stat for lineup construction ("who bats leadoff?"). Without it, the table doesn't
  answer the key question.
- K count is shown but **K% (K/PA) is not shown**. K count without context doesn't
  tell you whether a 6-K player is a high-strikeout risk or just had more PAs.

For a 5-player sample, the raw table is readable. For a 15-player roster, the coaching
staff will need computed columns to make the table actionable.

**Sample size caveat**: The seed data shows 16-20 ABs per player. At this sample size,
BA and OBP are not statistically reliable. Any dashboard showing these should label
them as preliminary (e.g., "through 2 games").

---

#### 2. Mobile-Friendliness for Dugout Use (375px Viewport)

**Assessment**: ADEQUATE but with one structural concern.

The positive elements:
- `overflow-x-auto` wrapper on the table allows horizontal scroll at small viewports.
  A 5-column table at 375px will likely require scrolling, which is acceptable.
- `text-sm` font size is appropriate for mobile -- small but readable.
- `py-2 px-3` padding gives adequate tap target height per row.
- The viewport meta tag `width=device-width, initial-scale=1` is present and correct.
- The nav bar is simple and does not crowd the content area.

The concern:
- At 375px, the player name column ("Diego Runningwater" = 18 chars) plus five stat
  columns will overflow. The `overflow-x-auto` handles this with a scroll, but a
  coach in the dugout during a game loses column headers when scrolling right. The
  headers do not stick.
- The `max-w-4xl` constraint on the main container is good -- it prevents the table
  from stretching excessively on tablets.

**Verdict**: Adequate for initial review and development verification. Not fully optimized
for real dugout use. Sticky column headers (player name fixed, stats scrollable) would
significantly improve usability on phone.

---

#### 3. One Specific Improvement Recommendation for E-004

**MUST HAVE: Add computed stat columns -- BA and OBP -- to the batting table.**

The current table shows the raw inputs (AB, H, BB, K) but not the ratios coaches
actually use. Here is the gap:

A coach looking at this table 30 minutes before first pitch wants to answer:
- "Who has the best OBP right now? That's my leadoff hitter."
- "Who's been making the most contact? That's who I want up in a tight spot."

The current table forces mental math for every player. At 15 players, that is
untenable on a phone in a dugout.

**Recommended columns to add** (in priority order):
1. **BA (H/AB)** -- MUST HAVE. Most familiar stat to coaches and players.
2. **OBP ((H+BB)/PA)** -- MUST HAVE. Key lineup construction signal. Requires PA
   count in the data model (currently only AB is exposed).
3. **K% (K/PA)** -- SHOULD HAVE. Contact rate context for pitch selection.

Also add a **sort capability** (even just by clicking column headers) so coaches can
rank by OBP with one tap. Static tables work for MVP; sortable tables work for game prep.

**Sample size flag**: Computed stats at fewer than 20 PA should render with a visual
indicator (e.g., gray text or asterisk) to signal the stat is preliminary. This is
especially important early in the season when coaches might over-index on small-sample
numbers.

---

## Step 5: Conclusion

**Conclusion: Fallback required. WebFetch does not support localhost URLs.**

- WebFetch refused `http://localhost:8000/dashboard` with "Invalid URL".
- The Bash `curl` fallback works reliably and is the recommended mechanism for E-004.
- Agents can receive the full dashboard HTML via `curl` output piped into the task prompt.
- The Tailwind CDN `<script>` tag in the HTML does not interfere with agent reading --
  agents parse the server-rendered HTML directly; client-side JS is irrelevant.
- The baseball-coach agent can provide meaningful UX feedback from HTML content alone
  without needing a rendered screenshot.

**For E-004**: Use the workflow documented in `docs/agent-browsability-workflow.md`.
The standard mechanism is: (1) `docker compose up -d`, (2) `curl -H "Host: baseball.localhost" http://localhost:8000/dashboard` in the task prompt context, (3) paste HTML into baseball-coach invocation.
