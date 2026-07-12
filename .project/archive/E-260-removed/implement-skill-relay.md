# Removed text snapshot — .claude/skills/implement/SKILL.md

- **Source:** `.claude/skills/implement/SKILL.md`
- **Story:** E-260-01 (Remove the verbatim-relay mandate apparatus)
- **Date:** 2026-07-11
- **Original line ranges (pre-edit):** 237, 243, 292, 303, 364, 569, 687

This file preserves verbatim the text removed or modified by E-260-01, per the epic Operating Rule ("snapshot before deleting unreviewed material").

---

## :237 — Context block requirements (token removed: `(never summarize)`)

Original line:
> **Context block requirements**: Include the full story file text and full Technical Notes verbatim (never summarize). Include Handoff Context from completed upstream dependencies.

Removed token only: ` (never summarize)`. The full-story-file / Technical-Notes-verbatim mandate is retained.

---

## :243 — "Relay integrity" blockquote (deleted, orphaned by the dispatch-pattern deletion)

> **Relay integrity:** when relaying review findings (CR or Codex) between the reviewer and implementer, relay only findings you have read from the persisted source to completion -- never content composed from empty/truncated/garbled output (no-relay-of-unread-content rule, `.claude/rules/dispatch-pattern.md`).

---

## :292 — Round-2 assignment list (phrase removed: `the round 1 findings verbatim, `)

The phrase `the round 1 findings verbatim, ` was struck from the Round-2 assignment sentence. Surrounding sentence retained; it now begins "...adding: updated Files Changed and Test Results...".

---

## :303 — Gate Interaction (sentence removed)

Removed sentence:
> PM AC rejection does NOT have its own circuit breaker -- the code-reviewer's 2-round circuit breaker governs the overall loop.

Surrounding paragraph retained and left coherent.

---

## :364 — second "Relay integrity" blockquote (deleted, same orphaned-citation class as :243; removed to satisfy AC-5)

> **Relay integrity:** before presenting or relaying these findings, you MUST have read the persisted codex output to completion -- never relay content composed from empty/truncated/garbled output (no-relay-of-unread-content rule, `.claude/rules/dispatch-pattern.md`).

---

## :569 — Phase 5 Step 8 sub-step 3 (MODIFIED, not removed — AC-6 merge-base correction)

Original line:
> 3. **Stage and diff the epic worktree:** `cd <epic-worktree-path> && git add -A` (stage all accumulated changes), then `git diff --binary --cached main > /tmp/E-NNN-epic.patch`.

Changed the diff base from `main` to `$(git merge-base epic/E-NNN main)`. Defect: a diff-against-`main` closure of a parked epic would revert work landed on `main` after the epic branched (the live E-256/E-260 case).

---

## :687 — Anti-Pattern #2 (deleted; following anti-patterns renumbered contiguously)

> 2. **Do not summarize context blocks.** Always send the full story file text and full Technical Notes verbatim.
