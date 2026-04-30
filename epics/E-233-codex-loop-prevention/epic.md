# E-233: Codex Review Loop Prevention

## Status
`READY`

## Overview
Install structural guards in the codex-review and implement skills (plus a paired memory entry) that bound user-directly-invoked codex-review re-runs, detect regression candidates against prior dispositions, and provide a fresh-eyes escape hatch when a current finding flips a prior fix. Goal: end the multi-round codex loop pattern observed in two recent epics.

## Background & Context

The agent ecosystem has been stuck in codex finding/regression loops twice in recent history. The most recent and best-documented instance is **E-229 closure**, which ran nine rounds of codex review:

- **Rounds 1-2**: Real, high-value findings — routing mismatches on AC-10, monkeypatch seam issues, missing operator surfaces (Codex-F1, F2, F6 in the E-229 history). Fixes were correct, no regressions.
- **Rounds 3-6**: Diminishing returns. Each round produced 1-3 findings, mostly stylistic / Tech Notes wording / fragment ordering. Fixes reasonable in isolation.
- **Round 7**: Over-correction. A finding about "Tech Notes ambiguity" in the format-string rule was remediated by tightening the wording, which created a contradiction with the literal auth-expiry append clause (resolved by the 2026-04-29 PM ruling on Reading (a)).
- **Rounds 8-9**: Regression. Round 9 surfaced a finding that was substantively the inverse of a round 7 disposition — codex recommended undoing what an earlier round had explicitly fixed.

The user flagged this as the second occurrence of the same pattern. The unifying signature across both instances:

1. Early rounds have high signal.
2. Middle rounds drift toward style/wording.
3. Late rounds flip prior framings.

**Root cause analysis**: The trigger isn't bad code review. It's that codex re-reads the same diff cold each round and rediscovers framings the team has already adjudicated. There is no mechanism for codex to know what the team decided in round N-1, and there is no per-invocation counter on user-directly-invoked codex re-runs. The implement skill's existing 2-round circuit breakers in Phase 3 (per-story CR) and Phase 4b (codex inside dispatch) bound the *automated* loops, but they do NOT bound user-directly-invoked codex re-runs that happen between dispatch completion and final closure.

The intervention is structural: a circuit breaker on user-directly-invoked codex re-runs (also covering implement Phase 4b's automated invocation so the same epic worktree's counter increments uniformly), a disposition log that codex review writes per round, a regression detector that compares current findings against prior dispositions, a fresh-eyes escape hatch that fires when the detector flags a regression candidate (firing from BOTH call sites — implement Phase 4b and the user-directly-invoked codex-review skill path), and a paired memory entry that codifies the "round 3+ requires sharper filter" guidance alongside the existing `feedback_fix_real_findings.md`.

**Out-of-scope future hardening signals (deferred per fresh-CA review):**
- The breaker addresses codex's blindness across rounds but does not address the deeper "main session iterates to clean" psychology. A future epic could add "round 1 produced no MUST FIX → no round 2 by default" — strictly stricter than the current cap=2 rule. Captured here for awareness, not action.
- Stories 02 and 04 are tightly coupled (both contribute to the round-counter contract). Backing out one without the other leaves silent waste; this is acceptable for a unified-design epic, but reviewers should treat 02 and 04 as a contract pair.

## Goals
- Bound USER-DIRECTLY-INVOKED codex-review skill re-runs to 2 rounds per epic closure. The implement skill's existing per-story (Phase 3) breaker bounds the in-dispatch automated loops at a different layer; this epic addresses the unbounded path where the user invokes codex-review directly between dispatch completion and final closure. The implement skill's Phase 4b "and review" pass shares the same round counter (it counts as round 1) so the user cannot effectively double-dip by combining "and review" with subsequent direct codex-review invocations.
- Surface regression candidates automatically: when a current codex finding overlaps in files + summary with a prior FIXED disposition, tag it `[REGRESSION CANDIDATE]` before triage.
- Break out of the loop when a regression is suspected: fresh-eyes escape hatch spawns a Task-tool code-reviewer (no shared prior-judgment context with the dispatch team CR) to judge whether the current finding is a real new issue, would regress the prior fix, or is a genuine framing choice. Trigger fires from BOTH the implement-skill Phase 4b path AND the user-directly-invoked codex-review skill path (single protocol, two call sites).
- Codify the "diminishing returns" pattern in user auto-memory so future PM/main-session work resists re-running codex past round 2 without justification.

