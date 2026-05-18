# E-229-05: Compact card template — quarter-letter 4-up geometry + coach design review

## Epic
[E-229: Team-Aggregate Defensive Positioning](epic.md)

## Status
`DONE`

## Description
After this story is complete, the card HTML/CSS template renders each per-position card at 4.25"×5.5" portrait geometry, with print CSS supporting a 4-up layout on letter portrait sheets. Each card carries header (opponent + position + coverage cue), field SVG + sidebar lookup side-by-side, and a one-line legend. Two extra layout variants render cleanly: a no-outliers state and a zero-coverage state. Baseball-coach reviews the final layout and signs off.

## Context
The user reframed the print workflow during planning: "he will never print them between innings. one report pre-game. let them be a print size that fits in high school baseball back pocket." That overrode UXD round-1's 1-card-per-letter-page recommendation. The new constraint is **quarter-letter cards** (4.25"×5.5"), cut from 4-up portrait letter sheets, that survive a 7-inning back-pocket.

4.25"×5.5" is tight. UXD will need to compress the layout from round-1's spacious mockup: smaller field SVG, compact sidebar lookup, tight legend. Print sheet 2 holds positions SS and 2B in slots 1–2 of the 4-up grid; **slots 3 and 4 are FILLED (not blank) with the visual compass key and opponent context card** per E-229-05 AC-9 lock (E-229-2b's locked-constants artifact specifies the layout for each of those two slots).

The coach design-review AC (E-228 used this pattern in E-228-04 AC-8) gates the layout on coaching usefulness: the deliverable is a documented baseball-coach review record (verdict, date, failure points on FAIL, no-failure-modes confirmation on PASS). The AC is satisfied by the *presence of a complete record*, not by a PASS verdict. PM-gated revision step on FAIL is a non-AC process gate.

