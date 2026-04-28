# E-231: Matchup visual polish + print hardening

## Status
`DRAFT`

## Overview
After E-228 v1 ships and a coach has used the matchup report in print form + mobile form + verified ergonomics in real game-prep workflow, this epic hardens the rendered output. Adds the AVOID inline sub-bullet typography (7pt small caps prefix, indented sub-bullet, B&W print survival), the full visual hierarchy spec (font sizes/weights per element), print stylesheet hardening (`break-inside: avoid` per sub-section AND per-hitter, page-break rules), mobile responsive at 375px viewport, and the byte-identical baseline-fixture regression machinery (substitution scheme + regen script + checked-in fixture).

## Background & Context
E-228 v1 (2026-04-28 refinement) cut the heavier visual treatment to ship faster with a smaller content surface. v1 uses the existing report typography classes (light treatment); v2 hardens the report for print and mobile use after the content shape stabilizes through real coaching use.

UX delivered the full v1 visual hierarchy spec on 2026-04-27. Most of it was deferred to this epic.

**Discovery decisions locked (from E-228 planning 2026-04-27, UX delivery):**

### AVOID Inline Sub-Bullet Typography
Per UX, "what to avoid" content is paired with the corresponding positive instruction in the SAME prose paragraph as an indented sub-bullet:
- "AVOID:" prefix in 7pt small caps bold
- Body text in 8.5pt regular
- NO color, NO icon, NO border (color-free differentiation that survives B&W printing)
- Indent reduces from `pl-6` to `pl-3` at `sm:` breakpoint (mobile)

Example:
```
SHOCKEY  #14
Attack the zone -- he chases off-speed away (2 BB in 91 PA).
  AVOID: Don't fall behind. He's .680 OBP when ahead in count
  (47 PA after 1-0 or 2-1).
```

**Note**: head-to-head was DROPPED from E-228 v1 entirely. Visual treatment of head-to-head (banner-vs-sidebar) does not apply.

### Visual Hierarchy Table
| Element | Style |
|---------|-------|
| Section header `GAME PLAN` | 11pt small caps |
| TL;DR line | 10pt bold, single line, middot-joined |
| Sub-section header | 10pt small caps + horizontal rule above |
| Hitter/pitcher name | 9pt bold |
| Body prose | 8.5pt regular |
| Citations | 8.5pt italic gray |
| AVOID prefix | 7pt small caps bold, indented |
| LLM narrative | 8.5pt regular, left border (`.starter-narrative-style`) |

