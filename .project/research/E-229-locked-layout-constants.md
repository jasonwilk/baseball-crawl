---
status: PROVISIONAL
version: 0
produced_by: E-229-2b (pending — flips to LOCKED v1 on AC-12 coach sign-off per E-229-2b AC-2)
calibration_history: []
---

# E-229 Locked Layout Constants

This artifact is the single source of truth for E-229's per-card layout constants, design tokens, and shared rendering rules. Downstream stories (E-229-03 card field SVG, E-229-04 outlier pills, E-229-05 compact card template, E-229-06 prep page, E-229-07 call sheet, E-229-08 bundle) consume the values here at implementation time per epic TN-16 design-tokens citation pattern, and MUST NOT hardcode them in story ACs or in source code outside this artifact's adoption sites.

## State machine

- **PROVISIONAL v0 (this state, created during E-229 Phase 4 iteration 2 PM-side incorporation)**: UXD round-1 / round-2 estimates as initial values. Downstream stories CITE this artifact path in their ACs but MUST NOT consume the v0 values for production implementation. SE waits for the LOCKED v1 flip.
- **LOCKED v1 (set by E-229-2b AC-2 + AC-12 on coach PASS verdict)**: values validated at print scale via the quarter-letter feasibility prototype; coach legibility review passed. Downstream implementations consume these values directly. Decisions Log section populated with 6–10 actual decisions (per E-229-2b AC-10) showing alternatives tried + rejection rationale.
- **LOCKED v2+ (Rollout calibration)**: real-opponent feedback during the calibration pass (epic Rollout section) may bump version and append to `calibration_history` with an entry of shape `{date, opponent, changed_constants[]}`.

Cross-reference: see `.project/research/E-229-2b-quarter-letter-prototype.html` (the static prototype HTML produced by E-229-2b) for the visual proof of these constants at print scale.

---

## A. Card geometry (per UXD B-1)

| Constant | v0 value | Notes |
|----------|----------|-------|
| Card width | 4.25 in | Quarter-letter portrait |
| Card height | 5.5 in | Quarter-letter portrait |
| Card padding | 0.15 in | Internal margin on all 4 sides |
| Body area (computed) | 3.95 in × 5.2 in | Card minus padding × 2 |
| Header height | 0.7 in | Opponent name + position name + coverage cue |
| Legend height | 0.25 in | One-line legend at bottom |
| Body inner area (computed) | 3.95 in × 4.25 in | Body area minus header + legend |

## B. SVG field diagram (per UXD B-1 + DE TN-15 coord convention)

| Constant | v0 value | Notes |
|----------|----------|-------|
| SVG aspect ratio (W/H) | 0.6 | Portrait; UXD round-1 estimate; accept 5% letterbox to preserve GC field geometry |
| SVG/sidebar split (% of body inner width) | 64 / 36 | SVG slot ~2.53 in wide × 4.25 in tall at the v0 aspect |
| SVG canvas pixels (W × H) | 320 × 480 | Matches `src/charts/spray.py` canonical layout |
| Y-axis convention | y=0 at deep CF; y increases toward home | Reference: `src/charts/spray.py:47, 480`; epic TN-15 |
| X-axis convention | x=0 at LF foul; x increases toward RF | Reference: `src/charts/spray.py` |
| Pill projection formula | `pill_x = star_x + dir_dev * scale_x; pill_y = star_y + (-depth_dev) * scale_y` | Per epic TN-15; tested by E-229-04 AC-8 coord-regression test |
| Compass-ring projection formula | `letter_x = star_x + sign(dir) * scale_x * R; letter_y = star_y + (-sign(depth)) * scale_y * R` | Per epic TN-15 + E-229-03 AC-4 (scale factors required to match story specs; drift fixed in Codex iter-3 P1.3) |
| `R` (compass ring radius) | 75–85% of available radius from star to field edge | Outer-edge placement per UXD B-3; edge-clamped to field outline per UXD I-4 |
| `scale_x`, `scale_y` (pill projection units) | TBD by E-229-2b | UXD round-1 had no explicit value; needs calibration at quarter-letter print |

