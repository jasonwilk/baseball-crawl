# E-267 Independent Audit — Consolidated Findings (2026-07-20/21)

**Purpose**: Durable record of the operator-commissioned 9-agent independent audit of commit `0c85623` (E-267) + follow-up `cfcbb74`. This is the defect-citation source for E-270 (code remediation, READY 2026-07-21) and E-271 (process redesign). Authored by the auditing session (main orchestrator), synthesizing five initial + four sharpening agent reports.

**Method**: 5 parallel auditors (3 Sonnet breadth: full-diff sweep, test-suite audit, planning/process audit; 2 Opus deep reasoning: reconcile deletion semantics, purge command), then a 4-lane sharpening round seeded by the builder-LLM's own disclosure prompt (claims treated as leads, not facts). All findings two-channel verified (Read + sed/cat) per `tool-output-integrity.md`; VERIFIED = auditor read and quoted the code through two independent channels.

## Code findings (remediated by E-270)

| ID | Severity | Finding | Evidence | E-270 story |
|---|---|---|---|---|
| C-1 | BLOCKING | Game grain has no absolute deletion cap; health gate reduces to `absent <= 0.5*prior` (`reconcile_at_load.py:190-192,489`); crawler accepts any HTTP-200 list (`scouting.py:230`); `boxscores_complete` only checks PRESENT games — truncated 15-of-30 schedule passes at boundary, hard-deletes 15 games + full child surface, unattended via morning-run | VERIFIED (recon-deep); corroborated by IDEA-160 | E-270-01 |
| C-2 | BLOCKING-adjacent | IDEA-159: `_other_perspectives` last-resort guard strippable by ordinary op sequence (merge twin → delete counterpart report → redirect-miss deletes survivor); 0/561 games currently in shape but no exotic preconditions | VERIFIED (diff-sweep) | E-270-01 |
| C-3 | HIGH | Purge production guard typo bypass: `APP_ENV=prod` normalizes non-production; `validate_app_env()` has zero call sites in `src/cli/` (only `SessionMiddleware.__init__`) | VERIFIED (purge-deep) | E-270-02 |
| C-4 | HIGH | Purge guard keys on APP_ENV, destruction keys on `resolve_db_path()` — decoupled; confirm prompt never shows resolved DB path (logged only after confirm, `cli/db.py:117-136`); `--force` disarms both prod refusal and prompt; no pre-purge backup (`backup_db.py` never invoked) | VERIFIED (purge-deep) | E-270-02 |
| C-5 | HIGH | No test drives `generate_report()` E2E with a shrunk crawl — only E2E class mocks ScoutingLoader entirely; destructive path never executed under full orchestration in any test | VERIFIED (test-audit) | E-270-03 |
| C-6 | MEDIUM | New annotation-as-coverage instance (missed by all E-267 reviews): `test_missing_boxscore_404_retires_nothing` (`test_player_line_reconcile.py:468-484`) passes whole-dict-empty fixture → outer `if not boxscores` fires → reconcile never runs; per-game-absent-key shape untested anywhere; collides with IDEA-158 if ever implemented | VERIFIED (test-audit sharpening) | E-270-04 |
| C-7 | MEDIUM | Verified no-op `not_final_ids &= fresh_ids` (`scouting_loader.py:354`) reads as filtering; C2↔C4 ordering constraints in `_load_team_core` point opposite directions across one call with nothing structural enforcing them (snapshot at :175 consumed :259); `test_roster_grain_reconcile.py:543` is the SOLE test able to catch reconcile-below-dedup (unique-name convention blinds the rest) — deletion landmine | VERIFIED (diff-sweep, recon-deep sharpening) | E-270-05 |
| C-8 | LOW | CLAUDE.md purge paragraph UNDERSTATES protection: claims drift test misses KEEP→PURGE FK, but `test_keep_set_has_no_foreign_key_into_a_purged_table` (`test_purge_scouting.py:392-424`) + live `_assert_foreign_keys_on` cover it; "silently breaks this command" is false — a KEEP→PURGE FK aborts LOUDLY (IntegrityError in txn) | VERIFIED (purge-deep, CR, ca-consult) | E-270-06 |