### Print Mechanics
- Game Plan uses the existing stats-page named page (landscape).
- Each sub-section: `break-inside: avoid`.
- Per-hitter blocks within Dangerous Hitters: `break-inside: avoid` individually (positive + AVOID don't split across pages).
- TL;DR: `break-after: avoid` (keeps adjacent to first sub-section).

### Mobile (375px Viewport)
- Vertical stack.
- Recent-form line wraps via `flex-wrap`.
- Lineup card stays 1-column.
- AVOID indent reduces from `pl-6` to `pl-3` at `sm:` breakpoint.

### Byte-Identical Baseline-Fixture Regression Machinery
Per SE-C2 from E-228 planning:
- Substitution scheme: `generated_at` → `__GENERATED_AT__`, `expires_at` → `__EXPIRES_AT__`, `slug` → `__SLUG__` (3 non-deterministic fields).
- Regen script: `scripts/regenerate_baseline_fixture.py` (drops + seeds tmp DB, generates report, applies substitution, writes `tests/fixtures/baseline_scouting_report.html`).
- Fixture-DB seed function: `tests/fixtures/seed_baseline_db.py::seed_baseline_db(conn)` -- 1 tracked opponent, 12 completed games, 15 players, sample stat rows.
- Test: byte-identical comparison after substitution.

E-228 v1 ships with a lighter regression check ("matchup-off path produces the same report it does today"); E-231 upgrades to full byte-identical machinery.

**Promotion trigger**: After E-228 v1 ships AND coach has used the report in print form + mobile form + verified ergonomics in real game-prep workflow.

## Goals
- AVOID inline sub-bullet treatment ships if the v1 LLM prose still produces avoid-clauses (depends on E-228-13 wrapper + v2's directive language).
- Full visual hierarchy table is implemented (font sizes, weights, italic gray citations, etc.).
- Print stylesheet hardening: every sub-section AND every per-hitter block has `break-inside: avoid`. The TL;DR has `break-after: avoid`. The full-page report prints cleanly on landscape letter without orphaned blocks.
- Mobile responsive at 375px viewport: vertical stack works, indent reduces, recent-form line wraps.
- Byte-identical baseline-fixture regression machinery: substitution scheme + regen script + checked-in fixture + test that fails loudly on any rendered HTML drift.

## Non-Goals
- Engine logic changes (those are E-230).
- Dashboard parity (that's E-232).
- Visual changes to existing report sections that pre-date the matchup section.
- Print-friendly redesign of the entire report (only the matchup section is in scope).
- Re-introducing head-to-head visual treatment (head-to-head was dropped from v1 entirely).

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| | To be written during planning | | | |

## Dispatch Team
- ux-designer
- software-engineer

## Technical Notes

### CSS Strategy
The visual hierarchy table maps cleanly to existing report styles plus a small set of new classes for matchup-specific elements (e.g., `.game-plan-section`, `.matchup-tldr`, `.matchup-avoid-prefix`). v2 planning decides whether to extend the existing report stylesheet or introduce a `matchup-specific.css`.

### Print Test Strategy
Print testing is hard to automate. v2 planning establishes the verification approach:
- Manual review on a real game-prep print run by the operator?
- Automated CSS pixel measurement via Puppeteer / playwright?
- Snapshot comparison of rendered PDF (server-side via WeasyPrint -- captured separately as a project memory item for PDF generation)?

### Mobile Test Strategy
Same question shape: `pytest` + Playwright at 375px viewport? Visual regression snapshots? v2 planning decides.

### Byte-Identical Machinery
Implementation per SE-C2:
1. `tests/fixtures/seed_baseline_db.py` defines `seed_baseline_db(conn)` -- a deterministic seed with 1 tracked opponent, 12 completed games, 15 players, sample `player_game_batting` + `player_game_pitching` rows.
2. `scripts/regenerate_baseline_fixture.py` applies the seed, generates a report, applies the 3-field substitution scheme, writes the result to `tests/fixtures/baseline_scouting_report.html`.
3. `tests/fixtures/README.md` documents the regeneration recipe so any implementer can reproduce.
4. The byte-equality regression test renders the report against the same seed and compares to the fixture (after substitution).

This story is the upgrade path from E-228-01's lighter regression check.

## Open Questions
1. **Does the AVOID inline sub-bullet treatment still apply** given v1's lighter prose style (single coach-voice paragraph + per-hitter cues)? If v1's LLM wrapper rarely produces avoid-clauses (or coach feedback says cues are sufficient without explicit "AVOID:" callouts), the AVOID treatment may not be needed.
2. **Print-vs-screen-vs-mobile split**: do these go in one story, three stories, or some other grouping? Planning decides based on the implementing agent's session size.
3. **PDF generation** (server-side, via WeasyPrint): captured in PM memory as `project_pdf_generation` -- whether E-231 owns adding PDF as an output format OR whether that lives in a separate epic is a planning-time question.
4. **Visual regression tooling**: snapshot HTML, snapshot PNG (Playwright), or no snapshot at all? Planning decides.

## Promotion Triggers
This epic is gated on real-use validation:
1. **E-228 v1 has shipped** (status COMPLETED, archived).
2. **Coach has used the matchup report in print form** at least 1 real game-prep workflow (pre-game bench card).
3. **Coach has used the matchup report on mobile** in at least 1 dugout reference workflow (during-game lookup).
4. **Coach reports specific ergonomic friction** (e.g., "the AVOID notes get cut off when I print," "the recent-form line wraps weirdly on my phone") -- the friction informs which stories E-231 prioritizes.

## History
- 2026-04-28: Created as DRAFT stub during E-228 v1 refinement. Discovery context preserved from E-228 planning sessions (2026-04-27 -- UX delivery). Original scope was distributed across story E-228-09 (renderer + visual hierarchy) and E-228-01 (byte-identical fixture machinery); promoted to its own epic because visual polish requires real-use ergonomic feedback that doesn't exist yet.