## Non-Goals
- Bounding standalone codex-review invocations (without an epic worktree). The loop pattern was observed during epic closure only; standalone reviews are user-deliberate single-shot invocations. The skill exemption documents the "if pattern recurs in standalone, extend" revision trigger inline.
- Bounding the per-story CR loop in implement Phase 3. It already has a 2-round circuit breaker and is not the loop hot zone the user flagged.
- IDEA-volume telemetry (rec #5 from CA's assessment). Soft heuristic without enforcement is hard to AC. Filed as IDEA-087 with the trigger condition for future codification.
- Persistent disposition logging that survives epic closure. The disposition log is intentionally ephemeral — it lives at epic-worktree root and dies with the worktree at closure. Cross-epic loop detection is out of scope.
- Expanding the breaker beyond round count (e.g., "no round 2 if round 1 had no MUST FIX"). Captured as future hardening signal in Background; out of scope this epic.

## Success Criteria
- Codex-review skill at round 3 of the same epic produces a hard-stop message naming the loop pattern, requiring an explicit authorization phrase or reset to advance. The counter is only persisted to disk if the gate passes (round-3 hard-stop does NOT advance the counter to 3 — it stays at 2 until authorized).
- A regression candidate tag appears on current findings when codex re-runs surface findings that overlap in files + summary with prior FIXED dispositions in the same epic worktree.
- A fresh-eyes code-reviewer spawn is documented as the trigger response in BOTH the codex-review skill's advisory triage step AND the implement skill's Phase 4b Step 3. Single protocol (defined in implement skill), two call sites. Verdict shape (a)/(b)/(c) with a spawn prompt template that carries ONLY the per-finding context (current finding, prior disposition, files, diff) and explicitly excludes any prior-judgment context from the dispatch team CR.
- A new feedback memory file `feedback_iteration_diminishing_returns.md` exists at the auto-memory directory with the canonical frontmatter shape and an index pointer in MEMORY.md.
- The implement skill's Phase 4b counter mirror increments the round counter via the canonical contract at `.claude/rules/codex-review-breaker.md`, sharing state files with the codex-review skill section. After this epic ships, an "and review" pass produces round 1 of the new breaker; subsequent user-direct codex-review invocations during the same closure increment the same counter; round 3 hits the gate.

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-233-01 | Paired feedback memory: iteration diminishing returns | TODO | None | claude-architect |
| E-233-02 | Rule file + codex-review skill: re-run circuit breaker + disposition log | TODO | None | claude-architect |
| E-233-03 | Regression detector + fresh-eyes escape hatch | TODO | E-233-02, E-233-04 | claude-architect |
| E-233-04 | Implement skill Phase 4b: counter mirror | TODO | None | claude-architect |

## Dispatch Team
- claude-architect

## Technical Notes

### TN-1: File scope and locations

The epic produces five runtime artifacts plus one planning artifact in the epic directory.

**Runtime files (created/modified by Story implementation):**
- `/workspaces/baseball-crawl/.claude/rules/codex-review-breaker.md` (new — created by Story E-233-02 implementer) — canonical contract for the round counter and disposition log behavior. Implementer formalizes this file by prepending a `paths:` frontmatter block to the planning draft (see "Planning artifact" below). Single source of truth; both consumers reference this rule.
- `/workspaces/baseball-crawl/.claude/skills/codex-review/SKILL.md` (modify) — adds Re-run Circuit Breaker section (referencing the canonical contract in `.claude/rules/codex-review-breaker.md`), Step 3.5 regression detector, disposition-log write at Step 6, Step 4 escape-hatch invocation reference, standalone-mode exemption block.
- `/workspaces/baseball-crawl/.claude/skills/implement/SKILL.md` (modify) — adds Phase 4b Step 3 item 7 fresh-eyes escape hatch (canonical protocol) AND a Phase 4b Step 1 mirror of the round counter / circuit breaker logic (referencing the canonical contract in `.claude/rules/codex-review-breaker.md`).
- The auto-memory directory for this project — concretely `/home/vscode/.claude/projects/-workspaces-baseball-crawl/memory/feedback_iteration_diminishing_returns.md` (new) — paired feedback file alongside `feedback_fix_real_findings.md`. The path is a per-machine resolution of the project's auto-memory directory; ACs verify at the resolved path on the implementer's machine, not by literal-string match.
- The same auto-memory directory's `MEMORY.md` (modify) — add index pointer line under the Feedback group.

**Planning artifact (epic directory, deleted during Story 02 dispatch):**
- `/workspaces/baseball-crawl/epics/E-233-codex-loop-prevention/codex-review-breaker.md.draft` — the canonical-contract content as a planning artifact. No `paths:` frontmatter; not loaded into agent context. Story E-233-02 AC-0 implementer copies this content (and prepends the `paths:` frontmatter block) to create the runtime rule file; Story E-233-02 AC-0b deletes the draft after the runtime rule file is created and verified. **Lifecycle**: the draft exists during planning and through Story 02 AC-0; AC-0b removes it. Post-dispatch the runtime rule file at `.claude/rules/codex-review-breaker.md` is the sole source of truth (single source of truth; eliminates divergence risk if the rule evolves later). The epic's git history preserves the draft for archival evidence — no in-tree copy is needed.

The auto-memory directory is the user's per-machine project memory, not under `.claude/agent-memory/`. It is the same directory the existing `feedback_fix_real_findings.md` lives in, ensuring both files load via the same MEMORY.md index. Implementer must use absolute paths to the auto-memory directory (it is outside the epic worktree but inside the user's home directory) — the worktree-guard hook does not block writes to this path because it is outside `/workspaces/baseball-crawl/`.

### TN-2: Skill-runtime state files (worktree root, not under `.claude/`)

Two ephemeral skill-runtime state files live at the **epic worktree root**, not under `.claude/`:

