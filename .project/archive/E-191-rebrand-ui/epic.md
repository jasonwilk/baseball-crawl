# E-191: Rebrand User-Facing UI from "LSB Baseball" to "Baseball Stats"

## Status
`COMPLETED`
<!-- Lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED) -->

## Overview
Replace "LSB Baseball" and "Lincoln Standing Bear" with the generic brand "Baseball Stats" in the 17 inventoried in-scope items across 14 files (see Brand Replacement Map in Technical Notes) so that public-facing pages do not identify the school. This is a privacy-motivated cosmetic change -- no functional behavior changes.

## Background & Context
The app currently displays "LSB Baseball" and "Lincoln Standing Bear" on login pages, nav headers, email messages, error pages, passkey registration, and the FastAPI description. The user wants these replaced with "Baseball Stats" so that anyone visiting the public URL cannot identify which school the app serves.

A full-codebase inventory was conducted (2026-03-30) covering 8 categories of references. The user chose to change **categories 1-3 only** (public pages, authenticated UI, backend/API). Categories 4-8 are explicitly deferred -- the full inventory is preserved in Technical Notes for future reference.

**Expert consultation completed:**
- **UXD**: Confirmed "Baseball Stats" works across all touchpoints. No layout concerns. Noted `base.html` line 6 default title is already "Baseball Dashboard" (no change needed).
- **CA**: Confirmed context-layer exclusion is correct. LSB references in CLAUDE.md and agent definitions serve as domain grounding and should not be genericized.

## Goals
- Remove the school name from the 17 inventoried in-scope items (see Brand Replacement Map in Technical Notes for the exhaustive list)
- Establish "Baseball Stats" as the public-facing brand

## Non-Goals
- Changing config/seed data (`config/teams.yaml`, `migrations/001_initial_schema.sql`)
- Changing context-layer files (CLAUDE.md, agent definitions, rules, agent memory)
- Changing test fixture data
- Changing documentation or archived epics
- Changing code comments or docstrings
- Changing admin form placeholders (`programs.html`) -- operator-only, not privacy-sensitive

## Success Criteria
- All 17 inventoried in-scope items are updated to use "Baseball Stats" (or generic equivalent for the FastAPI description)
- No occurrence of "LSB Baseball" or "Lincoln Standing Bear" remains in the 14 in-scope files
- Existing tests pass without modification (brand strings are not asserted in tests for these surfaces)

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-191-01 | Replace brand strings in templates, email, and API config | DONE | None | - |

## Dispatch Team
- software-engineer

## Technical Notes

### Brand Replacement Map (In-Scope -- Categories 1-3)

All replacements are literal string substitutions except the FastAPI description which is a rewrite:

| # | Current String | Replacement | File | Location |
|---|---------------|-------------|------|----------|
| 1 | `Log In — LSB Baseball` | `Log In — Baseball Stats` | `src/api/templates/auth/login.html:4` | `<title>` tag |
| 2 | `Log in to LSB Baseball` | `Log in to Baseball Stats` | `src/api/templates/auth/login.html:9` | `<h1>` heading |
| 3 | `Check Your Email — LSB Baseball` | `Check Your Email — Baseball Stats` | `src/api/templates/auth/check_email.html:3` | `<title>` tag |
| 4 | `Login Link Expired — LSB Baseball` | `Login Link Expired — Baseball Stats` | `src/api/templates/auth/verify_error.html:3` | `<title>` tag |
| 5 | `Register Passkey — LSB Baseball` | `Register Passkey — Baseball Stats` | `src/api/templates/auth/passkey_register.html:3` | `<title>` tag |
| 6 | `Register Your Device — LSB Baseball` | `Register Your Device — Baseball Stats` | `src/api/templates/auth/passkey_prompt.html:3` | `<title>` tag |
| 7 | `Passkey Registration Failed — LSB Baseball` | `Passkey Registration Failed — Baseball Stats` | `src/api/templates/auth/passkey_error.html:3` | `<title>` tag |
| 8 | `LSB Baseball` (default title) | `Baseball Stats` | `src/api/templates/base_auth.html:6` | Default `<title>` |
| 9 | `LSB Baseball` (nav brand) | `Baseball Stats` | `src/api/templates/base_auth.html:12` | Nav `<span>` |
| 10 | `LSB Baseball` (nav brand) | `Baseball Stats` | `src/api/templates/base.html:12` | Nav `<span>` |
| 11 | `403 Forbidden — LSB Baseball` | `403 Forbidden — Baseball Stats` | `src/api/templates/errors/forbidden.html:3` | `<title>` tag |
| 12 | `Server Error — LSB Baseball` | `Server Error — Baseball Stats` | `src/api/templates/errors/500.html:3` | `<title>` tag |
| 13 | `Page Not Found — LSB Baseball` | `Page Not Found — Baseball Stats` | `src/api/templates/errors/404.html:3` | `<title>` tag |
| 14 | `Your login link for LSB Baseball` | `Your login link for Baseball Stats` | `src/api/email.py:22` | Email subject |
| 15 | `log in to LSB Baseball` | `log in to Baseball Stats` | `src/api/email.py:51` | Email body |
| 16 | `LSB Baseball` (rp_name) | `Baseball Stats` | `src/api/routes/auth.py:561` | Passkey `rp_name` |
| 17 | `Lincoln Standing Bear High School` | Remove school name, keep purpose (e.g., "High school baseball coaching analytics platform.") | `src/api/main.py:81` | FastAPI description |

