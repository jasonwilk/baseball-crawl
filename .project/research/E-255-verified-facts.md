# E-255 Verified Facts (R-01 fact-verification spike)

**Produced by:** E-255-R-01 (api-scout lead + data-engineer for AC-3), MAIN checkout, pre-dispatch.
**Date:** 2026-07-07.
**Purpose:** The doc prose under correction is exactly the thing in doubt, so it cannot be its own source of truth. This artifact records each of the six load-bearing facts against ground truth (proxy captures, live public curl, cached samples, working code, config files) so the correction stories (E-255-01/02/04/05) cite verified facts, not doc prose.

**No credentials appear in this file.** All auth headers/tokens were stripped from every cited source. Real identifiers are redacted to prefixes or placeholders.

---

## AC-1 (F) — `game_stream.id` routing for boxscore + plays (PROXY-FIRST, HIGHEST RISK)

### Verified truth

1. **A SINGLE id serves BOTH the boxscore AND the plays endpoint — the same id, unchanged.** In the reports/scouting pipeline that id is the **public-games event id** (`id` in `GET /public/teams/{public_id}/games`, `event_id` in `.../games/preview` — same value, different field name). It is used verbatim as the `{id}` path parameter for:
   - `GET /game-stream-processing/{id}/boxscore`
   - `GET /game-stream-processing/{id}/plays`
   There is no per-endpoint id difference. The doc's "different UUIDs" wording (game-summaries L52) is about `game_stream.id` vs `game_stream.game_id`/`event_id` **within the authenticated response** — it is NOT a signal that boxscore and plays take different ids. They take the same one.

2. **Two "plays" URL shapes exist, but only one is an authenticated API endpoint:**
   - **API (authoritative for ingestion):** `GET /game-stream-processing/{id}/plays` on `api.team-manager.gc.com`. This is what the code calls (`src/reports/generator.py:920`).
   - **Web UI route (not an API call):** `GET /teams/{public_id}/{season-slug}/schedule/{event_id}/plays` — documented in `docs/api/endpoints/web-routes-not-api.md:21` as the browser play-by-play *view*, not a JSON API endpoint. E-255-04 should NOT document this as a second API ingestion path; it is a human-facing web route.

3. **Captured id cross-reference (unambiguous mapping).** The captured id `3cab6a64…` is one real game. Across the two proxy sessions it appears as the *same value* in every id role:
   | Endpoint (session) | id role | field/param carrying `3cab6a64…` |
   |---|---|---|
   | `GET /public/teams/{public_id}/games` (03-11, 200) | game record | `id` (record index 19) |
   | `GET /public/teams/{public_id}/games/preview` (03-11, 200) | game record | `event_id` (record index 18) |
   | `GET /game-stream-processing/{id}/boxscore` (03-09, 200) | path param | `{id}` |
   | `GET /game-stream-processing/{id}/plays` (03-09, 200) | path param | `{id}` |
   | `GET /public/game-stream-processing/{id}/details` (03-09/03-11, 200) | path param + body `id` | `{id}` |
   | `GET /events/{id}/best-game-stream-id` (03-09, 200) | path param (event_id) | `{id}` |
   | `GET /game-streams/gamestream-recap-story/{id}` (03-11, 200) | path param + body `recap._id` | `{id}` |

   → The public-games `id`/`event_id` (`3cab6a64…`) **is** the `/game-stream-processing/{id}/…` path parameter for both boxscore and plays. Proven from **live 200 responses**, not a naive swap.

### Important nuance (contradiction the sweep must resolve — do NOT overstate)