- `<epic-worktree-path>/.codex-review-rounds` — a single integer, the codex round counter for this epic closure (covers both Phase 4b automated invocations AND user-direct codex-review invocations per `.claude/rules/codex-review-breaker.md`).
- `<epic-worktree-path>/.codex-dispositions.jsonl` — append-only JSON-lines log, one entry per disposition.

The `<epic-worktree-path>` placeholder refers to the epic worktree path created by `implement/SKILL.md` Phase 2 Step 1 (`/tmp/.worktrees/baseball-crawl-E-NNN/`). All consumers (codex-review skill section, implement Phase 4b mirror) MUST use the dispatch-context-provided path, NOT glob-detect worktrees on disk. See `.claude/rules/codex-review-breaker.md` for the canonical contract that governs both consumers.

These files are deliberately NOT in `.claude/` because they are skill-runtime state, not configuration. They die with the worktree at closure (no persistence, no commit). Story 02 and Story 04 must include a Technical Approach note pointing this out: "Both files are deliberately NOT in `.claude/` — they are skill-runtime state, not configuration, and they vanish with the worktree at closure. This heads off a future 'shouldn't this be under `.claude/`?' finding."

The parallelism between the two file paths (both at worktree root, both dotfile-prefixed, both ephemeral) is intentional. Both consumer call sites (codex-review skill section AND implement Phase 4b mirror) read and write these files symmetrically.

### TN-3: Disposition log entry shape

Each line in `.codex-dispositions.jsonl` is a single JSON object:

```
{"round": 1, "finding_id": "R1-F1", "summary": "Routing mismatch on AC-10", "files": ["epics/E-229/E-229-05.md"], "disposition": "FIXED", "disposition_summary": "Moved to epic-level Closure Tasks"}
```

