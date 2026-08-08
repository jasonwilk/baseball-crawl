# E-263-01: UXD Layout Specification — Deep Scout report sections

## Epic
[E-263: Deep Scout v1 — Opponent-Intelligence Report Sections](epic.md)

## Status
`TODO`

## Description
After this story is complete, the epic has a single Layout Specification that tells the implementing engineer exactly where each new Deep Scout section lands in the existing report, how the shared trust-surface (floor/`thin`/`no_data`) idiom looks, and how the two highest-risk new components render — so the four builder stories produce a coherent, print-safe, mobile-safe report instead of nine independently-styled fragments.

## Context
The report is a self-contained HTML file with named CSS pages (`@page` landscape/portrait, `break-before`/`break-inside: avoid` throughout `scouting_report.html`). Nine new signals landing in the wrong page-flow position can silently break pagination (orphaned cards, a table split across a page boundary), visible only on print/PDF. The new signals are card- and narrative-scoped with their own floors (15 BIP alignment, 5-attempt steal light, backpicks as raw counts, `n` always shown per TN-1/TN-2) — if left to per-story SE judgment across the sections, the "thin data" treatment fragments. Existing mobile column-hiding (`mob-hide`) is table-only; the new card components need their own 375px-first treatment. This story front-loads those decisions once. It produces a design artifact only (no code); E-263-02a builds the shared partial + the four stub section partials from this spec (pinning their filenames), and the builder stories (E-263-04/05/06/07) fill those partials against it.

## Acceptance Criteria
- [ ] **AC-1**: A Layout Specification document exists (prose + ASCII wireframe) that assigns each of the four sections (per Technical Notes TN-5) a placement in the existing report against the current page-break structure, states the print-page assignment for each (such that no new section splits across a page boundary or orphans a card), and PINS the four section-partial filenames E-263-02a will create.
- [ ] **AC-2**: The spec contains a Component Inventory: for each new component (Game Plan synthesis card, the Who's-Pitching adjacent card, alignment directive, error-map, steal light, battery-control card) it names the data shape it consumes from the fact sheet, its trust-floor threshold (per TN-2), its badge/`thin`/`no_data` treatment, its 375px mobile behavior, and its print-page assignment.
- [ ] **AC-3**: The spec defines ONE unified trust-surface idiom reconciled with `.claude/rules/display-philosophy.md` per Technical Notes TN-2 (raw value ALWAYS shown at full weight + n/IP/PA badge; `ok`/`thin` identical, differentiated only by the badge; `no_data` = structural absence + raw count, never blank; SIG-006 FPS% as the literal template; and the stat-vs-synthesized-claim distinction — a directive/two-branch recommendation may withhold the RECOMMENDATION below floor while still showing the raw data). One idiom reused across all components, expressed concretely enough that E-263-02a can build it as a shared template partial/macro.
- [ ] **AC-4**: The spec includes 1-2 representative HTML/Tailwind reference mockups for the two highest-risk NEW components only — the Game Plan synthesis card and the steal-light/battery-control card grid — sufficient for SE to replicate the pattern for the remaining components. (A full 9-signal mockup set is explicitly out of scope.)
- [ ] **AC-5**: The spec documents the OQ3 resolution (SIG-008 error-map is its OWN sub-section within Their Hitters & Defense, per the baseball-coach/ux-designer convergence — NOT folded into the Game Plan), and specifies the **committee-state rendering shape** for the Game Plan per Technical Notes TN-5 §1 (2-arm committee → 2 compressed one-line bullets; 3+-arm → 1 composite bullet; within the ≤3-bullet/≤600-word budget), with full per-arm detail deferred to Who's Pitching.
- [ ] **AC-6**: The spec honors the ethics split (TN-8): it marks which components are coach-facing-only (steal light / named catcher) and which carry the number-only player-safe carve-out (SIG-007 alignment), so the render treatment does not accidentally expose a coach-only signal in a player-safe styling.
- [ ] **AC-7**: The spec specifies Section 3's (Their Hitters & Defense) graceful-dark state — when spray data is unavailable (gc_uuid unresolved or no defensive spray, per Technical Notes TN-5 §3) the whole section renders a clean, clearly-labeled `no_data` state, not an empty/broken card.

## Technical Approach
Read the design doctrine in `.project/research/deep-scout-design-2026-07-12.md` (§6 consumption verdicts, §8x live-validation) and the catalog (`.project/research/scouting-signal-catalog.md`) for per-signal shapes. Review the existing report template `src/api/templates/reports/scouting_report.html` for the current page-break map, the Most Likely Arms card, spray cards, and the `.depth-badge`/`.starter-estimate-badge` trust idiom. Deliver the spec as a design artifact under `.project/research/` (e.g. `E-263-uxd-layout-spec.md`). Placement (from the ux-designer + baseball-coach Phase-3 sync): Who's Pitching renders as an ADJACENT card sharing visual language + arm identity with the existing Most Likely Arms card (not an in-place edit); Game Plan is a new synthesis card immediately after it; Running Game & Battery is a new section right after the Pitching table before Batting; the alignment DIRECTIVE renders in the standalone Their Hitters & Defense section (not a spray-card extension — better landscape print, and structurally required since builders don't edit `scouting_report.html`). Confirm against the actual template.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-263-02a, E-263-04, E-263-05, E-263-06, E-263-07 (their render portions)

## Files to Create or Modify
- `.project/research/E-263-uxd-layout-spec.md` (new — the Layout Specification design artifact)

## Agent Hint
ux-designer

## Handoff Context
- **Produces for E-263-02a**: the unified trust-surface idiom (AC-3), the four pinned section-partial filenames (AC-1), and the graceful-dark/committee shapes that the framework story builds as the shared partial + stub partials.
- **Produces for E-263-04/05/06/07**: the section placement, print-page assignment, mobile behavior, and component inventory each builder story renders against.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Spec reviewed against the actual `scouting_report.html` page-break structure (not assumed)
- [ ] Follows project conventions (see CLAUDE.md)
- [ ] No code changes (design artifact only)

## Notes
This is a design-only story; the ux-designer produces a specification, not template code. SE implements the templates in the builder stories against this spec.