- The **authenticated** `game-summaries` endpoint DOES return two distinct UUIDs per record: `event_id` (== `game_stream.game_id`) ≠ `game_stream.id`. Confirmed on 3 cached records (`data/raw/game-summaries-sample.json`): e.g. `event_id=4c91cd0b…` / `game_stream.id=ba176ef0…` differ. So the doc's "they are different UUIDs" claim is **true for the authenticated response shape**.
- The **reports/scouting pipeline never uses the authenticated `game-summaries` endpoint** — it uses the **public** games endpoint (single id) and feeds that id straight into `/game-stream-processing/{id}/…`, which returns 200. Working code confirms this:
  - Boxscore: `src/gamechanger/crawlers/scouting.py:260,266` — `game_stream_id = game.get("id")` (public-games `id`) → `f"/game-stream-processing/{game_stream_id}/boxscore"`.
  - Plays: `src/reports/generator.py:861,920` — `game_ids` are documented in-code as "SOURCE event ids" → `f"/game-stream-processing/{game_id}/plays"`.
  - `.claude/rules/data-model.md` already states: "`event_id` from game-summaries is the path parameter for both `GET /game-stream-processing/{event_id}/boxscore` and `GET /game-stream-processing/{event_id}/plays`" — this contradicts the game-summaries endpoint doc L52/L114 ("USE `game_stream.id`"), and data-model.md matches the captured behavior.
- **Residual unknown (flag for E-255-04, do not assert either way):** I could NOT prove whether, for the `3cab6a64…` game specifically, the public-games `id` equals that game's authenticated `game_stream.id` or its `event_id`. The game-summaries request for this game was **304 Not Modified** in both proxy sessions (no body captured), and `.env` creds are ~4 months stale so a live authenticated fetch is not available. What is certain: whatever you call it, **one id drives both boxscore and plays**, and in the public/reports path it is the public-games `id`/`event_id`.

### Guidance for E-255-04 (game-summaries L52/L114 correction)

Reconcile the endpoint doc to reality by describing BOTH id-resolution paths rather than asserting a single canonical name:
- **Authenticated flow:** `game-summaries` returns `event_id` (== `game_stream.game_id`) and a distinct `game_stream.id`.
- **Public/reports flow (what the pipeline actually runs):** the public-games `id` (`= /games/preview event_id`) is used unchanged as the `/game-stream-processing/{id}/…` path parameter for **both** boxscore and plays.
- Do NOT claim boxscore and plays take *different* ids — they take the same id. Keep the factual authenticated `event_id ≠ game_stream.id` note (it is a real schema fact), but stop implying it forces a two-id boxscore/plays split.

### Sources
- Proxy: `proxy/data/sessions/2026-03-09_062059/endpoint-log.jsonl` (metadata; boxscore + plays + best-game-stream-id all 200 on `3cab6a64…`), `proxy/data/sessions/2026-03-11_032625/endpoint-log.jsonl` (full bodies; public-games `id`/preview `event_id` = `3cab6a64…`; game-summaries were 304).
- Cached: `data/raw/game-summaries-sample.json` (authenticated `event_id ≠ game_stream.id`, 3 records).
- Code: `src/gamechanger/crawlers/scouting.py:260-266`, `src/reports/generator.py:861,920`.
- Doc contradiction: `docs/api/endpoints/get-teams-team_id-game-summaries.md:52,114` vs `.claude/rules/data-model.md` (Enriched stat columns) vs `docs/api/endpoints/web-routes-not-api.md:21,40`.

---

## AC-2 (G) — `team_season` shape from `GET /public/teams/{public_id}` (PUBLIC, LIVE-CONFIRMED)

### Verified truth

`team_season` is a flat object. **`season` is a bare STRING (the season name), and `year` is a FLAT integer sibling** — there is NO `team_season.season.year` nesting:

```json
"team_season": {
  "season": "summer",              // bare STRING (season name), NOT an object
  "year": 2025,                    // FLAT int, sibling of season  → team_season.year
  "record": {"win": 12, "loss": 8, "tie": 0}    // singular keys (values generalized)
}
```

