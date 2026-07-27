---
name: e277-planning-state
description: E-277 reclamation-follow-ups planning state at the 2026-07-27 PM drain — triage record, both resolved decisions, and the facts a successor cannot derive from the files
metadata:
  type: project
---

# E-277 — planning state at PM drain (2026-07-27)

**Status on disk: DRAFT, five stories all TODO.** READY is the team lead's to set and was never authorized to PM. A Codex spec review was running at drain time; its findings had NOT reached PM.

**Why:** PM drained deliberately at tight context before a substantial batch landed, on operator directive — insurance over the negotiation round. Same pattern that worked in E-276.
**How to apply:** seed a successor from the worktree artifacts, not from any summary. The epic's 13 Technical Notes and the five story files carry every disposition; nothing material lived only in PM's context at drain.

## Triage record (round of 2026-07-27)

24 findings: `cr` 18 (8 MUST FIX / 10 SHOULD FIX), `se` 6, `de` 7 (applied in the prior round). **23 ACCEPTED, 1 withdrawn.** Both open decisions the predecessor left were resolved, not inherited.

- **Decision 1 (story 02 / epic Goal 3) → COVER.** A guard at `cleanup_expired_reports`' own entry, outside the `try` that swallows reaper failures (AC-2.1). Not the binary "working cover vs honest decline" it was framed as — the entry guard cost one precondition check in the same file. Gated on `se` instrumenting cleanup's own entry: all live shapes clean, so the cover is safe and Goal 3 was NOT narrowed.
- **Decision 2 (story 01 AC-6) → re-authored, split by verdict class.** Execution for the live roots (with production-path fixtures), writer/reader audit for the dead ones, and a binding clause barring a seeded synthetic run from being recorded as no-op evidence.

## Facts a successor CANNOT derive from the files

1. **`/tmp/e277-cr-audit.md` reflects the 23:3x file state plus its own re-verification block.** It is not a live view. Treat every quotation in it as evidence of what was audited, not of what the file now says.
2. **`cr`'s "M4, M5, S9 STAND" verdicts predate the incorporation and are already closed.** A reader comparing that audit against the current epic would otherwise conclude three MUST FIXes were left open.
3. **S7 is WITHDRAWN-AS-STALE, not dismissed-as-wrong.** `cr` held the 23:33 state where story 03 AC-2 genuinely carried a literal `999`; its quote was accurate for the file it read. "The finding was real and has since been fixed" and "the finding was mistaken" are different facts about a reviewer's reliability, and only the first is true. The differential that established this was mtime-based — the moved-file cause, not the garbled-read cause.
4. **TN-9 carries a two-sided statement that must not be re-merged.** `cr`'s caller enumeration covers `reclaim_orphan_reference_data` and `reap_stale_generating_reports`; `se`'s measurement covers `cleanup_expired_reports`, a different and much smaller call graph (exactly two live call sites; there is NO app-lifespan path into cleanup). Both are accurate. Setting them side by side as mutual corroboration overstates what either checked — PM did exactly that while fixing TN-9's original one-sidedness, and `se` caught it. Only the cleanup-specific measurement bears on AC-2.1.
5. **AC numbering is deliberately non-contiguous.** Story 01 runs AC-1..AC-10 with AC-6a/6b/6c and AC-9a; story 02 carries AC-2.1 and AC-5a. Do not renumber to tidy — the story text cross-references these labels.
6. **IDEA-198, 199 and 200 are E-277's and exist on disk with README rows.** A sibling thread holds 201+. Expect an additive `.project/ideas/README.md` conflict at closure; do not renumber.

## Durable lessons (these outlive the epic)

**A defect introduced at the moment of highest confidence.** PM correctly diagnosed TN-9's one-sided "SOLE trigger" claim, and then, while incorporating that fix, authored a fresh instance of the same class — merging two true statements about different functions into a broader claim neither supports. It did not slip past a tired reading; **it was authored by the same reasoning that had just succeeded.** Caught by a non-author reading the artifact for an unrelated reason. This is the strongest evidence this epic produced that awareness of a defect class confers no immunity to it. See [[feedback_structure_catches_what_reviewers_wont]].

**Distinguish the blast radius of what you are FIXING from what you are ADDING.** Story 01's draft said the blast radius "is exactly one live site" — true of the false comment, false of adding a fourth root. Any site enumerating or counting the roots goes stale from the addition alone. An AC written from the conflated premise always under-scopes, and this one did.

**An enumeration AC must regenerate its list BY SEARCH.** If it names the sites a reviewer found, it inherits that reviewer's fallibility and stops being a sweep. `cr` and PM reached this remedy independently. Applied to story 01 AC-9, story 03 AC-7a, story 04 AC-6a — and PM applied it against its own findings too.

**Wrong premise is not the same as wrong decision.** The lead chased `se` for a measurement on PM's report it had not arrived; all three copies had in fact arrived. The chase was still correct on the evidence available (absent gate + a documented four-send drop on that exact leg). A rule inferred from the outcome rather than the reasoning — "don't chase" — would make the team worse.

**The moved-file / garbled-read differential earns its keep.** Run it before naming either cause: the two demand opposite actions, and here it turned what looked like a reviewer misquote into "my read was real, and my OTHER findings on that file need re-checking" — which is what surfaced that story 01's AC-4 had changed underneath `cr`.
