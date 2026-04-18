# E-225: POST /search Punctuation Normalization Fallback

## Status
`READY`

## Overview
GameChanger's `POST /search` backend returns zero hits for team names containing certain punctuation characters -- historically observed: `/`, straight apostrophe `'` (U+0027), `%`, and `#` -- even though the indexed name stores the character. Replacing punctuation (any `[^\w ]` character) with spaces recovers the correct match. This epic adds a shared punctuation-normalization fallback to every call site that searches by team name, so punctuation-named teams stop silently failing to resolve. The motivating user impact: standalone reports for "Lincoln Northwest JV/Reserve Falcons" generate with zero spray charts because `gc_uuid` cannot be resolved.

## Background & Context

### The bug
`POST /search` is called in four places with a body shape of `{"name": team_name}` (content-type `application/vnd.gc.com.post_search+json; version=0.0.0`). When `team_name` contains any of four confirmed-problem characters, the backend returns zero hits on every page. api-scout probed this 2026-04-16 with a 14-character test (characters inserted into an otherwise-valid query string) and confirmed:

| Character | First-page hits |
|-----------|-----------------|
| `/` | 0 |
| `'` (straight, U+0027) | 0 |
| `%` | 0 |
| `#` | 0 |
| `&`, `(`, em-dash, en-dash, `-`, `\`, `+`, `.`, `,`, `:` | 25 (clean) |

User-impact probe for `public_id=yecaUcoSVpJa`:

- `{"name": "Lincoln Northwest JV/Reserve Falcons"}` -> 0 hits across all pages
- `{"name": "Lincoln Northwest JV Reserve Falcons"}` (slash replaced by space) -> exact single hit
- Recovered `gc_uuid` for `public_id=yecaUcoSVpJa`: `ac053e2c-ee27-4f55-9b16-ed77c1bdfebb`

**Non-obvious Unicode trap**: GameChanger's index stores the **curly** apostrophe `'` (U+2019), not the straight form. Real production traffic uses the curly form (typed or auto-corrected), so names like "Kearney A's 10U" work in practice. But any call site constructing a query from a name source that uses a straight `'` (keyboard input, copy-paste from plain text, our own teams.name column if it was seeded from a straight-apostrophe source) hits the zero-hit failure. The failure is invisible -- the two apostrophe glyphs are visually identical in most fonts. This trap is the specific reason the fix is a defensive general normalization, not a narrow four-character list.

### Failure signature
Every tested character scored either 25 hits clean or 0 hits -- no partial-failure modes were observed. That means "first attempt returned zero hits" is a reliable gate for the retry: if the backend returns any hits on the first attempt, the name worked and the fallback is never needed.

### Why general normalization, not a four-character list
api-scout recommended broadening the fallback from slash-only to general punctuation-to-space normalization via `re.sub(r"[^\w ]+", " ", team_name, flags=re.UNICODE)` with whitespace collapse. Rationale:

- GC's query-parser behavior is opaque; our 14-character probe covers the obvious ASCII punctuation, but Unicode punctuation and characters we have not tested could exhibit the same failure.
- The failure signature (0 hits vs. 25) is distinctive and reliable. The zero-hits gate already suppresses unnecessary retries for working names.
- An explicit four-character list is brittle: future team names could introduce new failure chars we have not probed, and each new character discovered would require a patch.
- The cost of broadening is at most one extra API call per not-found name (we already paid this cost for the slash-only fallback shape). The benefit is that the next surprise character does not create a silent failure.

### Why narrow Unicode-aware regex, not ASCII-only
api-scout's follow-up probe (2026-04-17, 27 queries) confirmed:

- GC's backend **folds diacritics server-side**: `Kéarney A's 10U` (U+00E9) returns the canonical "Kearney A's 10U" hit on the first attempt. Accented-Latin names do not need normalization at all.
- CJK / non-Latin scripts are tokenized around by GC's indexer; they do not cause zero-hit failures when Latin tokens are also present.
- An aggressive ASCII-only regex (`[^A-Za-z0-9 ]+`) strips accented letters in the fallback path, which is both unnecessary (first attempt already succeeded for accent-bearing inputs) and risky (e.g., `Müller` -> `M ller` can collide with an unrelated indexed team, returning a false-positive match).
- A narrow Unicode-aware regex (`[^\w ]+` with explicit `re.UNICODE`) preserves accented letters and non-Latin scripts while still replacing punctuation. This matches GC's observed tolerance and eliminates the false-positive risk at the admin-UI path where an operator types an accented name.

Therefore TN-3 specifies the narrow form. `\w` includes the underscore `_`, which is acceptable -- underscores in real team names are rare and, if present, ride through the first attempt unchanged.

### Straight-vs-curly apostrophe anomaly (2026-04-17 re-probe)
api-scout's 2026-04-16 probe observed that a straight apostrophe (U+0027) in `{"name": "..."}` returned zero hits, while the 2026-04-17 re-probe found `"Kearney A's 10U"` (U+0027) returned one hit for the canonical team. Either GC's query-parser was updated between the two probe dates, or the 2026-04-16 failure was context-dependent (surrounding tokens mattered). The epic does not treat this as load-bearing -- the fallback remains a **defensive net** that handles any punctuation-induced zero-hit regardless of which specific character triggers it. The 4-char list (`/`, `'` U+0027, `%`, `#`) is retained as "historically observed + defensively covered," not as a claim of current GC behavior.

### Call sites affected
Four call sites in `src/` issue `POST /search` with `{"name": ...}`:

1. `src/reports/generator.py::_resolve_gc_uuid` (lines ~415-471) -- standalone report generation. **User-impact confirmed**: reports `o02avokZOgA5p8W6` and `fXQ5uCAP560GSBEE` (both 2026-04-15/16, Lincoln Northwest JV/Reserve Falcons) generated with zero spray rows across 13 completed games.
2. `src/gamechanger/resolvers/gc_uuid_resolver.py::_tier3_search` -- tracked team gc_uuid resolution cascade (Tier 3). Partially masked by `_strip_classification_suffix()`, which for "Lincoln Northwest JV/Reserve Falcons" produces "Lincoln Northwest Falcons" (slash removed as a side effect of stripping JV and Reserve). However, a name whose problem character is NOT inside a classification-suffix pair (e.g., a straight-apostrophe team name like "O'Connor Academy Varsity", or a `%`/`#` name) still hits the bug.
3. `src/gamechanger/crawlers/opponent_resolver.py::_search_resolve_opponent` -- auto-discovery of opponents during `_discover_opponents()` in `run_member_sync`. Sends raw `opponent_name` with no suffix stripping. **Same bug applies** -- punctuation-named opponents fail to auto-resolve and remain in the admin "needs resolution" queue indefinitely.
4. `src/api/routes/admin.py::_gc_search_teams` -- admin UI manual opponent search. Operator typing a name containing any problem character (typically a straight apostrophe from normal keyboard input) hits the bug.

### Why a shared helper
Patching each call site independently would duplicate the fallback logic four times and invite drift when the fifth caller appears. A single `search_teams_by_name()` helper in a new module (`src/gamechanger/search.py`) with the fallback built in:

- Enforces one canonical behavior across every call site.
- Collapses the duplicated `_SEARCH_CONTENT_TYPE` constant (currently defined in 4 files).
- Gives future callers a one-line entry point that already handles the punctuation edge case.

### Existing broken reports
Reports `o02avokZOgA5p8W6` and `fXQ5uCAP560GSBEE` are ephemeral (14-day expiry) and will either age out or be regenerated by the user after the fix lands. No data backfill is needed -- the reports flow is in-memory crawl-to-load, so rerunning `bb report generate <public_id>` after the fix will produce complete spray data. This is a post-dispatch manual step for the user, explicitly NOT in epic scope.

### Team-row gc_uuid for Lincoln Northwest JV/Reserve Falcons
The user may wish to check whether the team row for `public_id=yecaUcoSVpJa` already has a `gc_uuid` populated via another tier (e.g., Tier 1 boxscore extraction from an LSB member team that played them). If not, the first post-fix run of any affected pipeline will populate it. This is also a post-dispatch manual check, not an epic deliverable.

### Expert consultation
api-scout diagnosed the bug, probed the API with a 14-character test (2026-04-16), confirmed the punctuation-normalization workaround, and ran a 27-query follow-up probe (2026-04-17) that established GC's server-side diacritic folding and CJK tokenization behavior. Final fallback shape: first attempt unchanged; retry with `re.sub(r"[^\w ]+", " ", name, flags=re.UNICODE)` + whitespace collapse when first attempt returns zero hits AND name contains at least one `[^\w ]` character. code-reviewer consulted on AC exactness (10 findings incorporated); software-engineer consulted on pagination cost (Option A: caller-level short-circuit in `_resolve_gc_uuid`) and call-site coverage (adding a tier3 regression AC). No additional consultation required -- this is a mechanical code fix against a documented external API quirk.

