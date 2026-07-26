# P4 — Consolidate and prune agent memories (CA-led, operator-approved deletions)

Invoke claude-architect for a memory-hygiene pass across ALL agent memory
(`.claude/agent-memory/*/`) and the main session's auto-memory
(`/home/vscode/.claude/projects/-workspaces-baseball-crawl/memory/`). Goal: remove or
merge entries that are stale, superseded, or duplicated — the operator's words:
"distracting from smooth operations." This is a PRUNING pass; add nothing new except
merge targets.

## Method (bias to delete, but two-step)

1. Inventory every MEMORY.md line and topic file; classify each: CURRENT / STALE
   (facts overtaken) / SUPERSEDED (a newer entry or rule covers it) / DUPLICATE
   (same lesson recorded in 2+ places) / WRONG (contradicted by verified evidence).
2. Present the full deletion/merge list to the operator for approval BEFORE editing.
3. Execute; keep MEMORY.md indexes in sync; delete orphaned topic files.

## Known-stale seeds (verified 2026-07-25; start here, don't stop here)

Main-session auto-memory (`memory/MEMORY.md` + files):
- "E-267 LANDED — operator does not trust it / expect findings" and the E-267 audit
  verdict entries: OVERTAKEN — the Fable audit ran (2026-07-25), found the health gate
  CRITICAL (fix in flight via P1) and otherwise verified the envelope. Collapse the
  E-267/E-270/E-273 pending-work entries into one short "post-audit fix queue" note.
- "2026-07 PLATFORM PROGRAM — CLOSED" block: compress to two lines + archive pointer;
  its falsifier-watch and follow-up details are dead weight now.
- "Review methodology retro epic — OVERTAKEN" and "Duplicate opponent teams — MOOT":
  delete (both self-declare dead).
- Ratchet follow-ups inside project_e270/e273 files ("3rd ratchet deferral",
  "T7 context-ratchet re-snapshot"): rewrite per the P5 ratchet decision.
- feedback_main_session_no_verify: KEEP but extend one sentence — the 07-25 session
  showed it must bind in ALL modes (open-mandate sessions, not just dispatch); hub
  asserts nothing about file contents it hasn't Read in full.
- feedback_test_mundane_hypothesis_before_garble: KEEP (verified accurate by the
  audit); it now duplicates tool-output-integrity.md's differential — shrink to a
  pointer.

Agent memories:
- product-manager: `operator-followups.md` ratchet items — rewrite per P5;
  MEMORY.md epic-numbering "next number" fields — verify by glob or delete the field
  (twice-burned pattern).
- baseball-coach / api-scout / ux-designer 2026-07-25 files: KEEP (audit-verified);
  check MEMORY.md index lines match the files that exist.
- All agents: any entry restating the OLD garble reading of the E-267 story-03
  incident (pre-caeb9a3) — the re-adjudication is canonical; sweep per
  `.claude/rules/doc-sweep.md` "Retired Claims Survive in Forms Carrying None of
  Their Tokens".
- claude-architect `epic-codifications.md` E-267 T3 entry: verify it matches the
  corrected retelling (it should — it was the source); dedupe against
  tool-output-integrity.md rather than keeping two full narratives.

## Constraints

- Deletion list needs operator approval before execution (step 2 is mandatory).
- Don't touch `.claude/rules/` in this pass except where a memory merges INTO an
  existing rule pointer — rules changes stay defect-cited and separate.
- Commit as a single `docs(memory): prune stale/superseded agent memories` commit;
  expect net-negative lines.
