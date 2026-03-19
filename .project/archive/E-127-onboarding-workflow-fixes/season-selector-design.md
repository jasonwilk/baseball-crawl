# Season Selector UX Design

**Story**: E-127-11
**Author**: UX Designer
**Status**: Final

---

## 1. Overview

The dashboard currently falls back to `{current_year}-spring-hs` when no `season_id` query parameter is present. Teams with data only in prior seasons show "No stats available" with no discovery path. Bottom nav links (`/dashboard`, `/dashboard/pitching`, etc.) also drop both `team_id` and `season_id` on navigation, resetting context on every tab change.

This spec defines:
1. Auto-detection of the most recent season with data for the selected team
2. A season selector UI element — placement, appearance, label format, game count
3. Season context persistence through the bottom nav and team selector
4. A data freshness indicator for prior-year seasons
5. Edge cases and opponent-view behavior

---

## 2. Auto-Detection Behavior (AC-1)

### When auto-detection fires

Auto-detection runs whenever no explicit `season_id` query parameter is provided (empty or absent). When `?season_id=` is explicitly supplied, the supplied value is used without auto-detection.

### The query

The backend performs a single query to enumerate available seasons for the active team, ordered most-recent first:

```sql
SELECT season_id, COUNT(DISTINCT game_id) AS game_count
FROM (
    SELECT season_id, game_id FROM game_batting WHERE team_id = :team_id
    UNION ALL
    SELECT season_id, game_id FROM game_pitching WHERE team_id = :team_id
)
GROUP BY season_id
ORDER BY season_id DESC
```

> **Implementation note**: The `ORDER BY season_id DESC` on the lexicographically-formatted `YYYY-type[-classification]` IDs reliably orders seasons with the most recent year first. Within the same year, season type ordering (fall > spring > legion > summer lexicographically) is acceptable — coaches are unlikely to have same-year conflicts in practice.

**Return shape**: a list of `(season_id: str, game_count: int)` tuples, most-recent first. The backend selects the first entry as the active season when no `season_id` param is provided.

**For opponent views** (`/dashboard/opponents/{opponent_team_id}`): the same query runs against the opponent's `team_id`, using `game_batting`/`game_pitching` rows for that opponent. Game count in this context means "games scouted" (rows with boxscore data in the database), not games the opponent actually played.

### Fallback when no seasons found

If the query returns no rows for the team, the route falls back to `{current_year}-spring-hs` (current behavior). This is the "no data loaded yet" state — handled by edge cases (Section 7).

---

## 3. Season ID → Human-Readable Label (AC-6)

Season IDs follow the pattern `{year}-{type}[-{classification}]`. The backend (or a Jinja2 filter) converts to human-readable labels using the following mapping:

| ID segment | Display |
|------------|---------|
| `spring`   | Spring  |
| `summer`   | Summer  |
| `fall`     | Fall    |
| `legion`   | Legion  |
| `hs`       | HS      |
| `usssa`    | USSSA   |

**Label format**: `{Season} {year}` when no classification, `{Season} {year} (classification)` when classification is present.

**Examples**:

| Raw ID | Human label |
|--------|-------------|
| `2025-spring-hs` | Spring 2025 (HS) |
| `2026-spring-hs` | Spring 2026 (HS) |
| `2025-summer` | Summer 2025 |
| `2025-fall-hs` | Fall 2025 (HS) |
| `2025-legion` | Legion 2025 |
| `2025-spring-usssa` | Spring 2025 (USSSA) |

**Implementation**: A Python helper function `format_season_label(season_id: str) -> str` is recommended in `src/api/helpers.py`, registered as a Jinja2 filter `season_label`. This keeps label logic out of templates.

---

## 4. Season Selector UI Element (AC-2, AC-8)

### Element type

A `<select>` dropdown rendered inside a `<form method="GET">`. Pill buttons (like the team selector) are not used for seasons — the season list can grow long over multiple years, and a dropdown is more space-efficient on mobile.

### Placement (AC-9)

The season selector appears **after the team selector and before the page `<h1>`** on all dashboard views that scope content to a season. This placement is consistent whether the view is own-team (Batting, Pitching, Games, Opponents list) or opponent (Opponents detail).

For own-team views, the order is:
1. Team selector (pill row — only shown when >1 permitted team)
2. Season selector (dropdown row)
3. `<h1>` page title

For the opponent detail view, the order is:
1. Back link
2. Opponent name `<h1>`
3. Season selector (positioned between the header block and the stat cards)

