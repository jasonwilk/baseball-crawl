# E-262-06: Step 1d Preflight & Gate-Ordering Corrections (creds-profile + generate/reconcile order)

## Epic
[E-262: Post-Program Housekeeping](epic.md)

## Status
`TODO`

## Description
After this story is complete, two Step 1d procedure defects in `.claude/skills/implement/SKILL.md` are corrected: (1) the credential-liveness preflight checks the exact profile the smoke uses (`bb creds check --profile web`) instead of the bare multi-profile check, so a dead WEB profile masked by a valid mobile profile no longer passes; and (2) the generate → reconcile-scoreboard gate no longer false-FAILs on a self-caused plays-ingestion delta — resolved at the ROOT by requiring the `.smoke-fixture` generate target to be a TERMINAL GC team page (a completed season that gains no further games) with high play-by-play coverage, so the post-generate scoreboard reads a static corpus and measures only the epic's own derivation effect. Both are Step 1d preflight/gate corrections in the same file — bundled here as two distinct concerns.

## Context
Two Step 1d procedure defects, both surfaced in the E-256 Step 1d live-run (2026-07-12). Both are procedure edits to `.claude/skills/implement/SKILL.md`; no new machinery.

### IDEA-122 (creds-profile preflight — re-scoped here from story 03)
The Step 1d preflight (`implement/SKILL.md:496`, currently "credentials live (`bb creds check`)") uses the BARE multi-profile `bb creds check`. SE+CA verified in code: single-profile `bb creds check --profile web` (`creds.py:604`) and all-dead multi-profile (`:610-611`) already exit non-zero; the ONLY exit-0-on-a-dead-profile case is the MIXED multi-profile path (`any_valid` over `ALL_PROFILES = ("web","mobile")`, `credentials.py:46`), where a valid mobile masks a dead web. The smoke's `bb report generate` uses the WEB profile specifically (`GameChangerClient` defaults `profile="web"`, `client.py:159`; report-flow clients construct with no profile arg). So the bare multi-check false-PASSES the preflight on dead web creds. The fix is to pin the preflight to `bb creds check --profile web` — the exact profile the smoke exercises. There is NO correct command-side fix: making multi-profile exit non-zero on ANY dead profile would break the legitimate "any valid = usable" contract (an operator who configures only web would get spurious failures). Originally an item in story 03 (`creds.py`); re-scoped here after SE+CA confirmed the fix is skill-side and command-neutral.

### IDEA-123 (generate-before-reconcile ordering)
The Step 1d closure smoke runs `bb report generate <public_id>` BEFORE `bb report reconcile-scoreboard` (deliberately, so the ratchet measures the state the smoke just produced). But `generate` is a WRITER — it can ingest net-new plays — and the reconcile-scoreboard ratchet is one-way against a committed baseline. If the generate's net-new plays move a ratcheted axis (`dropped_pitch_events` / `no_plays_units`) relative to a baseline captured BEFORE the generate, the gate can trip on a legitimate self-caused ingestion delta — a false epic-FAIL. A closure gate that can false-FAIL on its own side effect erodes trust and drives needless remediation churn.

**Defect citation (E-260 freeze):** a gate-ordering defect identified during the E-256 Step 1d live-run (2026-07-12) — the false-FAIL is a structural hazard reasoned from the ordering; the gate did NOT actually false-FAIL and drive bad remediation (the operator interpreted the result manually). This is a correction to an existing procedure, not new machinery (CA review F2).

**Mechanism — SETTLED by operator decision (2026-07-12); grounded-frequency read DISSOLVED.** The root fix is FIXTURE STABILITY, not reordering or recurring re-snapshots:
1. **Terminal fixture requirement.** The `.smoke-fixture` generate target MUST be a terminal GC team page — a completed season that will never gain another game — with high play-by-play coverage. The skill text documents this REQUIREMENT only; the actual team identifier stays in the gitignored `.smoke-fixture` file (operator-owned; real GC identifiers never enter tracked text).
2. **Keep the existing generate → reconcile-scoreboard order.** With a static fixture corpus, the post-generate scoreboard reading measures exactly the epic's own derivation effect, and the existing one-way ratchet already encodes the operator's directional principle (fidelity improvements pass, regressions trip; plays-derived counts converge on boxscore aggregates per the north star). No new judgment machinery.
3. **One bootstrap re-snapshot** of the reconcile-scoreboard baseline when the operator pins the fixture team (operator-owned, precedented per E-257).
4. **Why fixture stability, not the alternatives:** reorder-only would just move the false-fail to the NEXT epic's closure (the smoke's ingest still lands after the reading); re-snapshot-every-closure is a recurring operator burden. A terminal fixture kills the drift at the root — which is why no grounded-frequency measurement is needed: the mechanism is robust regardless of how often a target would ingest net-new plays.