### Forward-looking note: context-layer codification
Trigger #3 of the context-layer assessment gate (footgun / failure mode / boundary discovered) will fire at epic close -- `.claude/rules/gc-uuid-bridge.md` currently describes the bridge as a single `POST /search` call with no mention of the punctuation quirk or the shared helper. Codifying the quirk and pointing readers at `search_teams_by_name()` as the canonical entry point is a natural closure-time task for claude-architect via the assessment gate. Not an epic story -- the assessment exists precisely for this kind of post-code rule update.

## Goals
- Every `POST /search` by-team-name call site in `src/` transparently handles names containing punctuation via a shared normalization fallback.
- A shared helper in `src/gamechanger/search.py` is the single entry point for name-based team search; new callers use it automatically.
- The duplicated `_SEARCH_CONTENT_TYPE` constant is consolidated into the shared helper.
- Unit tests cover: no-punctuation behavior unchanged, punctuation-present with zero first-attempt hits triggers fallback, punctuation-present with non-zero first-attempt hits does NOT trigger fallback, fallback exhausted returns empty, the straight-vs-curly apostrophe Unicode trap is explicitly exercised, exact body strings and exact `start_at_page` values are asserted on both mocked calls, accented letters are preserved under the narrow Unicode-aware regex, and `_resolve_gc_uuid`'s pagination short-circuit bounds API cost at 2 calls per not-found lookup.

## Non-Goals
- Regenerating the two existing broken reports (`o02avokZOgA5p8W6`, `fXQ5uCAP560GSBEE`). The user can regenerate after the fix lands.
- Backfilling `gc_uuid` for the Lincoln Northwest JV/Reserve Falcons team row. Pipelines will populate on next run.
- Changing the `public_id` exact-match filter logic, pagination caps, or any other resolver behavior beyond the punctuation fallback.
- Any change to the three tiers of `gc_uuid_resolver.py`'s cascade (Tier 1 boxscore, Tier 2 progenitor) -- only the Tier 3 search call is touched.
- A broader refactor of the four resolver call sites (different return shapes, different filtering logic). Each call site keeps its existing post-search filtering; only the raw search step is centralized.
- Normalizing punctuation at write-time in the `teams.name` column or any other storage layer. The normalization is read-time only, applied at the API-call boundary.
- Updating `.claude/rules/gc-uuid-bridge.md` inside this epic. That codification is routed to claude-architect via the closure-time context-layer assessment gate.

## Success Criteria
- A single call to `search_teams_by_name(client, team_name)` returns hits for a punctuation-containing name that previously returned zero hits (verified against fixtures mimicking the confirmed API behavior for each of `/`, `'` (U+0027), `%`, and `#`).
- `_resolve_gc_uuid()` in `src/reports/generator.py` resolves `gc_uuid` for `public_id=yecaUcoSVpJa` (the Lincoln Northwest JV/Reserve Falcons case) using the helper -- verified by a regression test with mocked responses matching the confirmed probe output.
- The curly-apostrophe case (name stored with U+2019) is explicitly tested: the first attempt returns hits, the fallback does NOT fire, and the helper passes the curly-apostrophe name through unchanged. This protects against future regressions where someone "fixes" the helper to always normalize.
- Each of the four call sites delegates the raw `POST /search` step to the shared helper; no call site retains its own `_SEARCH_CONTENT_TYPE` constant or inline `client.post_json("/search", ...)` call.
- All existing tests in `tests/test_report_generator.py`, `tests/test_e211_report_generator.py`, `tests/test_gc_uuid_resolver.py`, `tests/test_crawlers/test_opponent_resolver.py`, and `tests/test_admin_resolve.py` pass after the call-site migration.
- No change to public behavior for punctuation-free team names -- first-attempt responses are returned unchanged.

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-225-01 | Shared search helper with punctuation-normalization fallback | TODO | None | - |
| E-225-02 | Migrate four call sites to shared helper | TODO | E-225-01 | - |

## Dispatch Team
- software-engineer

## Technical Notes

### TN-1: Helper contract
The new module `src/gamechanger/search.py` exposes one public function:

