# IDEA-199: The append-only migration rule is invisible to every agent except data-engineer

## Status
`CANDIDATE`

## Summary
Nothing in `.claude/rules/migrations.md` — the path-scoped rule that loads for anyone touching `migrations/**` — says migrations are append-only. The prohibition exists only in `.claude/agents/data-engineer.md`, so it binds DE and is invisible to a software-engineer, docs-writer, or claude-architect editing a migration file.

## Why It Matters
The rule is real and load-bearing: editing an applied migration makes the file disagree with the schema the database already ran. But the agent most likely to encounter it accidentally is the one who cannot see it. `.claude/rules/migrations.md` loads on `migrations/**` and covers numbering, naming, idempotency, seed data, the `datetime('now')` format, `executescript()`/PRAGMAs, and application — a thorough file whose thoroughness makes the omission read as deliberate.

The gap is invisible in the ordinary case because editing an applied migration usually does not fail. `apply_migrations.py` tracks by filename with no checksum, so an edited migration is simply never re-applied: no error, no mismatch, nothing to notice. The damage shows up later, when the file and the live schema disagree and someone trusts the file.

**This is a gap that always existed, not a regression — and the opposite belief is recorded in the archive, so state it plainly here or the next reader will inherit it.** `.project/archive/E-100-team-model-overhaul/epic.md` says its fresh-start authorization overrode "the append-only migration rule in `/.claude/rules/migrations.md`" and that E-100-06 would update that file afterwards. That sentence is false about where the rule lived. Data-engineer scanned all 10 revisions of `.claude/rules/migrations.md` with a positive control — "Idempotency" fires on all 10, a bare case-insensitive "append" fires on none — and the E-100-06 commit's diff to that file touches only the numbering lines and an ALTER TABLE precedent sentence. No revision ever contained append-only or never-edit language.

**Framing consequence for whoever promotes this:** the ask is "codify a rule that has only ever lived in one agent's definition," NOT "restore deleted text." Phrased as a restoration, it sends someone hunting git history for text that does not exist.

## Rough Timing
Promote when a context-layer epic is already touching `.claude/rules/`, since the fix is a few sentences and does not earn a dispatch of its own. No urgency: the rule has not been violated, and E-277 complied with it after discovering the gap.

## Dependencies & Blockers
- [ ] None.

## Open Questions
- Does the rule as restored need a scope qualifier? Its stated rationale is entirely about DDL divergence, and that rationale does not reach a comment — a comment-only edit is mechanically inert, since the runner tracks by filename and `conftest.load_real_schema` merely concatenates. E-277 chose to leave an applied migration's stale comment alone anyway, but for a different reason: an applied migration is a record of what was applied at the time, and correcting it in place quietly rewrites that record. Whether the written rule should say "never edit" or "never edit the DDL, and leave comments as history" is a real decision, not a wording preference.
- Should the rule live in `.claude/rules/migrations.md` alone, or also stay in the DE agent definition? Duplication risks the two drifting, but the DE definition is where a data-engineer will actually look.

## Notes
Surfaced during E-277 discovery (2026-07-26). Data-engineer initially stated the append-only bar as a project rule, then checked and corrected it to an agent-definition convention applied conservatively — the correction is what exposed the gap. PM verified independently: CLAUDE.md and `docs/` state no such rule.

**Provenance of the false "it used to be there" claim, recorded because it survived four months in an archived authority document.** It entered at E-100's Codex spec-review triage on 2026-03-14 as finding F2 ("rule override Technical Note for append-only migration rule"), was written into E-100's epic as a Rule-override note asserting the rule lived in `.claude/rules/migrations.md`, and was never checked against that file. PM read it on 2026-07-26 and compounded it into "the canonical file silently lost the rule" — adding a removal event that never happened. Data-engineer contested it and settled it from git history. The chain is the repo's own documented shape: a relayed claim becomes the relayer's the moment it is restated, and a spec that passed review is borrowed authority, not verification.

Owner when promoted: `claude-architect` (`.claude/rules/**` routes there per `.claude/rules/agent-routing.md` Routing Precedence).

---
Created: 2026-07-26
Last reviewed: 2026-07-26
Review by: 2026-10-24