### Files Modified (14 files)

**Auth templates** (6 files):
- `src/api/templates/auth/login.html` (2 changes: title + h1)
- `src/api/templates/auth/check_email.html` (1 change)
- `src/api/templates/auth/verify_error.html` (1 change)
- `src/api/templates/auth/passkey_register.html` (1 change)
- `src/api/templates/auth/passkey_prompt.html` (1 change)
- `src/api/templates/auth/passkey_error.html` (1 change)

**Base layouts** (2 files):
- `src/api/templates/base_auth.html` (2 changes: title + nav)
- `src/api/templates/base.html` (1 change: nav only; default title is already "Baseball Dashboard")

**Error templates** (3 files):
- `src/api/templates/errors/forbidden.html` (1 change)
- `src/api/templates/errors/500.html` (1 change)
- `src/api/templates/errors/404.html` (1 change)

**Python source** (2 files):
- `src/api/email.py` (2 changes: subject + body)
- `src/api/main.py` (1 change: description)

**Python source -- auth** (1 file):
- `src/api/routes/auth.py` (1 change: rp_name)

### Title Naming Note

The `base.html` default title "Baseball Dashboard" is intentionally different from the `base_auth.html` default title "Baseball Stats". The dashboard title describes function (what the page does); the auth title is brand identity (what the app is called). Both are correct and no change is needed to `base.html` line 6.

### Passkey rp_name Note

Changing `rp_name` does NOT invalidate existing passkeys -- `rp_name` is a display label only. The `rp_id` (domain) is what matters for passkey validity, and that is not changing.

### Dependent Epic AC Updates (Required Before Dispatch)

E-178 and E-181 are READY and contain ACs that reference "LSB Baseball":
- `epics/E-178-terminology-cleanup/E-178-01-replace-team-page-jargon.md:55` -- AC-20: `"Access Denied — LSB Baseball"`
- `epics/E-178-terminology-cleanup/epic.md:135` -- terminology mapping table
- `epics/E-181-auto-sync-experience-polish/E-181-03-dashboard-polish.md:29` -- AC-8: `"Welcome to LSB Baseball."`
- `epics/E-181-auto-sync-experience-polish/epic.md:105` -- welcome heading spec

These ACs MUST be updated to use "Baseball Stats" via a clarify pass **before** E-178 or E-181 are dispatched. If E-191 ships first, dispatching those epics with the old brand strings would reintroduce the school name. The PM will perform the clarify pass after E-191 is marked READY.

### Full Codebase Inventory (Deferred Categories 4-8)

The following categories were inventoried but explicitly deferred by the user. Preserved here for future reference.

#### Category 4: Config/Seed Data (DEFERRED)

