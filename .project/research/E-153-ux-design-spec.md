# E-153 UX Design Spec: Team-Centric Coaching Dashboard

**Epic**: E-153
**Story**: E-153-01
**Author**: ux-designer
**Format**: Layout specification + ASCII wireframes + component inventory

---

## 1. Design System Reference (Current State)

All new designs build on the established visual language. These patterns are extracted from `base.html` and existing dashboard templates.

### Colors
- **Nav bar**: `bg-blue-900 text-white`
- **Body background**: `bg-gray-50`
- **Table header**: `bg-blue-900 text-white`
- **Alternating rows**: even rows `bg-gray-50`, odd rows `bg-white`
- **Row border**: `border-b border-gray-200`
- **Card**: `bg-white rounded shadow border border-gray-200 p-4`
- **Card heading**: `text-base font-bold text-blue-900 mb-3`
- **Links**: `text-blue-900 hover:underline` (primary), `text-blue-700 hover:underline` (secondary)
- **Positive indicator**: `text-green-700 font-bold` (W)
- **Negative indicator**: `text-red-700 font-bold` (L)
- **Warning/empty state**: `bg-yellow-50 border border-yellow-200 rounded p-4 text-sm text-yellow-900`
- **Back link**: `text-blue-900 hover:underline text-sm` with `&larr;` prefix

### Typography
- **Page heading**: `text-xl font-bold`
- **Section heading**: `text-base font-bold` (inside cards: `text-blue-900`)
- **Body text**: `text-sm` (default)
- **Small/meta text**: `text-xs text-gray-600`
- **Table cells**: `py-2 px-3 text-sm`

### Layout
- **Container**: `max-w-4xl mx-auto`
- **Main padding**: `p-4 ... pb-16` (bottom padding clears fixed nav)
- **Table wrapper**: `overflow-x-auto` div around every table

### Interactive Elements
- **Team selector pills**: `px-3 py-2 rounded text-sm font-medium` with active/inactive/no-data states
- **Bottom nav tab**: `flex-1 flex flex-col items-center justify-center py-3 text-xs font-medium`
- **Active nav tab**: `text-blue-900 font-bold`
- **Inactive nav tab**: `text-gray-600 hover:text-blue-900`

---

## 2. Bottom Navigation (3-Tab)

### Current State
4 tabs: `Batting | Pitching | Games | Opponents`

### New State
3 tabs: `Schedule | Batting | Pitching`

### Wireframe

```
┌─────────────────────────────────────────┐
│  Schedule     │   Batting    │  Pitching │
│  (active)     │              │           │
└─────────────────────────────────────────┘
```

### Specification

- **Location**: Fixed bottom bar, identical position to current nav (`fixed bottom-0 w-full bg-white border-t border-gray-200 z-10`)
- **Tab count**: 3 (down from 4)
- **Tab labels**: "Schedule", "Batting", "Pitching"
- **URLs**:
  - Schedule: `/dashboard/schedule` (new landing page)
  - Batting: `/dashboard/batting` (current `/dashboard/` content moves here)
  - Pitching: `/dashboard/pitching` (unchanged)
- **`active_nav` values**: `'schedule'`, `'batting'`, `'pitching'`
- **Active state**: `text-blue-900 font-bold` (unchanged pattern)
- **Inactive state**: `text-gray-600 hover:text-blue-900` (unchanged pattern)
- **Query string preservation**: Each tab link carries `team_id`, `year`, `season_id` params (same pattern as current nav, via `_qs` variable in `base.html`)
- **Touch target**: Each tab is `flex-1` (equal width, ~125px on 375px screen) with `py-3` padding = ~48px tap height. Meets 44px minimum.
- **Old routes**: `/dashboard/games` and `/dashboard/opponents` remain functional (direct URL access, internal links) but are removed from the bottom nav.

