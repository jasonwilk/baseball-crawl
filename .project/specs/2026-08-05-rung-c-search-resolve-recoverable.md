# Make a search-resolved opponent correctable, and correct the flow doc

**Date:** 2026-08-05 · **Status:** **COMPLETE (this commit)** — `bb report map-opponent` now
overrides a wrong rung-(c) `search` resolution, and a corrected mapping regenerates rather than
hitting the idempotency skip. Resolves
`.project/specs/2026-08-04-rung-c-auto-accept-criteria-drift.md`.
Operator chose: fix recoverability **and** correct the doc; no confirmation gate on the override.
Full suite 4434 passed, RC=0. See the Progress log for the review findings and what they changed.

## Context

`docs/api/flows/opponent-resolution.md` documents three auto-accept conditions for opponent
resolution rung (c); `_resolve_via_search` implements one (exactly one team hit). Today's
entity-class filter (`b9bc37f`) narrowed that condition's population, widening the auto-accept
surface — so that single implemented condition is now the entire gate, and the absence of the other
two matters more than it did.

The eval (read-only, this session) confirmed every claim in the drift spec and found the thing that
decides the direction: **in code, a wrong auto-resolve has no supported correction path.**
`bb report map-opponent` gates on `resolution_method IS NULL` in both its SELECT and its UPDATE
(`src/cli/report.py:393`, `:402`), with no `--force`, so on a resolved row it exits 1 with
"No pending opponent." What remains is hand-written SQL or `bb db purge-scouting` (20 tables).

⚠ **Say "in code" and mean it** — the operator-facing runbook already promises the correction
(`operations.md:379`, codex P2). The gap is between the docs and the code, not an absence of
intent; see §3b.

⚰ **RETIRED by the codex spec review (2026-08-05) — the paragraph below was WRONG and is kept only
so the error is not silently reintroduced:** *"the two documented filters should not be built:
`post-search.md:168` says `result.name` typically includes the year … and `result.season.year` has
never been observed here (no proxy capture, no fixture, no reader in `src/`)."*

**What the repo actually shows** (measured this session against
`proxy/data/sessions/2026-03-11_032625/endpoint-log.jsonl`, the only real `POST /search` capture in
the repo — 15 hits across 2 queries):

- **`result.season.year` IS present and populated: 15/15 hits carry it** (values `2026` and `2025`),
  and `tests/fixtures/e2e/search_response.json` carries it too. "Never observed" was false. Only
  "no reader in `src/`" survives.
- **`result.name` carries NO year: 0/15.** So `post-search.md:168`'s *"typically includes year,
  e.g. 'Team Name 2026'"* is contradicted by the repo's own capture — **that is a defect in the
  endpoint doc, and it was my rationale for rejecting criterion 1.**

⚠ **Sample bound, stated so this is not over-read in the other direction:** those 15 hits are one
query family (a single youth-travel club, 2026-03-11). Strong against "typically includes year";
not a census of HS/Legion naming.

**What survives as a real objection to criterion 1** is different from what I originally wrote: the
stored name is scorekeeper free text off *our* schedule, and the captured canonical names vary in
word order and punctuation for the same club — `Northampton Nighthawks Navy 10U` vs
`Northampton Nighthawks 9U Navy` vs `Nighthawks (Navy) 13U(AAA)`. An exact match against free text
would miss on ordering and formatting, not on the year.

Live exposure is currently zero — `scheduled_report_runs` has 0 rows and no `search`-method link
exists — which makes this the cheap moment to fix it.

## Approach

**Widen the operator's correction tool, not the ladder's terminality gate.** The gate
(`opponent_ladder.py:391`) deliberately keys on `resolution_method IS NOT NULL` to avoid the
documented `no_presence` resurrection bug; leaving it untouched means that bug is structurally out
of reach of this change. Only `search` becomes overridable — the low-confidence method, and the
one this chunk widened.

### 1. `src/cli/report.py` — allow override of a `search` resolution

- `_apply_opponent_mapping`: eligibility becomes, in **both** the SELECT and the UPDATE (they must
  stay identical — the same predicate twice):

  ```sql
  WHERE root_team_id = ? AND (resolution_method IS NULL OR resolution_method = ?)
  ```

  🚨 **The parentheses are load-bearing — codex P1, demonstrated not argued.** `AND` binds tighter
  than `OR`, so the unparenthesized form parses as
  `(root_team_id = ? AND resolution_method IS NULL) OR (resolution_method = ?)` and matches **every
  `search` row in the table**, across every opponent. Executed against SQLite: the unparenthesized
  query returned a row belonging to a different `root_team_id`; the parenthesized one did not.
  **A test must pin this** — a second opponent's `search` row that must survive the UPDATE.
