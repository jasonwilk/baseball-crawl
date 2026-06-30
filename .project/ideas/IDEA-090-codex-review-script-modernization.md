# IDEA-090: Codex review/spec-review Script Modernization (v0.142.4)

## Status
`CANDIDATE`

## Summary
A set of independent, ergonomic cleanups to the two custom Codex wrapper scripts (`scripts/codex-review.sh`, `scripts/codex-spec-review.sh`) and their skills, surfaced by the CA+SE tooling evaluation that compared our custom `codex exec` wrappers against native `codex review`. The evaluation's KEEP-custom decision is already made and is NOT in scope here — these are forward maintenance/hardening items, not a re-litigation of custom-vs-native.

## Why It Matters
The scripts carry stale verification headers and one real under-feeding bug, and current Codex (v0.142.4) offers a cleaner persistence primitive that would harden the read-receipt gate. Keeping the review tooling accurate and current protects the spec-review and code-review gates that every epic passes through. None of these are urgent, but they are cheap and they reduce the chance of a reviewer silently seeing less than it should.

## Scope (the four cleanups, all surfaced by the CA+SE evaluation)
1. **Refresh stale version headers.** Both scripts' "verified against v0.107.0" headers → v0.142.4. Reaffirm the still-correct PROMPT-vs-diff-flag mutual-exclusivity note (empirically reconfirmed on v0.142.4 during the evaluation).
2. **Re-verify the sandbox-off branch.** Re-check whether the `CODEX_SANDBOX_OFF` / `--sandbox danger-full-access` branch is still needed, given current Codex's bundled-bubblewrap read-only fallback — it may be obsolete and removable.
3. **Adopt `-o/--output-last-message <FILE>`.** Use `codex exec`'s `-o/--output-last-message` to persist the final review message straight to the read-receipt `.txt`, removing the current re-run-to-persist step. This hardens the spec-review skill's read-receipt gate (the persisted file becomes a first-class output, not a reconstruction).
4. **Fix untracked-file under-feeding in `codex-review.sh` `uncommitted` mode.** The script currently sends untracked FILENAMES only, not CONTENTS (around lines ~150/159), so the reviewer cannot see new-but-unstaged files — whereas native `codex review` reads untracked contents. Feed untracked file contents so the code reviewer actually sees them. (This is the one item with a correctness flavor, not just ergonomics.)

## Rough Timing
Whenever the review tooling is next touched, or sooner if a missed untracked-file review (item 4) bites during a dispatch. No hard trigger; "someday / low-urgency maintenance," with item 4 the most worth doing proactively.

## Dependencies & Blockers
- [ ] None hard. CA owns the skill-side implementation when this is scoped (context-layer: `.claude/skills/codex-review/`, `.claude/skills/codex-spec-review/`, and the `scripts/codex-*.sh` wrappers).

## Open Questions
- Item 2: is the sandbox-off branch truly obsolete on v0.142.4 across both the devcontainer and the host, or is it still load-bearing for some environment? Verify before removing.
- Item 3: does `-o/--output-last-message` capture exactly the content the read-receipt gate expects (full final message), or only a summary? Confirm before swapping out the re-run-to-persist step.
- Item 4: feeding full untracked contents could enlarge the prompt for large new files — is a size cap or a per-file truncation needed?

## Notes
Filed 2026-06-30 from the CA+SE Codex-tooling A/B evaluation. **Evaluation conclusion (cross-reference):** keep the custom `codex exec` wrappers for BOTH the review and spec-review paths — native `codex review` (a) cannot apply our review rubric alongside a diff/scope target, (b) cannot path-scope, and (c) structurally cannot ingest a markdown spec directory as a review target (it scored 0/3 recall on the E-249 spec-review A/B, where our custom spec-review surfaced all 3 real defects F-A/F-B/F-C). These four items are the residual ergonomic/correctness cleanups left after that KEEP-custom decision. Context-layer work → route to claude-architect when promoted.

---
Created: 2026-06-30
Last reviewed: 2026-06-30
Review by: 2026-09-28 (90 days from created)
