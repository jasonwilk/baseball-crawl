---
name: Consistency sweep must grep concept words, not just code syntax
description: When sweeping for a locked-concept rename, grep both the code-syntax pattern AND the concept word as bare prose; syntax-only grep misses AC body prose
metadata:
  type: feedback
---

When PM runs the Phase 3/Phase 4 post-incorporation consistency sweep, the grep targets MUST include both the **code-syntax pattern** (function call shape, column name in code, variable check) AND the **concept word as bare prose** (the rename token spelled out in English in AC bodies, Technical Approach paragraphs, and Notes sections). Syntax-only grep misses prose drift.

**Why:** During E-229 Phase 3 iteration 1, PM swept for the locked `batting_order` → `alphabetical-only` rename by grepping syntax patterns like `batting_order is not None` and `any(row.batting_order` — both returned 0 occurrences, and PM declared the sweep clean. Codex Phase 4 review (P1.3) then found E-229-06 AC-4 still said "batting-order with alphabetical fallback" — the prose used the concept word "batting-order" without any code-syntax token, so syntax grep missed it. Same class of miss caught Codex P2.4: the locked page-4 slot fill (`blank | blank` → `compass-key | opponent-context-card`) survived in TN-12 + E-229-08 AC-1 prose because the syntax-only sweep didn't grep for the bare "blank slot" / "blank | blank" prose patterns.

**How to apply:**

1. **For every locked-concept rename in the sweep's Sub-step A change list, generate TWO grep patterns**:
   - The code-syntax pattern: function calls, variable checks, column names with surrounding code tokens (e.g., `\.batting_order`, `batting_order INTEGER`, `is not None`)
   - The concept word as bare prose: the rename token spelled out as English (e.g., `batting.order`, `batting-order`, `batting order`, `blank.slot`, `0\.6.*aspect`, `compass.key`)

2. **Run BOTH greps in Sub-step B**. A clean sweep requires both to return 0 occurrences (or only-in-retract-context occurrences).

3. **The high-risk surfaces for prose drift are**:
   - AC body prose (especially conditional clauses: "if X is populated, sort by Y; fallback to Z")
   - Technical Approach paragraphs (where PM cites the prior design decision in plain English)
   - Notes sections (free-form prose carrying historical context)
   - Epic Technical Notes paragraphs (where the concept is explained in narrative form)

4. **Cheap pattern when in doubt**: grep the unique English bigram or trigram that names the concept. E.g., `batting order`, `blank slot`, `upper-left`, `byte-identical`. If the bigram returns occurrences in retired-context locations, those need to be fixed in the same pass.

5. **Maintain the sweep change list in two columns**: the syntax pattern + the concept-word pattern. Both must be checked.

6. **If a sweep reports "clean" but a subsequent reviewer finds prose drift in the same area**: this is the smoking gun — the sweep used the wrong grep target. Update the sweep methodology in this memory + this iteration's plan + the next iteration's plan.

The plan skill's Phase 3 Step 6 + Phase 4 Step 6 consistency-sweep gate is the place this discipline lives. Both phases run the same sweep procedure; both must apply the dual-grep methodology.

This applies to any future epic where Phase 3 / Phase 4 incorporation renames a concept across multiple stories.

## Extension: cross-grep artifact-vs-stories for "single source of truth" artifacts (E-229 iter-3 lesson)

When an epic introduces an artifact that downstream stories CITE as the single source of truth (e.g., `/.project/research/E-229-locked-layout-constants.md` — formula constants, design tokens, legend strings), the consistency sweep MUST cross-grep:

- **Every formula** that appears in the artifact's text (e.g., projection formulas, expressions with variables)
- **Every constant name** the artifact defines (e.g., `COMPASS_LEGEND_SHORT`, scaling factors)
- **Every verbatim string** the artifact specifies (e.g., legend text, format strings, sample-data strings)

