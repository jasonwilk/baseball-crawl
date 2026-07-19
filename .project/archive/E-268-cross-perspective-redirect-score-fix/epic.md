# E-268: Cross-Perspective Redirect Score-Misattribution Fix (CC-2)

## Status
`COMPLETED`
<!-- COMPLETED 2026-07-19: E-268-01 DONE + AC-verified; code-reviewer per-story APPROVED + Closure
     Integration CLEAN; Codex no code findings. Closure assessments recorded in History (documentation:
     No impact; eight-trigger context-layer: no codification required, T7 operator-signed exception).
     AC-5 reconcile-scoreboard ratchet = operator post-merge closure step (dev DB absent from worktree). -->

## Overview
`_upsert_game` writes the game orientation tuple non-atomically: `home_team_id`/`away_team_id` are overwritten unconditionally from `excluded.*`, while `home_score`/`away_score` are gated on `preserve_scores`. On a cross-perspective redirect the team-ids and scores are therefore written from DIFFERENT orientations, silently re-crediting runs to the wrong team. This epic gates the two team-id assignments on `preserve_scores` exactly like the scores, so the whole `{home_team_id, home_score, away_team_id, away_score}` tuple is written atomically.

## Background & Context
Corner case CC-2 from the 2026-07-19 accumulate-only re-run audit (master record: `.project/research/2026-07-19-rerun-accumulate-only-audit.md`; idea: IDEA-153). Two-channel validated **CONFIRMED / high** (Codex `gpt-5.6-terra` xhigh AND an independent subagent), each with an executable in-memory repro against the migrated schema through the real `ScoutingLoader`.

MECHANISM: `_upsert_game` (`src/gamechanger/loaders/game_loader.py:1373-1378`) overwrites `home_team_id`/`away_team_id` unconditionally from `excluded.*`, while `home_score`/`away_score` use `CASE WHEN ? THEN COALESCE(games.*, excluded.*)` gated on `preserve_scores`. Contrast `game_stream_id` at `:1391`, which already correctly keeps-existing.

REACHABILITY (all must hold): (1) a cross-perspective 2nd load of a game already in the DB → `preserve_scores=True` (set at `:441`); (2) incoming `home_away=None` → own-team-defaults-to-home flip vs. the canonical orientation (`:568`; `home_away` sourced live at `scouting_loader.py:263`); (3) the tolerant schedule-count redirect fires (`incoming_schedule_count==1` + single DB candidate, `:1065`) — it is SCORE-AGNOSTIC; (4) a NON-TIE game for the W-L/runs corruption. Reached through the ordinary report pipeline (generator → `ScoutingLoader.load_team` → schedule count supplied).

NUANCE (both channels agree): a pure TIE redirects+flips but is numerically INERT for W-L/recent-form/runs-avg (it only reorients home/away splits + `plays.batting_team_id`). The corrupt state is set on the FIRST cross-perspective redirect and PERSISTS until a later reload of that perspective (`preserve_scores=False`) rewrites both scores and side-ids — not permanent, but can persist arbitrarily long between re-scouts.

