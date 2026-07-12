# E-256-05: Fix the rest-day reference date at all three UTC sites

## Epic
[E-256: Post-Descope Simplification & Foundations](epic.md)

## Status
`DONE`

## ⚠️ PM PRE-DISPATCH LINE-NUMBER CORRECTION (2026-07-09)
**Every `generator.py` line number in this story is STALE.** Story 04 moved 675 lines out of `generator.py` (3,031 → 2,356). The three UTC slice sites this story names as `:2378` / `:2411` / `:2431` are **now at `:2164`, `:2197`, `:2217`** — PM verified by grepping `generated_at[:10]`, which returns exactly those three lines:

- `:2164` — `generation_date = generated_at[:10]` (the string handed to `get_pitching_workload`; the 7-day `pitches_7d` window)
- `:2197` — `reference_date=date.fromisoformat(generated_at[:10])`
- `:2217` — `reference_date=date.fromisoformat(generated_at[:10])`

**Locate the sites by symbol (`generated_at[:10]`), not by line number.** AC-2's grep-audit for zero surviving `generated_at[:10]` occurrences is unaffected and remains the mechanical guard. This correction is itself an instance of the epic's standing lesson: a spec authored against one tree state cites a middle term — four staged-but-uncommitted stories — that the reader cannot see.

## Description
After this story is complete, report generation derives its venue-local reference date ONCE through the operating-timezone seam and passes it to all three consumers, so evening report generations no longer compute pitcher rest days and the 7-day rolling pitch-count window against tomorrow's UTC date.

## Context
This is the third, orphaned site of the systemic UTC-date finding whose other two sites E-252 (morning-run target date) and E-253 (stored `game_date`) already fixed. The rest-day reference date fell between those two epics and was never corrected. **Three UTC call sites, not one** — `generator.py:2378` (the 7-day rolling `pitches_7d` window), `:2411`, and `:2431` — and the partial fix is the *likely* failure: fix two, miss `:2378`, and the printed reference date is correct and the headline invariant passes green while the workload window stays silently broken. The canonical seam is `derive_local_date()` in `src/util/timezone.py` (the same converter E-253-04 relocated for cross-layer reuse).

## Acceptance Criteria
> **AMENDED IN PLACE 2026-07-09 (PM).** Original text preserved struck-through as the record of what was specified; **amended text is authoritative.** Corrections: the line numbers were stale (story 04 moved 675 lines out of `generator.py`), and there were **four** consumers, not three.