## C. Card frame elements (per UXD)

| Constant | v0 value | Notes |
|----------|----------|-------|
| Star marker style | Solid filled star, ~12pt | Full tier; per epic TN-4 |
| Star BIP-count caption | "(N BIP)", 6–7pt, below or beside star | All tiers where star renders (per coach BC-3) |
| Star thin-data badge | Dashed ring around star, OR "(~N BIP)" caption | Thin-data tier (15–49 BIPs) per epic TN-4 |
| Textbook reference dot | Open outlined circle, no fill, 1pt stroke, 30–40% grey, no label, smaller than star | Per UXD round-1 + epic TN-3 |
| Spray-density background | Single-channel grey dots, ~15% opacity max, no play-type differentiation | Hidden when `is_low_confidence = 1` |
| Compass letter (populated) | 10pt bold capital, black text on 0.18" diameter 20%-opacity grey filled circle | Full opacity |
| Compass letter (empty) | Same shape, ~30% opacity (faint placeholder) | Stable visual language per coach MN-1 + UXD I-4 |
| Pill style | White fill, 0.5pt grey border, 9pt bold black text, ~0.18"×0.14" min, 2pt corner radius | UXD I-3 v0 estimate; auto-width by content |
| Pill text format | `#<jersey> <truncated-last-name>` (≤6 chars) | Per UXD M-4; fallback last-initial when jersey is NULL |
| Cut lines | 0.5pt dashed (2pt/2pt), 50% grey, midlines only; no corner crops, no full-card borders | Per UXD M-3 |

## D. Sheet-2 fill content (per UXD I-2 + Codex P2.4)

Page 4 of the 4-page bundle holds positions SS and 2B in slots 1 and 2 of the 4-up grid; slots 3 and 4 are filled (not blank) with:

| Slot | Content | Layout notes |
|------|---------|--------------|
| 3 | **Visual compass key** | Mini diagram showing the 8-zone compass on a blank field; letters A–H labeled; "in/deep/left/right" axes annotated; renders at the same 4.25"×5.5" card geometry as the player cards. Coach-facing reference, kept by coach. |
| 4 | **Opponent context card** | Opponent name (large header), coverage cue, record / runs-per-game / runs-allowed-per-game (if available from existing scouting data), team total BIP count + tier label ("full" / "thin"). Same 4.25"×5.5" geometry. Coach-facing, kept by coach. |

## E. Typography parity across all three artifacts

| Surface | Element | v0 value |
|---------|---------|----------|
| Card (E-229-05) | Header | 11pt regular |
| Card | Coverage cue | 9pt regular, right-aligned |
| Card | Legend | 7pt |
| Card | Sidebar lookup row | 7pt monospace |
| Card | Pill | 9pt bold |
| Card | Compass letter | 10pt bold |
| Card | Star BIP caption | 6–7pt regular |
| Prep page (E-229-06) | Header | 13pt regular (larger; single-page artifact) |
| Prep page | Pill | 9pt bold (matches cards) — format `7-LF` (no `#`, hyphen separator) per UXD M-2 |
| Prep page | Sidebar matrix row | 7pt monospace (matches cards) |
| Call sheet (E-229-07) | Jersey column | 11pt bold (visually prominent per UXD I-7) |
| Call sheet | Name column | 9pt regular |
| Call sheet | Zone-letter cell | 9pt regular |
| Call sheet | Legend | 9pt regular (one line at top) |
| Call sheet | Header / coverage cue | 11pt regular / 9pt regular right-aligned |

### Rationale typography (Tier 2 LLM display, per Codex iter-3 P1.2 + UXD lock)

Single spec applies to both prep page (E-229-06 AC-10) and call sheet NOTE column (E-229-07 AC-1):

