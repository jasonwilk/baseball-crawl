# CR-2: Admin Routes & Templates Review

## Files Reviewed
- `src/api/routes/admin.py` (1664 lines)
- `src/api/templates/admin/confirm_team.html`
- `src/api/templates/admin/edit_team.html`
- `src/api/templates/admin/edit_user.html`
- `src/api/templates/admin/opponent_connect.html`
- `src/api/templates/admin/opponents.html`
- `src/api/templates/admin/teams.html`
- `src/api/templates/admin/users.html`

---

## Critical Issues

### 1. XSS via JavaScript context in `users.html` (line 57)

```html
onsubmit="return confirm('Delete {{ user.email }}? This cannot be undone.');"
```

Jinja2 auto-escaping produces HTML entities (e.g., `'` → `&#39;`), but the browser HTML-decodes attribute values **before** passing them to the JavaScript engine. A user-supplied value containing a single quote would produce:

1. Jinja2 output: `confirm('Delete o&#39;connor? ...')`
2. After HTML decode: `confirm('Delete o'connor? ...')`
3. JS parse: broken string → syntax error (benign), but a crafted value like `x');alert(document.cookie);//` would execute arbitrary JS.

The `opponents.html` template (line 111-112) already uses the safe pattern:
```html
data-name="{{ link.opponent_name }}"
onclick="return confirm('Disconnect ' + this.dataset.name + '?')"
```

**Fix**: Refactor `users.html` to use `data-*` attribute + `this.dataset.*` like `opponents.html` does.

**Severity**: Critical. Exploitable by anyone who can create a user account (admin-only route, but still a real XSS in production).

---

## Warnings

### 2. No server-side email format validation (`admin.py:631`)

`create_user` does `email.strip().lower()` but never validates email format. The HTML form uses `type="email"` for client-side validation, but a direct POST bypasses this. Malformed or malicious email values can be stored in the database and later rendered in templates.

This amplifies the XSS in Critical Issue #1 — without server-side validation, an attacker-controlled email value flows directly into the JS context.

**Fix**: Add a basic server-side email regex check (e.g., `re.match(r'^[^@]+@[^@]+\.[^@]+$', email)`) before insertion.

### 3. `discover_opponents` does not link opponents to the discovering team (`admin.py:1322-1323`)

```python
names = [opp.name for opp in discovered]
count = await run_in_threadpool(bulk_create_opponents, names)
```

The route calls `bulk_create_opponents(names)` with only opponent names — no reference to the discovering team's `id`. The flash message says "Discovered N new opponents **for {team_name}**" but the actual DB operation may not create `opponent_links` rows connecting the opponents to the team. This depends on `bulk_create_opponents` implementation (outside review scope), but the API at the route level doesn't pass the team relationship.

**Fix**: Verify `bulk_create_opponents` creates `opponent_links` rows, or pass `team_id` to establish the relationship.

### 4. Race condition in `_toggle_team_active_integer` (`admin.py:415-427`)

The SELECT + UPDATE is not atomic — between reading `is_active` and writing the toggled value, another request could toggle the same team. With SQLite WAL mode and single-server deployment this is low-risk, but the pattern is fragile.

**Fix**: Use `UPDATE teams SET is_active = NOT is_active WHERE id = ? RETURNING is_active` (SQLite 3.35+) for atomicity, or accept the risk given the single-admin deployment context.

---

## Minor Issues

### 5. Inconsistent URL path parameter naming (`admin.py`)

Team routes use both `team_id` (lines 1165, 1202) and `id` (lines 1254, 1281) for the same concept (INTEGER team PK). This inconsistency makes the code harder to maintain:
- `GET/POST /teams/{team_id}/edit` — uses `team_id`
- `POST /teams/{id}/toggle-active` — uses `id`
- `POST /teams/{id}/discover-opponents` — uses `id`

**Fix**: Standardize on `team_id` for all team routes.

### 6. `_VALID_CLASSIFICATIONS` includes `"legion"` which overlaps with program type (`admin.py:78-82`)

The classification set includes `legion` alongside HS divisions (`varsity`, `jv`, etc.) and USSSA age groups. Per CLAUDE.md, `legion` is a program type, not a classification. The confirm_team.html template (line 120) places it under the "High School" optgroup, which is semantically wrong.

**Fix**: Move `legion` to its own optgroup or clarify its classification vs. program-type semantics.

### 7. Duplicate `Jinja2Templates` instance (`admin.py:73`)

The admin routes module creates its own `Jinja2Templates` instance (`templates = Jinja2Templates(...)`) while `main.py` also creates one (`_templates = Jinja2Templates(...)`). These are independent instances pointing to the same directory. Not a bug, but wasteful — any future template configuration (filters, globals) would need to be duplicated.

---

## Observations

### Positive Findings

1. **SQL injection protection**: All SQL queries use parameterized `?` placeholders throughout. No string interpolation in SQL. Solid.

2. **INTEGER PK consistency**: All URL path parameters (`team_id: int`, `id: int`, `link_id: int`, `user_id: int`) correctly use `int` type annotations. All DB queries reference `teams.id` as INTEGER. Consistent with the data model.

3. **Membership type validation**: Both `confirm_team_submit` (line 1124) and `update_team` (line 1232) validate `membership_type` against `_VALID_MEMBERSHIP_TYPES` and return 400 on invalid values.

4. **Classification validation**: Both creation and update paths validate against `_VALID_CLASSIFICATIONS`, silently defaulting invalid values to `None`.

5. **Duplicate detection**: `_check_duplicate_new` checks both `public_id` and `gc_uuid` (including Phase 1 fallback). TOCTOU refresh guards against stale bridge results. `sqlite3.IntegrityError` caught as final safety net.

6. **Member radio disabled when gc_uuid unavailable**: `confirm_team.html` line 72 correctly disables the "Member" radio when `gc_uuid_status != 'found'`, with explanatory text.

7. **Two-phase add-team flow**: Phase 1 resolves URL → bridge → profile, redirects with query params. Phase 2 renders confirm page with duplicate check. POST Phase 2 does TOCTOU refresh + duplicate re-check + insert with IntegrityError catch. Well-structured.

8. **Admin guard**: `_require_admin` properly checks session, redirects unauthenticated users, and supports dev mode (ADMIN_EMAIL unset). Self-delete prevention on user delete route.

9. **Opponent connect flow**: Already-resolved check prevents double-linking. Member-team rejection prevents linking opponents to own teams. Duplicate warning (non-blocking) shown on confirmation page.

10. **Auto-escaping**: Jinja2Templates uses auto-escaping for `.html` extensions by default. All template variables use `{{ var }}` syntax with auto-escaping active — safe for HTML contexts. The only vulnerability is the JS context in `users.html` (Critical Issue #1).
