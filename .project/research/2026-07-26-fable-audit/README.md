# 2026-07-26 Fable audit — committed record

Artifacts from the 2026-07-25/26 independent audit (Fable navigator session) and
its follow-on work. Context: operator-commissioned audit of the prior three days
with extreme suspicion, then P1/E-276 handoff supervision, then the model-behavior
reference. No real team names or public_ids appear in these files.

- `final-audit-report.md` — headline verdicts (full report in session transcript).
- `steering-burden-addendum.md` — graded, relay-corrected steering burden by model
  era across 16 sessions.
- `workflow-amendment-list.md` — system encodings of what worked, tiered by
  evidence (A/B/C + measurement caveats). Seed for the consolidated layer pass.
- `handoff-eval-protocol.md` / `handoff-hiccup-ledger.md` — pre-registered eval
  criteria for the P1-P5 handoff threads and the classified hiccup record
  (includes the E-276 READY-gate and red-team verdicts).
- `handoff-P1..P5.md` — the five handoff prompts as issued (P1 executed as E-276;
  P2/P3 pending; P4/P5 fold into the consolidated layer pass).
- `sublead-experiment-design.md` — depth-2 dispatch experiment design (pending).
- `model-behavior-reference-draft.md` (v1) + `model-behavior-reference-v2.md` —
  per-model prompting reference; v2 consolidates four reviews (Sonnet 5 and
  Opus 5 self-reads in the session transcript; gpt-5.4 and gpt-5.6-sol reviews
  committed here as `codex-review-output.md` / `codex-sol-review-output.md`,
  prompt in `codex-review-prompt.txt`). v2 is the CA-pass seed; v1 kept because
  the reviews cite its line numbers.
- `harnesses/recon_audit/` — executed demonstrations of the reconcile-at-load
  health-gate defect (E-276's origin); E-276 closure verification re-runs these.
- `harnesses/e276-review/x_attack.py` — red-team X2/X3 demonstrations cited by
  E-276's R1 repair and AC-14.