**Rationale for opponent placement difference**: The opponent detail page has no team selector (the "which team am I viewing stats FOR?" concept doesn't apply — there's only one opponent). Placing the season selector before the stat cards, after the opponent identity header, feels natural and doesn't embed batting-first assumptions.

### Form behavior

The form submits via `GET` to the current page URL. It carries hidden inputs for `team_id` and (on opponent detail) `opponent_team_id`, so changing season does not lose team context.

```
[Season: Spring 2026 (HS) ▼]   [hidden team_id]
```

No submit button is required. The `<select>` uses `onchange="this.form.submit()"` to submit immediately on selection. This is plain HTML with an inline `onchange` attribute — it requires no JavaScript framework and works in all browsers.

> **If JS is blocked**: Users without JS can still submit via a fallback "Go" button — include `<button type="submit" class="...">Go</button>` and hide it visually if needed. Alternatively, omit it and accept JS as a soft dependency (low risk for dashboard users on modern devices).

### Appearance

```
[Spring 2026 (HS) — 12 games ▼]
```

Each `<option>` in the dropdown includes the human-readable label AND the game count. Format:

- Own-team views: `{label} — {N} games` (e.g., "Spring 2026 (HS) — 12 games")
- Opponent detail view: `{label} — {N} games scouted` (e.g., "Spring 2025 (HS) — 7 games scouted")

The `<option>` value is the raw season ID (e.g., `2026-spring-hs`). The displayed text is the human-readable label + count.

When only one season is available, the selector still renders (it is not hidden) so the coach can see which season they're viewing and confirm it's current.

### HTML/Tailwind reference mockup

```html
<!-- _season_selector.html macro -->
{% macro season_selector(seasons, active_season_id, base_url, team_id, label_suffix="games") %}
<form method="get" action="{{ base_url }}" class="mb-4">
  {% if team_id %}<input type="hidden" name="team_id" value="{{ team_id }}">{% endif %}
  <label class="block text-xs text-gray-500 uppercase tracking-wide mb-1">Season</label>
  <select
    name="season_id"
    onchange="this.form.submit()"
    class="border border-gray-300 rounded px-3 py-2 text-sm bg-white focus:outline-none focus:border-blue-500"
  >
    {% for s in seasons %}
    <option value="{{ s.season_id }}"{% if s.season_id == active_season_id %} selected{% endif %}>
      {{ s.season_id | season_label }} — {{ s.game_count }} {{ label_suffix }}
    </option>
    {% endfor %}
  </select>
</form>
{% endmacro %}
```

**Call sites**:
- Own-team views (Batting, Pitching, Games, Opponents list):
  `{{ season_selector(available_seasons, season_id, "/dashboard", active_team_id) }}`
- Opponent detail view:
  `{{ season_selector(available_seasons, season_id, "/dashboard/opponents/" ~ opponent_team_id, active_team_id, label_suffix="games scouted") }}`

Note: `base_url` for own-team views must be the view-specific URL (`/dashboard`, `/dashboard/pitching`, etc.) so the form submits to the correct route.

---

## 5. Season Context Persistence Across Navigation (AC-3)

Two mechanisms must carry `season_id` (and `team_id`) through navigation:

### 5a. Bottom nav bar (`base.html`)

The bottom nav currently has hardcoded href values. They must become template expressions using `active_team_id` and `season_id` from the template context.

**Required change to `base.html`**:

```html
<!-- Bottom fixed navigation bar -->
<nav class="fixed bottom-0 w-full bg-white border-t border-gray-200 z-10">
  <div class="flex justify-around">
    <a
      href="/dashboard{% if active_team_id or season_id %}?{% endif %}{% if active_team_id %}team_id={{ active_team_id }}{% endif %}{% if active_team_id and season_id %}&{% endif %}{% if season_id %}season_id={{ season_id }}{% endif %}"
      ...
    >Batting</a>
    <!-- (same pattern for pitching, games, opponents) -->
  </div>
</nav>
```

For clarity and maintainability, a Jinja2 macro or global helper should build these URLs. A simpler approach is a `nav_url(base, team_id, season_id)` macro defined in `base.html` or a shared partial:

```html
{% macro nav_url(base, team_id, season_id) %}
  {{ base }}{% if team_id or season_id %}?{% endif %}{% if team_id %}team_id={{ team_id }}{% endif %}{% if team_id and season_id %}&{% endif %}{% if season_id %}season_id={{ season_id }}{% endif %}
{% endmacro %}
```

Usage: `href="{{ nav_url('/dashboard', active_team_id, season_id) | trim }}"`