### Behavioral Notes
- The root `/dashboard/` URL should redirect to `/dashboard/schedule` (or serve the schedule template directly -- SE decides implementation)
- The team selector component (`_team_selector.html`) is reused on the schedule page with `base_url="/dashboard/schedule"`

---

## 3. Schedule Landing Page

### Layout Specification

The schedule page is divided into two sections: **Upcoming Games** (top) and **Completed Games** (bottom). Upcoming games are ordered by date ascending (nearest first). Completed games are ordered by date descending (most recent first).

### Wireframe (375px mobile)

```
┌─────────────────────────────────────┐
│ [Team Selector Pills]   [Year: ▼]  │
├─────────────────────────────────────┤
│                                     │
│ Varsity — Schedule                  │
│                                     │
│ ─── Upcoming ───────────────────    │
│                                     │
│ ┌─────────────────────────────────┐ │
│ │ NEXT   Mar 28 (4 days)         │ │
│ │ vs Central Lions        H      │ │
│ │ ● Scouted                      │ │
│ └─────────────────────────────────┘ │
│                                     │
│ ┌─────────────────────────────────┐ │
│ │ Apr 2 (9 days)                 │ │
│ │ @ West Eagles           A      │ │
│ │ ○ Not scouted                  │ │
│ └─────────────────────────────────┘ │
│                                     │
│ ┌─────────────────────────────────┐ │
│ │ Apr 5 (12 days)                │ │
│ │ vs North Bears   (8-2)  H      │ │
│ │ ● Scouted                      │ │
│ └─────────────────────────────────┘ │
│                                     │
│ ─── Completed ──────────────────    │
│                                     │
│  Mar 22  Central Lions  7-3  W  H  │
│  Mar 18  East Hawks     2-5  L  A  │
│  Mar 15  South Tigers   4-1  W  H  │
│  Mar 11  West Eagles    3-3  T  A  │
│                                     │
│                                     │
│ ┌───────────┬───────────┬─────────┐ │
│ │ Schedule  │  Batting  │Pitching │ │
│ └───────────┴───────────┴─────────┘ │
└─────────────────────────────────────┘
```

### Upcoming Games Section

#### Section Header
- `text-sm font-bold text-gray-500 uppercase tracking-wide border-b border-gray-300 pb-1 mb-3`
- Text: "Upcoming"

#### Game Cards (Upcoming)
Each upcoming game renders as a card, not a table row. Cards are tappable -- the entire card links to the opponent scouting page.

**Card styling**:
- Wrapper: `block` anchor tag wrapping the card (entire card is tappable)
- Default card: `bg-white rounded shadow-sm border border-gray-200 p-3 mb-2`
- "NEXT" card (nearest upcoming game): `bg-blue-50 rounded shadow-sm border-2 border-blue-900 p-3 mb-2`

**Card content layout** (3 rows within each card):

Row 1 (date + countdown):
```
[NEXT badge]  Mar 28  (4 days)
```
- NEXT badge (first card only): `inline-block bg-blue-900 text-white text-xs font-bold px-2 py-0.5 rounded mr-2`
- Date: `text-sm font-medium text-gray-900`
- Days-until: `text-sm text-gray-500 ml-1` — format: `(N days)` or `(Tomorrow)` or `(Today)`

Row 2 (opponent + home/away):
```
vs Central Lions                    H
```
- Prefix: `vs` (home) or `@` (away) or blank (TBD) — `text-sm text-gray-500 mr-1`
- Opponent name: `text-sm font-bold text-blue-900`
- Opponent record (if available): `text-sm text-gray-500 ml-1` — format: `(8-2)`
- Home/away badge: `text-xs font-medium text-gray-500` floated right — `H` / `A` / blank

Row 3 (scouted indicator):
```
● Scouted
```
- Scouted: `text-xs text-green-700` with filled dot `●`
- Not scouted: `text-xs text-gray-400` with open dot `○`

**Link target**: `/dashboard/opponents/{opponent_team_id}?team_id=...&year=...&season_id=...`