- Add `METHOD_SEARCH` to the existing import at `src/cli/report.py:18` (`METHOD_NO_PRESENCE`,
  `METHOD_OPERATOR` are already imported). Do **not** inline the literal `'search'` —
  `.claude/rules/data-model.md` requires the shared constants.
- Select `public_id, resolution_method` alongside `id` so the command can report **what it
  replaced**: an override must never be silent. Pending fills keep their current message.
- `progenitor`, `operator`, and `no_presence` rows stay untouchable — unchanged behavior,
  deliberate, and stated in the docstring.

⚠ **Two consequences found in self-review; neither blocks the approach, both must be stated:**

- **Blast radius widens.** The UPDATE keys on `root_team_id` ALONE (not the
  `(our_team_id, root_team_id)` table key), so it hits every one of our teams' links for that
  opponent — by design, per its docstring. Today that only ever rewrites *pending* rows; after this
  change one command can rewrite *already-resolved* sibling rows too. The reporting in the bullet
  above is what keeps that visible, so it is load-bearing, not cosmetic.
- **The fix buys exactly ONE correction.** An override writes `resolution_method = 'operator'`,
  which is not itself overridable — so a mistyped correction is permanent, with the same nuclear
  recovery as before. This is unchanged from today's behavior for operator mappings, but it does
  bound how much recoverability this chunk actually delivers. **Named sub-decision for the
  operator, deliberately NOT decided here:** leave `operator` immutable (narrow, matches today), or
  also allow re-correcting an `operator` row (a human overriding their own prior human call carries
  no automated-wrongness risk). `no_presence` stays immutable either way.

### 2. `src/gamechanger/opponent_ladder.py` — amend the prose that this makes false

`_resolve_via_search`'s docstring currently reads *"a wrong auto-resolve is never re-attempted and
never re-surfaces to the operator"* and cites the spec as an open question. After this change
"never re-attempted" is still true (the gate is untouched) but "never re-surfaces" is only half
true — it is now **correctable on demand**. Amend precisely; do not delete the warning, and keep
both sides of the trade stated. Same for the module docstring's rung (c) bullet (line ~25) and the
`.project/specs/...drift.md` citation, which now points at a resolved decision.

### 3. `docs/api/flows/opponent-resolution.md` — correct the drift

- Rewrite **"Auto-Accept Criteria"** (line 69) to state the implemented gate: exactly one **team**
  hit after organization filtering. The three criteria get **three different dispositions** — do not
  collapse them into one tombstone. Where a criterion IS retired, put the `⚰ RETIRED` marker
  **FIRST, before the quoted text** (`.claude/rules/doc-sweep.md` remedy (i)) so a future grep hit
  does not read as live. Reasons must be the corrected ones, not the retired ones above:
  - **Criterion 1 (name match): not implemented.** Canonical names vary in word order and
    punctuation against free-text schedule names, so exact matching would reject correct hits.
    NOT because they carry a year — 0/15 captured names do.
  - **Criterion 2 (season year): still OPEN, not retired.** The data exists (15/15). Point at
    `.project/specs/2026-08-05-rung-c-season-year-filter.md`. ⚠ Do **not** tombstone it as
    data-unavailable — that is the false claim this review retired.
- **Two POSITIONAL references break silently once the criteria list changes shape** — they name a
  position, not an object, which is the failure `.claude/rules/tool-output-integrity.md` warns
  about. They break under *any* of the three dispositions above, not only under a retirement:
  - line 90: *"auto-accept **criterion 3** (\"exactly one result\") can settle on an organization"*
  - line 94: *"The **three** auto-accept conditions in the section above assume every hit is a team."*

  Both must be de-positionalized (name the single-team-count gate directly), not renumbered.
  Renumbering just moves the same trap.
- Line 168 table row still reads "unambiguous single **name** match" — a site the previous sweep's
  wording missed. Make it "single **team** match".
- Document the new operator override: a `search` resolution can be corrected via
  `bb report map-opponent`; `progenitor` / `operator` / `no_presence` cannot.

### 3b. `docs/admin/operations.md` — the runbook already promises this (codex P2)

`operations.md:379` **already tells the operator**: *"If the mapping resolved to the wrong team, use
`bb report map-opponent` to correct it (the ladder's auto-resolution may have matched a name-alike
team)."* That instruction is false today — the command exits 1 on a resolved row. This is
independent corroboration that the fix restores *intended* behavior rather than inventing it, and
it makes the runbook a required site, not an optional one:

- Scope the promise to what will actually be true: `search` rows correctable,
  `progenitor` / `operator` / `no_presence` not.
- `operations.md:408` says a call "updates **all pending rows** for that `root_team_id`" — after
  this change it also updates `search` rows. Reconcile.