```
def search_teams_by_name(
    client: GameChangerClient,
    team_name: str,
    *,
    start_at_page: int = 0,
) -> list[dict]:
    """Return the `hits` list from POST /search for a team name query.

    start_at_page is a 0-indexed page offset passed through to POST /search
    as the "start_at_page" query param (GC's native paging key). The SAME
    start_at_page value is threaded to both the first attempt and the
    fallback attempt; the fallback never silently resets to page 0.

    If the first attempt with the raw name returns zero hits AND the name
    contains at least one `[^\\w ]` character (i.e., any character that is
    neither a Unicode word character nor a literal space), retries once
    with the name normalized: `[^\\w ]+` replaced by a single space, runs
    of whitespace collapsed to one space, leading and trailing whitespace
    stripped. Returns whatever hits the backend returns; callers apply
    their own downstream filtering (public_id match, season_year match,
    etc.).
    """
```

The helper does NOT paginate -- callers that need pagination (currently only `_resolve_gc_uuid`) invoke it per-page in a loop. This preserves existing pagination control at each call site and avoids changing page-size semantics during the migration.

### TN-2: Fallback trigger conditions
The normalization retry fires if and only if BOTH:

1. The first attempt returned zero hits (`len(hits) == 0`).
2. The name contains at least one character that is neither a Unicode word character (`\w`) nor a space (equivalent to: `re.search(r"[^\w ]", team_name, flags=re.UNICODE)` returns a match).

A name is called **gate-clean** when it contains no such character -- i.e., only Unicode word characters and spaces.

If the first attempt returned any hits, the helper returns those hits unchanged -- the fallback never runs. This preserves the current behavior for clean names exactly and avoids a second API call when the first succeeded. It also means a curly-apostrophe name (U+2019) that matches on the first attempt is passed through as-is; the normalization (which treats the curly apostrophe as punctuation) never runs on the successful path.

### TN-3: Normalization behavior
When the fallback fires, the name is transformed by:

1. Replace runs of one-or-more characters that are neither Unicode word characters nor spaces with a single space (regex: `re.sub(r"[^\w ]+", " ", name, flags=re.UNICODE)`).
2. Collapse runs of one-or-more whitespace characters into a single space (covers `\t`, `\n`, and other Unicode whitespace in addition to the literal space).
3. Strip leading and trailing whitespace.

The character class `[^\w ]` is deliberately Unicode-word-aware. Accented letters (`é`, `ñ`, `ü`), non-Latin scripts (CJK, Cyrillic), and Unicode digits are preserved. Only punctuation (including the curly apostrophe U+2019 and the straight apostrophe U+0027) is replaced by a space. This matches the confirmed behavior of GC's backend (2026-04-17 probe): the index folds diacritics server-side, so an accented-letter name succeeds on the first attempt and never reaches the fallback. Preserving accents in the rare case where the fallback does fire (punctuation + accents combined) gives GC its own folding to work with. `\w` includes the underscore `_`; team names containing a literal underscore ride through the first attempt unchanged in practice. The normalization is NOT a round-trippable transformation -- it is a lossy recovery used only after the raw-name attempt failed.

Exact output examples (these are AC-locked in Story 1):

| Input | Normalized output |
|-------|-------------------|
| `Lincoln Northwest JV/Reserve Falcons` | `Lincoln Northwest JV Reserve Falcons` |
| `Lincoln // JV  Team` | `Lincoln JV Team` |
| `Lincoln\tJV\nTeam` | `Lincoln JV Team` |
| `O'Connor Academy Varsity` (U+0027) | `O Connor Academy Varsity` |
| `Kearney A\u2019s 10U` (U+2019) | `Kearney A s 10U` |
| `Gonzàlez Varsity/JV` | `Gonzàlez Varsity JV` (accent preserved) |
| `///` | `` (empty string) |

### TN-4: Content type consolidation
The `_SEARCH_CONTENT_TYPE` module-level constant (`"application/vnd.gc.com.post_search+json; version=0.0.0"`) is defined once inside `src/gamechanger/search.py` and used exclusively by the helper. The four call-site files remove their local copies during Story 2.

### TN-5: Error handling
The helper does NOT catch `CredentialExpiredError` -- it propagates per the existing pattern at every call site. Other exceptions (network errors, `GameChangerAPIError`, rate limits) also propagate; each call site already has its own try/except wrapping the call and the helper should not swallow errors the callers are currently logging or propagating.

### TN-6: HTTP discipline
Both attempts (first + fallback) honor the shared `GameChangerClient` session, which already enforces headers, cookies, rate limiting, and timeouts per `.claude/rules/http-discipline.md`. No additional delay is added between the first attempt and the fallback beyond what the client already applies -- a single retry on an occasional edge case does not warrant a second delay.

