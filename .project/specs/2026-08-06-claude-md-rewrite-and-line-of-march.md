# Spec: CLAUDE.md rewrite + line of march (migration Step 1)

**Date:** 2026-08-06 · **Status:** COMPLETE (this commit).
**Source of truth:** `.project/research/2026-08-02-system-redesign-proposal.md` §6–7 and its
§9 Appendix (the agreement being transcribed). That file is the historical record — **do not
edit it.** Where the proposal and the repo disagree, the repo wins.

## Goal

Cut always-on context from ~87.7KB to ~9KB and make the operating agreement **ambient**
instead of pasted by hand. Audit 2 finds every current failure is framing, so CLAUDE.md leads
with the **product frame**, then the lifecycle card, then pointers.

## Files

### Delete (`git rm`)
- `.claude/rules/`: `dispatch-pattern.md`, `agent-routing.md`, `agent-team-compliance.md`,
  `workflow-discipline.md`, `worktree-isolation.md`, `doc-sweep.md`, `project-management.md`,
  `context-layer-assessment.md`, `context-layer-guard.md`, `tool-output-integrity.md`
- `.claude/skills/implement/`, `.claude/skills/plan/` — closes the trigger-phrase trap;
  nothing mechanical depends on them (grep over `tests/ scripts/ src/ .claude/hooks/` is empty).
- `.claude/hooks/context-ratchet.sh`, `.claude/hooks/dispatch-telemetry.py` — both **unwired**
  (0 matches in `settings.json` / `settings.local.json`; `context-ratchet.sh:4` says so itself).

### Write
**`CLAUDE.md`** — full rewrite, **≤8KB** (the ~6KB in earlier notes is superseded: the
agreement block alone is 5,342 bytes, measured at proposal `:388–473`). Sections in this order:

1. **PRODUCT FRAME (~1.5KB, first).** Reports-first — generate a scouting report for a
   GameChanger `public_id`, share the link. **Any** team by `public_id`: high school, Legion,
   USSSA/travel youth. A 9U team is a real user's team; reasoning "this is a high-school
   program, so a youth team is junk" once nearly discarded 84 real teams (2026-07-25).
   Single-season, one report at a time. **Explicit non-goals** barring what E-239 deleted:
   cross-team player identity, multi-season rollups, longitudinal tracking. The
   **byte-identical-ingestion north star**. The **two destructive seams**: `bb report generate`
   hard-deletes `games` and their child surface plus unreachable `teams` / `players` /
   `team_rosters`; `bb db purge-scouting` wipes 20 of 27 tables, `--force` and `--yes` are
   **separate** flags. Pointers to `docs/VISION.md` / `docs/ROADMAP.md` for the rest.
2. **HOW WORK GETS DONE HERE** — the 10-step chunk lifecycle + principles A–H, transcribed
   from the proposal appendix. **Every line imperative, addressed to the session, executable
   as written** — passive waypoints have failed twice. Step 9's Status vocabulary must match
   what the specs actually use: **COMPLETE / PARKED / STUB / OPEN** (the card names only two).
3. **LINE OF MARCH** — names `.project/specs/README.md`; read it before proposing scope.
4. **FACTS** — tech stack; the 5 GameChanger API gotchas; commands pointer
   (`docs/admin/operations.md`); security rules; git conventions incl. the `[pii-hook]` receipt.
5. **POINTERS** — the surviving path-scoped rules, by what each answers.

**`.claude/rules/tool-discipline.md`** — new. Frontmatter exactly `paths:` → `- "**"` (match
`vision-signals.md`). **≤20 lines**, 7 items: the garbled-vs-moved differential; grep finds
candidates, only a Read confirms; an unexpected count in either direction is a cross-check
trigger, never a finding; a clean result counts only with a positive control **confirmed
present in the target first**; prose you author or relay about code is an unverified claim;
doc sweeps need token grep + synonym expansion + a read; never trust a piped pytest exit code.
*(Proposal says ≤15; raised to 20 because 3 items were added beyond the original four.)*

**`.project/specs/README.md`** — new. Four sections: **NOW / NEXT / PARKED DECISIONS /
STANDING RESIDUALS**. Seed from audit 2's 3 decisions owed and 4 standing residuals, plus the
accepted residuals below. Lifecycle step 9 updates it.

**`.claude/skills/workflow-help/SKILL.md`** — regenerate the cheat sheet against the new
lifecycle; it currently prints triggers for the deleted skills.

