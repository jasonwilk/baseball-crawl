# Program Endgame Sweep — 2026-07-12

Final reconciliation of the 2026-07 platform program: the full adversarial audit
(2026-07-04) and the holistic agentic-flow review (2026-07-07), executed as epics
E-250..E-260 (eleven epics + one vision curation), closing with E-260 (dispatch
cost accounting), E-256 (post-descope simplification), and E-259 (query-time
season aggregates). This file is the program's terminal record; the two source
artifacts are archived beside it (`PLATFORM-AUDIT-2026-07-04.md`,
`AGENTIC-FLOW-REVIEW-2026-07-07.md`).

Method: three independent full-read reconciliation passes (platform-audit
findings, flow-review §6/§2/§7, ideas ledger IDEA-089..125), each verified
against archived epic records and live code; flagged residuals re-verified by
hand before inclusion here.

## 1. Platform audit reconciliation

~78 findings FIXED (epic-cited, 10/10 code spot-checks passed), ~14 HOMED as
ideas, ~4 SUPERSEDED, 0 declined, **12 UNRESOLVED**. All 5 HIGHs closed and
code-verified (F-H1→E-253, F-H2→E-252, F-H3→E-254, F-H4/H5→E-251). Decision
audit: 17 sound, the 1 upheld REVISIT landed as E-259, 3 defense-held REVISITs
and 5 underdocumented decisions all discharged or homed.

**The 12 unresolved residuals** (hand-verified in live code 2026-07-12):

| # | Sev | Item |
|---|-----|------|
| 1 | MED | `bb data dedup-players --dry-run --execute` silently executes — `dry_run` flag declared, never read (`src/cli/data.py:65,104`); needs mutual-exclusion error |
| 2 | MED | `bb data reload-annotated-pitches` exits 0 with `games_with_errors > 0` (unconditional `SystemExit(0)`) |
| 3 | LOW | `bb status` hardcodes `data/app.db`, bypasses `resolve_db_path()` |
| 4 | LOW | Seven loader docstrings model the banned cwd-relative `sqlite3.connect("./data/app.db")` |
| 5 | LOW | SE memory `app-conventions.md:26` falsely claims DEV_USER_EMAIL auto-creates an `is_admin=1` user (own-memory fix, SE) |
| 6 | LOW | Inline-schema test pragma is whole-file, degrades guardrail (`test_no_inline_schemas.py`) |
| 7 | LOW | Empty `tests/test_crawlers/` package (audit quick-win: delete) |
| 8 | LOW | docker-compose comment points at gitignored override file + names the deleted dashboard port |
| 9 | LOW | CLAUDE.md Architecture still says "Store raw API responses before transforming" — false for the in-memory pipeline (context-layer, CA) |
| 10 | LOW | "Write-only raw archive" idea (in-memory REVISIT residual) never captured |
| 11 | WATCH | Rotated GC refresh token persists only to container-local `.env` (persist to `./data` = cheap insurance); no idea filed |
| 12 | WATCH | `FEATURE_PREDICTED_STARTER` past its documented removal condition — operator promote-to-default decision never recorded |

Disposition (operator-ratified at sweep): #1–#9 → one small housekeeping epic
(next epic number); #10–#11 → idea captures; #12 → operator decision to record.

## 2. Agentic-flow review reconciliation

All **9 §2 gap classes** addressed by landed structural/rubric changes (E-258
primarily; E-256-14 for the PII class; class 2 accepted-open by design —
forensic archaeology of the opaque era was explicitly out of scope). §6: 13 of
25 landed clean, 2 landed with recorded substitutions (10: smoke_test kept +
IDEA-109; 12: byte-gate instead of fixture-aware scanner), 1 superseded
(1: relay apparatus deleted by E-260, persist-then-message replacement
explicitly declined), **9 partial-or-unresolved** (14, 16, 17, 18, 19-partial,
20-partial, 22, 23-partial, 24) — the dispatch-mechanics / messaging /
plan-right-sizing / skills / backlog-sustainment cluster.

**Ratified disposition: DECLINED-BY-FREEZE.** These nine were consciously
priced out by the overshoot correction (E-260 froze the meta-layer; further
process additions require a cited defect). They are not forgotten and not
failures; any can be revived by the operator with a defect citation. Fragments
already homed: IDEA-116 (of 14), IDEA-117 (of 17).