| Constant | Value |
|----------|-------|
| Font family | Same body font stack (single across artifacts) |
| Style | Italic |
| Size | 8pt |
| Color | 50% grey (§F greyscale palette) — soft contrast vs 100% black structural data |
| Max lines | 2 (CSS `-webkit-line-clamp: 2`) |
| Overflow | Hidden, no ellipsis |
| Empty/None render | Renders nothing (collapsed); no placeholder text |

**Audience split** (per UXD): rationale displays on coach surfaces (prep page + call sheet) but NOT on fielder surfaces (player cards). Cards' sidebar (~1.4" wide) cannot accommodate readable rationale without dropping below 7pt, and fielders don't need rationale at-glance; cards answer "where do I stand?" — rationale is secondary context for coach.

**Sizing rationale**: E-229-09 AC-2 caps rationale at 10–50 words (≈ 60–300 chars); CSS 2-line clamp at the actual column widths (prep-page sidebar second-line + call-sheet NOTE column ~2.2") accommodates ~140–180 chars with graceful overflow. UXD rejected 80-char ellipsis as too aggressive (chops mid-sentence; loses specificity).

**Rejected alternatives** (record per UXD): footnotes with numbered refs (forces lookup — exactly the cognitive cost being avoided); hover/tooltip (print loses it; artifact is print-primary); inside the SVG (cramped, fights markers/density bg).

## F. Shared design tokens

| Token | Value |
|-------|-------|
| Font family stack | (TBD by E-229-2b — propose `system-ui, -apple-system, "Helvetica Neue", sans-serif` for readability at small sizes; refine if dugout-printer rendering surfaces issues) |
| Greyscale palette | 0% (white), 15% (lightest), 30% (faint placeholder), 50% (cut lines), 70%, 100% (black) |
| Coverage-cue format string | `Through {Mon Day} ({N} games)` (full format restored per coach IM-2 + user lock; game-count snapshot persisted at bundle-generation time per E-229-08 AC-4a) |
| Legend constant — SHORT (cards) | `★ team default · ○ textbook · A–H = outlier zones (see right)` |
| Legend constant — LONG (call sheet, prep) | `A in-left · B left · C deep-left · D in · E deep · F in-right · G right · H deep-right · · = team default` |
| Color-not-load-bearing rule | All information (zone identity, confidence tier, batter identity) communicated by shape, position, or text. Color decorative only. (Per UXD I-6 + epic TN-16) |

## G. Mobile / web responsive (per UXD I-5)

| Constant | v0 value | Notes |
|----------|----------|-------|
| Breakpoint | 640px (Tailwind `sm:`) | NOT `md:` (768px) per UXD I-5 fix |
| Layout ≤640px | Single-column vertical: SVG full-width (aspect ratio preserved) → sidebar below at full-width → header and legend always full-width | Stacks vertically |
| Layout >640px | Side-by-side per A/B values above | Standard layout |

## Decisions log

*(populated during E-229-2b prototype work; record each locked value + rejected alternatives + 1-line rationale per UXD recommendation)*

### Example template (delete after first real entry)

```
### SVG aspect ratio: 0.6
- Tried 0.5: foul-line angles too narrow; home plate area below readable detail
- Tried 0.67 (GC native): forces sidebar < 1.3" — name truncation too aggressive
- 0.6 = best balance
```

---

## Frontmatter usage notes

- `status: PROVISIONAL` (v0) = downstream stories SHOULD NOT yet hardcode these values; consume after `LOCKED` flip
- `status: LOCKED` (v1+) = artifact is authoritative; downstream stories consume directly
- `version` bumps on each material change; old versions are not preserved here (per E-228 archive precedent, history lives in commit log)
- `calibration_history` is a list of `{date, opponent, changed_constants[]}` entries appended during Rollout
- `produced_by` documents the story that flipped status to LOCKED (E-229-2b at v1; later epics if any constant materially changes)
