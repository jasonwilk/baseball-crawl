# Line of march

The standing answer to "what should we do next?" Read this before proposing scope. Lifecycle
step 9 (HANDOFF) updates it: move what landed out of NOW, promote from NEXT, and add anything the
chunk discovered as a stub or a residual.

Individual chunk specs live beside this file as `<date>-<slug>.md`. Every one of them must read
`COMPLETE`, `READY`, `PARKED`, `STUB`, or `OPEN`, or belong to a chunk in flight. The vocabulary is
exactly those five. `READY` (added 2026-08-09, operator ruling) = spec written, codex-reviewed, and
committed — waiting only for a fresh execution session; the march's NEXT should name every READY
spec. `PARKED` now means ONLY "set aside deliberately, + why" — its former "ruled and queued" second
sense moved to READY. (`RULED` was retired 2026-08-08.) Audits verify READY specs are still wanted.

**`specs/done/`.** At handoff, a spec whose Status you just flipped to `COMPLETE` moves to
`.project/specs/done/` in the SAME commit. Everything still open stays in the live directory —
that is exactly what principle F's audit has to see. Note the rename cost: plain `git log` on the
new path shows only the move commit, so **use `git log --follow -- <path>`** to get a moved spec's
real history. Someday-work does not live here at all; it is one line in `IDEAS.md`.

## NOW

Clear. The rung-c season-year filter landed 2026-08-09 (spec in `done/`); pick the next chunk
from NEXT.

## NEXT

- **Migration Step 4 — second-pass rule trim.** After ~3 more real chunks, take the ~22 surviving
  path-scoped rules through "would removing this line cause a mistake?", run `/doctor`, and
  regenerate the cheat sheet from what actually got used. (The `PARKED`-splitting question this
  entry used to carry is CLOSED — settled ahead of Step 4 by `4fc1f6d`, which added `READY`. Do not
  re-open it.)
- ~~**Rung-c season-year filter**~~ — **LANDED 2026-08-09.** Spec moved to
  `done/2026-08-05-rung-c-season-year-filter.md`. It carried both queued residuals
  (worktree-guard `CLAUDE_HOME`, extensionless PII scannability) and settled the owed
  `codex-review`-vs-`codex review` comparison; all three are struck from the lists below.
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
- ✅ **CLOSED 2026-08-09** — `worktree-guard.sh` `CLAUDE_HOME` slash normalization. It was ~3 lines,
  not the 2 estimated; the empty case needed handling and had to DIVERGE from `REPO` (empty `REPO`
  denies, empty `CLAUDE_HOME` falls back to the literal default).
- ✅ **CLOSED 2026-08-09** — `codex-review` skill vs. first-party `codex review`. **Verdict: KEEP
  BOTH, they are not substitutes.** On one diff, four tools produced eleven findings with
  essentially ZERO overlap, and the two Codex paths failed in *characteristic* directions: the
  rubric-injected skill found the project-shaped defect (a fail-closed guard going silent), the
  uninstructed first-party path found the two a rubric would not prompt for (durable-state
  poisoning, and the already-cached-rows migration question). Dropping either would have lost real
  P1/P2/P3 findings. ⚠ Bound: ONE diff — this refutes "they are redundant", it is not a measured
  overlap rate. Feeds Migration Step 4.
- Residual one-sided game (both identifiers on the empty side) — needs a live probe.
- **`.env.example` carries three `email` matches and is now SCANNED** (2026-08-09). Our own
  `noreply@` service address plus two `USER:PASS@host` proxy-URL FORMAT comments — read and
  confirmed to hold no credential and no person's address. **Operator ruled: LEAVE, no suppressor.**
  Consequence to know: staging `.env.example` will trip the hook. Reword the lines then — remedy #1
  (change the data), never a `pii-ok` inside a credential template.
- **The extensionless scan allowlist is a NAMED LIST** (`SCANNABLE_BASENAMES`, 2026-08-09). A NEW
  extensionless file stays unscanned until someone adds its basename. A shebang test cannot replace
  it: the scannability gate runs BEFORE the content read on both paths, and `Dockerfile` has no
  shebang anyway.
- **Still outside the PII scan surface entirely** (surfaced by the 2026-08-09 security review, not
  fixed): non-dotfile templates whose final suffix is unlisted
  (`docker-compose.override.yml.example`), and file types absent from `SCANNABLE_EXTENSIONS`
  (`migrations/*.sql`, `requirements.in`, `*.conf`). Widening the surface to those is a policy call,
  not a bug fix.
- **`/security-review` can be handed the WRONG DIFF on uncommitted work** (2026-08-09). Its
  `DIFF CONTENT` came from the COMMITTED range while `GIT STATUS` showed the working tree; since
  markdown findings are an excluded category, it would have returned a VACUOUS CLEAN over two
  modified security controls. Check the scope before trusting the verdict.
- **Pre-existing `opponent_links` rows with `resolution_method='search'` never see the season-year
  filter** — the terminality gate short-circuits them, so a pre-patch cross-year auto-match survives.
  **Operator ruled 2026-08-09: LEAVE.** Correctable via `bb report map-opponent`, and they die at the
  next data reset regardless. No invalidation, no migration.
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

- ✅ **CLOSED 2026-08-09** — the PII scanner's blindness to EXTENSIONLESS files (`Dockerfile`,
  `.githooks/pre-commit`), fixed with a named-basename allowlist. The fix found a SECOND hole the
  residual had not named: `Path.suffix` lies about dotfiles carrying a further suffix, so the
  TRACKED `.env.example` and `proxy/.env.example` were unscanned too — the likeliest files in the
  repo to receive a real token by copy-paste. Both classes are now scanned, proven a strict
  widening (0 narrowings over 36,932 synthetic paths and 2,485 tracked files, against a control
  that produced 1,680).
- **`.project/archive/`, `.project/research`, `.project/decisions`, `reviews/` keep role names and
  pre-freeze `epics/` paths.** Historical records, not pointers — they stay as written. The frozen
  `epics/` and `ideas/` trees moved under `.project/archive/` on 2026-08-08 and are history:
  salvage on demand, never bulk-migrate.
- ✅ **CLOSED 2026-08-09** — the `codex-review`-vs-`codex review` comparison, owed since Step 2 and
  carried (not dropped) at Step 3. Verdict and its bound are in STANDING RESIDUALS above.

Closed by Step 3 (2026-08-08): the `codex-spec-review` triad now takes a spec FILE path and emits a
`RESULT_FILE` receipt; the four epic/story/spike/idea templates are gone, replaced by one
`spec-template.md`; the archive-refs gate is retired (script, test, hook stanza, ops-doc section) —
it had become permanently unsatisfiable, since it swept the working tree including gitignored
`.codex-home/` Codex transcripts that regenerate on every `codex exec` run.
