---
name: design-competition-level-disclosure
description: Design pattern for disclosing engine-detected classification (competition level) on the scouting report -- three-state model, point-of-use placement, provenance-as-soft-qualifier
metadata:
  type: project
---

Full spec: `.project/research/2026-07-25-uxd-competition-level-disclosure-design.md`
(design-only, not yet implemented as of 2026-07-25; feeds a successor to E-274-03
/ IDEA-177, likely folded into E-275).

## Durable pattern (reusable beyond this one feature)

When a report discloses an ENGINE CLASSIFICATION that only drives one downstream
computed section (not a report-wide fact), disclose it **at the point of use**,
not in the footer trust block and not as new masthead real estate. The footer
trust block (`trust-block` / `.trust-quiet` / `.trust-flagged` / `.trust-loud`)
is a DIFFERENT epistemic axis -- data currency/coverage -- from a classification
confidence disclosure. Don't blur the two into one block just because both are
"trust surfaces."

**Three-state honest-absence model, reusable pattern:**
1. **Bound** -- system produced a real result; show it plainly, low visual
   weight (sublabel/tag-line, not a boxed callout).
2. **Recognized, no output built** -- deliberate boundary, not a data gap. Bold
   the SPECIFIC recognized thing (never a generic placeholder) at the start of
   the note.
3. **Genuinely unresolved** -- system limitation, no specific fact to show.

States 2 and 3 share ONE visual container (reuse `.trust-quiet`'s slate tone:
bg `#f1f5f9`, text `#475569` -- already established on this report for "honest
disclosure, not error") -- the differentiator between them is COPY/bolding, not
color. Giving state 2 a warmer/louder color than state 3 misreads as "found a
problem" when neither is an error. This directly extends
`.claude/rules/display-philosophy.md`'s carve-out (the starter card's suppress
state is "an honest absence of a projection, not the hiding of present data")
to a second engine field on the same card.

**Provenance disclosure -- the resolved middle path.** When a coach might
reasonably want to know WHICH signal decided a classification (structured field
vs. a fragile fallback like name-keyword matching), don't expose raw internals
(field names, regex sources -- that's a debug view) and don't suppress the
distinction entirely (loses real trust value). Instead: a single soft qualifier
in coach language ("from team name") appended ONLY when the fallback path won;
say nothing when the confident/structured path won (silence = default = trust).
One bit of signal, translated, not a provenance trail.

## Update 2026-07-25b: split "what is this team" from "what rules apply"

When an operator/domain ruling collapses two previously-distinct engine outputs
onto the same rule table (here: NRBL declared "essentially Legion rules" for
pitch-count purposes, confirmed byte-identical `PitchCountRules` in
`starter_prediction.py`), don't let that collapse also erase the LABEL
distinction the domain expert still considers real. The tell: the operator's own
phrasing keeps naming both things separately ("summer reserve is NRBL... [but]
essentially legion rules") even while ruling the computation should be shared.

Pattern: split the single label field into **`rules_label`** (names the table
that computes the numbers below) and **`level_label`** (names the finer
scouting-fact tier, computed independently of which table won — reusing
whatever signal-detection logic already exists for the SUPERSEDED
precedence-change proposal, just repurposed as a display-only overlay that
never touches resolution). Render ONE line when they coincide, TWO when they
diverge. This is a materially lower-risk ask than the precedence change it
replaces, because it never touches which rule table gets applied — pure
display-layer reuse of an existing signal.

Don't over-generalize the two-field split reflexively to every "the enum
doesn't distinguish X from Y" case in the same session — check first whether a
genuine discarded SIGNAL exists to recover (Legion/NRBL: yes, a bracket/name
word is discarded by ngb precedence) or whether the source data structurally
lacks the distinction (HS Freshman/Reserve, IDEA-177: GC's own `age_group` enum
has no Reserve value at all — nothing is being discarded, there's nothing to
recover). Only the first case gets the two-field treatment; naming the parallel
to PM is good design coherence, but bundling the two into one implementation
decision blurs two separate rulings (mirrors IDEA-178's own note about not
folding into E-274).

## Update 2026-07-25c: "narrower scope" is not "still accurate" — check the copy against its own cited source

I first wrote off a banner-copy question ("its existing copy is still accurate
for the narrower surviving case") without checking the claim the copy itself
makes against the rule file it's describing. It was wrong: the banner said
"this level doesn't publish pitch-count rules," and `pitch-rules.md` names the
fallback curve `PITCH_SMART_15_18` — a curve named for a BAND only makes sense
if other bands exist, which they do, so the banner's premise was false even in
the narrowed case, just for a weaker reason (declining to pick a band within an
ambiguous range, not lacking a guide entirely). Lesson: when a scope-narrowing
event (a suppression fix, a population shrink) makes a copy claim's AUDIENCE
smaller, that says nothing about whether the copy's PREMISE is still true for
the survivors — re-derive the claim against its cited source, don't infer
accuracy from "there's less of it now."

## Related

[[design_principles]] (Consequence-Oriented Labels -- this pattern is an
extension: tell the coach what they get / what's true, not which code path
fired). See also `.claude/rules/display-philosophy.md` for the "Never suppress,
always contextualize" principle and its starter-card carve-out this pattern
extends.
