# E-125: Full-Project Code Review Remediation

## Status
`COMPLETED`

## Overview
Remediate all Critical and Important findings from the 4-session full-project code review (2026-03-17). This is the highest-priority remediation epic: the project has no CSRF protection, a SQL injection surface, plaintext magic link tokens, a Docker container running as root, a broken OBP formula that misinforms coaching decisions, and multiple correctness bugs. Loader stat population gaps (review 02 C-1/C-2/I-4/I-9) are already covered by E-117 and excluded here.

## Background & Context
Four independent code-reviewer sessions (each with full 1M context) reviewed the entire codebase on 2026-03-17. Review reports are at:
- `reviews/01-client-auth-http.md` (client, auth, HTTP layer)
- `reviews/02-crawlers-loaders-pipeline.md` (crawlers, loaders, pipeline)
- `reviews/03-web-app-cli.md` (web app, CLI)
- `reviews/04-data-safety-infrastructure.md` (data layer, safety, infrastructure)

User directive: "Having CSRF and SQL injection stuff going on when we're doing code reviews is rather unacceptable." and "Do not take Cloudflare as the mitigation for missing CSRF. Unless there's a reason to skip it."

The code-reviewer agent has already been hardened with a security checklist (context-layer change by CA). That is done and does not need a story.

Expert consultations completed:
- **baseball-coach** (OBP formula, E-125-03): Confirmed `(H + BB + HBP) / (AB + BB + HBP + SF)` is correct at all levels (MLB, NCAA, NFHS). Column names verified: `hbp` and `shf` in `player_season_batting`. MUST HAVE: COALESCE NULLs to 0; guard against zero denominator.
- **data-engineer** (FK enforcement, E-125-04): Confirmed `executescript()` FK enforcement is unreliable in Python's sqlite3 module. Prepending `PRAGMA foreign_keys=ON;\n` to the SQL string is the correct fix. No existing FK violations in seed data. Very low risk.

## Goals
- Eliminate all SQL injection surfaces
- Add CSRF protection to all state-mutating POST endpoints
- Hash magic link tokens before storage (consistent with session token handling)
- Fix the OBP formula so coaching decisions are based on correct data
- Run the Docker production container as a non-root user
- Fix all correctness bugs (broken links, FK enforcement, rate limit crash, connection leaks)
- Clean up security hygiene issues (hardcoded UUIDs, XSS risk, pagination URL validation)

