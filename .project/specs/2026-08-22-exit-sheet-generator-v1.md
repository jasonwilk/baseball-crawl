# Exit-sheet generator v1 — build to the athlete feedback model

**Status: OPEN — release candidate verified clean, awaiting coach sign-off (gate 6)** (rounds 1-13 executed; 15/15 sheets + staff page pass independent recomputation; delivered to operator 2026-08-27)
**Created**: 2026-08-22. Operator authorized: spec now; execution mode later amended to
subagent-driven rounds (see progress log).

## Goal

A sheet generator that conforms to `docs/design/athlete-feedback-model.md` (at its current
version — v1.3 as of this writing) — the
committed spec that carries all design intent. This chunk is the mechanical build the model
was written to make deterministic. The prior ad-hoc scripts in
`ephemeral/2026-08-15-exit-meeting-player-sheets/` violate the model (priority language,
20-PA standing floor, precise percentiles, sample×magnitude ranking, named archetypes) and
are superseded. Mine them for the CSV section parsing only (`build_sheets.py:83`
`parse_export` is sound and was verified); the arithmetic cross-check existed only as
session one-off commands, NOT as code in that folder — reimplement it from model §9.

## Shape

- **Chunk dir (pinned)**: all implementation code lives in
  `ephemeral/2026-08-22-exit-sheet-generator-v1/` (new, per the ephemeral convention), as
  `build.py` (pipeline) and `checks.py` (acceptance gates), outputs under `out/`. Real
  minors' data flows through this dir; nothing in it enters git.
- **Pipeline**: parse (staff CSV exports + coverage-gated DB windows from a read-only DB
  snapshot) → structured claim records (model §9), written to `out/claims/<player>.json` →
  fixed-template rendering → per-player PDFs `out/pdf/<Last>-<First>-2026-exit.pdf` → staff
  provenance page `out/staff-provenance.pdf`.
- **Lenses in scope**: season lines, team bands, the season arc (model §5),
  context/abstention rung, coach manifest hooks, and the **staff provenance page — in v1**
  (model §8 treats it as part of delivery; previously mis-carried here as an open decision).
  **Barometer**: build the cohort-validity gate and pool builder; the lens activates only
  when the gate passes (opponent crawl is a separately sanctioned operation; until it
  completes the gate must demonstrably fail closed — see verification 4).
