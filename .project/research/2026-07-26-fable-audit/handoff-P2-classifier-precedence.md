# P2 — Classifier precedence fixes (live under-rest defect) + ground-truth fixture pack

Plan an epic (plan skill; PM + baseball-coach + SE; glob `epics/` AND `.project/archive/`
for the next number). This is the natural home for the E-275 classifier-hardening
decision — read `.claude/agent-memory/baseball-coach/e275-classifier-hardening-rulings.md`
FIRST; several rulings are already made and must not be re-litigated.

## Finding 1 (MAIN, live, wrong direction): `varsity` shadows the Legion word patterns

2026-07-25 independent audit, verified by execution against
`src/reports/starter_prediction.py`: `\bvarsity\b` sits at index 4 of
`_LEVEL_WORD_PATTERNS`, ahead of all three Legion patterns (Legion / Post N /
Seniors+Juniors). Executed:

    'American Legion Varsity'  season-absent -> nsaa_varsity   summer -> legion
    'Post 12 Varsity'          season-absent -> nsaa_varsity   summer -> legion
    'Anytown Seniors Varsity'  season-absent -> nsaa_varsity   summer -> legion

Season-absent, these names take the NSAA varsity table, which UNDER-RESTS vs Legion at
46-50 (1d vs 2d), 61-70 (2d vs 3d), 81-90 (3d vs 4d) — and 81-105 pre-April
(`NSAA_PRE_APRIL` has no tier above 90, so the overflow branch applies 3 days vs
Legion's 4). Unlike the NRBL shadow (byte-identical tables, cosmetic today), these
tables genuinely diverge NOW. The docstring at :368 ("Legion-specific words are
season-independent") is false for these names.

GATE: baseball-coach must rule the intended precedence when a name carries BOTH a
Legion word and a level word (does "American Legion Varsity" mean Legion-senior or
HS-varsity?). Do not fix the ordering before that ruling.

## Finding 2: the LEGION == NRBL divergence tripwire (from IDEA-178 PM triage)

Per IDEA-178's PM triage (display-only overlay; precedence change contingent on curve
divergence): the contingency has no trigger today. Add the few-line test asserting the
`LEGION` and `NRBL` constants (`starter_prediction.py:188-197` vs `:208-217`) are equal,
so a future single-league change fails loudly (`.claude/rules/pitch-rules.md:134` names
exactly this risk). The display-only overlay itself is UX-gated — include only if the
ux-designer deliverable (`.project/research/2026-07-25-uxd-competition-level-disclosure-design.md`,
Revision 2026-07-25b two-field split) is judged ready; otherwise leave it out.

## Finding 3 (bundle only what coach/SE endorse; the rest stays as ideas)

Audit-verified adjacent defects in the same function — candidates, not mandates:
- `_parse_ngb` case asymmetry (:498-515): JSON string is lowercased, pre-parsed list is
  not — `'["AMERICAN_LEGION"]'` → legion but `["AMERICAN_LEGION"]` → unknown; bare
  non-JSON string silently swallowed to [].
- `classification` compare is case-sensitive and fails toward the LESS strict table:
  `classification="JV"` → nsaa_varsity (wrong direction for a rest gate).
- The two name matchers disagree: `_nsaa_level_from_name` (:523) is substring,
  `_LEVEL_WORD_PATTERNS` is word-boundary — 'Sophomores'/'Freshmen'/'Jvortex' classify
  differently on the ngb path vs the name path (IDEA-176 is the plural sub-case).
- Weak test: `test_legion_ngb_beats_14u_bracket` (tests/test_league_detection.py:995-998)
  ratifies ngb-over-bracket precedence using 14U — the only bracket where the precedence
  is harmless; 15U/16U untested.

## Mandatory AC regardless of scope: a ground-truth fixture pack

Both recent classifier defects were found ONLY by running real, operator-labeled teams
(a green suite and two closure reviews caught neither). The epic must add a fixture
pack of operator-labeled input shapes (redacted/sentinel names; label = the league a
human says is right) executed as a test, and every future classifier change must keep
it green. Ask the operator to label any cases where the right answer is unclear.

Guardrails: pure-logic module — verify every claim by executing the classifier, not by
reading it. No data/app.db access needed or permitted.

## Report back: coach's precedence ruling, story list, the fixture-pack contents,
before/after classification table for the three shadow names.