CORRUPTED SURFACES (BOTH teams' reports): `_query_record` (W-L), `_query_recent_games` (recent form), `_query_runs_avg` (runs for/against) in `src/reports/generator.py`, plus `plays.batting_team_id` and home/away splits.

**Consultation verdicts (per-domain, consulted-or-waived):**
- **data-engineer — CONSULTED, SOUND** (note below).
- **baseball-coach — WAIVED (no input required).** CC-2 corrects run/win MISATTRIBUTION on EXISTING report surfaces (W-L, recent form, runs-for/against) — it credits scores to the RIGHT team. It changes NO stat definition, no coaching logic, and adds no coach-facing surface; the numbers a coach reads are the same numbers, merely attributed correctly. There is no coaching-value decision here, so no baseball-coach input is required. (Recorded waiver, not a silent skip, per the consultation-completeness discipline.)

**DE consultation note (2026-07-19, data/schema soundness — SOUND).** `(home_team_id, away_team_id, home_score, away_score)` form ONE semantic orientation tuple. Today on a cross-perspective redirect (`preserve_scores=True`) the scores are kept existing-first (CASE at `:1375-1378`) but the two team-ids are UNCONDITIONALLY overwritten with the incoming perspective's orientation (`:1373-1374`) — a TORN WRITE: if the incoming perspective's home/away is flipped vs. the canonical row, the preserved `home_score` ends up attributed to the now-swapped away team. Extending the same keep-existing CASE to both team-ids moves all four fields atomically (all keep-existing on redirect; all take-incoming on first-insert / same-perspective reload). First-insert is unaffected (ON CONFLICT DO UPDATE is not evaluated on a plain insert; `games.*` in the CASE is safe), and the same-perspective correction path (`preserve_scores=False`) still writes incoming for all four. It is the exact analogue of the E-261 keep-existing treatment already applied to `game_stream_id` (`:1391`) and the scores — just closing the orientation gap.

## Goals
- Write the orientation tuple `{home_team_id, home_score, away_team_id, away_score}` atomically on a cross-perspective redirect — team-ids gated on `preserve_scores` exactly like the scores.
- Preserve the existing same-perspective reload correction behavior (`preserve_scores=False` still rewrites both scores and side-ids).
- Ship a regression test that reproduces the flip (fails pre-fix, passes post-fix).

## Non-Goals
- H4 / IDEA-147 (stale `plays.batting_team_id` after an orientation change via the frozen-plays path) — shares the same `_upsert_game` orientation root but is a distinct symptom (frozen-plays path, broader). OUT of this epic; tracked as IDEA-147.
- The retire-absent reconcile family (E-267) — different mechanism.

## Success Criteria
- Given a game canonically loaded A-home 5-3, when team B loads the same game with `home_away=None` (triggering the cross-perspective redirect), then the row keeps A as home with 5-3 — NOT B — and neither report mis-credits the runs.
- Given a same-perspective reload (`preserve_scores=False`), when it runs, then both scores and side-ids are rewritten as before (no regression to the correction path).
- `bb report reconcile-scoreboard` shows no gated regression before/after (TN — ratchet gate).

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-268-01 | Gate team-id assignments on preserve_scores (atomic orientation tuple) + regression test | DONE | None | software-engineer |

## Dispatch Team
- software-engineer

## Technical Notes

**TN-1 — Fix locus.** `_upsert_game` (`src/gamechanger/loaders/game_loader.py:1373-1378`). Gate the two team-id assignments on `preserve_scores` the same way the scores are gated, so on a cross-perspective redirect the whole orientation tuple is written atomically and same-perspective reloads keep the existing correction behavior. The exact SQL/CASE shaping is the implementer's decision — the requirement is atomicity of the four-field tuple under `preserve_scores`.

**TN-2 — Regression test (HARD AC, operator directive).** Both validators produced runnable in-memory repros against the migrated schema through the real `ScoutingLoader` — seed the test from those: canonical A-home 5-3 → B loads the same game with `home_away=None` → assert the row keeps A as home with 5-3 (not B), and assert ALL THREE affected reads are not mis-credited: `_query_record` (W-L), `_query_runs_avg` (runs for/against), AND `_query_recent_games` (recent form) — both validators confirmed recent-form is corrupted, so it must be asserted alongside record and runs. Must FAIL pre-fix and PASS post-fix.

**TN-3 — Ratchet gate.** Gate the change against the E-257 reconciliation-scoreboard (`bb report reconcile-scoreboard`): no gated stat's abs-Δ increases, neither ratcheted axis counter increases, `self_games` stays 0. Manual operator diagnostic against live data (dev DB absent from worktrees/CI), recorded at closure.

**TN-4 — Canonical seams / invariants.** `preserve_scores` is set at `game_loader.py:441`; `home_away=None` own-team-default flip at `:568`; the tolerant schedule-count redirect at `:1065`; `game_stream_id` keep-existing at `:1391` is the correct-pattern reference. Perspective-provenance invariant (`.claude/rules/perspective-provenance.md`) binds the touched write.

## Open Questions
- None. H4 / IDEA-147 (`plays.batting_team_id` re-derive on the same orientation-change root) is OUT of this epic and tracked as IDEA-147 (see Non-Goals) — a READY spec does not reopen its own scope.

## History
- 2026-07-19: **ACTIVE → COMPLETED.** E-268-01 implemented, AC-verified, and archived-ready.
  - **Closure Review Scorecard:**
    - Origin: CC-2 two-channel CONFIRMED/high (Codex `gpt-5.6-terra` xhigh + independent subagent, each an executable in-memory repro through the real `ScoutingLoader`).
    - Consultation verdicts (both recorded pre-dispatch): data-engineer CONSULTED/SOUND (torn-write / four-field orientation-tuple analysis); baseball-coach WAIVED (CC-2 corrects run/win misattribution on existing report surfaces — no stat/coaching-logic change, no coach-facing surface, no coach input required).
    - Implementation (software-engineer): `_upsert_game` extended the `preserve_scores` CASE gate to `home_team_id`/`away_team_id` so the four-field orientation tuple `{home_team_id, away_team_id, home_score, away_score}` writes atomically on ON CONFLICT update (14 placeholders / 14 binds, 4 trailing `preserve_flag` binds in SQL order — parity CR-confirmed). Plus the HARD regression test `test_cc2_redirect_preserves_orientation_tuple_and_reports` (real two-loader `load_payload` redirect path; asserts A-home 5-3 survives AND `_query_record`/`_query_runs_avg`/`_query_recent_games` credit correctly for BOTH teams), a supplementary SQL-level unit test, and the AC-4 over-gating guard `test_upsert_game_correction_path_takes_incoming_orientation`.
    - Fail-pre/pass-post: SE demonstrated the pre-fix failure (`assert (2,1,5,3) == (1,2,5,3)` — B mis-credited with A's 5-run win); CR independently confirmed it is genuine.
    - code-reviewer: per-story APPROVED (no findings) + Closure Integration Review CLEAN; independent 14/14 placeholder/bind parity confirmation.
    - Codex: P1–P4 no code findings; lone P5 = the AC-5 operator-closure item flagged as a false positive (CR concurred — AC-5 is deferred to the operator by design, not a defect).
    - Test evidence (verbatim): `python -m pytest tests/test_loaders/test_game_dedup.py tests/test_loaders/test_game_loader.py` → `112 passed`, exit 0; SE broader loaders-package sweep → 470 passed, no regressions.
  - **Documentation assessment (`.claude/rules/documentation.md`): No documentation impact.** E-268 is an internal play-ingestion bug fix that corrects run/win ATTRIBUTION on existing report surfaces (W-L, recent form, runs-for/against). No new/changed command, no schema change, no user-facing workflow change, no new or materially-changed agent — no doc update trigger fires.
  - **Context-layer assessment (`.claude/rules/context-layer-assessment.md`, eight triggers — main-session-evaluated verdicts):**
    - T1 (convention): NO — extends the existing E-261 keep-existing orientation pattern; no new convention.
    - T2 (architecture): NO — localized SQL fix, no structural/tech choice.
    - T3 (footgun/boundary): NO — the torn-write root is already captured by the E-261 precedent and now embodied in code; the remaining sibling (`plays.batting_team_id` re-derive) is tracked as IDEA-147.
    - T4 (agent behavior/routing): NO.
    - T5 (domain knowledge): NO.
    - T6 (CLI/workflow): NO.
    - T7 (context-growth ratchet): FAIL at +564 over baseline, but E-268 touches ZERO context-layer files (staged diff = `game_loader.py`, `test_game_dedup.py`, `epic.md`, story `.md`) — the overage is entirely pre-existing drift. **OPERATOR-SIGNED EXCEPTION for E-268** (Jason approved 2026-07-19: +564 is pre-existing, E-268 adds none; recurring friction tracked as the E-262 re-snapshot item).
    - T8 (reusable behavioral lesson): NO promotion — the atomic-orientation-tuple lesson is already embodied/documented via the E-261 precedent, and IDEA-147 tracks the sibling; promoting under an already-failing ratchet is marginal.
    - Net: no trigger requires claude-architect codification.
  - **AC-5 (E-257 reconcile-scoreboard ratchet):** the `bb report reconcile-scoreboard` run is the operator's post-merge closure step against the live dev DB (absent from the worktree/CI) — PENDING operator execution; no gated stat's abs-Δ may increase, neither ratcheted axis counter may increase, `self_games` stays 0.
- 2026-07-19: **DRAFT → READY.** **Review Scorecard** (all findings accepted/incorporated; verified clean by a main-session grep of the baseball-coach waiver, the E-257 DoD reframe, the GAP-5 ACs, and the CC-2 fix + hard repro test):
  - Origin: CC-2 two-channel CONFIRMED/high (Codex `gpt-5.6-terra` xhigh + independent subagent, each an executable in-memory repro through the real `ScoutingLoader`).
  - Consultation verdicts: data-engineer CONSULTED/SOUND (torn-write / orientation-tuple analysis); baseball-coach WAIVED (recorded — CC-2 corrects run/win misattribution on existing surfaces, no stat/coaching-logic change, no coach input required).
  - Codex spec review r1/r2: wrote the missing E-268-01 story file (P1); removed the H4 scope-reopen (H4 stays OUT → IDEA-147); added `_query_recent_games` to the TN-2 regression assertions; recorded the baseball-coach waiver (P2); reframed the E-257 ratchet DoD as a closure/operator gate (P2).
  - code-reviewer test-coverage audit: GAP-5 — E-268-01 AC-3 asserts BOTH teams' reports; new AC-4 adds the `preserve_scores=False` correction-path (over-gating regression guard).
  - NOT dispatched — awaits explicit user dispatch authorization.
- 2026-07-19: Created READY from CC-2 (IDEA-153), two-channel CONFIRMED/high. Single-story targeted fix.
- 2026-07-19: READY → DRAFT pending spec-review re-run. Incorporated the DE soundness note (Background) and the Codex spec review: wrote the missing E-268-01 story file (P1); removed the H4 scope-reopen from Open Questions (H4 stays OUT, tracked as IDEA-147); added `_query_recent_games` to the TN-2 hard regression-test assertions.
- 2026-07-19: code-reviewer test-coverage audit — E-268-01 AC-3 now asserts BOTH teams' reports; new AC-4 adds the GAP-5 `preserve_scores=False` correction-path test (over-gating regression guard); ratchet AC renumbered AC-5 + reworded to closure-verified. `plays.batting_team_id` re-derive stays OUT (IDEA-147 boundary, deliberate). Awaits the main session's spec-review re-run to re-confirm READY.
