<!-- NO REAL NAMES OR IDENTIFIERS — no person's name, ever; for teams, orgs, ids and UUIDs use the PII-Safe Placeholder Taxonomy in `.claude/rules/api-docs.md`. -->

# Rung (c): require a season-year match before auto-accept

**Date**: 2026-08-05 (spec written 2026-08-09) · **Status**: `COMPLETE (this commit)` — executed
2026-08-09. Full suite green (4471), both step-5 reviews run and folded in, all three carried
questions ruled by the operator. (`READY` was added to the vocabulary 2026-08-09, `4fc1f6d`,
resolving the `PARKED` double-duty this line previously had to gloss around — this spec was the
first to carry it, and it is now the first to retire it.)
**Source**: operator ruling 2026-08-08 (`README.md` PARKED DECISIONS #2, now in NEXT). Split out of
`2026-08-04-rung-c-auto-accept-criteria-drift.md`; premise re-established by the codex spec review
of `2026-08-05-rung-c-search-resolve-recoverable.md`.

## Goal

Rung (c) of the opponent-resolution ladder auto-accepts on **exactly one team hit and nothing
else** — no name corroboration, no season corroboration. After this chunk it also requires the
search hit's `result.season.year` to equal the member team's `teams.season_year`; a mismatched or
absent year drops the hit before the uniqueness bar, and a member team with no stored year refuses
every rung-(c) auto-accept. Two queued residuals ride along because this is the next `src/`-touching
chunk: the worktree guard stops rejecting legitimate `~/.claude/` writes when `HOME` carries a
trailing or doubled slash, and the PII pattern scanner stops skipping extensionless files.

**Ruled semantics (operator, 2026-08-08 — settled, do not reopen).** A team from one YEAR must never
auto-match a team from another year. Cross-season *within* the same year (spring 2026 vs summer
2026) is legitimate and must still auto-accept — so the comparison is on `season.year` alone and
**never** on `season.name`. A hit with `season.year` absent refuses auto-accept (fail-closed). The
comparison is against the member team's `teams.season_year`, not the scheduled game's date.

**Direction of the trade, stated plainly:** this TIGHTENS auto-accept. Fewer wrong auto-resolves,
more opponents punted to the operator queue. That is the opposite trade from the entity-class
filter, and the operator absorbs the difference. A wrong auto-resolve is correctable via
`bb report map-opponent` (2026-08-05) but must be NOTICED first, and an unnoticed one feeds reports
indefinitely — prevention and recovery are complements, which is why this is still worth building.

## Files

**Behavior changes**

- `src/gamechanger/opponent_ladder.py` — `_resolve_via_search` takes the member season year and
  filters on it; `resolve_opponent` reads `teams.season_year` for `our_team_id` and passes it down.
- `src/reports/morning_run.py` — `run_morning` (~L662) passes `season_year` to `ensure_team_row` so
  the own-team row is not created with a NULL year.
- `.claude/hooks/worktree-guard.sh` (L50, 55) — residual fix.
- `src/safety/pii_scanner.py` and/or `src/safety/pii_patterns.py` — residual fix.

**Tests**

- `tests/test_opponent_ladder.py` — new rung-(c) season cases; `_search_hit` (L90-102) gains the
  `season` key; the two negative-property tests re-audited (see §7).
- `tests/test_morning_run.py` — own-team `season_year` is recorded.
- `tests/test_cli_report.py` — `TestSearchOverride` docstring (L477-481).
- `tests/test_worktree_guard.py` — `HOME` slash variants.
- `tests/test_pii_scanner.py` — extensionless-file cases.

**Inbound prose — the complete inventory (§1). All MUST-FIX; none appears in a diff of the code.**

| # | Site | The stale claim |
|---|---|---|
| 1 | `src/gamechanger/opponent_ladder.py` ~L22-31 | module docstring, rung (c) bullet |
| 2 | `src/gamechanger/opponent_ladder.py:300-308` | "season-year filters are NOT implemented"; "Criterion 2 … still OPEN" |
| 3 | `src/cli/report.py:401` | `_apply_opponent_mapping` docstring, "no name or season corroboration" |
| 4 | `src/cli/report.py:520` | **`map-opponent` CLI help text** — operator-facing, "no name or season check" |
| 5 | `docs/api/flows/opponent-resolution.md:70-75` | "the gate is a single condition"; "no name check and no season check … the ENTIRE gate" |
| 6 | `docs/api/flows/opponent-resolution.md:80` | 🔶 OPEN criterion 2 → implemented |
| 7 | `docs/admin/operations.md:385` | operator-facing `[via search]` table row |
| 8 | `.claude/rules/data-model.md:83` | "the one method that auto-accepts with no name or season corroboration" |
| 9 | `.claude/rules/canonical-seams.md:35` | `is_team_hit` entry: "BEFORE its **unchanged** single-team uniqueness bar" |
| 10 | `tests/test_cli_report.py:478` | `TestSearchOverride` docstring |

**Deliberately NOT swept:** `.project/specs/done/*` (three files) and `.claude/agent-memory/*`.
Those are historical records of what was true when written, not live contracts — the
criterion-vs-evidence rule in `.project/specs/README.md`. Recorded so their absence reads as a
ruling, not an oversight.

## The work

Claims below were verified against the repo on 2026-08-09, not inherited. Line numbers are as of
that read — **audit them before trusting them**; a spec is a CLAIM.

### 1. Audit first

A spec is a claim. Before editing, re-walk the call chain and confirm it still reads:

`bb report morning-run` → `run_morning` → `_process_opponent` (`src/reports/morning_run.py:493`) →
`resolve_opponent` (`opponent_ladder.py:387`) → `_resolve_via_search` (`opponent_ladder.py:282`).

**⚠ The predecessor stub said the change was "a signature change plus a caller change in
`morning_run::_process_opponent`". That was wrong, and it is P1 #1 of the dogfood review that
produced this spec.** `morning_run` calls `resolve_opponent`, not `_resolve_via_search` — the season
year has to reach a private function two levels below the caller — and the change also strands **ten
live prose sites** that assert this filter is NOT implemented (table under Files, all MUST-FIX).
None appears in a diff of the code change. This is the
`feedback_moves_and_rewrites_owe_an_inbound_sweep` class.

**⚠ And the first draft of THIS spec claimed five sites, not ten** — the codex spec review found
four more, and a follow-up token-plus-synonym sweep found a fifth. An inbound inventory written
from the sites you happen to remember is itself an unverified claim. Before editing, re-run the
sweep rather than trusting the table: `.claude/rules/tool-discipline.md` requires token grep, then
synonym expansion (how would someone state this WITHOUT my search term?), then a read of each
touched section. The productive terms were `season corroboration`, `season check`, `or season`,
`criterion 2`, and — the one that found a site none of the others did — `uniqueness bar`.

### 2. Plumb the year — the ladder looks it up itself

`resolve_opponent` already holds `conn` and `our_team_id`. It reads `teams.season_year` for that team
and passes the value into `_resolve_via_search`.

**Why this and not a threaded parameter** (ruled 2026-08-08): no public signature changes, so the two
direct `resolve_opponent` callers in `tests/test_cli_report.py` (~L850-905) and `_process_opponent`
need no edit, and a future caller cannot forget to pass it. The alternative — an explicit
`member_season_year` parameter from `morning_run` — makes the dependency visible in the signature but
touches every caller and test. `.claude/rules/python-style.md` requires EVIDENCE parameters to be
REQUIRED precisely because an omitted one silently disables a guard; a value the function reads for
itself cannot be omitted at all, which satisfies the rule's intent more strongly than a required
parameter does.

### 3. Filter — fail-closed, on `year` only

In `_resolve_via_search`, drop hits whose `result.season.year` is absent, non-integer, or unequal to
the member year, **before** the existing single-team uniqueness bar and after the existing
`is_team_hit` organization drop. Ordering matters for the log lines: keep the existing
"all hits are non-team" WARNING reachable, and add a distinguishable DEBUG for
"N team hits, M dropped on season year".

Shape, verified against `docs/api/endpoints/post-search.md:174-175,203`: `season` is an **object**
`{name, year}` on this endpoint. It is NOT the public team profile's flat `team_season` shape, where
`season` is a bare string and `year` is a sibling integer. **Do not carry a parser between the two** —
`.claude/rules/testing.md` records `team_season.season.year` as a fabricated path that a mirrored
mock will happily validate.

Fail-closed on an absent year is cheap here: `post-search.md:199` re-verified 2026-07-25 that for
TEAM hits the `result` key set is closed and includes `season` (59 hits, 6 queries), and all 15 hits
in the repo's captured `/search` bodies carry a populated `season.year`.

**No `api-scout` consultation, and why** (the codex spec review flagged the omission; the rubric
accepts a stated reason). This section consumes an API field whose shape, presence rate, and
object-vs-flat trap are ALREADY documented in our own endpoint spec
(`docs/api/endpoints/post-search.md:174-175,199,203`) and re-measured against committed captures.
No endpoint is probed, no new field is discovered, no doc is authored — there is no API
archaeology to do, and CLAUDE.md principle D says not to delegate what a handful of tool calls
finishes. The out-of-scope section already forbids re-probing `POST /search`. **If execution finds
the documented shape does not hold** — a hit whose `season` is a bare string, a third shape — that
is archaeology: STOP and consult `api-scout` rather than widening the parser by inference.

### 4. Stop creating own-team rows with a NULL year

**Measured 2026-08-09 against the live dev DB:** 487 teams, **0 with NULL `season_year`** (2025: 55,
2026: 432). So no team is broken today. But `morning_run.py:662` calls `ensure_team_row(conn,
public_id=..., gc_uuid=..., source="morning_run")` with no `season_year`, and `ensure_team_row`
defaults it to `None` — so a team's **first-ever** morning-run row is created NULL, and under the
ruled fail-closed rule rung (c) would be silently dead for that team. This is a code-reachable hole,
not a data problem, and closing it is what makes fail-closed safe rather than surprising.

`run_morning` fetches the own-team public profile via `resolve_team(public_id)` (already imported at
`morning_run.py:50`) and passes `season_year=profile.year` (`TeamProfile.year`,
`src/gamechanger/team_resolver.py:47`) into `ensure_team_row`. `_backfill_season_year`
(`src/db/teams.py:338-354`) writes NULL→value only, so this also heals an existing NULL row and can
never clobber a stored year.

**Two costs, stated rather than hidden.** (a) It is one extra public GET per team per run:
`resolve_own_team_gc_uuid` already fetches this same profile internally
(`src/gamechanger/crawlers/opponents.py:205`) but returns only the `gc_uuid`, and widening its return
type would break ~10 tests in `tests/test_opponents_crawler.py` — the duplicate fetch is the cheaper
trade. Once per team per morning is not a tight loop, so `.claude/rules/http-discipline.md` is
satisfied, but do not replicate the pattern anywhere hotter. (b) A profile-fetch failure must
degrade to `None` and NOT abort the team (wrap it the way the opponent display-profile fetch at
`morning_run.py:517` is wrapped) — which under the ruled rule disables rung (c) for that team that
morning. That is the accepted fail-closed consequence; log it at WARNING so it is not invisible.

### 5. Residual — worktree guard `CLAUDE_HOME` normalization

`.claude/hooks/worktree-guard.sh` normalizes `FILE_PATH` (L31, `tr -s '/'`) and `REPO` (L44-45,
`tr -s '/'` + `${REPO%/}`), but `CLAUDE_HOME` (L50) gets neither. So `HOME=/home/vscode/` builds the
case arm `/home/vscode//.claude/*` (L55), which cannot match the slash-collapsed `FILE_PATH`, and the
guard DENIES a legitimate `~/.claude/` write. **It fails CLOSED — this is friction, not a hole.**

Mirror `REPO`'s treatment. Note it is ~3 lines, not the ~2 the residual estimated, because the empty
case needs handling too — and it must diverge from `REPO` there: `REPO` empty DENIES (L49, an
unusable project root is our misconfiguration), but `CLAUDE_HOME` empty should fall back to the
literal `/home/vscode` default, because `HOME=/` is not our misconfiguration and denying would kill
every memory write. Say so in a comment; the divergence will otherwise read as an oversight.
`tests/test_worktree_guard.py` already parameterizes `HOME` (L50), so the new cases have a home.

### 6. Residual — PII scanner skips extensionless files

`is_scannable` (`src/safety/pii_scanner.py:82-97`) returns the suffix test, and for a name that does
not start with `.` it returns `False` outright. Exactly two tracked files are affected:
`.githooks/pre-commit` (itself a PII gate) and `Dockerfile` (which the security checklist's §4h asks
reviewers to check). Neither is caught by `should_skip_path` — the `.git/` prefix does not match
`.githooks/` under `startswith`.

Fix by naming known extensionless basenames as scannable, alongside `SCANNABLE_EXTENSIONS`
(`src/safety/pii_patterns.py:108`).

**Two things to record in code comments, both learned while writing this spec.** (a) The shebang
variant the residual suggested does not work: `_scannability_skip_reason` runs BEFORE the content
read on both paths, and the `--staged` path reads its blob via `git show :<path>` *after* the gate —
so a shebang test would need the very read it gates. `Dockerfile` has no shebang either. (b) The
allowlist's known limitation: a NEW extensionless file stays unscanned until someone adds it. That is
a real residual of this fix, not a solved problem — carry it to `README.md` STANDING RESIDUALS at
step 9.

This is a security control (`.claude/rules/pii-safety.md`): it STRENGTHENS coverage, never weakens a
pattern or widens a skip list. `tests/test_pii_scanner.py:867-875`'s `_prior_inline_decision` helper
composes from `is_scannable` itself, so it tracks the change rather than breaking — which also means
it cannot detect this change. Add direct `is_scannable` cases instead.

### 7. Tests — the fixture does not carry `season`, and one test will pass for the wrong reason

**Verified 2026-08-09:** `_search_hit` (`tests/test_opponent_ladder.py:90-102`) builds a team hit with
`name`, `public_id`, `id`, `number_of_players`, `staff` — and **no `season` key at all**. That is
already a `test-validates-spec` defect (`.claude/rules/testing.md`): `post-search.md:199` records
`season` as part of the closed key set for team hits, so the fixture does not match the authoritative
shape. It becomes load-bearing here.

Add `season: {"name": ..., "year": ...}` to `_search_hit` with the year parameterizable, and set
`season_year` on the `_OUR_TEAM_ID` team row fixture. Then work the two directions separately,
because they fail differently:

- **The positive tests fail LOUDLY** — e.g. the auto-accept at L302 gets no season, is dropped, and
  the assertion breaks. That is the good case: caught, fixed by giving the fixture a matching year.
- **`test_search_two_teams_plus_organization_is_still_ambiguous` (L474-481) keeps PASSING, for the
  wrong reason.** Its docstring says "The team-side uniqueness bar is UNCHANGED"; after this change
  both team hits are dropped on season, so the result is `None` because of the *new* filter, not
  because of ambiguity. The test would certify a property it no longer exercises.
  `test_search_single_organization_hit_does_not_resolve` (L416-425, "the case the uniqueness bar
  cannot catch") needs the same look.

This is precisely the class `.claude/rules/testing.md` names: *"When a change makes an input
load-bearing, go re-read the tests asserting it is NOT… they never fail; they quietly stop meaning
anything. The searchable tell is the test NAME asserting a negative property."* Give both tests a
season year that MATCHES, so ambiguity stays the only reason they return `None`, and re-read every
other `_search_hit` call site for the same trap. **Do not settle for a green suite here** — green is
the failure mode.

## Out of scope

- **`pii_scanner.py --staged` ACMR rename-blindness** (`src/safety/pii_scanner.py:320`) — its own
  queued chunk with its own `/security-review`. Do not touch it here even though it is in the same
  function's neighbourhood.
- **A `season` column on `opponent_links`.** The predecessor stub listed this as genuinely open. The
  ruled semantics compare against `teams.season_year` at resolution time, so nothing durable is
  needed. Considered and not needed — not forgotten.
- **`season.name` matching.** Explicitly excluded by the ruling: same-year cross-season is
  legitimate.
- **Re-probing `POST /search`** to re-establish that `season.year` exists. Measured; the bar was the
  semantics decision, and it is ruled.
- **Backfilling `teams.season_year` for existing rows** as a migration. `_backfill_season_year` heals
  a NULL on next touch, and 0 of 487 rows are NULL today.

## Verification

**Every numbered item below carries a literal runnable command in a fenced block.** Anything that is
not a command is outside the numbered list and labelled as such. (The predecessor stub's block mixed
one command with three prose bullets that read as verification but were acceptance criteria — that
was P1 #2 of the dogfood review. The first draft of THIS spec half-fixed it and the codex review
caught the remainder.) Tools confirmed present 2026-08-09: pytest 9.0.3, ruff 0.15.20,
Python 3.13.13.

**Never pipe pytest** — the pipe's exit code is reported, not pytest's
(`.claude/rules/tool-discipline.md`). Redirect, capture `$?` separately, and READ the file for both
the RC and the pass/fail line.

1. **Test-scope discovery** — find every test importing a module you changed, per
   `.claude/rules/testing.md`. False positives are harmless; false negatives are the risk.
   **`--include="*.py"` is load-bearing**: without it the walk matches `tests/__pycache__/*.pyc` and
   returns 13 paths instead of 6, tripping the "more than 10 files" branch on noise. (The codex spec
   review caught exactly that on the first draft.)
   ```
   grep -rl --include="*.py" "gamechanger.opponent_ladder\|reports.morning_run\|safety.pii_scanner\|safety.pii_patterns" tests/
   ```
   *Expected 2026-08-09 (6 files):* `test_cli_report.py`, `test_morning_run.py`,
   `test_opponent_ladder.py`, `test_orphan_reclamation.py`, `test_pii_scanner.py`,
   `test_report_generator.py`. A different list is not an error — run what it returns. If it exceeds
   10 files, skip step 2 and run the full suite only.

2. **Targeted suite** — the files discovered above, plus the two the grep cannot find (the guard is
   a shell script; `test_opponents_crawler.py` covers `resolve_own_team_gc_uuid`, which §4 reasons
   about):
   ```
   python -m pytest tests/test_cli_report.py tests/test_morning_run.py \
     tests/test_opponent_ladder.py tests/test_orphan_reclamation.py \
     tests/test_pii_scanner.py tests/test_report_generator.py \
     tests/test_opponents_crawler.py tests/test_worktree_guard.py \
     > /tmp/bb-verify-targeted.txt 2>&1; echo "RC=$?" >> /tmp/bb-verify-targeted.txt
   ```
   *Expected:* `RC=0` and a `N passed` line. Read the file.

3. **Full suite** — mandatory; this chunk touches `src/` and `tests/`. No green, no done.
   ```
   python -m pytest tests/ > /tmp/bb-verify-full.txt 2>&1; echo "RC=$?" >> /tmp/bb-verify-full.txt
   ```
   *Expected:* `RC=0`. Read the file.

4. **Lint**
   ```
   ruff check src/ tests/; echo "RC=$?"
   ```
   *Expected:* `All checks passed!` and `RC=0`.

5. **PII scanner positive control — extensionless files (principle G).** Prove the instrument can
   FAIL before trusting its pass. Uses `/tmp` targets so nothing in the repo is mutated; the
   allowlist matches on basename, so these exercise the real gate. `/tmp/...` is not under any
   `SKIP_PATHS` prefix.
   ```
   CTL=abcdefghijklmnopqrstuvwxyz012345
   printf 'ENV GC_ACCESS_TOKEN=%s\n' "$CTL" > /tmp/Dockerfile
   printf '#!/bin/sh\nGC_REFRESH_TOKEN=%s\n' "$CTL" > /tmp/pre-commit
   python3 src/safety/pii_scanner.py /tmp/Dockerfile /tmp/pre-commit; echo "RC=$?"
   ```
   *Expected AFTER the fix:* `RC=1` with an `api_key_assignment` violation reported for BOTH files.
   *Expected BEFORE the fix (run it first, to prove the control discriminates):* `RC=0`, silent —
   that silence is the defect. Neither file may contain `synthetic-test-data` in its first 5 lines
   (the file-level suppressor) or a `pii-ok` marker.
   ⚠ **The indirection through `$CTL` is deliberate, not style.** Writing the fake token inline as
   `GC_ACCESS_TOKEN=abcdef…` makes THIS SPEC FILE match `api_key_assignment` — `.project/specs/` is
   scanned, so the spec would block its own commit. Verified both ways 2026-08-09: as written the
   spec scans clean, and the files it generates still carry the pattern. This is remedy #1 of
   `.claude/rules/pii-safety.md`'s choice hierarchy (change the data), not a `pii-ok` suppression —
   a standing suppressor here would sit in a file about credential scanning, the worst place for one.
   Per `.claude/rules/pii-safety.md`'s reviewer gotcha, an editable install can shadow the worktree
   module — run from the repo root and confirm you are exercising the worktree's `pii_patterns.py`.
   Clean up: `rm -f /tmp/Dockerfile /tmp/pre-commit`.

6. **PII scanner negative control** — the real tracked files must scan CLEAN once reachable.
   ```
   python3 src/safety/pii_scanner.py Dockerfile .githooks/pre-commit; echo "RC=$?"
   ```
   *Expected:* `RC=0`. Both were scanned by hand with a positive control at Step 2 (2026-08-08) and
   were clean; this is the first automated pass. A violation here is a real finding, not a test
   artifact — read it before triaging.

7. **Worktree guard** — the fix targets a path the suite can drive; assert all four `HOME` forms.
   ```
   python -m pytest tests/test_worktree_guard.py -v > /tmp/bb-verify-guard.txt 2>&1; echo "RC=$?" >> /tmp/bb-verify-guard.txt
   ```
   *Expected:* `RC=0`, with passing cases for `HOME=/home/vscode`, `/home/vscode/`, `//home/vscode`,
   and `HOME=/`. The first three must ALLOW a `$HOME/.claude/...` write; confirm at least one of them
   FAILS against the unfixed script, or the test proves nothing.

### Two things that are NOT commands, recorded so their absence reads as a decision

These are deliberately outside the numbered list above, which is commands only.

- **Ladder behavior has no CLI-level check.** The acceptance criteria below are covered by
  `tests/test_opponent_ladder.py`, which step 2 runs. Rung (c) is reachable only through a live
  authenticated `POST /search`, and `.claude/rules/testing.md` forbids real HTTP in tests, so there
  is nothing to run by hand.
- **`bb report reconcile-scoreboard` is NOT required.** CLAUDE.md's north star scopes it to
  *ingestion* changes; this chunk changes opponent RESOLUTION and touches no play-ingestion path.

### Acceptance criteria

Behavior that must be true — distinct from the commands above, which prove it.

- A single team hit whose `season.year` **equals** the member team's `teams.season_year`
  auto-accepts (method `search`), exactly as today.
- A single team hit whose `season.year` **differs** is dropped; the ladder falls to rung (d) and
  persists a pending row. Not a hard failure.
- A single team hit whose `season` key is **absent**, or whose `season.year` is absent or
  non-integer, is dropped (fail-closed). It must NOT be silently treated as matching.
- Two team hits where only ONE matches the member year now auto-accept on that one — the season
  filter narrows the population the uniqueness bar counts, the same way the organization drop does.
  **State both sides in the docstring: like the entity-class filter, this both narrows and widens
  the accept surface**, and that is the deliberate trade, not a no-op.
- A member team whose `teams.season_year` is NULL auto-accepts NOTHING at rung (c); every opponent
  goes to the operator queue, with a WARNING naming the team.
- `run_morning` records the own team's `season_year` on `ensure_team_row`, and a failed profile
  fetch degrades to `None` without aborting that team's run.
- Fixtures carry the real endpoint shape — `season` as an object `{name, year}`, never the public
  profile's flat `team_season`. A mock mirroring a fabricated path passes vacuously.

### Review (step 5) — the review-automation experiment, addressed to the EXECUTION session

This chunk carries a standing experiment that has now been deferred twice (owed at Migration Step 2,
carried at Step 3 rather than silently dropped). **Do not drop it a third time.** At step 5, in
addition to the normal `/code-review` (operator-typed) and `/security-review` (required — this
touches a PII gate, a write guard, and auto-accept safety):

- **(a)** Test whether `claude -p "/code-review"` runs headless from Bash. Record the exact command,
  the exit code, and whether real findings came back or it silently no-op'd.
- **(b)** Run BOTH the `codex-review` skill AND first-party `codex review --uncommitted` against the
  same staged diff. Record which findings each catches — overlap, and what only one of them found.

Write the verdict in the progress log below. That comparison decides the `codex-review` skill's fate
at Migration Step 4. A null result ("both found the same three things") is a finding worth recording;
an unrun experiment is not.

### Step 6 (SCAN) note

`.claude/` is in `SKIP_PATHS`, and the scanner returns a silent `RC=0` there even for explicitly
passed files (verified 2026-08-06). So the `worktree-guard.sh` edit gets **no** automatic PII
coverage: give it a by-hand pass with a positive control, and treat its silence as vacuous, not
clean. Compare scanned-count to staged-count as CLAUDE.md step 6 requires.

## Progress log

- **2026-08-05** — Stubbed. No code, no doc edit. Split from the drift spec after a codex spec review
  refuted the "data unavailable" premise; measurements re-taken directly against the capture and
  fixtures rather than inherited from the review. Measured then, and carried forward here: 15/15 hits
  in `proxy/data/sessions/2026-03-11_032625/endpoint-log.jsonl` carry a populated `result.season.year`
  (values 2026 and 2025), and one captured query returned a `{"name": "summer", "year": 2025}` hit in
  the same result set as `spring 2026` hits — so the filter discriminates something real. ⚠ Sample
  bound, stated so this is not over-read: 15 hits from one query family (a single youth-travel club,
  2026-03-11). Enough to refute "never observed"; **not** a census, and no evidence about how often a
  stale-season hit is the ONLY hit — which is the case that actually matters, and which nothing here
  measures.
- **2026-08-08** — Operator ruled BUILD, semantics settled (never cross-YEAR; same-year cross-season
  fine; absent year refuses; compare against `teams.season_year`).
- **2026-08-09** — Stub rewritten as an executable spec (lifecycle steps 1-2; no code written).
  Fixed the two dogfood P1s: the scope claim (the real chain is `_process_opponent` →
  `resolve_opponent` → `_resolve_via_search`, plus five stale prose sites — **an undercount, see the
  next entry**) and the non-executable verification block (acceptance criteria split out). Three
  decisions ruled by the operator this session: the ladder reads `teams.season_year` itself rather
  than taking a threaded parameter; morning-run fills the own-team year AND rung (c) still refuses if
  it is missing; the PII scanner fix is a named-basename allowlist. New measurements taken directly:
  0 of 487 live dev-DB teams have a NULL `season_year`, but `morning_run.py:662` creates rows without
  one. Two residuals folded in from `README.md` (worktree-guard `CLAUDE_HOME`, extensionless PII
  scannability); the `--staged` ACMR residual deliberately left to its own chunk.
- **2026-08-09** — `./scripts/codex-spec-review.sh` run (result file read in full, not the preview).
  Three findings, **all three real, all folded in**; each verified against the repo before folding
  rather than taken at face value.
  - *P1, incomplete inbound sweep.* Upheld. It named four sites the draft missed
    (`docs/admin/operations.md:385`, `.claude/rules/data-model.md:83`, `tests/test_cli_report.py:478`,
    and a SECOND site in `src/cli/report.py` at :520 — the operator-facing CLI help text). A
    follow-up synonym sweep of my own found a fifth (`docs/api/flows/opponent-resolution.md:70-75`,
    which uses none of the obvious terms). Five → ten; the table under Files is now the inventory,
    and §1 says to re-run the sweep rather than trust it.
  - *P2, verification block still partly prose.* Upheld, and sharper than stated: the discovery
    command matched `tests/__pycache__/*.pyc` and returned 13 paths, which by the spec's own rule
    would have skipped the targeted run. Fixed with `--include="*.py"` (6 files) — and the corrected
    command surfaced two test files the hand-written step-2 list had missed. Items 8-9 moved out of
    the numbered list into a clearly-labelled non-command note.
  - *P2, no `api-scout` consultation recorded.* Upheld as a documentation gap, not a process one:
    the reason for skipping is now stated in §3, with a trigger to consult if the documented shape
    does not hold at execution.
  - **Found by neither the review nor the draft, while verifying the P1:** `_search_hit`
    (`tests/test_opponent_ladder.py:90-102`) carries no `season` key, so
    `test_search_two_teams_plus_organization_is_still_ambiguous` would keep PASSING after this
    change while no longer testing ambiguity. New §7 covers it. Codex verified the two residuals by
    construction (it executed the guard against all four `HOME` forms and confirmed the scanner's
    `RC=0` silence on extensionless files), which is stronger evidence than the spec's own claim.
- **2026-08-09 (EXECUTION session)** — Implemented. Lifecycle steps 3-4 complete.

  **Step 3 audit — the spec held, with one correction to its own inventory.** Re-walked the call
  chain: `run_morning` → `_process_opponent` → `resolve_opponent` → `_resolve_via_search`, confirmed
  unchanged. Re-verified every load-bearing claim against the repo rather than inheriting it:
  `_search_hit` (`tests/test_opponent_ladder.py`) carries no `season` key; the `db` fixture seeds the
  own-team row with no `season_year`; `worktree-guard.sh` normalizes `REPO` but not `CLAUDE_HOME`;
  `is_scannable` returns `False` outright for an extensionless name; `morning_run.py:662` calls
  `ensure_team_row` with no `season_year`; `TeamProfile.year` and `_backfill_season_year`
  (NULL→value only) are as described.

  ⚠ **The ten-site table was an UNDERCOUNT — again, and §1 was right to say so.** Re-running the
  token-plus-synonym sweep (the productive new terms were `single team hit`, `ENTIRE gate`,
  `unambiguous single`, `auto-accept`) found **five more live sites**, all fixed:
  `docs/api/flows/opponent-resolution.md:83` ("Because the count is the whole gate"), `:148-150`
  (the null-progenitor fallback list), `:176` (the resolution-method table), `:103` (criterion 3's
  restatement), `src/gamechanger/opponent_ladder.py:510` (the rung-(c) inline comment), and
  `docs/ROADMAP.md:423` ("auto-ingest only on an unambiguous single match"). **Ten became fifteen.**
  This is the third consecutive count for this one inventory (5 → 10 → 15); the lesson is not "count
  more carefully" but that an inbound inventory is never evidence — only a re-run sweep is. Also
  refreshed the flow doc's `Last updated` header.

  **Deviation from the Files table, stated rather than hidden:** `docs/api/**` is api-scout's tree
  (`.claude/rules/documentation.md`). These edits were made directly, not routed, because they state
  OUR implementation status, not endpoint facts — no request param, response shape, field
  description or observed capability was touched. That is the fidelity split the rule draws; flagging
  it so the choice reads as a decision.

  **Implementation.** `_resolve_via_search` takes a REQUIRED `member_season_year`; `resolve_opponent`
  reads `teams.season_year` itself via `_read_member_season_year` (no public signature change, so no
  caller can forget it). New `_hit_season_year` parses `result.season.year` from the OBJECT shape,
  returning `None` for every non-integer form — `bool` excluded explicitly, since `True == 1` would
  otherwise compare as a year. Filter sits after the organization drop and before the uniqueness bar,
  keeping the "all hits are non-team" WARNING reachable. `run_morning` fetches the own-team profile
  and passes `season_year=profile.year`, degrading to `None` with a WARNING on failure rather than
  aborting the team. Both residuals fixed.

  **Verification — every command run, none piped.** Test-scope discovery returned the expected 6
  files. Targeted suite `RC=0`, **607 passed**. Full suite `RC=0`, **4454 passed** (`/tmp/bb-verify-full.txt`).
  `ruff check src/ tests/` → `All checks passed!`, `RC=0`.

  **Positive controls, both run BEFORE and AFTER (principle G).** Neither is a bare pass.
  - *PII extensionless (item 5)*: against the reverted pre-fix modules the control was **`RC=0` and
    silent** — the defect. After: **`RC=1`** with an `api_key_assignment` violation on BOTH
    `/tmp/Dockerfile` and `/tmp/pre-commit`. The revert was asserted applied before measuring, and
    `__pycache__` cleared on both sides. Item 6 negative control: the real tracked `Dockerfile` and
    `.githooks/pre-commit` now report `Scanned 2 file(s), 0 violations` — the count line is what
    makes that clean non-vacuous.
  - *Worktree guard (item 7)*: against the unfixed script **4 of the new cases FAIL** (three slash
    variants plus the `HOME=/` fallback); all 31 pass after. The four `HOME` forms are covered.
  - *Season filter*: ran a real mutation (fail-OPEN on a missing year — the plausible future edit,
    not vandalism), mutation asserted applied, `__pycache__` cleared, control run first. **6 of 6
    fail-closed parametrized cases FAIL under the mutant**, 49 pass; restored clean at 55.
    Per-test outcomes, not an aggregate.

  **One instrument misreported and was caught by cross-check.** The `grep -c` used to confirm the
  guard file was restored after `git stash pop` returned `0` in BOTH directions — i.e. it proved
  nothing either way. Resolved by reading the file and `git stash list` directly (restored correctly,
  stash empty). The discrimination evidence is the test outcomes above, not that grep. Recording it
  because a self-confirming instrument that reads `0` twice is exactly the shape that gets believed
  once.

  **Documentation assessment**: triggers fired (behavior change + rule change). Updated
  `docs/api/flows/opponent-resolution.md`, `docs/admin/operations.md`, `docs/ROADMAP.md`,
  `.claude/rules/data-model.md`, `.claude/rules/canonical-seams.md`.

- **2026-08-09 — the review-automation experiment (owed since Migration Step 2; RUN, not deferred
  a third time).** All three tools were pointed at the SAME working-tree diff.

  **(a) `claude -p "/code-review"` runs headless from Bash. It works.** Exact command:
  `timeout 900 claude -p "/code-review"` from the repo root. **Exit code 0**, ~15 min, and it
  returned FOUR real findings — not a silent no-op. It also independently re-ran the full suite and
  re-verified the `season` object shape against `post-search.md` before reporting. Caveat worth
  recording: it reviews the WORKING TREE, so it must be run after the edits and before/independent
  of staging; and it is a fresh session with no chunk context, which is a feature here.

  **(b) The two Codex paths found DISJOINT findings. That is the headline.** Three tools, eight
  findings, **zero overlap** — not one finding was reported by two tools. A null result was the
  expected outcome and this is emphatically not one.
  - `./scripts/codex-review.sh uncommitted` (the SKILL, rubric + checklists injected) — **P1:** the
    season fill warned only on the EXCEPTION path, so a successful `resolve_team` returning
    `TeamProfile(year=None)` — a documented shape, `int | None` — wrote NULL and said nothing,
    silently disabling rung (c). It verified the counterexample by construction rather than
    asserting it. **P2:** the new tests covered only "fetch raises", never "fetch succeeds with
    year=None", which is why the P1 stayed green.
  - `codex review --uncommitted` (FIRST-PARTY, no custom instructions) — **P2:** the terminality
    gate short-circuits pre-existing `resolution_method='search'` rows, so a pre-patch cross-year
    auto-match survives this change until an operator remaps it. **P3:** `profile.year` is written
    to `teams.season_year` unvalidated; a quoted year would persist, and since the read side fails
    closed AND `_backfill_season_year` never overwrites a non-NULL, one malformed response would
    wedge rung (c) OFF for that team permanently.
  - `claude -p "/code-review"` — the stale-stored-year asymmetry (the generator force-updates the
    same column via `COALESCE(?, season_year)`, morning-run cannot), plus three
    logging/message-accuracy findings: no WARNING when the season filter drops EVERY hit, a
    NULL-year WARNING that claimed a refusal on zero-hit opponents where nothing was refused, and a
    failure message asserting "season_year stays unset / rung (c) disabled" which is false whenever
    a year is already stored.

  **Verdict on the `codex-review` skill's fate (the question this comparison was to decide):
  KEEP BOTH — they are not substitutes.** The evidence is the disjointness, and the two paths failed
  in *characteristic* directions rather than randomly. The rubric-injected skill found the
  project-shaped defect (a fail-closed guard going silent — the `.claude/rules/python-style.md`
  "missing safety signal" class the rubric names). The first-party path, carrying no instructions,
  found the two defects a rubric would not prompt for: durable-state poisoning and the migration
  question about already-cached rows. Dropping either would have lost real P1/P2/P3 findings on this
  very diff. `claude -p` is additive again — it was the only one to catch prose asserting
  consequences that do not hold, which is the `feedback_prose_is_a_claim_you_must_walk` class.
  ⚠ Bound on this result, stated so it is not over-read: **one diff, one chunk**. It refutes "these
  tools are redundant"; it is not a measured overlap RATE, and a single chunk cannot supply one.

  **All findings triaged and FIXED except one, which is a scope decision (see below):** the
  `year=None` silence, the missing test, the malformed-year poisoning, the all-hits-dropped WARNING,
  and both misleading messages are all fixed with tests. Full suite re-run after the fixes:
  **RC=0, 4460 passed**; `ruff` clean; both PII controls re-run and still correct.

  **NOT fixed, deliberately — two carried to the operator as decisions, not silently dropped:**
  (1) *Stale own-team `season_year`.* Morning-run cannot refresh a stored year, so a stale one now
  silently drops every rung-(c) hit. Force-updating it (as `generator.py` does) would move
  `derive_season_id_for_team` and the `season_id` games are filed under — real blast radius, well
  outside this chunk. Mitigated by DETECTION instead: the new all-hits-dropped WARNING is exactly
  the symptom a stale year produces, and it names the suspicion.
  (2) *Pre-existing cached `search` rows never see the new filter.* Correct as described; the
  terminality gate is unchanged by design and `bb report map-opponent` is the recovery path. Whether
  to invalidate them is an operator call with data consequences, not an implementer's.

- **2026-08-09 — operator-typed `/code-review` (step 5).** Three findings, **all three real**, each
  verified against the repo before acting. It brings the tool count on this diff to FOUR and the
  finding count to eleven, still with essentially no overlap.
  - *MEDIUM — `is_scannable` skipped every dotfile carrying a SECOND suffix.* **Upheld, and it
    found a hole my own fix had walked past.** The dotfile branch sat BELOW the suffix test, so it
    was reachable only when `Path.suffix` was empty — and for the repo's TRACKED env templates it is
    not. Verified by execution: both tracked templates returned `False`. Worse, the comment on that
    branch named the `.local` variant as handled; it never was. That is the
    `feedback_prose_is_a_claim_you_must_walk` class sitting inside the very function this chunk
    edits. **Fixed** by testing dotfiles FIRST — whole name, then leading dotted component, then
    **falling through** to the ordinary suffix test. The fall-through is load-bearing and has its own
    test: a `return` there would have made `.eslintrc.json` unscannable, NARROWING a security
    control while ostensibly widening it.
  - *MEDIUM — own-team `season_year` is write-once.* **Upheld, and it REFUTES a premise I wrote
    into this log and into a test docstring.** I had claimed `generator.py:1839`'s force-update
    mitigates a stale year. It does not reach this row: in morning-run `generate_fn` is called with
    the OPPONENT's `public_id`, so that UPDATE always targets the opponent's team id, never the
    member's. **Nothing refreshes a member team's `season_year`.** So a team first seen in spring
    2026 is pinned at 2026; in 2027 every hit carries 2027, every hit drops, and rung (c)
    auto-accepts nothing for that team ever again, with no self-heal short of a hand-edited row.
    The reviewer also noted `--dry-run` writes and commits this value. Corrected everywhere I had
    asserted otherwise; NOT fixed in code (see the open decision below).
  - *LOW — the all-hits-dropped WARNING misdiagnosed an API shape change as a year mismatch.*
    Upheld. `_hit_season_year` fails closed to `None` for a renamed or dropped `season` key exactly
    as it does for a different year, so the message pointed the operator at their own DB row for a
    fault that would be upstream — in precisely the class-wide case the warning exists to catch.
    **Fixed**: unparseable hits are counted separately and the all-unparseable case emits a distinct
    "API SHAPE problem … NOT the member team's season_year" message. Two tests.

  **Discovered while fixing the first finding, and NOT fixed here on purpose.** Making the env
  templates reachable surfaced three pre-existing `email` matches in `.env.example`: our own
  `noreply@` service address and two `USER:PASS@host` proxy-URL FORMAT comments. **No credential and
  no person's address** — read and confirmed. Left alone because the remedy is a suppressor inside a
  credential TEMPLATE, which is the exact placement `.claude/rules/pii-safety.md` warns against, and
  that is the operator's call. The consequence to know: staging `.env.example` will now trip the
  hook until it is addressed. The negative-control test was accordingly narrowed to the property
  this chunk owns — no CREDENTIAL findings — rather than pinning blanket cleanliness of a file the
  chunk does not control.

  Re-verified after all fixes: full suite **RC=0, 4471 passed**; `ruff` clean; extensionless
  positive control `RC=1`, env-template positive control `RC=1`, negative control `RC=0` with
  `Scanned 2 file(s)`.

- **2026-08-09 — operator-typed `/security-review` (step 5, second gate).** **No findings at or
  above threshold; no HIGH or MEDIUM vulnerability introduced.**

  ⚠ **The harness handed the review the WRONG DIFF, and that is worth recording as a process
  finding.** Its `DIFF CONTENT` was the COMMITTED range (`@{upstream}...HEAD`) — docs and specs
  only — while `GIT STATUS` correctly showed the uncommitted working tree. Since findings in
  markdown are an excluded category, reviewing what was supplied would have returned a **vacuous
  clean** on a chunk that modifies two security controls. The review was re-scoped by hand to
  `git diff -- .claude/hooks/worktree-guard.sh src/ tests/`. Anyone running `/security-review`
  against uncommitted work should check the scope before trusting the verdict.

  Because both modified controls could regress SILENTLY, each was settled by proof plus a positive
  control rather than by inspection (principle G):
  - *`is_scannable` cannot NARROW coverage.* The new dotfile block contains no terminal
    `return False` — it returns True or falls through to the byte-identical suffix test — and the
    final `SCANNABLE_BASENAMES` line replaces the old `return False` on a strictly narrower
    reachable set. So it can only turn False into True. Measured: 36,932 synthetic paths → **0
    narrowings, 2,205 widenings**; 2,485 tracked real files → **0 narrowings, 4 widenings**.
    Control: the same function with the early `return False` the comment warns about → **1,680
    narrowings**, so the harness demonstrably fails when it should.
  - *The guard cannot WIDEN the allowed write set.* The arm is `"$CLAUDE_HOME"/.claude/*`, not
    `"$CLAUDE_HOME"/*` — even at the empty limit it requires a literal `.claude` segment, which is
    precisely what makes the deliberate divergence from `REPO`'s deny-on-empty safe. 15 paths × 13
    `HOME` variants: the only deltas are ALLOWs on the intended tree. Control: a mutant with the arm
    loosened to `"$CLAUDE_HOME"/*` allows `/etc/passwd` at `HOME=/`.

- **2026-08-09 — operator rulings on the three carried items. All three DECIDED; none left open.**
  1. **Season rollover: detection-only ACCEPTED for this chunk; do NOT build the force-update.** The
     likely real answer is OPERATIONAL — under single-season doctrine a new season starts with a
     reset + re-scout, which recreates the rows with the new year, so the pinned value never
     survives to matter. Derive-at-read is the fallback DESIGN if that premise proves wrong; the
     force-update stays declined either way because it moves `season_id`. Recorded as a stub with
     the premise written down to be CHECKED, not assumed:
     `.project/specs/2026-08-09-member-season-year-rollover.md` (`PARKED`, revisit near spring 2027).
  2. **Pre-existing cached `search` rows: LEAVE them.** Correctable via `bb report map-opponent`,
     and they die at the next data reset regardless. No invalidation, no migration.
  3. **`.env.example`: LEAVE it, no suppressor.** The three `email` matches carry no credential and
     no person's address. If they ever block a real commit, reword the lines then — which keeps the
     remedy at `.claude/rules/pii-safety.md`'s preferred tier (change the data) instead of planting
     a standing suppressor inside a credential template.
