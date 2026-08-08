# Line of march

The standing answer to "what should we do next?" Read this before proposing scope. Lifecycle
step 9 (HANDOFF) updates it: move what landed out of NOW, promote from NEXT, and add anything the
chunk discovered as a stub or a residual.

Individual chunk specs live beside this file as `<date>-<slug>.md`. Every one of them must read
`COMPLETE`, `PARKED`, `STUB`, or `OPEN`, or belong to a chunk in flight. The vocabulary is exactly
those four — `RULED` was retired on 2026-08-08 and its three specs re-statused to `PARKED + why`.

**`specs/done/`.** At handoff, a spec whose Status you just flipped to `COMPLETE` moves to
`.project/specs/done/` in the SAME commit. Everything still open stays in the live directory —
that is exactly what principle F's audit has to see. Note the rename cost: plain `git log` on the
new path shows only the move commit, so **use `git log --follow -- <path>`** to get a moved spec's
real history. Someday-work does not live here at all; it is one line in `IDEAS.md`.

## NOW

Clear. Step 3 landed 2026-08-08; pick the next chunk from NEXT.

## NEXT

- **Migration Step 4 — second-pass rule trim.** After ~3 more real chunks, take the ~22 surviving
  path-scoped rules through "would removing this line cause a mistake?", run `/doctor`, and
  regenerate the cheat sheet from what actually got used. Also decide there whether `PARKED`
  needs splitting: it now carries two meanings — "set aside indefinitely" and "ruled and queued"
  — distinguished only by whether NEXT names the spec.
- **Rung-c season-year filter — RULED: BUILD** (operator, 2026-08-08). Semantics settled: a team
  from one YEAR must never auto-match a team from another year; cross-season within the same
  year (spring 2026 vs summer 2026) is legitimate; a hit with `season.year` absent REFUSES
  auto-accept (fail-closed). Compare against the member team's `teams.season_year`. Small chunk
  (`_resolve_via_search` signature + `morning_run` caller + tests); spec
  `2026-08-05-rung-c-season-year-filter.md`.
- **Opponent org-reachability measurement — RULED: measure only** (operator, 2026-08-08). Bulk
  org discovery is DECLINED (vision non-goal). The funded question: what fraction of our real
  unresolved opponents (no `progenitor_team_id`) are reachable via a discoverable organization's
  roster surface? Read-only, needs a team→org lookup answer first; design nothing unless the
  number is material. Spec `2026-08-04-org-team-discovery-and-roster-ingest.md`.
- **Sweep `docs/` for the retired workflow — now unblocked, the agents are gone.** Deliberately
  out of Step 2's and Step 3's scope. Operator-facing docs still teach the PM/epic/dispatch flow;
  the Step 2 sweep measured 4 files still naming a deleted agent, of which **3 remain**
  (`docs/admin/agent-guide.md`, 124 lines and about nothing else;
  `docs/admin/production-deployment.md:564`; `docs/vision-signals.md:15`) — Step 3 closed the
  fourth by deleting the `[archive-refs: BLOCKED]` section that carried `operations.md:1048`'s
  role-name routing list. On top of that, the ~110 references across 18 files the Step 1 review
  counted for the wider workflow prose. **This sweep owns the one seam Step 3 left open**:
  `docs/admin/agent-guide.md:66-68,106,108` still describes `epics/` and `.project/ideas/` as live
  surfaces, and both are frozen as of 2026-08-08. **Plus four DEAD `epics/` pointers on LIVE
  surfaces, found by Step 3's code review and predating it** — these are not covered by the
  historical-record exemption below, because they are live API reference and a live skill
  instruction, not records: `docs/api/auth.md:489` and `docs/api/endpoints/post-auth.md:322`
  (→ `epics/E-075-mobile-credential-capture/R-01-findings.md`),
  `.claude/skills/ingest-endpoint/SKILL.md:112` (→ `epics/E-002-data-ingestion/E-002-R-01.md`), and
  `.claude/agent-memory/api-scout/mobile-auth-notes.md:53` (→ E-075 again). Both trees have been at
  `.project/archive/` since well before Step 3; the retired archive-refs gate should have caught
  them and did not, which is its own evidence the gate was already inert. Also still open from
  Step 1:
  `docs/admin/production-deployment.md:507` points at the deleted `.claude/skills/implement/SKILL.md`
  and `docs/admin/agent-guide.md:102` says `context-ratchet.sh` "survives," which is false.
- **Morning-of-game scheduled reports** — the forward product feature (`docs/ROADMAP.md`).