- **Operator-visibility gap (codex P2, second half):** the RESOLVED line the operator eyeballs
  (`src/cli/report.py:675`) does not print `resolution_method`, so they cannot tell whether a
  correction will be accepted before trying it. Add the method to that line — it is what makes the
  runbook instruction actionable rather than trial-and-error.

### 4. `.project/specs/2026-08-04-rung-c-auto-accept-criteria-drift.md`

Flip Status to COMPLETE and record: the direction chosen and why; that criterion 1 is rejected
(word-order/punctuation divergence) while **criterion 2 remains open** and moved to its own stub;
that the terminality gate was deliberately left alone; and that the spec review retired this
chunk's own false "season.year never observed" premise. Do not write it up as "both criteria
rejected" — that is the error this review caught.

### 5. Two spec stubs for work this chunk deliberately does not do

**Operator decision (2026-08-05): track the season-year filter separately; keep this chunk focused.**

- `.project/specs/2026-08-05-rung-c-season-year-filter.md` — the season-year match, marked
  **OPEN and viable, NOT retired**. Record: `result.season.year` is present 15/15 in the repo's only
  real capture; a `summer 2025` hit was returned beside `spring 2026` hits in one result set, which
  is exactly what the filter would discriminate. What is open: `_resolve_via_search` does not
  receive the member team's `season_year` (signature change), `opponent_links` has no season column,
  and which season to match is undecided. Not urgent — live exposure is zero.
- `.project/specs/2026-08-05-post-search-name-year-doc-defect.md` — `post-search.md:168` claims
  `result.name` *"typically includes year, e.g. 'Team Name 2026'"*; the repo's capture shows **0/15**.
  Correcting a factual API-behavior doc on a 15-hit single-family sample deserves a real probe, not
  an inline edit, so it is stubbed rather than fixed here.

## Housekeeping

This spec currently lives at the harness plan path only because plan mode confines edits to one
assigned file. **Move it to `.project/specs/2026-08-05-rung-c-search-resolve-recoverable.md`** as
the first act of execution; the generated "woolly-ladybug" name does not survive.

## Out of scope

- Implementing criterion 1 (rejected — word-order/punctuation divergence against free text).
- Implementing criterion 2 — **open, not rejected**; tracked in its own stub per §5.
- Any change to the ladder's terminality gate.
- Making `progenitor` / `operator` / `no_presence` overridable.
- `docs/ROADMAP.md:423` — describes rung (c) as "unambiguous single match", which matches the
  code; its stale "admin UI" reference is pre-existing E-239 residue, not this chunk's.

## Verification

- `python -m pytest tests/ > /tmp/out.txt 2>&1; echo "RC=$?" >> /tmp/out.txt`, then read the file.
  **Never pipe pytest.** Full suite green before commit.
- Targeted: `tests/test_cli_report.py` (the map-opponent home), `tests/test_opponent_ladder.py`;
  scope discovery via `grep -rl "opponent_ladder" tests/`.
- New tests in `tests/test_cli_report.py`:
  - `search`-resolved row IS overridden, and the command reports the replaced `public_id`.
  - 🚨 **A DIFFERENT opponent's `search` row is UNTOUCHED** — the codex-P1 precedence guard. Seed two
    `root_team_id`s, both with `search` rows, map one, assert the other still holds its original
    `public_id`. This is the test that fails if the parentheses are dropped.
  - **`no_presence` row is still REFUSED** — the resurrection-bug regression guard.
  - `progenitor` and `operator` rows still refused.
  - Pending (NULL) row still fills, unchanged.
  - The RESOLVED output line includes `resolution_method`.
- Pin that the ladder's terminality gate still short-circuits a `search` row (behavior unchanged by
  this chunk) in `tests/test_opponent_ladder.py`.
- Mutation-check the widened predicate per `.claude/rules/testing.md`: clear `__pycache__` around
  each run, assert the mutation applied, report **per-test** outcomes (never an aggregate count).
  Two plausible wrong edits, and they are caught by different tests — which is the point of
  reporting per-test:
  1. widening to `resolution_method IS NOT NULL` → resurrects `no_presence`; the `no_presence`
     test must fail.
  2. **dropping the parentheses** → cross-opponent bleed; the different-opponent test must fail.
- **This chunk contains code, so step 5 applies in full** (`/code-review`; `/simplify` optional and
  only BEFORE it). The docs-only "PII gates alone" shortcut does NOT apply — it is a property of
  the chunk, not of the individual files in it.

## Progress log

