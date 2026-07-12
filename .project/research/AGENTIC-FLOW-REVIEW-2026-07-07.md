# AGENTIC-FLOW-REVIEW — Holistic Infrastructure Review

**Date:** 2026-07-07 · **Scope:** agents, harness, context layer, review system, learning loop — entire agentic infrastructure of baseball-crawl
**Evidence bases used throughout:** `[MC]` mechanical count · `[IS]` interpreted sample · `[SEED]` first-hand orchestrating-session evidence (2026-07-04..07, treat as confirmed) · `[SC]` scorecard totals · `[V]` verifier verdict CONFIRMED. No taxonomy class was REFUTED; count caveats are noted inline where verifiers flagged soft overcounts.

---

## 1. Executive Summary

**1. Persist-then-message-the-path — one convention that fixes three problem families at once.** SendMessage drops are the single most expensive harness defect: 4+ final-report drops in one session `[SEED]`, ~540 idle-without-report candidates and 109 assistant-authored "never reached me" recovery turns corpus-wide `[IS]`, plus ~112 turns burned proving duplicate resends carry no new content `[MC]`. Simultaneously, relay traffic (~16MB) is the top context consumer in exactly the sessions that compact `[MC]`, and 58 of 71 >12KB messages inline a body *alongside* the file path that already names it `[IS]`. One edit to `dispatch-pattern.md` + `implement/SKILL.md` — substantive content (completion reports, findings, story text) is written to a worktree file and the message carries only path + ≤5-line summary — converts silent drops into deterministic file reads, kills duplicate-diff churn, and removes the largest driver of mid-dispatch compaction.

**2. Close the codex-review fabrication hole structurally, not by discipline.** `scripts/codex-review.sh` streams 300KB–3200-line reports to the Bash preview with no persistence; the manual `> file` redirect the read-receipt gate depends on was omitted in 44/48 invocations `[MC]`, and this produced two documented fabrication/mischaracterization incidents (E-230, E-231) — the exact failure the gate was written to stop. Edit the script to `tee` to a deterministic file and print `RESULT_FILE=` + `wc -l`; update the skill to read that file. Small script change, eliminates an incident class.

**3. Attack the #1 verified review-gap class with scope, not reviewer skill.** Cross-cutting integration & mirror-path drift is the largest genuinely-CR-missed class (66 findings, E-220-dominated but persisting 1–2/epic through the newest epics) `[SC][V]`, and it is explicitly a review-*scope* problem the E-251 routing fix cannot touch. Fixes: a mandatory consumer-audit step in `code-reviewer.md` for any signature/dimension/invariant change, a codified project twin-path checklist (game_loader/scouting_loader, detect/cleanup, recompute/parity column sets), mechanical triggers for Invariant Audit Mode, and making the CR integration review unconditional at closure (today a plain "implement E-NNN" — the user's documented default — closes with *no* combined-diff reviewer at all `[IS]`).

