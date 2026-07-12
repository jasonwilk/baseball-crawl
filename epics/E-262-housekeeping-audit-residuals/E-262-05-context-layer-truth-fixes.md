# E-262-05: Context-Layer Truth & Staleness Corrections

## Epic
[E-262: Post-Program Housekeeping](epic.md)

## Status
`TODO`

## Description
After this story is complete, five defect-cited context-layer falsehoods and stale figures are corrected: two false/stale CLAUDE.md claims, an over-broad skill instruction, stale ambient skill figures, and two rule-table corrections — all mechanical prose fixes, no new machinery.

## Context
Five context-layer corrections, each defect-cited to satisfy the E-260 meta-layer freeze (freeze allows defect-cited changes; this story adds NO new rules/skills/gates — corrections only). Line refs below are from source ideas + reviewer verification — re-verify against current file state before editing:
- **Audit #9 (CLAUDE.md raw-archive claim — FALSE):** `CLAUDE.md:115` Architecture says "Store raw API responses before transforming (raw -> processed pipeline)." This is false for the in-memory crawl-to-load pipeline (`CLAUDE.md:137`), which stores no raw payloads. (The forward "make it true, write-only" direction is captured as IDEA-129 — not built here; this only corrects the false claim.)
- **IDEA-114 (CLAUDE.md morning-run `--dry-run` prose — MISLEADING):** `CLAUDE.md:85` prose reads as if `--dry-run` sends the always-sent summary email, but the code exempts dry-run — `src/cli/report.py:530` (`_emit_summary_if_needed` early-returns on `dry_run`; the other `if not dry_run:` gates are `:616`/`:688`/`:736`). This ambiguity misled a CR spec-audit (finding 6, refuted by code) during E-256/E-259 planning. One-line clarification. (Note: the earlier `:581`/`:666` refs cited in IDEA-114 have drifted — CA verified the current lines above.)
- **IDEA-117 (multi-agent-patterns:24 over-broad — AMBIGUOUS):** `.claude/skills/multi-agent-patterns/SKILL.md:24` "Never summarize" reads as a blanket verbatim-relay mandate; its `:26` already scopes it to the dispatch context block. Scope `:24` in place (mirroring E-260-04's `:203` treatment) so it can't be re-cited as license for the expensive live-agent relay E-260 removed.
- **IDEA-118 (context-fundamentals ambient figures — STALE):** the genuinely-stale ambient figures are `.claude/skills/context-fundamentals/SKILL.md:28` ("~614-886 lines") and `:193` ("~750 lines") — non-contradicting (ambient subset, not the whole-layer total) but stale. Refresh to current ambient figures. **Do NOT** re-do the post-E-213 provenance removal or the whole-layer budget section (`:70-90`): E-260-04 already re-derived those (now "~12,000 lines / 2026-07-11" with a regenerating command, provenance already dropped). This corrects ONLY the two leftover ambient figures.
- **IDEA-128 (perspective-provenance.md field-table caveats — INCOMPLETE/OUTDATED):** `.claude/rules/perspective-provenance.md`'s field table needs two api-scout-flagged corrections (surfaced in E-261 Codex review): add a public-scorebook caveat to the "scores stable across perspectives" row (`:43`) (two independent public scorebooks CAN disagree by a run — E-261's 12-4 vs 12-5), and promote the "Uncertain: public games `id`" row (`:45`) to definitively perspective-specific (post-E-239 the public path is sole populator; `event_id` per-perspective = `game_stream_id`).

**Removed from this story (CA review, F1):** IDEA-092 (data-engineer.md Core Entities table) was dropped. CA verified `.claude/agents/data-engineer.md:105-118` already names ONLY real tables (no `PlayerTeamSeason`; the hallucination cells were stripped by E-250-04) and carries a self-aware note at `:118`. The cited falsehood is already fixed; the residual "fuller schema-aligned entity refresh" is an ENHANCEMENT barred by the E-260 freeze. IDEA-092 flipped to DISCARDED.

## Acceptance Criteria
- [ ] **AC-1**: Given CLAUDE.md's Architecture section, when it is read, then the false "Store raw API responses before transforming" claim is corrected to reflect the in-memory pipeline reality (no stored raw payloads), and the morning-run `--dry-run` prose no longer implies dry-run sends the summary email.
- [ ] **AC-2**: Given `.claude/skills/multi-agent-patterns/SKILL.md:24`, when read alone, then it is scoped to the dispatch context block and cannot be read as a blanket verbatim-relay mandate.
- [ ] **AC-3**: Given `.claude/skills/context-fundamentals/SKILL.md`, when its two stale ambient figures (`:28`, `:193`) are read, then they reflect current ambient numbers and remain consistent (non-contradicting) with the already-re-derived `:70-90` whole-layer budget section (which is NOT re-edited by this story).
- [ ] **AC-4**: Given `.claude/rules/perspective-provenance.md`'s field table, when the two flagged rows are read, then the "scores stable" row carries the public-scorebook disagreement caveat and the public games `id` row is stated as definitively perspective-specific.
- [ ] **AC-5**: Each correction's defect citation (from this story's Context) is preserved in the epic/story record so the freeze-compliance rationale is visible.

## Technical Approach
Mechanical prose corrections across CLAUDE.md, `.claude/skills/multi-agent-patterns/SKILL.md`, `.claude/skills/context-fundamentals/SKILL.md`, and `.claude/rules/perspective-provenance.md`. Each item has a named anchor (line refs in Context are reviewer-verified but re-check current file state before editing). Apply the doc-sweep discipline (`.claude/rules/doc-sweep.md`): grep + synonym expansion + semantic read for each corrected concept. Keep edits reword-in-place / additive-caveat only — no new rules, skills, or gates.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `CLAUDE.md`
- `.claude/skills/multi-agent-patterns/SKILL.md`
- `.claude/skills/context-fundamentals/SKILL.md`
- `.claude/rules/perspective-provenance.md`

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
- [ ] Context-ratchet holds (or any net growth is operator-signed at closure)

## Notes
Sources: audit residual #9; IDEA-114, 117, 118, 128. All defect-cited (concrete falsehood / staleness) → permitted under the E-260 freeze. No new context-layer machinery is added. IDEA-092 was DROPPED after CA review (F1) — its cited falsehood was already fixed by E-250-04; residual is freeze-barred enrichment (IDEA-092 → DISCARDED). E-261 (READY, parked) does NOT edit perspective-provenance.md, so AC-4 has no expected overlap with it (confirm E-261's file list at dispatch per CA coordination flag).

**CA holistic review (2026-07-12, iter 1/3) incorporated:** F1 (drop IDEA-092 — already-fixed, freeze-barred); F4 (narrow IDEA-118 to `:28`/`:193`; the provenance/budget-section work is already done by E-260-04); F5 (correct IDEA-114 line refs to `report.py:530`). Verified-good by CA: audit #9, IDEA-117, IDEA-128, and the AC framing.