## Non-Goals
- Loader stat population gaps (covered by E-117)
- DRY refactoring of duplicated helpers (review 02 I-3, review 03 #11/#13 -- valuable but not security/correctness; future epic)
- Code style / convention issues (`from __future__ import annotations` gaps, type annotation fixes, local imports) -- too minor for dedicated stories
- Passkey challenge store process-safety (review 03 #6 -- latent issue, single-worker deployment, no active bug)
- Login rate limiting (review 03 #10 -- Cloudflare Zero Trust provides this at the network layer)
- Tailwind CDN replacement (review 03 #19 -- pre-production optimization)
- Dashboard code duplication refactor (review 03 #11 -- maintenance, not correctness)
- Dead code cleanup in signing.py (review 01 C-1 -- no functional impact, low priority)
- `format_avg` None handling (review 03 #7 -- COALESCE prevents None from reaching it)
- Passkey unbounded challenge stores (review 03 #8 -- low severity at current scale)

## Success Criteria
- Zero SQL injection surfaces: all SQL uses parameterized queries exclusively
- All POST endpoints validate a CSRF token; JS-initiated POSTs include CSRF token via header or compatible transport
- Mutating GET endpoints are converted to POST with CSRF (logout) or documented as excluded with rationale (verify)
- Magic link tokens are hashed (SHA-256) before database storage, verified by hash comparison
- OBP formula includes HBP and SF in all dashboard templates
- Docker production container runs as a non-root user
- Broken `/dashboard/stats` backlinks return valid navigation
- `executescript()` calls enforce foreign keys
- `int(Retry-After)` cannot crash on non-integer values
- Backup connections are properly closed on error
- No hardcoded real UUIDs in committed scripts
- No `|safe` filter on user-influenced JSON
- Pagination follows only same-host URLs
- All existing tests pass after all changes

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-125-01 | CSRF protection for all POST endpoints | DONE | None | se-01 |
| E-125-02 | SQL injection fix + magic link token hashing | DONE | E-125-01 | se-02 |
| E-125-03 | OBP formula correction + broken backlink fix | DONE | None | se-03 |
| E-125-04 | Docker non-root user + executescript FK enforcement | DONE | None | se-04 |
| E-125-05 | HTTP client hardening (rate limit crash, pagination validation, XSS) | DONE | E-125-01 | se-05 |
| E-125-06 | Security hygiene (hardcoded UUIDs, backup connection, pii_scanner sys.path, stale .env.example) | DONE | None | se-06 |
| E-125-07 | Claude hooks PII scanner invocation update | DONE | None | ca-07 |

## Dispatch Team
- software-engineer (E-125-01 through E-125-06)
- claude-architect (E-125-07)

**Routing note:** E-125-01 through E-125-06 are Python implementation, test writing, and infrastructure fixes -- SE is correct per the routing table. E-125-07 modifies `.claude/hooks/pii-check.sh` (context-layer file) and must route to claude-architect per the routing precedence rule.

## Technical Notes

### TN-1: CSRF Implementation Approach

FastAPI does not include CSRF middleware. The standard approach for server-rendered Jinja2 forms is:
1. Generate a per-session CSRF token (stored in the session or a separate signed cookie)
2. Include the token as a hidden field in every `<form>` that uses POST
3. Validate the token server-side on every POST request via middleware
4. Reject requests with missing or invalid tokens (403 response)

The `SameSite=lax` cookie attribute already set on session cookies provides partial defense but does NOT protect against cross-origin POST form submissions. CSRF tokens are defense-in-depth.

Libraries to consider: `starlette-csrf`, `fastapi-csrf-protect`, or a minimal custom middleware. The implementing agent should choose the simplest approach that covers all POST routes.

### TN-2: Magic Link Token Hashing

The session token path already uses `hash_token()` (SHA-256) in `src/api/auth.py:96`. Magic link tokens should follow the same pattern:
- Hash the token before INSERT into `magic_link_tokens`
- On verification (`/auth/verify?token=X`), hash the incoming token and look up by hash
- This is the same pattern used for session tokens -- no new crypto needed

### TN-3: OBP Formula

Correct OBP: `(H + BB + HBP) / (AB + BB + HBP + SF)`

Current (wrong): `(H + BB) / (AB + BB)`

This affects four templates:
- `src/api/templates/dashboard/team_stats.html`
- `src/api/templates/dashboard/opponent_detail.html`
- `src/api/templates/dashboard/player_profile.html` (two occurrences)

The dashboard DB queries (`src/api/db.py`) must also be updated to SELECT `hbp` and `shf` columns so the template has access to them.

### TN-4: executescript() FK Enforcement

SQLite's `executescript()` issues an implicit COMMIT and resets connection state, so `PRAGMA foreign_keys=ON` set before the call has no effect. The fix is to include `PRAGMA foreign_keys=ON;` as the first statement inside the SQL string passed to `executescript()`, or to switch to `execute()` with individual statements.

Affected files:
- `migrations/apply_migrations.py` (line ~130)
- `src/db/reset.py` (line ~130)
- `scripts/seed_dev.py` (line ~108)

### TN-5: E-117 Overlap

Review 02 findings C-1, C-2, I-4, and I-9 (game_loader and season_stats_loader skipping stats that have schema columns) are fully covered by E-117 (Loader Stat Population). E-125 does NOT duplicate those stories. If E-117 is dispatched first, those findings will be resolved. If E-125 is dispatched first, those findings remain open until E-117 ships.

### TN-6: Pagination URL Validation

`src/gamechanger/client.py` line ~333: the `x-next-page` header value replaces the URL entirely. Validate that the parsed URL's host matches `self._base_url`'s host before following. Reject with a warning log if the host differs.

### TN-7: XSS via |safe Filter

`src/api/templates/auth/passkey_register.html:32` uses `{{ options_json | safe }}` to embed WebAuthn options JSON. The `user_display_name` field (set from user email) could contain HTML injection characters. Replace `|safe` with a Jinja2-safe JSON embedding pattern (e.g., `{{ options_json | tojson }}` or base64-encode and decode in JS).

### TN-8: File Overlap and Sequencing Note

**Source file overlaps** (non-overlapping sections, parallel-safe with trivial merge conflicts):
- `src/api/templates/auth/passkey_register.html`: E-125-01 (CSRF hidden field + JS token transport) and E-125-05 (`|safe` filter replacement in script block).
- `src/api/routes/auth.py`: E-125-01 (CSRF token context, logout route change) and E-125-02 (magic link INSERT/verify hashing).

**Test file overlap** (requires sequencing):
- `tests/test_auth_routes.py`: E-125-01, E-125-02, and E-125-05 all modify this file. E-125-01 should merge first because CSRF changes require all auth test POSTs to include CSRF tokens -- every subsequent story touching this test file must build on E-125-01's test fixtures. Dispatch E-125-02 and E-125-05 in a second wave after E-125-01 merges, or expect non-trivial merge conflicts in test fixtures.

### TN-9: OBP Consultation Findings (baseball-coach)

The correct OBP formula at all levels (MLB, NCAA, NFHS) is `(H + BB + HBP) / (AB + BB + HBP + SF)`. Schema columns: `hbp` (INTEGER, nullable) and `shf` (INTEGER, nullable) in `player_season_batting`. Key requirements:
- **MUST**: COALESCE NULL `hbp` and `shf` to 0 in both DB queries and template calculations. NULL means "not reported," not "zero events." A NULL must never propagate to make the entire OBP NULL.
- **MUST**: Guard against zero denominator `(AB + BB + HBP + SF) = 0` -- display "—" or omit, never 0.000 or division error.
- **Confirmed**: SLG formula is already correct; only OBP needs fixing.

### TN-10: FK Enforcement Consultation Findings (data-engineer)

The `executescript()` FK enforcement issue is real in spirit even if the mechanism description is imprecise. Python's `sqlite3.executescript()` uses `sqlite3_exec()` internally and FK enforcement is unreliable through this path. Fix: prepend `PRAGMA foreign_keys=ON;\n` to SQL strings before `executescript()`. Three production call sites: `apply_migrations.py:130`, `src/db/reset.py:130`, `scripts/seed_dev.py:108`. No existing FK violations in seed data -- insertion order is correct. Test fixtures also use `executescript()` and should be fixed for consistency (lower priority). The `executescript()` atomicity limitation (auto-commit makes rollback ineffective) is noted but out of scope for E-125.

## Open Questions
- None. All findings have clear fixes.

## History
- 2026-03-17: Created from 4-session full-project code review. Grouped findings into 6 stories by domain. E-117 overlap noted and excluded. Set to READY.
- 2026-03-17: Codex spec review triage. Incorporated baseball-coach (OBP formula) and data-engineer (FK enforcement) consultations. Expanded E-125-01 for mutating GETs and JS CSRF transport. Added E-125-07 (CA) for `.claude/hooks/pii-check.sh`. Updated TN-8 with test file overlap sequencing. Expanded E-125-03 with NULL handling ACs. Expanded E-125-06 AC-5 for both stale `.env.example` references. Re-verified READY.
- 2026-03-17: COMPLETED. All 7 stories DONE. Two-wave dispatch: wave-1 (E-125-01, 03, 04, 06, 07 parallel), wave-2 (E-125-02, 05 after E-125-01 merged). E-125-01 AC-7 failed initial verification (7 dashboard logout links still GET after route converted to POST) -- fixed and re-verified. Key deliverables: CSRF middleware (double-submit cookie, pure ASGI), SQL injection elimination, magic link token hashing, OBP formula correction, Docker non-root user, executescript FK enforcement, HTTP client hardening (Retry-After, pagination validation, XSS), security hygiene cleanup. ~25 new tests added across stories.

### Documentation Assessment
- Trigger 1 (new feature/endpoint): YES -- CSRF middleware is a new feature, logout converted from GET to POST.
- Trigger 2 (architecture/deployment change): YES -- Docker non-root user changes production deployment (data directory ownership).
- Trigger 3 (agent modification): No.
- Trigger 4 (schema change): No.
- Trigger 5 (changes how system works/user interaction): YES -- logout is now POST (coaches see a button instead of a link), CSRF tokens required on all forms.
- **Verdict**: docs-writer dispatch needed. Affected docs: `docs/admin/` (deployment runbook re: non-root user, data dir ownership), `docs/production-deployment.md` if it exists.

### Context-Layer Assessment
1. **New convention/pattern/constraint**: NO -- CSRF, parameterized SQL, and token hashing are standard security practices, not project-specific conventions. No new naming or file organization rules.
2. **Architectural decision with ongoing implications**: NO -- CSRF middleware and double-submit cookie pattern are implementation details, not architectural decisions that change how future epics are planned. The CSRF token inclusion in forms/JS is mechanical.
3. **Footgun/failure mode/boundary discovered**: YES -- The `executescript()` FK enforcement gotcha (PRAGMA resets across executescript boundaries) is a real footgun that future migration or seed work could trip over. Also, the `|safe` filter XSS risk in Jinja2 templates is worth noting.
4. **Change to agent behavior/routing/coordination**: NO -- E-125-07 updated `.claude/hooks/pii-check.sh` invocation but the hook behavior is unchanged (same scanner, same deny/allow logic).
5. **Domain knowledge for future epics**: NO -- OBP formula is standard baseball knowledge, not a project-specific discovery.
6. **New CLI command/workflow/operational procedure**: NO -- No new commands or workflows.
- **Verdict**: Trigger 3 fires. claude-architect dispatch recommended to codify the `executescript()` FK gotcha and `|safe` XSS risk as a rule or CLAUDE.md note.

### Ideas Backlog Review
No CANDIDATE ideas are newly unblocked by E-125. This epic was security/correctness remediation with no new capabilities or data model changes that would unblock existing ideas.

### Vision Signals
24 unprocessed signals exist in `docs/vision-signals.md` (accumulated since 2026-03-07). No new signals generated by E-125 (security remediation, no vision-relevant work). The backlog is substantial -- worth mentioning to the user at a natural pause.