**4. Give context-layer stories a review gate.** 16 verified findings reached Codex with zero prior review because context-layer stories skip per-story CR by design, and token-grep verification structurally misses prose (E-250's "across games and seasons" survived a keyword sweep) `[SC][V]`. Formalize what Codex already de-facto does: context-layer epics get a mandatory Codex (or CR) pass, and doc sweeps pair grep with a semantic read of touched sections. This also feeds the cross-season recurrence — the single most-repeated user correction in the corpus (5 sessions) `[MC]`.

**5. Stand up a closure runtime smoke — the reports flow is never actually driven.** The closure gate is pytest-only; the one live runtime gate ever run (E-247's `bb report verify-aggregates`) was a hand-negotiated one-off `[MC]`. Consequences on record: a physically-impossible FPS stat shipped in a live report and was caught only by the operator's baseball intuition `[IS]`; a rest-day UTC bug slipped *between* two epics that both closed green `[IS]`; fresh-DB goldens provably cannot see populated-DB DELETE+rebuild regressions (E-247 F1) `[IS][V]`. Add a conditional Phase 5 Step 1c smoke (`bb report generate` + `verify-aggregates` + morning-run `--dry-run`), name the code-reviewer as its authorized runner (a second carve-out beside the closure-pytest exception), and expedite E-257 (reconciliation scoreboard) — the North Star's enforcement mechanism is 8+ months unbuilt.

**6. Fix the two hooks that cry wolf; leave the ones that work.** The edit-verify hook false-positives on **every** auto-memory Write (11/11 real blocks in the corpus were memory-path false alarms; 3 in one session `[MC][SEED]`) because the harness injects frontmatter after the write — add a path carve-out or substring predicate. The PII pre-commit hook's only 2 real fires were both test-fixture phone-shaped constants `[MC]` — make the scanner fixture-aware. Meanwhile the *real* PII hole is open: `epics/` and `.project/` are in `SKIP_PATHS`, names aren't regex-detectable, and a minor's real name has already landed in an idea file (IDEA-096/102) `[MC]` — wire `scripts/check_doc_pii.sh` into the commit hook for planning artifacts.

**7. Codify multi-session operation — it's happening, ungoverned.** 13 sessions ran against this checkout Jul 3–7; the operator hand-carries state between threads and sessions rediscover peer commits via git archaeology `[IS]`. The worktree-reuse instruction can't distinguish "resume my crashed dispatch" from "another live session owns this epic" `[MC]`; worktree-guard's dispatch mode is machine-global; the shared MEMORY.md took an observed modified-since-read collision `[IS]`. One new always-loaded rule (`multi-session-coordination.md`: dispatch claim in epic History, repo-state-as-channel, shared-memory hygiene) closes all three.

**8. Make the learning loop actually load, and make the backlog actually shrink.** The codification gate certifies "was recorded," not "will be recalled": high-value lessons strand in topic memory files that never auto-load (the grep-match trap is invisible to every agent but PM) `[MC]`, and the decided promote-to-rule policy is untriggerable (citation counting with no counter) and homeless (waiting on DRAFT E-255) `[MC]`. On the backlog side: 73 CANDIDATEs, 0 DEFERRED ever, 43 past their own Review-By date, zero routine pruning `[MC]`. Add a load-target classification to the context-layer assessment, make closure idea-triage a recorded verdict like its neighboring gates, and give the 90-day sweep an executor.

---

## 2. Architecture

### 2.1 Roster & model/effort allocation

**Keep — the expensive core is earned.** PM, CR, SE, DE at `opus[1m]/high` account for 209 spawns and are the load-bearing quality surface `[MC]`. The gates they run demonstrably catch real defects: CR NOT-APPROVED blocks ranged 5–45/session; the closure full-suite gate caught red suites per-story review missed in at least 3 sessions (8769fe96 "4 failed", c05fdb72 "1 failed", 601d2deb "2 failed"); PM AC-verify caught implementer-summary drift ("verified against the worktree, not just the implementer summary") `[MC]`. `docs-writer` and `baseball-coach` are already correctly at sonnet `[MC]` — no downgrade available there.

**Change — three edge misallocations** `[MC]`:
- **`claude-architect.md`: `model: opus` → `opus[1m]`.** It is the heaviest context-layer reader (longest average spawn prompt, 3140 chars; 44 spawns; scoped to hold CLAUDE.md + all rules + all agent defs at once) and the only judgment agent without the 1M window. Cost is near-zero below 200K tokens; above it, it's paying for context it genuinely needs.
- **`ux-designer.md`: `opus[1m]/high` → `sonnet`, default effort.** 3 spawns total, shortest prompts, text-wireframe deliverables, and its definition still names the E-239-removed "coaching dashboard" — fix the stale scope in the same edit.
- **`api-scout.md`: add explicit `effort: medium`.** It is the only agent with implicit effort; declare it so behavior is reproducible. Keep opus — undocumented-API semantics are judgment work.

**Routing addendum:** add one line to `agent-routing.md` — read-only tracing/diagnosis routes to built-in `Explore`; ~6 such tasks went to heavier full-tool `general-purpose` spawns `[MC]`. No new investigator agent — Explore already fits.

### 2.2 Planning flow

**Keep:** the READY gate, the Dispatch Authorization Gate (planning never auto-chains to dispatch), and the Codex spec-review phase (its second pass has fired for real: E-241/E-243/E-233) `[IS]`.

**Change:**
- **Right-size ceremony by epic size.** E-244 — a single-story, single-file fix — drew 12 spec-review findings across three review layers plus two consistency sweeps `[IS]`. Add an S/M/L classification to `plan/SKILL.md` Phase 0: S epics (≤2 stories, no schema/security/API surface) get a single CR spec-audit pass, Codex opt-in. The small audit-spawned epics (E-246/247/248) already do this informally; codify it.
- **Delete the dead internal-review loop.** Across ~20 recent scorecards, the plan skill's 3-iteration internal loop ran exactly once every time `[IS]` — ~60 lines of never-taken branching loaded on every planning trigger. Collapse to a single pass.
- **Extend the single-source rule beyond Technical Notes.** A recurring finding class (E-244, E-243, E-249, E-253) is Goals/Success-Criteria restating and drifting from ACs — the template manufactures the drift the review then pays to catch `[IS]`. Edit `epic-template.md` Goals/Success Criteria comments: reference story IDs, never restate concrete values; add a matching PM Quality Checklist item.
- **Mandate the canonical scorecard schema.** 5+ distinct header shapes across archived epics make spec-review yield unmeasurable `[MC]` — the exact data needed to calibrate ceremony. Fix the schema in `plan/SKILL.md` Phase 5 and add it to the closure checklist.
- **Add a READY-freshness gate.** Five epics have sat READY 99–122 days on premises the reports-first descope invalidated (E-072/E-073 target surfaces E-239 deleted) `[MC]`. READY > 60 days = STALE, PM re-confirms against ROADMAP or demotes to DRAFT; wire the check into both plan and implement Prerequisites.

### 2.3 Dispatch-pattern design

**Keep — and name why.** The staging boundary, per-story CR verdict, PM verify-against-worktree, and the Step 1b/Step 8 full-suite gate all have documented catches (§2.1) `[MC]`. Add a short "why these gates cost what they cost" note to `dispatch-pattern.md` citing the concrete incidents, so future cost-cutting passes exclude them. Worktree isolation also works: worktree-guard produced 6 denials, all correct, 0 false positives `[IS]`.

**Change — mechanics only, not gates:**
- **Collapse the PM status choreography.** PM absorbs ~half of all dispatch SendMessage traffic (49%/48%/40% across three sessions) `[MC]`, largely on three bookkeeping round-trips per story. Merge IN_PROGRESS into the assignment turn (fire-and-forget; execution is strictly serial so nothing races the flag), and combine AC-verify + conditional DONE into one PM instruction ("verify; if all pass and CR approved, mark DONE"). PM still owns every status edit — this changes the *wait*, not the owner, so `feedback_pm_owns_statuses` is untouched.
- **Stop pasting story files into messages.** 35 assignments across 6 sessions inlined ~332K chars of "FULL STORY FILE TEXT" for files that exist at a path named in the same message, in the worktree every recipient works in `[MC]`; the skill mandates it at lines 130/142/236/255/670. Replace with path + "Read to completion before starting" (the read-receipt convention covers fidelity). Keep verbatim only for content not on disk. This is the flagged renegotiation of Anti-Pattern #2 — the risk it guarded (agent skips the Read) is mitigated by requiring the recipient cite path + line count.
- **Boundary flag — do NOT change main-session relay yet.** Relay doubles every finding into two hops `[IS]`, but the mandate exists because peer DMs drop silently, and relay drops too `[SEED]`. The persist-then-message-the-path convention (§4.1) is the right fix; only after it proves out should direct CR→implementer relay of persisted findings be considered.

### 2.4 Multi-session operation

Nothing in the context layer governs parallel sessions, and they are the operating reality (13 active Jul 3–7; user quotes: "give me the fixes to pass to the other thread"; "what epics were done after this audit?") `[IS][MC]`. Create **`.claude/rules/multi-session-coordination.md`** (`paths: "**"`) containing:
1. **Dispatch claim:** at dispatch start, PM appends `DISPATCH-CLAIMED session=<id> at <ISO>` to the epic's History; `DISPATCH-RELEASED` at closure/abort. `implement/SKILL.md:117`'s blanket "reuse the existing worktree" becomes a three-case check (own claim = resume; foreign open claim = refuse; no claim = user-confirmed stale-crash reuse).
2. **Channel rule:** between sessions, committed repo state is the sole source of truth; re-read HEAD/epic status at dispatch prerequisites and before closure apply — never act on an in-context snapshot older than HEAD.
3. **Shared-memory hygiene:** MEMORY.md and sidecars are cross-session shared state — Read immediately before Edit, prefer append/sidecar over rewrite, treat modified-since-read as a peer-session signal (one observed collision `[IS]`).
4. Document in `worktree-isolation.md` that worktree-guard's dispatch mode is **machine-global** (any session's dispatch flips all sessions to strict mode) `[MC]`, and add a stale-worktree advisory notice so a crashed dispatch doesn't mysteriously brick a solo session's writes.

---

## 3. The Review System

### 3.1 Totals and what dual review demonstrably earns

CR findings: **432**. Codex findings: **309**, of which **217 were CR-missed** `[SC]`. Codex is almost never clean — 38/47 runs produced findings, 2 clean `[MC]`. In ~13 of ~19 finding-producing runs, the *whole-epic* CR integration pass had just come back clean/approved `[IS]`. Even budget-degraded static-only Codex passes (E-247, E-239) out-caught CR `[IS]`. Three verified classes — integration drift, concurrency, security — have **only ever** been caught by Codex `[V]`. Dual review is earning its cost; the question is where CR's share of the work should be repositioned.

### 3.2 The verified gap taxonomy

All nine classes CONFIRMED by independent verification against archived epic records `[V]`. Count caveats from verifiers noted.

| Class | Count | Root cause | Era pattern | Count confidence |
|---|---|---|---|---|
| Cross-cutting integration & mirror-path drift | 66 | Diff-only blindness — defects live outside the story diff (untouched consumers, twin paths, second edit sites, un-enumerated scope keys) | Persists through newest epics; E-251 cannot fix (scope, not skill) | E-220 ≈50 of 66; per-round counting would land ~20. Class real either way `[V]` |
| Undescribed accepted findings (opaque era) | 71 | Record-keeping, not detection: pre-E-251 scorecards were count-only | Entirely old epics; already closed by itemized scorecards | Sampled 24/71 exact-match `[V]` |
| Test-integrity & missing coverage | 23 | CR barred from worktree pytest → evaluates assertions textually; removal-epic stale tests invisible by construction | Even across eras, still recurring | Soft overcount — E-252 misattributed; true count somewhat <23 `[V]` |
| Function-contract & edge-case bugs | 16 | Happy-path AC verification misses edge-shape enumeration; partially routing-era | Thins but persists post-E-233 (E-247, E-252) | Plausible; ~8 verified in 4 sampled epics `[V]` |
| Doc & context-layer drift | 16 | Context-layer stories skip per-story CR entirely; token-grep verification misses prose | Both eras — the CR-skip policy is unchanged | ~1–3 generous `[V]` |
| Spec/AC-compliance drift | 11 | Falls between gates — nobody owns the AC×surface matrix | Even across eras | Plausible `[V]` |
| Migration & deploy-time schema bugs | 5 | Migrations read as text, tested on clean fixtures — never run against production-shaped data | Old-era in this dataset; treat as **dormant, not solved** | Exact `[V]` |
| Concurrency/atomicity races | 5 | No standing read-then-write check; single-process tests never interleave | **Recent-skewed** (E-235/245/252 post-maturation); dual review didn't move it | Honest count ~4; "no standing check" slightly overstated (CR caught a sibling race in E-235) `[V]` |
| Security vulnerabilities | 4 | No security rubric in CR; PII scanner doesn't gate planning artifacts | **Exclusively recent** — genuinely open | Exact `[V]` |

### 3.3 The routing-era test

Until E-251 (2026-07-05), SE/DE/api-scout stories ran as bare `general-purpose` spawns — no definition, no checklist, no memory, default effort — for essentially the whole review-history window `[SEED]`. Prediction: the CR-vs-Codex gap **narrows** post-E-251 for reviewer-quality classes (edge-case bugs already thin post-E-233) but **does not move** for the structural classes: integration drift (review scope), test-integrity (no execution), doc drift (CR skipped), concurrency, security (no rubric). The taxonomy's era analysis supports exactly this split `[SC][V]`. **Action:** re-run the gap tally after ~5 post-E-251 epics with the now-mandatory canonical scorecard schema (§2.2) — that is the empirical check on whether the remaining rubric edits below are earning their keep.

### 3.4 Rubric edits — `.claude/agents/code-reviewer.md`

1. **Consumer-audit step** (targets class 1): for any signature/dimension/invariant change, grep-enumerate all call sites, mirror paths, and duplicate constant lists; check each explicitly. Codify the project **twin-path checklist**: game_loader ↔ scouting_loader, detect ↔ cleanup mirrors, recompute ↔ parity column sets — the same pairs recur `[V]`.
2. **Adversarial assertion rubric** (class 3): for each new/changed test, "what wrong implementation would still pass this?"; require element-pinned/scoped assertions and a demonstrated fail-then-pass for bug-regression tests.
3. **Edge-case enumeration per changed function** (class 4): null/empty/malformed, error propagation, and for refactors diff the OLD function's branches against the new — the E-247 lesson. Behavior-preserving epics require populated-DB characterization tests, not fresh-DB goldens.
4. **Standing concurrency question** (class 8): "who else can write this row between my read and my write?" — admin UI + CLI + cron is now three SQLite writers. Every read-check-write must be atomic and rowcount-gated; every shared-connection error path must rollback.
5. **Security trigger** (class 9): any story touching auth, credentials, or PII paths gets an explicit security rubric pass (replay, TOCTOU, fail-open vs fail-closed, PII in ALL artifact types).
6. **Self-load fallback for API/migration context** `[IS]`: replace "Do not load endpoint docs/migration files independently" with — if the assignment omits the section but the diff shows GC field access or new column references, self-load the docs rather than silently no-op'ing both E-147 checklist items.
7. **Cumulative migration baseline** `[IS]`: build the schema baseline from all `migrations/*.sql` in the tree plus `git diff --cached main`, never the current-story unstaged diff alone.
8. **No truncated reads in integration review** `[IS]`: prohibit `| head`/`| tail` pipes on diff/grep reads (E-239's self-admitted miss cause), and require an actual pytest run for any epic whose diff touches `tests/` at the closure integration pass.
9. **Verbatim test evidence** `[IS]`: implementer's `## Test Results` must include the exact pytest summary line and command; CR cross-checks claimed test files against its grep-discovered import set.

### 3.5 Structural edits — implement skill and process

- **Make the CR integration review unconditional at closure** (`implement/SKILL.md` Phase 4a → Phase 5, between invariant audit and full-suite gate). Today a plain "implement E-NNN" — the user's documented default — gets *no* combined-diff review `[IS]`; only Codex (4b) stays gated on "and review."
- **Fix the CR→Codex→CR ordering.** CR approves, Codex finds, CR reverses itself (E-239, E-251, E-253) `[IS]`. Either run Codex before the CR integration pass so CR adjudicates a real finding list, or drop the separate 4a pass on epics that will get Codex and use CR purely as finding-validator/remediation reviewer.
- **Mechanical Invariant Audit triggers** (`implement/SKILL.md` Step 1a): the only mode that sweeps untouched files is currently triggered by the one actor barred from reading code `[IS]`. Add a checklist evaluable from permitted artifacts: NOT NULL/FK migration in diff, canonical-helper signature change in Technical Notes, new required field on a core INSERT → audit fires.
- **Context-layer review gate** (class 5): context-layer epics get a mandatory Codex or CR pass instead of PM-AC-verification-only; doc sweeps pair token-grep with a semantic read of touched sections plus synonym expansion.
- **AC×surface matrix** (class 6): joint PM+CR checklist item — for each conditional AC ("only when X", vocabulary mappings), enumerate every render/call/error path and verify the condition at each.
- **Migration rubric** (class 7, dormant): enumerate live-DB data states and dry-run migrations against a production DB copy with before/after scope assertions — keep as a standing item so dormancy doesn't become recurrence when migrations return.
- **Single-source the Codex rubric.** `.project/codex-review.md` is a manually-synced abbreviation of CR's checklist and already lags it (SQL-scope and multi-scope-aggregate items have no Codex counterpart) `[IS]`. Have `codex-review/SKILL.md` embed the CR Bug Pattern Checklist from `code-reviewer.md` at prompt-assembly time; reduce `codex-review.md` to Codex-specific priorities.
- **Opaque-era archaeology (optional):** a one-time pass over E-189/E-173/E-223/E-168 story files/commits would reclass the 71 undescribed findings into the real taxonomy `[SC]` — forensic value only; the process fix (itemized scorecards) already landed.

### 3.6 Tooling — `scripts/codex-review.sh`

- **Tee output to a deterministic file**, print `RESULT_FILE=`, `wc -l`, and `tail -n1`; update the skill's read-receipt to consume that file. 44/48 invocations skipped the manual redirect; 2 fabrication incidents resulted `[MC][SEED]`.
- **Default the WORKDIR diff to `--diff-filter=ACMR`** so pure deletions don't burn Codex's 20-minute budget — on the largest epics (E-239's 2.57M-char diff) Codex silently degrades to static-only, losing its test sweep exactly where integration risk peaks `[IS]`. Note in the skill that Codex's pytest sweep is best-effort; Phase 5 Step 1b is the authoritative test gate.

### 3.7 Where runtime verification slots in

Per-story CR is structurally diff-only and pytest-barred `[SEED]`; the closure gate is pytest-only; no role is authorized to run `bb` at closure — which is why a live runtime gate has run exactly once in ~240 epics (E-247, hand-negotiated) `[MC]`. Add **Phase 5 Step 1c "closure runtime smoke"**, conditional on the epic touching `src/reports/`, `src/db/`, loaders, or `src/api/`:
- `bb report generate <fixture public_id>` with one asserted headline invariant (e.g., `reference_date` == today in operating tz — the rest-day UTC bug shipped between two green epics `[IS]`), `curl /health`, `bb report morning-run --dry-run`.
- `bb report verify-aggregates` as a hard sub-check for loader/aggregate epics — promoting E-247's one-off to standing, and the only gate class that can see populated-DB DELETE+rebuild regressions `[IS][V]`.
- **Owner:** the code-reviewer, via a named second exception in its Test Execution Constraint (alongside the closure-pytest carve-out); FAIL routes into the Phase 4a remediation loop like a red suite.
- **Expedite E-257** (reconciliation scoreboard, currently a DRAFT that "was on no list anywhere") to give the North Star its enforcement mechanism; fold its axis counters (self-games==0, dropped pitch events, no-plays) into the smoke.
- **Dispatch E-256's CI slice**: `.github/workflows/ci.yml` for the static half (pytest + case-insensitive PII sweep + lockfile drift + `docker build`); document explicitly that CI cannot absorb the credentialed populated-DB smoke — that stays with CR at closure and the operator post-deploy. Wire the orphaned `scripts/smoke_test.py` into both, or delete it `[MC]`.
- **Report-time plausibility gate** (new story, `src/reports/generator.py` / `build_pitcher_profiles`): range-check headline rates (FPS 40–75%, P/PA 3.0–4.5) before render — the operator was the only QA that caught an 18x-off FPS in a shipped report `[IS]`.

---

## 4. Flow Friction & Harness

### 4.1 Message reliability (the big one)

- **File-backed completion reports** `[SEED][IS]`: reports travel only as SendMessage free text; a drop has no fallback. Require every implementer/CR/PM completion report to be written to `/tmp/.worktrees/baseball-crawl-E-NNN/.reports/<story-or-role>-<round>.md` before SendMessage; lead rule: idle-without-report → read the file, don't nudge. Edit `implement/SKILL.md`.
- **Path-only relay rule** `[MC][IS]`: when relayed content exists as a readable file, the message MUST NOT inline the body — path + ≤5-line summary. Edit `dispatch-pattern.md` (relay-context-budget subsection) + `tool-output-integrity.md` relay section. This is also the primary compaction fix: all 6 compaction events were multi-agent sessions (15.7 avg spawns vs 1.8) and relay traffic was their #1 context consumer `[MC]`.
- **Message idempotency ids** `[MC]`: substantive reports carry a stable id (`CR-E-NNN-SS-r2`); lead dedupes by id, never re-diffs a resend. ~112 duplicate-verification turns eliminated. Edit `dispatch-pattern.md`.
- **ACK convention** `[MC]`: implementers reply "ACK <story-id> starting" on assignment; missing ACK within a turn = deterministic re-send trigger (~22 recovery round-trips across 6 sessions). Edit `implement/SKILL.md`.
- **Shutdown termination discipline** `[MC]`: 213 shutdown_approved vs 202 teammate_terminated; ~36 turns of closure-time re-issuing. Lead waits for `teammate_terminated` specifically as the delete-team precondition; one capped retry. Edit `implement/SKILL.md` closure sequence.
- **Canonical teammate ids** `[MC]`: 60+ id variants for ~9 roles (PMx/PMz/SE2/cr-2…are respawn scars that abandon live context). Add a canonical-id table to `dispatch-pattern.md`; respawns REUSE the id. Extend the line-162 PM respawn-recovery pattern to CR/implementers with a fixed state-recovery brief pointing at persisted work products.
- **Round-2 relay deltas** `[MC]`: SKILL.md line 289 re-pastes round-1 findings verbatim in the hottest sessions; switch to findings-file path + delta.
- **Idle-notification noise** `[MC]`: 417 pure/multi-idle bundles train the lead to skim — feeding report misses. Codify that idle-only inbound requires no response; optionally a notification-hook filter.
- **Destructive-action re-confirmation** `[IS]`: before executing a peer-DM-requested rm of an artifact, re-read on-disk state and confirm against the peer's latest message (the E-245 create/rm/restore thrash). One clause in `dispatch-pattern.md` relay-integrity.

### 4.2 Hooks

- **edit-verify memory carve-out** (immediate; `.claude/hooks/edit-verify.sh` ~line 43): early-exit for `*/projects/*/memory/*` and `*/.claude/agent-memory/*`, or use a substring predicate there — the harness injects `originSessionId` frontmatter after every memory Write, so byte-equality is structurally impossible; all 11 corpus blocks were this false positive `[MC][SEED]`. On genuine mismatches, include the byte-length delta and recovery step in the block reason.
- **PII scanner fixture-awareness** (epic story; `src/safety/pii_scanner.py`): both real fires were `us_phone` matches on test fixtures `[MC]` — exempt `tests/**` from shape heuristics or honor a `# pii-ok` pragma.
- **PII planning-artifact gate** (epic story; settings + wrapper): `epics/` and `.project/` are in SKIP_PATHS and names aren't pattern-detectable; a minor's real name reached an idea file and only Codex caught it `[MC][V]`. Wire `scripts/check_doc_pii.sh` (with the denylist) into the commit hook for staged `epics/` + `.project/` trees; fail-open-announced only on the denylist-absent exit.
- **Secret-read guard** (new `.claude/hooks/secret-read-guard.sh`): nothing stops a `cat .env` from pulling live GC tokens into context; the only credential control fires at commit, which reads never reach `[IS]`. Deny Read/Bash targeting `**/.env*` and `secrets/**` (excluding `*.example`).
- **pii-scan loudness**: emit explicit `[pii-scan] ok` / `SKIPPED (jq missing)` so the fail-open path is loud; optionally enforce the Co-Authored-By trailer in the same hook `[IS]`.

### 4.3 Permission hygiene & harness ergonomics

- **No Bash allowlist** — the corpus shows near-zero Bash permission prompts and 0 worktree-guard false positives `[IS]`. Adding one is complexity without a problem. Explicit non-change.
- **SendMessage approval semantics** `[MC]`: 21 sessions hit the same rejection (approval + content in one call). One documented convention: approvals travel alone; substantive replies are a separate message. Home: `multi-agent-patterns` content — which per §4.4 should fold into `dispatch-pattern.md`.
- **Agent-teams tool contract** `[MC]`: 13 `TeamGet` guesses in one session, 10 Task* schema errors, 9 missing-`summary` errors — document the real tool names and required params in the same folded location.
- **Background-log reads** `[MC]`: 17 sessions hit the 256KB Read cap on `.output` logs — one line in `tool-output-integrity.md`: use tail/grep/offset, never bare Read.
- **Memory-edit read-gate** `[MC]`: 15 of 30 Edit-before-Read errors target MEMORY.md — add "Read in the same turn immediately before Edit" to the memory-update convention (also serves multi-session hygiene, §2.4).
- **Pause/resume protocol** `[IS]`: eight steering messages to land one clean pause in E-239. Add a "Pausing and Resuming a Dispatch" subsection to `implement/SKILL.md`: finish the in-flight story through staging/DONE, hold team warm, "continue" resumes.
- **Stale doc**: `docs/E-221-HANDOFF.md:166` still instructs running the removed `TeamCreate` `[MC]` — fix or archive; reinforce in `agent-team-compliance.md` that mechanism changes are stated proactively.
- **Flaky read channel**: 14+ narrated empty-then-correct-on-retry events confirm the transport issue, and `tool-output-integrity.md` is working as designed `[IS]` — monitor, no process added.

### 4.4 Skills surface

- **Add YAML frontmatter to all 10 skills** `[MC]`: none has it, so Skill-tool discovery is inoperative project-wide; only CLAUDE.md-routed skills ever fire (implement 30, plan 20, spec-review 4; four reference skills ≤5 loads in 913 sessions). Update `agent-standards` to require frontmatter going forward.
- **Retire/fold the dead reference skills** `[MC]`: fold `multi-agent-patterns` into always-loaded `dispatch-pattern.md` (it overlaps it anyway, and becomes the home for §4.3's tool-contract notes); inline 3-bullet essentials where agent defs cite `filesystem-context`/`context-fundamentals`; move `agent-standards` to docs as CA reference.
- **Fix `workflow-help` drift** `[MC]`: it falsely claims internal skills "load automatically" and omits `bb report` — the sole product surface.
- **Decide `ingest-endpoint`'s fate** `[MC]`: zero loads ever, stalest file, depends on rules that have churned since March — reconcile or archive.
- **De-duplicate the codex skills' triage discipline** `[MC]`: extract the shared read-receipt/triage procedure into one referenced file.
- **New `operator-runbook` skill** `[IS]`: the backfill→recompute→verify ordering footgun lives only as a CLAUDE.md sentence and the maintenance commands have near-zero guided invocations; encode the ordered recipes (backfill, reload-annotated-pitches, fix-self-games, redeploy) plus a reconcile→verify→interpret-residual section (or standalone `reconcile-audit`) once E-257 lands.
- **Do NOT add a review-landed-commit skill** — covered by codex-review's standalone path; add a checklist subsection there instead `[IS]`.

---

## 5. Learning Loop & Backlog

### 5.1 Promote-to-rule pipeline (implements the already-decided memory-lifecycle policy — do not re-decide it)

The policy (promote memory→rule when it recurs or generalizes; strike when the named code is deleted) is decided but **untriggerable** (citation counting with no counter) and **homeless** (waiting on DRAFT E-255) `[MC]`. Land it, event-driven, in `.claude/rules/context-layer-assessment.md` as part of E-255:

1. **Trigger 7 — "reusable behavioral lesson surfaced":** evaluated at every closure like the existing six; if a lesson recurred this epic OR generalizes beyond one agent, promote it to its load target now. This replaces the uncountable "cited across 2+ epics" criterion with the always-firing closure gate.
2. **Load-Target Classification:** every codified lesson is typed — (a) universal-behavioral → `paths:"**"` rule/CLAUDE.md; (b) role-scoped → agent def or MEMORY.md top-200; (c) path-scoped rule; (d) workflow skill; (e) reference-only topic file. Only (e) may terminate in a non-auto-loading file, and only for lookup material. Today the gate certifies "recorded," not "recallable" — recorded-but-dormant is the default failure `[IS]`.
3. **Two immediate promotions** proving the pipeline: move the grep-match trap ("never rule on a grep/OR-pattern match — Read and quote the literal line") from PM's topic file into `tool-output-integrity.md`'s Prohibitions (it's currently invisible to every non-PM agent `[MC]`); and promote "read reviewer findings to completion before characterizing" from the Related-discipline aside into a numbered Response-protocol step (the ad-hoc main-session context where E-230 actually failed is the thin spot `[IS]`).
4. **Staleness eviction (deletion-side symmetry):** closure procedure gains "for each file/flag/table this epic DELETED, grep rules/agents/MEMORY.md for references; strike or annotate." The cross-season saga — user asked ~5× while passes leaf-patched `[MC]` — is the standing proof this direction is missing.
5. **Memory retirement at closure:** PM greps Pending-Work for the archived epic's ID (E-149 sat listed as READY months after completing `[IS]`).

### 5.2 Idea/signal lifecycle sustainment

Backlog state: 73 CANDIDATE / 21 PROMOTED / 8 DISCARDED / **0 DEFERRED ever**; 6 of 8 discards came from one strategic reframe; 43 CANDIDATEs past their own Review-By date; every sampled `Last reviewed` equals `Created` `[MC]`. Capture works hard (~22 new ideas in the last handful of epics); pruning never runs. Fixes, all small edits:
- **Recorded triage verdict at closure** (`implement/SKILL.md` Step 4): required History line `Ideas triaged: promoted=[], discarded=[], deferred=[], N past-due` — same recorded-verdict shape as the doc/context-layer gates beside it, non-blocking but non-skippable.
- **Triage-your-own-captures:** each idea the closing epic created gets promote / keep-with-trigger / discard-eligible assigned while the scoping context is fresh.
- **Give the 90-day sweep an executor:** a scheduled monthly PM backlog sweep (cron precedent: morning-run) walking past-due rows; cross-reference from `ideas-workflow.md` so the cadence names its trigger.
- **Age-out rule:** CANDIDATE >180 days past Review-By auto-converts to DEFERRED (reversible) at the next sweep; closure summary prints the past-due count so growth is visible when it happens.
- ~~Vision curation is overdue~~ **CORRECTION (2026-07-07, orchestrating session):** the curation session ran 2026-07-05 (commit `ef375b2`) — VISION.md is reconciled to reports-first and 29 signals were cleared. This bullet's evidence predated it. The *sustainment* items above still stand; the one-off is done.

---

## 6. Proposed Change List

| # | Change | File(s) | Size | Expected effect | Home |
|---|---|---|---|---|---|
| 1 | Persist-then-message-the-path: file-backed reports, path-only relay, idempotency ids, ACK, round-2 deltas | `dispatch-pattern.md`, `implement/SKILL.md`, `tool-output-integrity.md` | M | Drops→file reads; ~112 dup-turns + relay context volume eliminated; compaction pressure drops | E-255 |
| 2 | Tee codex-review output to file + RESULT_FILE/wc receipt; ACMR default diff | `scripts/codex-review.sh`, `codex-review/SKILL.md` | S | Closes fabrication incident class; Codex finishes test sweep on big epics | Immediate |
| 3 | edit-verify memory-path carve-out | `.claude/hooks/edit-verify.sh` | S | Kills 100%-FP block on every memory write | Immediate |
| 4 | CR rubric additions: consumer-audit + twin-path checklist, adversarial assertions, edge-case enum, concurrency question, security trigger, self-load fallback, cumulative migration baseline, no-`|head`, verbatim pytest evidence | `.claude/agents/code-reviewer.md` | M | Directly targets classes 1,3,4,7,8,9 (≈114 verified findings) | New epic (review-system hardening) |
| 5 | Unconditional closure CR integration review; Codex-before-CR ordering (or drop redundant 4a); mechanical invariant-audit triggers; AC×surface matrix | `implement/SKILL.md` | M | Whole-epic review on every dispatch; ends approve-then-supersede loop | New epic (same) |
| 6 | Context-layer stories get a review gate; semantic-read doc sweeps | `implement/SKILL.md`, plan/context-layer rules | S | Closes class 5 (16 findings, structural hole) | New epic (same) |
| 7 | Single-source Codex rubric (embed CR checklist at prompt time) | `codex-review/SKILL.md`, `.project/codex-review.md` | S | Ends silent rubric drift between reviewers | New epic (same) |
| 8 | Closure runtime smoke (Step 1c): report generate + verify-aggregates + morning-run dry-run; CR authorized as runner | `implement/SKILL.md`, `code-reviewer.md`, `docs/production-deployment.md` | M | First live-runtime gate; catches populated-DB & wrong-output classes | E-256 |
| 9 | Expedite E-257 scoreboard to READY; fold counters into smoke | `epics/E-257.../epic.md` | M | North Star gets its enforcement mechanism | E-257 |
| 10 | CI workflow: pytest + case-insensitive PII sweep + docker build; wire/delete `smoke_test.py` | `.github/workflows/ci.yml`, `src/safety/pii_scanner.py`, `scripts/` | M | Static gate stops being per-machine ritual; DOA-on-fresh-clone caught | E-256 |
| 11 | Report-time plausibility gate (FPS/P-PA range checks) | `src/reports/generator.py` or `src/api/db.py` | S | Operator stops being the only QA on impossible stats | E-257 or new story |
| 12 | PII: fixture-aware scanner + gate `epics/`/`.project/` via check_doc_pii wrapper | `src/safety/pii_scanner.py`, `.claude/settings.json`, hook wrapper | M | Ends fixture FPs; closes the minor's-name planning-artifact hole (IDEA-102) | New epic / E-256 |
| 13 | Secret-read guard hook (.env / secrets/ Read+Bash deny) | `.claude/hooks/secret-read-guard.sh`, `.claude/settings.json` | S | Prevents credential ingestion into context | Immediate |
| 14 | `multi-session-coordination.md`: dispatch claim, repo-state channel, memory hygiene; worktree-reuse 3-case; global-guard note + stale-worktree notice | new rule, `implement/SKILL.md:117`, `worktree-isolation.md`, `worktree-guard.sh` | M | Ends ungoverned parallel-session mode; prevents double-dispatch | E-255 |
| 15 | Model/effort: CA→opus[1m]; UXD→sonnet (+scope fix); api-scout `effort: medium`; Explore routing line | 3 agent defs, `agent-routing.md` | S | Right-sizes the three edge misallocations | Immediate |
| 16 | PM status choreography collapse (IN_PROGRESS fire-and-forget; verify+DONE combined) | `implement/SKILL.md` | S | ~2 fewer PM round-trips per story (~half of PM traffic is status flips) | E-255 |
| 17 | Path-reference story handoffs (replace verbatim paste; renegotiate Anti-Pattern #2) | `implement/SKILL.md` L130/142/236/255/670 | S | ~330K chars/6-sessions of duplication removed; stale-paste risk gone | E-255 |
| 18 | Shutdown = wait for `teammate_terminated`; canonical teammate-id table; idle-only no-op rule | `implement/SKILL.md`, `dispatch-pattern.md` | S | Cleaner closures; ends respawn-scar id churn | E-255 |
| 19 | Plan right-sizing: S/M/L path, delete 3-iteration loop, single-source template rule, canonical scorecard schema, READY-freshness gate | `plan/SKILL.md`, `epic-template.md`, `product-manager.md`, `workflow-discipline.md` | M | Ceremony proportional to size; yield becomes measurable; stale READYs can't dispatch | E-255 |
| 20 | Skill frontmatter ×10; fold multi-agent-patterns into dispatch-pattern; fix workflow-help; decide ingest-endpoint; dedupe codex triage prose | `.claude/skills/**` | M | Skill discovery works; dead 36KB stops pretending to load | E-255 |
| 21 | Learning loop: trigger 7 + load-target classification + eviction check + 2 immediate promotions + memory retirement | `context-layer-assessment.md`, `tool-output-integrity.md`, `implement/SKILL.md` | M | Lessons land where they load; loop prunes as well as accretes | E-255 |
| 22 | Backlog: recorded triage verdict, own-capture triage, scheduled sweep, age-out, past-due counter | `implement/SKILL.md`, `ideas-workflow.md`, templates | S | Backlog gains its first routine shrink mechanism | E-255 |
| 23 | Pause/resume dispatch subsection; fix stale TeamCreate line | `implement/SKILL.md`, `docs/E-221-HANDOFF.md` | S | One-message pauses; no removed-tool instructions | E-255 / immediate |
| 24 | SendMessage approval semantics + agent-teams tool contract + 256KB-log + same-turn memory-Read notes | `dispatch-pattern.md` (post-fold), `tool-output-integrity.md` | S | Removes the widest-spread retry loops (21 sessions; 30 read-gate errors) | E-255 |
| 25 | Post-E-251 gap re-measurement after ~5 epics using canonical scorecards | (process, no file) | S | Empirically tests the routing-era hypothesis; calibrates further rubric spend | Process note in new review epic |

Suggested epic packaging: **E-255** absorbs the context-layer/dispatch-mechanics/learning-loop cluster (1, 14, 16–24); **E-256** absorbs CI/smoke/platform (8, 10, parts of 12); **E-257** the scoreboard (9, 11); a **new "review-system hardening" epic** takes 4–7 + 25; items 2, 3, 13, 15 are immediate/small enough to land outside epic ceremony (though per `feedback_small_epics_for_ui`, 13 touches settings and can ride E-255).

---

## 7. What NOT to Change

Name these explicitly so future optimization passes don't churn them:

- **The staging boundary, per-story CR verdict, PM verify-against-worktree, and the closure full-suite-green gate.** Each has documented catches: red suites at closure in 3 sessions, implementer-summary drift caught by PM, 5–45 real CR blocks per session `[MC]`. Batching or eliding any of them reopens the exact failure it closed.
- **The main-session relay default.** It exists because peer DMs drop silently; both channels are lossy `[SEED]`. Fix delivery via persisted files (change #1) first; only revisit the relay mandate with evidence the drop failure has abated. Flagged boundary, not an edit.
- **The core-four model allocation** (PM/CR/SE/DE at opus[1m]/high) and **docs-writer/baseball-coach at sonnet** — both ends verified correct `[MC][IS]`. Cost passes should target the three named edges only.
- **`tool-output-integrity.md`** — the flaky-channel discipline is demonstrably working (14+ narrated catch-and-retry events, agents not asserting empty reads as truth) `[IS]`. Strengthen its content per §5.1; don't restructure it.
- **worktree-guard** — 6 denials, all correct, 0 false positives `[IS]`. Add the multi-session notice; don't loosen the modes.
- **Permission settings** — no Bash allowlist; near-zero prompt friction evidenced `[IS]`. Pre-populating one is complexity without a problem.
- **The Dispatch Authorization Gate and READY/dispatch separation** — plan-mode requests never auto-dispatch; the freshness gate (change #19) tightens this, it doesn't replace it.
- **The canonical-helper architecture** (`ensure_team_row`, `canonical_recompute`, `resolve_db_path`, etc.) and prevention-over-cleanup — this consolidation discipline is precisely what the twin-path review checklist leans on; the review gap is in *checking* mirrors, not in the consolidation pattern itself.
- **The itemized Review Scorecard practice** — post-E-233 epics itemize every finding, which is what closed the 71-finding opaque-era class `[SC][V]`. Change #19 standardizes the schema; the practice itself is already right.
- **The Explore-for-investigation pattern** — no new investigator agent; the built-in already fits `[MC]`.