## PARKED DECISIONS

None open. The sitting of 2026-08-08 ruled all three (details in the named specs):

1. **Bulk org discovery: DECLINED** — vision non-goal; the narrow roster-recovery measurement is
   funded instead (see NEXT).
2. **Season-year filter: BUILD**, semantics settled — never cross-YEAR, same-year cross-season
   fine, absent year refuses (see NEXT).
3. **Prefix corpus: rule RELAXED, scrub CANCELLED** — real team/org/game ID prefixes are
   acceptable in `-REDACTED` placeholders; PERSON-scoped identifiers (player/user ids) remain
   synthetic-only, verified whenever those docs are next touched. The `api-docs.md` rule edit
   rides the PII-docs chunk.

## STANDING RESIDUALS

Carried deliberately. Not prose, not tickets — things that will bite if forgotten.

- Devcontainer pip will break the way CI did when its image floats to pip 26.2.
- `worktree-guard.sh`: the `CLAUDE_HOME` case arm is not slash-normalized the way `REPO` is. A
  2-line fix; fold it into the next `src/`-touching chunk.
- `codex-review` skill vs. first-party `codex review` — comparison owed at Step 2.
- Residual one-sided game (both identifiers on the empty side) — needs a live probe.
- **CLAUDE.md is at 11,241 of the 11KB (11,264-byte) cap — 23 bytes of headroom** (measured
  2026-08-08, after Step 3). It hit the cap exactly at 11,264, then went 31 bytes OVER when the
  code review's finding 4 forced a step-2 rewrite; the overrun was resolved by tightening that
  same newly-written gloss (redundant with the script and the skill), not by cutting anything
  older. Per principle I the cap is a TRIPWIRE, not a wall: when it next binds against
  **load-bearing** content, STOP and bring the operator the specific trade — never compress
  meaning to fit, never raise the cap unilaterally. 23 bytes is not room for a real addition.
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

- **`pii_scanner.py --staged` is BLIND TO RENAMES** (found 2026-08-08, Step 3). `src/safety/
  pii_scanner.py:320` enumerates with `--diff-filter=ACM`; the pre-commit hook enumerates `ACMR`.
  Measured on the Step 3 commit: ACM 17 paths vs ACMR 284 — **267 renames invisible**, including a
  move-AND-edit git scored `R099`. The HOOK is unaffected, so committed content is still gated; the
  gap is in the by-hand command CLAUDE.md step 6 tells every session to run. Same defect class
  `.claude/rules/pii-safety.md` already records as a live bypass for the frozen-archive gate. A
  one-line fix that touches a security control — give it its own spec and a `/security-review`.
- **A `git mv` into `specs/done/` strands pointers.** Step 3 moved seven specs and stranded six
  references across four live specs; two were repointed (path-shaped / "See" navigation), four
  provenance records were left as written per the criterion-vs-evidence rule. Any future `done/`
  move owes the same sweep — the retired archive-refs gate used to catch exactly this class.

### Accepted residuals from Step 2

- **The PII pattern scanner is blind to EXTENSIONLESS files** — `is_scannable` gates on suffix,
  so a file with no `.` in its name is skipped as "non-scannable extension" regardless of
  `SKIP_PATHS`. Exactly two tracked files are affected today: `.githooks/pre-commit` (which is
  itself a PII gate) and `Dockerfile` (which the security checklist's 4h asks reviewers to check).
  Found at Step 2 because this chunk edits the hook; both were scanned BY HAND with a positive
  control and are clean. A one-line fix (treat a shebang or a known basename as scannable) —
  fold it into the next `src/`-touching chunk.
- **`.project/archive/`, `.project/research`, `.project/decisions`, `reviews/` keep role names and
  pre-freeze `epics/` paths.** Historical records, not pointers — they stay as written. The frozen
  `epics/` and `ideas/` trees moved under `.project/archive/` on 2026-08-08 and are history:
  salvage on demand, never bulk-migrate.
- **The `codex-review` skill vs. first-party `codex review` comparison was owed at Step 2 and was
  NOT done.** Carried forward at Step 3 rather than silently dropped.

Closed by Step 3 (2026-08-08): the `codex-spec-review` triad now takes a spec FILE path and emits a
`RESULT_FILE` receipt; the four epic/story/spike/idea templates are gone, replaced by one
`spec-template.md`; the archive-refs gate is retired (script, test, hook stanza, ops-doc section) —
it had become permanently unsatisfiable, since it swept the working tree including gitignored
`.codex-home/` Codex transcripts that regenerate on every `codex exec` run.