**What held up under adversarial attack (bounds the fix list)**: Fable fix correctly wired (`processed_event_ids`, `game_loader.py:384`); extra_guard structurally narrowing-only; scored-but-empty refusal per-block; roster cap truncation-immune; cross-perspective refusal; transaction discipline (no write-txn across network, deletes pend to single commit); purge partition complete/disjoint (27 tables vs migrations 001-012), FK-order edge-verified; path traversal on report_path defended; all 6 `_load_team_core` ordering constraints compose (2 dangerous violations test-pinned); the stale-invariant incident (`previously_rostered_ids`) was caught and its replacement tests genuinely discriminate; boundary behavior (0.5 floor at-and-below) deliberately pinned at unit + integration level; the 4 recorded "measured the wrong thing" tests all verified fixed.

## Process findings (remediated by E-271)

| ID | Finding | Evidence |
|---|---|---|
| P-1 | 16+ same-context review rounds (12 story-rounds all APPROVED + 4 Codex spec + 1 Codex code) missed the live data-loss defect; the one no-continuity review (Fable) caught it in one pass (4 real defects). Shared context ⇒ shared blind spot: every internal layer inherited the ACs + the stories' "unreachable in production" annotations | VERIFIED (epic.md:144-166; process-audit) |
| P-2 | The worst defect was ONE blind spot re-annotated across 3 stories ("annotation-as-coverage"); code-reviewer's own pre-dispatch audit flagged the exact region (GAP-1) then accepted a comment as resolving it. Rule now exists in prose (`testing.md`) with no mechanical check | VERIFIED (IDEA-158; testing.md diff in 0c85623) |
| P-3 | Fail-open defaults recurred 3-4× in a bias-to-refuse epic; every catch was human pattern-noticing; epic record and commit message disagree on the count (3 vs 4) | VERIFIED (epic.md:242; commit msg) |
| P-4 | Closure evidence ("4053 passed / 0 failed", live-DB smoke scope) exists ONLY in commit-message prose — zero occurrences in the epic's otherwise meticulous History; smoke never exercised a genuine retire | VERIFIED (grep of archive; commit msg admission) |
| P-5 | Five successive wrong context-ratchet figures (+214/+217/+221/+236/+237, actual +263) — each hand-derived from a stale/partial base; no canonical measure-command wired into closure | VERIFIED (cfcbb74) |
| P-6 | Send-cap (`send-message-counter.sh`, DENY_AT=25, from E-260) hard-blocked SE and PM COMPLETION REPORTS — working agents looked idle; denial visible to sender only | VERIFIED (hook source; epic.md:190,256) |
| P-7 | Orchestrator structurally pushed to escalate: told to classify finding validity (implement SKILL :278-284) while barred from reading the code (dispatch-pattern); every circuit breaker ends "escalate to user" with no decide-first test; escalation round-trip cost named nowhere | VERIFIED (process-design; skill text) |
| P-8 | Seven spec defects during implementation: 2 plan-avoidable via existing-but-underused steps, 1 PM role-discipline miss, 1 partial, 3 execution-only — more spec-review ceremony would NOT have caught the majority (the record's own argument) | VERIFIED (epic.md:170; per-defect analysis by process-audit) |
| P-9 | Live reproduction during E-270 planning (2026-07-21): PM/main mutual-wait stall at plan-skill Phase 1→2 (~16 min; PM idle "need epic scope" while brief sat in inbox; no handoff signal defined) | VERIFIED (this session) |
| P-10 | Over-escalation incident ("told twice to stop") exists only in operator account — NOT in any repo record; the main session has no durable record surface, so its failures leave no trace | NOT FOUND in repo (process-audit search) |

## Sharpening-round corrections (leads from the builder's prompt that dissolved)
- "Two blind spots each with a defect" → actually ONE region with two different defects (Fable + Codex) plus two other annotated regions closed proactively defect-free.
- Boundary coincidence in tests → NOT found; floor pinned in both directions at both layers.
- Ordering constraints → all six compose; no blocking defect.
- No review layer was pure ceremony (Codex spec rounds caught genuine would-break issues pre-code; story-04's circuit-breaker escalation caught a defect in the reviewer's own proposed fix); the failure was false-confidence accumulation, not zero value.

## Operator decisions taken on this audit
- E-270 scope: full list C-1..C-8 (2026-07-20); `MAX_GAME_RETIREMENTS = 2` (2026-07-21, api-scout's recommendation).
- E-271 framing: net-deletion + independent no-continuity review gate (2026-07-20).
- Standing caution: do NOT run purge-and-recrawl until E-270-01 and E-270-02 land.