**Touch target**: Full card is a link. Minimum card height with 3 rows + `p-3` padding ≈ 72px. Well above 44px minimum.

#### Empty State (No Upcoming Games)
When there are no upcoming games (all games completed or season not started):
```
┌─────────────────────────────────────┐
│  No upcoming games on the schedule. │
└─────────────────────────────────────┘
```
- Styling: `text-sm text-gray-500 py-4`

### Completed Games Section

#### Section Header
- Same pattern as Upcoming: `text-sm font-bold text-gray-500 uppercase tracking-wide border-b border-gray-300 pb-1 mb-3 mt-6`
- Text: "Completed"

#### Game Rows (Completed)
Completed games use a compact table layout (not cards) because there are more of them and they are reference data, not primary action items.

**Table styling**: Standard project table pattern (`min-w-full text-sm bg-white rounded shadow`, `bg-blue-900 text-white` thead).

**Columns** (ordered by importance for 375px):

| Column | Width | Content | Responsive |
|--------|-------|---------|------------|
| Date | auto | `Mar 22` (short date format) | Always visible |
| Opponent | auto | Opponent name, linked to scouting page | Always visible |
| Score | ~60px | `7-3` (our score first) | Always visible |
| W/L | ~30px | W (green) / L (red) / T (gray) | Always visible |
| H/A | ~30px | H / A | `hidden sm:table-cell` (hidden on smallest screens) |

**Row links**:
- Opponent name: links to `/dashboard/opponents/{opponent_team_id}?...` (scouting report)
- Score: links to `/dashboard/games/{game_id}?...` (box score)
- Date and W/L are plain text (not linked)

**Row styling**: Standard alternating rows (`border-b border-gray-200`, even rows `bg-gray-50`).

#### Empty State (No Completed Games)
When no games have been played yet:
```
No completed games yet this season.
```
- Styling: `text-sm text-gray-500 py-4`

#### Empty State (No Games At All)
When the team has no schedule data loaded:
```
┌──────────────────────────────────────────────────────┐
│  No schedule data yet. Run a data sync to populate   │
│  your team's schedule.                               │
└──────────────────────────────────────────────────────┘
```
- Styling: warning card pattern (`bg-yellow-50 border border-yellow-200 rounded p-4 text-sm text-yellow-900`)

### Mobile Layout Notes (375px)

- **No horizontal scroll** on upcoming game cards (card content wraps naturally within `max-w-4xl`)
- **Completed games table**: 5 columns fit comfortably at 375px. The H/A column uses `hidden sm:table-cell` as a safety valve -- it hides below 640px if needed, but at 375px with short column content, all 5 columns should fit without scroll.
- **Team selector**: Same responsive flex-wrap behavior as current implementation
- **Cards vs. table**: Upcoming games use cards (higher visual weight, larger touch targets for the primary action area). Completed games use a table (compact, scannable reference data).

---

## 4. Opponent Detail Page (Redesigned)

### Section Order (Pitching-First)

The current page order is: Header → Key Players → Last Meeting → Batting Leaders → Pitching Leaders.

The new order per coaching consultation (TN-6): Header → **Pitching Card** → **Team Batting Summary** → Last Meeting → Full Pitching Table → Full Batting Table.

The "Key Players" card is removed. Its content is superseded by the new Pitching Card (which shows top pitchers by innings) and the Team Batting Summary (which shows aggregate tendencies).

### Wireframe — Full Stats State