- **Committed artifacts of this chunk**: this spec, any model-doc corrections discovered
  during build, and the golden fixtures at `docs/design/fixtures/` (FICTIONAL players only;
  path pinned, not the executing session's call).
- Productization (`bb report exit-sheets` in `src/`) is explicitly OUT.

## Verification (executable; run from the chunk dir on the host)

1. `python3 checks.py --gate arithmetic` — recomputes every displayed rate from the exports'
   counting columns and diffs against the exports' own rate columns; prints max abs diff;
   RC=0 iff all ≤ 0.001. Then `python3 checks.py --gate arithmetic --perturb` must RC≠0
   (positive control; a passing control run is a FAILED gate).
2. `python3 checks.py --gate register` — banned lexicon + sample-bounded-negative assertions
   over `out/`; RC=0 clean. Seeded control: `--gate register --seed-violation` must RC≠0.
3. `python3 checks.py --gate claims` — claim-matrix assertions over `out/claims/*.json`
   (no rate below display floor, no standing below floors/pool minimums, no superlative on a
   rate, no evaluative/prescriptive text absent a coach-manifest entry); RC=0 clean.
4. `python3 checks.py --gate golden` — builds the fixture roster from
   `docs/design/fixtures/`, compares claim records and rendered text byte-for-byte against
   expected outputs (model §9 fixture list, including the cohort-gate-must-fail-closed case
   and the consolidation trigger); RC=0 iff identical. Run twice; `cmp` the two runs'
   outputs — any byte difference is a determinism failure.
5. Read-through pass (as the athlete, as the coach) on the two hardest live sheets; recorded
   as a progress-log entry naming both sheets and what was changed or accepted.

## Release gates (operational — outside repo verification, still blocking)

6. Proof sheet delivered to the operator, relayed to the assistant coach; his sign-off is
   recorded in the progress log (date + quoted reply) BEFORE the batch of 15 is generated to
   `out/pdf/`. Coach batch approval is a named model-§8 gate, not a courtesy.

## Out of scope

- `src/`, `tests/`, `migrations/` — untouched; no full-suite obligation.
- The opponent crawl batch (separately sanctioned; scripts staged in the 08-15 chunk dir).
- Situational splits, weight-room data, productization, any serving route.

## Progress log

- 2026-08-27 (rounds 9-13, the adversarial loop; RELEASE CANDIDATE CLEAN): round 9 opened on
  an operator finding (Mason Hiatt's sheet): every page-2 lens was scoped to one "primary"
  season — hiding a 36.1 IP / 8-start varsity spring behind "4.2 innings pitched" — and the
  barometer reused the pool's 20-PA membership floor as its subject floor, ranking 30-PA
  lines the §4 standing floor forbids. Operator ruled: every lens per-team-season, subject
  obeys §4 floors → model v1.3.4. Round 10 (v1.3.4 build) also fixed a real
  perspective-fallback bug the stopped first verifier pointed at — the barometer pools
  silently dropped games a pool club never crawled itself (all three pools grew). Round 11:
  an independent verifier (no builder code; own recomputation from CSVs + read-only DB;
  positive control per check class) swept ~1,850 checks and found 10 discrepancy classes —
  contact-profile denominators mislabeled "trips" (systemic), double-rounded rates (3),
  fielding still primary-only (11 sheets), a spring pool club dropped undisclosed, a false
  consolidation sentence (trigger counted bat+arm families together), staff prep
  summer-only, a deadband boundary case — all fixed with root causes; the definitional gaps
  it exposed were pinned into the doc as v1.3.5 (inclusive deadband, even-pool median,
  display rounding from raw components half-even, Tukey-hinge band cutpoints, barometer
  thirds, and a WHIP deadband of 0.10 replacing a vacuous 1.5 fallthrough — 9 real WHIP
  bands surfaced). Round 12: final sweep (~2,000 checks) left two hinge-tie rows (builder
  used exclusive Tukey; pinned rule is inclusive — fixed, exactly those 2 rows
  convention-sensitive in the whole set) and cameo-season scope-skips (fielding, then mound
  and contact) — resolved from the doc, not new rulings: cameos face each section's floors
  like any season (Linn's 8 IP juniors cameo mound block appeared; floors correctly
  suppressed all cameo standing). Round 13 confirmation pass: **15/15 sheets + staff page
  CLEAN** — lines 922/0, bands 437/0, arc 60/0, barometer 558/0, staff prep 0 issues; only
  non-adjudicable residue is 40 staff-page pool-share cells at ±0.1pp (harness identity
  merging weaker than builder's). RESIDUALS carried: duplicate player identities in crawled
  opponent data ("Herrmann"/"Hermann" as two players — data-quality signal beyond this
  chunk); staff meeting-prep doesn't read cameo standing (no-op this batch); FPS% has no raw
  count in exports (displayed from GC's column, disclosed); Went-Well stays primary-scoped
  (operator may extend); class years sourced from the roster photo only. REMAINING: operator
  docs-commit approval (model v1.3.5, this spec, fixtures, hooks stub), then release gate 6
  — coach sign-off recorded here before distribution.
- 2026-08-26 (rounds 4-8, catching the log up): Round 4 = v1.3 conformance (ordering rule,
  AVG family, arc adjacency, Went-Well cap; naming aligned to the doc's coverage vocabulary).
  Rounds 5-6 = the barometer flip: both original cohort gates PASSED on the post-crawl
  snapshot (49/49 opponent crawl, then 25+3 Juniors clubs; alias-join operationalized the
  identity-dedup clause — schedule-alias stubs resolve to crawled twins via the runlist CSV);
  the sensitivity check suppressed one real borderline band on its first live outing. Round 7
  = coach ruling: Where-To-Grow blank/coach-owned, its derivations moved to the staff page as
  meeting prep (model v1.3.1); mutant-based positive control on the leak check. Round 8 (the
  definitive pass) = all 15 sheets on app-final.db, Juniors barometer live (37 clubs resolved,
  pool of 36 after one disclosed drop — model v1.3.2/v1.3.3 carry the drop-with-disclosure
  rule), no-self-narration ruling (privacy footer removed; **defect found: the pipeline's
  --print-to-pdf-no-header was a nonexistent Chrome flag, silently ignored — every earlier
  PDF leaked its file path and a timestamp; fixed with --no-pdf-header-footer and proven by
  strings-grep over all 16 PDFs plus a flag-difference control**). In flight: v1.3.3
  regeneration — empty sections omit entirely (no abstention prose on sheets), machinery
  vocabulary added to the banned lexicon with seeded controls, Meeting Notes reduced to the
  single coach-fillable "Where to grow" block. Register gate grew a self-narration check.
  **Correction of record: `docs/design/fixtures/` is TRACKED (committed at 3c03b53), not
  untracked as rounds 1-6 assumed — golden regenerations are real working-tree diffs.**
  Verification gates 1-4 re-run green with all positive controls at every round; determinism
  double-runs byte-identical throughout. Gate 5 (read-through) done each round on the two
  hardest sheets. REMAINING: deliver the v1.3.3 set, then release gate 6 — assistant-coach
  sign-off recorded here before distribution; then the docs commit (model v1.3.3, goldens,
  this spec, hooks-stub update).

- 2026-08-22 (round 2): operator narrowed the first execution to 3 prototype sheets and
  authorized a subagent-executed build (Sonnet, deliberately — the determinism-thesis test)
  instead of the fresh session originally assumed. Round 1 built the full pipeline to the
  model as written; gates 1-4 green with positive controls fired; sheets were skeletal, which
  exposed that the model lacked a normative content inventory → model v1.2. Round 2 rebuilt
  to v1.2: full inventory rendered, coverage gate reimplemented with perspective-fallback
  recovery (round 2's key find: the "forfeit" game's rows live under the opponent's
  perspective id), 31 claims/player gated, byte-identical across separate processes, fixture
  suite at 24/24 including three new coverage scenarios. Round-2 ambiguities → model v1.3
  (ordering rule, band-table scope, AVG family, arc adjacency, Went-Well cap). REMAINING:
  round 3 = v1.3 conformance + barometer activation once the opponent crawl's cohort gate can
  pass; then gates 5-6 and the batch of 15 behind coach sign-off.
- 2026-08-22: spec drafted; codex review (host-run, gpt-5.4 via documented models-cache
  fallback) returned five findings — verification not executable (P1), rollout gate inside
  verification (P2), unnamed chunk dir + unpinned fixture path (P1), provenance-page open
  decision contradicting the model (P1), false claim that the legacy folder contains the
  arithmetic verifier (P2). All five folded above; provenance page decided INTO v1; paths
  pinned; verifier claim corrected.