| File | Line | String | Context |
|------|------|--------|---------|
| `migrations/001_initial_schema.sql` | 33 | `Lincoln Standing Bear HS` | SQL comment |
| `migrations/001_initial_schema.sql` | 35 | `lsb-hs` | SQL comment |
| `migrations/001_initial_schema.sql` | 36 | `Lincoln Standing Bear HS` | Column doc comment |
| `migrations/001_initial_schema.sql` | 509 | `('lsb-hs', 'Lincoln Standing Bear HS', 'hs', 'Lincoln Standing Bear')` | Seed INSERT |
| `config/teams.yaml` | 1 | `Lincoln Standing Bear High School` | File header comment |
| `config/teams.yaml` | 7 | `LSB` | Comment |
| `config/teams.yaml` | 18 | `LSB` | Comment |
| `config/teams.yaml` | 21-34 | `REPLACE_WITH_LSB_*_TEAM_ID`, `Lincoln Standing Bear *` | Placeholder IDs + team names (8 items) |

**Note**: The `lsb-hs` program seed in the migration is the root source for production DB. Changing it would require a new migration and cascading test fixture updates.

#### Category 5: Code Internals (DEFERRED)

| File | Line | String | Context |
|------|------|--------|---------|
| `src/api/db.py` | 1231 | `LSB` | Docstring |
| `src/gamechanger/config.py` | 72 | `LSB` | Docstring |
| `src/gamechanger/crawlers/roster.py` | 44 | `LSB` | Docstring |
| `src/gamechanger/crawlers/schedule.py` | 45 | `LSB` | Docstring |
| `src/gamechanger/crawlers/player_stats.py` | 45 | `LSB` | Docstring |

#### Category 6: Context Layer (DEFERRED -- CA recommends no change)

~30+ references across CLAUDE.md, 5 agent definitions, 1 rule, and 6 agent memory directories. All serve as factual domain grounding for agents. CA assessed that genericizing these would remove useful signal.

#### Category 7: Tests (DEFERRED)

~200+ occurrences across 28 test files. All are fixture data (`'lsb-hs'` program seeds, `'LSB Varsity'`/`'LSB JV'` team names). One exception: `test_migrations.py:236` asserts the seed row contains "Lincoln Standing Bear".

#### Category 8: Docs/Archive (DEFERRED)

~50+ occurrences across `docs/VISION.md`, `docs/coaching/`, `docs/admin/`, `.project/ideas/`, `.project/archive/`, `.project/research/`.

## Open Questions
- **E-178/E-181 clarify pass**: PM must update ACs in E-178 and E-181 to replace "LSB Baseball" with "Baseball Stats" before those epics are dispatched. Tracked in Technical Notes under "Dependent Epic AC Updates."

## History
- 2026-03-30: Created. Full-codebase inventory conducted (58 items, 8 categories). User selected categories 1-3 (17 items across 14 files). UXD and CA consulted. Categories 4-8 deferred with full inventory preserved.
- 2026-03-30: Internal review iteration 1. 6 findings accepted (file count 13->14, DoD clarification, AC robustness, admin placeholder rationale, title naming note), 3 dismissed (duplicates/informational). Consistency sweep completed.
- 2026-03-30: Codex spec review iteration 1. 2 findings accepted (scope overclaim narrowed, E-178/E-181 clarify pass strengthened). Consistency sweep completed.
- 2026-03-30: Codex spec review iteration 2. 1 finding accepted (scope language further tightened from "categories 1-3 surfaces" to "17 inventoried in-scope items across 14 files"). Consistency sweep completed.
- 2026-03-30: Set to READY after 4 review passes.
- 2026-03-30: COMPLETED. All 17 brand string replacements applied across 14 files. "LSB Baseball" and "Lincoln Standing Bear" removed from all public-facing UI surfaces (auth templates, error pages, base layouts, email, passkey config, FastAPI description). Zero findings across CR and Codex code review. No ideas unblocked. 26+ unprocessed vision signals exist (pre-existing, advisory). Open question remains: PM must perform E-178/E-181 clarify pass to update dependent ACs before those epics are dispatched.

### Spec Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 -- CR spec audit | 4 | 4 | 0 |
| Internal iteration 1 -- Holistic team (PM + UXD + CA) | 5 | 2 | 3 |
| Codex iteration 1 | 2 | 2 | 0 |
| Codex iteration 2 | 1 | 1 | 0 |
| **Total** | **12** | **9** | **3** |

Note: Some findings were duplicates across reviewers (e.g., file count found by CR, CA, UXD, and PM). The counts above are deduplicated by unique finding.

### Code Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Per-story CR -- E-191-01 | 0 | 0 | 0 |
| CR integration review | 0 | 0 | 0 |
| Codex code review | 0 | 0 | 0 |
| **Total** | **0** | **0** | **0** |
