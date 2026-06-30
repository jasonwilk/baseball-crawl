# E-249: Player-Dedup Stale-Worklist Fix (connected-components, no-cross-merge)

## Status
`READY`
<!-- Lifecycle: DRAFT → READY → ACTIVE → COMPLETED (or BLOCKED / ABANDONED) -->

## Overview
Fix a confirmed data-correctness bug in same-team player deduplication: the merge worklist is computed up front and then iterated serially while each merge DELETEs a player, so the worklist goes stale. This produces a cascade of caught `PlayerMergeError`s and leaves residual duplicate players (split/halved stat lines, phantom roster entries) in opponent scouting reports. The fix replaces the stale-worklist orchestration with per-roster connected-components grouping that collapses unambiguous components and **refuses ambiguous forks** — closing the cascade and the latent silent-cross-merge risk in one change. **Coaching guarantee:** this epic closes the silent mis-merge this bug could cause — a short-name entry (like an initial "O") ambiguously matching two different full names and having its stats folded into the wrong player. That class of confidently-wrong attribution no longer happens. (One narrower, pre-existing case is NOT yet addressed: when one player's full name is a strict prefix of another's — e.g. "Alex" and "Alexa" on the same roster — the system may still absorb one player's stats into the other's line. That limitation predates this fix and is tracked for Tier 2 / IDEA-089.)

## Background & Context
Surfaced during a live report-generation scan for `public_id=wW5cdZlmYxIS` (`team_id=196`) on 2026-06-30: the load completed cleanly (loaded=644, errors=0) but post-load validation logged "expected 19 roster entries for team_id=196, found 51 in DB" plus ~15-20 `ERROR [src.db.player_dedup] dedup_team_players: failed to merge X into Y` / `PlayerMergeError: Canonical/Duplicate player '…' not found`. The errors are caught and non-fatal — the report still generated — but the underlying duplicates are only partially resolved.

**Root cause (confirmed by data-engineer):** `find_duplicate_players` (`src/db/player_dedup.py:54-197`) computes the ENTIRE pair list up front via a roster self-join with prefix-matching detection. Two consumers then iterate that FROZEN list serially:
- **Load path** — `scouting_loader.py:253-268` (Hook 1) → `dedup_team_players` (`player_dedup.py:780-868`).
- **CLI** — `bb data dedup-players` (`src/cli/data.py:106-188`) inlines its OWN `find_duplicate_players` + `merge_player_pair` loop (it does not call `dedup_team_players`, but shares the two defective primitives).

Each successful `merge_player_pair` ends with `DELETE FROM players WHERE player_id = ?`, but the worklist is never re-resolved against the mutated table. For a prefix-connected component the self-join emits all `C(n,2)` edges; serial processing deletes intermediate players, so later edges referencing a deleted player hit the up-front existence guards in `merge_player_pair` (`:432-444`) and raise `PlayerMergeError`.

**Failure modes:**
- **Total chains** (O⊂Oli⊂Oliver) still fully collapse — the failing edges are redundant; harmless noise.
- **Branching/fork components** leave RESIDUAL DUPLICATES (Mode A): a human split across two `players` UUIDs → two `player_season_batting`/`player_season_pitching` rows → split/halved stats and a phantom extra player in the report (the 51-vs-19 symptom).

**The load-bearing-edge reframe (why a naive fix is UNSAFE):** the current code's FAILING redundant edge is *accidental* protection against cross-merge. Today, for "O" prefixing both "Oliver" and "Owen", `O→Oliver` succeeds (O deleted), then `O→Owen` fails → Oliver and Owen are never cross-merged. A naive worklist fix (union-find OR a chase-to-survivor map) REMOVES that protection and actively INTRODUCES a silent cross-merge (Mode B): two distinct humans collapsed into one, the wrong kid's stats absorbed into a named player. Prefix matching alone CANNOT distinguish "Jo/John/Jon = one human" from "O/Oliver/Owen = two humans" — they are the identical structure; only same-game co-occurrence carries that signal. So the fix must *replace* the accidental protection with a deliberate one: refuse to merge ambiguous forks.

