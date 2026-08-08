# Line of march

The standing answer to "what should we do next?" Read this before proposing scope. Lifecycle
step 9 (HANDOFF) updates it: move what landed out of NOW, promote from NEXT, and add anything the
chunk discovered as a stub or a residual.

Individual chunk specs live beside this file as `<date>-<slug>.md`. Every one of them must read
`COMPLETE`, `PARKED`, `STUB`, or `OPEN`, or belong to a chunk in flight.

## NOW

- **Migration Step 3 — specs live.** A ≤30-line spec template (first line: no real names, use the
  `api-docs.md` placeholder taxonomy), `codex-spec-review` rewritten to take a spec file path
  instead of resolving an epic dir, a `specs/done/` convention, and trims to `documentation.md` and
  `ideas-workflow.md`. `epics/` freezes; new work enters as specs. **Rule on E-263 Deep Scout
  (READY) before the freeze** — it is the only epic dir carrying real product work.
- **The three operator decisions below** — still queued for one sitting.

## NEXT

- **Migration Step 4 — second-pass rule trim.** After ~3 more real chunks, take the ~23 surviving
  path-scoped rules through "would removing this line cause a mistake?", run `/doctor`, and
  regenerate the cheat sheet from what actually got used.
- **Sweep `docs/` for the retired workflow — now unblocked, the agents are gone.** Deliberately
  out of Step 2's scope. Operator-facing docs still teach the PM/epic/dispatch flow; the Step 2
  sweep measured **4 files** still naming a deleted agent (`docs/admin/agent-guide.md`, 124 lines
  and about nothing else; `docs/admin/production-deployment.md:564`; `docs/admin/operations.md:1048`;
  `docs/vision-signals.md:15`), on top of the ~110 references across 18 files the Step 1 review
  counted for the wider workflow prose. Also still open from Step 1:
  `docs/admin/production-deployment.md:507` points at the deleted `.claude/skills/implement/SKILL.md`
  and `docs/admin/agent-guide.md:102` says `context-ratchet.sh` "survives," which is false.
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

### Accepted residuals from Step 2

- **The PII pattern scanner is blind to EXTENSIONLESS files** — `is_scannable` gates on suffix,
  so a file with no `.` in its name is skipped as "non-scannable extension" regardless of
  `SKIP_PATHS`. Exactly two tracked files are affected today: `.githooks/pre-commit` (which is
  itself a PII gate) and `Dockerfile` (which the security checklist's 4h asks reviewers to check).
  Found at Step 2 because this chunk edits the hook; both were scanned BY HAND with a positive
  control and are clean. A one-line fix (treat a shebang or a known basename as scannable) —
  fold it into the next `src/`-touching chunk.
- **`.project/codex-spec-review.md` still resolves an epic dir and points at three rules Step 1
  deleted** (`workflow-discipline`, `agent-routing`, `dispatch-pattern`). Step 2 scrubbed its role
  names so this commit adds no NEW dangling pointer, but the structural rewrite is Step 3's.
- **`.project/templates/{epic,story}-template.md` still enumerate the deleted agent roster.** They
  are epic machinery and die with `epics/` at Step 3; left deliberately.
- **`epics/`, `.project/ideas`, `.project/research`, `.project/decisions`, `reviews/` keep role
  names.** Historical records, not pointers. `epics/` freezes at Step 3; the rest stay as written.
- **The `codex-review` skill vs. first-party `codex review` comparison was owed at Step 2 and was
  NOT done.** Carried forward rather than silently dropped.