```
┌─────────────────────────────────────┐
│ ← Back to Schedule                  │
│                                     │
│ Central Lions                       │
│ 8-2 · 12 games                     │
│                                     │
│ ┌─────────────────────────────────┐ │
│ │ Their Pitchers                  │ │
│ │                                 │ │
│ │ #12 J. Smith (R)        5 GP   │ │
│ │ 2.10 ERA · 8.4 K/9 · 1.05 WHIP│ │
│ │ 2.8 BB/9 · 3.0 K/BB            │ │
│ │                                 │ │
│ │ #8  M. Jones            3 GP   │ │
│ │ 3.50 ERA · 6.1 K/9 · 1.22 WHIP│ │
│ │ 3.5 BB/9 · 1.7 K/BB            │ │
│ │                                 │ │
│ │ #21 T. Brown (L)        2 GP   │ │
│ │ 4.00 ERA · 5.0 K/9 · 1.50 WHIP│ │
│ │ 4.5 BB/9 · 1.1 K/BB            │ │
│ └─────────────────────────────────┘ │
│                                     │
│ ┌─────────────────────────────────┐ │
│ │ Team Batting (12 games)         │ │
│ │                                 │ │
│ │ OBP    K%     BB%    SLG       │ │
│ │ .345   18.2%  9.1%   .410      │ │
│ └─────────────────────────────────┘ │
│                                     │
│ ┌─────────────────────────────────┐ │
│ │ Last Meeting                    │ │
│ │ Mar 22  7-3  W   Box Score →   │ │
│ └─────────────────────────────────┘ │
│                                     │
│ Pitching Leaders                    │
│ ┌─────────────────────────────────┐ │
│ │ # Player  ERA K/9 GP IP ...    │ │
│ │ (full sortable pitching table)  │ │
│ └─────────────────────────────────┘ │
│                                     │
│ Batting Leaders                     │
│ ┌─────────────────────────────────┐ │
│ │ # Player  AVG OBP GP AB ...    │ │
│ │ (full sortable batting table)   │ │
│ └─────────────────────────────────┘ │
│                                     │
│ ┌───────────┬───────────┬─────────┐ │
│ │ Schedule  │  Batting  │Pitching │ │
│ └───────────┴───────────┴─────────┘ │
└─────────────────────────────────────┘
```

### 4.1 Header

```html
<div class="mb-4">
  <h1 class="text-xl font-bold">{{ opponent_name }}</h1>
  <p class="text-gray-600 text-sm mt-1">{{ wins }}-{{ losses }} · {{ game_count }} games</p>
</div>
```

- Opponent name: `text-xl font-bold` (unchanged pattern)
- Record + game count: `text-gray-600 text-sm mt-1`
- Format: `W-L · N games` — the game count is per TN-7 (sample size transparency)

### 4.2 Pitching Card ("Their Pitchers")

**Purpose**: The #1 question a coach asks before a game: "Who's on the mound?" This card shows the top 3 pitchers by innings pitched (most usage = most likely to face).

**Card styling**: Standard card pattern (`bg-white rounded shadow border border-gray-200 p-4 mb-4`)

**Card heading**: `text-base font-bold text-blue-900 mb-3` — Text: "Their Pitchers"

**Each pitcher entry** (up to 3):

```
┌─────────────────────────────────────┐
│ #12 J. Smith (R)              5 GP  │
│ 2.10 ERA · 8.4 K/9 · 1.05 WHIP    │
│ 2.8 BB/9 · 3.0 K/BB                │
├─────────────────────────────────────┤
│ (next pitcher...)                   │
```

**Layout per pitcher**:

Row 1: Identity + games
- Jersey number: `text-sm text-gray-500` — `#12`
- Name: `text-sm font-bold text-gray-900` — `J. Smith`
- Handedness (if available): `text-sm text-gray-500` — `(R)` or `(L)` — only shown when `players.throws` is populated
- Games pitched: `text-sm text-gray-500 float-right` — `5 GP` (per TN-7)

Row 2: Primary stats
- `text-sm text-gray-700`
- Format: `ERA · K/9 · WHIP` separated by middots

Row 3: Secondary stats
- `text-sm text-gray-500`
- Format: `BB/9 · K/BB ratio`
- K/BB ratio: computed as `SO / BB` (or `∞` if BB = 0). This is the single most predictive pitching quality metric at the HS level.

**Separator between pitchers**: `border-t border-gray-100 pt-2 mt-2` (light divider within the card)

