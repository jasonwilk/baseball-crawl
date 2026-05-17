# E-229-2b: Quarter-letter layout feasibility prototype — locked constants artifact

## Epic
[E-229: Team-Aggregate Defensive Positioning](epic.md)

## Status
`TODO`

## Description
After this story is complete, two artifacts exist that lock the design constants for every downstream visual story in E-229: (1) a static HTML prototype rendering representative positioning cards at exact quarter-letter geometry (4.25" × 5.5"), and (2) a markdown spec listing every layout, typography, and design-token value the prototype validates. The artifacts are signed off by baseball-coach (legibility) and UXD (design coherence). Every downstream visual story (E-229-03 SVG generator, E-229-04 pills, E-229-05 card template, E-229-06 prep page, E-229-07 call sheet) reads its design constants from the locked artifact instead of carrying them inline in ACs.

## Context
Round-1 UXD consultation assumed a letter-portrait card geometry (~5" × 6" per card). The user reframed during planning to quarter-letter geometry (4.25" × 5.5", 4-up on letter portrait sheets, back-pocket size). The quarter-letter dimensions force every downstream design constant to compress — SVG aspect ratio, sidebar width, pill size, compass-letter typography, density-background opacity. UXD round-1 numbers (SVG aspect 0.6, pill 0.18"×0.14", letter font 10pt) are provisional estimates that need to be validated at the actual print size before E-229-03 commits to them in code.

Round-2 holistic review surfaced this rework risk explicitly: E-229-03 and E-229-04 commit to design constants without a validated reference; E-229-05 (the card template) is the first place those constants render at print size; if E-229-05 finds the constants don't work, E-229-03 and E-229-04 must refactor. This story is the cheapest insurance against that risk — a half-day UXD effort produces a static prototype and a constants spec that downstream stories cite.

The constants spec also resolves the cross-cutting coverage-cue / pill / legend / typography-parity issues from the Phase 4 Codex review (P2.5 + adjacent UXD findings I-1, I-3, I-4, I-6, M-1, M-3, M-4): one document is the single source of truth for design tokens across all 5 visual stories.

Phase 4 iteration 2 PM-side incorporation created a PROVISIONAL v0 stub of the constants artifact at `/.project/research/E-229-locked-layout-constants.md` with UXD round-1 round-2 estimates as initial values. This story validates those values at print scale and flips the frontmatter to LOCKED v1 on coach sign-off (per AC-12). Downstream stories cite the artifact path; they MUST NOT consume the PROVISIONAL v0 values for production implementation — they wait for the LOCKED v1 flip.

## Acceptance Criteria

- [ ] **AC-1**: A static HTML prototype exists at `.project/research/E-229-2b-quarter-letter-prototype.html`. The prototype renders one representative positioning card at exact 4.25" × 5.5" portrait geometry (using inline `<style>` with absolute inch dimensions and `@page { size: letter portrait }` print CSS). The prototype renders three card variants in sequence on the same page: full-data state (5+ outliers, density bg, BIP-count caption on star), thin-data state (15–49 BIPs, dashed-ring star indicator or "(~N BIP)" caption, no density bg), and zero-coverage state (0–14 BIPs, "Not enough spray data — play your standard alignment" message, no star/dot/letters). The prototype also renders the full 2×2 sheet layout (letter portrait, 4-up) showing all 4 card slots — including the sheet-2 fill content (compass-key slot and opponent-context-card slot per E-229-05 AC-9 lock).

- [ ] **AC-2**: A locked-constants spec exists at `.project/research/E-229-locked-layout-constants.md` with frontmatter:
  ```
  ---
  status: LOCKED        (was PROVISIONAL v0 before this story; flipped to LOCKED v1 on AC-12 coach sign-off)
  version: 1
  produced_by: E-229-2b
  calibration_history: []
  ---
  ```
  The doc cross-links to the prototype HTML. The doc opens with a brief preamble explaining its role as the single source of design truth and the citation pattern downstream stories should use (per epic TN-16). The PROVISIONAL v0 stub created during Phase 4 iteration 2 is superseded by the LOCKED v1 version on this story's completion.

- [ ] **AC-3**: Constants spec §A — Card geometry. Lists: card outer dimensions (4.25" × 5.5"), card inner padding, 4-up sheet layout (2×2 grid on letter portrait + page margins), and cut-line spec (weight, dash pattern, color, placement on midlines only). All values are exact print measurements.

