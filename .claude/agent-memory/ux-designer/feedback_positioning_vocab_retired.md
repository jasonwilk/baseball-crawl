---
name: positioning-vocab-retired
description: E-228 categorical positioning vocabulary (POSITIONING_CALL_WORDS, SHADE LEFT / MIXED / LEFT_SHALLOW, call_state, team_state_call, direction_shade, depth_shade, zone_concentration, per-position glyphs) was retired wholesale in E-229. Do not cite or propose in new designs.
metadata:
  type: feedback
---

Do not cite, propose, or design around the E-228 categorical positioning vocabulary. It was retired wholesale in E-229.

**Retired identifiers (do NOT reintroduce):**
- `POSITIONING_CALL_WORDS` (the dict in `src/reports/renderer.py`)
- `call_state`, `team_state_call`, `direction_shade`, `depth_shade`, `zone_concentration` (engine fields)
- Categorical labels: "SHADE LEFT", "MIXED", "LEFT_SHALLOW", "STANDARD", per-position glyphs
- The "shade {direction} {depth}" call-text shape generally

**Why:** E-228 shipped a categorical vocabulary baked into both the engine (stored enum keys) and the render layer (display words dict). E-229 retired it wholesale — the rationale lives in `.claude/rules/positioning-vocabulary.md`. The current model is the 8-zone compass + "in/deep" vocabulary, but positioning calls are PURELY VISUAL in the rendered artifact (star on field, outlier dots with zone letters). The chart IS the call. No text caption.

**How to apply:**
- When designing any positioning UI/surface, do NOT propose per-card "call text" lines, "Shade left shallow"–style captions, or any text translation of a star's location.
- The position label (LF/CF/RF/3B/SS/2B) is permitted as a card heading. The outlier list is permitted as a per-batter override list. The COVERAGE CUE (Through {date} · N games · M BIP) is permitted as a section-level data-depth annotation. No third text layer.
- If a future epic needs vocabulary work, that is a separate epic with coach consultation — never inline-design new positioning vocabulary inside a layout epic.
- Before citing `POSITIONING_CALL_WORDS` or any of the retired identifiers from memory, grep `src/` to confirm — if hits are only in historical comments, the vocabulary is gone.

**Origin:** E-230 planning, 2026-05-19. UXD proposed per-card call-text using `POSITIONING_CALL_WORDS`, citing E-228 from memory. PM caught it in consult before spec review — would have reintroduced the regression. The lesson: grep before citing dicts/constants from prior epics in active vocabulary domains.

**Source of truth:** `.claude/rules/positioning-vocabulary.md` is the authoritative reference for current positioning vocabulary and what was retired.

Related: [[design-principles]] (the engine-vocabulary-agnostic principle is the architectural reason the retired vocabulary cannot return inline).