For each, grep ALL citing stories (and the epic file's Technical Notes) to confirm the artifact's value matches the story's reference verbatim. **The artifact is canonical**; if the story has a different value, the bug is in the artifact (drift goes artifact → story, not the other way).

**Why:** During E-229 Phase 4 iteration 2, PM created the locked-constants artifact stub and self-grep'd it for internal consistency (PROVISIONAL/LOCKED state machine, path references, sample-data references) — all clean. But Codex iteration 3 caught two drifts where the artifact's content disagreed with the stories that cited it:
- The compass-ring projection formula in the artifact omitted `scale_x`/`scale_y` factors that epic TN-15 + E-229-03 AC-4 specified verbatim
- The `COMPASS_LEGEND_SHORT` constant in the artifact omitted the `(see right)` suffix that epic.md + E-229-03 specified verbatim

The internal-only sweep missed these because the drift wasn't word-level inside the artifact — it was a mismatch between the artifact and its consumers. Both files were internally consistent; the gap was between them.

**How to apply:**

1. **When the consistency sweep runs after incorporation involves an artifact citation pattern**, enumerate the artifact's content section by section: each formula, each named constant, each verbatim string.
2. For each item, grep ALL citing files (the epic file's Technical Notes for the canonical spec, plus every story that references the artifact). The artifact's value must appear verbatim in EVERY citing file.
3. If a mismatch is found, the artifact is wrong by default (downstream stories trust the artifact, so it must match what they cite). Fix the artifact.
4. Add this artifact-vs-stories cross-grep as a separate Sub-step E in the consistency sweep checklist for any iteration where an artifact citation pattern is in play.

The discipline scales beyond E-229: any epic that introduces a single-source-of-truth artifact (research doc, schema spec, shared API contract) needs the same cross-grep when the artifact is incorporated and again whenever the artifact or its consumers change.

This methodology gap was caught by Codex iter-3 P1.3 in E-229 (2026-05-17). Two specific drifts found; both PM-owned (introduced when PM wrote the artifact stub during iter-2 incorporation).

## Extension: when accepting a rename, grep every English variant of the OLD concept (E-230 Phase 4 CX4 lesson)

When the consistency sweep follows a finding that retires an OLD concept and replaces it with a NEW concept (e.g., E-230 SE F4 retired "byte-equality" in favor of "content-level parity"), the grep targets must include **every plausible English variant of the OLD concept**, not just the literal phrase named in the finding.

**Why**: During E-230 Phase 3 incorporation, PM accepted SE F4 (AC-9 reframed from byte-equality to content-level slot-fill) and swept for `byte-equality|byte equality` — clean. Codex iter-1 (P1 CX4) then found 4 surviving instances of `byte-identical` and `byte-for-byte identical` across the epic and Story 2. The sweep used the literal phrase from the SE finding rather than enumerating the variants of the retired concept. All 4 instances were genuine drift that contradicted the AC the sweep was supposed to protect.

**How to apply**:

1. **When accepting a rename finding, list every plausible English variant of the OLD concept before sweeping**. For "byte-equality" the variants include: `byte.equality`, `byte equality`, `byte.identical`, `byte-identical`, `byte.for.byte`, `byte-for-byte`. For "render_field_svg" the variants include: `render.field.svg`, `inline SVG`, `SVG renderer`. Cast wide.

2. **Run a single grep with all variants OR-joined**. Use ripgrep's regex syntax: `byte.identical|byte.for.byte|byte.equality|byte equality`. If any returns occurrences in retired-context locations, fix in the same pass.

3. **The high-risk surfaces for variant survival are** (same as the prose-drift list above):
   - Epic Goals / Non-Goals (where the old concept was named as a guarantee)
   - Success Criteria (where the old concept was a deliverable)
   - Story Description / Context paragraphs (where the old concept was set up as a contract)
   - Files-to-Modify notes (where the old concept named the test or file)

4. **Rule of thumb**: a finding that names ONE phrasing of a retired concept means the concept's English variants are all suspect. Sweep for the variants before declaring the rename complete.

This methodology gap was caught by Codex iter-1 CX4 in E-230 (2026-05-19). Four specific drifts found; all PM-owned (the original synthesis used multiple English variants of "byte-equality" and the Phase 3 sweep only matched two of them).
