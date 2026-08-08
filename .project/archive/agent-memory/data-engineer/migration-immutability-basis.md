---
name: migration-immutability-basis
description: What the "never edit an applied migration" rule actually rests on -- DE agent definition only, absent from .claude/rules/migrations.md in every revision, and mechanically unenforced (filename tracking, no checksum)
metadata:
  type: project
---

The append-only migration rule binds **only the data-engineer agent**. Established
by execution during E-277 planning (2026-07-26), after I asserted it to PM as a
hard project constraint and PM correctly pressed for the authority.

**Where it lives:** `.claude/agents/data-engineer.md`, stated twice (the Migration
Management section and Anti-Pattern 2). Nowhere else.

**Where it does NOT live:** `.claude/rules/migrations.md` -- the path-scoped
canonical rule for `migrations/**`, and therefore the ONLY migration guidance a
non-DE agent (an SE on a migration story) ever loads. It covers numbering,
naming, idempotency, seed data, `datetime('now')`, `executescript()`/PRAGMAs, and
application. **No revision of that file has EVER contained append-only or
never-edit language** -- verified by scanning all 10 revisions with a positive
control ("Idempotency" fires on all 10; a bare case-insensitive "append" fires on
none). Not in CLAUDE.md or `docs/` either.

**It is also mechanically unenforced.** `apply_migrations.py` tracks applied
migrations by FILENAME in `_migrations` (`get_applied_migrations` returns a set of
filename strings; `pending` filters on `f.name not in applied`). No checksum, no
content hash -- its own E-220 guard docstring says "the migration runner tracks by
filename, not by content." So editing an applied migration is never detected,
never re-applied, and raises nothing. `conftest.load_real_schema` concatenates and
re-executes the files, so a comment edit is inert to schema reconstruction too.

**The trap this creates:** the rule's rationale is entirely schema-focused ("to
change a schema, write a new migration"), so a COMMENT-only edit satisfies the
purpose while violating the letter, and nothing mechanical distinguishes them.

**My standing ruling (E-277): keep the strict reading, but argue it from the
right premise.** Not "it is written down" (weak -- it is written in one agent's
definition, which does not reach the implementer). The durable reason: **there is
no mechanical boundary between an inert comment and a comment that documents DDL
semantics** (a CHECK vocabulary, a DEFAULT, an FK's ON DELETE choice). Once
"comments may be edited when judged inert" is precedent, the judgment call moves
to whoever is editing, and the convention is the only thing holding the line.
Correct stale prose where readers actually look (`.claude/rules/data-model.md`),
and let the applied migration stand as a record of what was applied.

**Corollary -- an epic can mis-cite a rule's LOCATION, and the mis-citation
outlives it.** `.project/archive/E-100-team-model-overhaul/epic.md` overrides "the
append-only migration rule in `/.claude/rules/migrations.md`" -- a rule that was
not there then and never has been. E-100-06 duly "updated" the file and removed
nothing (its diff touches only numbering and an ALTER TABLE precedent line). Same
defect class as migration 005 citing `generator.py::_delete_team_scoped_data` for
a symbol that lives in `lifecycle.py`: a citation naming a file that does not hold
the thing. Resolve a cited LOCATION, not just the cited claim.

Related: [[etl-patterns]], [[schema_drop_test_blast_radius]].