### Edit
- `.claude/settings.json` — remove `env.CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`.
- **Reference sweep — 5 files, 16 refs** (enumerated per-file):

| File | Refs |
|---|---|
| `.claude/skills/codex-review/SKILL.md` | 11 — `implement skill` ×7 (`46`×2, `85`, `114`×2, `142`×2); `tool-output-integrity` (`97`); `workflow-discipline` (`110`, `352`); `agent-routing` (`115`) |
| `.claude/skills/workflow-help/SKILL.md` | 2 (`60`, `61`) — regenerated, not patched |
| `.claude/skills/codex-spec-review/SKILL.md` | 1 (`72`) |
| `.claude/agents/api-scout.md` | 1 (`196`) |
| `.claude/rules/testing.md` | 1 (`24`) |

`codex-review` gets a **bounded scrub only**: drop the "and review" dispatch-chain mode;
replace the two `workflow-discipline` authorization citations and the `agent-routing`
remediation-team citation with "the session fixes real findings." Deeper single-sourcing off
`code-reviewer.md` stays Step 2. `ingest-endpoint`, `baseball-coach`, `documentation.md`,
`ideas-workflow.md`, `devcontainer.md`, `pii-safety.md` have **zero** deleted-file refs.

## Accepted residuals (record in `specs/README.md`; all expire at Step 2)
The 7 agent definitions and the `context-fundamentals` / `agent-standards` skills keep dangling
refs to deleted rules; `product-manager.md` and `code-reviewer.md` also reference the deleted
skills. `epic-archive-check.sh` stays wired (`epics/` holds E-271/E-274/E-275, none COMPLETED,
so it does not fire). `codex-review` lacks `disable-model-invocation: true`.

## Out of scope
Step 2 (agent definitions, agent-memory archival, `epic-archive-check.sh`, codex-review
single-sourcing, `ingest-endpoint` phase-2). Step 3 (spec template, `specs/done/`,
`codex-spec-review` input rewrite, `documentation.md` / `ideas-workflow.md` trims). Step 4
(trimming the 22 path-scoped rules). `epics/`, `.project/archive/`, `.project/research/`, and
completed `.project/specs/*` chunk logs are dated records of what past chunks did — rewriting
them falsifies the record, so they are excluded from the sweep by design.

## Verification

1. `python -m pytest tests/` — baseline **4434 passed / 0 failed @ `d6645de`**, measured
   2026-08-06. **Weak signal here:** no wired hook, test, script, `docs/`, or `src/` file
   references any deleted rule, so the mechanical blast radius is zero. Green means "nothing
   collapsed," not "the change is right." Do not pipe the run — a pipe reports its own exit code.
2. `bash -n .claude/hooks/*.sh`; `python -c "import json; json.load(open('.claude/settings.json'))"`;
   `ls .claude/hooks/*.py` returns nothing (no Python hook survives).
3. `wc -c CLAUDE.md` ≤ 8192 **(SUPERSEDED at review time — cap raised to 11KB by operator
   decision; see Progress, "Fourth departure")**; `wc -l .claude/rules/tool-discipline.md` ≤ 20.
4. **Reference sweep by ABSENCE.** Pattern: the 10 deleted rule stems plus
   `skills/implement|skills/plan|implement skill|plan skill`. Scope: `CLAUDE.md`,
   `.claude/rules/`, `.claude/skills/`, `.claude/hooks/`, `.claude/settings.json`, kept agents.
   **Run per-file in a loop, or `-r` against one directory at a time — never multiple path
   arguments with an alternation:** that form returns a silent EMPTY in this environment and
   produced a false clean while this spec was being written. Expect **zero** outside the
   accepted residuals. **Positive control:** before trusting any empty, run the pattern against
   a file *verified by Read* to contain one of the stems. A control drawn by assumption is not
   a control — that failed during planning for exactly this reason.
5. `grep -rn CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS .claude/settings.json` → zero.
6. `grep -rnE 'Dispatch active|two modes'` over `CLAUDE.md`, then `.claude/rules/`,
   `.claude/skills/`, `.claude/agents/` **separately** → zero. Agent-memory is excluded; those
   files are archived at Step 2.
7. Lifecycle step 6: `python3 src/safety/pii_scanner.py --staged`, **comparing scanned-count to
   staged-count**. `.claude/` is in `SKIP_PATHS` (`src/safety/pii_patterns.py:164`) and this
   chunk stages almost nothing else, so the gate scans near-vacuously — give staged `.claude/`
   files a manual pass with a positive control.