**Coaching impact (baseball-coach, advisory):** Mode B (silent mis-merge into a named player) is the trust-killer — coaches make real pitch-around / lineup / matchup decisions off confidently-wrong stat lines and never see the error. It must NOT be deferred. Mode A (visible phantom/split) is self-revealing (a coach sees too many names and discards the report) and operator-recoverable; tolerable for one tracked follow-up sprint. Recommendation: close Mode B in this epic; recover the remaining same-human residuals (Mode A) in the Tier 2 follow-on (IDEA-089).

This is a CONFIRMED bug fix, not a feature. Two experts converged on the scope (data-engineer on the mechanism and fork-refusal rule, baseball-coach on the impact ordering); the user resolved the one open question (refused forks emit WARN-level logs only on both paths; no new durable store).

## Goals
- Eliminate the stale-worklist `PlayerMergeError` cascade: a prefix-connected component never produces a caught-and-logged merge error from a redundant edge.
- Fully collapse every unambiguous (single-terminal) component to one canonical player with combined stat totals, on BOTH the load path and the CLI.
- Introduce NO NEW cross-merge mode: the fix must never collapse two distinct humans through fork-shaped ambiguity — any component with ≥2 terminals with distinct names (a fork) is refused (left entirely unmerged) and emits a WARN log, per Technical Notes (TN-1, TN-3) — while equal-named maximal members (same-human cross-perspective duplicates) still collapse. (Scope honesty: this does NOT eliminate the PRE-EXISTING strict-prefix linear-chain merge — e.g. "Alex"⊂"Alexa" — which is unchanged by this epic and deferred to Tier 2 / IDEA-089; see Non-Goals.)
- Preserve all existing merge invariants: provenance-aware season-row handling (E-237), per-merge FK/conflict mechanics, perspective-provenance, and the `recompute_aggregates` ownership contract (E-237 TN-11).
- Consolidate detection + component planning + fork refusal into ONE shared unit consumed by both the load-path orchestrator and the CLI (the CLI stops re-inlining a parallel merge loop).

## Non-Goals
- **Tier 2 — co-occurrence fork disambiguation (IDEA-089):** auto-collapsing GENUINE same-human forks (Jo/John/Jon) using same-game co-occurrence between component terminals is explicitly OUT of scope. This epic refuses ALL forks conservatively. As a consequence, **this epic does NOT promise the 51→19 symptom fully resolves**: on teams with genuine same-human forks, those residuals deterministically PERSIST as refused, visible duplicates (a coach reading the report still sees the inflated roster count and the extra names; the operator additionally sees a WARN log) until Tier 2 ships. This epic must not be read as a complete symptom fix.
- **Perfect prefix detection:** the fork rule prevents the fix from INTRODUCING new cross-merges; it does NOT make prefix-matching detection perfect. A true two-human *linear chain* (e.g. "Alex"⊂"Alexa", single terminal) still collapses — a PRE-EXISTING detection limitation, not introduced here, and also addressed by Tier 2 (IDEA-089).
- **Durable/queryable operator surfacing** of refused forks (a review table, report-run-record fields, admin UI). Per the user decision, Tier 1 is WARN-log-only on both paths; durable surfacing folds into IDEA-089.
- **Live-data remediation.** Re-running dedup against the production DB to clean up the existing `team_id=196` residuals is a post-merge OPERATOR follow-up (needs credentials + the live DB, not available in an epic worktree) — see History / operator note, mirroring the E-245 precedent. It is not a dispatchable story.
- Changing the detection *signal* (prefix matching + matching last name) or the canonical-selection *tiebreak* rules (longer first_name → stat count → alphabetical) beyond what the per-component canonical choice requires.

## Success Criteria
- Running dedup over a roster fixture containing a total chain, a single-stub pair, and a fork: the chain and the stub fully collapse to one canonical each; the fork is left untouched with all its members surviving as distinct `players` rows; zero `PlayerMergeError`s are raised/caught for redundant edges.
- The fork's two distinct-human terminals (Oliver, Owen) remain separate `players` rows after dedup — proven by a no-cross-merge assertion.
- Season aggregates are correct after dedup over a POPULATED fixture whose stored aggregate deliberately disagrees with the per-game sum (E-247 corollary — the aggregate test has teeth): a collapsed component yields one combined `player_season_*` line; `verify-aggregates` reports no mismatch attributable to the merge.
- Both the load path (`dedup_team_players`) and the CLI (`bb data dedup-players`) route through the single shared component-planning unit; the CLI no longer contains a parallel inline `find_duplicate_players` + merge loop.
- Refused forks emit a WARN-level log line on both paths.
- Full test suite passes with no regressions; provenance-aware season handling (E-237) and the `recompute_aggregates` ownership contract are unchanged.

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-249-01 | Connected-components dedup with fork refusal (core fix + fixture suite) | TODO | None | - |
| E-249-02 | CLI delegation to shared planner + refused-fork WARN surfacing | TODO | E-249-01 | - |