- [ ] **AC-4**: Constants spec §B — SVG (field diagram). Lists every per-card SVG design constant: SVG aspect ratio, SVG dimensions in inches, SVG viewBox dimensions, star marker (size + fill + stroke + BIP-count caption typography), textbook reference dot (size + stroke + color + opacity), compass letter (font size + backing circle diameter + backing opacity + ring placement radius as % of SVG min dimension + edge-clamping rule), outlier pill (width range + height + fill + stroke + font + font size + corner radius + jersey-number formatting rule + jersey-NULL fallback), density background (dot size + opacity + color + render-gate rule), z-order stack (back to front). **Includes the projection formula constants `scale_x` and `scale_y`** (pixels per ordinal-bucket unit) per epic TN-15.

- [ ] **AC-5**: Constants spec §C — Card frame. Lists: header zone (height + typography for opponent name + position name + coverage cue + alignment), body zone (SVG/sidebar split ratio + gap), legend zone (height + typography), sidebar (row layout for jersey + last-name + zone letter + last-name truncation rule + per-column font sizes + row height + empty-state banner spec per coach IM-1 + UXD M-4).

- [ ] **AC-6**: Constants spec §D — Sheet 2 fill content. Lists specs for the two fill slots: (a) visual compass key (mini diagram showing 8-zone compass on blank field with label placement + axis annotations per epic TN-15 SVG coord convention) and (b) opponent context card (name treatment + stat lines for record, runs/game, runs-allowed/game + team total BIP + tier label + coverage cue placement).

- [ ] **AC-7**: Constants spec §E — Typography parity across artifacts. Lists: call sheet typography (header + legend text long form + cell typography + jersey-column emphasis rule per UXD I-7), prep page typography (header + sidebar table typography + pill format `7-LF` per UXD M-2 + collision rules per epic TN-10), parity rules linking shared elements (e.g., coverage cue renders identically on cards / prep page / call sheet).

- [ ] **AC-8**: Constants spec §F — Shared design tokens. Lists: font family (single stack across all artifacts), greyscale palette (specific values, e.g., 0% / 15% / 30% / 50% / 70% / 100% with usage rules per token), coverage-cue text format constant (`Through {Mon Day} ({N} games)` per coach IM-2 + E-229-08 AC-4a snapshot), legend text constants (`COMPASS_LEGEND_SHORT` for cards + `COMPASS_LEGEND_LONG` for call sheet/prep page, both with verbatim text matching epic TN-3), color-is-never-load-bearing rule per UXD I-6.

- [ ] **AC-9**: Constants spec §G — Responsive (web view). Lists: mobile breakpoint (640px, Tailwind `sm:` per UXD I-5), stacking behavior at ≤640px (SVG full width + sidebar below, aspect ratio maintained), behavior at >640px (print layout per §C).

- [ ] **AC-10**: Constants spec — Decisions log. Final section of the spec. For each constant that has a non-obvious value (target ~6–10 entries: SVG aspect ratio, body split ratio, pill dimensions, compass letter font size, ring placement radius, density opacity, header height, font family stack), records: (a) the locked value, (b) one to two alternatives tried during prototyping, (c) why each alternative was rejected. Format: subsection per constant. The Decisions Log is REQUIRED content (template only is insufficient — actual decisions for the constants listed above must appear).

- [ ] **AC-11**: UXD legibility self-validation. The prototype HTML is printed (or rendered + measured) at exact quarter-letter size. UXD verifies each of the following at arm's length in normal indoor light: (a) outlier pills are legible (jersey number + truncated last name); (b) compass letters are distinguishable from pills and the star; (c) sidebar lookup is readable without squinting; (d) coverage cue and opponent name are readable; (e) legend text is legible. UXD documents pass/fail per criterion in this story's Notes (5 verdicts total).

- [ ] **AC-12**: Baseball-coach legibility review (documented-record pattern matching E-229-05 AC-8). A written coach review record exists in this story's Notes section with: verdict (PASS / FAIL), date, failure points on FAIL or no-failure-modes confirmation on PASS. AC is satisfied by **presence of the record**, NOT by a PASS verdict; PM-gated revision on FAIL is a non-AC process step. Coach reviews against quarter-letter print sample focusing on dugout-glance-test legibility for a 15-year-old fielder in dugout shade between pitches. **On PASS**, UXD flips the constants spec frontmatter `status` from PROVISIONAL to LOCKED, bumps `version` to 1, and updates `produced_by: E-229-2b`.