**If fewer than 3 pitchers**: Show however many exist. If zero pitchers, this card is not rendered (the empty state cards from section 4.6 take over).

### 4.3 Team Batting Summary

**Purpose**: Quick snapshot of the opponent's offensive tendencies, not individual player stats. Helps the coach understand what kind of lineup they're facing.

**Card styling**: Standard card pattern.

**Card heading**: `text-base font-bold text-blue-900 mb-3` — Text: "Team Batting (N games)" where N is the game count per TN-7.

**Stat grid** (2x2 on mobile, 4-across on wider screens):

```html
<div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
  <!-- each stat block -->
  <div>
    <p class="text-xs text-gray-500 uppercase tracking-wide">OBP</p>
    <p class="text-lg font-bold text-gray-900">.345</p>
  </div>
  ...
</div>
```

**Stats shown** (4 aggregate values):
- **OBP**: Team on-base percentage — `(H + BB + HBP) / (AB + BB + HBP + SHF)` aggregated across all batters
- **K%**: Team strikeout rate — `SO / PA` as percentage
- **BB%**: Team walk rate — `BB / PA` as percentage
- **SLG**: Team slugging — `TB / AB` aggregated across all batters

**Stat label**: `text-xs text-gray-500 uppercase tracking-wide`
**Stat value**: `text-lg font-bold text-gray-900`

### 4.4 Last Meeting Card

**Unchanged** from current implementation. Same card styling, same content (date, score, W/L, box score link).

**One change**: The "Back to Opponents" link in the current template header becomes **"Back to Schedule"** linking to `/dashboard/schedule?team_id=...&year=...&season_id=...` since the schedule page is now the primary entry point.

### 4.5 Full Stat Tables (Pitching + Batting)

**Pitching Leaders table**: Unchanged content and columns. **Repositioned** above Batting Leaders (was below in current layout). Section heading: `text-base font-bold mb-2` — "Pitching Leaders". Same sortable columns, same sort macros.

**Batting Leaders table**: Unchanged content, columns, and sort behavior. Positioned after Pitching Leaders. Section heading: `text-base font-bold mb-2` — "Batting Leaders".

Both tables retain: jersey number, sortable column headers, alternating row stripes, `overflow-x-auto` wrapper, `sticky top-0` thead. GP column is present in both tables and renders the `games` value (per TN-7).

### 4.6 Opponent Empty States

Three mutually exclusive states based on the opponent's link and data status.

#### State A: Unlinked Opponent

**Detection**: The opponent has no `opponent_links` row with `resolved_team_id IS NOT NULL` for the current team context, AND `public_id IS NULL` on the `teams` row, AND no rows in `player_season_batting`/`player_season_pitching` for this team_id + season_id.

**What renders**: Header only (name + record if available) + yellow info card. No pitching card, no batting summary, no stat tables.

```
┌─────────────────────────────────────┐
│ ← Back to Schedule                  │
│                                     │
│ Central Lions                       │
│                                     │
│ ┌─────────────────────────────────┐ │
│ │ ⚠ Stats not available.         │ │
│ │                                 │ │
│ │ This opponent hasn't been       │ │
│ │ linked to a GameChanger team    │ │
│ │ yet.                            │ │
│ │                                 │ │
│ │ [Link in Admin →]              │ │
│ └─────────────────────────────────┘ │
│                                     │
│ ┌───────────┬───────────┬─────────┐ │
│ │ Schedule  │  Batting  │Pitching │ │
│ └───────────┴───────────┴─────────┘ │
└─────────────────────────────────────┘
```

**Card styling**: Warning card (`bg-yellow-50 border border-yellow-200 rounded p-4 text-sm text-yellow-900`)

**Card content**:
- Heading: `font-bold mb-1` — "Stats not available."
- Body: "This opponent hasn't been linked to a GameChanger team yet."
- Admin shortcut (conditional): Only shown when user is admin (per TN-6 admin detection pattern). Link text: "Link in Admin →". Link target: `/admin/opponents/{link_id}/connect` if an `opponent_links` row exists, or `/admin/opponents` if none exists. Styling: `inline-block mt-2 text-sm font-medium text-blue-900 hover:underline`