- [x] **AC-1** (amended): Given report generation, when this story is complete, then the venue-local reference date is derived ONCE via `derive_local_date()` (`src/util/timezone.py`), bound to a single variable, and passed to **all four consumers** — located by symbol (`generated_at[:10]`), ~~not by line (`generator.py:2378`/`:2411`/`:2431` — stale)~~. No consumer site re-derives the date. The fourth consumer is the render dict's `"generation_date"` (`generator.py:2336`), which **stores** the value rather than using it on the line, and so was invisible to the pattern that produced this list.
- [x] **AC-2**: Given the generator module, when this story is complete, then a grep for `generated_at[:10]` (the UTC-slice pattern) returns **zero** surviving occurrences in `generator.py` — the caller-audit check that catches the partial fix. **⚠️ RECORDED DEFECT (do not copy this AC's shape):** this grep also *produced* the story's consumer list, so guard and target shared identical blind spots and a clean result was guaranteed for exactly the sites the grep could see. It missed the fourth consumer and all five Jinja sites. **The enumeration and the guard must have independent origins.**
- [x] **AC-3** (amended): Given an evening report generation (a `generated_at` UTC timestamp that has rolled past local midnight), when the report is produced, then the reference date, the pitcher rest-day math, and the 7-day `pitches_7d` window all use the venue-local date, verified by a test that pins a late-UTC `generated_at` and asserts the local date is used at **each consumer independently** ~~(at all three consumers)~~ — one falsifying mutant per consumer, each caught alone.
- [ ] **AC-4**: Given `bb report generate`, when a report is generated successfully, then the command prints the reference date it used — otherwise Step 1d's headline invariant (`reference_date` == today in operating tz) is unassertable.
- [ ] **AC-5** (PM-routed during dispatch, surfaced by story 02's ruff capture): Given the dead assignment `latest_game_date = all_dates[-1] if all_dates else ""` at **`src/reports/starter_prediction.py:1127`** — whose comment reads *"Latest game date for rest calculations"* though every rest calculation in that module anchors on the caller-supplied `reference_date` (`:456`, `:581`, `:664`, `:683`, `:995`) — when this story is complete, then that line has been **judged, not merely deleted**, and the judgment is recorded in the completion report. It is plausibly the vestige of an intended fix for the very bug this story corrects. **Decision rule**: if the rest anchor SHOULD be the latest game date rather than the report's reference date, that is a **finding to escalate to PM, not to fix here** (it changes coaching output and needs baseball-coach input). If the reference date is the correct anchor, say so explicitly and leave the line for story 08's ruff pass to remove as dead. Either way, do not delete it silently — this story is the last reader with the context to interpret it, and story 08 (which runs after) would see only an F841.

## Technical Approach
Depends on story 04 (same file; the settled `generator.py` structure and the public `utcnow_iso`). Derive once, pass down; do not re-derive at any consumer. The caller-audit AC (grep for `generated_at[:10]`) is the mechanical guard against the partial fix — a reviewer confirms zero surviving occurrences. AC-4's printed reference date is consumed by the Step 1d smoke (story 11); coordinate the exact output shape with that story so the invariant is assertable.

**Type note (SE):** `derive_local_date()` returns a `"YYYY-MM-DD"` **string**, not a `date`. The three consumers differ: `:2378`'s `get_pitching_workload` takes the string directly (the 7-day window is SQL `date(ref, '-6 days')`), while `:2411`/`:2431` compute date arithmetic and so wrap the string in `date.fromisoformat(...)`. Bind the single derived string once; each consumer adapts it as needed — do NOT derive twice to get one string and one `date`.

## PM RULING — the template date skew (2026-07-09)
**Option (a): WIDEN story 05. Fix the two template sites now. No baseball-coach consultation required.** SE was right to escalate, and right not to touch them unasked.

**New AC-6**: in `src/api/templates/reports/scouting_report.html`, the two sites still rendering a UTC date must render the venue-local `generation_date`, preserving their existing formatting exactly:
- `:498` — `<div class="report-date">{{ generated_at[:10] ... }}</div>` (the header date the coach reads first)
- `:865` — footer `Generated {{ generated_at[:10] ... }}`

Keep the `if ... else ""` guards. **Do not** apply `format_date` at either site (both render raw ISO by design). **Do not** touch `expires_at[:10]` at `:865` — an expiry is a UTC instant, not a venue-local game-day anchor, and it carries no "Generated" label to disagree with.

**Why (a), and why this is not a coaching decision.** PM read the template. The coach sees the word "**Generated**" **three times** (`:665`, `:855`, `:865`) plus a header date at `:498`. After this story, two say `2026-07-09` and two say `2026-07-10`. **A report that disagrees with itself about the day it was generated is worse than one that is uniformly wrong** — a uniform error is invisible, while a skew tells the coach the report is broken and gives no way to know which half to trust.

The *value* is not an open question: venue-local is the anchor this entire story establishes, and CLAUDE.md's Data Philosophy already requires freshness be presented in the coach's terms, not the system's. Applying that anchor at the sites that display it is **executing the story's premise, not making a new coaching decision**. Baseball-coach would be consulted if we were changing *what* is displayed or *how*; we are changing neither — label, format, and placement are untouched.

Option (c) is wrong: reverting to uniformly-UTC preserves the exact defect this story exists to fix (rest days and the `pitches_7d` window inflated after ~19:00 local). Option (b) is wrong: the skew did not pre-exist — **story 05 created it** — and shipping a self-contradicting report to close a story faster is the trade this project's core principle forbids. It is two lines.

**Captured, not chased**: `admin/reports.html:143-144` renders `generated_at[:10]` in the operator's report list — an operator surface showing a generation *timestamp*, disagreeing with nothing beside it. Leave it. `:855`'s UTC fallback is now provably unreachable (SE) — dead but harmless, and templates lie outside ruff's reach, so it is nobody's story. Note and move on.

## PM AC-Verification (2026-07-09)
**AC-1, AC-2, AC-3, AC-4, AC-5 PASS. AC-6 pending (the ruling above).**

- **AC-1 PASS.** Derived once at `generator.py:2163-2165` via `derive_local_date(generated_at, get_operating_timezone().key)` with a venue-local `operating_today()` fallback — never a UTC slice. `reference_date_local = date.fromisoformat(reference_date)` (`:2170`) adapts the single derivation rather than repeating it. SE: *"Re-introducing a slice as the fallback would be the bug wearing a `try`."*
- **AC-2 PASS.** Zero `generated_at[:10]` in `generator.py` (PM grep). SE's AST audit by *derivation* rather than spelling — subscripts, `.split()`, `date.today`, `.utcnow()`, every `fromisoformat` and `derive_local_date` argument — is stronger than the AC required. **Its stated blind spot is the right one to state: Jinja templates are structurally invisible to both grep and AST.** That is SE's own rule applied to SE's own audit, and it is what produced the escalation.
- **AC-3 PASS, and it is the story's real deliverable.** Four independent mutants, each reintroducing `generated_at[:10]` at **exactly one consumer**, each caught alone (RC=1); pristine restored (RC=0); all on a shadow copy outside the worktree. The named failure — fix two, miss the third, printed date correct while the workload window stays broken — cannot fail a test unless someone writes the test. Someone wrote four.
- **AC-4 PASS.** `  Reference date: YYYY-MM-DD` on the `ready` branch, with a companion test asserting the line is **omitted** when absent — so Step 1d can never assert against a trailing `Reference date: `.
- **AC-5 SETTLED — PM's hypothesis was wrong, and the AC still earned its place.** PM guessed `latest_game_date` was *the vestige of an intended fix*. It is **the residue of a fix that already happened**: `83b5458 feat(E-214): fix predicted starter rest day anchoring` replaced it with `reference_date` at every rest site, changed the parameter type, and **left the producing assignment behind**. `TestReferenceDateAnchorsReasoning` already pins the corrected behavior with a falsifying input (asserts "9 days rest"; anchoring on `latest_game_date` yields 3). `reference_date` **is** the correct anchor — no escalation, no baseball-coach. The comment *"Latest game date for rest calculations"* describes pre-E-214 behavior and is false. **AC-5 was still right to exist**: it forced a judgment, and the judgment produced a citation instead of a shrug.
  - **Handoff to story 08 that ruff cannot supply**: `all_dates` (`:1126`) exists *only* to feed `latest_game_date` (`:1127`). Removing `:1127` alone makes `all_dates` dead in turn. Both lines and the stale comment go together — ruff would otherwise flag them one round at a time.

**The spec named three consumers. There were four.** `generator.py:2336` stores `"generation_date": reference_date` into the render dict — the coach-facing "Generated \<date\>" annotation. Deleting the variable raised `NameError`. AC-2's grep would have returned **zero** while the report still showed an inconsistent date. SE: *"The spec enumerated the ones that matched `generated_at[:10]` on the line where the value was **used**, and missed the one where it was **stored into a dict**."* Eleventh undercount, and the purest instance yet: **the list was bounded by the pattern that produced it.**

## PM AC-6 Verification (2026-07-09)
**AC-6 PASS. All six ACs pass.** PM read `src/api/templates/reports/scouting_report.html` directly:

- `:498` → `{{ generation_date if generation_date else "" }}` — venue-local, guard kept, **no `format_date`**.
- `:865` → `Generated {{ generation_date if generation_date else "" }}{% if expires_at %} &middot; Expires {{ expires_at[:10] }}{% endif %}` — venue-local, guard kept, no `format_date`, **`expires_at[:10]` untouched**.
- `:665` and `:855` unchanged. All four "Generated" renderings agree.

**`generated_at` now appears exactly once in the template — inside `:855`'s provably-unreachable fallback.** The coach-facing template has no reachable UTC slice left. SE's compression of the ruling is the keeper: *"The `expires_at` carve-out is the whole ruling in one line: this story corrects a **game-day anchor**, not every UTC slice in sight."*

**AC-2's audit re-confirmed against its own blind spot.** Its AST sweep could not see Jinja; PM checked that surface by hand, and SE closed it with two more independent falsifiers (header and footer reverted separately, each CAUGHT). **Six consumers, six independent falsifiers.**

**PM ruling — do NOT split the four AC-3 assertions into four tests.** CR is right that pytest stops at the first failure, so a two-consumer mutant reports only the earlier one. That costs *diagnostics*, not *safety*: such a regression still fails, still blocks, and the second failure surfaces on the next run. The property AC-3 requires — each single-consumer mutant caught by its own assertion — holds as written and was proven six times. Splitting buys blast-radius visibility for a failure mode that is already self-correcting and cannot ship silently. Leave it.

**The template fix surfaced a third instance of the epic's pattern, this time in test data.** `test_report_renderer.py::TestCompleteReport::test_produces_html_with_all_sections` failed: its fixture `_make_full_data` — docstring *"Build a complete report data dict"* — **omits `generation_date`**, and had been passing only because the footer sliced `generated_at`. SE verified `render_report` has exactly one production caller, which always sets it, then fixed the **fixture**, not the assertion. SE: *"a test whose data was bounded by what the old code happened to read."* Same shape as the `NameError` on the fourth consumer.

**CR's honest-form correction, adopted**: `:855`'s fallback is dead **on every production path**, but reachable from a test passing a dict without the key. *"Dead code in production, not dead code absolutely — which is the honest form of the claim."*

**The closed-loop failure — SE's sharpening, and the one that indicts the spec author.** PM wrote that AC-2's blind spot was *assumed* to fall outside the failure space. SE corrected the diagnosis: **AC-2's grep produced the story's site list.** The spec did not independently enumerate three consumers and then pick a grep to verify them — *the grep **was** the enumeration.* Guard and target therefore shared identical blind spots, and a clean result was **guaranteed for exactly the sites the grep could see**. This is distinct from "a method has a blind spot": it is a method that **defined the target it later verifies** — the `x == x` tautology at spec-authoring altitude, and it cannot fail. **PM checklist form: the enumeration and the guard MUST have independent origins.** Ask not *"is this check good?"* but *"did this check also write the list it is checking?"* — when it did, a green result carries no information.

## Dependencies
- **Blocked by**: E-256-04 (same file; settled structure + `utcnow_iso`)
- **Blocks**: E-256-11 (Step 1d asserts on the printed reference date)

## Files to Create or Modify
- `src/reports/generator.py`
- `tests/test_report_generator.py` (or the appropriate report test file) — the late-UTC fixture test
- Possibly `src/cli/report.py` (the `bb report generate` reference-date print, AC-4)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-256-11**: the `bb report generate` printed reference date that Step 1d's headline invariant asserts (`reference_date` == today in operating tz).

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing (late-UTC fixture + grep-audit)
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
The 7-day window uses `date(ref, '-6 days')` inclusive semantics (`.claude/rules/data-model.md`); the fix corrects the `ref` value, not the window arithmetic.