### TN-7: Testing pattern
Per `.claude/rules/testing.md`, tests mock at the HTTP layer (the `client.post_json` method). Test data matches the authoritative probe output:

- The user-impact case: a hit with `result.public_id == "yecaUcoSVpJa"`, `result.id == "ac053e2c-ee27-4f55-9b16-ed77c1bdfebb"`, `result.name == "Lincoln Northwest JV/Reserve Falcons"`.
- The mock distinguishes calls by inspecting the `body` argument: it returns `{"hits": []}` when the body's `name` contains any `[^\w ]` character, else the matching hit payload. This lets a single mock verify both "first attempt hits zero" and "normalized attempt finds match".
- **Exact-string assertions are required.** Wherever an AC describes "calls with the normalized name" (Story 1 AC-3, AC-5, AC-7; Story 2 AC-5, AC-6), the test MUST assert the literal body string on each mocked call: e.g., `mock_post_json.call_args_list[0].kwargs["body"]["name"] == "Lincoln Northwest JV/Reserve Falcons"` and `mock_post_json.call_args_list[1].kwargs["body"]["name"] == "Lincoln Northwest JV Reserve Falcons"`. Asserting resolution alone is insufficient -- a helper that ignores the gate and always normalizes would pass resolution-only tests.

### TN-8: Unicode apostrophe trap -- explicit coverage
Two test cases cover the U+0027 vs. U+2019 distinction and document the trap in-code (tests are executable documentation):

1. **Straight-apostrophe name, fallback recovers**: a name like `"O'Connor Academy Varsity"` (with U+0027) returns zero hits on first attempt; the fallback normalizes it to `"O Connor Academy Varsity"` and recovers a canonical match. Asserts the fallback fired and returned the matching hit.
2. **Curly-apostrophe name, fallback does NOT fire**: a name like `"Kearney A\u2019s 10U"` (with U+2019) returns hits on first attempt; the fallback never fires. Asserts only one `post_json` call occurred and the hits returned are the first-attempt payload.

A comment at the test-module level explains the GC-side storage convention (curly is canonical) so future readers understand why case 2's mock returns hits for the curly form but not for any normalized form.

### TN-9: Call-site filtering preserved
Each of the four call sites retains its own post-search filtering (`public_id` exact match, `name.lower() == opponent_name.lower()`, season year match, etc.). The shared helper does not do filtering. The raw `team_name` passed into the helper is also the name used by the caller's filter -- the caller's filter sees the original (pre-normalization) name unchanged. The helper's normalization transformation is transparent to the caller.

Note: a caller that matches on `name.lower() == opponent_name.lower()` already compares against `hit.result.name` from the API response. The response name reflects GC's canonical storage (e.g., curly apostrophe). The caller's filter will therefore not match a name constructed locally with a straight apostrophe, even after the helper recovers hits via normalization. This is a pre-existing edge case in the caller's filter logic, not introduced by this epic. If it becomes a problem in practice, the caller should normalize both sides of the comparison -- but that is out of epic scope.

### TN-9a: Multi-page fallback semantics
Each page invocation of the helper is independent. If the fallback fires on page 0 and returns hits, subsequent pages (1+) still use the raw name; there is no cross-page memoization of "use normalized form." In practice this is not reached because:

- For names that return a canonical single match (the common case), `len(hits) < _SEARCH_PAGE_SIZE` on page 0 after the fallback, and the caller's short-circuit terminates the loop.
- Story 2 adds an explicit caller-level short-circuit in `_resolve_gc_uuid`: if page 0's raw attempt returns zero hits AND the name is not gate-clean, the caller breaks out of raw-name pagination (the helper's fallback on page 0 runs; subsequent pages are not attempted with the raw name). This bounds the worst-case API cost at 2 calls per not-found paginated lookup (one raw, one normalized on page 0) instead of 10 (5 raw attempts each firing their own normalized retry).

### TN-10: `_gc_search_teams` shape preservation
The admin UI helper `_gc_search_teams` normalizes hits into flat dicts with `name`, `gc_uuid`, `public_id`, `city`, etc. (see `src/api/routes/admin.py` lines 2815-2844). That normalization stays in place; only the raw `client.post_json` call is replaced by a call to `search_teams_by_name`.

### TN-11: Edge cases
Defined behavior for pathological inputs, so the implementer does not need to invent policy:

- **Name is exactly `"/"` or other single punctuation**: first attempt returns zero hits, fallback transforms to `""` (empty), which the backend returns zero hits for. Net: empty list. No crash.
- **Name is all punctuation (e.g., `"///"`)**: same as above. Normalization collapses to `""`. No crash.
- **Name contains only non-ASCII Unicode word characters (e.g., an all-katakana team name)**: first attempt is sent as-is; because `\w` matches Unicode word characters, the name is gate-clean and the fallback never fires. Net: whatever hits the first attempt produced (possibly empty). This is correct -- GC tokenizes around non-Latin scripts, so the first attempt is the only meaningful recovery path.
- **Empty string**: first attempt is sent with empty name; backend returns zero hits; gate condition is false (empty string contains no `[^\w ]` character); helper returns empty list after one call.
- **Whitespace-only name (tabs, newlines, spaces)**: `\t` and `\n` are not word characters and not literal spaces, so the gate matches them. First attempt returns zero hits; normalization produces `""`; fallback returns empty list. No crash.
- **`None` input**: Not defended. All four call sites pass `str`-typed names (schema NOT NULL columns, FastAPI form validation, schedule-response fields). If `None` arrives, the helper raises `TypeError` loudly from `re.search` -- that is a caller bug, not a helper concern.

## Open Questions
None. Bug is fully diagnosed and fix shape is confirmed by api-scout's 14-character probe.

## History
- 2026-04-16: Created. Scope set at 2 stories (shared helper + 4-site migration) based on four confirmed callers of the same broken API pattern. Initial shape: slash-to-space fallback only.
- 2026-04-16: Revised. api-scout probed 14 characters and found four confirmed-problem characters (`/`, `'` U+0027, `%`, `#`) plus a Unicode apostrophe trap (U+0027 vs. U+2019). Fallback broadened from slash-to-space to general punctuation normalization. Goals, non-goals, success criteria, and Technical Notes updated. Story titles and ACs revised.
- 2026-04-17: Triaged combined Codex spec-review + internal team review findings. api-scout re-probed (27 queries) and recommended narrowing the regex from `[^A-Za-z0-9 ]+` (aggressive, ASCII-only) to `[^\w ]+` with `re.UNICODE` (narrow, Unicode-aware) -- diacritics fold server-side, so accented-letter names never reach the fallback; preserving them when they do reach it is safer. software-engineer recommended Option A for pagination cost: caller-level short-circuit in `_resolve_gc_uuid`. code-reviewer identified 10 AC refinements (6 must-fix for exactness/proof, 4 polish). TN-2, TN-3, TN-7, TN-9, TN-9a (new), TN-11 updated; Story 1 ACs tightened for exact-string assertions and signature lock-in; Story 2 ACs tightened with short-circuit AC, tier3 regression AC, and trigger-char swap for opponent-resolver regression to sidestep the curly-vs-straight apostrophe filter edge case.
- 2026-04-17: Status moved DRAFT -> READY after review scorecard below cleared. Review scorecard:

  | Review round | Findings raised | Accepted | Dismissed | Outcome |
  |--------------|-----------------|----------|-----------|---------|
  | Internal team review (iteration 1) | ~8 (approx.) | ~8 | 0 | Incorporated: regex narrowing (TN-3), pagination short-circuit Option A (TN-9a + Story 2 AC-1a), tier3 compositional regression (Story 2 AC-7), opponent-resolver trigger-char swap (Story 2 AC-6). |
  | Codex spec review (iteration 1) | ~10 (approx.) | ~8 | ~2 | Incorporated: exact-string body assertions on both mocked calls (Story 1 AC-3/5/7/8, Story 2 AC-5/6/7), signature lock-in via `inspect.signature` (Story 1 AC-1), multi-word gate negative regression (Story 1 AC-10), exact normalization output lock (Story 1 AC-11), grep verification of migration completeness (Story 2 AC-9). Dismissed 2 findings per prior PM triage (specifics not reconstructable from History -- best-effort approximation). |
  | Consistency sweep | n/a | n/a | n/a | Spot-checked 2026-04-17 by replacement PM: Stories table (IDs, deps, status) aligns with both story files; TN-N references in Story 1 (TN-1/2/3/4/5/7/8/11) and Story 2 (TN-1/4/7/8/9/9a/10) all resolve to sections present in epic.md; no dangling references. |

  Counts are reconstructed from the incorporation record in earlier History entries. Exact per-round raise counts could not be reconstructed from the artifacts present and are marked approximate.