This coordinates with E-257's convention that the reconcile-scoreboard baseline is operator-owned. The operator's specific fixture pick and its rationale are recorded in Notes (identifier kept out of tracked text).

## Acceptance Criteria
- [ ] **AC-1 (IDEA-122)**: Given the Step 1d credential-liveness preflight, when it runs, then it invokes `bb creds check --profile web` (the exact profile the smoke's `bb report generate` uses) rather than the bare multi-profile `bb creds check`, so a dead WEB profile masked by a valid mobile profile no longer passes the preflight. No `src/cli/creds.py` change is made (the command is already correct per-profile).
- [ ] **AC-2 (IDEA-123)**: Given the Step 1d procedure in `implement/SKILL.md`, when the `.smoke-fixture` generate target is described, then it documents the REQUIREMENT that the target be a terminal GC team page (a completed season that gains no further games) with high play-by-play coverage — and does NOT embed the actual team identifier in the tracked skill text (it lives in the gitignored `.smoke-fixture` file).
- [ ] **AC-3 (IDEA-123)**: Given the terminal-fixture requirement, when the Step 1d procedure is read, then it KEEPS the existing `generate` → `reconcile-scoreboard` order (a static corpus makes the post-generate reading measure only the epic's own derivation effect) and states that the reconcile-scoreboard baseline is re-snapshotted ONCE at fixture bootstrap (operator-owned), consistent with E-257 — no per-closure re-snapshot and no reorder.
- [ ] **AC-4 (IDEA-123, bootstrap check)**: Given the fixture-bootstrap instructions, when the operator pins the fixture team, then the procedure instructs verifying the pinned team's play-by-play coverage in the dev DB (a games-with-plays count) as part of the one-time bootstrap.

## Technical Approach
Both fixes are procedure edits in `.claude/skills/implement/SKILL.md` (Step 1d) — one file, two distinct concerns, no new machinery.

**IDEA-122 (creds-profile):** a one-token change to the preflight line (`:496`) — pin it to `bb creds check --profile web` (the profile the smoke exercises) instead of the bare multi-profile check. Ready-now, no open question. Frame the fix as "check the profile(s) the smoke actually exercises — today that is web only"; if a future smoke step exercises mobile, extend the preflight then.

**IDEA-123 (ordering) — mechanism SETTLED (see Context):** the fix is a skill-text edit that (a) documents the terminal-fixture REQUIREMENT for the `.smoke-fixture` generate target, (b) keeps the generate → reconcile order, and (c) records the one-time operator-owned bootstrap re-snapshot + the plays-coverage bootstrap check. No candidate-mechanism decision is left open and no measurement is required — the terminal fixture removes the drift at the root. The implementer documents the requirement; the actual fixture identifier is operator-supplied via the gitignored file and MUST NOT be written into the skill.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `.claude/skills/implement/SKILL.md`

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
- [ ] Context-ratchet holds (or any net growth is operator-signed at closure)

## Notes
Sources: IDEA-122 + IDEA-123 (both from the same E-256 Step 1d live-run). IDEA-123 interacts with E-257's reconcile-scoreboard baseline-ownership model.

**IDEA-122 landing (SE+CA consult, 2026-07-12):** SE and CA both verified the code and confirmed IDEA-122 belongs here, not in story 03: the false-green is only the mixed multi-profile case, there is no correct `creds.py` fix (the "any valid = usable" contract must hold), and the fix is the skill-side `--profile web` preflight — story 06's exact file/section. CA's bundle call: keep 122 + 123 as two distinct ACs in one story. Both concerns are now settled (no open question at the story level).

**IDEA-123 mechanism — OPERATOR DECISION (2026-07-12):** the grounded-frequency read is DISSOLVED; the root fix is a terminal, static `.smoke-fixture` corpus (see Context). Operator's recorded fixture pick and rationale (the concrete GC identifier is NOT written here — it lives only in the gitignored `.smoke-fixture` file): a same-season terminal school-season team (the 2026 spring freshman team) — chosen because it is a terminal school-season page (no further games), operator-scored (ground-truth scorekeeping), ~school-season size (not the 80+ game cost of a longer corpus), and — critically — the SAME season year as the dev DB, so it does not create a second `seasons` row (a 2024/2025 fixture would permanently force `--season-id` on `dedup-players` and add a second season — rejected for that reason).

**CA holistic review (2026-07-12, iter 1/3) incorporated:** F2 (IDEA-123 citation reworded — the gate did not actually false-FAIL; reasoned structural hazard, operator interpreted the E-256 result manually); F3 (the grounded-frequency read is now moot — the terminal-fixture mechanism removed the dependency entirely).
