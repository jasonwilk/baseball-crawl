# Spec: CLAUDE.md rewrite + line of march (migration Step 1)

**Date:** 2026-08-06 · **Status:** OPEN — spec approved, execution owed in a fresh session.
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
3. `wc -c CLAUDE.md` ≤ 8192; `wc -l .claude/rules/tool-discipline.md` ≤ 20.
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