## Dispatch Team
- data-engineer
- software-engineer

## Technical Notes

### TN-1 — Component model and the collapse/refuse decision
Within a single `(team_id, season_id)` roster, the detected prefix pairs form an undirected graph whose vertices are `player_id`s. Group the vertices into connected components (every pair-edge joins its two endpoints). For each component:
- A **terminal** is a member whose first_name is NOT a strict prefix of any other member's first_name in the component (the maximal name(s) under the prefix partial order). All name comparisons here are case-insensitive, mirroring the detection query's `COLLATE NOCASE` (`player_dedup.py:122-133`).
- **DISTINCT-name test (load-bearing — see Background "identical-name" note below):** a fork is decided on whether the terminals have **DISTINCT (case-insensitively unequal) names**, NOT merely on the count of terminal `player_id`s. Equal-named maximal members (the same full first+last name under two different UUIDs — the bread-and-butter cross-perspective duplicate) are the SAME human and MUST collapse together, never refuse.
- **Single-terminal-NAME component** (chain, single stub, OR a set of equal-named maximal members): every other member is a prefix-ancestor of — or case-insensitively equal to — the maximal name. COLLAPSE — pick the canonical per TN-2 canonical selection and merge every other member directly into it.
- **Fork** (≥2 terminals with mutually-DISTINCT names — e.g. O→Oliver + O→Owen): REFUSE — leave every member of the component unmerged, and emit a WARN log naming the component (per TN-3). Refusing the whole component (not just the ambiguous edges) is the safe choice: the shorter shared stub is the ambiguity source and cannot be safely assigned to either distinct terminal.

This rule is the deliberate replacement for the accidental no-cross-merge protection described in Background. It guarantees two DISTINCT-human terminals are never collapsed — while still collapsing equal-named same-human duplicates (the regression Finding 1 guards against: a `{Jon, Jon}` two-UUID pair currently collapses via the existing tiebreak and MUST continue to; classifying it as a fork because both are non-strict-prefix "terminals" would turn a currently-fixed duplicate into a refused residual, making the symptom worse, not better).

### TN-2 — Canonical selection per component
The canonical for a collapsed component is selected by the EXISTING tiebreak precedence already implemented in `_select_canonical_player` (`player_dedup.py:200-231`): longer first_name wins → more total stat rows → alphabetically lower `player_id`. For a single-terminal-name component the terminal is the longest name and wins on the first criterion; the stat-count / alphabetical tiebreaks apply only among equal-length names (which is exactly how the canonical is chosen between equal-named maximal members per TN-1). Do not invent a new selection *rule* — apply the same precedence per component. **Implementation note:** `_select_canonical_player`'s signature is strictly PAIRWISE (`pid1, fname1, pid2, fname2, stat_counts`) — "extend it to operate per component" means write an N-way reducer that applies the SAME precedence across all component members, not call the pairwise function as a drop-in.

### TN-3 — Refused-fork logging (user decision)
When a component is refused as a fork, emit ONE WARN-level log line per refused component on BOTH the load path and the CLI execute path, identifying the team and the conflicting terminal names so an operator can review. WARN-log-only is the explicit user decision for Tier 1 — do NOT add a new table, column, or persisted record (durable surfacing is deferred to IDEA-089). The CLI dry-run output should also surface refused forks in its preview so the operator sees them before executing.

### TN-4 — Shared planning unit (de-dup the dedup)
The component-grouping + collapse/refuse decision + per-component canonical selection MUST live in ONE shared unit in `src/db/player_dedup.py`, consumed by BOTH `dedup_team_players` (load path) and the `bb data dedup-players` CLI. The CLI MUST stop re-inlining its own `find_duplicate_players` + merge loop (`cli/data.py:106-188`). The shared unit should emit a plan — the set of `(canonical, [duplicates])` collapses plus the list of refused forks — that the CLI can render in dry-run and execute, and that `dedup_team_players` can execute directly. The exact factoring (new function name, return dataclass shape) is the implementer's decision; the constraint is single-source, no parallel loop. This follows the canonical-function and "prevention over cleanup" patterns in CLAUDE.md.