## Technical Approach

**Prototype HTML structure**: a single self-contained HTML file at `.project/research/E-229-2b-quarter-letter-prototype.html` following the precedent of `.project/research/E-228-positioning-cards-mockup.html`:
- Inline `<style>` block (no external CSS)
- `@page { size: letter portrait; margin: 0.25in }` for print fidelity
- A screen banner (hidden on print) explaining the prototype's role
- Cards rendered at exact 4.25"×5.5" geometry using absolute inch dimensions
- Three card variants in sequence (full / thin-data / zero-coverage)
- A 2×2 sheet layout showing all 4 card slots including sheet-2 fill content (compass-key, opponent-context)
- Browser Print → "Save as PDF" produces a print sample for the legibility test

**Use representative content**: invent a fictional opponent ("Eastlake Bears, Through Apr 12 (8 games)") with 5 outlier batters at varying zones for the full-data state. Real-data validation comes during the calibration pass (epic Rollout), not this story.

**Constants spec structure** (markdown):
```
---
status: LOCKED
version: 1
produced_by: E-229-2b
calibration_history: []
---

# E-229 Locked Layout Constants

[preamble: role of doc, citation pattern per epic TN-16]

## A. Card Geometry
| Constant | Value | Notes |
|---|---|---|
...

## B. SVG (field diagram)
...

## C. Card Frame
...

## D. Sheet 2 Fill Content
...

## E. Typography Parity Across Artifacts
...

## F. Shared Design Tokens
...

## G. Responsive (web view)
...

## Decisions Log

### SVG aspect ratio: <locked value>
- Tried <alternative>: <rejection reason>
- Tried <alternative>: <rejection reason>
- <locked value> chosen because: <reason>

### Body split ratio: <locked value>
...
```

**Citation pattern for downstream stories**: downstream stories cite `.project/research/E-229-locked-layout-constants.md §B (SVG)` rather than naming specific values in ACs. E-229-03 AC-1, E-229-04 AC-3, E-229-05 AC-1/AC-2, E-229-06, and E-229-07 already use this citation form (updated during Phase 4 iteration 2 incorporation per Codex P2.5).

**Coach legibility review process**: when the prototype is ready, package a printed sample at quarter-letter size (the user can print the prototype HTML and verify scale by ruler — 4.25"×5.5" cards) and route to baseball-coach via PM. Coach reviews against the dugout-glance-test criteria: can a 15-year-old fielder read this in dugout shade between pitches? Coach produces a written verdict; verdict goes in this story's Notes. On PASS, UXD flips the constants spec frontmatter from PROVISIONAL v0 to LOCKED v1 and applies any necessary refinements from coach feedback.

**Iteration discipline**: if the prototype reveals a constant the round-1/round-2 estimates got wrong (e.g., 0.18" pill height is illegible; needs 0.22"), UXD iterates within this story's scope rather than escalating. The Decisions Log captures the iteration path. Only escalate if the geometry fundamentally doesn't fit (e.g., legible pills require a card larger than 4.25"×5.5") — that would warrant revisiting the user-locked quarter-letter geometry, which is out of scope here.