- **2026-08-05 — EXECUTED.** Spec moved here from the harness plan path (step 3's first act).

  **What shipped.** `bb report map-opponent` now accepts a `resolution_method = 'search'` row as
  well as a pending one, via the single `_MAPPABLE_ROW_PREDICATE` constant interpolated into BOTH
  the SELECT and the UPDATE (they cannot drift). It returns each updated row's PRIOR state so an
  override announces what it displaced. The ladder's terminality gate was NOT touched. The
  morning-run RESOLVED line and the operator summary line both now carry `[via <method>]`.

  **`/simplify`** — 4 fixes (shared `_team_seeded_conn()` test helper; the predicate constant;
  one report line per DISTINCT prior state with a count, instead of N identical lines; dropped a
  comment that restated the docstring). 2 skipped with reasons: the `(None, None)` return entry is
  the literal prior state of a pending row, not a sentinel needing a dataclass; and moving the SQL
  into `opponent_ladder.py` is pre-existing structure, outside this diff.

  ⚠ **An altitude finding was deliberately DECLINED, and the reasoning matters more than the
  verdict.** The reviewer wanted "which methods are overridable" hoisted into a shared constant,
  citing E-270's guard-surface==delete-surface precedent. Declined because the failure directions
  differ: E-270's drift failed OPEN (a guard waving through a delete); this one fails CLOSED (a
  new method simply is not overridable). A frozenset of one plus the dynamic `IN` clause it needs
  would complicate the very SQL whose parenthesization is the load-bearing subtlety. A pointer
  sits at the `METHOD_*` block instead — **stating both directions**, including that fail-closed
  is not harmless. If a second automatic method lands, hoist it then.

- **2026-08-05 — REVIEWED (`/code-review` + codex). 8 findings, all verified against the repo,
  all fixed.** The sharpest is worth carrying forward:

  ⚠ **The correction was INERT for the case it exists for, and nothing in the plan or either
  spec review caught it.** `_prior_success` (morning-run's idempotency skip) keyed only on
  `(own_team_id, opponent_root_team_id, game_date)` plus a non-expired report — never on WHICH
  team the report was for. So the full operator loop was: cron auto-resolves the wrong team and
  delivers a report → operator corrects the mapping → operator re-runs morning-run exactly as
  `docs/admin/operations.md` instructs → the skip fires on the OLD report → `skipped` → the coach
  keeps reading the wrong team's report until it expires. Fixed by comparing the slot's stored
  `resolved_public_id`; NULL-or-different regenerates, which is the safe direction (cost: one
  wasted regeneration; the other direction serves the wrong team). **The lesson is about REACH,
  not this predicate**: the chunk changed what a mapping MEANS, and the sweep stopped at the
  writers of `opponent_links` rather than reaching everything that DECIDES on it downstream.

  Also fixed: `[via <method>]` was missing from the summary email — the channel an unattended cron
  run actually reports through (the console line only covers `--dry-run`), so the feature's own
  justification did not hold where it mattered; the SELECT/UPDATE were not in one transaction
  (now `BEGIN IMMEDIATE`, with the UPDATE's rowcount asserted against the rows read so a
  divergence aborts loudly instead of printing a confident "Replaced…" over a write that did not
  happen — codex reproduced that race with two connections); a partial apply was silent when one
  opponent's rows are split by method (rung (a) resolves per-team, so Varsity can be `progenitor`
  while JV is `search`) — now a `Left unchanged` line; and `map-opponent --help` still described
  pending-only behavior, shipping doc/code drift on the command surface itself.

  **Operator decision (asked, and re-asked in plain terms after the first framing assumed too
  much context): NO confirmation gate.** Overwriting stays a single command that announces what
  it replaced afterwards. Recorded because it is a real trade, not an oversight: an override
  writes `operator`, which this command will not overwrite again, so a mistyped correction cannot
  be re-corrected here — the fallback is `bb report generate <public_id>` directly.

  **Verification.** Full suite **4434 passed, RC=0** (unpiped, written to a file and read back;
  up from 4419 at the start — 15 new tests). Every guard added this session was mutation-proved
  with `__pycache__` cleared around each run, the mutation asserted applied, and **per-test**
  outcomes recorded (never an aggregate):
  - parentheses dropped → ONLY `test_map_opponent_override_does_not_touch_a_different_opponent`
    fails (a bystander opponent's row was rewritten). Solely load-bearing for that finding.
  - predicate widened to `IS NOT NULL` → 3 fail, including `test_no_presence_row_is_still_refused`
    (the resurrection guard).
  - `_prior_success` reverted to the pre-fix predicate → `test_corrected_mapping_regenerates_
    instead_of_skipping` fails with "a corrected mapping must regenerate".
  - `[via ...]` tag removed → `test_summary_detail_line_carries_the_resolution_method` fails.
  - dedupe reverted to the naive loop → the two-team count test fails (`assert 2 == 1`).

  Source was restored from a scratchpad copy taken BEFORE each mutation — never from the index
  (`.claude/rules/worktree-isolation.md`).
