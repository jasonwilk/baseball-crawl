# Exit-sheet generator v1 — build to the athlete feedback model

**Status: OPEN — execution in progress** (codex-spec-reviewed; rounds 1-2 executed; v1.3 conformance, barometer activation, and batch owed)
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