## Progress

**2026-08-06 — executed in one session. All verification commands run.**

Landed as specified: 10 rules, 2 skills and 2 unwired hooks deleted; `CLAUDE.md` rewritten
(product frame → lifecycle → line of march → facts → pointers); `tool-discipline.md` and
`.project/specs/README.md` written; `workflow-help` regenerated; the 5-file reference sweep
applied; `env.CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` removed.

Verification results:

1. `python -m pytest tests/` — **4434 passed, 0 failed, RC=0**, matching the spec's baseline
   exactly. Run unpiped with `$?` captured to a file. Weak signal by the spec's own reasoning,
   and it stayed weak: nothing mechanical referenced the deleted files.
2. `bash -n` clean on all 6 surviving hooks; `settings.json` parses; `ls .claude/hooks/*.py`
   returns no matches — no Python hook survives.
3. `wc -l tool-discipline.md` = **14** (≤ 20). **`wc -c CLAUDE.md` = 10,585, which DOES NOT meet
   the spec's ≤ 8192 — the cap was raised to 11KB by operator decision at review time. See the
   fourth departure below.** The file did meet 8192 (at 8157, then 8189 after the review's prose
   fixes); the cap was lifted deliberately, not missed.
4. Reference sweep by absence — run per-file, never multi-path-with-alternation. **Positive
   control confirmed by Read first**: `.claude/agents/code-reviewer.md:368` carries both
   `skills/implement` and `dispatch-pattern` contiguously; the pattern returned 6 there, so the
   zeros below are verified absence rather than an unexplained empty. **Zero** in `CLAUDE.md`,
   `.claude/rules/`, `.claude/hooks/`, `.claude/settings.json`, and all four surviving
   user-facing skills.
5. `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` in `settings.json` — zero.
6. `Dispatch active|two modes` — zero in `CLAUDE.md`, `.claude/rules/`, `.claude/skills/`,
   `.claude/agents/`, each swept separately.
7. Lifecycle step 6 PII gate, scanned-count vs staged-count: **3 scanned of 24 staged**, 0
   violations. The 21 skipped are all `.claude/` (14 of them deletions). Manual pass on the 7
   added/modified `.claude/` files: a control-verified pattern sweep (credential/email/phone
   shapes) over the 107 added lines returned **0**, with the same pattern returning 2 on a
   known-bad control file. Name coverage, which no pattern reaches, via
   `scripts/check_doc_pii.sh`: `.project/specs` → rc=0 PASS; `.claude` → rc=1, but **zero
   overlap** with the 21 files this commit touches (all hits pre-existing in `agent-memory/`,
   four agent definitions, and three rules), confirmed with an injected-overlap control proving
   `comm` could detect one.
   **Finding:** `SKIP_PATHS` blinds the scanner even to EXPLICIT file arguments. Copying a
   known-bad file under `.claude/` returned RC=0 and printed nothing, versus RC=1 outside — so a
   silent RC=0 there is vacuous, not clean. Recorded as a standing residual.
8. Write-safety guard proved in both directions by live probe: an outside-repo write and a
   `..`-traversal write were both DENIED (neither left a file on disk), a scratchpad write was
   ALLOWED. Principle G applied to the guard itself.

**Review (lifecycle step 5).** Codex review + an independent adversarial review. Dispositions:

- **FIXED** — `codex-spec-review/SKILL.md:77,193` cited "CLAUDE.md's Agent Ecosystem table,"
  which this rewrite deletes. I had fixed the identical line in `codex-review` and not swept its
  sibling. Both now read `.claude/agents/`; verified by absence with a live control.
