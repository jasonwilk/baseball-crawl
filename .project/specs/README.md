# Line of march

The standing answer to "what should we do next?" Read this before proposing scope. Lifecycle
step 9 (HANDOFF) updates it: move what landed out of NOW, promote from NEXT, and add anything the
chunk discovered as a stub or a residual.

Individual chunk specs live beside this file as `<date>-<slug>.md`. Every one of them must read
`COMPLETE`, `PARKED`, `STUB`, or `OPEN`, or belong to a chunk in flight.

## NOW

- **Migration Step 2 — retire the choreography.** Single-source `codex-review` (copy the bug-pattern
  and security checklists it reads out of `code-reviewer.md` into the skill's own directory) and
  rewrite `ingest-endpoint` phase 2 so findings go to the session, THEN delete the 7 agent
  definitions and the `agent-standards` / `context-fundamentals` / `filesystem-context` /
  `multi-agent-patterns` skills, archive their agent-memory, drop `epic-archive-check.sh` and its
  `settings.json` wiring, and trim `api-scout` / `baseball-coach`. Every accepted residual below
  expires here. Order matters: single-source BEFORE deleting, or `codex-review` fails closed.
- **The three operator decisions below** — queued for one sitting, now unblocked by Step 1.

## NEXT

- **Migration Step 3 — specs live.** A ≤30-line spec template (first line: no real names, use the
  `api-docs.md` placeholder taxonomy), `codex-spec-review` rewritten to take a spec file path
  instead of resolving an epic dir, a `specs/done/` convention, and trims to `documentation.md` and
  `ideas-workflow.md`. `epics/` freezes; new work enters as specs.
- **Migration Step 4 — second-pass rule trim.** After ~3 more real chunks, take the ~23 surviving
  path-scoped rules through "would removing this line cause a mistake?", run `/doctor`, and
  regenerate the cheat sheet from what actually got used.
- **Sweep `docs/` for the retired workflow.** Found by the Step 1 codex review, out of that
  chunk's declared sweep scope (which covered `CLAUDE.md`, `.claude/`, and settings only).
  Operator-facing docs still teach the PM/epic/dispatch flow: ~110 references across 18 files,
  and `docs/admin/agent-guide.md` (124 lines) is about nothing else. Two references are broken by
  the Step 1 commit specifically — `docs/admin/production-deployment.md:507` points at the
  deleted `.claude/skills/implement/SKILL.md`, and `docs/admin/agent-guide.md:102` says
  `context-ratchet.sh` "survives," which this commit made false. Best sequenced after Step 2,
  when the agents this documentation describes are actually gone.
- **Morning-of-game scheduled reports** — the forward product feature (`docs/ROADMAP.md`).

## PARKED DECISIONS

Each needs the operator, not more analysis. Evidence is in the named spec.

1. **Bulk team discovery via organizations** — does the product want it?
   (`2026-08-04-org-team-discovery-and-roster-ingest.md`; vision-adjacent, consider alongside
   "curate the vision".)
2. **Rung-c season-year filter** — a cost/semantics call.
   (`2026-08-05-rung-c-season-year-filter.md`, status OPEN.)
3. **`docs/api` redacted-prefix corpus** — relax the `api-docs.md` rule, or scrub ~140 sites?
   (`2026-08-04-docs-api-redacted-prefix-corpus.md`; recommendation on file: relax, the prefixes
   are team-scoped IDs.)

## STANDING RESIDUALS

Carried deliberately. Not prose, not tickets — things that will bite if forgotten.

- Devcontainer pip will break the way CI did when its image floats to pip 26.2.
- `worktree-guard.sh`: the `CLAUDE_HOME` case arm is not slash-normalized the way `REPO` is. A
  2-line fix; fold it into the next `src/`-touching chunk.
- `codex-review` skill vs. first-party `codex review` — comparison owed at Step 2.
- Residual one-sided game (both identifiers on the empty side) — needs a live probe.
- **CLAUDE.md is at 10,585 bytes against an 11KB (11,264-byte) cap** — ~680 bytes of headroom.
  The original 8KB cap was raised by operator decision during the Step 1 review, after it proved
  to be trading against the file's own acceptance criterion: meeting 8192 had squeezed out the
  per-rule pointer enumeration, the `bb` command groups, the session-token sensitivity rule and
  more, and the compression itself introduced prose defects. Keep measuring it — the point of the
  cap was to stop the drift back toward a 20KB always-on file, and that point still stands.
- **`.claude/` is ungated for PII by BOTH instruments.** `SKIP_PATHS` blinds the pattern scanner
  to it even when files are passed as explicit arguments — verified 2026-08-06 by copying a
  known-bad file under `.claude/`, where it returned RC=0 and printed nothing, versus RC=1
  outside. And `scripts/check_doc_pii.sh .claude` exits 1 today on pre-existing content in
  `agent-memory/`, four agent definitions, and `data-model` / `gc-uuid-bridge` / `pitch-rules`.
  That state predates this chunk and is consistent with the "identifiers are fine where they
  anchor evidence" scoping, but it means a `.claude/` write gets no automatic PII coverage: scan
  it by hand, and note that a silent RC=0 there is vacuous, not clean.

### Accepted residuals from Step 1 — all expire at Step 2

Step 1 deleted 10 always-on rules and the `implement` / `plan` skills. These references to them
were left standing on purpose, because the files carrying them die at Step 2 and fixing them now
would blow the chunk boundary:

- Five agent definitions keep dangling references: `claude-architect` (6), `code-reviewer` (6),
  `product-manager` (7), `data-engineer` (2), `software-engineer` (2). Measured by the Step 1
  sweep, 2026-08-06. The spec predicted seven; `docs-writer` and `ux-designer` have none, and
  `api-scout`'s single reference was repointed in Step 1.
- `.claude/skills/agent-standards/SKILL.md:121` cites the "CLAUDE.md Agent Ecosystem table",
  which Step 1 deleted. Its two siblings in `codex-review` and `codex-spec-review` were repointed
  because those skills survive; this one dies at Step 2, so it was left.
- Three skills keep dangling references: `agent-standards` (1), `context-fundamentals` (2), and
  `multi-agent-patterns` (1, at `SKILL.md:50` — "the implement skill (Phase 3) is authoritative").
  The spec's residual list named only the first two; `multi-agent-patterns` is the same class and
  dies at the same step.
- `epic-archive-check.sh` stays wired in `settings.json`. It does not fire, but the spec's reason
  was wrong and is corrected here: `epics/` holds **five** directories, not three — E-174
  (DRAFT), **E-263 Deep Scout (READY)**, E-271 (DRAFT), E-274 (DRAFT), E-275 (DRAFT). The hook
  denies only on a status line of exactly `COMPLETED` or `ABANDONED`, so none of the five trips
  it. **E-263 is the live one to decide about**: it is the only READY epic carrying real product
  work, and Step 3 freezes `epics/`. Do not let that freeze happen without ruling on it.
- `codex-review` lacks `disable-model-invocation: true`.
- The "curate the vision" workflow no longer names an owning agent. The trigger phrase and the
  do-not-edit-`VISION.md`-directly rule survive in `.claude/rules/vision-signals.md`; the session
  runs the curation itself.