## Dependencies
- **Blocked by**: E-229-02 (engine output shape needed so the prototype's representative content matches the engine's actual emission shape — pills carry `direction_deviation` + `depth_deviation` per epic TN-15 projection formula; the prototype must demonstrate the projection correctly per epic TN-15 sign rule). UXD round-2 note flagged this dep as "soft" (placeholder data fine if engine isn't locked), but PM keeps it as a hard blocker to ensure the prototype represents the locked engine output shape; if dispatch sequencing pressure surfaces, revisit and consider parallel execution.
- **Blocks**: E-229-03 (SVG generator cites §B), E-229-04 (pills cite §B), E-229-05 (card template cites §A, §C, §G), E-229-06 (prep page cites §E typography parity), E-229-07 (call sheet cites §E + §F legend text)

## Files to Create or Modify
- `.project/research/E-229-2b-quarter-letter-prototype.html` — create (static HTML prototype, design reference only; NOT production code)
- `.project/research/E-229-locked-layout-constants.md` — modify (supersedes the PROVISIONAL v0 stub created during Phase 4 iteration 2 PM-side incorporation; flip to LOCKED v1 with actual measured constants and the populated Decisions Log)

## Agent Hint
ux-designer

## Handoff Context
- **Produces for E-229-03 / 04 / 05 / 06 / 07**: a locked constants spec at `/.project/research/E-229-locked-layout-constants.md` (status: LOCKED v1) that downstream visual stories cite instead of carrying values inline in ACs. PM already updated downstream story ACs during Phase 4 iteration 2 to use the citation pattern; the LOCKED v1 flip on this story's completion is the contract those ACs depend on.
- **No production code changes**: this story produces design reference artifacts only. The prototype HTML lives in `.project/research/`, not `src/api/templates/`.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Prototype HTML exists and renders correctly at print size (verified by UXD eyeball + measure per AC-11)
- [ ] Locked-constants spec exists, frontmatter flipped to LOCKED v1 after coach sign-off per AC-12
- [ ] UXD legibility self-validation record present in Notes per AC-11
- [ ] Baseball-coach legibility review record present in Notes per AC-12
- [ ] Decisions Log populated with actual entries per AC-10 (not just template scaffolding)

## Notes

### UXD legibility self-validation (per AC-11)

Assessed at the documented typography sizes against the print geometry locked in §A–G of `.project/research/E-229-locked-layout-constants.md`. Caveat: UXD cannot physically print and view at arm's length in dugout conditions; this assessment is against the documented typography minimums (TN-16 ≥ 7 pt absolute floor; coach MN-2 pill jersey ≥ 7–8 pt; ≥ 7–8 pt compass letters) and the spatial relationships visible in browser preview at the absolute-inch geometry. Five verdicts:

- (a) **Outlier pills legible (jersey + truncated last name) — PASS.** Pill text is 9 pt Arial bold (TN-16 minimum is 9 pt for this element). Pill height 14 px in viewBox (~0.20 in printed) gives 1 px headroom each side of the cap line. Format `#7 RAMIR` fits in ~0.5 in pill width with the auto-sizing rect. White fill + 0.5 pt black stroke gives contrast against both the 12% density bg and the 20%-opacity compass discs. Coach AC-12 confirmed PASS.

- (b) **Compass letters distinguishable from pills / star — PASS.** Compass letters are 10 pt Arial bold inside circular discs (rect-vs-circle shape distinction from pills); star is a solid filled 10-point star (geometric-shape distinction from both letters and pills). Z-order (pills draw last) prevents any letter from obscuring an actionable pill. Coach AC-12 confirmed PASS — "compass letters (10 pt) leading the eye to pills, then sidebar confirming zone assignment, is the right two-step read."

- (c) **Sidebar lookup readable without squinting — PASS.** 7.5 pt Arial proportional with `tabular-nums` on jersey + zone cells; CSS grid with explicit column widths (0.34 in / 1fr / 0.20 in) keeps columns aligned. 5 rows fit comfortably in the sidebar height with breathing room. 7.5 pt is above the TN-16 ≥ 7 pt floor. Coach AC-12 confirmed PASS.

- (d) **Coverage cue + opponent name readable — PASS.** Opponent name is 11 pt Arial bold (well above any legibility floor). Coverage cue is 9 pt Arial regular at 70% grey, right-aligned. Format string "Through Apr 12 (8 games)" fits in ~1.4 in at 9 pt, leaving 2.5+ in for the opponent name without truncation. Coach AC-12 confirmed PASS.

- (e) **Legend text legible — PASS (post-remediation).** Initial self-validation at 6.5 pt was flagged as "below TN-16 floor of 7 pt; may not survive coach review." Coach AC-12 confirmed the FAIL and pre-approved Option 1 (shortened legend text + 7 pt). Post-remediation: legend renders `★ default · ○ textbook · A-H outliers` at 7 pt 70% grey, fits one line at the 3.95 in card-inner width. Meets the TN-16 floor with margin. **The remediated legend was not re-reviewed by coach** — coach pre-approved Option 1 as the fix, so the LOCKED v1 flip is authorized by the AC-12 PASS verdict against the remediated form.

Final: **5/5 PASS** at the LOCKED v1 typography sizes.

### Baseball-coach legibility review record (per AC-12)

**Verdict**: FAIL (partial — primary workflow PASSES; legend typography FAILS TN-16 minimum)
**Date**: 2026-05-17
**Review focus**: Dugout-glance-test legibility for a 15-year-old fielder in dugout shade between pitches, 4.25" × 5.5" quarter-letter card

**Primary workflow — PASS.** Sidebar lookup → field diagram navigation is clean. Sidebar (jersey 7.5 pt bold, last names 7.5 pt weight-500, zone letters 7.5 pt bold), compass letter discs (10 pt bold, 0.18 in disc), outlier pills (#JERSEY LAST, 9 pt bold), and header (11 pt opponent / 10 pt position uppercase) all clear the dugout-glance bar comfortably. A 15-year-old fielder will navigate the primary path correctly in dugout shade. No failure modes.

**Legend — FAIL.** 6.5 pt at 70% grey is below TN-16's 7 pt absolute minimum, and the grey ink compounds the legibility problem in shade. Acceptable for a briefed player mid-at-bat, but a freshman with cold cards or any player wanting a quick reminder will lean in and squint — violates dugout-glance standard.

**Preferred fix: Option 1** — `★ default · ○ textbook · A-H outliers` at 7 pt.
- Meets TN-16 minimum
- "(see right)" parenthetical adds nothing — sidebar IS to the right, zone letter is already printed there
- All three symbol types still present (star, circle, A–H)
- Shortened content fits one line at 7 pt — solves the root cause (geometry constraint that forced UXD to drop to 6.5 pt), not fighting geometry
- Option 2 (wrap) wastes vertical space and risks bleeding into body zone — unacceptable
- Option 3 (drop textbook-dot reference) is defensible but removes a symbol that DOES appear on cards, leaving ○ unexplained — Option 1 is cleaner

**Secondary observation (non-blocking)**: BIP-count star caption (`(142 BIP)` / `(~28 BIP)`) also renders at 6.5 pt. NOT in primary fielder read path — coach treats this as low-stakes from dugout-glance standpoint. UXD + PM judgment call: bump to 7 pt if it fits without geometry tradeoffs that hurt more important elements; otherwise 6.5 pt acceptable on BIP caption while holding the line on the legend.

**Information hierarchy — correct.** Header → outlier pills on field → sidebar lookup → everything else matches fielder processing order under game pressure. Compass letters (10 pt) leading the eye to pills, then sidebar confirming zone assignment, is the right two-step read.

**Coach summary**: "FAIL on 6.5 pt legend. Apply Option 1 — shorten to `★ default · ○ textbook · A-H outliers` at 7 pt. All other elements PASS the dugout-glance test. On that one fix, I'd sign off PASS and the constants spec can flip to LOCKED v1."

### Remediation applied (2026-05-17, UXD; coach pre-approval per AC-12 above)

- Prototype HTML (`.project/research/E-229-2b-quarter-letter-prototype.html`): legend CSS bumped 6.5 pt → 7 pt; all 9 legend occurrences updated to Option 1 text (`★ default · ○ textbook · A-H outliers`); all 8 SVG BIP-caption `font-size` values bumped 6.5 → 7 pt (explicit pt unit so the rendered size matches the spec).
- Constants spec (`.project/research/E-229-locked-layout-constants.md`): §B BIP caption 6.5 → 7 pt; §B added "SVG font-size unit convention (normative)" subsection so SE generators target print pt explicitly; §C legend typography 6.5 → 7 pt with rationale; §E typography parity table bumped Card Star BIP caption + Card Legend to 7 pt; §F `COMPASS_LEGEND_SHORT` updated to Option 1 text + TN-3 amendment note added directly below the §F table (PM owns the routed amendment to epic TN-3); Decisions Log new entry "Legend text + typography" recording PROVISIONAL → 6.5 pt → coach FAIL → Option 1 path.

### Constants spec status transition

- 2026-05-17: PROVISIONAL v0 → LOCKED v1. Authorized by coach AC-12 PASS verdict (above) on the Option 1 remediation pre-approval. `produced_by: E-229-2b`. `calibration_history` empty (first-real-opponent calibration is the epic Rollout note, not this story).

**Provenance**: this story spec was drafted by ux-designer during Phase 4 iteration 2 of E-229 planning (2026-05-17), per UXD's offer at end of round-2 consultation and PM's acceptance via team-lead relay. PM framed AC-12's documented-record gate shape (matches E-229-05 AC-8 precedent) and confirmed the soft-vs-hard E-229-02 dependency call. AC granularity (12 ACs) preserves per-section verifiability per UXD's recommendation; consolidation into fewer ACs with sub-checklists was considered and rejected. Pattern note: this is the second instance in E-229 of a domain expert drafting full story content (the first was UXD's round-1 expanded scope on the locked-constants artifact). Worth surfacing to claude-architect as a candidate skill / rule observation after E-229 completes.