## Acceptance Criteria
- [ ] **AC-1**: Card HTML/CSS template renders each per-card area at 4.25" × 5.5" portrait geometry consuming ALL layout constants from the locked-constants artifact at `/.project/research/E-229-locked-layout-constants.md` (per E-229-2b): SVG aspect ratio, sidebar width, header height, legend height, typography minimums, padding. Print CSS pages match: `@page positioning-cards { size: letter portrait; margin: 0.25in }` with a 2×2 internal CSS grid yielding 4 cards per letter page.
- [ ] **AC-2**: Layout per card: header (opponent name + position name + coverage cue) at the top spanning full card width; field SVG + sidebar lookup arranged side-by-side in the main area; legend at the bottom spanning full card width. **Side-by-side ratio (SVG/sidebar split) is consumed from the locked-constants artifact** — this story does NOT name a specific split percentage. UXD round-1 estimate (64/36 split with 0.6 SVG aspect) lives in the artifact as PROVISIONAL; E-229-2b validates and either confirms or refines.
- [ ] **AC-3**: Sidebar lookup contents: jersey + truncated last-name + zone-letter compact table for THIS position's outliers, one row per outlier. Per UXD M-4: rows display `#<jersey>` + last-name (truncated to ~6 chars, e.g., "RAMIR" for "RAMIREZ") + zone letter with minimal whitespace, ~7pt monospace. If 0 outliers, sidebar shows the single-line note "No outliers this opponent" (per IM-1 lock: sidebar always shows content — never empty).
- [ ] **AC-4**: Print CSS supports a 4-up portrait layout per page. **Cut-line indicators**: 0.5pt dashed hairlines (2pt dash, 2pt gap), 50% grey, on the horizontal and vertical midlines only — no corner crop marks, no full-card borders (per UXD M-3 lock). No card breaks across pages.
- [ ] **AC-5**: B&W primary readability — the layout uses no color-only differentiation. All information (zone identity, confidence tier, batter identity) is communicated by shape, position, or text. Test: SVG output contains no `fill` or `stroke` color values other than `black`, `white`, or grey-scale (`#xxx` where R=G=B, or named greys).
- [ ] **AC-6**: Mobile / web view — the card template responsively collapses to a single-column layout at viewports ≤640px (Tailwind `sm:` breakpoint, NOT `md:` per UXD I-5 fix). At ≤640px: SVG full-width (maintaining the aspect ratio locked in the constants artifact, not a hardcoded value), sidebar below at full width, header and legend always full-width. At >640px: side-by-side layout per AC-2. (CR M2 fix: the prior reference to "TN-7 implied" was wrong — TN-7 is JOIN patterns; mobile responsive is spec'd inline here.)
- [ ] **AC-7**: Empty / state variants render cleanly within the same template: the no-outliers state (sidebar shows the one-line "No outliers this opponent" note; field SVG renders all 8 compass letters as faint placeholders per E-229-03 AC-8) and the zero-coverage state (field SVG renders the dominant "Not enough spray data — play your standard alignment" message; sidebar renders a matching one-line note OR is hidden via CSS `visibility: hidden` to preserve grid layout — **never visually empty**). Both are visually distinct from the full state. IM-1 fix: sidebar always shows content, never structurally absent.
- [ ] **AC-8**: Coach design review of the layout: a documented baseball-coach review record exists in this story's Notes section (verdict, date, failure points on FAIL or no-failure-modes confirmation on PASS). The AC is satisfied by the presence of the record; revision on FAIL is a PM-gated process step, not part of the AC. **Review medium**: coach reviews against a **print-ready output rendered at the exact 4.25"×5.5" quarter-letter geometry** (PDF or screenshot at print resolution) — NOT a browser preview at default zoom, which exaggerates typography legibility and hides print-scale problems. SE produces the print-ready sample as part of this story; the routing message to coach explicitly identifies the medium. **Coach legibility minimums** (per coach MN-2): pill jersey numbers ≥7–8pt, compass letters ≥7–8pt, simple field outline (no texture). Fold-line consideration: if folded landscape mid-card, the fold runs through the field-diagram body — coach's review verdict captures whether this is workable. Coach reviews the typography minimums in context.
- [ ] **AC-9**: **Two-blank-slots filled** per UXD I-2 (user-confirmed during incorporation):
  - **Slot 3 (sheet 2 position 3): Visual compass key** — a mini diagram showing the 8-zone compass on a blank field with the letters labeled A-H and the "in/deep/left/right" axes annotated. Complements the one-line legend on every card.
  - **Slot 4 (sheet 2 position 4): Opponent context card** — opponent name (large), coverage cue, record / runs-per-game / runs-allowed-per-game (if available from existing scouting data), team total BIP count + tier label ("full" / "thin").
  Both slots render at the same 4.25"×5.5" geometry as the player cards (same template family).
- [ ] **AC-10**: **Retire the v1 categorical renderer surface in `src/reports/renderer.py`.** E-229-02's Technical Approach defers the renderer-side cleanup of the v1 vocabulary block to this story (the engine retires its own vocabulary references and writes no categorical columns; the renderer still references them via the old card-building path). This story owns:
  - **Delete the v1 vocabulary block**: `POSITIONING_CALL_WORDS`, `POSITIONING_CELL_SHORT_FORMS`, `POSITIONING_COLUMN_ORDER`, and `POSITIONING_POSITION_LABELS` (four module-level constants at ~lines 67-110 of `src/reports/renderer.py`). No relocation — E-229-03's `COMPASS_LEGEND_SHORT` lives in the card-SVG module, not as a successor to this block.
  - **Retire or rewrite `_build_positioning_context()`** (and any helper exclusively consumed by it) so it no longer reads from the retired columns or the deleted vocabulary block. The new template consumes a context shape built from the v2 row set (`zone_id`, `is_thin`, `bip_count`, `is_low_confidence`, deviations) plus the per-position SVG produced by E-229-03 + outlier pills from E-229-04. Helper-function structure is SE's call.
  - **`grep` AC** (verified by code review): after this story lands, the strings `POSITIONING_CALL_WORDS`, `POSITIONING_CELL_SHORT_FORMS`, `POSITIONING_COLUMN_ORDER`, `POSITIONING_POSITION_LABELS`, `call_state`, `team_state_call`, `direction_shade`, `depth_shade`, and `zone_concentration` MUST NOT appear in `src/reports/renderer.py`.
- [ ] **AC-11**: **xfail-marker clearance.** After this story lands, NO `@pytest.mark.xfail` marker citing `E-229-05` may remain in `tests/test_report_renderer.py` or `tests/test_report_generator.py`. E-229-02 AC-10(f) permitted SE to xfail-mark assertion-side tests that depended on render-layer logic landing in this story; this story closes the loop. Each such test is resolved in exactly one of three ways:
  - **Update the assertion** to the new v2 / new-template shape if the test is still meaningful.
  - **Delete the test** if it is fully superseded by tests added in this story or by upstream tests in E-229-02/03/04.
  - **Re-xfail with a different reason** ONLY if the test depends on a *different* downstream story (e.g., E-229-08 bundle generation or E-229-09 LLM contract) — that requires a fresh `reason="re-enable in E-229-NN"` citing the correct downstream story. A re-xfail citing E-229-05 is not allowed.
  - **`grep` AC** (verified by code review): `grep -E 'xfail.*E-229-05' tests/test_report_renderer.py tests/test_report_generator.py` returns no matches.

## Technical Approach

**Template surface**: modify `src/api/templates/reports/positioning_cards.html` substantially. E-228's 2×3 grid layout is retired; the new template uses a 2×2 grid per page with explicit page breaks between sheets. Two letter pages total for cards: sheet 1 (LF/CF/RF/3B) and sheet 2 (SS/2B + 2 slots).

**Card partial**: consider extracting a single-card partial `src/api/templates/reports/_card.html` if it helps E-229-06 (prep page) reuse the SVG rendering. E-228's renderer.py may already follow this pattern.

**Print CSS structure**:
```css
@page positioning-cards { size: letter portrait; margin: 0.25in }
.cards-page { display: grid; grid-template-columns: 1fr 1fr; grid-template-rows: 1fr 1fr; gap: 0; page-break-after: always; }
.card { width: 4.25in; height: 5.5in; padding: 0.15in; ... }
.card-header { ... }
.card-body { display: flex; ... } /* SVG + sidebar */
.card-legend { ... }
```
Cut-line indicators via `border` styles on midlines.

**Compact field SVG sizing**: at 4.25"×5.5" with header + legend taking ~1.5" vertical, the body area is ~5.5"×4". A 60/40 SVG/sidebar split gives the SVG ~3.3" wide × 4" tall. E-229-03's SVG must scale cleanly to this size — verify before locking the template.

**Sheet-2 slots 3+4 layout**: locked during Phase 3 iteration 1 to compass-key (slot 3) + opponent-context-card (slot 4) per AC-9. Implementation details for each (the compass-key diagram + axes annotation; the opponent-context-card content list) are defined in the locked-constants artifact section D (per E-229-2b) and consumed by this story at impl time.

**Coach design review process**: when the template is ready, package a quarter-letter print sample (HTML rendered + printed or screenshot at quarter-letter scale) and route to baseball-coach. Coach reviews against the design questions from epic Background: is the field plot legible at this size? Does the sidebar lookup support the in-game workflow? Does the legend obviate the "what am I looking at" tax? Coach produces a written verdict (PASS / FAIL with failure points). Verdict goes in this story's Notes.

**Mobile responsive**: Tailwind `flex-col md:flex-row` on the card body. Test at 375px viewport width.

## Dependencies
- **Blocked by**: E-229-04 (the field SVG with outlier pills is the content this template wraps), E-229-2b (locked layout constants from feasibility prototype)
- **Blocks**: E-229-08 (bundle generation needs the card template to assemble the 4-page bundle)

## Files to Create or Modify
- `src/api/templates/reports/positioning_cards.html` — modify (substantial; new 4-up layout)
- `src/api/templates/reports/_card.html` — create, optional (single-card partial for reuse)
- `tests/test_positioning_card_template.py` — create or extend (layout snapshot + state variants + mobile responsive)
- `src/reports/renderer.py` — modify (delete the v1 vocabulary block + retire/rewrite `_build_positioning_context()` per AC-10; both per epic TN-13 + E-229-02 deferral)
- `tests/test_report_renderer.py` — modify (clear all `xfail` markers citing E-229-05 per AC-11; update or delete the underlying tests)
- `tests/test_report_generator.py` — modify (clear all `xfail` markers citing E-229-05 per AC-11; update or delete the underlying tests)

## Agent Hint
software-engineer

<!-- Re-routed from ux-designer to software-engineer during Phase 4 iteration 2 incorporation per Codex P2.7 + claude-architect verification. Rationale: file list (Jinja2 templates under `src/api/templates/` + pytest under `tests/`) is unambiguously SE territory per `.claude/rules/agent-routing.md` file-path-deterministic routing. UXD-only design exploration lives in E-229-2b (paper mockup + locked-constants artifact); E-229-05 implements per those locked constants. Coach design-review AC (AC-8) is a quality gate — SE renders template, captures print-preview, PM routes to coach for verdict (E-228-04 precedent). Pattern: "When design exploration and template implementation are both required, split into separate stories. UXD owns the spec/feasibility story; SE owns the implementation story." -->


## Handoff Context
- **Produces for E-229-08**: a complete card template that renders 4-up portrait pages. E-229-08's bundle assembler stitches 2 card pages (sheet 1 + sheet 2) into the 4-page PDF after the landscape call sheet and prep page.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
- [ ] Baseball-coach design-review record present in Notes (per AC-8)

## Notes

- **Two-blank-slots decision** (per AC-9): LOCKED during incorporation per UXD I-2 + user confirmation: slot 3 = visual compass key, slot 4 = opponent context card. Both render in the same card template family. Implementation details (the visual compass key's layout, the opponent context card's content list) are this story's design call.
### Coach design review record (per AC-8)

**Verdict**: PASS (transitive validation per user decision 2026-05-17)

**Review medium**: Transitive validation via E-229-2b's LOCKED v1.2 constants (PASS'd by coach AC-12 on 2026-05-17 against the quarter-letter prototype HTML at `.project/research/E-229-2b-quarter-letter-prototype.html`). E-229-05's `src/api/templates/reports/positioning_cards.html` template implements those constants verbatim: card geometry per artifact §A (4.25"×5.5" outer, 0.15" padding, 4-up sheet), typography per §C and §E (≥7pt floor on legend; 9pt pill text; 10pt compass letters; 7.5pt sidebar), sheet-2 fill content per §D (visual compass key in slot 3 + opponent context card in slot 4), shared design tokens per §F (`COMPASS_LEGEND_SHORT`/`LONG` text, greyscale palette, font family `Arial, Helvetica, sans-serif`). No deviation from the validated visual.

**Review path**: User accepted SE's transitive-validation reasoning rather than requiring a fresh print-ready sample at 4.25"×5.5" geometry. The locked constants ARE what coach reviewed and approved during E-229-2b AC-12; E-229-05's template implementation matches without deviation. SE's transitive argument (template implements LOCKED v1.2 constants verbatim → coach's E-229-2b verdict structurally carries forward) was accepted by the user as the AC-8 record.

**Print-ready sample**: NOT produced for this story. The E-229-2b prototype HTML at `.project/research/E-229-2b-quarter-letter-prototype.html` is the reference print-ready artifact that locks the typography minimums (≥7pt floor) and dugout-glance legibility. E-229-05's template output renders the same visual at the same geometry.

**Calibration follow-up**: if the first-real-opponent calibration pass (epic Rollout) surfaces visual issues the transitive validation didn't catch (e.g., legibility regression from template structure differences vs. the prototype HTML — render path divergence under the bundle PDF pipeline, font fallback drift on a different print server, etc.), the fix lives in E-229-05's template + optionally an artifact constants update at v1.3+. This is a Rollout-note item, not a shippability gate for E-229-05 closure.

**Date**: 2026-05-17