- The correct year path is **`team_season.year`** (flat), NOT `team_season.season.year`.
- `team_season.season` holds a **season-name string** (`"summer"` / `"spring"` / etc.), not an object with `.year`/`.name`.
- `team_season.record` uses **singular** keys `win`/`loss`/`tie` (already correctly documented; the authenticated endpoint uses plural `wins`/`losses`/`ties`).

### What is WRONG in current docs (for E-255-01/02/04)

- `docs/api/endpoints/get-public-teams-public_id.md:72-73,94` documents `team_season.season` as an **object** `{"year": 2024, "name": "summer"}` (year at `team_season.season.year`). **Wrong** — invert it: `season` is a string, `year` is flat.
- `.claude/rules/testing.md` "Test-Validates-Spec" worked example asserts the public endpoint nests year at `team_season.season.year`. **Wrong** for the same reason; the flat `team_season.year` is correct. (The authenticated endpoint's top-level `season_year` int, also cited in that example, is a separate and correct fact — only the public-endpoint nesting is wrong.)

### Verification (live, no creds)

- **Live curl 2026-07-07:** `GET https://api.team-manager.gc.com/public/teams/{public_id}` → **200 OK**, returned `season="summer"` (str), `year=2025` (int, flat), `record={win,loss,tie}`. No `gc-token`/`gc-device-id` sent (public endpoint).
- **Cached corroboration:** `data/raw/public-team-profile-sample.json` shows the identical flat shape (`season` str, `year` flat int, singular record keys).
- Two independent sources (live + cached) agree, resolving the prior single-sample UNVERIFIED caveat.

### Sources
- Live: `GET /public/teams/{public_id}` (200, no auth), executed 2026-07-07.
- Cached: `data/raw/public-team-profile-sample.json`.
- Doc under correction: `docs/api/endpoints/get-public-teams-public_id.md:72-73,94`; `.claude/rules/testing.md` (Test-Validates-Spec example).

---

## pitches_7d (AC-3)

**Verified semantics** (the 3-state model, authoritative):
- **`0`** = pitcher had a last outing but NO appearances in the 7-day window (LEFT JOIN miss — `seven_day` CTE produced no row for the player).
- **`NULL`** = pitcher had appearance(s) in the window but EVERY one has an unrecorded (NULL) pitch count.
- **`SUM`** = normal case: sum of the non-NULL recorded pitch counts in the window.

**Source**: `src/api/db.py`, `get_pitching_workload()`, the final `SELECT`'s CASE expression at **L205–209**:

```sql
CASE
    WHEN sd.appearances_7d IS NULL THEN 0      -- no window appearances (LEFT JOIN miss) → 0
    WHEN sd.non_null_pitch_count = 0 THEN NULL -- appeared, but all pitch counts unrecorded → NULL
    ELSE sd.raw_sum                            -- normal SUM
END AS pitches_7d
```

Supporting definitions in the `seven_day` CTE (L185–200): `appearances_7d = COUNT(*)`, `non_null_pitch_count = COUNT(pitches)` (COUNT ignores NULLs), `raw_sum = SUM(pitches)` (NULL when all pitches are NULL). The outer `LEFT JOIN seven_day sd` (L213) is what makes `sd.appearances_7d IS NULL` mean "no window appearances," yielding `0`.

Note the semantic ordering: the `0`-vs-`NULL` distinction is "did the pitcher appear in the window at all" (0 = no appearances) vs. "appeared but pitch counts unknown" (NULL). This is the opposite of a naive reading where NULL = "no data / no outings" and 0 = "recorded zero" — hence the audit's inversion claim against the doc.

### Guidance for E-255-02 (key-metrics.md correction)
`.claude/rules/key-metrics.md` currently describes these two states INVERTED. Correct it to match the code above: **`0` = pitched (had a last outing) but no appearances in the 7-day window; `NULL` = appeared in the window but all pitch counts unrecorded; `SUM` = normal.** Verified by data-engineer against `src/api/db.py:205-209`.

---

## AC-4 (E-211 self-heal) — the deliberate `gc_uuid` overwrite

### Verified truth

`gc-uuid-bridge.md`'s Storage Rule ("never overwrite an existing `gc_uuid`"; `UPDATE ... WHERE gc_uuid IS NULL`) is the rule for the **bridge resolution path in general**, but the **E-211 self-heal in the report generator deliberately OVERWRITES `gc_uuid` for TRACKED teams** — with no `gc_uuid IS NULL` guard. The overwrite is made safe by a `membership_type = 'tracked'` guard, so member `gc_uuid`s are never touched.

Actual code — `src/reports/generator.py::_resolve_gc_uuid_stage` (L2088-2117):

```python
if membership_type == "member" and existing_gc_uuid:
    self.resolved_gc_uuid = existing_gc_uuid            # member: stored gc_uuid authoritative, never re-resolved
elif self.team_info.get("name"):
    self.resolved_gc_uuid = _resolve_gc_uuid(self.client, self.team_info["name"], self.public_id)
    if self.resolved_gc_uuid:
        conn.execute(
            "UPDATE teams SET gc_uuid = ? WHERE id = ? "
            "AND membership_type = 'tracked'",       # <-- NO "AND gc_uuid IS NULL"; overwrites for tracked
            (self.resolved_gc_uuid, self.team_id),
        )
```

**The real overwrite condition:**
- **TRACKED teams** re-search-resolve `gc_uuid` on every report run and **overwrite** the stored value unconditionally (guarded only by `membership_type='tracked'`). Rationale (docstring L2091-2093): "stored gc_uuid may be contaminated by opponent-perspective boxscore keys -- see E-211." Re-resolving from the team name + `public_id` each run heals a contaminated value.
- **MEMBER teams** use the stored `gc_uuid` (from the authenticated API) as-is and are **never** overwritten by this path.

### Guidance for E-255-02 (gc-uuid-bridge.md reconciliation)

Keep the "never overwrite" Storage Rule as the default for the generic bridge, but add the E-211 carve-out: **tracked teams are deliberately re-resolved and overwritten each report run (membership_type='tracked' guard), because a tracked team's stored `gc_uuid` can be a contaminated opponent-perspective boxscore key; member `gc_uuid`s are authoritative and never overwritten.** The `WHERE gc_uuid IS NULL` shape in the rule is the storage-time bridge write; it is not the self-heal write.

### Sources
- Code: `src/reports/generator.py:2088-2117` (`_resolve_gc_uuid_stage`), docstring L2091-2093.
- Rule under correction: `.claude/rules/gc-uuid-bridge.md` (Storage Rule section).

---

## AC-5 (recovery command) — the real `bb creds` surface

### Verified truth

`bb creds` has **no `login` subcommand.** `operations.md`'s `bb creds login` recovery step names a command that does not exist. The registered subcommands (`src/cli/creds.py`) are exactly:

| Subcommand | Function (line) |
|---|---|
| `import` | `import_creds` (L173/174) |
| `refresh` | `refresh` (L285/286) |
| `check` | `check` (L586/587) |
| `extract-key` | `extract_key` (L808/809) |
| `capture` | `capture` (L889/890) |
| `setup` | `setup` (L922/923) |

**Recovery command to record (feeds E-255-05 AC-8):**
- **First-line: `bb creds refresh`** — renews the access token from the refresh token. When no refresh token is present it falls back to a login bootstrap using `GAMECHANGER_USER_EMAIL` + `GAMECHANGER_USER_PASSWORD` (`refresh` at L332-366: `use_login_bootstrap = not refresh_token`; `tm.do_login()` vs `tm.force_refresh(allow_login_fallback=True)`). Matches the existing idiom at `operations.md:418` and `getting-started.md:137`.
- **Fallback (refresh token dead): `bb creds import`** (import a fresh captured session) **or `bb creds setup web`** (guided web-profile setup).

("login" appears in `creds.py` only as internal identifiers — `has_login_creds`, `use_login_bootstrap`, `do_login()` — never as a CLI subcommand.)

### Sources
- Code: `src/cli/creds.py` command registrations (`@app.command`) at L173, L285, L586, L808, L889, L922; refresh/login-bootstrap logic L314-366.
- Idiom corroboration: `operations.md:418`, `getting-started.md:137`.
- Doc under correction: `operations.md` (`bb creds login`).

---

## AC-6 (host execution) — invocation form for `bb` / `python scripts/backup_db.py`

### Verified truth

The Python package (which provides the `bb` console script) is **pip-installed ONLY inside the container** — there is no host install step. Therefore all runbook commands that invoke `bb …` or `python scripts/backup_db.py` must run **inside the app container**:

- **Invocation form to record (feeds E-255-05 AC-9): `docker compose exec [-T] app …`**
  e.g. `docker compose exec -T app python scripts/backup_db.py`, `docker compose exec app bb creds setup web`.
  (Use `-T` for non-interactive/cron contexts, without `-T` for interactive.)

Evidence:
- `Dockerfile:22` `RUN pip install --no-cache-dir -r requirements.txt` and `Dockerfile:30` `RUN pip install --no-cache-dir --no-deps -e .` — dependencies + editable package install happen **in the image build only**. No host-side `pip install` / `bb` bootstrap exists.
- `docker-compose.yml` — the `app` service is `build: .` (L2-3), so `bb` and `scripts/` live only in that container's environment.
- Consequently the runbook's bare `bb creds setup web` (production-deployment L144) and bare `python scripts/backup_db.py` (L300/411/455, incl. the host cron at L428) cannot run on the bare host as written.

### FYI for the READY summary (Jason's deployment-owner call, non-blocking)

Whether the **daily backup cron** ultimately uses `docker compose exec -T app python scripts/backup_db.py` vs. a documented host-side install of the package is a deployment-owner decision for Jason. The **truth-sweep default is `docker compose exec`** (matches the actual current install topology); surface the host-install option as an alternative for Jason to decide, but do not block the sweep on it.

### Sources
- Config: `Dockerfile:22,30`; `docker-compose.yml:2-3` (`app` service `build: .`).
- Doc under correction: `docs/admin/production-deployment.md` (bare `bb`/`python scripts/backup_db.py` at L144/L300/L411/L428/L455 — note: file relocated from `docs/` root in this same R-01 step).

---

## Summary table (for the correction stories)

| Fact | Verdict | Feeds |
|---|---|---|
| **F** (game_stream.id routing) | ONE id for boxscore AND plays; public-games `id`/`event_id` is the `/game-stream-processing/{id}/…` path param; second "plays" form is a WEB UI route, not an API endpoint; authenticated `event_id ≠ game_stream.id` is a real schema fact but does NOT force a two-id split | E-255-04 |
| **G** (team_season shape) | `team_season.season` = bare STRING; `year` FLAT at `team_season.year`; record singular `{win,loss,tie}`. Doc's `team_season.season.year` nesting is WRONG (LIVE-confirmed) | E-255-01, -02, -04 |
| **pitches_7d** | `0` = pitched but no appearances in 7-day window; `NULL` = appeared but all pitch counts unrecorded; `SUM` = normal (verified by DE against `src/api/db.py:205-209`); key-metrics.md states these INVERTED | E-255-02 |
| **E-211 self-heal** | Tracked teams' `gc_uuid` is deliberately OVERWRITTEN each run (membership_type='tracked' guard, no `gc_uuid IS NULL`); member teams never overwritten | E-255-02 |
| **recovery command** | `bb creds refresh` (first-line); `bb creds import` / `bb creds setup web` fallback; NO `bb creds login` exists | E-255-05 (AC-8) |
| **host-exec** | `docker compose exec [-T] app …`; package installed in container only (Dockerfile:30) | E-255-05 (AC-9) |