#### State B: Linked but Unscouted

**Detection**: The opponent has `resolved_team_id IS NOT NULL` in `opponent_links` for the active team's `our_team_id`, OR `public_id IS NOT NULL` on the `teams` row, BUT no rows in `player_season_batting`/`player_season_pitching` for this team_id + season_id.

**What renders**: Header (name + record if available from public endpoint) + yellow info card. No pitching card, no batting summary, no stat tables.

```
┌─────────────────────────────────────┐
│ ← Back to Schedule                  │
│                                     │
│ Central Lions                       │
│                                     │
│ ┌─────────────────────────────────┐ │
│ │ ⚠ Stats not loaded yet.        │ │
│ │                                 │ │
│ │ This team is linked but stats   │ │
│ │ haven't been loaded yet. They   │ │
│ │ will appear after the next      │ │
│ │ scouting sync.                  │ │
│ └─────────────────────────────────┘ │
│                                     │
│ ┌───────────┬───────────┬─────────┐ │
│ │ Schedule  │  Batting  │Pitching │ │
│ └───────────┴───────────┴─────────┘ │
└─────────────────────────────────────┘
```

**Card styling**: Same warning card pattern.

**Card content**:
- Heading: `font-bold mb-1` — "Stats not loaded yet."
- Body: "This team is linked but stats haven't been loaded yet. They will appear after the next scouting sync."

#### State C: Full Stats

**Detection**: `player_season_batting` or `player_season_pitching` has at least one row for this team_id + season_id.

**What renders**: All sections (Header → Pitching Card → Team Batting Summary → Last Meeting → Full Pitching Table → Full Batting Table). No yellow info cards.

This is the wireframe shown in section 4 above.

---

## 5. Component Inventory

### New Templates

| File | Type | Purpose |
|------|------|---------|
| `dashboard/schedule.html` | Page template | Schedule landing page with upcoming cards + completed table. Extends `base.html`. Sets `active_nav = 'schedule'`. |
| `dashboard/_upcoming_game_card.html` | Jinja2 partial (macro) | Renders a single upcoming game card. Accepts: game date, days until, opponent name, opponent team id, home/away, is_scouted, is_next, opponent_record. |
| `dashboard/_completed_game_row.html` | Jinja2 partial (macro) | Renders a single completed game table row. Accepts: game date, opponent name, opponent team id, game id, our score, their score, wl, is_home. Included as a macro or inline in schedule.html. |

### Modified Templates

| File | Change | Purpose |
|------|--------|---------|
| `base.html` | Replace 4-tab nav with 3-tab nav | Schedule replaces Batting as first tab; Games and Opponents tabs removed. `active_nav` values updated: `'schedule'`, `'batting'`, `'pitching'`. |
| `dashboard/team_stats.html` | Change `active_nav` to `'batting'`, update URL in sort links | Batting page moves to `/dashboard/batting`. The `active_nav` value stays `'batting'` (no change needed since current is already `'batting'`). Sort header links change from `/dashboard?...` to `/dashboard/batting?...`. |
| `dashboard/opponent_detail.html` | Restructure sections, add pitching card + batting summary + empty states | Reorder from Key Players → Last Meeting → Batting → Pitching to Pitching Card → Batting Summary → Last Meeting → Pitching Table → Batting Table. Add three empty state branches. Remove Key Players card. Change back link to "Back to Schedule". |
| `dashboard/opponent_list.html` | Update `active_nav` | Change from `'opponents'` to `'schedule'` (opponents are accessed through schedule, not a dedicated tab). This page remains accessible via direct URL. |
| `dashboard/game_list.html` | Update `active_nav` | Change from `'games'` to `'schedule'` (same rationale). This page remains accessible via direct URL. |
| `dashboard/_team_selector.html` | No changes | Reused as-is on the schedule page. |