### TN-5 — Invariants that MUST be preserved (no regressions)
1. **Provenance-aware season handling (E-237):** every component merge routes season-row handling through the existing `_delete_or_repoint_season_rows` (`player_dedup.py:713-772`). Member `full`/`supplemented` rows must be preserved/re-pointed, never deleted or downgraded to a boxscore sum. See `.claude/rules/data-model.md` (Season-Aggregate Parity, "Mixed-provenance scope invariant").
2. **Per-merge mechanics:** reuse `merge_player_pair`'s existing FK-reassignment and delete-or-update conflict handling (`_delete_or_update_game_stats`, `_delete_or_update_recon`, `_delete_or_update_rosters`). This epic changes the ORCHESTRATION / worklist, not the per-merge internals.
3. **One transaction per component (SHOULD; footgun):** a component's merges should run under a single transaction/savepoint so a component collapses atomically (all-or-nothing), consistent with the existing `manage_transaction` / SAVEPOINT pattern. **Footgun:** per-component atomicity requires the component EXECUTOR to own the transaction/savepoint and call `merge_player_pair(..., manage_transaction=False)` (inner SAVEPOINTs nest fine). `merge_player_pair(..., manage_transaction=True)` — the CLI's current default at `cli/data.py` — does its OWN `BEGIN IMMEDIATE … COMMIT` per merge and CANNOT be wrapped in an outer per-component `BEGIN` (SQLite has no nested `BEGIN`); naively keeping `manage_transaction=True` either loses atomicity or raises a nested-BEGIN error. The load path already passes `manage_transaction=False` (inside ScoutingLoader's open txn), so only the CLI path changes here. This is a "should" — a mid-component partial collapse is self-healing on re-run (the leftover members re-form a smaller single-terminal-name component), so it is a footgun to call out, not a correctness blocker.
4. **`recompute_aggregates` ownership (E-237 TN-11):** the load path passes `recompute_aggregates=False` (the end-of-load canonical recompute owns it); the CLI passes `True`. This contract is independent of `manage_transaction` and must be preserved.
5. **Perspective-provenance:** the overlap check (`_check_game_overlaps`) is already team- + perspective-scoped (E-220); preserve that scoping. See `.claude/rules/perspective-provenance.md`.

### TN-6 — Verification strategy
Characterization/behavioral tests must encode the component shapes below with `game_id` co-occurrence baked into the fixtures (co-occurrence is the signal that *distinguishes* same-human from two-human, and is what Tier 2 will key on — fixtures should make the distinction explicit even though Tier 1 refuses all forks):
- **(a) Total chain** O⊂Oli⊂Oliver → collapses to one canonical; combined stats; no errors.
- **(b) Single-stub pair / branching-same-target** Jo/John/Jon where only Jo→John and Jo→Jon edges exist → this is a FORK (John and Jon are distinct-named terminals) and is REFUSED in Tier 1. (Note: a true single-stub two-member pair Jo→John, no third member, is single-terminal → collapses. Include both a clean single-stub collapse AND the Jo/John/Jon fork-refusal case.)
- **(c) Stub-to-two-distinct** O→Oliver + O→Owen → REFUSED; Oliver and Owen remain distinct `players` rows (no-cross-merge assertion).
- **(d) Identical-name pair `{Jon, Jon}`** (same first+last name, two UUIDs — the cross-perspective duplicate) → COLLAPSES (canonical by the existing stat-count/alpha tiebreak). This fixture is the regression guard for TN-1 Finding 1: it FAILS if the fork rule is implemented on terminal *count* rather than terminal *distinct names*.
- **(e) Equal-named-under-a-longer-terminal `{Jon, Jon, Jonathan}`** → both Jons are strict prefixes of Jonathan → single terminal name → collapses all three into Jonathan.
- **No-PlayerMergeError-cascade assertion:** a multi-edge component (e.g. the total chain) produces zero caught merge errors.
- **Aggregate-parity-after-dedup:** per the E-247 corollary in `.claude/rules/data-model.md`, the aggregate test MUST seed a POPULATED state whose stored `player_season_*` deliberately DISAGREES with the per-game sum, then assert the post-dedup recompute yields the correct combined line — a fresh/empty DB gives the test no teeth.
- **Test scope discovery:** per `.claude/rules/testing.md`, grep `tests/` for every file importing `db.player_dedup` and run them all (changes to `find_duplicate_players` / merge orchestration ripple beyond the story-named tests).

## Open Questions
- None blocking. Open-question B from discovery (load-path fork surfacing) was resolved by the user: WARN-log-only on both paths, durable surfacing deferred to IDEA-089.

## History
- 2026-06-30: Created (DRAFT). Discovery: data-engineer confirmed the stale-worklist root cause and the load-bearing-edge reframe (a naive worklist fix would introduce a Mode-B cross-merge); baseball-coach ranked Mode B (silent mis-merge) as the must-not-defer trust-killer; user resolved the surfacing question (WARN-log-only, Tier 1). Tier 2 (co-occurrence auto-collapse + durable surfacing) split out to IDEA-089, cross-referenced from Non-Goals.
- 2026-06-30: **Data-engineering spec review incorporated.** DE (root-cause author) found one must-fix spec defect: the original TN-1 fork definition (terminal = non-strict-prefix; fork = ≥2 mutually-non-prefix terminals) misclassified identical-name two-UUID duplicate pairs (`{Jon, Jon}` — the bread-and-butter cross-perspective duplicate) as forks → would REFUSE a pair that currently collapses, regressing the symptom. TN-1 reworded to decide forks on terminals with **DISTINCT names** (equal-named maximal members collapse via the existing tiebreak); added regression-guard fixtures `{Jon, Jon}` and `{Jon, Jon, Jonathan}` (TN-6 (d)/(e), E-249-01 AC-3). Also folded in two footgun clarifications: TN-5.3 (per-component atomicity requires the executor to own the transaction and call `merge_player_pair(manage_transaction=False)` — `True` self-commits and can't nest under an outer BEGIN; only the CLI path changes) and TN-2 (`_select_canonical_player` is pairwise — "extend per component" means an N-way reducer, not a drop-in call). DE confirmed the rest faithful: connected-components-into-single-canonical structurally eliminates the stale-reference cascade and preserves no-cross-merge; E-237 provenance, per-merge mechanics, perspective scoping, recompute ownership, and the single-shared-planner all correctly carried over.
- 2026-06-30: **Operator follow-up (post-merge, not a story):** after this epic merges, re-run dedup against the production DB and inspect the `team_id=196` residuals to confirm the error cascade is gone and to count how many refused-fork residuals remain (input to validating IDEA-089). Requires credentials + live DB (unavailable in an epic worktree). Mirrors the E-245 operator-follow-up precedent.
- 2026-06-30: **Codex spec review (iter 1) incorporated + set READY.** Codex found 3 findings, all ACCEPTED: F-A (P1, internal over-claim — the positive coaching guarantee/Goals/E-249-01 Description promised "no stat line ever contains another player's stats" while Non-Goals disclose the pre-existing strict-prefix "Alex"⊂"Alexa" linear-chain merge still happens; reworded to the honest "closes the silent ambiguous-initial mis-merge / introduces no NEW cross-merge mode" with the residual disclosed — coach approved the bench-facing wording); F-B (P2 — TN-5.3's executor-owns-the-transaction / `manage_transaction=False` constraint had not propagated to E-249-02; added AC-6 + Technical Approach line + a no-nested-transaction test); F-C (P2 — E-249-02 test scope broadened to the full CLI import surface per testing.md, since `src/cli/__init__.py` imports `data` at module load + the subprocess convention tests). Post-incorporation consistency sweep clean.

### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iter 1 — CR spec audit | 1 | 1 | 0 |
| Internal iter 1 — Holistic (DE) | 4 | 4 | 0 |
| Internal iter 1 — Holistic (coach) | 2 | 2 | 0 |
| Codex iter 1 | 3 | 3 | 0 |
| **Total** | **10** | **10** | **0** |

Convergence note: the identical-name fork-misclassification MUST-FIX was raised INDEPENDENTLY by three passes — CR spec audit (its sole finding F1), DE holistic (its Finding 1), and counts once each per-pass above; it is ONE underlying defect surfaced by multiple reviewers, not three distinct defects. Likewise Codex F-A is the over-claim that DE/coach's scope-honesty work had narrowed in the Non-Goals but left live in the Overview/Goals. Zero findings dismissed across all passes.
