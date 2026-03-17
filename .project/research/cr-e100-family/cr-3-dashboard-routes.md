# CR-3: Dashboard Routes & Templates

## Files Reviewed

- `src/api/routes/dashboard.py`
- `src/api/templates/dashboard/game_detail.html`
- `src/api/templates/dashboard/game_list.html`
- `src/api/templates/dashboard/opponent_detail.html`
- `src/api/templates/dashboard/opponent_list.html`
- `src/api/templates/dashboard/player_profile.html`
- `src/api/templates/dashboard/team_pitching.html`
- `src/api/templates/dashboard/_team_selector.html`
- `src/api/templates/dashboard/team_stats.html`
- `src/api/templates/errors/forbidden.html`
- `src/api/db.py` (supporting queries)
- `src/api/helpers.py` (Jinja2 filters)
- `src/api/templates/base.html` (base layout)

---

## Critical Issues

### 1. Broken back-link URL in player_profile.html

**File:** `src/api/templates/dashboard/player_profile.html:22,26`

The back-link points to `/dashboard/stats?team_id={{ backlink_team_id }}` (line 22) and `/dashboard/stats` (line 26), but no such route exists. The batting stats route is `GET /dashboard` (defined at `dashboard.py:48`). These links will produce a 404.

**Fix:** Change `/dashboard/stats` to `/dashboard` on both lines 22 and 26.

### 2. Game box score pitching table displays non-existent HR column

**File:** `src/api/templates/dashboard/game_detail.html:113,129` and `src/api/db.py:309-322`

The game detail template has an "HR" column header (line 113) and renders `{{ pitcher.hr }}` (line 129) for each pitching line. However:
- The `get_game_box_score` pitching query (`db.py:309-322`) does NOT select an `hr` column.
- The `player_game_pitching` schema explicitly excludes HR ("Excluded: HR allowed (not present in boxscore pitching extras)" -- `migrations/001_initial_schema.sql:185`).

This means every game box score pitching row shows a blank in the HR column. Jinja2 renders undefined dict keys as empty string rather than crashing, but the column is misleading -- it implies zero HRs when the data simply isn't available.

**Fix:** Remove the HR column header and `{{ pitcher.hr }}` cell from `game_detail.html`, since the underlying data does not exist at the per-game pitching level.

### 3. Tied games display "-" instead of "T" in game list

**File:** `src/api/templates/dashboard/game_list.html:68-74`

The `_compute_wl` function (`dashboard.py:270-291`) correctly returns `"T"` for tied games. However, the template only checks for `"W"` and `"L"`, with everything else falling through to the `else` branch that displays `"-"`. This means tied games are visually indistinguishable from games with null scores. E-120-07 was supposed to fix tied-game W/L display, but the template was not updated to render "T".

**Fix:** Add `{% elif game.wl == 'T' %}` branch displaying `<span class="text-gray-600">T</span>` between the "L" check and the `else`.

---

## Warnings

### 1. Opponent detail back-link loses team context

**File:** `src/api/templates/dashboard/opponent_detail.html:21`

The back-link `<a href="/dashboard/opponents">` does not include `?team_id={{ active_team_id }}`. If a user viewing opponents for Team A clicks into a scouting report and then clicks "Back to Opponents", they may land on the default team instead of Team A. Compare with `game_detail.html:21` which correctly preserves `team_id`.

### 2. OBP calculation is simplified (no HBP/SF)

**Files:** `team_stats.html:57`, `player_profile.html:51,106`, `opponent_detail.html:129`

OBP is calculated as `(H + BB) / (AB + BB)` rather than the full formula `(H + BB + HBP) / (AB + BB + HBP + SF)`. This is consistent across all templates and matches the available data (HBP and SF are not surfaced in the season stats queries), so it's a known data limitation rather than a bug. Noting for completeness.

### 3. Season ID defaults to hardcoded pattern

**File:** `src/api/routes/dashboard.py:102,235,344,521,614`

Every route defaults `season_id` to `f"{datetime.date.today().year}-spring-hs"`. This assumes all users are viewing spring HS seasons. If the platform expands to USSSA (`-summer-usssa`) or Legion (`-summer-legion`), users without an explicit `?season_id=` will always see HS data. This is a known design decision for the current scope but worth flagging for multi-program expansion.

---

## Minor Issues

### 1. `_check_opponent_authorization` uses inline imports

**File:** `src/api/routes/dashboard.py:669-671`

The function imports `sqlite3` and `closing` inside the function body rather than using the module-level imports already present at lines 17 (`closing`) and the `db` module's `get_connection`. The function also opens its own raw SQLite connection and builds a query with string formatting for placeholders, while all other dashboard queries go through `db.py` functions. This inconsistency is replicated in `_check_player_authorization` (lines 823-824).

### 2. `_check_player_authorization` same pattern

**File:** `src/api/routes/dashboard.py:823-824`

Same inline-import and raw-connection pattern as `_check_opponent_authorization`. Both authorization checks would be more consistent as functions in `db.py`.

---

## Observations

- **Auth enforcement is solid**: Every route validates `permitted_teams` from `request.state`, returns 403 for unauthorized access, and handles the no-assignments case. Game detail and opponent detail have additional resource-level authorization checks.
- **INTEGER PK usage is correct**: All URL patterns use integer team_ids, all DB queries reference `teams.id` as integers, and the team selector macro passes integer IDs.
- **XSS protection is adequate**: Jinja2 auto-escaping is active (no `|safe` filter usage found). All dynamic content goes through `{{ }}` which auto-escapes.
- **No stale `display_name`/`is_admin` references**: Templates use `user.email` consistently; no legacy field names found.
- **Null score handling is correct** in `game_detail.html` (uses `is not none` checks) and `game_list.html` (same pattern).
- **`_compute_wl` logic is correct** for W/L/T computation -- the issue is only in the template rendering of "T".
- **Pitching rate calculations** (ERA, K/9, BB/9, WHIP) in `_compute_pitching_rates` and `_compute_opponent_pitching_rates` are mathematically correct with proper zero-division guards.
- **SLG calculation** `(H + 2B + 2*3B + 3*HR) / AB` is the correct total-bases formula, used consistently.
- **`forbidden.html`** extends `base_auth.html` (not `base.html`), which is appropriate for an error page shown to authenticated users who lack team permissions.