**All dashboard templates must pass `season_id` and `active_team_id` to the template context** so `base.html` can use them in the nav. Currently, `team_stats.html` (Batting view) does NOT pass `season_id` to the template context; `game_list.html` and `opponent_list.html` do. This must be made consistent across all four tab views.

### 5b. Team selector macro (`_team_selector.html`)

The team selector macro currently generates links like `{base_url}?team_id={team.id}`. When `season_id` is active, those links must preserve it:

```html
{% macro team_selector(permitted_team_infos, active_team_id, base_url, season_id=None) %}
{% if permitted_team_infos|length > 1 %}
<div class="mb-4 flex flex-wrap gap-2">
  {% for team in permitted_team_infos %}
  <a
    href="{{ base_url }}?team_id={{ team.id }}{% if season_id %}&season_id={{ season_id }}{% endif %}"
    class="px-3 py-2 rounded text-sm font-medium
      {% if team.id == active_team_id %}
        bg-blue-900 text-white
      {% else %}
        bg-white text-blue-900 border border-blue-900 hover:bg-blue-50
      {% endif %}"
  >{{ team.name }}</a>
  {% endfor %}
</div>
{% endif %}
{% endmacro %}
```

All `team_selector` call sites must pass the current `season_id`:
`{{ team_selector(permitted_team_infos, active_team_id, "/dashboard", season_id) }}`

### 5c. Opponent list → opponent detail link

The opponent list currently links to:
`/dashboard/opponents/{{ opp.opponent_team_id }}?team_id={{ active_team_id }}`

It must also carry `season_id`:
`/dashboard/opponents/{{ opp.opponent_team_id }}?team_id={{ active_team_id }}&season_id={{ season_id }}`

### 5d. Opponent detail → back link

The back link currently:
`/dashboard/opponents{% if active_team_id %}?team_id={{ active_team_id }}{% endif %}`

Must carry `season_id`:
`/dashboard/opponents?team_id={{ active_team_id }}{% if season_id %}&season_id={{ season_id }}{% endif %}`

---

## 6. Data Freshness Indicator (AC-7)

### When it appears

A yellow info bar appears when the active season's year is strictly less than the current calendar year. "Active season year" is derived from the first four characters of `season_id` (the `YYYY` prefix).

Example: if today is March 2026 and the active season is `2025-spring-hs`, the indicator appears.

### Placement

The freshness indicator appears immediately **below the season selector and above the page `<h1>`** on own-team views. On the opponent detail view, it appears below the season selector and above the stat cards.

### Message copy

> **Showing {human_label} data — no {current_year} season data has been loaded for this team yet.**

Full example:
> Showing Spring 2025 (HS) data — no 2026 season data has been loaded for this team yet.