### Route Changes (for SE reference)

| Route | Change |
|-------|--------|
| `GET /dashboard/schedule` | **New route**. Serves `schedule.html`. Query params: `team_id`, `year`, `season_id`. |
| `GET /dashboard/` | Redirect to `/dashboard/schedule` (or serve schedule directly -- SE decides) |
| `GET /dashboard/batting` | **New route** (or alias). Serves current `team_stats.html` at new URL. |
| `GET /dashboard/pitching` | Unchanged. |
| `GET /dashboard/games` | Unchanged (still accessible, removed from nav). |
| `GET /dashboard/games/{game_id}` | Unchanged. |
| `GET /dashboard/opponents` | Unchanged (still accessible, removed from nav). |
| `GET /dashboard/opponents/{opponent_team_id}` | Modified handler: adds empty state detection logic, pitching card data (top 3 by IP), team batting aggregates. |

---

## 6. Mobile Layout Specification (375px)

### Schedule Page

- **Upcoming game cards**: Full width (`w-full`). No horizontal scroll. Content wraps within `p-3` padding. The opponent name + record line wraps naturally if the name is long. Home/away badge floats right on the same line.
- **Completed games table**: 5 columns at 375px. Column widths:
  - Date: ~70px (short format like "Mar 22")
  - Opponent: flex (takes remaining space; `truncate` if name exceeds space)
  - Score: ~50px (`text-center`)
  - W/L: ~30px (`text-center`)
  - H/A: ~30px (`text-center`, `hidden sm:table-cell` as fallback)
- **Total table width** at 375px: ~70 + ~165 + ~50 + ~30 + ~30 = ~345px + padding. Fits without scroll.
- **Row height**: `py-3 px-3` on `td` = ~44px touch target for linked elements.

### Opponent Detail Page

- **Pitching card**: Single column layout. Each pitcher entry stacks vertically (name line, stat line 1, stat line 2). No horizontal constraints.
- **Team batting summary**: `grid-cols-2` at 375px (2x2 grid). Each stat block is ~170px wide. At `sm:` (640px+) switches to `grid-cols-4` (all 4 in a row).
- **Full stat tables**: Same `overflow-x-auto` pattern as current implementation. Most important columns (Player, ERA/AVG, K/9/OBP, GP) are leftmost. On 375px, the user may need to scroll right for secondary columns (H, ER, BB, etc.) -- this is acceptable for the full detail tables as they are reference data.

### Touch Targets

| Element | Minimum Height | Actual Height |
|---------|---------------|---------------|
| Bottom nav tab | 44px | ~48px (`py-3` + text) |
| Upcoming game card | 44px | ~72px (3 content rows + `p-3`) |
| Completed game table row | 44px | ~44px (`py-3` + text) |
| Team selector pill | 44px | ~44px (`py-2` + text + border) |
| Back link | 44px | Text link -- add `py-2 inline-block` to ensure 44px tappable area |
| Admin shortcut link | 44px | Add `py-2 inline-block` to ensure tappable area |

---

## 7. Interaction Patterns

### Coach Workflow: "Prepare for Tomorrow's Game"

1. **Land on Schedule** (default page after login)
2. **See the NEXT game card** with visual emphasis (blue border, NEXT badge)
3. **Tap the NEXT game card** → navigates to opponent detail scouting page
4. **See "Their Pitchers" card** immediately — who's likely on the mound
5. **Scan Team Batting summary** — how dangerous is this lineup
6. **Check Last Meeting** (if applicable) — how did we do last time
7. **Scroll to full tables** if deeper analysis needed

**Total taps from login to scouting report: 1** (tap the NEXT card). This is the optimal path for the primary coaching use case.

### Coach Workflow: "Review Last Game"

1. **Land on Schedule**
2. **Scroll to Completed section** — most recent game is first
3. **Tap the score** → navigates to box score detail page