§7 check: E-260 deliberately reversed three "what NOT to change" items (relay
default, tool-output-integrity framing, trigger-7/8 shape) — all
operator-commissioned, which is the authority §7 deferred to. Everything else
on §7 held or was tightened.

Item 25 (CR-vs-Codex gap re-measurement): precondition NOT met (4 qualifying
post-2026-07-08 scorecard epics vs ≥5). Substantive caveat: the default
workflow runs CR-only, so paired CR+Codex data barely exists; the E-259
closure Codex pass (5 findings, 4 accepted — all missed by 6 clean per-story
CR rounds + Step 1c) is the strongest single data point and argues for
running Codex at closure on large epics. Trigger stays installed as E-258-04
left it.

## 3. Ideas ledger (IDEA-089..125)

Trustworthy: 37/37 file-vs-index status consistency, no overdue review dates,
promotions/discards verified (102→E-256-14 genuinely closed its class;
119 correctly DISCARDED-moot). One correction owed: **IDEA-098 flip to
DELIVERED** — its deliverable (csrf.py via `is_production()`) shipped in
E-254-01; `csrf.py:136` verified. IDEA-116's time-sensitive resume-guard rider
is discharged (E-256 resumed and closed cleanly); its durable cwd-attribution
fix stays parked. Eviction-cluster partition (115 discipline / 125 file-trees /
E-259-05 AC-6 memory-dirs) is deliberate; 117 belongs with 118, not that
cluster.

## 4. Operator actions — verified state at sweep

Discharged and verified: `backfill-game-dates` (dry-run 0 rows), GS
`appearance_order` NULLs = 0, E-245 reloads (scoreboard axis counters 0/0),
E-249 fork residuals (0 refused forks live), reconcile-scoreboard baseline
committed (22626bc), ratchet baseline committed and green (12225 ≤ 12229),
first CI push green (docker-build validated; discharges E-256-06 AC-4 /
09 AC-5), redaction of archived-tree identifiers (964942e), fresh pre-011 DB
backup (2026-07-12 14:32).

Still owed at sweep time:
1. **Rebuild the stack** so migration 011 applies to the live dev DB
   (`_migrations` at 010; both `player_season_*` tables still present).
   Backup already taken.
2. `bb data dedup-players --execute` — 157 pending same-name merges across 13
   teams (0 forks).
3. Prod, at next deploy: backup first (011 applies there), and decide/record
   `FEATURE_PREDICTED_STARTER` (residual #12).

## 5. Process-ledger notes

- **One `--no-verify` closure commit** (E-256, 8d66727): evidence-backed
  exception — the story-14 doc-PII byte-gate correctly fired on PRE-EXISTING
  identifiers in old archived trees, not E-256 content; E-256's own docs were
  gate-clean in isolation and the whole-tree pattern scan was 0. The unblock
  (redaction, 964942e) landed the next commit. Not precedent.
- **Ratchet exceptions: 2 signed in the first 3 closures** (E-256 +93 gate
  addition; E-259 +49 history annotations on a −3k-line epic; E-260 itself was
  net −9). Falsifier #1 trips if exceptions run at ≥half of closures — at n=3
  the rate is literally at threshold, but both were bootstrap-class
  (a defect-cited gate; reconcile-not-strike history). Expectation: routine
  epics close at-or-below baseline; the rate is the thing to watch, starting
  now.

## 6. E-260 falsifiers — the standing health check

1. Layer exceeds baseline beyond signed exceptions, or exceptions at ≥half of
   closures (see §5 — at threshold, watch).
2. Median sends-per-story ≥14, or a hard stop crossed without operator
   escalation. (No dispatch-log TSVs survived the first three closures; data
   collection effectively starts with the next dispatch.)
3. An epic authored by agents to sharpen E-260's own machinery. (Held: IDEA-116
   /122/123/125 were captured, not actioned.)
4. A hard stop resolved by in-session reinterpretation instead of operator
   decision. (Held; the one spurious-deny mechanism — the stray cross-session
   counter — was pre-ruled "delete the file, not a falsifier event.")

## 7. Program close

The audit-to-execution program is complete: 11 epics + a vision curation
landed; every HIGH closed; the one upheld decision-revisit shipped; the
meta-layer is frozen except defect-cited changes; the reports-first,
single-season product core is smaller, gated, and measured (ratchet,
reconcile-scoreboard, CI, Step 1d smoke). Residual work is enumerated above
and in the ideas ledger — nothing else is silently open.