This message:
- Names the season being viewed so the coach is not confused about what data they're seeing
- Explains the cause in plain language (data hasn't been loaded, not that the team has no data)
- Is non-alarming: "hasn't been loaded yet" implies a solvable state, not a permanent gap
- Tells the operator what to do (run a crawl — they recognize "data hasn't been loaded yet" as their cue)

### Tailwind reference

```html
{% if season_year < current_year %}
<div class="mb-4 p-3 bg-yellow-50 border border-yellow-200 rounded text-sm text-yellow-900">
  Showing {{ season_id | season_label }} data — no {{ current_year }} season data has been loaded for this team yet.
</div>
{% endif %}
```

**Template context requirements**: The route must pass `season_year` (int, parsed from `season_id[:4]`) and `current_year` (int, `datetime.date.today().year`) to the template.

---

## 7. Edge Cases (AC-4)

### 7a. Team with no data in any season

**Trigger**: Auto-detection query returns zero rows.

**Behavior**: Fall back to `{current_year}-spring-hs` (existing behavior). The season selector is rendered with a single option: `{current_year}-spring-hs — 0 games`. Page content shows "No stats available." The freshness indicator does NOT fire (we're showing current-year, just with no data).

> **Note**: This is the new-team or pre-crawl state. The "No stats available" message alone is sufficient. The season selector showing the current season with 0 games confirms where the system is looking.

### 7b. Team with data in multiple seasons

**Trigger**: Auto-detection query returns 2+ rows.

**Behavior**: All seasons appear in the dropdown, most recent first. The most recent season is auto-selected. The coach can switch seasons by selecting a different option.

Example dropdown options:
```
Spring 2026 (HS) — 3 games   ← auto-selected (most recent)
Spring 2025 (HS) — 28 games
Fall 2024 (HS) — 12 games
```

### 7c. Team selector changes to a team with different seasons

**Trigger**: User taps a different team in the team selector while a `season_id` is active.

**Behavior**: The team selector link carries `season_id`. If the new team has data in that season, the season is preserved. If the new team has no data in that season, the backend auto-detection runs (because no data = auto-detect fires, or the route explicitly falls back to the most-recent season for the new team).

**Design decision**: The team selector link should carry the current `season_id` as a query param. The backend must detect when the supplied `season_id` has zero data for the new team and fall back to auto-detection. This is a backend behavior the SE should implement: after resolving the team, check if `season_id` has data; if not, run auto-detection.

> **UX implication**: A coach switches from Varsity to JV while viewing "Spring 2025." If JV has no Spring 2025 data but has Spring 2026 data, the page should show Spring 2026 for JV automatically. The coach is not stuck on a zero-data view just because they carried a stale `season_id`.

### 7d. Single season available

**Trigger**: Only one season in the dropdown.

**Behavior**: The selector renders with one option. It is not hidden — the single option confirms the season to the coach. If a freshness indicator is warranted (single available season is prior-year), it still appears.

### 7e. Opponent with no scouted data

**Trigger**: Opponent detail page reached, but no boxscore data loaded for this opponent.

**Behavior**: Season selector shows one option (current-year fallback) with "0 games scouted." Stat sections show their empty-state messages ("No batting stats available", etc.).

---

## 8. New Template Macro: `_season_selector.html`

A new Jinja2 macro file at `src/api/templates/dashboard/_season_selector.html` encapsulates the season selector form. This follows the same pattern as `_team_selector.html`.

**Macro signature**:

```
season_selector(seasons, active_season_id, base_url, team_id, label_suffix="games")
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `seasons` | list of `{season_id: str, game_count: int}` | Available seasons, most-recent first |
| `active_season_id` | str | Currently displayed season (pre-selected option) |
| `base_url` | str | Form action URL (view-specific: `/dashboard`, `/dashboard/pitching`, etc.) |
| `team_id` | int or None | Current team — passed as hidden input to preserve team context |
| `label_suffix` | str | `"games"` for own-team views; `"games scouted"` for opponent detail |

---

## 9. Backend Contract

The following changes to route handlers support this design. These are implementation notes for E-127-12.

### New context variables (all season-scoped routes)

| Variable | Type | Description |
|----------|------|-------------|
| `season_id` | str | Active season ID (always present, even if fallback) |
| `available_seasons` | list[dict] | `[{season_id, game_count}, ...]` most-recent first |
| `season_year` | int | `int(season_id[:4])` |
| `current_year` | int | `datetime.date.today().year` |

All four tab views (Batting, Pitching, Games, Opponents list) and the opponent detail view must include these in their template context.

### New DB query

A new function `db.get_available_seasons(team_id: int) -> list[dict]` returns `[{season_id, game_count}, ...]` ordered descending. This replaces the inline fallback logic at lines 100-102, 234-235, 343-344, 520-521 of `src/api/routes/dashboard.py`.

For opponent detail: `db.get_opponent_available_seasons(opponent_team_id: int) -> list[dict]` — same query but scoped to the opponent's `team_id`.

### Auto-detection logic

Route handlers call `get_available_seasons(team_id)`. If `season_id` param is absent or empty, use `seasons[0]["season_id"]` if available, else fall back to `f"{current_year}-spring-hs"`. If `season_id` param is present but has no data for this team, fall back to auto-detection (do not show 0-data view when a better season exists).

---

## 10. Summary of Files to Create or Modify

| File | Change |
|------|--------|
| `src/api/templates/dashboard/_season_selector.html` | **New** — Jinja2 macro |
| `src/api/templates/dashboard/_team_selector.html` | **Modify** — add `season_id` param to links |
| `src/api/templates/base.html` | **Modify** — bottom nav links carry `active_team_id` and `season_id` |
| `src/api/templates/dashboard/team_stats.html` | **Modify** — import and call season_selector; pass season_id in context |
| `src/api/templates/dashboard/team_pitching.html` | **Modify** — same as team_stats |
| `src/api/templates/dashboard/game_list.html` | **Modify** — import and call season_selector |
| `src/api/templates/dashboard/opponent_list.html` | **Modify** — import and call season_selector; carry season_id in opponent links |
| `src/api/templates/dashboard/opponent_detail.html` | **Modify** — import and call season_selector (opponent mode); update back link |
| `src/api/routes/dashboard.py` | **Modify** — replace hardcoded fallback with auto-detection; add new context vars |
| `src/api/db.py` | **Modify** — add `get_available_seasons` and `get_opponent_available_seasons` |
| `src/api/helpers.py` | **Modify** — add `format_season_label` function; register as Jinja2 filter |
