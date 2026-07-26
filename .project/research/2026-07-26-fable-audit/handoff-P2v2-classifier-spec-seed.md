# P2 (v2) — Classifier precedence fixes: SPEC-SEEDED handoff

Supersedes handoff-P2-classifier-precedence.md (the plan-shaped version). This is
the spec-seeded form per the audit's A4/C1 amendment: discovery is done and cited;
the receiving session VERIFIES rather than re-derives. THIS SEED IS A RELAY — every
code claim below must be resolved against the repo before an AC pins it; the file
wins. Provenance tags: [EXECUTED] = demonstrated by a run whose harness/report is
cited; [READ] = code reading, verify by execution before pinning; [GATE] = decision
belonging to a named authority.

## Operator decision points, FIRST (route before stories firm up)

D1 [GATE: baseball-coach] The precedence ruling: when a team name carries BOTH a
   Legion word and a level word ("American Legion Varsity", "Post 12 Varsity"),
   which wins? Today `\bvarsity\b` (index 4, `_LEVEL_WORD_PATTERNS`,
   starter_prediction.py:309-312 region) precedes all three Legion patterns
   [EXECUTED: audit-starter 2026-07-25 — season-absent these resolve
   nsaa_varsity, summer -> legion]. Season-absent NSAA under-rests vs LEGION at
   46-50/61-70/81-90 (81-105 pre-April: NSAA_PRE_APRIL has no tier above 90)
   [EXECUTED: _is_excluded driven at every count 1-90]. Do NOT reorder before
   this ruling. Read `.claude/agent-memory/baseball-coach/
   e275-classifier-hardening-rulings.md` first — do not re-litigate settled
   rulings.
D2 [GATE: operator] Scope: fix-only (finding 1 + tripwire) vs bundle the
   adjacent MINORs (below). Recommendation: fix-only + tripwire + fixture pack;
   MINORs ride only if coach/SE endorse each in one round.

## Finding 1 — varsity shadows the Legion words (live, under-rest direction)

Fix shape after D1: reorder or context-qualify the Legion patterns ahead of
`varsity` for names carrying both. The docstring at :368 ("Legion-specific words
are season-independent") is FALSE for these names [EXECUTED] — correct it in the
same story (prose-with-behavior rule).
ACs the seed proposes (PM refines): (a) the three shadow names resolve per D1
ruling in both seasons — fail-first against current code; (b) ground-truth
fixture pack (below) green; (c) docstring corrected.

## Finding 2 — LEGION == NRBL divergence tripwire

A few-line test asserting the LEGION (starter_prediction.py:188-197) and NRBL
(:208-217) constants byte-equal [EXECUTED: verified byte-identical 2026-07-25],
failing loudly on divergence — the activation trigger IDEA-178's contingency
needs (`.claude/rules/pitch-rules.md:134` names the risk). Cheap, standalone.

## Mandatory AC regardless of scope — the ground-truth fixture pack

Operator-labeled input shapes (sentinel names ONLY — the doc-PII gate blocked
"Anytown"-class real-token sentinels once already; build names from scratch),
each labeled with the league a human says is right, executed as a test. Both
recent classifier defects (NRBL shadow, varsity shadow) were found ONLY by
ground truth — a green suite and two closure reviews caught neither
[EXECUTED: 5,049-combination sweep, audit-starter]. Ask the operator to label
unclear cases; the pack is append-only across future classifier changes.

## Adjacent MINORs (bundle only per D2; all [EXECUTED] by audit-starter)

- `_parse_ngb` case asymmetry (:498-515): JSON string lowercased, pre-parsed
  list not — '["AMERICAN_LEGION"]' -> legion but ["AMERICAN_LEGION"] -> unknown;
  bare non-JSON string silently -> [].
- `classification` compare case-sensitive, fails toward LESS strict table
  ("JV" -> nsaa_varsity).
- Matcher divergence: `_nsaa_level_from_name` (:523) substring vs
  `_LEVEL_WORD_PATTERNS` word-boundary — 'Sophomores'/'Freshmen'/'Jvortex'
  classify differently by path (IDEA-176 is the plural sub-case).
- Weak test: `test_legion_ngb_beats_14u_bracket` ratifies ngb-over-bracket
  using 14U, the only harmless bracket; 15U/16U untested.

## Boundaries

- Do NOT touch the ngb-precedence/NRBL-shadow behavior (IDEA-178: display-only
  overlay is PM-triaged and UX-gated, separate); do NOT fold E-274 (age_group,
  school family — different decision); IDEA-179 rec-forms need their own coach
  ruling.
- Pure-logic module: every claim verified by EXECUTING the classifier, never by
  reading it. Fail-first discipline per E-276's DoD style (name which ACs
  discriminate). No data/app.db access.

## Process (per workflow rules)

Plan-skill gates still run: PM verifies this seed's citations against the repo,
coach consult (D1) first, spec review, READY, operator authorizes dispatch.
Story-shape suggestion (PM owns): 01 D1-ruling + reorder + docstring + shadow
ACs; 02 tripwire + fixture pack; 03 (conditional on D2) MINORs. Glob epics/ AND
.project/archive for the next epic number.