Field semantics:
- `round`: integer, the codex round this finding was raised in (1-indexed). Sourced from the breaker counter value at the time the finding was first reported (not the disposition write time, in case rounds bump between).
- `finding_id`: ALWAYS namespaced as `R{round}-{codex_id_or_ordinal}` — never the raw codex `F1`/`F2` directly. This guarantees globally unique finding IDs across rounds (codex assigns the same `F1` in round 1 and round 2; without namespacing, the disposition log would have ID collisions). The `{codex_id_or_ordinal}` part is the codex-assigned ID where present (e.g., codex's `F1` becomes `R1-F1` in round 1 and `R2-F1` in round 2). Where codex does not assign a stable ID, the skill substitutes `F{ordinal}` where ordinal is the 1-indexed position of the finding in the current round's codex output, counting ALL findings (assigned and unassigned). This makes the suffix predictable regardless of mix.
- `summary`: first line of the codex finding text, truncated to ~120 characters at a word boundary. Extracted from the codex output, NOT from PM's prose disposition.
- `files`: array of FILE PATHS ONLY — line and column suffixes MUST be stripped at write time. If codex cites `src/foo.py:42` or `src/foo.py:42:7`, the writer strips the trailing `:<digits>(:<digits>)?` suffix and stores `src/foo.py`. The stored value is a well-formed pathspec that downstream consumers (TN-11 diff-context resolution invoking `git -C <epic-worktree-path> diff main -- <files>`) can pass directly without further parsing. Stripping rule: if a codex-cited path matches `<path>:<digits>(:<digits>)?$`, strip the trailing colon-digits group(s); otherwise preserve as-is. Deduplicate the resulting array (a single Codex finding may cite the same file at multiple line numbers — store the path once).
- `disposition`: one of `FIXED`, `DISMISSED`, `FALSE POSITIVE`. Sourced from PM's disposition record.
- `disposition_summary`: free-text reasoning for the disposition. Sourced from PM's prose disposition (the same text PM writes to epic History or the standalone remediation log).

The log is append-only during a single epic closure. Each round's dispositions are written at Step 6 of the headless path, after PM has recorded dispositions in the epic History (or in the standalone remediation log). Truncation happens only on `reset codex breaker` (see TN-4) — both the counter and the log are wiped together so the next round 1 starts fresh.

### TN-4: Re-run Circuit Breaker semantics

This section documents the breaker behavior. The canonical contract (state files, scope, increment rules, prompt-gen behavior, resume behavior) lives in `.claude/rules/codex-review-breaker.md`; this section is the operational description that the codex-review skill section embodies. TN-10 below is now a pointer summary into the rule file.

On entry to the headless path Step 1 AND the prompt-generation path Step 1, the skill:

1. Reads `<epic-worktree-path>/.codex-review-rounds` (default 0 if file does not exist). Call this `current_count`. The skill MUST use the dispatch-context-provided epic-worktree path; it MUST NOT glob-detect worktree directories on disk to discover one (an unrelated epic's worktree must not be picked up).
2. Computes `prospective_round = current_count + 1`. This is the round number for THIS invocation if it advances.
3. Gate check: if `prospective_round >= 3` AND the user's invocation phrase does NOT contain the authorization phrase for this exact round value AND does NOT contain the reset phrase, hard-stop. **Do NOT write the counter on hard-stop** — leave the file at `current_count`.
4. Hard-stop message shape:

> This is round N of codex review for E-NNN. The loop pattern (rounds 1-2 produce real findings, round 3+ tend toward stylistic regressions and may flip prior dispositions) is a known anti-pattern — see `feedback_iteration_diminishing_returns.md`. To proceed, the user must explicitly authorize: "authorize round N codex review" (with N matching this exact round number). To reset the counter to zero AND truncate the disposition log, say: "reset codex breaker". Otherwise stop.

5. The hard-stop message MUST include: the round number (substituted from `prospective_round`), the epic ID, a reference to the feedback memory file, both the authorization phrase and the reset phrase verbatim.
6. Flow control after hard-stop: the main session presents the hard-stop message and ends the skill invocation. The user must re-invoke explicitly. Re-invocation paths:
   - User re-invokes with the exact authorization phrase `authorize round N codex review` where N matches `prospective_round`: skill writes `prospective_round` to the counter file and proceeds. The authorization is one-time — round N+1 (the next invocation) will hit the gate again at `prospective_round = N+1`.
   - User re-invokes with the reset phrase `reset codex breaker`: skill zeroes the counter file AND truncates `.codex-dispositions.jsonl` (both state files reset together — see TN-3). Skill proceeds with `prospective_round = 1`.
   - User re-invokes with neither phrase: gate fires again, hard-stop again. The skill never advances on its own — only the explicit phrases unlock it.

Phrase semantics:
- `authorize round N codex review` — N must literally match `prospective_round`. If the user says "authorize round 5 codex review" while `prospective_round` is 3, the gate does NOT pass (mismatched N). The skill falls back to the hard-stop message naming the correct round number.
- `reset codex breaker` — zeroes the counter file AND truncates `.codex-dispositions.jsonl`. Both state files reset together — the user explicitly wiped the slate, so prior dispositions are gone too.

Round 1 and round 2 invocations advance unconditionally (gate check fails because `prospective_round < 3`). The counter is written to `prospective_round` on advance.

**Prompt-generation path note**: The prompt-generation path increments the counter on entry (same gate logic as headless) but writes NO disposition log entries — the prompt-gen path produces no codex findings; it only assembles a prompt for copy-paste. This is intentional and correct: the counter measures user-driven invocation pressure regardless of whether the invocation runs codex headlessly or just generates a prompt the user copies elsewhere. Disposition log entries are produced only when codex actually runs (headless path Step 6).

**Resume scenario**: When a dispatch is resumed in a reused worktree (per implement skill Phase 2 Step 1), the state files (`.codex-review-rounds`, `.codex-dispositions.jsonl`) persist from the prior session. Behavior on resume: counter starts at the persisted value; new invocations increment from there. If the operator wants a clean slate, they invoke `reset codex breaker` before the next codex pass.

Standalone mode (no `<epic-worktree-path>` available from the dispatch context) skips the entire counter mechanism. See TN-7.

### TN-5: Step 3.5 regression detector semantics

Inserted between current Step 3 (Evaluate output) and Step 4 (Offer advisory triage) in the headless path.

On entry:
1. If `<epic-worktree-path>/.codex-dispositions.jsonl` does not exist OR is empty, skip the detector entirely. (Round 1 has no prior dispositions to compare against.)
2. Otherwise, load all entries from the disposition log.
3. For each finding in the current codex output, compute matches against each prior disposition:
   - **File overlap**: at least one path in the current finding's `files` matches a path in the prior disposition's `files` exactly (string equality).
   - **Summary overlap**: case-insensitive token overlap of >= 50% between current finding summary and prior disposition `summary`. Tokens are whitespace-split, lowercased, leading/trailing-punctuation-stripped, AND filtered to remove tokens shorter than 3 characters and a small stop-word set (the, a, an, and, or, but, of, in, on, to, for, with, is, was, be, by, at, as, that, this, it, its). The 50% threshold applies to the SHORTER summary's filtered token set — at least half of the shorter summary's content tokens must appear in the longer summary's filtered token set.
4. A current finding "matches" a prior disposition when BOTH file overlap AND summary overlap hold. Annotate matched findings with one of:
   - `[REGRESSION CANDIDATE]` if the prior disposition was `FIXED` — indicates the current finding may flip a prior remediation.
   - `[PRIOR DISMISSAL]` if the prior disposition was `DISMISSED` or `FALSE POSITIVE` — indicates codex previously raised a similar finding that the team chose not to act on.
5. **Multi-match resolution**: if a current finding matches multiple prior dispositions, the highest-priority annotation wins (`REGRESSION CANDIDATE` > `PRIOR DISMISSAL`). The annotation cites the most-recent matching prior round (highest `round` value among matches). If multiple priors share the highest priority and same round, cite the first by `finding_id` ordering.
6. Annotated findings are passed through to Step 4 (advisory triage) with their tag visible in the user-facing output. The detector does NOT auto-dismiss; it surfaces context.

**Tag response semantics**:
- `[REGRESSION CANDIDATE]` triggers the fresh-eyes escape hatch protocol (see TN-6) BEFORE Step 4's normal triage proceeds for the tagged finding.
- `[PRIOR DISMISSAL]` is INFORMATIONAL ONLY. It does NOT trigger the escape hatch — the escape hatch fires only on REGRESSION CANDIDATE. The tag is shown to the user during triage so they can consider whether the prior dismissal still holds, but no automated workflow action is taken.

### TN-6: Fresh-eyes escape hatch — single protocol, two call sites

The escape hatch protocol is defined ONCE in `implement/SKILL.md` Phase 4b Step 3 (as new item 7) and is REFERENCED by `codex-review/SKILL.md` Step 4 (advisory triage) when an epic worktree path is available. This widens the trigger surface to cover BOTH the in-dispatch automated codex path AND the user-directly-invoked codex-review skill path — the latter is the loop hot zone this epic is designed to bound.

**Trigger**: Pattern-detected, NOT human-judged. The regression detector (TN-5) emits the `[REGRESSION CANDIDATE]` tag. The escape hatch is the policy that fires on that tag wherever Step 3.5 ran. Two call sites:

- **Implement skill Phase 4b Step 3 (item 7)**: codex was run by the dispatch automation; tagged finding came from Phase 4b's headless invocation.
- **Codex-review skill Step 4 (advisory triage)**: codex was run directly by the user (between dispatch completion and final closure); tagged finding came from the user-invoked invocation. Step 4 references item 7's protocol — it does NOT duplicate the protocol.

Note: only `[REGRESSION CANDIDATE]` triggers the escape hatch. `[PRIOR DISMISSAL]` is informational only (per TN-5).

The fresh-eyes spawn happens INSTEAD OF the normal remediation routing for the tagged finding. The escape hatch is bypassed in standalone mode (no epic worktree → no Step 3.5 → no tags → escape hatch never triggers).

**Mechanism (the canonical definition lives in `implement/SKILL.md` Phase 4b Step 3 item 7)**: When any current finding is tagged `[REGRESSION CANDIDATE]`:

1. Pause triage for the tagged finding — do NOT route to the existing remediation team or the user.
2. Spawn a code-reviewer via the Task tool. The spawn is NOT a teammate on the dispatch team — it is a one-shot Task-tool invocation with no shared message history with the dispatch team CR. The Task tool intrinsically provides a fresh instance; the load-bearing property is that the spawn prompt MUST NOT include any context from the dispatch team CR's prior judgments.
3. The spawn prompt provides ONLY the per-finding evaluation context: current finding text (pasted VERBATIM from codex output, not paraphrased), prior disposition entry (pasted VERBATIM from `.codex-dispositions.jsonl`, not summarized), file paths involved, and a diff context resolved per TN-11. It does NOT provide: the dispatch team CR's prior approval reasoning, the team's interaction history, or any prior remediation justifications beyond the single disposition log entry attached.
4. The spawned CR replies with one letter — (a) real new issue, (b) would regress the prior fix, (c) genuine framing choice — plus 1-2 sentences of reasoning.
5. Routing on the verdict:
   - (a) → proceed to remediation as normal (route the tagged finding to an implementer per the call-site's normal triage; for Phase 4b that's item 3 triage; for codex-review Step 4 that's the standard advisory triage path).
   - (b) → dismiss the current finding with the fresh CR's reasoning recorded in the disposition log. Do NOT route for remediation.
   - (c) → escalate to user with both framings and the fresh CR's reasoning. User chooses.

**Why a fresh Task-tool spawn and not the existing team CR**: The dispatch team CR was the one who approved the prior remediation. Asking them to re-evaluate creates a confirmation-bias risk — they already committed to the prior framing. A Task-tool spawn has no shared judgment history with the team's CR. This rationale must appear in the documented item 7 so it doesn't get optimized away later as "redundant — just ask the existing CR."

**Spawn prompt template** (canonical text for both call sites; placeholders `[paste codex finding text]`, `[paste from .codex-dispositions.jsonl]`, `[paths]`, `[team-name]`, `N`, `M` are intentional and remain as-is in the skill markdown):

```
You are a code-reviewer agent spawned for fresh-eyes regression check on the [team-name] team. This is a one-shot Task-tool invocation. You have NO shared judgment history with this team's existing code-reviewer; that is the design intent.

Two findings are attached below. The first is a CURRENT codex finding from round N. The second is a PRIOR disposition from round M (M < N) where the team marked the issue FIXED.

Current finding: [paste codex finding text]
Prior disposition: [paste from .codex-dispositions.jsonl]
Files involved: [paths]
Diff context: [resolve per TN-11]

Read both. Decide one of:
(a) The current finding is a real new issue (not a regression of the prior fix).
(b) The current finding would regress the prior fix — dismiss it.
(c) Both findings are correct; this is a genuine framing choice the team needs to make.

Reply with the letter and 1-2 sentences of reasoning. Do not propose remediation.
```

The escape hatch is orthogonal to the existing 2-round circuit breaker. The breaker says "stop after N rounds." The escape hatch says "this round flipped a prior round's framing — re-evaluate with fresh context."

### TN-7: Standalone mode exemption

Exact language to embed in the codex-review skill so the exemption doesn't read as oversight:

> **Standalone mode exemption**: When this skill is invoked without an epic worktree (`<epic-worktree-path>` not available), the re-run circuit breaker (Re-run Circuit Breaker section) and the regression detector (Step 3.5) are both skipped. Standalone post-dev reviews are user-deliberate single-shot invocations, not closure-loop iterations — the failure mode these mechanisms guard against has only been observed during epic closure. If the loop pattern is observed in standalone mode in the future, this exemption can be revisited (the disposition log path for standalone would be `.project/research/codex-review-YYYY-MM-DD-dispositions.jsonl`).

Story 02 must include this exact block. Story 03 must reference it for the detector's standalone behavior.

### TN-8: Paired feedback memory file shape

`feedback_iteration_diminishing_returns.md` uses the canonical project-memory frontmatter:

```
---
name: Diminishing returns past round 2 of codex re-review
description: After 2 rounds of codex re-review on the same epic, additional rounds drift toward stylistic regressions and may flip prior dispositions. Resist re-running codex past round 2 unless a new substantive change has been introduced.
type: feedback
---
```

Body has three sections in this order: rule, **Why:**, **How to apply:**.

- **Rule**: After 2 rounds of codex re-review on the same epic, additional rounds drift toward stylistic regressions and may flip prior dispositions. Resist re-running codex past round 2 unless a new substantive change has been introduced.
- **Why**: E-229 nine-round trajectory — rounds 1-2 produced real findings (routing mismatches, monkeypatch seams, missing operator surface), rounds 3-6 produced stylistic findings, round 7 over-corrected, round 9 regressed. Pattern matches a prior epic. Codex re-reads diffs cold each round and rediscovers framings the team has already adjudicated.
- **How to apply**: Treat round 2 as the natural endpoint. If codex output round 3+ proposes changes that contradict prior remediations or only adjust wording/style, dismiss them and trust the team's prior judgment. Use this in tension with `feedback_fix_real_findings.md` — small real findings still get fixed in rounds 1-2; rounds 3+ require a sharper "is this real, or is this codex chasing its tail" filter.

The cross-reference to `feedback_fix_real_findings.md` is required and explicit; both files load via the same MEMORY.md index and are intended to operate in tension.

MEMORY.md index pointer line (placement: under the existing "Feedback" group, alphabetical or thematic placement near `feedback_fix_real_findings.md`):

```
- [Diminishing returns past round 2](feedback_iteration_diminishing_returns.md) -- After 2 codex rounds, drift to stylistic regressions; pair with feedback_fix_real_findings.md
```

### TN-9: "And review" on this epic — validation pass definition

CA recommends running "and review" on this epic itself. The "and review" modifier produces ONE codex pass via implement Phase 4b's headless invocation. That single pass increments the round counter from 0 to 1 (round 1 of the new breaker for this epic, no gate trip because `prospective_round = 1 < 3`). If Phase 4b's existing 2-round automated remediation loop fires, that loop is INTERNAL to Phase 4b and produces remediation work but does NOT increment the new breaker counter further within the same Phase 4b invocation — Phase 4b's internal loop is bracketed by a single skill-level invocation, which advances the counter once.

**Validation pass definition (concrete and falsifiable)**:

The "and review" pass is the validation pass for this epic if and only if:

1. The codex round counter file at `<epic-worktree-path>/.codex-review-rounds` contains the integer `1` after the pass completes (round 1 advanced).
2. The disposition log at `<epic-worktree-path>/.codex-dispositions.jsonl` either contains valid JSONL entries (one per disposition recorded by PM during triage) OR is empty/absent (clean codex pass produced no findings).
3. If the codex pass produced findings AND the validation log entries exist, each entry conforms to the TN-3 schema (six fields, correct shape, non-empty disposition value).

This definition does NOT require the round-3 cap to fire — that cap fires only on round 3, which the "and review" pass cannot reach by itself (a single skill invocation = round 1). Round-3 cap correctness is verified by AC contract on TN-4 + Story 02 AC-2/AC-3/AC-10/AC-13 (gate behavior + hard-stop message + flow control + dispatch-context-only worktree-path detection), not by live test in this epic. Real round-3 validation comes when a future epic's user-direct codex re-runs hit round 3 in the wild.

Implementer note: do not panic if "and review" produces a clean round 1. The skills are short, focused additions; clean is plausible. A clean round 1 means the breaker counter ends at 1, the disposition log is empty (no findings to record), and any user-invoked re-runs would proceed cleanly through round 2 and trip the gate at round 3.

### TN-10: Round counter and disposition log — canonical contract (rule file)

The canonical contract is implemented at `.claude/rules/codex-review-breaker.md` per Story E-233-02. Both consumers (`codex-review/SKILL.md` Re-run Circuit Breaker section installed by Story 02, `implement/SKILL.md` Phase 4b Step 1 mirror installed by Story 04) reference that rule file as the source of truth. During planning, the contract content lives at `epics/E-233-codex-loop-prevention/codex-review-breaker.md.draft` (no frontmatter, no runtime loading); Story 02 formalizes the draft into the runtime rule file by prepending a `paths:` frontmatter block.

**Why a rule file, not just a TN**: The contract governs project-wide behavior across two skills indefinitely. A rule file:
- Persists past this epic's archival (TNs are archived with the epic; the rule stays loaded into context for any future agent touching the matched paths).
- Loads into context for any agent touching `.claude/skills/codex-review/**`, `.claude/skills/implement/**`, `epics/**`, or `.project/archive/**` via the `paths:` frontmatter (these are the planned `paths:` values; Story 02 ACs pin them).
- Is the project-standard location for cross-skill invariants.

**Pointer summary** (full contract at `epics/E-233-codex-loop-prevention/codex-review-breaker.md.draft` during planning; at `.claude/rules/codex-review-breaker.md` post-implementation):
- State files at `<epic-worktree-path>/.codex-review-rounds` and `<epic-worktree-path>/.codex-dispositions.jsonl`.
- Counter is per-epic-worktree, shared across both call sites (Phase 4b "and review" + user-direct codex-review).
- Round 3+ requires explicit `authorize round N codex review` (with literal N match) or `reset codex breaker` to advance; counter is NOT written on hard-stop.
- Reset zeros counter AND truncates log atomically.
- Resume: state persists with the worktree; reset before next pass for a clean slate.
- Standalone mode (no epic-worktree path from dispatch context): skip ALL counter + log behavior.
- `files` array in disposition log entries holds FILE PATHS ONLY — line/column suffixes (`:42`, `:42:7`) MUST be stripped at write time. Downstream consumers (TN-11 diff-context resolution) feed the array directly to `git diff main -- <files>` without further parsing.
- Disposition-log writes cover BOTH Phase 4b paths: headless-success (codex-review.sh ran) AND prompt-gen-fallback (codex-review.sh timed out / failed → user pasted findings). Both paths produce JSONL entries after PM records dispositions.

ACs in Stories E-233-02 and E-233-04 reference `.claude/rules/codex-review-breaker.md` directly as the canonical source. Implementers of either consumer MUST follow the rule file verbatim.

### TN-11: Diff-context resolution for fresh-eyes spawn

The escape hatch spawn prompt template (TN-6) has a `Diff context: [resolve per TN-11]` placeholder. This section is the resolution algorithm both call sites must follow.

The diff context's purpose is to give the fresh-eyes CR enough code context to judge whether the current finding is a regression of the prior remediation. The challenge: when the fresh-eyes spawn happens INSIDE Phase 4b (mid-dispatch), prior remediations are staged via `git add -A` (per implement skill staging boundary protocol) but NOT committed — they accumulate in the worktree until Phase 5 closure. So `git show <sha>` doesn't work mid-dispatch (no commit exists yet). The algorithm:

**Resolution algorithm**:
1. **If a commit SHA is available for the prior remediation** (post-closure user-invoked re-runs OR the rare case where the prior remediation was committed individually): use `git -C <epic-worktree-path> show <sha>`. This produces the cleanest single-commit diff.
2. **Otherwise** (in-dispatch, pre-closure, or any case where the prior remediation is staged but not committed): use `git -C <epic-worktree-path> diff main -- <files>`. This shows the cumulative epic delta on the affected files (all stories' staged changes from the epic worktree against main). It's slightly more context than strictly necessary (includes other stories' changes to the same files) but it captures the prior remediation's effect.

The `<files>` argument is the `files` array from the prior disposition's JSONL entry. Both consumers (implement Phase 4b Step 3 item 7, codex-review Step 4 reference) follow this same algorithm.

**Why not `git diff` (unstaged)**: `git diff` (no arguments) shows only unstaged changes. In Phase 4b mid-dispatch, prior remediations are staged via the staging boundary protocol — `git diff` would show ONLY the current round's unstaged work, missing the prior round's remediation entirely. That's why the algorithm uses `diff main -- <files>` instead, which captures all accumulated work.

## Open Questions
None outstanding. Q1, Q2, Q3 resolved during planning per History.

## History
- 2026-04-29: Created. CA-led design via consultation; PM frames ACs.
- 2026-04-29: User confirmed planning decisions: Q1 cap = 2 (round 3+ requires authorization); Q2 counter scope = per-closure (epic-scoped, dies with worktree); Q3 rec #5 (IDEA-volume telemetry) deferred to be filed as IDEA-087 at epic close.
- 2026-04-29: Iteration 1 internal review (PM holistic + on-team CA holistic, 13 distinct findings after merging duplicates, all ACCEPTED). Incorporation pass applied to epic.md, E-233-01.md, E-233-02.md, E-233-03.md.
- 2026-04-30: Iteration 2 review (fresh-eyes CA + CR spec audit). 17 distinct findings + 5 systemic risks across both sources. Triage outcome: 19 ACCEPT, 8 DISMISS (4 already-addressed-in-iter-1, 4 strategic risks with reasoning). Most consequential change: F-FRESH-1 / CR-2 — implement Phase 4b runs codex via Bash script, bypassing the codex-review skill markdown. Resolution per CA: Option B (Phase 4b duplicates counter logic with cross-reference) + canonical contract lives in TN-10. New Story E-233-04 added for the implement-skill mirror. Other notable changes: TN-3 namespaces all finding_ids as `R{round}-{codex_id_or_ordinal}` to prevent collisions; TN-4 documents resume scenario and prompt-gen behavior; TN-5 adds stop-word/min-length token filter and PRIOR DISMISSAL informational-only semantics; TN-6 adds verbatim-paste rule for spawn prompt fields; TN-9 redefines "validation pass" concretely (round 1 produces valid disposition log entries) and drops the unfalsifiable round-3-cap-fires success criterion; new TN-10 (round counter canonical contract) and TN-11 (diff-context resolution algorithm). Story 01: auto-memory directory referenced conceptually (CR-5). Story 02: AC-9 diagram update removed (consolidated to story 03 AC-14 per CR-4); AC-7 verbatim TN-2 sentence; AC-8 bounded-list framing; new ACs for prompt-gen counter, TN-10 conformance, resume scenario. Story 03: AC-2 stop-word filter; AC-4 PRIOR DISMISSAL informational only; AC-8 placeholders intact; new ACs for verbatim spawn paste and TN-11 invocation. Story 04 (new): implement Phase 4b counter mirror per TN-10.
- 2026-04-30: Iteration 3 — canonical-contract location migration. Per team-lead's authorization message ("canonical contract lives in a rule"), the round-counter + disposition-log contract was extracted from epic TN-10 into a new file `.claude/rules/codex-review-breaker.md`. Stories 02 and 04 updated to reference the rule file directly. (Subsequently superseded by iteration 3b — see next entry.)
- 2026-04-30: Status set to READY. Quality checklist passed (every story delivers a vertical slice; ACs are testable; file dependencies listed; epic Background explains WHY; non-goals listed; stories sized for single agent sessions; numbering correct; all template sections filled; Technical Approach sections name absolute paths to research artifacts; no implementation code prescribed; consistency sweep clean post-iteration-3b). Awaiting user dispatch authorization. **One blocker for the user**: `/workspaces/baseball-crawl/.claude/rules/codex-review-breaker.md` exists on disk from PM's iteration-3 implementation overreach; user must `rm` it before dispatch (Story 02 AC-0 will recreate it cleanly during dispatch).
- 2026-04-30: Iteration 3 closed all Codex Phase 4 findings; canonical contract draft + Story 02 AC-0 formalization pattern established; advanced to READY. Team-lead verified iteration 3 clean: 3 Codex P1/P2 findings properly applied (path-stripping in AC-4, AC-3 split into AC-3a/AC-3b, Phase 4b Step 5 layout consistent across AC-3a + Files-to-Modify + Handoff Context); planning-boundary fix complete with team-lead deletion of `.claude/rules/codex-review-breaker.md` (draft remains at `epics/E-233-codex-loop-prevention/codex-review-breaker.md.draft` as the canonical source until Story 02 dispatch); spec internally consistent.
- 2026-04-30: Iteration 3c — added AC-0b to Story 02 deleting planning draft after runtime rule file is created (single-source-of-truth post-dispatch; per user direction option B). TN-1 lifecycle clause added documenting the dispatch-time draft deletion. Story 02 Files-to-Modify lists the draft as a delete target. AC count: Story 02 16 → 17 (AC-0b added). Total: 50 ACs. Status remains READY (small AC addition, not structural).
- 2026-04-30: Iteration 3b — Codex Phase 4 findings + planning-boundary fix. Boundary: PM's iteration 3 created `.claude/rules/codex-review-breaker.md` directly, which is implementation work (PM owns spec files, not rule files). Per team-lead's auto-mode decision: rule-file content moved to `epics/E-233-codex-loop-prevention/codex-review-breaker.md.draft` (planning artifact, no frontmatter, NOT loaded into runtime); the runtime rule file at `.claude/rules/codex-review-breaker.md` is to be deleted before commit and recreated by Story E-233-02 implementer (claude-architect) with proper `paths:` frontmatter prepended. TN-1 restructured into Runtime files vs Planning artifact sections; TN-10 reframed as "canonical contract is implemented at `.claude/rules/codex-review-breaker.md` per Story 02; draft is the source of truth during planning, rule file is the source of truth post-implementation." Stories 02 and 04 ACs updated to make implementer responsibility explicit (Story 02 AC formalizes the rule file from the draft; Story 04 ACs reference `.claude/rules/codex-review-breaker.md` parallel to Story 02, eliminating the half-migration). Codex P1 #1 (`files` line-suffix stripping) folded into TN-3 + draft "Disposition Log Writes" section + Story 02 AC-4. Codex P1 #2 (Phase 4b prompt-gen-fallback path coverage) folded into TN-10 + draft + Story 04 AC-3 (split into AC-3a / AC-3b for the two paths). Codex P2 #1 (half-applied migration) resolved by parallel Story 02 / Story 04 rule-file references. Codex P2 #2 (Phase 4b step numbers) resolved by pinning the new step number(s) explicitly: Phase 4b gains a new disposition-log writer step inserted after the existing Step 4 (referred to in ACs as "the new disposition-log writer step Phase 4b adds in this story"). Story 04 Files-to-Modify pinned accordingly. AC counts unchanged (5 + 15 + 16 + 11 = 47). Consistency sweep clean.