- **FIXED** — CLAUDE.md steps 7, 8 and 9 each failed the spec's own acceptance criterion. Step 8
  was purely descriptive and had **lost the investigate-on-missing-receipt lesson** entirely
  (the receipt's ABSENCE is the alarm); step 7 described the operator's behavior instead of
  instructing the session; step 9 ordered a Status flip whose deadline had already passed two
  steps earlier, so it was executable only by reading ahead. The flip now lives in step 7. Byte
  compression had also dropped "no hash needed," inverting it into an instruction to cite a
  hash — restored.
- **FIXED** — Principle F named only COMPLETE/PARKED, so a session reading it alone could
  conclude STUB is an illegal state. It now names all four.
- **FIXED** — the `epics/` enumeration was wrong in the spec and in the line of march: five
  directories, not three, and the omitted **E-263 is READY with real product work**. The
  conclusion (the hook does not fire) survives — verified against the hook's match rule and all
  five status lines — but it was a false premise under a correct conclusion, sitting in the file
  that now answers "what next," about the one epic Step 3's freeze would strand.
- **DISMISSED** — "spec marked COMPLETE before the commit exists." This is the ratified design:
  step 9 prescribes flipping before staging, and the prior chunk's spec
  (`2026-08-05-rung-c-search-resolve-recoverable.md`) uses the identical `**COMPLETE (this
  commit)**` form.
- **DEFERRED to a new chunk** — `docs/` still teaches the retired flow (~110 refs / 18 files;
  `docs/admin/agent-guide.md` is about nothing else). Two references break with this commit:
  `production-deployment.md:507` → the deleted implement skill, and `agent-guide.md:102` →
  `context-ratchet.sh` "survives," now false. Logged under NEXT.
- **NOTED, no change** — `.claude/rules/devcontainer.md:101` and `documentation.md` /
  `ideas-workflow.md` describe procedures owned by roles that die at Step 2 but are not trimmed
  until Steps 3–4. The migration sequencing accepts this window; it had not been written down.
- **NOTED, no change** — a THIRD "Agent Ecosystem table" reference stands at
  `.claude/skills/agent-standards/SKILL.md:121`. Left deliberately: unlike `codex-review` and
  `codex-spec-review`, which survive, `agent-standards` dies at Step 2. Recorded because the
  FIXED entry above would otherwise read as though the sibling sweep were exhaustive.

**Third departure from the spec.** Files §4 says FACTS carries "git conventions incl. the
`[pii-hook]` receipt". The shipped Facts/Git line does not: the receipt moved to lifecycle step 8,
where it sits at the point of action and carries the alarm semantics (its ABSENCE is the signal)
that a passive mention under Facts would not. Deliberate, and better, but a deviation.

**Fourth departure — the 8KB cap was raised to 11KB by operator decision.** The cap was not merely
tight, it was TRADING AGAINST the spec's own acceptance criterion. Meeting 8192 cost, in order:
the POINTERS per-rule enumeration that Files §5 explicitly asked for (compressed to one browse
sentence), the line-of-march section names, the `bb` command groups, "treat GameChanger session
tokens as sensitive at all times", the pip-tools / `docker compose up` / server-rendered stack
detail, and principle H's "(a worktree needs its own HEAD)" clause — plus three prose defects
introduced by the compression itself, one of which (a line beginning `- ` mid-paragraph) would
have rendered as a stray markdown bullet. The operator chose to restore the dropped context.
Restored at 10,585 bytes against a new 11KB (11,264-byte) cap, ~680 bytes of headroom.

Two items were restored that the cap did NOT force out — the spec's section outline simply had no
place for them, and the adversarial review flagged both as silent losses: **"Simple first.
Complexity as needed."** (the repo's founding principle, absent from the new file and from the
spec's outline) and the **mitmproxy host-vs-container boundary** (previously ambient, reduced by
this migration to a path-scoped rule invisible to a session that runs a `mitmproxy` Bash command
without touching `proxy/**`). The Data Philosophy was restored on the same grounds. Reversible: if
the intent was to drop them, delete those three blocks.

Two departures from the spec, both recorded in `.project/specs/README.md`:

- **The accepted-residual list was incomplete.** The sweep found a live reference to the deleted
  `implement` skill in `.claude/skills/multi-agent-patterns/SKILL.md:50` (confirmed by Read, not
  by grep count). Same class as the listed residuals, same Step-2 expiry, so it was left standing
  and recorded rather than fixed. The list also over-predicted the agent count: five definitions
  carry dangling refs, not seven — `docs-writer` and `ux-designer` have none.
- **`codex-review` needed one edit beyond the enumerated scrub.** Its triage step routed agent
  selection through "CLAUDE.md's Agent Ecosystem table", which this rewrite deletes. Left as-is
  it would have been a dangling claim created by this chunk, so it now reads `.claude/agents/`
  directly. Deeper single-sourcing remains Step 2.

**The 8KB cap is now the binding constraint on CLAUDE.md and it actively fought prose quality.**
Reaching it required cutting the pointer section from a per-rule enumeration to a grouped browse
line, and an intermediate draft introduced three prose defects that only a full read-back caught
— including a line beginning `- ` mid-paragraph, which markdown would have rendered as a stray
list item. Budget a removal before any future addition.
