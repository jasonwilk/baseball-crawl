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

Clear. The `docs/` retired-workflow sweep landed 2026-08-09 (spec in `done/`); pick the next
chunk from NEXT.

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
- ~~**Sweep `docs/` for the retired workflow**~~ — **LANDED 2026-08-09.** Spec moved to
  `done/2026-08-09-docs-retired-workflow-sweep.md`. `docs/admin/agent-guide.md` deleted (124
  lines); 26 files touched; no executable line of `scripts/codex-review.sh` changed (proven by a
  before/after diff of its `--help` output, not by a `#`-prefix check).

  **The undercount ran to five passes, not three.** The spec inherited a 12-site inventory built
  across a term-grep pass, the codex-spec-review, and a post-`902fb1e` file-then-read pass. The
  execution session's re-run of Verification 10 found **six more**, taking it 5 → 8 → 12 → 18:
  `ephemeral/README.md` (the per-epic convention `safe-data-handling.md` points AT as "the full
  convention"), `.claude/rules/devcontainer.md:85,106` ("closure-gate tests"),
  `.claude/rules/dependency-management.md:46` ("a story's Files to Modify list"),
  `docs/admin/operations.md:309` ("until a follow-up story removes it"), and
  `.claude/rules/python-style.md:20`. **Four of the six sat in files already on the edit list** —
  the same blind spot that produced passes 1 and 2, reproduced by an inventory that had already
  been corrected twice for exactly it. Re-running the sweep is what caught them; trusting the
  inbound inventory would not have.
- **PII scanner hardening** — **READY 2026-08-10**, spec
  `2026-08-10-pii-scanner-hardening.md`. Closes both `get_staged_files()` enumeration bypasses (`ACM`→`ACMR`
  and `-z`), each behind a RED test proven failing first, and takes the two inert `epics/` entries out with
  every restatement of them. Execution needs a FRESH session and owes `/code-review` **and**
  `/security-review`, operator-typed as two separate messages. It also carries a pre-registered review
  experiment (all arms against one frozen diff, criterion stated before the data) that feeds Audit 4 — run it
  as written; fixing between passes is what muddied the last measurement.
- **Plays final-score recovery (seed §2)** — **READY 2026-08-10**, spec
  `2026-08-10-plays-final-score-recovery.md`. Recovers the game-ending run that GameChanger puts on
  a trailing play our parser skips: **91 units / 88 games, 102 runs**, and youth is hit ~2.5× harder
  than high school (7.9% vs 3.2%). Execution needs a FRESH session and owes `/code-review`;
  `/security-review` is explicitly NOT needed (no auth/serving/PII/delete surface) — the spec says
  so rather than leaving it assumed. **Read Verification 0 first**: it gates on score sums and the
  step-6 count, NOT on `player_game_*` row counts, which drift on their own. A post-commit backfill
  (backup → reset → re-scout) follows in its own session; its success criterion is **91 → the
  abandoned-charting residual, NOT → 0**.
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
- **The reconciliation gate CANNOT work on a growing corpus, and this is a design fault, not drift**
  (found 2026-08-10). `evaluate_gate` ratchets on ABSOLUTE deltas, so data growth alone fails it:
  across one ingest, pitching-BF accuracy moved 98.8% → 98.5% while its abs-Δ went 132 → 464. Nothing
  got worse; the corpus tripled. **Why you should care**: `CLAUDE.md` calls `reconcile-scoreboard`
  "a diagnostic, not a gate", but the CLI still calls `evaluate_gate`, exits non-zero, and its
  docstring calls itself "the north-star ratchet" — so every session that runs it sees a red FAILED
  it must be told to ignore. Reviving it needs RATE-based thresholds; retiring it means deleting the
  gate half. Operator ruling owed. ⚠️ **The nearest prior record, `IDEA-195`, is ARCHIVED
  (`.project/archive/ideas/`, not live `IDEAS.md`) and its PREMISE IS NOW REFUTED**: it calls the
  machinery "vestigial" and the scoreboard "a pure diagnostic with no verdict to trip". Measured
  2026-08-10 — the CLI calls `evaluate_gate`, prints `Reconciliation gate FAILED`, and exits **RC=1**.
  It is live, not vestigial. Read that idea before acting anyway: it carries a real footgun about two
  ratchets sharing this vocabulary, and says to scope any deletion by FILE, never by grepping
  "baseline"/"ratchet"/`--update-baseline`.
- **Row counts cannot detect an UPDATE — do not use them as a "DB is settled" check** (found
  2026-08-10, cost two rounds of wrong numbers in one spec). `games` and `plays` counts held
  identical at 2,303 / 143,613 across an entire session while `games.home_score` changed underneath,
  moving a measured population from 92 units to 91 and invalidating a 90-game validation run.
  **Why you should care**: every before/after measurement in this repo rests on a stability
  assumption, and the obvious check is the one that fails silently. Gate on CONTENT (score sums, the
  detection count itself), and only on the tables the chunk actually depends on.
- **The plays endpoint doc is silent on the terminal play's score fields** (found 2026-08-10).
  `docs/api/endpoints/` records the `${uuid} at bat` trailing play as "1 per game, always last,
  empty final_details" — but not that it carries `0`/`0` with `did_score_change: false` normally,
  and the REAL final with `did_score_change: true` when the last PA was unresolved mid-scoring.
  **Why you should care**: that silence is the entire defect the §2 chunk fixes, and the doc as
  written invites the exact rule that would zero every score in the DB. One paragraph.
- **`teams.classification` is unset on ALL 1,029 teams; `innings_per_game` is fetched for 66**
  (found 2026-08-10). **Why you should care**: any future segmentation by level (youth vs HS vs
  Legion) has no direct column to use — the §2 chunk's 2.5× youth skew rests on regulation-innings
  as a proxy over a 66-team basis. A real level analysis needs one of these backfilled first.
- ✅ **CLOSED 2026-08-10** — CI's whole-tree PII scan was RED on `main`, found by the scanner-hardening
  chunk's `/code-review` and NOT introduced by it. The 2026-08-09 dotfile widening made `.env.example`
  scannable and it carried three `email` matches, so CI's own command exited **123**, failing `ci.yml:95`
  under `pipefail`. **The operator ruling changed** — the earlier "LEAVE, no suppressor" was made against
  only half the consequence (it named the pre-commit hook, not CI). Fixed by remedy #1, changing the data:
  the FROM address moved to an RFC 2606 domain, and the two proxy-URL format comments to angle-bracket
  placeholders. Same command now exits **0**. Positive control: re-adding the old address returns RC=1, so
  the instrument still fires. **The lesson worth keeping**: a consequence stated for one gate is not the
  whole consequence — this ruling named the hook and missed CI, and nothing re-checked it for eight days.
- **`tests/fixtures/*.sql` are outside the scan surface and the residual below does not name them.** The
  `SCANNABLE_EXTENSIONS` gap recorded for `migrations/*.sql` also leaves `tests/fixtures/seed.sql`,
  `parity_consistent.sql`, and `recon_scoreboard_seed.sql` unscanned. **Why you should care**: seed fixtures
  are the higher-risk half — the plausible landing spot for a real player name or email, the same class that
  once put a real minor's name in a planning file.
- **The `codex-spec-review` rubric is stale on spec Status.**
  `.project/codex-spec-review.md:48` still lists FOUR statuses and calls a fifth a finding, but `READY` was
  added 2026-08-09. **Why you should care**: it flags every `READY` spec — it flagged the one committed
  today, and codex noted the conflict itself. One-line docs fix; it does not belong inside a security chunk.
- **`.project/ideas/` is inert in `SKIP_PATHS`** (found 2026-08-10). No such directory exists — ideas live at
  `.project/specs/IDEAS.md`, history at `.project/archive/ideas/`. **Operator ruled 2026-08-10: LEAVE.**
  Unlike `epics/`, which can never return, this tree plausibly could, and the re-measured TN-2 noise
  rationale still covers it. Recorded so the next sweep does not re-discover it as a defect.
- ✅ **CLOSED 2026-08-10** — three PII-scanner residuals below (`--staged` rename blindness, the `-z`
  C-quoting bypass, the inert `epics/` entries) all landed in the scanner-hardening chunk. Spec moved to
  `.project/specs/done/`. **Four NEW residuals that chunk's five-arm review surfaced are recorded above** —
  read those, not these.
- **`pii_scanner.get_staged_files()` fails OPEN when git itself fails** (found 2026-08-10, `/code-review` +
  bare-headless). `except (CalledProcessError, FileNotFoundError): return []`, and `main()` then hits
  `if not file_paths: return 0` — printing NOTHING and exiting 0. Reproduced from a non-repo cwd: `rc=0`,
  silent. `.claude/hooks/pii-check.sh` reads exit 0 as "no PII found, allow the commit". **Why you should
  care**: this is the same fail-open class the unreadable-blob handler 100 lines below explicitly refuses —
  that path prints `REFUSING to certify clean` and exits non-zero; this one certifies clean silently. Not
  fixed in the hardening chunk because raising changes the contract for every caller and needs its own RED
  test and `/security-review`.
- **The git pre-commit hook scans the WORKING TREE, not the staged blob** (found 2026-08-10 by three of five
  review arms independently). `.githooks/pre-commit:107` pipes paths to `pii_scanner --stdin`, which routes
  `scan_files` → `scan_file` → `Path.read_text()`. Reproduced side by side: stage a token, blank the
  working-tree copy, commit → `Scanned 1 file(s), 0 violations`, rc=0, token in `HEAD`; the same path under
  `--staged` → `[PII BLOCKED]`, rc=1. **Why you should care**: `.claude/rules/pii-safety.md` advertises
  staged-blob reading as a scanner capability, and it is real — but ONLY in `--staged`, which is the agent
  PreToolUse hook. A human `git commit` does not get it. The byte-gate half of the hook judges the index
  correctly; it is only the pattern-scanner half that reads the working tree. This is a LARGER divergence
  than the flag drift the hardening chunk just closed.
- **A typechange (`T`) reaches zero PII gates, and empties the hook's staged set so the byte-gate is skipped
  too** (found 2026-08-10, `/security-review`, reproduced). Replacing a tracked symlink with a regular file
  scores `T`, which `--diff-filter=ACMR` drops on BOTH enumerations. Executed: a `T`-only staged set returns
  zero bytes → scanner rc=0 with no output, and in the hook `STAGED_ARR` is empty so it `exit 0`s at line
  100-102 **above** the byte-gate. **Why you should care**: the repo currently tracks no symlinks, so this
  needs a two-step sequence — that is what makes it a residual and not a live hole. Fix is `ACMRT` in both
  enumerations in ONE commit, or invert to `--diff-filter=d` so a future status letter defaults to *scanned*.
- **DISPUTED, owed an operator ruling: does removing `epics/` from `GATE_TREES` reduce coverage?** Codex
  (2026-08-10, P1) reproduced that with `epics/` gone from the gate, staging `epics/E-999-demo/epic.md` with a
  denylisted identifier now commits clean, and cites `AGENTS.md:8` still naming `epics/` as a work location.
  The counter-argument, which the spec and the prior operator ruling rest on: the tree is retired and deleted,
  nothing is under it, and keeping dead entries forever is the drift `CLAUDE.md` warns against. **Both are
  true** — the entry was doing LATENT work, and the session did not silently overrule the ruling. **Why you
  should care**: the real question is whether the byte-gate should gate ALL staged paths rather than a tree
  allowlist, which would moot the argument permanently. Decide the general form, not the `epics/` instance.
- **The inert `epics/` entries in the two security controls ride the scanner-hardening chunk.**
  `src/safety/pii_patterns.py` (`SKIP_PATHS`) and `.githooks/pre-commit:125` (`GATE_TREES`) both
  still name `epics/`. Neither can match — nothing can be staged under a tree that does not
  exist — so the 2026-08-09 docs sweep deliberately left them. **Why you should care**: they must
  move WITH `.claude/rules/pii-safety.md:50,52,54`, which restates `SKIP_PATHS` accurately as the
  code stands today. Editing either side alone breaks a doc/code agreement that is currently
  correct. Route them through the chunk that owns the `pii_scanner --staged` rename blindness
  below, which already owes a `/security-review`.

  **ROUTED 2026-08-10** — spec `2026-08-10-pii-scanner-hardening.md`, Status `READY`. ⚠ **The coupling claim
  above was AUDITED and is over-broad — do not execute it as written.** Only `:54` restates `SKIP_PATHS` and
  must move. `:52` is a section heading (cosmetic). **`:50` is REFUTED and must be LEFT ALONE**: its `epics/`
  mentions are historical provenance plus an illustration mirrored verbatim at `scripts/check_doc_pii.sh:57`,
  so editing it would CREATE the divergence this residual exists to prevent. The spec carries the evidence.
- **The runtime smoke check is not a named step in the `CLAUDE.md` lifecycle.** The 2026-08-09
  sweep retitled it to "Runtime Smoke Check" (`docs/admin/production-deployment.md`) and restated
  its trigger as operator-run before a commit touching a runtime or build-input surface — but
  nothing in the lifecycle tells the operator to run it. **Why you should care**: it used to fire
  automatically at epic closure, and that trigger is now deleted, so a real gate silently became
  opt-in. Wiring it into `CLAUDE.md` is a byte-cap trade (~23 bytes of headroom), which principle
  I sends to the operator, not to a session.
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
- ✅ **SUPERSEDED 2026-08-10** — `.env.example` was SCANNED and carried three `email` matches (2026-08-09):
  our own `noreply@` service address plus two proxy-URL FORMAT comments, read and confirmed to hold no
  credential and no person's address. **The 2026-08-09 ruling was "LEAVE, no suppressor", and it named the
  consequence as only "staging `.env.example` will trip the hook."** That was half of it — CI's whole-tree
  scan was also failing, which nobody checked for eight days. **Ruling reversed 2026-08-10: reworded, still
  no suppressor**, by remedy #1 exactly as this bullet prescribed. The file now scans clean. What survives
  from the original: the three matches never were PII, and a `pii-ok` inside a credential template is still
  the wrong instrument.
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

  **ROUTED 2026-08-10** — spec `2026-08-10-pii-scanner-hardening.md`, Status `READY`. Two corrections to the
  above. The citation **`:320` has drifted to `:353`** (the file grew when the extensionless fix landed
  2026-08-09). And it is **not** a one-line fix: the same function has a SECOND documented bypass — no `-z`,
  so a C-quoted path names no readable file — which the operator ruled rides along, so the chunk is two fixes,
  two RED tests, and the `epics/` removals above. It also reaches further than "the by-hand command":
  `.claude/hooks/pii-check.sh:35` runs `--staged` as a PreToolUse gate on **every agent commit**.
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