**Total taps: 1** (tap the score link).

### Coach Workflow: "Scout a Future Opponent (Not Next Game)"

1. **Land on Schedule**
2. **Tap an upcoming game card** (any game, not just NEXT)
3. **See opponent scouting report**

**Total taps: 1**.

### Coach Workflow: "Check Own Team Batting"

1. **Land on Schedule**
2. **Tap "Batting" in bottom nav**
3. **See batting stats table** (current functionality, unchanged)

**Total taps: 1** (tap Batting tab).

### Home/Away Display Convention

- **Home game**: Prefix opponent name with "vs" — `vs Central Lions`
- **Away game**: Prefix opponent name with "@" — `@ West Eagles`
- **Unknown (null home_away)**: No prefix, no H/A badge. The schedule row omits the home/away indicator rather than guessing. In the completed games table, the H/A cell shows `—` (em dash).

---

## 8. Data Requirements Summary

This section maps each UI element to the data it needs, for SE and DE reference.

### Schedule Page Data

The route handler needs a single query returning all games for the team + season, with:

| Field | Source | Used In |
|-------|--------|---------|
| `game_id` | `games.game_id` | Completed row link to box score |
| `game_date` | `games.game_date` | Date display, days-until calculation |
| `status` | `games.status` | Split into upcoming vs. completed sections |
| `opponent_team_id` | `games.home_team_id` or `games.away_team_id` (whichever is NOT our team) | Link to opponent detail |
| `opponent_name` | JOIN to `teams.name` via opponent_team_id | Display |
| `home_score` | `games.home_score` | Completed score display |
| `away_score` | `games.away_score` | Completed score display |
| `is_home` | Derived: `our_team_id == home_team_id` | vs/@/H/A display |
| `has_stats` | CTE per TN-3: EXISTS in `player_season_batting` OR `player_season_pitching` | Scouted indicator on upcoming cards |
| `opponent_record` | Aggregated W-L from opponent's games (SHOULD HAVE per TN-5) | Display next to opponent name |

**Days-until calculation**: `game_date - today` in Python (route handler). Pass as integer to template. Template renders: 0 → "Today", 1 → "Tomorrow", N → "(N days)".

**"NEXT" game identification**: Route handler identifies `MIN(game_date) WHERE game_date >= today AND status = 'scheduled'` and passes a `next_game_id` to the template. Template checks `game.game_id == next_game_id` to apply emphasis styling.

### Opponent Detail Page Data (New Fields)

In addition to existing scouting report data:

| Field | Source | Used In |
|-------|--------|---------|
| `game_count` | COUNT of games for this opponent in the season | Header ("N games") |
| `top_pitchers` (list, max 3) | Top 3 from `player_season_pitching` by `ip_outs DESC` for this team_id + season_id | Pitching card |
| `pitcher.throws` | `players.throws` | Handedness display (R)/(L) |
| `pitcher.k_bb_ratio` | Computed: `so / bb` (or "∞") | Pitching card secondary stats |
| `team_obp` | Aggregate: `SUM(h+bb+hbp) / SUM(ab+bb+hbp+shf)` across all batters | Team Batting Summary |
| `team_k_pct` | Aggregate: `SUM(so) / SUM(ab+bb+hbp+shf)` as percentage | Team Batting Summary |
| `team_bb_pct` | Aggregate: `SUM(bb) / SUM(ab+bb+hbp+shf)` as percentage | Team Batting Summary |
| `team_slg` | Aggregate: `SUM(tb) / SUM(ab)` across all batters | Team Batting Summary |
| `empty_state` | Enum: `'unlinked'` / `'linked_unscouted'` / `'full_stats'` | Conditional rendering |
| `is_admin` | From user role check (TN-6 pattern) | Show/hide admin shortcut |
| `admin_link_url` | `/admin/opponents/{link_id}/connect` or `/admin/opponents` | Admin shortcut target |

---

*End of design spec. All sections complete, no TBD placeholders.*
